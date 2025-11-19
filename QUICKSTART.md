# EdgeFirst Perception Samples - Quick Start Guide

**Ready-to-run examples for EdgeFirst Perception Middleware topics.**

This package contains pre-built sample applications demonstrating how to subscribe to and process topics from EdgeFirst Perception Middleware—a modular edge AI platform for vision, LiDAR, radar, and sensor fusion.

---

## What's Included

All 26 compiled examples for your platform:

- **Discovery:** `list-topics` - Discover available topics
- **Combined:** `mega-sample` - Complete vision pipeline demo
- **Camera:** `camera-dma`, `camera-h264`, `camera-info` - Image acquisition
- **ML Models:** `model-boxes`, `model-mask`, `model-boxes_tracked`, `model-info` - Object detection/segmentation
- **Radar:** `radar-targets`, `radar-clusters`, `radar-cube`, `radar-info` - Radar processing
- **LiDAR:** `lidar-points`, `lidar-depth`, `lidar-clusters`, `lidar-reflect` - Point clouds
- **Fusion:** `fusion-boxes3d`, `fusion-occupancy`, `fusion-lidar`, `fusion-radar` - Multi-sensor integration
- **Navigation:** `imu`, `gps` - Inertial and positioning data

Plus: `README.md`, `LICENSE`, `NOTICE`

---

## Running the Samples

### Local Mode (On EdgeFirst Device)

When running on an EdgeFirst platform (Maivin, Raivin) with Perception middleware active:

```bash
# Discover available topics
./list-topics

# View complete vision pipeline
./mega-sample

# Subscribe to specific topics
./camera-h264
./model-boxes
```

### Remote Mode (From Another Computer)

To connect to an EdgeFirst device over the network:

```bash
# Enable Zenoh router on EdgeFirst device first
ssh user@192.168.1.100
sudo systemctl enable --now zenohd

# From your computer - connect to device
./list-topics --remote tcp/192.168.1.100:7447
./mega-sample --remote tcp/192.168.1.100:7447
./camera-h264 --remote tcp/192.168.1.100:7447
```

> **Note:** Replace `192.168.1.100` with your EdgeFirst device's IP address.

---

## Key Examples

### 1. List Topics - "Hello World"

**Discover what's available:**

```bash
./list-topics
```

This connects to the Zenoh network and lists all published topics like:
- `rt/camera/h264` - Camera video stream
- `rt/model/boxes2d` - Object detections
- `rt/lidar/points` - LiDAR point cloud
- `rt/radar/targets` - Radar detections

### 2. Mega Sample - Complete Vision Pipeline

**See EdgeFirst in action:**

```bash
./mega-sample
```

This is the **showcase demo** displaying:
- Real-time camera feed with H.264 decoding
- Bounding boxes around detected objects
- Segmentation masks for pixel classification
- 3D sensor fusion (if LiDAR/radar available)
- GPS location (if available)

Perfect for demonstrating EdgeFirst's edge vision capabilities!

### 3. Individual Topic Examples

**Focus on specific data sources:**

```bash
# Camera stream only
./camera-h264

# Detection results only
./model-boxes

# LiDAR point cloud
./lidar-points

# Radar targets
./radar-targets
```

---

## Common Options

All examples support:

```bash
# Show help
./list-topics --help

# Connect to remote device
./camera-h264 --remote tcp/192.168.1.100:7447

# Specify custom topic (when applicable)
./camera-h264 --topic rt/camera/h264
```

---

## What is EdgeFirst Perception?

EdgeFirst Perception Middleware is a modular software stack for edge AI:

- **Camera Service** - Interfaces with cameras, delivers H.264/H.265/JPEG streams
- **Vision Models** - Runs ML inference for object detection and segmentation
- **LiDAR/Radar Services** - Processes point clouds and target tracking
- **Fusion Service** - Combines multiple sensors for 3D scene understanding

Services communicate using **Zenoh** (high-performance pub/sub) with **ROS2 CDR** message serialization.

```
         Publishers              Subscriber-Publishers        Subscribers
         ==========              =====================        ===========

┌─────────────┐              ┌──────────────┐              ┌─────────────┐
│   Camera    │─────────────▶│ Vision Model │─────────────▶│ Sample Apps │
│   Service   │              │   Service    │              │   (These)   │
└─────────────┘              └──────────────┘              └─────────────┘
      │                              │                             ▲
      │                              │                             │
      ├──────────────────────────────┼─────────────────────────────┤
┌─────────────┐              ┌─────────────┐                       │
│    LiDAR    │─────────────▶│   Fusion    │───────────────────────┤
│   Service   │              │   Service   │                       │
└─────────────┘              └─────────────┘                       │
      │                              │                             │
      │                              │                             │
      ├──────────────────────────────┴─────────────────────────────┤
┌─────────────┐                                                    │
│    Radar    │────────────────────────────────────────────────────┘
│   Service   │
└─────────────┘

                    All communicate via Zenoh Topics (rt/*)
            Topics: rt/camera/h264, rt/model/boxes2d, rt/fusion/boxes3d, ...
```

---

## Next Steps

### Learn More

- **Full Documentation:** https://doc.edgefirst.ai/develop/perception/dev/
- **Source Code:** https://github.com/EdgeFirstAI/samples
- **API Reference:** https://doc.edgefirst.ai/develop/perception/api/
- **Platform Docs:** https://doc.edgefirst.ai/develop/platforms/

### Build Custom Applications

These samples demonstrate the patterns for:
1. Connecting to Zenoh network
2. Subscribing to topics
3. Deserializing ROS2 CDR messages
4. Processing sensor data

Use them as templates for your own applications!

### Visualization Tools

- **Rerun:** Real-time visualization (source builds with `--features rerun`)
- **MCAP Recorder:** Record topics for playback
- **Foxglove Studio:** ROS2-compatible visualization
- **EdgeFirst Studio:** MLOps platform for model deployment

---

## Support

- **GitHub:** https://github.com/EdgeFirstAI/samples
- **Documentation:** https://doc.edgefirst.ai/
- **Email:** support@au-zone.com

---

## License

Apache License 2.0 - Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

See `LICENSE` file for full license text and `NOTICE` for third-party dependencies.
