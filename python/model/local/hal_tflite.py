# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""
TFLite model loading, inference, and post-processing utilities for EdgeFirst workflows.

- Loads and runs TFLite models using tflite-runtime or TensorFlow
- Handles model metadata, preprocessing, and output decoding
- Supports YOLO box/mask decoding, NMS, and image transforms
"""

from argparse import ArgumentParser
from pathlib import Path
import sys
import os

import numpy as np

try:
    from tflite_runtime.interpreter import Interpreter  # type: ignore
    _TFLITE_RUNTIME_AVAILABLE = True
except ImportError:
    _TFLITE_RUNTIME_AVAILABLE = False

    try:
        import tensorflow as tf  # type: ignore
        Interpreter = tf.lite.Interpreter
        _TENSORFLOW_AVAILABLE = True
    except ImportError as e:
        _TENSORFLOW_AVAILABLE = False

import edgefirst_hal as ef

sys.path.append(str(Path(__file__).resolve().parents[2]))

from utils.common import (select_tflite_delegate, get_shape,
                          load_tflite_metadata, build_metadata)
from utils.hal_utils import hal_letterbox


class HALTFLiteRunner:
    def __init__(
        self,
        model_path: str,
        score: float = 0.50,
        iou: float = 0.50,
        max_boxes: int = 300
    ):
        if not _TFLITE_RUNTIME_AVAILABLE:
            print("[WARNING] tflite-runtime is not installed in the system.")
            if not _TENSORFLOW_AVAILABLE:
                raise ImportError(
                    "Please install tflite-runtime or tensorflow to run TFLite models.")

        self.score = score
        self.iou = iou
        self.max_boxes = max_boxes

        ext_delegate = select_tflite_delegate()
        if ext_delegate:
            self.model = Interpreter(
                model_path=model_path,
                experimental_delegates=[ext_delegate]
            )
        else:
            self.model = Interpreter(model_path=model_path)
        self.model.allocate_tensors()
        self.input_details = self.model.get_input_details()
        self.output_details = self.model.get_output_details()
        self.input_quantization = self.input_details[0]["quantization"]
        self.input_type = self.input_details[0]["dtype"]
        self.input_tensor = self.model.tensor(self.input_details[0]["index"])
        self.input_shape, self.transpose = get_shape(
            self.input_details[0]["shape"])

        self.metadata, self.labels = load_tflite_metadata(model_path)
        if self.metadata is None:
            self.metadata = build_metadata(self.output_details)

        # To use OpenGL assign image FourCC as RGBA.
        self.dst = ef.TensorImage(
            self.input_shape[1], self.input_shape[0], ef.FourCC.RGBA)
        self.decoder = ef.Decoder(
            self.metadata,
            score_threshold=self.score,
            iou_threshold=self.iou
        )
        self.converter = ef.ImageProcessor()

    def base_infer(self, tensor_image: ef.TensorImage):
        # Input quantization
        zero_point = None
        if self.input_quantization is not None:
            if self.input_type == np.uint8:
                # For uint8 quantized models, use zero_point=0 (raw pixel data)
                zero_point = 0
            elif self.input_type == np.int8:
                zero_point = abs(self.input_quantization[-1])

        hal_letterbox(tensor_image, self.dst)
        self.dst.normalize_to_numpy(self.input_tensor()[0, :, :, :],
                                    normalization=ef.Normalization.DEFAULT,
                                    zero_point=zero_point)
        self.model.invoke()
        return [self.model.get_tensor(output["index"])
                for output in self.output_details]

    def infer(self, tensor_image: ef.TensorImage):
        outputs = self.base_infer(tensor_image)
        return self.decoder.decode(outputs, max_boxes=self.max_boxes)

    def static_infer(self, tensor_image: ef.TensorImage):
        outputs = self.base_infer(tensor_image)

        detection_output, segmentation_output = None, None
        for x in outputs:
            if len(x.shape) == 3:
                detection_output = x[0]
            elif len(x.shape) == 4:
                segmentation_output = x[0]

        if segmentation_output is not None and detection_output is not None:
            return ef.Decoder.decode_yolo_segdet(
                boxes=detection_output,
                protos=segmentation_output,
                score_threshold=self.score,
                iou_threshold=self.iou,
                max_boxes=self.max_boxes
            )
        return ef.Decoder.decode_yolo_det(
            boxes=detection_output,
            score_threshold=self.score,
            iou_threshold=self.iou,
            max_boxes=self.max_boxes
        )

    def inference(self, image_path: str, save_path: str = None):
        tensor_image = ef.TensorImage.load(image_path)
        boxes, scores, classes, masks = self.infer(tensor_image)

        if save_path is not None:
            # Render detections on the image using the HAL converter
            self.converter.draw_masks(
                dst=self.dst,
                bbox=boxes,
                scores=scores,
                classes=classes,
                seg=masks
            )
            self.dst.save_jpeg(save_path)
        return boxes, scores, classes, masks


def main():
    opts = ArgumentParser(
        description="Run TFLite model on a sample image"
    )
    opts.add_argument("--model", type=str, required=True,
                      help="Path to TFLite model")
    opts.add_argument("--image", type=str, required=True,
                      help="Path to input image")
    opts.add_argument('-s', '--score', type=float, default=0.50,
                      help='Specify the score threshold for NMS')
    opts.add_argument('-i', '--iou', type=float, default=0.50,
                      help='Specify the IoU threshold for NMS')
    opts.add_argument('--max-boxes', type=int, default=300,
                      help='Specify the maximum number of devices')
    opts.add_argument('--save', type=str,
                      help='Whether to save the output visualization as output.jpg')
    args = opts.parse_args()

    if os.path.splitext(os.path.basename(args.model))[-1] != ".tflite":
        raise NotImplementedError(
            "Only quantized Ultralytics TFLite models are supported in this sample.")

    runner = HALTFLiteRunner(
        model_path=args.model,
        score=args.score,
        iou=args.iou,
        max_boxes=args.max_boxes
    )

    # Visualize outputs
    save_path = None
    if args.save:
        save_path = os.path.expanduser(args.save)
        # Create parent directory only
        parent_dir = os.path.dirname(save_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

    boxes, scores, classes, masks = runner.inference(
        args.image, save_path=save_path)

    num_dets = 0 if boxes is None else int(boxes.shape[0])
    print(f"Found objects: {num_dets}")
    if num_dets > 0:
        for i in range(num_dets):
            label = (
                runner.labels[classes[i]]
                if runner.labels is not None and classes is not None
                else classes[i]
            )
            print(
                f"  - {label}: score={scores[i]:.3f} box={boxes[i].tolist()}"
            )


if __name__ == "__main__":
    main()
