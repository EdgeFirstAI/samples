# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""EdgeFirst Samples - GStreamer Sample (Local - on-device).

Reads from the camera, /dev/video3 by default and displays the captured
frame in a window if available. 

This example is intended to run locally on an EdgeFirst device.
Specify `--camera <device>` to select a different camera device, e.g. /dev/video3. 
Specify --resolution to output the frame in a different resolution, e.g. 1280x720.
"""

from argparse import ArgumentParser
import os

# Note autopep8 and other auto-formatters can break this piece of code so we
# include a comment of the appropriate layout for reference.  This is required
# by the GObject Introspection for Python library.
#
# https://pygobject.readthedocs.io/
#
import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
from gi.repository import Gst, GstApp, GLib


class GStreamerCapture:
    def __init__(self, camera: str, height: int, width: int):
        # This is needed to expose the app_sink.pull_sample() function.
        _ = GstApp
        Gst.init(None)

        self.camera = camera
        self.camera_width, self.camera_height = width, height
        self.frame_count = 0
        self.loop = GLib.MainLoop()
        self.pipeline = self._build_pipeline()

    @staticmethod
    def has_display() -> bool:
        return (
            os.environ.get("DISPLAY") or
            os.environ.get("WAYLAND_DISPLAY")
        ) and os.access("/dev/dri", os.R_OK)

    def _build_pipeline(self):
        if self.has_display():
            pipeline = Gst.parse_launch("""
                v4l2src device=%s !
                video/x-raw,width=%d,height=%d !
                queue !
                waylandsink
            """ % (self.camera, self.camera_width, self.camera_height))
        else:
            pipeline = Gst.parse_launch("""
                v4l2src device=%s !
                video/x-raw,width=%d,height=%d !
                queue !
                appsink sync=true max-buffers=1 drop=true name=sink emit-signals=true
            """ % (self.camera, self.camera_width, self.camera_height))

        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::error", self.on_error)

        appsink = pipeline.get_by_name("sink")
        if appsink is not None:
            appsink.connect("new-sample", self.on_new_sample)

        return pipeline

    def on_new_sample(self, app_sink):
        _ = app_sink.pull_sample()
        self.frame_count += 1
        print(f"Captured frame: {self.frame_count}", end="\r")
        return False

    def on_error(self, bus, msg):
        err, dbg = msg.parse_error()
        print(err.message)
        self.loop.quit()

    def run(self):
        print('capturing from %s at %dx%d' %
              (self.camera, self.camera_width, self.camera_height))
        print("Press CTRL-C to stop")
        self.pipeline.set_state(Gst.State.PLAYING)
        self.loop.run()


def main():
    opts = ArgumentParser(
        description='GStreamer Camera with Python')
    opts.add_argument('-c', '--camera', type=str, default="/dev/video3",
                      help='video4linux2 camera device for capture')
    opts.add_argument('-r', '--resolution', type=str, default='640x480',
                      help='camera capture resolution')
    args = opts.parse_args()

    camera_width, camera_height = map(int, args.resolution.split('x'))
    capture = GStreamerCapture(args.camera, camera_height, camera_width)
    capture.run()


if __name__ == "__main__":
    main()
