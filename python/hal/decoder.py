# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

from argparse import ArgumentParser
import asyncio
import io
import sys
import av
import zenoh
import threading
import onnxruntime as ort
import numpy as np
from edgefirst.schemas.edgefirst_msgs import Detect, Mask
import edgefirst_hal as ef
import rerun as rr
import rerun.blueprint as rrb


class FrameSize:
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


def h264_worker(msg, frame_storage, raw_data, container, ort_session, input_name):
    raw_data.write(msg.payload.to_bytes())
    raw_data.seek(0)
    for packet in container.demux():
        try:
            if packet.size == 0:
                continue
            raw_data.seek(0)
            raw_data.truncate(0)
            for frame in packet.decode():
                frame_array = frame.to_ndarray(format="rgb24")
                frame_height, frame_width = frame_array.shape[:2]
                frame_storage.set(frame_width, frame_height)
                
                ef_im = ef.TensorImage(frame_array.shape[1], frame_array.shape[0], ef.FourCC.RGB)
                ef_im.copy_from_numpy(frame_array)
                converter = ef.ImageConverter()
                output = ef.TensorImage(640, 640)
                converter.convert(ef_im, output)
                
                out_array = np.zeros((640, 640, 3), dtype=np.uint8)
                output.normalize_to_numpy(out_array)
                out_array = np.transpose(out_array, (2, 0, 1))  # Channels x Height x Width
                # Prepare input for YOLO
                input_tensor = out_array.astype(np.float32) / 255.0
                input_tensor = np.expand_dims(input_tensor, axis=0)
                
                # Run inference
                outputs = ort_session.run(None, {input_name: input_tensor})
                
                # YOLO outputs: [predictions, proto]
                predictions = outputs[0]
                boxes, scores, classes = ef.Decoder.decode_yolo_det(predictions.squeeze(),  (0.0040811873, -123),
                0.25,
                0.7,
                50,)
                
                # Log frame and detections to Rerun
                rr.log("/camera/frame", rr.Image(frame_array))
                
                # Convert boxes to pixel coordinates and log
                centers, sizes, labels = [], [], []
                for box, score, cls_id in zip(boxes, scores, classes):
                    x1, y1, x2, y2 = box
                    # Denormalize from 640x640 space to frame size
                    x1_px = int(x1 / 640.0 * frame_width)
                    y1_px = int(y1 / 640.0 * frame_height)
                    x2_px = int(x2 / 640.0 * frame_width)
                    y2_px = int(y2 / 640.0 * frame_height)
                    
                    center_x = (x1_px + x2_px) / 2
                    center_y = (y1_px + y2_px) / 2
                    width = x2_px - x1_px
                    height = y2_px - y1_px
                    
                    centers.append((center_x, center_y))
                    sizes.append((width, height))
                    labels.append(f"class_{int(cls_id)} ({score:.2f})")
                
                rr.log(
                    "/camera/boxes",
                    rr.Boxes2D(centers=centers, sizes=sizes, labels=labels),
                )

        except Exception as e:
            print(str(e))
            continue


async def h264_handler(drain, frame_storage, ort_session, input_name):
    raw_data = io.BytesIO()
    container = av.open(raw_data, format="h264", mode="r")

    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(
            target=h264_worker, args=[msg, frame_storage, raw_data, container, ort_session, input_name]
        )
        thread.start()

        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


def boxes2d_worker(msg, boxes_tracked, frame_size):
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
            (int(box.center_x * frame_size[0]), int(box.center_y * frame_size[1]))
        )
        sizes.append((int(box.width * frame_size[0]), int(box.height * frame_size[1])))
    rr.log(
        "/camera/boxes",
        rr.Boxes2D(centers=centers, sizes=sizes, labels=labels, colors=colors),
    )


async def boxes2d_handler(drain, frame_storage):
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


async def main_async(args):
    rr.script_setup(args, "camera-model")

    blueprint = rrb.Blueprint(
        rrb.Grid(contents=[rrb.Spatial2DView(origin="/camera", name="Camera Feed")])
    )
    rr.send_blueprint(blueprint)
    # Load YOLO model with ONNX Runtime
    ort_session = ort.InferenceSession(args.model_path)
    input_name = ort_session.get_inputs()[0].name
    print(f"Loaded YOLO model from {args.model_path}")

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{args.remote}"]}}')
    session = zenoh.open(config)

    # Create drains
    loop = asyncio.get_running_loop()
    h264_drain = MessageDrain(loop)
    frame_size_storage = FrameSize()

    session.declare_subscriber("rt/camera/h264", h264_drain.callback)
    await asyncio.gather(
        h264_handler(h264_drain, frame_size_storage, ort_session, input_name),
    )

    while True:
        asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Camera-Model with YOLO")
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
    rr.script_add_args(parser)
    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
