# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""
ONNX model loading, inference, and post-processing utilities
for EdgeFirst workflows using HAL.

- Loads and runs ONNX models using ONNX Runtime
- Handles model metadata, preprocessing, and output decoding
- Supports YOLO box/mask decoding, NMS, and image transforms
"""

from argparse import ArgumentParser
from pathlib import Path
import sys
import os

import numpy as np

try:
    import onnxruntime as ort
    _ONNX_RUNTIME_AVAILABLE = True
except ImportError:
    _ONNX_RUNTIME_AVAILABLE = False

import edgefirst_hal as ef

sys.path.append(str(Path(__file__).resolve().parents[2]))

from utils.common import (get_shape, check_normalized_boxes,
                          load_onnx_metadata, select_onnx_providers,
                          build_metadata)
from utils.hal_utils import hal_letterbox


class HALONNXRunner:
    def __init__(
        self,
        model_path: str,
        score: float = 0.50,
        iou: float = 0.50,
        max_boxes: int = 300
    ):
        if not _ONNX_RUNTIME_AVAILABLE:
            raise ImportError(
                "ONNX Runtime is required for this example. " +
                "Please install it with `pip install onnxruntime`."
            )

        self.score = score
        self.iou = iou
        self.max_boxes = max_boxes

        providers = select_onnx_providers()
        self.ort_session = ort.InferenceSession(
            model_path, providers=providers)
        self.output_names = [x.name for x in self.ort_session.get_outputs()]

        self.input_type = (np.float16 if "float16" in self.ort_session.get_inputs()[0].type
                           else np.float32 if "float" in self.ort_session.get_inputs()[0].type
                           else np.uint8 if "uint8" in self.ort_session.get_inputs()[0].type
                           else np.int8 if "int8" in self.ort_session.get_inputs()[0].type
                           else self.ort_session.get_inputs()[0].type)
        self.input_shape, self.transpose = get_shape(
            self.ort_session.get_inputs()[0].shape)
        self.input_name = self.ort_session.get_inputs()[0].name
        outputs = self.ort_session.get_outputs()

        self.metadata, self.labels = load_onnx_metadata(model_path)
        if self.metadata is None:
            self.metadata = build_metadata(outputs)

        # To use OpenGL assign image FourCC as RGBA.
        self.dst = ef.TensorImage(self.input_shape[1],
                                  self.input_shape[0], ef.FourCC.RGBA)
        self.decoder = ef.Decoder(
            self.metadata,
            score_threshold=score,
            iou_threshold=iou,
        )
        self.converter = ef.ImageProcessor()

    def base_infer(self, tensor_image: ef.TensorImage):
        hal_letterbox(tensor_image, self.dst)

        input_array = np.zeros((self.dst.height,
                                self.dst.width, self.input_shape[-1]),
                               dtype=self.input_type)

        if self.input_type in [np.float32, np.float16]:
            norm = ef.Normalization.UNSIGNED
        else:
            norm = ef.Normalization.DEFAULT
        self.dst.normalize_to_numpy(input_array, normalization=norm)

        if self.transpose:
            # Transpose from (height, width, channels) to (channels, height,
            # width)
            input_array = np.transpose(input_array, (2, 0, 1))
        input_array = input_array[None]  # Add batch dimension

        return self.ort_session.run(self.output_names,
                                    {self.input_name: input_array})

    def infer(self, tensor_image: ef.TensorImage):
        outputs = self.base_infer(tensor_image)
        # Normalize bounding boxes which is needed to decode the outputs.
        for x in outputs:
            if len(x.shape) == 3:
                if x.dtype in [np.float32, np.float16]:
                    x[:, :4, :] = check_normalized_boxes(
                        x[:, :4, :], width=self.input_shape[1],
                        height=self.input_shape[0]
                    )
        return self.decoder.decode(outputs, max_boxes=self.max_boxes)

    def static_infer(self, tensor_image: ef.TensorImage):
        outputs = self.base_infer(tensor_image)

        detection_output, segmentation_output = None, None
        for x in outputs:
            if len(x.shape) == 3:
                if x.dtype in [np.float32, np.float16]:
                    # Normalize bounding boxes which is needed to decode the
                    # outputs.
                    x[:, :4, :] = check_normalized_boxes(
                        x[:, :4, :], width=self.input_shape[1],
                        height=self.input_shape[0]
                    )
                detection_output = x[0]
            elif len(x.shape) == 4:
                segmentation_output = x[0]
                # Tranpose (32, 160, 160) to (160, 160, 32)
                segmentation_output = segmentation_output.transpose(
                    1, 2, 0)  # (H, W, C)

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
            self.converter.render_to_image(
                self.dst,
                bbox=boxes,
                scores=scores,
                classes=classes,
                seg=masks
            )
            self.dst.save_jpeg(save_path)
        return boxes, scores, classes, masks


def main():
    opts = ArgumentParser(
        description="Run ONNX model on a sample image"
    )
    opts.add_argument("--model", type=str, required=True,
                      help="Path to ONNX model")
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

    if os.path.splitext(os.path.basename(args.model))[-1] != ".onnx":
        raise NotImplementedError(
            "Only Ultralytics ONNX models are supported in this sample.")

    runner = HALONNXRunner(
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
