# EdgeFirst Perception Middleware Combined Samples

This section provides sample applications for reading from the camera that's connected to the device and preprocess the fetched frames with either letterbox or resizing operations that will be provided to the model for inference. A display will be shown on the monitor showing the model outputs. 

The **local** examples shows the pipeline (read camera -> fetch frame -> preprocess frame -> model inference -> model decoding -> display window) which uses either the GStreamer or OpenCV libraries installed in the device. The **zenoh** directory shows examples for subscribing to Zenoh topics hosted by an [EdgeFirst Platform](https://doc.edgefirst.ai/latest/platforms/).

> Note: The local examples only supports quantized Ultralytics TFLite models.
> Note: For any of these programs press CTRL-C to quit.

## Local Examples

The following table shows which examples are supported across various platforms.

### **1. Camera Model Example**

**Purpose**: Demonstrate reading from the camera and invoke the model for inference and display the outputs on the monitor using either GStreamer or OpenCV libraries.

**Source Code:** [Python](python/combined/local/camera_model.py)

**Usage:**

1. Optimized (default) pipeline which uses GStreamer to fetch DMA buffers for zero-copy which HAL can read, preprocess, and use for model inference. Furthermore, the frame with the model outputs is displayed on the monitor using PyCairo.

```bash
python python/combined/local/camera_model_hal.py --model /path/my/model.tflite --camera=/dev/video3 
```

2. Alternative pipeline which uses OpenCV and a base method for reading the camera to fetch frames that can be copied into the model for inference. OpenCV is also used to visualize the frame on the monitor.

```bash
python python/combined/local/camera_model_opencv.py --model /path/my/model.tflite --camera=/dev/video3 --method=opencv
```

## Zenoh Examples

These examples are only supported in [EdgeFirst Platforms](https://doc.edgefirst.ai/latest/platforms/) such as the Maivin or Raivin. These platforms publishes data in Zenoh (ROS-like) topics which are unique to these platforms where other devices can then use to subscribe and recieve data.

These examples can be run with an EdgeFirst Platform with the Zenoh, camera, and model services enabled.

`sudo systemctl enable --now zenohd`
`sudo systemctl enable --now camera`
`sudo systemctl enable --now model`

### **1. Camera LiDAR**

**Purpose:** Subscribes to Zenoh topics to fetch LiDAR cluster data (e.g. `rt/lidar/clusters`) alongside camera and model topics, and visualizes the results with Rerun.

**Source Code:** [Python](python/combined/zenoh/camera_lidar.py)

**Usage:**

1. Connect remotely with an EdgeFirst Platform.
```bash
python python/combined/zenoh/camera_lidar.py --remote 192.168.1.100:7447
```

2. Connect via proxy server.

Run the following command in your PC. You should get the following URL link in the form: `rerun+http://<PC IP address>:9876/proxy`
```bash
rerun --bind <PC IP address>
```

Run the following command in your EdgeFirst Platform.
```bash
python python/combined/zenoh/camera_lidar.py --connect --url rerun+http://<PC IP address>:9876/proxy
```

### **2. Camera Radar**

**Purpose:** Subscribes to Zenoh topics to fetch radar cluster data (e.g. `rt/radar/clusters`) alongside camera and model topics, and visualizes the results with Rerun.

**Source Code:** [Python](python/combined/zenoh/camera_radar.py)

**Usage:**

1. Connect remotely with an EdgeFirst Platform.
```bash
python python/combined/zenoh/camera_radar.py --remote 192.168.1.100:7447
```

2. Connect via proxy server

Run the following command in your PC. You should get the following URL link in the form: `rerun+http://<PC IP address>:9876/proxy`
```bash
rerun --bind <PC IP address>
```

Run the following command in your EdgeFirst Platform.
```bash
python python/combined/zenoh/camera_radar.py --connect --url rerun+http://<PC IP address>:9876/proxy
```

### **3. Camera Model**

**Purpose:** Subscribes to Zenoh topics to fetch model outputs (e.g. `rt/model/boxes2d`, `rt/model/mask`/`rt/model/mask_compressed`) alongside camera frames, then visualizes the results with Rerun.

**Source Code:** [Python](python/combined/zenoh/camera_model.py)

**Usage:**

1. Connect remotely with an EdgeFirst Platform.
```bash
python python/combined/zenoh/camera_model.py --remote 192.168.1.100:7447
```

2. Connect via proxy server

Run the following command in your PC. You should get the following URL link in the form: `rerun+http://<PC IP address>:9876/proxy`
```bash
rerun --bind <PC IP address>
```

Run the following command in your EdgeFirst Platform.
```bash
python python/combined/zenoh/camera_model.py --connect --url rerun+http://<PC IP address>:9876/proxy
```

### **4. Mega Sample**

**Purpose:** Subscribes to multiple Zenoh topics (camera, model outputs, LiDAR/radar/GPS, and fusion topics) to provide an end-to-end, all-in-one visualization and processing example.

**Source Code:** [Python](python/combined/zenoh/mega_sample.py)

**Usage:**

1. Connect remotely with an EdgeFirst Platform.
```bash
python python/combined/zenoh/mega_sample.py --remote 192.168.1.100:7447
```

2. Connect via proxy server

Run the following command in your PC. You should get the following URL link in the form: `rerun+http://<PC IP address>:9876/proxy`
```bash
rerun --bind <PC IP address>
```

Run the following command in your EdgeFirst Platform.
```bash
python python/combined/zenoh/mega_sample.py --connect --url rerun+http://<PC IP address>:9876/proxy
```
