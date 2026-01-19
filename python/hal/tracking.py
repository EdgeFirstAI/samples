# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""
HAL Tracking Example

Demonstrates real-time object tracking using the edgefirst_hal library for 
image processing and YOLO model inference with object tracking.

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

from argparse import ArgumentParser
import asyncio
import io
import sys
import av
import zenoh
import threading
import onnxruntime as ort
import numpy as np
from collections import defaultdict
from edgefirst.schemas.edgefirst_msgs import Detect
import rerun as rr
import rerun.blueprint as rrb
import edgefirst_hal as ef


# Track state configuration
MAX_DISTANCE = 0.15  # Maximum normalized distance for track association
MAX_FRAMES_WITHOUT_UPDATE = 10  # Frames before dropping a track
CONFIDENCE_THRESHOLD = 0.25
NMS_THRESHOLD = 0.7
MAX_DETECTIONS = 50


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
        return np.sqrt(dx*dx + dy*dy)
    
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
                
                dist = self.distance((track.center_x, track.center_y), (cx, cy))
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
    
    def set(self, width, height):
        self._size = [width, height]
        if not self._event.is_set():
            self._event.set()
    
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


def h264_worker(msg, frame_storage, raw_data, container, ort_session, input_name, 
                tracker, visualization_enabled):
    """
    Decode H.264 video, run YOLO inference, and perform tracking.
    
    Uses edgefirst_hal for optimized image preprocessing.
    """
    try:
        raw_data.write(msg.payload.to_bytes())
        raw_data.seek(0)
        
        for packet in container.demux():
            try:
                if packet.size == 0:
                    continue
                
                raw_data.seek(0)
                raw_data.truncate(0)
                
                for frame in packet.decode():
                    # Decode frame to RGB24
                    frame_array = frame.to_ndarray(format="rgb24")
                    frame_height, frame_width = frame_array.shape[:2]
                    frame_storage.set(frame_width, frame_height)
                    
                    # Use edgefirst_hal for image preprocessing
                    # Create input tensor from frame
                    ef_input = ef.TensorImage(frame_width, frame_height, ef.FourCC.RGB)
                    ef_input.copy_from_numpy(frame_array)
                    
                    # Resize to YOLO input size (640x640) using hardware acceleration
                    ef_output = ef.TensorImage(640, 640)
                    converter = ef.ImageConverter()
                    converter.convert(ef_input, ef_output)
                    
                    # Extract resized image to NumPy
                    resized_array = np.zeros((640, 640, 3), dtype=np.uint8)
                    ef_output.normalize_to_numpy(resized_array)
                    
                    # Prepare input for YOLO (normalize to 0-1 range)
                    resized_array = np.transpose(resized_array, (2, 0, 1))
                    input_tensor = resized_array.astype(np.float32) / 255.0
                    input_tensor = np.expand_dims(input_tensor, axis=0)
                    
                    # Run YOLO inference
                    outputs = ort_session.run(None, {input_name: input_tensor})
                    predictions = outputs[0]
                    
                    # Use HAL decoder for YOLO output
                    boxes, scores, class_ids = ef.Decoder.decode_yolo_det(
                        predictions.squeeze(),
                        anchors=(0.0040811873, -123),
                        confidence_threshold=CONFIDENCE_THRESHOLD,
                        nms_threshold=NMS_THRESHOLD,
                        max_boxes=MAX_DETECTIONS,
                    )
                    
                    # Convert boxes to normalized coordinates and track
                    detections = []
                    for box, score, cls_id in zip(boxes, scores, class_ids):
                        x1, y1, x2, y2 = box
                        # Denormalize from 640x640 space
                        x1, x2 = x1 / 640.0, x2 / 640.0
                        y1, y2 = y1 / 640.0, y2 / 640.0
                        
                        # Center and size in normalized coordinates
                        center_x = (x1 + x2) / 2.0
                        center_y = (y1 + y2) / 2.0
                        label = f"class_{int(cls_id)}"
                        
                        detections.append((center_x, center_y, label))
                    
                    # Update tracker
                    tracked_objects = tracker.update(detections)
                    
                    # Visualization
                    if visualization_enabled:
                        # Log frame
                        rr.log("camera/frame", rr.Image(frame_array))
                        
                        # Log tracked objects
                        if tracked_objects:
                            centers = []
                            sizes = []
                            labels = []
                            colors = []
                            
                            for track_id, label, cx, cy, color in tracked_objects:
                                # Convert to pixel coordinates for visualization
                                px = cx * frame_width
                                py = cy * frame_height
                                
                                # Assume ~5% of frame width for box size (adjust as needed)
                                box_width = frame_width * 0.05
                                box_height = frame_height * 0.05
                                
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
                            rr.Scalar(len(tracker.tracks)),
                        )
                        rr.log(
                            "tracker/detections_per_frame",
                            rr.Scalar(len(detections)),
                        )
                    
                    # Optional: Log detected objects for debugging
                    if len(tracked_objects) > 0:
                        print(f"Frame: {len(detections)} detections, "
                              f"{len(tracked_objects)} active tracks")
            
            except Exception as e:
                print(f"Error processing packet: {e}")
                continue
    
    except Exception as e:
        print(f"Error in h264_worker: {e}")


async def h264_handler(drain, frame_storage, ort_session, input_name, 
                       tracker, visualization_enabled):
    """Main handler for H.264 stream processing."""
    raw_data = io.BytesIO()
    container = av.open(raw_data, format="h264", mode="r")
    
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(
            target=h264_worker,
            args=[msg, frame_storage, raw_data, container, ort_session, 
                  input_name, tracker, visualization_enabled],
        )
        thread.start()
        
        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


async def main_async(args):
    """Main async function."""
    
    # Load YOLO model
    print(f"Loading YOLO model from {args.model_path}...")
    ort_session = ort.InferenceSession(args.model_path)
    input_name = ort_session.get_inputs()[0].name
    print(f"Model loaded. Input: {input_name}")
    
    # Initialize tracker
    tracker = SimpleTracker()
    
    # Setup visualization if enabled
    visualization_enabled = not args.no_visualization
    if visualization_enabled:
        print("Setting up Rerun visualization...")
        args.memory_limit = 10
        rr.script_setup(args, "hal-tracking")
        
        blueprint = rrb.Blueprint(
            rrb.Grid(
                contents=[
                    rrb.Spatial2DView(origin="/camera", name="Camera Feed"),
                    rrb.BarChartView(origin="/tracker", name="Tracker Stats"),
                ]
            )
        )
        rr.send_blueprint(blueprint)
    
    # Zenoh configuration
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote:
        # Ensure remote endpoint has tcp/ prefix
        remote = args.remote if args.remote.startswith("tcp/") else f"tcp/{args.remote}"
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote}"]}}')
    
    session = zenoh.open(config)
    print("Zenoh session opened")
    
    # Create async drains
    loop = asyncio.get_running_loop()
    h264_drain = MessageDrain(loop)
    frame_size_storage = FrameSize()
    
    # Subscribe to H.264 stream
    session.declare_subscriber("rt/camera/h264", h264_drain.callback)
    print("Subscribed to rt/camera/h264")
    print("Waiting for H.264 stream...")
    
    # Start processing
    await asyncio.gather(
        h264_handler(h264_drain, frame_size_storage, ort_session, input_name,
                     tracker, visualization_enabled),
    )
    
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
        "--model-path",
        type=str,
        required=True,
        help="Path to YOLO ONNX model file",
    )
    parser.add_argument(
        "-r",
        "--remote",
        type=str,
        default=None,
        help="Connect to the remote endpoint instead of local.",
    )
    parser.add_argument(
        "--no-visualization",
        action="store_true",
        help="Disable Rerun visualization",
    )
    
    # Rerun args
    rr.script_add_args(parser)
    
    args = parser.parse_args()
    
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\nShutdown requested")
        sys.exit(0)


if __name__ == "__main__":
    main()
