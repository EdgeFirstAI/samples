# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""
Image and tensor transformation utilities for model preprocessing
and postprocessing using OpenCV.

- Includes box format conversions, mask cropping, dequantization,
and YOLO output decoding
- Used for preparing model inputs and interpreting outputs
"""

from typing import Optional, Tuple, Union

from PIL import Image
import numpy as np

try:
    import cv2
    _OPENCV_AVAILABLE = True
except ImportError:
    _OPENCV_AVAILABLE = False


def has_display() -> bool:
    if not _OPENCV_AVAILABLE:
        return False
    
    try:
        cv2.namedWindow("Camera", cv2.WINDOW_AUTOSIZE)
        visible = cv2.getWindowProperty("Camera", cv2.WND_PROP_VISIBLE)
        return visible >= 1
    except cv2.error:
        return False


def _build_pipeline(camera: str) -> str:
    return (
        f"v4l2src device={camera} io-mode=dmabuf ! "
        "video/x-raw,format=YUY2 ! "
        "imxvideoconvert_g2d ! "
        "video/x-raw,format=BGRA ! "
        "appsink drop=true max-buffers=1 sync=false"
    )


def cv2_resize(image: np.ndarray, size: Optional[tuple] = None) -> np.ndarray:
    if not _OPENCV_AVAILABLE:
        raise ImportError(
            "OpenCV is not available. Please install OpenCV to use cv2_resize.")
    if size is None:
        return image
    return cv2.resize(image, size, interpolation=cv2.INTER_LINEAR)


def pillow_resize(image: np.ndarray,
                  size: Optional[tuple] = None) -> np.ndarray:
    if size is None:
        return image
    im = Image.fromarray(image.astype(np.uint8))
    im = im.resize(size)
    return np.array(im)


def cv2_letterbox(
    image: np.ndarray,
    size: Optional[tuple] = None,
    constant: int = 114,
    method: str = "opencv"
) -> np.ndarray:
    if not _OPENCV_AVAILABLE:
        raise ImportError("OpenCV is not available. " +
        "Please install OpenCV to use cv2_letterbox.")
    height, width = image.shape[:2]
    scale = min(size[0] / width, size[1] / height)
    new_width = int(round(width * scale))
    new_height = int(round(height * scale))

    if scale != 1.0:
        if method == "opencv":
            image = cv2_resize(image, size=(new_width, new_height))
        else:
            image = pillow_resize(image, size=(new_width, new_height))

    # Compute padding
    dw, dh = size[0] - new_width, size[1] - new_height  # wh padding
    top = round(dh / 2)
    bottom = dh - top
    left = round(dw / 2)
    right = dw - left

    if method == "opencv":
        padded_image = cv2.copyMakeBorder(
            image, top, bottom, left, right, cv2.BORDER_CONSTANT,
            value=(constant, constant, constant))  # add border
    else:
        padded_image = np.zeros(
            (3, new_height + top + bottom, new_width + left + right))

        for i, _ in enumerate(padded_image):
            padded_image[i, :, :] = np.pad(
                image[:, :, i], ((top, bottom), (left, right)),
                mode='constant', constant_values=constant)
        padded_image = np.transpose(
            padded_image, axes=(1, 2, 0)).astype(np.uint8)
    return padded_image


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
