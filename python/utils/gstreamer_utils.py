# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""
Functions needed for the GStreamer examples.
"""

from typing import Tuple
import os

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

import edgefirst_hal as ef


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


def has_display() -> bool:
    return (
        os.environ.get("DISPLAY") or
        os.environ.get("WAYLAND_DISPLAY")
    ) and os.access("/dev/dri", os.R_OK)


def get_format(format: str) -> Tuple[int, ef.PixelFormat]:
    if format == "NV12":
        # planar YUV 4:2:0, usually 1.5 bytes per pixel
        channels = 1  # single channel for Y plane; need special handling
        format = ef.PixelFormat.Nv12
    elif format in ["YUY2", "YUYV"]:
        channels = 2
        format = ef.PixelFormat.Yuyv
    elif format == "RGB":
        channels = 3
        format = ef.PixelFormat.Rgb
    elif format == "RGBA":
        channels = 4
        format = ef.PixelFormat.Rgba
    elif format == "ARGB":
        channels = 4
        format = ef.PixelFormat.PlanarRgba
    else:
        raise RuntimeError(f"Unsupported pixel format: {format}")
    return channels, format


def _build_pipeline(camera: str, use_cairo: bool = False):
    if has_display() and not use_cairo:
        # cmd:
        # gst-launch-1.0 v4l2src device=/dev/video3 ! \
        # video/x-raw ! imxvideoconvert_g2d ! \
        # video/x-raw,format=RGBA ! queue ! waylandsink
        pipeline = Gst.parse_launch("""
            v4l2src device=%s !
            video/x-raw !
            imxvideoconvert_g2d !
            video/x-raw,format=RGBA !
            queue !
            waylandsink
        """ % (camera))
    else:
        # cmd:
        # gst-launch-1.0 v4l2src device=/dev/video3 ! \
        # video/x-raw,format=YUY2 ! imxvideoconvert_g2d ! \
        # video/x-raw,format=RGBA ! queue ! \
        # appsink sync=true max-buffers=1 drop=true name=sink
        # emit-signals=true
        pipeline = Gst.parse_launch("""
            v4l2src device=%s io-mode=dmabuf !
            video/x-raw,format=YUY2 !
            imxvideoconvert_g2d !
            video/x-raw,format=RGBA !
            appsink sync=true max-buffers=1 drop=true name=sink emit-signals=true
        """ % (camera))

    return pipeline
