# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""EdgeFirst Samples - OpenCV Sample (Local - on-device).

Reads from the camera, 0 by default and displays the captured
frame in a window if available.

This example is intended to run locally on target.
Specify `--camera <device>` to select a different camera device, 0.
"""

from utils.opencv_utils import (has_display as opencv_has_display,
                                _build_pipeline as opencv_build_pipeline)
from argparse import ArgumentParser
from typing import Union
from pathlib import Path
import time
import sys

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


class OpenCVCapture:
    def __init__(self, device_index: Union[int, str] = 0):
        if not _OPENCV_AVAILABLE:
            raise ImportError(
                "OpenCV is not available. Please install OpenCV.")

        # Display init
        self.device_index = device_index
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
        return frame

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
    opts = ArgumentParser(
        description='OpenCV Camera with Python')
    opts.add_argument('-c', '--camera', type=str, default='/dev/video3',
                      help='Camera device for capture')
    args = opts.parse_args()

    capture = OpenCVCapture(
        int(args.camera) if args.camera.isdigit() else args.camera)
    capture.run()


if __name__ == "__main__":
    main()
