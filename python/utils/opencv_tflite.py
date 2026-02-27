# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""
TFLite model loading, inference, and post-processing utilities using OpenCV.

- Loads and runs TFLite models using tflite-runtime or TensorFlow
- Handles model metadata, preprocessing, and output decoding
- Supports YOLO box/mask decoding, NMS, and image transforms
"""

import numpy as np

try:
    import cv2
    _OPENCV_AVAILABLE = True
except ImportError:
    _OPENCV_AVAILABLE = False

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

from .common import (select_tflite_delegate, load_tflite_metadata,
                     build_metadata, get_shape)
from .opencv_utils import (decode_yolo_boxes, decode_yolo_masks, dequantize,
                           crop_masks, cv2_letterbox, cv2_resize)
from .nms import nms


class OpenCVTFLiteRunner:
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
        self.metadata = None
        if self.metadata is None:
            self.metadata = build_metadata(self.output_details)

    def infer(self, input_tensor: np.ndarray):
        # For quantized models, run input quantization parameters.
        if self.input_quantization is not None:
            if self.input_type == np.int8:
                scale, zero_point = self.input_quantization
                # Apply proper INT8 quantization: quantized = round(normalized / scale) + zero_point
                # First normalize to [0, 1] range, then quantize
                normalized = input_tensor.astype(np.float32) / 255.0
                quantized = np.round(
                    normalized / scale).astype(np.int32) + zero_point
                input_tensor = np.clip(quantized, -128, 127).astype(np.int8)

        input_tensor = input_tensor[None]
        if self.input_shape[-1] == 3 and input_tensor.shape[-1] == 4:
            # Drop alpha channel if model expects 3 channels but input has 4
            # channels
            input_tensor = input_tensor[:, :, :, :3]
        # Directly copy the input tensor into the model for TFLite.
        if self.input_tensor is not None:
            np.copyto(self.input_tensor(), input_tensor)

        self.model.invoke()

        outputs = [self.model.get_tensor(output["index"])
                   for output in self.output_details]

        return self.decode_outputs(outputs)

    def inference(self, image_path: str, save_path: str = None):
        if not _OPENCV_AVAILABLE:
            raise ImportError(
                "OpenCV is required to run this sample. " +
                "Please install OpenCV and try again."
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
            input_tensor = input_tensor[0]
            if input_tensor.shape[-1] == 4:
                # Drop alpha channel if present
                input_tensor = input_tensor[:, :, :3]
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
