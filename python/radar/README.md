# EdgeFirst Perception Middleware Radar Samples

This section provides sample applications that demonstrate using EdgeFirst utilities for radar data decoding, visualization, and topic subscription. The **local** examples run on-device and focus on radar data processing, while the **zenoh** directory shows examples for subscribing to Zenoh topics hosted by an [EdgeFirst Platform](https://doc.edgefirst.ai/latest/platforms/).

> Note: For any of these programs press CTRL-C to quit.

## Local Examples

The following examples are intended to run locally on an EdgeFirst device.

### **1. Radar Targets**

**Purpose:** Demonstrate decoding and visualizing radar target data from local sources.

**Source Code:** [targets.py](targets.py)

**Usage:**

```bash
python python/radar/targets.py --input /path/to/radar_data.bin
```

| Parameters | Definition | Default |
|------------|------------|---------|
| --input    | Path to radar data file | None |
| --save     | Path to save visualizations | None |

### **2. Radar Clusters**

**Purpose:** Demonstrate decoding and visualizing radar cluster data.

**Source Code:** [clusters.py](clusters.py)

**Usage:**

```bash
python python/radar/clusters.py --input /path/to/radar_data.bin
```

### **3. Radar Cube**

**Purpose:** Demonstrate decoding and visualizing radar cube data.

**Source Code:** [cube.py](cube.py)

**Usage:**

```bash
python python/radar/cube.py --input /path/to/radar_cube_data.bin
```

### **4. Radar Info**

**Purpose:** Display radar sensor information and configuration.

**Source Code:** [info.py](info.py)

**Usage:**

```bash
python python/radar/info.py --input /path/to/radar_info.json
```

## Zenoh Examples

These examples are only supported in [EdgeFirst Platforms](https://doc.edgefirst.ai/latest/platforms/) such as the Maivin or Raivin. These platforms publish radar data in Zenoh (ROS-like) topics which are unique to these platforms where other devices can then use to subscribe and receive data.

These examples can be run with an EdgeFirst Platform with the Zenoh and radar services enabled.

`sudo systemctl enable --now zenohd`
`sudo systemctl enable --now radar`

### **1. Radar Targets (Zenoh)**

**Purpose:** Subscribes to Zenoh topics (e.g. `rt/radar/targets`) to receive and visualize radar target detections.

**Source Code:** [targets.py](targets.py)

**Usage:**

```bash
python python/radar/targets.py --remote <edgefirst-ip>:7447
```

### **2. Radar Clusters (Zenoh)**

**Purpose:** Subscribes to Zenoh topics to receive and visualize radar cluster data.

**Source Code:** [clusters.py](clusters.py)

**Usage:**

```bash
python python/radar/clusters.py --remote <edgefirst-ip>:7447
```

### **3. Radar Cube (Zenoh)**

**Purpose:** Subscribes to Zenoh topics to receive and visualize radar cube data.

**Source Code:** [cube.py](cube.py)

**Usage:**

```bash
python python/radar/cube.py --remote <edgefirst-ip>:7447
```

### **4. Radar Info (Zenoh)**

**Purpose:** Subscribes to Zenoh topics to receive and display radar sensor information.

**Source Code:** [info.py](info.py)

**Usage:**

```bash
python python/radar/info.py --remote <edgefirst-ip>:7447
```

---

For more details, see the code and docstrings in each script, or visit the [EdgeFirst documentation](https://doc.edgefirst.ai/latest/).
