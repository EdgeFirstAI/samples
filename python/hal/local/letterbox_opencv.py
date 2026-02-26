# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""EdgeFirst Samples - Letterbox Sample using OpenCV (Local - on-device).

Reads from the camera, /dev/video3 by default and transforms the frame with 
letterbox and displays the letterboxed frame in a window if available.
The letterbox method uses OpenCV library functions for resizing and padding.

This example is intended to run locally on target.
Specify `--camera <device>` to select a different camera device.
"""

from typing import Optional
from argparse import ArgumentParser
from pathlib import Path
import time
import sys

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

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from resize_opencv import cv2_resize, pillow_resize
from utils.opencv_utils import (has_display as opencv_has_display, 
                                _build_pipeline as opencv_build_pipeline)


def cv2_letterbox(
    image: np.ndarray,
    size: Optional[tuple] = None,
    constant: int = 114,
    method: str = "opencv"
) -> np.ndarray:
    height, width = image.shape[:2]
    scale = min(size[0] / width, size[1] / height)
    new_width = int(round(width * scale))
    new_height = int(round(height * scale))

    if scale != 1.0:
        if method == "opencv":
            image = cv2_resize(image, size=(new_width, new_height))
        else:
            image = pillow_resize(image, size=(new_width, new_height))

    # Compute padding
    dw, dh = size[0] - new_width, size[1] - new_height  # wh padding
    top = round(dh / 2)
    bottom = dh - top
    left = round(dw / 2)
    right = dw - left

    if method == "opencv":
        padded_image = cv2.copyMakeBorder(
            image, top, bottom, left, right, cv2.BORDER_CONSTANT,
            value=(constant, constant, constant))  # add border
    else:
        padded_image = np.zeros(
            (3, new_height + top + bottom, new_width + left + right))

        for i, _ in enumerate(padded_image):
            padded_image[i, :, :] = np.pad(
                image[:, :, i], ((top, bottom), (left, right)),
                mode='constant', constant_values=constant)
        padded_image = np.transpose(
            padded_image, axes=(1, 2, 0)).astype(np.uint8)
    return padded_image


class LetterboxOpenCVCapture:
    def __init__(self, device_index: int, size: Optional[tuple] = None,
                 method: str = "opencv"):
        if not _OPENCV_AVAILABLE:
            raise ImportError(
                "OpenCV is not available. Please install OpenCV.")

        # Display init
        self.device_index = device_index
        self.size = size
        self.method = method
        self.pipeline = opencv_build_pipeline(self.device_index)
        self.cap = cv2.VideoCapture(self.pipeline, cv2.CAP_GSTREAMER)
        if not self.cap.isOpened():
            # Try standard VideoCapture if GStreamer pipeline fails
            self.cap = cv2.VideoCapture(self.device_index)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera {self.device_index}")
        self.window_available = opencv_has_display()

        # Performance measurements
        self.frame_count = 0
        self.window_start = time.perf_counter()
        self.fetch_fps = 0.0
        self.cpu_percent = 0.0
        self.process = psutil.Process() if _PSUTIL_AVAILABLE else None
        if self.process is not None:
            self.process.cpu_percent(interval=None)

    def on_new_sample(self):
        ret, frame = self.cap.read()
        # if frame is read correctly ret is True
        if not ret:
            self.clear()
            raise RuntimeError("Failed to read frame from camera")
        return cv2_letterbox(frame, size=self.size, method=self.method)

    def run(self):
        print('capturing from %s at %dx%d' % (
            self.device_index,
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
    opts = ArgumentParser(description='Camera Letterbox using OpenCV')
    opts.add_argument('-c', '--camera', type=str, default='/dev/video3',
                      help='Camera device for capture')
    opts.add_argument('-s', '--size', type=str, default='640x360',
                      help='Resize dimensions in WIDTHxHEIGHT format, e.g. 640x360')
    opts.add_argument('-m', '--method', type=str, default='opencv',
                      choices=["opencv", "pillow"],
                      help='resize method to use')
    args = opts.parse_args()

    camera_width, camera_height = map(int, args.size.split('x'))
    capture = LetterboxOpenCVCapture(
        int(args.camera) if args.camera.isdigit() else args.camera,
        size=(camera_width, camera_height),
        method=args.method)
    capture.run()


if __name__ == "__main__":
    main()
