"""
Implementations for the Non-Maximum Suppression (NMS) algorithms.
"""

from typing import Tuple

import numpy as np


def nms(
    boxes: np.ndarray,
    scores: np.ndarray,
    masks: np.ndarray = None,
    iou_threshold: float = 0.70,
    score_threshold: float = 0.001,
    max_detections: int = 300,
    class_agnostic: bool = False,
    clip_boxes: bool = False,
    nms_type: str = "tensorflow"
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Deploy the NMS algorithm on object detection outputs. The NMS algorithm
    can be specified using "tensorflow" by default. Otherwise, "numpy"
    or "torch" are possible options.

    Parameters
    ----------
    boxes: np.ndarray
        Normalized input boxes to the NMS with shape (n, 4)
        in [xmin, ymin, xmax, ymax] format.
    scores: np.ndarray
        Input scores to the NMS (n, ).
    masks: np.ndarray
        (Optional) Instance segmentation masks to also
        to also be filtered during NMS.
    iou_threshold: float
        This is the IoU threshold for the NMS. Higher values
        are less strict in filtering overlapping detections.
    score_threshold: float
        The confidence score threshold for the NMS. Filters to accept
        more confident detections based on this threshold.
    max_detections: int
        The maximum number of boxes to be selected by NMS per class.
    class_agnostic: bool
        Run class-agnostic NMS. Default includes class.
    clip_boxes: bool
        If set to True, boxes will be clipped between 0 and 1. If False,
        the coordinates are kept as it is.
    nms_type: str
        By default the Tensorflow NMS algorithm is deployed by
        specifying "tensorflow" in this parameter. Otherwise, "numpy"
        or "torch" are possible options.

    Returns
    -------
    boxes : np.ndarray
        This contains only the valid bounding boxes post NMS.
    classes : np.ndarray
        This contains only the valid classes post NMS.
    scores : np.ndarray
        This contains only the valid scores post NMS.
    masks: np.ndarray
        This contains only the valid instance segmentation masks
        post NMS if it exists. Otherwise, None is returned.

    Raises
    ------
    ImportError
        Depending on the type of NMS specified, the TensorFlow or
        PyTorch libraries are needed to use the NMS+.
    """
    if nms_type == "tensorflow":
        return tensorflow_combined_nms(
            boxes=boxes,
            scores=scores,
            masks=masks,
            iou_threshold=iou_threshold,
            score_threshold=score_threshold,
            max_detections=max_detections,
            class_agnostic=class_agnostic,
            clip_boxes=clip_boxes
        )
    else:
        # Reshape boxes and scores and compute classes.
        scores = np.reshape(scores, (boxes.shape[0], -1))
        boxes = np.reshape(boxes, (-1, 4))
        classes = np.argmax(scores, axis=1).astype(np.uintp)

        # Prefilter boxes and scores by minimum score
        max_scores = np.max(scores, axis=1)
        mask = max_scores >= score_threshold

        # Prefilter the boxes, scores and classes IDs.
        scores = max_scores[mask]
        boxes = boxes[mask]
        classes = classes[mask]
        if masks is not None:
            masks = masks[mask]

        if nms_type == "torch":
            keep = torch_nms(
                boxes=boxes,
                scores=scores,
                iou_threshold=iou_threshold,
                max_detections=max_detections
            )
        else:
            keep = numpy_nms(
                boxes=boxes,
                scores=scores,
                iou_threshold=iou_threshold,
                max_detections=max_detections
            )

        # Filter boxes, scores, and classes.
        if len(keep):
            boxes = np.reshape(boxes[keep], (-1, 4))
            scores = np.reshape(scores[keep], (boxes.shape[0],))
            classes = np.reshape(classes[keep], (boxes.shape[0],))
            if masks is not None:
                masks = masks[keep]

        return boxes, classes, scores, masks


def tensorflow_combined_nms(
    boxes: np.ndarray,
    scores: np.ndarray,
    masks: np.ndarray = None,
    iou_threshold: float = 0.001,
    score_threshold: float = 0.70,
    max_detections: int = 300,
    class_agnostic: bool = False,
    clip_boxes: bool = False
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Return output of the TensorFlow NMS.
    https://www.tensorflow.org/api_docs/python/tf/image/combined_non_max_suppression
    By default, class-aware NMS is deployed. However, class-agnostic NMS
    can be specified.

    Parameters
    ----------
    boxes: np.ndarray
        Normalized input boxes to the NMS with shape (n, 4)
        in [xmin, ymin, xmax, ymax] format.
    scores: np.ndarray
        Input scores to the NMS (n, ).
    masks: np.ndarray
        (Optional) Instance segmentation masks to also
        to also be filtered during NMS.
    iou_threshold: float
        This is the IoU threshold for the NMS. Higher values
        are less strict in filtering overlapping detections.
    score_threshold: float
        The confidence score threshold for the NMS. Filters to accept
        more confident detections based on this threshold.
    max_detections: int
        The maximum number of boxes to be selected by NMS per class.
    class_agnostic: bool
        Run class-agnostic NMS. Default includes class.
    clip_boxes: bool
        If set to True, boxes will be clipped between 0 and 1. If False,
        the coordinates are kept as it is.

    Returns
    -------
    boxes : np.ndarray
        This contains only the valid bounding boxes post NMS.
    classes : np.ndarray
        This contains only the valid classes post NMS.
    scores : np.ndarray
        This contains only the valid scores post NMS.
    masks: np.ndarray
        This contains only the valid instance segmentation masks
        post NMS if it exists. Otherwise, None is returned.

    Raises
    ------
    ImportError
        Raised if TensorFlow is not installed in the system
        which is needed to run the NMS.
    """

    try:
        import tensorflow as tf  # type: ignore
    except ImportError as e:
        raise ImportError(
            "TensorFlow is needed to use `tensorflow_nms`.") from e

    if class_agnostic:
        # Sort boxes by score.
        boxes = tf.reshape(boxes, [-1, 4])
        num_boxes = boxes.shape[0]
        scores = tf.reshape(scores, [num_boxes, -1])
        nms_scores = tf.reduce_max(scores, axis=1)
        classes = tf.argmax(scores, axis=1)

        keep = tensorflow_nms(
            boxes=boxes,
            scores=nms_scores,
            iou_threshold=iou_threshold,
            score_threshold=score_threshold,
            max_detections=max_detections
        )
        boxes = tf.gather(boxes, keep).numpy()
        scores = tf.gather(nms_scores, keep).numpy()
        classes = tf.gather(classes, keep).numpy().astype(np.uintp)
        if masks is not None:
            masks = tf.gather(masks, keep).numpy()

    else:
        num_boxes = boxes.shape[0]
        boxes = np.reshape(boxes, (1, num_boxes, 1, 4))
        scores = np.expand_dims(scores, 0)

        # Get maximum class score per anchor.
        per_anchor_scores = tf.reduce_max(scores, axis=-1)  # shape (1, 8400)
        per_anchor_scores = per_anchor_scores[0].numpy()

        boxes, scores, classes, valid_boxes = \
            tf.image.combined_non_max_suppression(
                boxes=boxes,
                scores=scores,
                max_output_size_per_class=max_detections,
                max_total_size=max_detections,
                iou_threshold=iou_threshold,
                score_threshold=score_threshold,
                clip_boxes=clip_boxes
            )
        valid_boxes = valid_boxes.numpy()[0]
        boxes = boxes.numpy()[0]
        classes = classes.numpy()[0]
        scores = scores.numpy()[0]

        boxes = boxes[:valid_boxes]
        scores = scores[:valid_boxes]
        classes = classes[:valid_boxes].astype(np.uintp)

        if masks is not None:
            # Keep top-k scores (e.g., the top 100 used in NMS).
            sorted_indices = np.argsort(per_anchor_scores)[::-1]
            top_indices = sorted_indices[:valid_boxes]
            masks = masks[top_indices]

    return boxes, classes, scores, masks


def tensorflow_nms(
    boxes: np.ndarray,
    scores: np.ndarray,
    iou_threshold: float = 0.70,
    score_threshold: float = 0.001,
    max_detections: int = 300
):
    """
    Return output from single class TensorFlow NMS.
    https://www.tensorflow.org/api_docs/python/tf/image/non_max_suppression

    Parameters
    ----------
    boxes: np.ndarray
        Normalized input boxes to the NMS with shape (n, 4)
        in [xmin, ymin, xmax, ymax] format.
    scores: np.ndarray
        Input scores to the NMS (n, ).
    iou_threshold: float
        This is the IoU threshold for the NMS. Higher values
        are less strict in filtering overlapping detections.
    score_threshold: float
        The confidence score threshold for the NMS. Filters to accept
        more confident detections based on this threshold.
    max_detections: int
        The maximum number of boxes to be selected by NMS per class.

    Returns
    -------
    Tensor
        This contains the indices of the boxes to keep.

    Raises
    ------
    ImportError
        Raised if TensorFlow is not installed in the system
        which is needed to run the NMS.
    """
    try:
        import tensorflow as tf  # type: ignore
    except ImportError as e:
        raise ImportError(
            "TensorFlow is needed to use `tensorflow_nms`.") from e

    return tf.image.non_max_suppression(
        boxes=boxes,
        scores=scores,
        max_output_size=max_detections,
        iou_threshold=iou_threshold,
        score_threshold=score_threshold
    )


def torch_nms(
    boxes: np.ndarray,
    scores: np.ndarray,
    iou_threshold: float,
    max_detections: int = 300
):
    """
    Return output from single class torchvision NMS.
    https://docs.pytorch.org/vision/0.9/ops.html#torchvision.ops.nms

    Parameters
    ----------
    boxes: np.ndarray
        Normalized input boxes to the NMS with shape (n, 4)
        in [xmin, ymin, xmax, ymax] format.
    scores: np.ndarray
        Input scores to the NMS (n, ).
    iou_threshold: float
        This is the IoU threshold for the NMS. Higher values
        are less strict in filtering overlapping detections.
    max_detections: int
        The maximum number of boxes to be selected by NMS per class.

    Returns
    -------
    torch.Tensor
        This contains the indices of the boxes to keep.

    Raises
    ------
    ImportError
        Raised if PyTorch NMS is not installed.
    """
    try:
        import torch  # type: ignore
        import torchvision  # type: ignore
    except ImportError as e:
        raise ImportError(
            "Torch and Torchvision is needed to use `torch_nms`.") from e

    i = torchvision.ops.nms(torch.tensor(
        boxes), torch.tensor(scores), iou_threshold)

    if i.shape[0] > max_detections:  # limit detections
        i = i[:max_detections]  # This limits detections.
    return i


def numpy_nms(
    boxes: np.ndarray,
    scores: np.ndarray,
    iou_threshold: float = 0.70,
    max_detections: int = 300,
    eps: float = 1e-7
) -> np.ndarray:
    """
    Single class NMS implemented in NumPy.
    Method taken from:: https://github.com/Megvii-BaseDetection/YOLOX/blob/main/yolox/utils/demo_utils.py#L57
    Original source from:: https://github.com/amusi/Non-Maximum-Suppression/blob/master/nms.py

    Parameters
    ----------
    boxes: np.ndarray
        Normalized input boxes to the NMS with shape (n, 4)
        in [xmin, ymin, xmax, ymax] format.
    scores: np.ndarray
        Input scores to the NMS (n, ).
    iou_threshold: float
        This is the IoU threshold for the NMS. Higher values
        are less strict in filtering overlapping detections.
    max_detections: int
        The maximum number of boxes to be selected by NMS per class.
    eps: float
        Scalar to avoid division by zeros.

    Returns
    -------
    np.ndarray
        This contains the indices of the boxes to keep.
    """
    if len(boxes) == 0:
        return np.array([], dtype=np.int32)

    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]

    # Calculate areas (remove the +1 for normalized coordinates)
    areas = (x2 - x1) * (y2 - y1)

    # Sort by scores in descending order
    order = scores.argsort()[::-1]

    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)

        if len(keep) >= max_detections:
            break

        # Calculate intersection coordinates
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        # Calculate intersection area (remove +1 for normalized coords)
        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h

        # Calculate IoU
        union = areas[i] + areas[order[1:]] - inter
        iou = inter / (union + eps)

        # Keep boxes with IoU less than threshold
        inds = np.where(iou <= iou_threshold)[0]
        order = order[inds + 1]

    return np.array(keep, dtype=np.int32)
