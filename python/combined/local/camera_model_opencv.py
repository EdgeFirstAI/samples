# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""EdgeFirst Samples - Camera Model Sample using OpenCV (Local - on-device).

Reads from the camera, /dev/video3 by default and runs the model
inference on the captured frames and displays the frames in a window if available.

This example is intended to run locally on target.
Specify `--camera <device>` to select a different camera device.
"""

from argparse import ArgumentParser
from pathlib import Path
import time
import sys
import os

import numpy as np

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

try:
    import cv2
    _OPENCV_AVAILABLE = True
except ImportError:
    _OPENCV_AVAILABLE = False

sys.path.append(str(Path(__file__).resolve().parents[2]))

from utils.opencv_utils import (has_display as opencv_has_display,
                                _build_pipeline as opencv_build_pipeline,
                                cv2_letterbox)
from utils.opencv_tflite import OpenCVTFLiteRunner
from utils.opencv_onnx import OpenCVONNXRunner


class OpenCVInference:
    def __init__(
        self,
        camera: str,
        model_path: str,
        method: str = "opencv",
        score: float = 0.50,
        iou: float = 0.50,
        max_boxes: int = 300
    ):

        if not _OPENCV_AVAILABLE:
            raise ImportError(
                "OpenCV is not available. Please install OpenCV.")

        # Display init
        self.camera = camera
        self.method = method
        self.pipeline = opencv_build_pipeline(self.camera)
        self.cap = cv2.VideoCapture(self.pipeline, cv2.CAP_GSTREAMER)
        if not self.cap.isOpened():
            # Try standard VideoCapture if GStreamer pipeline fails
            self.cap = cv2.VideoCapture(self.camera)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera {self.camera}")
        self.window_available = opencv_has_display()

        # Performance measurements
        self.frame_count = 0
        self.window_start = time.perf_counter()
        self.fetch_fps = 0.0
        self.cpu_percent = 0.0
        self.process = psutil.Process() if _PSUTIL_AVAILABLE else None
        if self.process is not None:
            self.process.cpu_percent(interval=None)

        # Model init
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

        self.size = (self.runner.input_shape[1], self.runner.input_shape[0])

    def on_new_sample(self):
        start_pipeline = time.perf_counter()

        ret, frame = self.cap.read()
        # if frame is read correctly ret is True
        if not ret:
            self.clear()
            raise RuntimeError("Failed to read frame from camera")
        frame = cv2_letterbox(frame, size=self.size, method=self.method)

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
                    if frame.shape[-1] == 3:
                        color = np.array([0, 255, 0])
                    else:
                        color = np.array([0, 255, 0, 255])

                    frame[masks[i] > 0] = (
                        frame[masks[i] > 0] * (1 - alpha) + color * alpha
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

    def run(self):
        print('capturing from %s at %dx%d' % (
            self.camera,
            int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))))
        print("Press CTRL-C to stop")

        while True:
            # Capture frame-by-frame
            frame = self.on_new_sample()

            self.frame_count += 1
            elapsed = time.perf_counter() - self.window_start
            if elapsed >= 1.0:
                self.fetch_fps = self.frame_count / elapsed
                self.frame_count = 0
                self.window_start = time.perf_counter()
                if self.process is not None:
                    self.cpu_percent = self.process.cpu_percent(interval=None)

            performance = (
                f"CPU: {self.cpu_percent:.1f}% | "
                f"FPS: {self.fetch_fps:.1f}"
            )
            print(performance, end="\r")

            if self.window_available:
                cv2.imshow("Camera", frame)
                # Check if window was closed by clicking X
                if cv2.getWindowProperty("Camera", cv2.WND_PROP_VISIBLE) == 0:
                    break
            if cv2.waitKey(1) == ord('q'):
                break

        # When everything done, release the capture
        self.clear()

    def clear(self):
        # When everything done, release the capture
        self.cap.release()
        if self.window_available:
            cv2.destroyWindow("Camera")


def main():
    opts = ArgumentParser(
        description='Camera Letterbox')
    opts.add_argument('--model', type=str, required=True,
                      help='The path to the TFLite model')
    opts.add_argument('-c', '--camera', type=str, default='/dev/video3',
                      help='Camera device for capture')
    opts.add_argument('-m', '--method', type=str, default='opencv',
                      choices=["opencv", "pillow"],
                      help='Letterbox method to use')
    opts.add_argument('-s', '--score', type=float, default=0.50,
                      help='Specify the score threshold for NMS')
    opts.add_argument('-i', '--iou', type=float, default=0.50,
                      help='Specify the IoU threshold for NMS')
    opts.add_argument('--max-boxes', type=int, default=300,
                      help='Specify the maximum number of devices')
    args = opts.parse_args()

    capture = OpenCVInference(
        int(args.camera) if args.camera.isdigit() else args.camera,
        model_path=args.model,
        method=args.method,
        score=args.score,
        iou=args.iou,
        max_boxes=args.max_boxes
    )
    capture.run()


if __name__ == "__main__":
    main()
