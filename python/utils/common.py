# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""
Common utilities for EdgeFirst samples.
"""

from typing import Tuple, Union, List
import zipfile
import ctypes
import json
import ast
import os

import numpy as np

try:
    import onnxruntime as ort
    _ONNX_RUNTIME_AVAILABLE = True
except ImportError:
    _ONNX_RUNTIME_AVAILABLE = False

try:
    from tflite_runtime.interpreter import load_delegate  # type: ignore
    _TFLITE_RUNTIME_AVAILABLE = True
except ImportError:
    _TFLITE_RUNTIME_AVAILABLE = False

    try:
        import tensorflow as tf  # type: ignore
        load_delegate = tf.lite.experimental.load_delegate
        _TENSORFLOW_AVAILABLE = True
    except ImportError as e:
        _TENSORFLOW_AVAILABLE = False


def check_tensorrt_runtime() -> list:
    required_libs = ["libnvinfer.so",
                     "libnvinfer_plugin.so", "libnvonnxparser.so"]
    missing = []
    for lib in required_libs:
        try:
            ctypes.CDLL(lib)
        except OSError:
            missing.append(lib)
    return missing


def select_onnx_providers() -> list:
    if not _ONNX_RUNTIME_AVAILABLE:
        return []

    selected_providers = ["CPUExecutionProvider"]
    available_providers = ort.get_available_providers()

    preferred_providers = ["NnapiExecutionProvider",
                           "VsiNpuExecutionProvider",
                           "VSINPUExecutionProvider",
                           "CUDAExecutionProvider",
                           "CPUExecutionProvider"]
    selected_providers = []
    for i, provider in enumerate(preferred_providers):
        if provider in available_providers:
            if provider == "TensorrtExecutionProvider":
                missing_libraries = check_tensorrt_runtime()
                if missing_libraries:
                    continue
            selected_providers.append(provider)
    print(f"Selected providers: {selected_providers}")
    return selected_providers


def select_tflite_delegate():
    if not _TFLITE_RUNTIME_AVAILABLE and not _TENSORFLOW_AVAILABLE:
        return None
    ext_delegate = None
    if os.path.exists("/usr/lib/libvx_delegate.so"):
        ext_delegate = load_delegate("/usr/lib/libvx_delegate.so", {})
    elif os.path.exists("/usr/lib/libneutron_delegate.so"):
        ext_delegate = load_delegate("/usr/lib/libneutron_delegate.so", {})
    return ext_delegate


def load_onnx_metadata(
        model_path: str) -> Tuple[Union[dict, None], Union[List[str], None]]:

    metadata = None
    labels = None

    try:
        import onnxruntime
        model = onnxruntime.InferenceSession(model_path)
        custom_metadata = model.get_modelmeta().custom_metadata_map

        if "edgefirst" in custom_metadata.keys():
            metadata = json.loads(custom_metadata["edgefirst"])

        if "labels" in custom_metadata.keys():
            labels = ast.literal_eval(custom_metadata["labels"])
    except ImportError as e:
        try:
            import onnx
            model = onnx.load(model_path)
            for prop in model.metadata_props:
                if prop.key == 'edgefirst':
                    metadata = json.loads(prop.value)

            for prop in model.metadata_props:
                if prop.key == 'labels':
                    labels = json.loads(prop.value)
        except ImportError:
            raise ImportError(
                "onnxruntime or onnxruntime-gpu, or onnx is needed to load ONNX models."
            ) from e
    return metadata, labels


def load_tflite_metadata(
        model_path: str) -> Tuple[Union[dict, None], Union[List[str], None]]:
    metadata = None
    labels = None

    if zipfile.is_zipfile(model_path):
        with zipfile.ZipFile(model_path) as zip_ref:
            if "edgefirst.yaml" in zip_ref.namelist():
                import yaml
                with zip_ref.open("edgefirst.yaml") as f:
                    yaml_text = f.read().decode("utf-8")
                    metadata = yaml.safe_load(yaml_text)
            elif "edgefirst.json" in zip_ref.namelist():
                with zip_ref.open("edgefirst.json") as f:
                    json_text = f.read().decode("utf-8")
                    metadata = json.loads(json_text)
            else:
                print(
                    "[WARNING] - The model file does not contain the "
                    "'edgefirst.yaml' or 'edgefirst.json' metadata file.")

            if "labels.txt" in zip_ref.namelist():
                with zip_ref.open("labels.txt") as f:
                    labels_text = f.read().decode("utf-8")
                    labels = [line.rstrip()
                              for line in labels_text.splitlines()
                              if line not in ["\n", "", "\t"]]
            else:
                print(
                    "[WARNING] - The model file does not contain the 'labels.txt'.")
    return metadata, labels


def build_metadata(outputs: Union[List[dict], list]):
    # Create metadata if it doesn't exist. Needed to initialize HAL
    # decoder.
    metadata = {"outputs": []}
    for output in outputs:
        if isinstance(output, dict):
            shape = output["shape"].tolist()
            quantization = output.get("quantization", None)
        else:
            shape = output.shape
            quantization = None
        output_metadata = {
            "decode": True,
            "decoder": "ultralytics",
            "shape": shape,
            "quantization": quantization,
        }
        # [1, 32, 160, 160] or [1, 160, 160, 32]
        if len(shape) == 4:
            batch = shape[0]
            transposed = shape[1] < shape[-1]
            num_protos = shape[1] if transposed else shape[-1]
            height = shape[2] if transposed else shape[1]
            width = shape[-1] if transposed else shape[2]
            output_metadata["type"] = "protos"

            # dshape must be in the correct order
            dshape = []
            keys = []
            for s in shape:
                if s == batch and "batch" not in keys:
                    dshape.append(("batch", batch))
                    keys.append("batch")
                elif s == num_protos and "num_protos" not in keys:
                    dshape.append(("num_protos", num_protos))
                    keys.append("num_protos")
                elif s == height and "height" not in keys:
                    dshape.append(("height", height))
                    keys.append("height")
                elif s == width and "width" not in keys:
                    dshape.append(("width", width))
                    keys.append("width")
            output_metadata["dshape"] = dshape
        # [1, 37, 8400]
        else:
            batch = shape[0]
            num_features = shape[1] if shape[1] < shape[2] else shape[2]
            num_boxes = shape[2] if shape[2] > shape[1] else shape[1]
            output_metadata["type"] = "detection"

            # dshape must be in the correct order
            dshape = []
            keys = []
            for s in shape:
                if s == batch and "batch" not in keys:
                    dshape.append(("batch", batch))
                    keys.append("batch")
                elif s == num_features and "num_features" not in keys:
                    dshape.append(("num_features", num_features))
                    keys.append("num_features")
                elif s == num_boxes and "num_boxes" not in keys:
                    dshape.append(("num_boxes", num_boxes))
                    keys.append("num_boxes")
            output_metadata["dshape"] = dshape
        metadata["outputs"].append(output_metadata)
    return metadata


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
