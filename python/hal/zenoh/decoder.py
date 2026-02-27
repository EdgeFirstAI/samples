# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""EdgeFirst Samples - Camera/Model Decoder (Zenoh + HAL).

Subscribes to Zenoh topics (e.g. `rt/camera/h264`) to decode incoming frames,
runs a YOLO ONNX model, and publishes decoded model outputs (boxes/masks) to
Rerun for visualization.

Use `--remote <IP:PORT>` to connect to a remote Zenoh endpoint, otherwise local
discovery is used.
"""

from utils.hal_tflite import HALTFLiteRunner
from utils.hal_onnx import HALONNXRunner
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
from edgefirst.schemas.edgefirst_msgs import Detect

sys.path.append(str(Path(__file__).resolve().parents[2]))


# Shared storage for latest decoded frame
latest_frame_lock = threading.Lock()
latest_frame = None
frame_available_event = threading.Event()


class FrameSize:
    def __init__(self):
        self._size = []
        self._event = asyncio.Event()
        self.raw_data = io.BytesIO()
        self.tensor_image = None

    def set(self, width: int, height: int):
        self._size = [width, height]
        if not self._event.is_set():
            self._event.set()

        self.tensor_image = ef.TensorImage(
            width,
            height,
            ef.FourCC.RGB
        )

    async def get(self) -> list[int]:
        await self._event.wait()
        return self._size


class MessageDrain:
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._queue = asyncio.Queue(maxsize=100)
        self._loop = loop

    def callback(self, msg: zenoh.Sample):
        if not self._loop.is_closed():
            if self._queue.full():
                self._queue.get_nowait()
            self._loop.call_soon_threadsafe(self._queue.put_nowait, msg)

    async def read(self) -> zenoh.Sample:
        return await self._queue.get()

    async def get_latest(self) -> zenoh.Sample:
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
    runner: Union[HALONNXRunner, HALTFLiteRunner]
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
        frame_storage.tensor_image.copy_from_numpy(frame_array)

        # Run model inference
        boxes, scores, classes, masks = runner.static_infer(
            frame_storage.tensor_image)

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

            centers = (boxes[:, [0, 1]] + boxes[:, [2, 3]]) / 2
            centers *= [runner.input_shape[1], runner.input_shape[0]]
            sizes = (boxes[:, [2, 3]] - boxes[:, [0, 1]])
            sizes *= [runner.input_shape[1], runner.input_shape[0]]

            labels = []
            for cls_id, score in zip(classes, scores):
                cls_id = int(cls_id)

                if runner.labels is not None:
                    name = runner.labels[cls_id]
                else:
                    name = f"class_{cls_id}"

                labels.append(f"{name} ({score:.2f})")

            rr.log(
                "/camera/boxes",
                rr.Boxes2D(
                    centers=centers,
                    sizes=sizes,
                    labels=labels))


def h264_worker(
    msg: zenoh.Sample, frame_storage: FrameSize,
    container: av.container.InputContainer, runner: Union[HALONNXRunner, HALTFLiteRunner]
):
    try:
        frame_storage.raw_data.write(msg.payload.to_bytes())
        frame_storage.raw_data.seek(0)
        for packet in container.demux():
            if packet.size == 0:
                continue
            for frame in packet.decode():
                # for frame in packet.decode():
                frame_array = frame.to_ndarray(format="rgb24")
                frame_height, frame_width = frame_array.shape[:2]
                frame_storage.set(frame_width, frame_height)

                frame_storage.tensor_image.copy_from_numpy(frame_array)
                boxes, scores, classes, masks = runner.static_infer(
                    frame_storage.tensor_image)

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

                    # Log frame and detections to Rerun
                    rr.log("/camera/frame", rr.Image(n))

                    # Convert boxes to pixel coordinates and log
                    centers = (boxes[:, [0, 1]] + boxes[:, [2, 3]]) / 2
                    centers *= [runner.input_shape[1], runner.input_shape[0]]
                    sizes = (boxes[:, [2, 3]] - boxes[:, [0, 1]])
                    sizes *= [runner.input_shape[1], runner.input_shape[0]]

                    labels = []
                    for cls_id, score in zip(classes, scores):
                        cls_id = int(cls_id)

                        if runner.labels is not None:
                            name = runner.labels[cls_id]
                        else:
                            name = f"class_{cls_id}"
                        labels.append(f"{name} ({score:.2f})")

                    rr.log(
                        "/camera/boxes",
                        rr.Boxes2D(
                            centers=centers, sizes=sizes, labels=labels),
                    )

            # Clear buffer after successful packet processing
            frame_storage.raw_data.seek(0)
            frame_storage.raw_data.truncate(0)
    except Exception as e:
        print(f"Error in h264_worker: {e}")
        # Clear buffer on any error
        frame_storage.raw_data.seek(0)
        frame_storage.raw_data.truncate(0)


async def h264_handler(
    drain: MessageDrain,
    frame_storage: FrameSize,
    runner: Union[HALONNXRunner, HALTFLiteRunner]
):
    container = av.open(frame_storage.raw_data, format="h264", mode="r")

    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(
            target=h264_worker, args=[msg, frame_storage, container, runner]
        )
        thread.start()

        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


def boxes2d_worker(msg: zenoh.Sample, boxes_tracked: dict, frame_size: tuple):
    detection = Detect.deserialize(msg.payload.to_bytes())
    centers, sizes, labels, colors = [], [], [], []
    for box in detection.boxes:
        if box.track.id and box.track.id not in boxes_tracked:
            boxes_tracked[box.track.id] = [
                box.label + ": " + box.track.id[:6],
                list(np.random.choice(range(256), size=3)),
            ]
        if box.track.id:
            colors.append(boxes_tracked[box.track.id][1])
            labels.append(boxes_tracked[box.track.id][0])
        else:
            colors.append([0, 255, 0])
            labels.append(box.label)
        centers.append(
            (int(box.center_x * frame_size[0]),
             int(box.center_y * frame_size[1]))
        )
        sizes.append(
            (int(box.width * frame_size[0]), int(box.height * frame_size[1])))
    rr.log(
        "/camera/boxes",
        rr.Boxes2D(centers=centers, sizes=sizes, labels=labels, colors=colors),
    )


async def boxes2d_handler(drain: MessageDrain, frame_storage: FrameSize):
    boxes_tracked = {}
    _ = await frame_storage.get()
    while True:
        msg = await drain.get_latest()
        frame_size = await frame_storage.get()
        thread = threading.Thread(
            target=boxes2d_worker, args=[msg, boxes_tracked, frame_size]
        )
        thread.start()

        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


async def main_async(session: zenoh.Session,
                     runner: Union[HALONNXRunner, HALTFLiteRunner]):
    # Create drains
    loop = asyncio.get_running_loop()
    h264_drain = MessageDrain(loop)
    frame_size_storage = FrameSize()

    session.declare_subscriber("rt/camera/h264", h264_drain.callback)
    # Start decoder thread
    threading.Thread(target=h264_handler_sync,
                     args=(h264_drain, loop),
                     daemon=True).start()

    # Start inference thread
    threading.Thread(target=inference_handler_sync,
                     args=(frame_size_storage, runner),
                     daemon=True).start()

    # Keep the async loop alive
    while True:
        await asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(
        description="EdgeFirst Samples - Camera-Model with YOLO")
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        required=True,
        help="Path to YOLO ONNX or TFLite model file",
    )
    parser.add_argument(
        "-r",
        "--remote",
        type=str,
        default=None,
        help="Connect to the remote endpoint instead of local.",
    )
    rr.script_add_args(parser)
    args = parser.parse_args()

    rr.script_setup(args, sys.argv[0])

    blueprint = rrb.Blueprint(
        rrb.Grid(
            contents=[
                rrb.Spatial2DView(
                    origin="/camera",
                    name="Camera Feed")])
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

    # Zenoh config
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
