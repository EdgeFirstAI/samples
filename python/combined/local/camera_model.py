# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""EdgeFirst Samples - Camera Model Sample (Local - on-device).

Reads from the camera, /dev/video3 by default and runs the model
inference on the captured frames and displays the frames in a window if available.

This example is intended to run locally on target.
Specify `--camera <device>` to select a different camera device, 0.
"""

from argparse import ArgumentParser
import time
import os

import numpy as np

try:
    import gi
    gi.require_version("Gst", "1.0")
    gi.require_version("GstApp", "1.0")
    gi.require_version("GstAllocators", "1.0")
    from gi.repository import Gst, GstApp, GLib, GstAllocators
    _GSTREAMER_AVAILABLE = True
except ImportError:
    _GSTREAMER_AVAILABLE = False

try:
    import cv2
    _OPENCV_AVAILABLE = True
except ImportError:
    _OPENCV_AVAILABLE = False

import edgefirst_hal as ef

from python.hal.local.letterbox import (LetterboxGStreamerCapture,
                                        LetterboxOpenCVCapture)
from python.model.local.tflite import (HALRunner as HALTFLiteRunner,
                                       OpenCVRunner as OpenCVTFLiteRunner)
from python.model.local.onnx import (HALRunner as HALONNXRunner,
                                     OpenCVRunner as OpenCVONNXRunner)


class GStreamerInference(LetterboxGStreamerCapture):
    def __init__(
        self,
        camera: str,
        model_path: str,
        score: float = 0.50,
        iou: float = 0.50,
        max_boxes: int = 300
    ):
        if os.path.splitext(os.path.basename(model_path)
                            )[-1].lower() == ".tflite":
            self.runner = HALTFLiteRunner(
                model_path=model_path,
                score=score,
                iou=iou,
                max_boxes=max_boxes
            )
        elif os.path.splitext(os.path.basename(model_path))[-1].lower() == ".onnx":
            self.runner = HALONNXRunner(
                model_path=model_path,
                score=score,
                iou=iou,
                max_boxes=max_boxes
            )
        else:
            raise NotImplementedError(
                "Only ONNX and TFLite Ultralytics models are supported in this sample.")

        super().__init__(camera, size=(self.runner.input_shape[1],
                                       self.runner.input_shape[0]))

    def on_new_sample(self, app_sink):
        start_pipeline = time.perf_counter()
        sample = app_sink.pull_sample()

        caps = sample.get_caps()
        buffer = sample.get_buffer()
        memory = buffer.get_all_memory()

        if not GstAllocators.is_dmabuf_memory(memory):
            raise RuntimeError('DMA Buffers is required for zero-copy')

        dmabuf = GstAllocators.dmabuf_memory_get_fd(memory)
        dmabuf_dup = os.dup(dmabuf)

        width = caps.get_structure(0).get_value("width")
        height = caps.get_structure(0).get_value("height")
        format = caps.get_structure(0).get_value("format")
        channels, fourcc = self.get_format(format)

        try:
            tensor = ef.TensorImage.from_fd(
                fd=dmabuf_dup,
                shape=[height, width, channels],
                fourcc=fourcc
            )
            boxes, scores, classes, masks = self.runner.infer(tensor)
            # Render detections on the image using the HAL converter
            self.runner.converter.render_to_image(
                self.runner.dst,
                bbox=boxes,
                scores=scores,
                classes=classes,
                seg=masks
            )

            channels = 1 if self.runner.dst.format == ef.FourCC.GREY else 4
            if self.use_cairo and self.cairo_window is not None:
                with self.runner.dst.map() as m:
                    n = np.array(
                        m.view()).reshape(
                        (self.runner.dst.height, self.runner.dst.width, channels))
                    if channels == 4:
                        n = n[:, :, :3]
                    n = np.ascontiguousarray(n, dtype=np.uint8)

                    end_pipeline = time.perf_counter() - start_pipeline
                    if self.process is not None:
                        self.cpu_percent = self.process.cpu_percent(
                            interval=None)
                    performance = (
                        f"CPU: {self.cpu_percent:.2f}% | "
                        f"End2End Latency: {end_pipeline * 1000:.2f} ms"
                    )

                    GLib.idle_add(
                        self.cairo_window.update_frame, n, performance)
                    if self.cairo_window.closed:
                        return True
        finally:
            os.close(dmabuf_dup)
        self.frame_count += 1
        return False


class OpenCVInference(LetterboxOpenCVCapture):
    def __init__(
        self,
        camera: str,
        model_path: str,
        method: str = "opencv",
        score: float = 0.50,
        iou: float = 0.50,
        max_boxes: int = 300
    ):

        if os.path.splitext(os.path.basename(model_path)
                            )[-1].lower() == ".tflite":
            self.runner = OpenCVTFLiteRunner(
                model_path=model_path,
                score=score,
                iou=iou,
                max_boxes=max_boxes
            )
        elif os.path.splitext(os.path.basename(model_path))[-1].lower() == ".onnx":
            self.runner = OpenCVONNXRunner(
                model_path=model_path,
                score=score,
                iou=iou,
                max_boxes=max_boxes
            )
        else:
            raise NotImplementedError(
                "Only ONNX and TFLite Ultralytics models are supported in this sample.")

        super().__init__(camera,
                         size=(self.runner.input_shape[1],
                               self.runner.input_shape[0]),
                         method=method)

    def on_new_sample(self):
        start_pipeline = time.perf_counter()
        frame = super().on_new_sample()
        boxes, scores, classes, masks = self.runner.infer(frame)
        height, width, _ = frame.shape

        # Denormalize box coordinates
        boxes[:, [0, 2]] *= width
        boxes[:, [1, 3]] *= height
        boxes = boxes.astype(np.int32)

        if _OPENCV_AVAILABLE:
            alpha = 0.50
            for i in range(boxes.shape[0]):
                cv2.rectangle(frame,
                              (boxes[i, 0], boxes[i, 1]),
                              (boxes[i, 2], boxes[i, 3]), (0, 255, 0), 2)

                if masks is not None:
                    frame[masks[i] > 0] = (
                        frame[masks[i] > 0] * (1 - alpha) +
                        np.array([0, 255, 0, 255]) * alpha
                    )
                cv2.putText(
                    frame,
                    f"{self.runner.labels[classes[i]] if self.runner.labels is not None else classes[i]}: {scores[i]:.2f}",
                    (boxes[i, 0], boxes[i, 1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2
                )

            end_pipeline = time.perf_counter() - start_pipeline
            if self.process is not None:
                self.cpu_percent = self.process.cpu_percent(interval=None)
            performance = (
                f"CPU: {self.cpu_percent:.2f}% | "
                f"End2End Latency: {end_pipeline * 1000:.2f} ms"
            )
            cv2.putText(
                frame, performance, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (0, 255, 0), 2, cv2.LINE_AA,
            )
        return frame


def main():
    opts = ArgumentParser(
        description='Camera Letterbox')
    opts.add_argument('--model', type=str, required=True,
                      help='The path to the TFLite model')
    opts.add_argument('-c', '--camera', type=str, default='/dev/video3',
                      help='Camera device for capture')
    opts.add_argument('-m', '--method', type=str, default='hal',
                      choices=["hal", "opencv", "pillow"],
                      help='Letterbox method to use')
    opts.add_argument('-s', '--score', type=float, default=0.50,
                      help='Specify the score threshold for NMS')
    opts.add_argument('-i', '--iou', type=float, default=0.50,
                      help='Specify the IoU threshold for NMS')
    opts.add_argument('--max-boxes', type=int, default=300,
                      help='Specify the maximum number of devices')
    args = opts.parse_args()

    if args.method in ["opencv", "pillow"]:
        capture = OpenCVInference(
            int(args.camera) if args.camera.isdigit() else args.camera,
            model_path=args.model,
            method=args.method,
            score=args.score,
            iou=args.iou,
            max_boxes=args.max_boxes
        )
    else:
        # GStreamer captures is intended for HAL in this use-case to show
        # benefits with the HAL optimizations.
        capture = GStreamerInference(
            int(args.camera) if args.camera.isdigit() else args.camera,
            model_path=args.model,
            score=args.score,
            iou=args.iou,
            max_boxes=args.max_boxes
        )
    capture.run()


if __name__ == "__main__":
    main()
