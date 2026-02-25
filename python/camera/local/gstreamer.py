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
import os
import time

import numpy as np

# Note autopep8 and other auto-formatters can break this piece of code so we
# include a comment of the appropriate layout for reference.  This is required
# by the GObject Introspection for Python library.
#
# https://pygobject.readthedocs.io/
#

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
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, Gdk, GdkPixbuf
    import cairo
    _PYCAIRO_AVAILABLE = True
except Exception:
    _PYCAIRO_AVAILABLE = False

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False


class GStreamerCapture:
    def __init__(self, camera: str, use_cairo: bool = False):
        if not _GSTREAMER_AVAILABLE:
            raise ImportError(
                "GStreamer is not available. Please install GStreamer and its Python bindings.")
        # This is needed to expose the app_sink.pull_sample() function.
        _ = GstApp
        Gst.init(None)

        self.camera = camera
        self.use_cairo = use_cairo and _PYCAIRO_AVAILABLE and self.has_display()
        self.cairo_window = CairoWindow() if self.use_cairo else None

        self.frame_count = 0
        self.window_start = time.perf_counter()
        self.fetch_fps = 0.0
        self.cpu_percent = 0.0
        self.process = psutil.Process() if _PSUTIL_AVAILABLE else None
        if self.process is not None:
            self.process.cpu_percent(interval=None)
        self.loop = GLib.MainLoop()
        self.pipeline = self._build_pipeline()

    @staticmethod
    def has_display() -> bool:
        return (
            os.environ.get("DISPLAY") or
            os.environ.get("WAYLAND_DISPLAY")
        ) and os.access("/dev/dri", os.R_OK)

    def _build_pipeline(self):
        if self.has_display() and not self.use_cairo:
            pipeline = Gst.parse_launch("""
                v4l2src device=%s !
                video/x-raw !
                queue !
                waylandsink
            """ % (self.camera))
        else:
            pipeline = Gst.parse_launch("""
                v4l2src device=%s !
                video/x-raw !
                videoconvert ! video/x-raw,format=RGB !
                queue !
                appsink sync=true max-buffers=1 drop=true name=sink emit-signals=true
            """ % (self.camera))

        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::error", self.on_error)

        appsink = pipeline.get_by_name("sink")
        if appsink is not None:
            appsink.connect("new-sample", self.on_new_sample)
        return pipeline

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

        if pixel_format != "RGB":
            raise RuntimeError(
                f"Unsupported format for direct NumPy mapping: {pixel_format}. "
                "Use videoconvert to RGB in the pipeline."
            )

        success, map_info = buffer.map(Gst.MapFlags.READ)
        if not success:
            raise RuntimeError("Failed to map buffer to CPU memory")

        try:
            channels = 3
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


class CairoWindow:
    def __init__(self, title: str = "Camera"):
        if not _PYCAIRO_AVAILABLE:
            raise RuntimeError("pycairo/GTK is not available")
        ok, _argv = Gtk.init_check()
        if not ok:
            raise RuntimeError("Gtk couldn't be initialized")
        self.title = title
        self.window = Gtk.Window(title=title)
        self.area = Gtk.DrawingArea()
        self.window.add(self.area)
        self.window.connect("destroy", self._on_destroy)
        self.area.connect("draw", self._on_draw)
        self.window.show_all()
        self.frame = None
        self.overlay_text = ""
        self.closed = False
        self._size_set = False

    def _on_destroy(self, *_args):
        self.closed = True

    def update_frame(self, frame: np.ndarray, overlay_text: str = ""):
        if self.closed:
            return False
        self.frame = frame
        self.overlay_text = overlay_text
        if not self._size_set:
            h, w = frame.shape[:2]
            self.window.resize(w, h)
            self._size_set = True
        self.area.queue_draw()
        return False

    def _on_draw(self, _widget, cr):
        if self.frame is None:
            return False
        frame = self.frame
        h, w = frame.shape[:2]
        if frame.ndim == 2:
            frame = np.stack([frame, frame, frame], axis=2)
        if frame.shape[2] == 4:
            frame = frame[:, :, :3]

        rowstride = frame.shape[1] * frame.shape[2]
        data = frame.tobytes()
        pixbuf = GdkPixbuf.Pixbuf.new_from_data(
            data,
            GdkPixbuf.Colorspace.RGB,
            False,
            8,
            w,
            h,
            rowstride,
        )
        Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
        cr.paint()

        if self.overlay_text:
            cr.set_source_rgba(0, 0, 0, 0.5)
            cr.rectangle(5, 5, 500, 28)
            cr.fill()
            cr.set_source_rgb(0, 1, 0)
            cr.select_font_face(
                "Sans",
                cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(16)
            cr.move_to(12, 24)
            cr.show_text(self.overlay_text)
        return False


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
