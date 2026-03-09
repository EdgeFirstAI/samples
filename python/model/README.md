# EdgeFirst Perception Middleware Model Samples

This section provides sample applications that demonstrate using EdgeFirst model utilities for inference, output decoding, and visualization. The **local** examples run on-device and focus on model loading, metadata extraction, preprocessing, and postprocessing, while the **zenoh** directory shows examples for subscribing to Zenoh topics hosted by an [EdgeFirst Platform](https://doc.edgefirst.ai/latest/platforms/).

> Note: For any of these programs press CTRL-C to quit.

## Local Examples

The following examples are intended to run locally on an EdgeFirst device.

### **1. TFLite Model Inference**

**Purpose:** Demonstrate loading a TFLite model, running inference, and decoding outputs (boxes, masks, etc) on a sample image.

**Source Code:** [tflite.py](python/model/local/tflite.py)

**Usage:**

```bash
python python/model/local/hal_tflite.py --model /path/to/model.tflite --image /path/to/image.jpg
```

| Parameters | Definition | Default |
|------------|------------|---------|
| --score    | Specify the score threshold for NMS | 0.50 |
| --iou      | Specify the IoU threshold for NMS | 0.50 |
| --max-boxes | Specify the max boxes for NMS | 300 |
| --method | Specify the method for running model inference <hal, opencv> | hal
| --save | Specify the path to the image file with the visualizations of the model outputs | None

### **2. ONNX Model Inference**

**Purpose:** Demonstrate loading an ONNX model, running inference, and decoding outputs (boxes, masks, etc) on a sample image.

**Source Code:** [onnx.py](python/model/local/onnx.py)

**Usage:**

```bash
python python/model/local/hal_onnx.py --model /path/to/model.onnx --image /path/to/image.jpg
```

| Parameters | Definition | Default |
|------------|------------|---------|
| --score    | Specify the score threshold for NMS | 0.50 |
| --iou      | Specify the IoU threshold for NMS | 0.50 |
| --max-boxes | Specify the max boxes for NMS | 300 |
| --method | Specify the method for running model inference <hal, opencv> | hal
| --save | Specify the path to the image file with the visualizations of the model outputs | None

### **3. Metadata Extraction**

**Purpose:** Extract and display model metadata from TFLite, ONNX, or YAML/JSON files.

**Source Code:** [metadata.py](python/model/local/metadata.py)

**Usage:**

```bash
python python/model/local/metadata.py --model /path/to/model.tflite
```

> Note: The --model could be the path to an ONNX model.

### **4. NMS and Transforms**

**Purpose:** Run Non-Maximum Suppression (NMS) and apply box/mask transforms for postprocessing.

**Source Code:** [nms.py](python/model/local/nms.py), [transforms.py](python/model/local/transforms.py)

**Usage:**

See function docstrings and test code in each file for usage examples.

## Zenoh Examples

These examples are only supported in [EdgeFirst Platforms](https://doc.edgefirst.ai/latest/platforms/) such as the Maivin or Raivin. These platforms publish data in Zenoh (ROS-like) topics which are unique to these platforms where other devices can then use to subscribe and receive data.

These examples can be run with an EdgeFirst Platform with the Zenoh, camera, and model services enabled.

`sudo systemctl enable --now zenohd`
`sudo systemctl enable --now camera`
`sudo systemctl enable --now model`

### **1. 2D Boxes (Zenoh)**

**Purpose:** Subscribes to Zenoh topics (e.g. `rt/model/boxes2d`) to receive and visualize 2D bounding box detections.

**Source Code:** [boxes2d.py](python/model/zenoh/boxes2d.py), [boxes2d_tracked.py](python/model/zenoh/boxes2d_tracked.py)

**Usage:**

```bash
python python/model/zenoh/boxes2d.py --remote <edgefirst-ip>:7447
```

### **2. Masks (Zenoh)**

**Purpose:** Subscribes to Zenoh topics to receive and visualize segmentation masks (compressed or raw).

**Source Code:** [mask.py](python/model/zenoh/mask.py), [compressed_mask.py](python/model/zenoh/compressed_mask.py)

**Usage:**

```bash
python python/model/zenoh/mask.py --remote <edgefirst-ip>:7447
```

### **3. Model Info (Zenoh)**

**Purpose:** Subscribes to Zenoh topics to receive and display model information.

**Source Code:** [model_info.py](python/model/zenoh/model_info.py)

**Usage:**

```bash
python python/model/zenoh/model_info.py --remote <edgefirst-ip>:7447
```
