# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""EdgeFirst Samples - Letterbox Sample (Local - on-device).

Reads from the camera, 0 by default and transforms the frame with letterbox
and displays the letterboxed frame in a window if available.
The letterbox method is selectable between OpenCV, Pillow, and HAL which uses
either OpenCV VideoCaptures and streaming, or a GStreamer pipeline
with zero-copy DMA buffers and OpenGL optimizations in HAL.

This example is intended to run locally on target.
Specify `--camera <device>` to select a different camera device, 0.
"""

from typing import Optional
from argparse import ArgumentParser
import time
import os

import numpy as np

try:
    import cv2
    _OPENCV_AVAILABLE = True
except ImportError:
    _OPENCV_AVAILABLE = False

try:
    import gi
    gi.require_version("Gst", "1.0")
    gi.require_version("GstApp", "1.0")
    gi.require_version("GstAllocators", "1.0")
    from gi.repository import Gst, GstApp, GLib, GstAllocators
    _GSTREAMER_AVAILABLE = True
except ImportError:
    _GSTREAMER_AVAILABLE = False

import edgefirst_hal as ef

from python.hal.local.resize import cv2_resize, pillow_resize
from python.hal.local.resize import ResizedOpenCVCapture, ResizedGStreamerCapture


CONVERTER = ef.ImageProcessor()


def hal_letterbox(image: ef.TensorImage, dst: ef.TensorImage,
                  constant: int = 114):
    ratio = min(dst.height / image.height, dst.width / image.width)
    height = image.height * ratio
    width = image.width * ratio
    top = round((dst.height - height) / 2)
    left = round((dst.width - width) / 2)
    height = round(height)
    width = round(width)
    CONVERTER.convert(image, dst,
                      dst_crop=ef.Rect(left, top, width, height),
                      dst_color=[constant, constant, constant, 255])


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


class LetterboxGStreamerCapture(ResizedGStreamerCapture):
    def __init__(self, camera: str, size: Optional[tuple] = None):
        super().__init__(camera, size)
        self.dst = None
        if self.size is not None:
            # To use OpenGL assign image FourCC as RGBA.
            self.dst = ef.TensorImage(
                self.size[0], self.size[1], ef.FourCC.RGBA)

    def on_new_sample(self, app_sink):
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

            hal_letterbox(tensor, self.dst)

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

            channels = 1 if self.dst.format == ef.FourCC.GREY else 4
            if self.use_cairo and self.cairo_window is not None:
                with self.dst.map() as m:
                    n = np.array(
                        m.view()).reshape(
                        (self.dst.height, self.dst.width, channels))
                    if channels == 4:
                        n = n[:, :, :3]
                    n = np.ascontiguousarray(n, dtype=np.uint8)
                    GLib.idle_add(self.cairo_window.update_frame, n)
                    if self.cairo_window.closed:
                        return True
        finally:
            os.close(dmabuf_dup)

        self.frame_count += 1
        return False


class LetterboxOpenCVCapture(ResizedOpenCVCapture):
    def on_new_sample(self):
        frame = super(ResizedOpenCVCapture, self).on_new_sample()
        return cv2_letterbox(frame, size=self.size, method=self.method)


def main():
    opts = ArgumentParser(
        description='Camera Letterbox')
    opts.add_argument('-c', '--camera', type=str, default='/dev/video3',
                      help='Camera device for capture')
    opts.add_argument('-s', '--size', type=str, default='640x360',
                      help='Resize dimensions in WIDTHxHEIGHT format, e.g. 640x360')
    opts.add_argument('-m', '--method', type=str, default='hal',
                      choices=["hal", "opencv", "pillow"],
                      help='Letterbox method to use')
    args = opts.parse_args()

    camera_width, camera_height = map(int, args.size.split('x'))

    if args.method in ["opencv", "pillow"]:
        capture = LetterboxOpenCVCapture(
            int(args.camera) if args.camera.isdigit() else args.camera,
            size=(camera_width, camera_height),
            method=args.method)
    else:
        # GStreamer captures is intended for HAL in this use-case to show
        # benefits with the HAL optimizations.
        capture = LetterboxGStreamerCapture(
            int(args.camera) if args.camera.isdigit() else args.camera,
            size=(camera_width, camera_height))
    capture.run()


if __name__ == "__main__":
    main()
