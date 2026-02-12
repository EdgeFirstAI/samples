# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""EdgeFirst Samples - OpenCV Sample (Local - on-device).

Reads from the camera, 0 by default and displays the captured
frame in a window if available. 

This example is intended to run locally on an EdgeFirst device.
Specify `--camera <device>` to select a different camera device, 0. 
"""

from argparse import ArgumentParser
from typing import Union 

import cv2


class OpenCVCapture:
    def __init__(self, device_index: Union[int, str] = 0):
        self.device_index = device_index
        self.cap = cv2.VideoCapture(self.device_index)
        if not self.cap.isOpened():
            raise RuntimeError("Cannot open camera")
        self.window_available = self.has_display()

    @staticmethod
    def has_display() -> bool:
        try:
            cv2.namedWindow("Camera", cv2.WINDOW_AUTOSIZE)
            visible = cv2.getWindowProperty("Camera", cv2.WND_PROP_VISIBLE)
            return visible >= 1
        except cv2.error:
            return False

    def run(self):
        print('capturing from %s at %dx%d' % (
            self.device_index, 
            int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)), 
            int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))))
        print("Press CTRL-C to stop")
        while True:
            # Capture frame-by-frame
            ret, frame = self.cap.read()

            # if frame is read correctly ret is True
            if not ret:
                print("Can't receive frame (stream end?). Exiting ...")
                break

            if self.window_available:
                cv2.imshow("Camera", frame)
                if cv2.getWindowProperty("Camera", cv2.WND_PROP_VISIBLE) < 1:
                    break
            if cv2.waitKey(1) == ord('q'):
                break

        # When everything done, release the capture
        self.cap.release()
        if self.window_available:
            cv2.destroyWindow("Camera")


def main():
    opts = ArgumentParser(
        description='OpenCV Camera with Python')
    opts.add_argument('-c', '--camera', type=str, default="0",
                      help='Camera device for capture')
    args = opts.parse_args()
    
    capture = OpenCVCapture(int(args.camera) if args.camera.isdigit() else args.camera)
    capture.run()

if __name__ == "__main__":
    main()
