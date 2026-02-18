# EdgeFirst Perception Middleware Fusion Samples

This section provides sample applications for subscribing to Fusion outputs published over Zenoh by an [EdgeFirst Platform](https://doc.edgefirst.ai/latest/platforms/). The examples focus on fused perception outputs (e.g., 3D boxes, radar clusters, occupancy grids, and model outputs) and visualize them with Rerun.

> Note: For any of these programs press CTRL-C to quit.

## Zenoh Examples

These examples are only supported in [EdgeFirst Platforms](https://doc.edgefirst.ai/latest/platforms/) such as the Maivin or Raivin. These platforms publish data in Zenoh (ROS-like) topics which are unique to these platforms where other devices can then use to subscribe and receive data.

These examples can be run with an EdgeFirst Platform with the Zenoh and fusion services enabled.

`sudo systemctl enable --now zenohd`
`sudo systemctl enable --now fusion`

### **1. Boxes3D**

**Purpose:** Subscribes to Zenoh topics that publish 3D bounding boxes (e.g. `rt/fusion/boxes3d`) and visualizes Box3D outputs with Rerun.

**Source Code:** [Python](python/fusion/zenoh/boxes3d.py)

**Usage:**

1. Connect remotely with an EdgeFirst Platform.
```bash
python zenoh/boxes3d.py --remote 10.10.41.67:7447
```

2. Connect via proxy server

Run the following command in your PC. You should get the following URL link in the form: `rerun+http://<PC IP address>:9876/proxy`
```bash
rerun --bind <PC IP address>
```

Run the following command in your EdgeFirst Platform.
```bash
python zenoh/boxes3d.py --connect --url rerun+http://<PC IP address>:9876/proxy
```

### **2. LiDAR (Fusion)**

**Purpose:** Subscribes to Zenoh topics that publish LiDAR fusion data (e.g. `rt/fusion/lidar`) and visualizes clustered point clouds in Rerun.

**Source Code:** [Python](python/fusion/zenoh/lidar.py)

**Usage:**

1. Connect remotely with an EdgeFirst Platform.
```bash
python zenoh/lidar.py --remote 10.10.41.67:7447
```

2. Connect via proxy server

Run the following command in your PC. You should get the following URL link in the form: `rerun+http://<PC IP address>:9876/proxy`
```bash
rerun --bind <PC IP address>
```

Run the following command in your EdgeFirst Platform.
```bash
python zenoh/lidar.py --connect --url rerun+http://<PC IP address>:9876/proxy
```

### **3. Occupancy Grid**

**Purpose:** Subscribes to Zenoh topics that publish occupancy grid data (e.g. `rt/fusion/occupancy`) and visualizes the resulting point cloud in Rerun.

**Source Code:** [Python](python/fusion/zenoh/occupancy.py)

**Usage:**

1. Connect remotely with an EdgeFirst Platform.
```bash
python zenoh/occupancy.py --remote 10.10.41.67:7447
```

2. Connect via proxy server

Run the following command in your PC. You should get the following URL link in the form: `rerun+http://<PC IP address>:9876/proxy`
```bash
rerun --bind <PC IP address>
```

Run the following command in your EdgeFirst Platform.
```bash
python zenoh/occupancy.py --connect --url rerun+http://<PC IP address>:9876/proxy
```

### **4. Model Output**

**Purpose:** Subscribes to Zenoh topics that publish model outputs (e.g. `rt/fusion/model_output`) and visualizes segmentation masks in Rerun.

**Source Code:** [Python](python/fusion/zenoh/model_output.py)

**Usage:**

1. Connect remotely with an EdgeFirst Platform.
```bash
python zenoh/model_output.py --remote 10.10.41.67:7447
```

2. Connect via proxy server

Run the following command in your PC. You should get the following URL link in the form: `rerun+http://<PC IP address>:9876/proxy`
```bash
rerun --bind <PC IP address>
```

Run the following command in your EdgeFirst Platform.
```bash
python zenoh/model_output.py --connect --url rerun+http://<PC IP address>:9876/proxy
```

### **5. Model Output Tracked**

**Purpose:** Subscribes to Zenoh topics that publish tracked model outputs (e.g. `rt/fusion/model_output/tracked`) and visualizes segmentation masks in Rerun.

**Source Code:** [Python](python/fusion/zenoh/model_output_tracked.py)

**Usage:**

1. Connect remotely with an EdgeFirst Platform.
```bash
python zenoh/model_output_tracked.py --remote 10.10.41.67:7447
```

2. Connect via proxy server

Run the following command in your PC. You should get the following URL link in the form: `rerun+http://<PC IP address>:9876/proxy`
```bash
rerun --bind <PC IP address>
```

Run the following command in your EdgeFirst Platform.
```bash
python zenoh/model_output_tracked.py --connect --url rerun+http://<PC IP address>:9876/proxy
```

### **6. Radar (Fusion)**

**Purpose:** Subscribes to Zenoh topics that publish radar fusion data (e.g. `rt/fusion/radar`) and visualizes clustered point clouds in Rerun.

**Source Code:** [Python](python/fusion/zenoh/radar.py)

**Usage:**

1. Connect remotely with an EdgeFirst Platform.
```bash
python zenoh/radar.py --remote 10.10.41.67:7447
```

2. Connect via proxy server

Run the following command in your PC. You should get the following URL link in the form: `rerun+http://<PC IP address>:9876/proxy`
```bash
rerun --bind <PC IP address>
```

Run the following command in your EdgeFirst Platform.
```bash
python zenoh/radar.py --connect --url rerun+http://<PC IP address>:9876/proxy
```

