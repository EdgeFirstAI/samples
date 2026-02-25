# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""
Image and tensor transformation utilities for model preprocessing
and postprocessing in EdgeFirst workflows.

- Includes box format conversions, mask cropping, dequantization,
and YOLO output decoding
- Used for preparing model inputs and interpreting outputs
"""

from typing import Tuple, Union

import numpy as np


def xcycwh2xyxy(boxes: np.ndarray) -> np.ndarray:
    return np.concatenate([
        boxes[:, 0:2] - boxes[:, 2:4] / 2,
        boxes[:, 0:2] + boxes[:, 2:4] / 2
    ], axis=1)


def crop_masks(
    masks: np.ndarray,
    boxes: np.ndarray,
) -> np.ndarray:
    n, h, w = masks.shape
    x1, y1, x2, y2 = np.split(  # pylint: disable=unbalanced-tuple-unpacking
        boxes[:, :, np.newaxis], 4, axis=1)  # shape (n, 1, 1)
    r = np.arange(w, dtype=boxes.dtype)[None, None, :]  # rows shape(1,1,w)
    c = np.arange(h, dtype=boxes.dtype)[None, :, None]  # cols shape(1,h,1)

    cropped = masks * ((r >= x1 * w) * (r < x2 * w)
                       * (c >= y1 * h) * (c < y2 * h))
    return cropped


def dequantize(x: np.ndarray, scale: float, zero_point: float) -> np.ndarray:
    if scale > 0:
        x = (x.astype(np.float32) - zero_point) * scale  # re-scale
    return x


def decode_yolo_boxes(
    p: np.ndarray,
    with_masks: bool,
    nc: int,
) -> Tuple[np.ndarray, np.ndarray, Union[np.ndarray, None]]:
    masks = None
    if p.shape[0] == 1:
        p = p[0]
    # Only transpose if shapes are [116, 8400] or [85, 25200]
    if p.shape[0] < p.shape[1]:
        # Transposing shape (116, 8400) -> (8400, 116).
        p = p.transpose((1, 0))
    boxes = xcycwh2xyxy(boxes=p[:, 0:4])
    if with_masks:
        det_i = p.shape[1] - 32
        scores = p[:, 4:det_i]
        masks = p[:, det_i:]  # Additional 32 protos from segmentation models.
    else:
        # Heuristic fallback for models without score_format metadata.
        # YOLOv5 models contains [x, y, x, y, obj_conf, cls_conf] outputs.
        if p.shape[1] == nc + 5:
            scores = p[:, 5:]
            scores *= p[:, 4:5]  # conf = obj_conf * cls_conf # NOSONAR
        # YOLOv8 and YOLOv11
        else:
            scores = p[:, 4:]
    return boxes, scores, masks


def decode_yolo_masks(masks: np.ndarray, protos: np.ndarray) -> np.ndarray:
    # In case of shape (1, 32, h, w).
    if protos.shape[1] == 32:
        c, h, w = protos[0].shape
    else:
        h, w, c = protos[0].shape
        protos = np.transpose(protos, (0, 3, 1, 2))
    return np.matmul(masks, protos.reshape(c, -1)).reshape(-1, h, w)


def check_normalized_boxes(
    boxes: np.ndarray, width: int, height: int
) -> np.ndarray:
    # Checks if the boxes are normalized between 0 and 1.
    # If not, it normalizes them using the provided width and height.
    boundary = (boxes >= 0) & (boxes <= 1)
    if boundary.shape[0] > 0:
        normalized_conf = np.mean(boundary)
        if normalized_conf < 0.80 and boxes.shape[0] > 0:
            boxes[:, [0, 2]] /= width
            boxes[:, [1, 3]] /= height
    return boxes


def get_shape(shape: list[int]) -> Tuple[Tuple[int, int], bool]:
    transpose = False
    if shape[-1] in [1, 2, 3, 4]:
        channels = shape[-1]
        # This includes batch size. Format (1, height, width, channels).
        if len(shape) == 4:
            height, width = shape[1:3]
        else:
            height, width = shape[0:2]
    else:
        transpose = True
        # This includes batch size. Format (1, channels, height, width).
        if len(shape) == 4:
            height, width = shape[2:4]
            channels = shape[1]
        else:
            height, width = shape[1:3]
            channels = shape[0]
    return (height, width, channels), transpose
