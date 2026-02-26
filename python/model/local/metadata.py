# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""
Utilities for loading, parsing, and displaying model metadata from various formats (TFLite, ONNX, JSON, YAML).

- Provides MetaData class for structured access and pretty-printing
- Supports extracting metadata from model files and archives
- Used for model inspection and validation in EdgeFirst workflows

Metadata follows the same structure specified in the EdgeFirst documentation:
https://doc.edgefirst.ai/latest/models/metadata/

"""

from typing import Union, Tuple, List
from argparse import ArgumentParser
import zipfile
import json
import ast
import os


class MetaData:
    def __init__(self, metadata: Union[dict, None]):
        self.metadata = metadata

    def print(self):
        # Parse and print metadata
        if self.metadata is not None:
            print("Model Metadata:")
            for key, value in self.metadata.items():
                if isinstance(value, dict):
                    print(f"- {key}:")
                    for sub_key, sub_value in value.items():
                        print(f" \t {sub_key}: {sub_value}")
                else:
                    print(f"- {key}: {value}")

    def get_quick_metadata(self, key: str):
        # Extract and return quick metadata
        if key in self.metadata.keys():
            return self.metadata[key]
        return None

    @staticmethod
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
            import python.model.local.hal_onnx as hal_onnx
            model = hal_onnx.load(model_path)
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


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Model Metadata")
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        help="Path to the model file to extract metadata.",
    )
    args = parser.parse_args()

    if args.model:
        if os.path.splitext(args.model)[1].lower() == ".onnx":
            metadata, labels = load_onnx_metadata(args.model)
        elif os.path.splitext(args.model)[1].lower() == ".tflite":
            metadata, labels = load_tflite_metadata(args.model)
        else:
            print(
                f"[ERROR] - Unsupported model format {os.path.splitext(args.model)[1]}. ")
            return

        print("Labels:", labels)
        metadata_obj = MetaData(metadata)
        metadata_obj.print()

        outputs = metadata_obj.get_quick_metadata('outputs')
        for i, o in enumerate(outputs):
            print(f"Output {i}: {o}\n")


if __name__ == "__main__":
    main()
