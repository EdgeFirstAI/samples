# EdgeFirst Perception Middleware LiDAR Samples

This section provides sample applications that demonstrate using EdgeFirst utilities for LiDAR data decoding, visualization, and topic subscription. The **local** examples run on-device and focus on LiDAR data processing, while the **zenoh** directory shows examples for subscribing to Zenoh topics hosted by an [EdgeFirst Platform](https://doc.edgefirst.ai/latest/platforms/).

> Note: For any of these programs press CTRL-C to quit.

## Local Examples

The following examples are intended to run locally on an EdgeFirst device.

### **1. LiDAR Points**

**Purpose:** Demonstrate decoding and visualizing LiDAR point cloud data from local sources.

**Source Code:** [points.py](points.py)

**Usage:**

```bash
python python/lidar/points.py --input /path/to/lidar_data.bin
```

| Parameters | Definition | Default |
|------------|------------|---------|
| --input    | Path to LiDAR data file | None |
| --save     | Path to save visualizations | None |

### **2. LiDAR Depth**

**Purpose:** Demonstrate decoding and visualizing LiDAR depth data.

**Source Code:** [depth.py](depth.py)

**Usage:**

```bash
python python/lidar/depth.py --input /path/to/lidar_data.bin
```

### **3. LiDAR Clusters**

**Purpose:** Demonstrate decoding and visualizing LiDAR cluster data.

**Source Code:** [clusters.py](clusters.py)

**Usage:**

```bash
python python/lidar/clusters.py --input /path/to/lidar_data.bin
```

### **4. LiDAR Reflectivity**

**Purpose:** Demonstrate decoding and visualizing LiDAR reflectivity data.

**Source Code:** [reflect.py](reflect.py)

**Usage:**

```bash
python python/lidar/reflect.py --input /path/to/lidar_data.bin
```

## Zenoh Examples

These examples are only supported in [EdgeFirst Platforms](https://doc.edgefirst.ai/latest/platforms/) such as the Maivin or Raivin. These platforms publish LiDAR data in Zenoh (ROS-like) topics which are unique to these platforms where other devices can then use to subscribe and receive data.

These examples can be run with an EdgeFirst Platform with the Zenoh and lidar services enabled.

`sudo systemctl enable --now zenohd`
`sudo systemctl enable --now lidar`

### **1. LiDAR Points (Zenoh)**

**Purpose:** Subscribes to Zenoh topics (e.g. `rt/lidar/points`) to receive and visualize LiDAR point cloud data.

**Source Code:** [points.py](points.py)

**Usage:**

```bash
python python/lidar/points.py --remote <edgefirst-ip>:7447
```

### **2. LiDAR Depth (Zenoh)**

**Purpose:** Subscribes to Zenoh topics to receive and visualize LiDAR depth data.

**Source Code:** [depth.py](depth.py)

**Usage:**

```bash
python python/lidar/depth.py --remote <edgefirst-ip>:7447
```

### **3. LiDAR Clusters (Zenoh)**

**Purpose:** Subscribes to Zenoh topics to receive and visualize LiDAR cluster data.

**Source Code:** [clusters.py](clusters.py)

**Usage:**

```bash
python python/lidar/clusters.py --remote <edgefirst-ip>:7447
```

### **4. LiDAR Reflectivity (Zenoh)**

**Purpose:** Subscribes to Zenoh topics to receive and visualize LiDAR reflectivity data.

**Source Code:** [reflect.py](reflect.py)

**Usage:**

```bash
python python/lidar/reflect.py --remote <edgefirst-ip>:7447
```

---

For more details, see the code and docstrings in each script, or visit the [EdgeFirst documentation](https://doc.edgefirst.ai/latest/).
