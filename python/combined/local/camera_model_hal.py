# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""EdgeFirst Samples - Camera Model Sample using HAL (Local - on-device).

Reads from the camera, /dev/video3 by default and runs the model
inference on the captured frames and displays the frames in a window if available.

This example is intended to run locally on target.
Specify `--camera <device>` to select a different camera device, 0.
"""

from argparse import ArgumentParser
from pathlib import Path
import time
import sys
import os

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
from utils.hal_tflite import HALTFLiteRunner
from utils.hal_onnx import HALONNXRunner


class GStreamerInference:
    def __init__(
        self,
        camera: str,
        model_path: str,
        score: float = 0.50,
        iou: float = 0.50,
        max_boxes: int = 300
    ):
        if not _GSTREAMER_AVAILABLE:
            raise ImportError(
                "GStreamer is not available. Please install GStreamer and its Python bindings.")
        # This is needed to expose the app_sink.pull_sample() function.
        _ = GstApp
        Gst.init(None)

        # Display init
        self.camera = camera
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

        # Model init
        if os.path.splitext(os.path.basename(model_path)
                            )[-1].lower() == ".tflite":
            self.runner = HALTFLiteRunner(
                model_path=model_path,
                score=score,
                iou=iou,
                max_boxes=max_boxes
            )
        elif os.path.splitext(os.path.basename(model_path))[-1].lower() == ".onnx":
            self.runner = HALONNXRunner(
                model_path=model_path,
                score=score,
                iou=iou,
                max_boxes=max_boxes
            )
        else:
            raise NotImplementedError(
                "Only ONNX and TFLite Ultralytics models are supported in this sample.")

    def on_new_sample(self, app_sink):
        start_pipeline = time.perf_counter()
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
            boxes, scores, classes, masks = self.runner.infer(tensor)
            # Render detections on the image using the HAL converter
            self.runner.converter.draw_masks(
                dst=self.runner.dst,
                bbox=boxes,
                scores=scores,
                classes=classes,
                seg=masks
            )

            channels = 1 if self.runner.dst.format == ef.FourCC.GREY else 4
            if self.use_cairo and self.cairo_window is not None:
                with self.runner.dst.map() as m:
                    n = np.array(
                        m.view()).reshape(
                        (self.runner.dst.height, self.runner.dst.width, channels))
                    if channels == 4:
                        n = n[:, :, :3]
                    n = np.ascontiguousarray(n, dtype=np.uint8)

                    end_pipeline = time.perf_counter() - start_pipeline
                    if self.process is not None:
                        self.cpu_percent = self.process.cpu_percent(
                            interval=None)
                    performance = (
                        f"CPU: {self.cpu_percent:.2f}% | "
                        f"End2End Latency: {end_pipeline * 1000:.2f} ms"
                    )

                    GLib.idle_add(
                        self.cairo_window.update_frame, n, performance)
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
        description='Camera Letterbox')
    opts.add_argument('--model', type=str, required=True,
                      help='The path to the TFLite model')
    opts.add_argument('-c', '--camera', type=str, default='/dev/video3',
                      help='Camera device for capture')
    opts.add_argument('-s', '--score', type=float, default=0.50,
                      help='Specify the score threshold for NMS')
    opts.add_argument('-i', '--iou', type=float, default=0.50,
                      help='Specify the IoU threshold for NMS')
    opts.add_argument('--max-boxes', type=int, default=300,
                      help='Specify the maximum number of boxes')
    args = opts.parse_args()

    # GStreamer captures is intended for HAL in this use-case to show
    # benefits with the HAL optimizations.
    capture = GStreamerInference(
        int(args.camera) if args.camera.isdigit() else args.camera,
        model_path=args.model,
        score=args.score,
        iou=args.iou,
        max_boxes=args.max_boxes
    )
    capture.run()


if __name__ == "__main__":
    main()
