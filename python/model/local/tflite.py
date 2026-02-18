from typing import List
from argparse import ArgumentParser
import os

import numpy as np

try:
    import cv2
    _OPENCV_AVAILABLE = True
except ImportError:
    _OPENCV_AVAILABLE = False

try:
    from tflite_runtime.interpreter import Interpreter, load_delegate  # type: ignore
    _TFLITE_RUNTIME_AVAILABLE = True
except ImportError:
    _TFLITE_RUNTIME_AVAILABLE = False

    try:
        import tensorflow as tf  # type: ignore
        Interpreter = tf.lite.Interpreter
        load_delegate = tf.lite.experimental.load_delegate
        _TENSORFLOW_AVAILABLE = True
    except ImportError as e:
        _TENSORFLOW_AVAILABLE = False

from python.model.local.metadata import load_tflite_metadata
from python.model.local.transforms import (decode_yolo_boxes,
                                           decode_yolo_masks, 
                                           dequantize, crop_masks)
from python.hal.local.letterbox import cv2_letterbox
from python.hal.local.resize import cv2_resize
from python.model.local.nms import nms


def select_tflite_delegate():
    ext_delegate = None
    if os.path.exists("/usr/lib/libvx_delegate.so"):
        ext_delegate = load_delegate("/usr/lib/libvx_delegate.so", {})
    elif os.path.exists("/usr/lib/libneutron_delegate.so"):
        ext_delegate = load_delegate("/usr/lib/libneutron_delegate.so", {})
    return ext_delegate


class TFLiteRunner:
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
        self.input_shape = self.input_details[0]["shape"][1:3] # Fetching height, width

        self.metadata, self.labels = load_tflite_metadata(model_path)
        if self.metadata is None:
            self.metadata = self.build_metadata(self.output_details)

    @staticmethod
    def build_metadata(output_details: List[dict]):
        # Create metadata if it doesn't exist. Needed to initialize HAL decoder.
        metadata = {"outputs": []}
        for output_details in output_details:
            shape = output_details["shape"].tolist()
            output_metadata = {
                "decode": True,
                "decoder": "ultralytics",
                "shape": output_details["shape"].tolist(),
                "quantization": output_details["quantization"],
            }
            # [1, 32, 160, 160] or [1, 160, 160, 32]
            if len(shape) == 4:
                batch = shape[0]
                transposed = shape[1] < shape[-1] 
                num_protos = shape[1] if transposed else shape[-1]
                height = shape[2] if transposed else shape[1]
                width = shape[-1] if transposed else shape[2]
                output_metadata["type"] = "protos"
                output_metadata["dshape"] =  [("batch", batch), 
                                                ("height", height),
                                                ("width", width),
                                                ("num_protos", num_protos)]
            # [1, 37, 8400]
            else:
                batch = shape[0]
                num_features = shape[1] if shape[1] < shape[2] else shape[2]
                num_boxes = shape[2] if shape[2] > shape[1] else shape[1]
                output_metadata["type"] = "detection"
                output_metadata["dshape"] =  [("batch", batch), 
                                                ("num_features", num_features),
                                                ("num_boxes", num_boxes)]
            metadata["outputs"].append(output_metadata)
        return metadata

    def inference(self, input_tensor: np.ndarray):
        # For quantized models, run input quantization parameters.
        if self.input_quantization is not None:
            if self.input_type == np.int8:
                scale, zero_point = self.input_quantization
                # Apply proper INT8 quantization: quantized = round(normalized / scale) + zero_point
                # First normalize to [0, 1] range, then quantize
                normalized = input_tensor.astype(np.float32) / 255.0
                quantized = np.round(normalized / scale).astype(np.int32) + zero_point
                input_tensor = np.clip(quantized, -128, 127).astype(np.int8)

        input_tensor = input_tensor[None]
        # Directly copy the input tensor into the model for TFLite.
        if self.input_tensor is not None:
            np.copyto(self.input_tensor(), input_tensor)

        self.model.invoke()

        outputs = [self.model.get_tensor(output["index"])
                   for output in self.output_details]
        
        return self.decode_outputs(outputs)
        
    def decode_outputs(self, outputs: list):
        boxes, classes, scores = None, None, None
        masks, protos = None, None
        for i, metadata in enumerate(self.metadata["outputs"]):
            x = outputs[i]
            x = x.astype(np.float32) if x.dtype == np.float16 else x
            if (metadata["quantization"] is not None and x.dtype != np.float32):
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
                boxes, classes, scores, masks = nms(
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
                
        return boxes, classes, scores, masks
    

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
    
    runner = TFLiteRunner(
        model_path=args.model,
        score=args.score,
        iou=args.iou,
        max_boxes=args.max_boxes
    )

    if not _OPENCV_AVAILABLE:
        raise ImportError("OpenCV is required to run this sample. Please install OpenCV and try again.")    

    input_tensor = cv2.imread(args.image)
    input_tensor = cv2_letterbox(input_tensor, size=runner.input_shape)
    boxes, classes, scores, masks = runner.inference(input_tensor)

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
    
    # Visualize outputs
    if args.save:
        save_path = os.path.expanduser(args.save)
        # Create parent directory only
        parent_dir = os.path.dirname(save_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        # Denormalize box coordinates
        boxes[:, [0, 2]] *= runner.input_shape[1]
        boxes[:, [1, 3]] *= runner.input_shape[0]
        boxes = boxes.astype(np.int32)

        alpha = 0.50
        for i in range(boxes.shape[0]):
            cv2.putText(
                input_tensor,
                f"{runner.labels[classes[i]] if runner.labels is not None else classes[i]}: {scores[i]:.2f}",
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

if __name__ == "__main__":
    main()
