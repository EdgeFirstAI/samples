# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""
ONNX model loading, inference, and post-processing utilities using OpenCV.

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
    import cv2
    _OPENCV_AVAILABLE = True
except ImportError:
    _OPENCV_AVAILABLE = False

try:
    import onnxruntime as ort
    _ONNX_RUNTIME_AVAILABLE = True
except ImportError:
    _ONNX_RUNTIME_AVAILABLE = False


sys.path.append(str(Path(__file__).resolve().parents[2]))

from utils.opencv_utils import (dequantize, decode_yolo_boxes,
                                decode_yolo_masks, crop_masks, cv2_letterbox,
                                cv2_resize)
from utils.common import (get_shape, check_normalized_boxes,
                          load_onnx_metadata, select_onnx_providers,
                          build_metadata)
from utils.nms import nms


class OpenCVONNXRunner:
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

    def infer(self, input_tensor: np.ndarray):
        # This method is used by camera_model.py and letterbox is already
        # performed.
        if self.input_type in [np.float32, np.float16]:
            input_array = input_tensor.astype(self.input_type) / 255.0
        else:
            input_array = input_tensor.astype(self.input_type)

        if self.transpose:
            # Transpose from (height, width, channels) to (channels, height,
            # width)
            input_array = np.transpose(input_array, (2, 0, 1))
        input_array = input_array[None]  # Add batch dimension

        outputs = self.ort_session.run(self.output_names,
                                       {self.input_name: input_array})

        # Normalize bounding boxes which is needed to decode the outputs.
        for x in outputs:
            if len(x.shape) == 3:
                if x.dtype in [np.float32, np.float16]:
                    x[:, :4, :] = check_normalized_boxes(
                        x[:, :4, :], width=self.input_shape[1],
                        height=self.input_shape[0]
                    )
        return self.decode_outputs(outputs)

    def inference(self, image_path: str, save_path: str = None):
        if not _OPENCV_AVAILABLE:
            raise ImportError(
                "OpenCV is required for this example. " +
                "Please install it with `pip install opencv-python`."
            )

        input_tensor = cv2.imread(image_path)
        input_tensor = cv2_letterbox(input_tensor, size=(self.input_shape[1],
                                                         self.input_shape[0]))
        boxes, scores, classes, masks = self.infer(input_tensor)

        # Denormalize box coordinates
        boxes[:, [0, 2]] *= self.input_shape[1]
        boxes[:, [1, 3]] *= self.input_shape[0]
        boxes = boxes.astype(np.int32)

        if save_path is not None:
            alpha = 0.50
            for i in range(boxes.shape[0]):
                label = (
                    self.labels[classes[i]]
                    if self.labels is not None
                    else classes[i]
                )
                cv2.putText(
                    input_tensor,
                    f"{label}: {scores[i]:.2f}",
                    (boxes[i, 0], boxes[i, 1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2
                )
                cv2.rectangle(input_tensor,
                              (boxes[i, 0], boxes[i, 1]),
                              (boxes[i, 2], boxes[i, 3]), (0, 255, 0), 2)
                input_tensor[masks[i] > 0] = (
                    input_tensor[masks[i] > 0] * (1 - alpha) +
                    np.array([0, 255, 0]) * alpha
                )
            cv2.imwrite(save_path, input_tensor)
        return boxes, scores, classes, masks

    def decode_outputs(self, outputs: list):
        boxes, scores, classes = None, None, None
        masks, protos = None, None
        for i, metadata in enumerate(self.metadata["outputs"]):
            x = outputs[i]
            x = x.astype(np.float32) if x.dtype == np.float16 else x
            if (metadata["quantization"]
                    is not None and x.dtype != np.float32):
                x = dequantize(x, *metadata["quantization"])

            if metadata["type"] == "protos":
                protos = x
            elif metadata["type"] == "detection":
                # Decode detection outputs
                boxes, scores, masks = decode_yolo_boxes(
                    p=x,
                    with_masks=len(outputs) > 1,
                    nc=(len(self.labels)
                        if self.labels is not None else 0)
                )

                # Run NMS
                boxes, scores, classes, masks = nms(
                    boxes=boxes,
                    scores=scores,
                    masks=masks,
                    iou_threshold=self.iou,
                    score_threshold=self.score,
                    max_detections=self.max_boxes,
                    class_agnostic=True,
                    nms_type="numpy"
                )

        if masks is not None and protos is not None:
            masks = decode_yolo_masks(masks, protos=protos)

            # Mask postprocessing: resize + crop.
            if masks.shape[0] > 0:
                masks = (masks > 0).astype(np.uint8)
                masks = [cv2_resize(mask, size=(self.input_shape[1],
                                                self.input_shape[0]))
                         for mask in masks]
                masks = np.stack(masks, axis=0)
                masks = crop_masks(masks, boxes)

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

    runner = OpenCVONNXRunner(
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
