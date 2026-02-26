# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""HAL Tracking Example (Zenoh + HAL).

Subscribes to Zenoh topics (e.g. `rt/camera/h264`) to decode frames, run YOLO
inference, and track detections across frames. Results are visualized in Rerun.

Features:
- H.264 video decoding and preprocessing using edgefirst_hal
- YOLO inference for object detection
- Object tracking with persistent IDs across frames
- Visualization with Rerun for debugging
- Zenoh integration for distributed systems

The tracker maintains object identities using simple centroid tracking,
which is suitable for real-time edge applications. More sophisticated
tracking algorithms (Kalman filtering, Hungarian algorithm) can be
integrated as needed.
"""

import asyncio
from typing import Union
from argparse import ArgumentParser
from pathlib import Path
import io
import os
import sys
import threading

import av
import numpy as np
import rerun as rr
import rerun.blueprint as rrb
import zenoh

import edgefirst_hal as ef

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.hal_onnx import HALONNXRunner
from utils.hal_tflite import HALTFLiteRunner


# Shared storage for latest decoded frame
latest_frame_lock = threading.Lock()
latest_frame = None
frame_available_event = threading.Event()

# Track state configuration
MAX_DISTANCE = 0.15  # Maximum normalized distance for track association
MAX_FRAMES_WITHOUT_UPDATE = 10  # Frames before dropping a track


class TrackState:
    """Maintains state for a single tracked object."""

    def __init__(self, track_id, label, center_x, center_y):
        self.track_id = track_id
        self.label = label
        self.center_x = center_x
        self.center_y = center_y
        self.frames_without_update = 0
        self.color = list(np.random.choice(range(256), size=3))
        self.detection_history = [(center_x, center_y)]

    def update(self, center_x, center_y):
        """Update track with new detection."""
        self.center_x = center_x
        self.center_y = center_y
        self.frames_without_update = 0
        self.detection_history.append((center_x, center_y))
        # Keep last 30 frames of history
        if len(self.detection_history) > 30:
            self.detection_history.pop(0)

    def age_without_update(self):
        """Age the track (called every frame with no matching detection)."""
        self.frames_without_update += 1

    def is_active(self):
        """Check if track should still be maintained."""
        return self.frames_without_update < MAX_FRAMES_WITHOUT_UPDATE

    def get_short_id(self):
        """Get shortened ID for display."""
        return self.track_id[:8] if self.track_id else "unknown"


class SimpleTracker:
    """Centroid-based object tracker for real-time edge applications."""

    def __init__(self):
        self.tracks = {}
        self.next_id = 0

    def distance(self, p1, p2):
        """Normalized Euclidean distance between two points."""
        dx = p1[0] - p2[0]
        dy = p1[1] - p2[1]
        return np.sqrt(dx * dx + dy * dy)

    def update(self, detections):
        """
        Update tracks with new detections.

        Args:
            detections: List of (center_x, center_y, label) tuples in normalized coordinates

        Returns:
            List of (track_id, label, center_x, center_y) tracked objects
        """
        # Age existing tracks
        for track in self.tracks.values():
            track.age_without_update()

        # Match detections to existing tracks
        matched_detections = set()
        for track_id, track in list(self.tracks.items()):
            if not track.is_active():
                del self.tracks[track_id]
                continue

            best_distance = MAX_DISTANCE
            best_idx = -1

            # Find closest detection
            for i, (cx, cy, label) in enumerate(detections):
                if i in matched_detections:
                    continue

                dist = self.distance(
                    (track.center_x, track.center_y), (cx, cy))
                if dist < best_distance:
                    best_distance = dist
                    best_idx = i

            # Update track if match found
            if best_idx >= 0:
                cx, cy, label = detections[best_idx]
                track.update(cx, cy)
                track.label = label
                matched_detections.add(best_idx)

        # Create new tracks for unmatched detections
        for i, (cx, cy, label) in enumerate(detections):
            if i not in matched_detections:
                track_id = f"track_{self.next_id:06d}"
                self.next_id += 1
                self.tracks[track_id] = TrackState(track_id, label, cx, cy)
                matched_detections.add(i)

        # Return active tracks
        return [
            (track.track_id, track.label, track.center_x, track.center_y, track.color)
            for track in self.tracks.values()
            if track.is_active()
        ]


class FrameSize:
    """Async event for frame size synchronization."""

    def __init__(self):
        self._size = []
        self._event = asyncio.Event()
        self.raw_data = io.BytesIO()
        self.tensor_image = None

    def set(self, width, height):
        self._size = [width, height]
        if not self._event.is_set():
            self._event.set()

        self.tensor_image = ef.TensorImage(
            width,
            height,
            ef.FourCC.RGB
        )

    async def get(self):
        await self._event.wait()
        return self._size


class MessageDrain:
    """Async queue for Zenoh messages with automatic overflow handling."""

    def __init__(self, loop):
        self._queue = asyncio.Queue(maxsize=100)
        self._loop = loop

    def callback(self, msg):
        if not self._loop.is_closed():
            if self._queue.full():
                self._queue.get_nowait()
            self._loop.call_soon_threadsafe(self._queue.put_nowait, msg)

    async def read(self):
        return await self._queue.get()

    async def get_latest(self):
        latest = await self._queue.get()
        while not self._queue.empty():
            latest = self._queue.get_nowait()
        return latest


def h264_handler_sync(drain, loop):
    global latest_frame
    decoder = av.CodecContext.create("h264", "r")

    while True:
        future = asyncio.run_coroutine_threadsafe(
            drain.get_latest(),
            loop
        )
        msg = future.result()
        packet = av.Packet(msg.payload.to_bytes())

        try:
            frames = decoder.decode(packet)
        except av.error.InvalidDataError:
            continue  # wait for valid keyframe

        for frame in frames:
            with latest_frame_lock:
                latest_frame = frame
            frame_available_event.set()


def inference_handler_sync(
    frame_storage: FrameSize,
    runner: Union[HALONNXRunner, HALTFLiteRunner],
    tracker: SimpleTracker
):
    global latest_frame
    while True:
        # Wait until a new frame is available
        frame_available_event.wait()
        with latest_frame_lock:
            frame_to_process = latest_frame
            latest_frame = None
            frame_available_event.clear()

        if frame_to_process is None:
            continue

        frame_array = frame_to_process.to_ndarray(format="rgb24")
        h, w = frame_array.shape[:2]
        frame_storage.set(w, h)

        # Use edgefirst_hal for image preprocessing
        # Create input tensor from frame
        frame_storage.tensor_image.copy_from_numpy(frame_array)
        # Run model inference
        boxes, scores, classes, masks = runner.static_infer(
            frame_storage.tensor_image)

        # Convert boxes to center coordinates and track
        detections = [((box[0] + box[2]) / 2.0,
                       (box[1] + box[3]) / 2.0,
                       f"class_{int(cls_id)}")
                      for box, cls_id in zip(boxes, classes)]

        # Update tracker
        tracked_objects = tracker.update(detections)

        runner.converter.render_to_image(
            runner.dst,
            bbox=boxes,
            scores=scores,
            classes=classes,
            seg=masks
        )

        with runner.dst.map() as m:
            n = np.array(m.view()).reshape((runner.dst.height,
                                            runner.dst.width, 4))
            n = n[:, :, :3]  # RGB
            n = np.ascontiguousarray(n, dtype=np.uint8)

            # Log frame and detections
            rr.log("/camera/frame", rr.Image(n))

        # Log tracked objects
        if tracked_objects:
            centers = []
            sizes = []
            labels = []
            colors = []

            for track_id, label, cx, cy, color in tracked_objects:
                # Convert to pixel coordinates for visualization
                px = cx * runner.input_shape[1]
                py = cy * runner.input_shape[0]

                # Assume ~5% of frame width for box size (adjust as
                # needed)
                box_width = runner.input_shape[1] * 0.05
                box_height = runner.input_shape[0] * 0.05

                centers.append((px, py))
                sizes.append((box_width, box_height))
                labels.append(f"{label}: {track_id[:8]}")
                colors.append(color)

            rr.log(
                "camera/tracked_objects",
                rr.Boxes2D(
                    centers=centers,
                    sizes=sizes,
                    labels=labels,
                    colors=colors
                ),
            )

        # Log tracker statistics
        rr.log(
            "tracker/active_tracks",
            rr.Scalars(len(tracker.tracks)),
        )
        rr.log(
            "tracker/detections_per_frame",
            rr.Scalars(len(detections)),
        )
        if len(tracked_objects) > 0:
            print(f"Frame: {len(detections)} detections, "
                  f"{len(tracked_objects)} active tracks")


def h264_worker(
    msg: zenoh.Sample, frame_storage: FrameSize,
    container: av.container.InputContainer,
    runner: Union[HALONNXRunner, HALTFLiteRunner],
    tracker: SimpleTracker
):
    """
    Decode H.264 video, run YOLO inference, and perform tracking.

    Uses edgefirst_hal for optimized image preprocessing.
    """
    try:
        frame_storage.raw_data.write(msg.payload.to_bytes())
        frame_storage.raw_data.seek(0)
        for packet in container.demux():
            try:
                if packet.size == 0:
                    continue
                for frame in packet.decode():
                    # Decode frame to RGB24
                    frame_array = frame.to_ndarray(format="rgb24")
                    frame_height, frame_width = frame_array.shape[:2]
                    frame_storage.set(frame_width, frame_height)

                    # Use edgefirst_hal for image preprocessing
                    # Create input tensor from frame
                    frame_storage.tensor_image.copy_from_numpy(frame_array)
                    boxes, scores, classes, masks = runner.static_infer(
                        frame_storage.tensor_image)

                    # tracked_objects = tracker.update(
                    #     boxes, scores, class_ids, time.time())

                    # Convert boxes to center coordinates and track
                    detections = [((box[0] + box[2]) / 2.0,
                                   (box[1] + box[3]) / 2.0,
                                   f"class_{int(cls_id)}")
                                  for box, cls_id in zip(boxes, classes)]

                    # Update tracker
                    tracked_objects = tracker.update(detections)

                    runner.converter.render_to_image(
                        runner.dst,
                        bbox=boxes,
                        scores=scores,
                        classes=classes,
                        seg=masks
                    )

                    with runner.dst.map() as m:
                        n = np.array(m.view()).reshape((
                            runner.dst.height, runner.dst.width, 4))
                        n = n[:, :, :3]  # RGB format
                        n = np.ascontiguousarray(n, dtype=np.uint8)

                        # Log frame
                        rr.log("camera/frame", rr.Image(n))

                    # Log tracked objects
                    if tracked_objects:
                        centers = []
                        sizes = []
                        labels = []
                        colors = []

                        for track_id, label, cx, cy, color in tracked_objects:
                            # Convert to pixel coordinates for visualization
                            px = cx * runner.input_shape[1]
                            py = cy * runner.input_shape[0]

                            # Assume ~5% of frame width for box size (adjust as
                            # needed)
                            box_width = runner.input_shape[1] * 0.05
                            box_height = runner.input_shape[0] * 0.05

                            centers.append((px, py))
                            sizes.append((box_width, box_height))
                            labels.append(f"{label}: {track_id[:8]}")
                            colors.append(color)

                        rr.log(
                            "camera/tracked_objects",
                            rr.Boxes2D(
                                centers=centers,
                                sizes=sizes,
                                labels=labels,
                                colors=colors
                            ),
                        )

                    # Log tracker statistics
                    rr.log(
                        "tracker/active_tracks",
                        rr.Scalars(len(tracker.tracks)),
                    )
                    rr.log(
                        "tracker/detections_per_frame",
                        rr.Scalars(len(detections)),
                    )
                    if len(tracked_objects) > 0:
                        print(f"Frame: {len(detections)} detections, "
                              f"{len(tracked_objects)} active tracks")

                frame_storage.raw_data.seek(0)
                frame_storage.raw_data.truncate(0)

            except Exception as e:
                print(f"Error processing packet: {e}")
                continue

    except Exception as e:
        print(f"Error in h264_worker: {e}")


async def h264_handler(
    drain: MessageDrain,
    frame_storage: FrameSize,
    runner: Union[HALONNXRunner, HALTFLiteRunner],
    tracker: SimpleTracker
):
    """Main handler for H.264 stream processing."""
    container = av.open(frame_storage.raw_data, format="h264", mode="r")

    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(
            target=h264_worker,
            args=[msg, frame_storage, container, runner, tracker],
        )
        thread.start()

        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


async def main_async(session: zenoh.Session,
                     runner: Union[HALONNXRunner, HALTFLiteRunner]):
    """Main async function."""

    # Initialize tracker
    tracker = SimpleTracker()
    # tracker = ef.ByteTrack()

    # Create async drains
    loop = asyncio.get_running_loop()
    h264_drain = MessageDrain(loop)
    frame_size_storage = FrameSize()

    # Subscribe to H.264 stream
    session.declare_subscriber("rt/camera/h264", h264_drain.callback)
    # Start decoder thread
    threading.Thread(target=h264_handler_sync,
                     args=(h264_drain, loop),
                     daemon=True).start()

    # Start inference thread
    threading.Thread(target=inference_handler_sync,
                     args=(frame_size_storage, runner, tracker),
                     daemon=True).start()
    # Keep running
    while True:
        await asyncio.sleep(0.001)


def main():
    """Entry point."""
    parser = ArgumentParser(
        description="EdgeFirst HAL Tracking Example - "
                    "Real-time object tracking with edgefirst_hal preprocessing"
    )
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        required=True,
        help="Path to YOLO ONNX or TFLitemodel file",
    )
    parser.add_argument(
        "-r",
        "--remote",
        type=str,
        default=None,
        help="Connect to the remote endpoint instead of local.",
    )
    # Rerun args
    rr.script_add_args(parser)
    args = parser.parse_args()

    # Setup Rerun visualization
    args.memory_limit = 10
    rr.script_setup(args, sys.argv[0])

    blueprint = rrb.Blueprint(
        rrb.Grid(
            contents=[
                rrb.Spatial2DView(origin="/camera", name="Camera Feed"),
                rrb.BarChartView(origin="/tracker", name="Tracker Stats"),
            ]
        )
    )
    rr.send_blueprint(blueprint)

    # Load YOLO model with ONNX Runtime
    if os.path.splitext(os.path.basename(args.model))[-1].lower() == ".onnx":
        runner = HALONNXRunner(args.model)
    elif os.path.splitext(os.path.basename(args.model))[-1].lower() == ".tflite":
        runner = HALTFLiteRunner(args.model)
    else:
        raise NotImplementedError(
            "Only ONNX and TFLite Ultralytics models are supported in this sample.")
    print(f"Loaded YOLO model from {args.model}")

    # Zenoh configuration
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote:
        # Ensure remote endpoint has tcp/ prefix
        remote = args.remote if args.remote.startswith(
            "tcp/") else f"tcp/{args.remote}"
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote}"]}}')
    session = zenoh.open(config)

    try:
        asyncio.run(main_async(session, runner))
    except KeyboardInterrupt:
        session.close()
        sys.exit(0)
    session.close()


if __name__ == "__main__":
    main()
