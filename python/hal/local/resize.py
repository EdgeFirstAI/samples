# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.


"""EdgeFirst Samples - Resizing Sample (Local - on-device).

Reads from the camera, 0 by default and resizes the frame based on
the specified dimensions and displays the resized frame in a window if available.
The resize method is selectable between OpenCV, Pillow, and HAL which uses
either OpenCV VideoCaptures and streaming, or a GStreamer pipeline
with zero-copy DMA buffers and OpenGL optimizations in HAL.

This example is intended to run locally on target.
Specify `--camera <device>` to select a different camera device, 0.
"""

from typing import Optional, Tuple
from argparse import ArgumentParser
import time
import os

from PIL import Image
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

from python.camera.local.opencv import OpenCVCapture
from python.camera.local.gstreamer import GStreamerCapture


CONVERTER = ef.ImageProcessor()


def hal_resize(image: ef.TensorImage,
               size: Optional[tuple] = None) -> ef.TensorImage:
    if size is None:
        return image
    # To use OpenGL assign image FourCC as RGBA.
    fourcc = (ef.FourCC.RGBA if image.format ==
              ef.FourCC.RGB else image.format)
    dst = ef.TensorImage(size[0], size[1], fourcc=fourcc)
    CONVERTER.convert(image, dst)
    return dst


def cv2_resize(image: np.ndarray, size: Optional[tuple] = None) -> np.ndarray:
    if not _OPENCV_AVAILABLE:
        raise ImportError(
            "OpenCV is not available. Please install OpenCV to use cv2_resize.")
    if size is None:
        return image
    return cv2.resize(image, size, interpolation=cv2.INTER_LINEAR)


def pillow_resize(image: np.ndarray,
                  size: Optional[tuple] = None) -> np.ndarray:
    if size is None:
        return image
    im = Image.fromarray(image.astype(np.uint8))
    im = im.resize(size)
    return np.array(im)


class ResizedGStreamerCapture(GStreamerCapture):
    def __init__(self, camera: str, size: Optional[tuple] = None):
        super().__init__(camera, use_cairo=True)
        self.size = size

    @staticmethod
    def get_format(format: str) -> Tuple[int, ef.FourCC]:
        if format == "NV12":
            # planar YUV 4:2:0, usually 1.5 bytes per pixel
            channels = 1  # single channel for Y plane; need special handling
            fourcc = ef.FourCC("NV12")
        elif format in ["YUY2", "YUYV"]:
            channels = 2
            fourcc = ef.FourCC("YUYV")
        elif format == "RGB":
            channels = 3
            fourcc = ef.FourCC("RGB")
        elif format == "RGBA":
            channels = 4
            fourcc = ef.FourCC("RGBA")
        elif format == "ARGB":
            channels = 4
            fourcc = ef.FourCC("PLANAR_RGBA")
        else:
            raise RuntimeError(f"Unsupported pixel format: {format}")
        return channels, fourcc

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

            dst_tensor = hal_resize(tensor, size=self.size)

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

            channels = 1 if dst_tensor.format == ef.FourCC.GREY else 4
            if self.use_cairo and self.cairo_window is not None:
                with dst_tensor.map() as m:
                    n = np.array(m.view()).reshape((dst_tensor.height,
                                                    dst_tensor.width, channels))
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


class ResizedOpenCVCapture(OpenCVCapture):
    def __init__(self, device_index: int, size: Optional[tuple] = None,
                 method: str = "opencv"):
        super().__init__(device_index)
        self.size = size
        self.method = method

    def on_new_sample(self):
        frame = super().on_new_sample()
        if self.method == "opencv":
            return cv2_resize(frame, self.size)
        return pillow_resize(frame, self.size)


def main():
    opts = ArgumentParser(
        description='Camera Resize')
    opts.add_argument('-c', '--camera', type=str, default='/dev/video3',
                      help='Camera device for capture')
    opts.add_argument('-s', '--size', type=str, default='640x360',
                      help='Resize dimensions in WIDTHxHEIGHT format, e.g. 640x360')
    opts.add_argument('-m', '--method', type=str, default='hal',
                      choices=["hal", "opencv", "pillow"],
                      help='Resize method to use')
    args = opts.parse_args()

    camera_width, camera_height = map(int, args.size.split('x'))

    if args.method in ["opencv", "pillow"]:
        capture = ResizedOpenCVCapture(
            int(args.camera) if args.camera.isdigit() else args.camera,
            size=(camera_width, camera_height),
            method=args.method)
    else:
        # GStreamer captures is intended for HAL in this use-case to show
        # benefits with the HAL optimizations.
        capture = ResizedGStreamerCapture(args.camera,
                                          size=(camera_width, camera_height))
    capture.run()


if __name__ == "__main__":
    main()
