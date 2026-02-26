# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""EdgeFirst Samples - Resizing Sample using HAL (Local - on-device).

Reads from the camera, /dev/video3 by default and resizes the frame based on
the specified dimensions and displays the resized frame in a window if available.
The resize method uses a GStreamer pipeline with zero-copy DMA buffers 
and OpenGL optimizations in HAL.

This example is intended to run locally on target.
Specify `--camera <device>` to select a different camera device.
"""

from typing import Optional
from argparse import ArgumentParser
from pathlib import Path
import time
import sys
import os

from PIL import Image
import numpy as np

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

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

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.gstreamer_utils import (_PYCAIRO_AVAILABLE, CairoWindow, 
                                   _build_pipeline, has_display, get_format)

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


class ResizedGStreamerCapture:
    def __init__(self, camera: str, size: Optional[tuple] = None):
        if not _GSTREAMER_AVAILABLE:
            raise ImportError(
                "GStreamer is not available. Please install GStreamer and its Python bindings.")
        # This is needed to expose the app_sink.pull_sample() function.
        _ = GstApp
        Gst.init(None)

        # Display init
        self.camera = camera
        self.size = size
        self.use_cairo = _PYCAIRO_AVAILABLE and has_display()
        self.cairo_window = CairoWindow() if self.use_cairo else None

        # Performance measurements
        self.frame_count = 0
        self.window_start = time.perf_counter()
        self.fetch_fps = 0.0
        self.cpu_percent = 0.0
        self.process = psutil.Process() if _PSUTIL_AVAILABLE else None
        if self.process is not None:
            self.process.cpu_percent(interval=None)
        
        # Initialize pipeline
        self.loop = GLib.MainLoop()
        self.pipeline = _build_pipeline(self.camera, self.use_cairo)

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::error", self.on_error)

        appsink = self.pipeline.get_by_name("sink")
        if appsink is not None:
            appsink.connect("new-sample", self.on_new_sample)

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
        channels, fourcc = get_format(format)

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

    def on_error(self, bus, msg):
        err, dbg = msg.parse_error()
        print(err.message)
        self.loop.quit()

    def run(self):
        print('capturing from %s' % (self.camera))
        print("Press CTRL-C to stop")
        self.pipeline.set_state(Gst.State.PLAYING)
        self.loop.run()


def main():
    opts = ArgumentParser(
        description='Camera Resize using HAL')
    opts.add_argument('-c', '--camera', type=str, default='/dev/video3',
                      help='Camera device for capture')
    opts.add_argument('-s', '--size', type=str, default='640x360',
                      help='Resize dimensions in WIDTHxHEIGHT format, e.g. 640x360')
    args = opts.parse_args()

    camera_width, camera_height = map(int, args.size.split('x'))

    # GStreamer captures is intended for HAL in this use-case to show
    # benefits with the HAL optimizations.
    capture = ResizedGStreamerCapture(
        args.camera,
        size=(camera_width, camera_height)
    )
    capture.run()


if __name__ == "__main__":
    main()
