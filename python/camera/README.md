# EdgeFirst Perception Middleware Camera Samples

This section provides sample applications for reading from the camera connected to the device using Python. There are multiple ways to read from the camera either through external libraries such as GStreamer or OpenCV as shown in the **local** directory or by subscribing to Zenoh topics hosted by an [EdgeFirst Platform](https://doc.edgefirst.ai/latest/platforms/) as shown in the **zenoh** directory.

Prior to running the following examples, ensure that you have followed the [Python Quick Start](../../README.md#python-quickstart) which shows how to set up a [Python virtual environment](https://docs.python.org/3/library/venv.html) and installs the required dependencies. 

> Note: For any of these programs press CTRL-C to quit.

## Local Examples

The following table shows which examples are supported across various platforms.

| Platform         | gstreamer.py | opencv.py | 
|------------------|--------------|-----------|
| Windows x86_64   |      ✕       |     ✓     |
| Linux x86_64     |      ✕       |     ✓     |
| macOS            |  (untested)  | (untested)|    
| i.MX 8M Plus EVK |      ✓       |     ✓     |
| NVIDIA Orin      |      ✓       |     ✓     |
| Maivin           |      ✕       |     ✕     |
| Raivin           |      ✕       |     ✕     |   
| i.MX 95 EVK      |  (untested)  | (untested)|

### **1. GStreamer Camera Example**

**Purpose:** Demonstrate reading from the camera using GStreamer pipelines in Python.

**Source Code:** [Python](python/camera/local/gstreamer.py)

**Usage:**
```bash
python python/camera/local/gstreamer.py --camera=/dev/video3
```

By default the display is rendered using wayland sink. However, you can render the display using PyCairo using the command

```bash
python python/camera/local/gstreamer.py --camera=/dev/video3 --use-cairo
```

### **2. OpenCV Camera Example**

**Purpose:** Demonstrate reading from the camera using OpenCV. 

**Source Code:** [Python](python/camera/local/opencv.py)

**Usage:**
```bash
python python/camera/local/opencv.py --camera=0
```

## Zenoh Examples

These examples are only supported in [EdgeFirst Platforms](https://doc.edgefirst.ai/latest/platforms/) such as the Maivin or Raivin. These platforms publishes data in Zenoh (ROS-like) topics which are unique to these platforms where other devices can then use to subscribe and recieve data.

These examples can be run with an EdgeFirst Platform with the Zenoh and the camera
service enabled.

`sudo systemctl enable --now zenohd`
`sudo systemctl enable --now camera`

A host machine such as a PC with a monitor connected can be used to run the following commands. 

### **1. Camera Info**

**Purpose:** Subscribes to the Zenoh topic `rt/camera/info`, deserializes `CameraInfo` messages, and logs basic camera properties (width/height) to a Rerun viewer.

**Source Code:** [Python](python/camera/zenoh/info.py)

**Usage:**

1. Connect remotely with an EdgeFirst Platform.
```bash
python .\python\camera\zenoh\info.py --remote 10.10.41.67:7447
```

2. Connect via proxy server.

Run the following command in your PC. You should get the following URL link in the form: `rerun+http://<PC IP address>:9876/proxy`
```bash
rerun --bind <PC IP address>
```

Run the following command in your EdgeFirst Platform.
```bash
python python/camera/zenoh/info.py --connect --url rerun+http://<PC IP address>:9876/proxy
```

### **2. DMABuffer Receiver**

**Purpose:** Subscribes to the Zenoh topic `rt/camera/dma`, receives `DmaBuffer` messages, maps the DMA buffer into userspace (Linux/EdgeFirst platforms only), and logs the resulting YUY2 frames to a Rerun viewer under `/camera`.

**Source Code:** [Python](python/camera/zenoh/dma.py)

**Usage:**

1. Connect remotely with an EdgeFirst Platform.
```bash
python .\python\camera\zenoh\dma.py --remote 10.10.41.67:7447
```

2. Connect via proxy server.

Run the following command in your PC. You should get the following URL link in the form: `rerun+http://<PC IP address>:9876/proxy`
```bash
rerun --bind <PC IP address>
```

Run the following command in your EdgeFirst Platform.
```bash
python python/camera/zenoh/dma.py --connect --url rerun+http://<PC IP address>:9876/proxy
```

### **3. JPEG Decoder**

**Purpose:** Subscribes to the Zenoh topic `rt/camera/jpeg`, deserializes `CompressedImage` messages, decodes the JPEG payload into an RGB image, and logs the image stream to a Rerun viewer under `/camera`.

**Source Code:** [Python](python/camera/zenoh/jpeg.py)

**Usage:**

1. Connect remotely with an EdgeFirst Platform.
```bash
python .\python\camera\zenoh\jpeg.py --remote 10.10.41.67:7447
```

2. Connect via proxy server.

Run the following command in your PC. You should get the following URL link in the form: `rerun+http://<PC IP address>:9876/proxy`
```bash
rerun --bind <PC IP address>
```

Run the following command in your EdgeFirst Platform.
```bash
python python/camera/zenoh/jpeg.py --connect --url rerun+http://<PC IP address>:9876/proxy
```

### **4. H264 Decoder**

**Purpose:** Subscribes to the Zenoh topic `rt/camera/h264`, decodes the incoming H.264 byte stream into RGB frames, and logs the video frames to a Rerun viewer under `/camera`.

**Source Code:** [Python](python/camera/zenoh/h264.py)

**Usage:**

1. Connect remotely with an EdgeFirst Platform.
```bash
python .\python\camera\zenoh\h264.py.py --remote 10.10.41.67:7447
```

2. Connect via proxy server.

Run the following command in your PC. You should get the following URL link in the form: `rerun+http://<PC IP address>:9876/proxy`
```bash
rerun --bind <PC IP address>
```

Run the following command in your EdgeFirst Platform.
```bash
python python/camera/zenoh/h264.py --connect --url rerun+http://<PC IP address>:9876/proxy
```
