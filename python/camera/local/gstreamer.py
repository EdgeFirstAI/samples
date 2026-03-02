# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""EdgeFirst Samples - GStreamer Sample (Local - on-device).

Reads from the camera, /dev/video3 by default and displays the captured
frame in a window if available.

This example is intended to run locally on target.
Specify `--camera <device>` to select a different camera device, e.g. /dev/video3.
Specify --resolution to output the frame in a different resolution, e.g. 1280x720.
"""

from argparse import ArgumentParser
from pathlib import Path
import time
import sys

import numpy as np

# Note autopep8 and other auto-formatters can break this piece of code so we
# include a comment of the appropriate layout for reference.  This is required
# by the GObject Introspection for Python library.
#
# https://pygobject.readthedocs.io/
#

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

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from utils.gstreamer_utils import (_PYCAIRO_AVAILABLE, CairoWindow,
                                   _build_pipeline, has_display)


class GStreamerCapture:
    def __init__(self, camera: str, use_cairo: bool = False):
        if not _GSTREAMER_AVAILABLE:
            raise ImportError(
                "GStreamer is not available. Please install GStreamer and its Python bindings.")
        # This is needed to expose the app_sink.pull_sample() function.
        _ = GstApp
        Gst.init(None)

        # Display init
        self.camera = camera
        self.use_cairo = use_cairo and _PYCAIRO_AVAILABLE and has_display()
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

        width = caps.get_structure(0).get_value("width")
        height = caps.get_structure(0).get_value("height")
        structure = caps.get_structure(0)
        pixel_format = structure.get_value("format")

        if pixel_format not in ["RGB", "RGBA"]:
            raise RuntimeError(
                f"Unsupported format for direct NumPy mapping: {pixel_format}. "
                "Use videoconvert to RGB in the pipeline."
            )

        success, map_info = buffer.map(Gst.MapFlags.READ)
        if not success:
            raise RuntimeError("Failed to map buffer to CPU memory")

        try:
            channels = 4 if pixel_format == "RGBA" else 3
            stride = structure.get_value("stride") if structure.has_field(
                "stride") else width * channels
            data = np.frombuffer(map_info.data, dtype=np.uint8)
            frame = data.reshape(
                (height, stride // channels, channels))[:, :width, :]
            frame = np.ascontiguousarray(frame)
        finally:
            buffer.unmap(map_info)

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

        if self.use_cairo and self.cairo_window is not None:
            GLib.idle_add(self.cairo_window.update_frame, frame)
            if self.cairo_window.closed:
                return True
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
        description='GStreamer Camera with Python')
    opts.add_argument('-c', '--camera', type=str, default='/dev/video3',
                      help='video4linux2 camera device for capture')
    opts.add_argument('--use-cairo', action='store_true',
                      help='Use Cairo for display if available')
    args = opts.parse_args()

    capture = GStreamerCapture(
        int(args.camera) if args.camera.isdigit() else args.camera,
        use_cairo=args.use_cairo)
    capture.run()


if __name__ == "__main__":
    main()
