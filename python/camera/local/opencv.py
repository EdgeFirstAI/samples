# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""EdgeFirst Samples - OpenCV Sample (Local - on-device).

Reads from the camera, 0 by default and displays the captured
frame in a window if available.

This example is intended to run locally on target.
Specify `--camera <device>` to select a different camera device, 0.
"""

from argparse import ArgumentParser
from typing import Union
import time

try:
    import cv2
    _OPENCV_AVAILABLE = True
except ImportError:
    _OPENCV_AVAILABLE = False

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False


class OpenCVCapture:
    def __init__(self, device_index: Union[int, str] = 0):
        if not _OPENCV_AVAILABLE:
            raise ImportError(
                "OpenCV is not available. Please install OpenCV.")

        self.device_index = device_index

        self.pipeline = (
            f"v4l2src device={self.device_index} io-mode=dmabuf ! "
            "video/x-raw,format=YUY2 ! "
            "imxvideoconvert_g2d ! "
            "video/x-raw,format=BGRA ! "
            "appsink drop=true max-buffers=1 sync=false"
        )

        self.cap = cv2.VideoCapture(self.pipeline, cv2.CAP_GSTREAMER)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera {self.device_index}")
        self.window_available = self.has_display()

        self.frame_count = 0
        self.window_start = time.perf_counter()
        self.fetch_fps = 0.0
        self.cpu_percent = 0.0
        self.process = psutil.Process() if _PSUTIL_AVAILABLE else None
        if self.process is not None:
            self.process.cpu_percent(interval=None)

    @staticmethod
    def has_display() -> bool:
        try:
            cv2.namedWindow("Camera", cv2.WINDOW_AUTOSIZE)
            visible = cv2.getWindowProperty("Camera", cv2.WND_PROP_VISIBLE)
            return visible >= 1
        except cv2.error:
            return False

    def on_new_sample(self):
        # Placed as a method to allow method overloading
        # Capture frame-by-frame
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
