# AI Assistant Development Guidelines

Instructions for AI coding assistants (GitHub Copilot, Cursor, Claude Code, etc.) working on the **EdgeFirst Samples** repository.

**Project:** EdgeFirst Samples (https://github.com/EdgeFirstAI/samples)
**Organization:** Au-Zone Technologies
**Version:** 2.0
**Last Updated:** March 2026

---

## Overview

Au-Zone Technologies develops edge AI and computer vision solutions for resource-constrained embedded devices. This repository provides **sample applications** demonstrating **EdgeFirst Perception Middleware**—a modular edge AI platform communicating over Zenoh pub/sub.

**Target Audience:**
- Developers learning EdgeFirst Perception
- Platform integrators building edge AI systems
- Engineers evaluating EdgeFirst for projects

**Priorities:**
- **Resource efficiency**: Memory, CPU, and power consumption matter on embedded devices
- **Code quality**: Maintainability, readability, and adherence to established patterns
- **Documentation**: Clear explanations for complex logic and public APIs
- **License compliance**: Strict adherence to approved open source licenses (Apache-2.0)

---

## Technology Stack

**Languages:**
- **Rust**: 2024 edition (primary language for examples)
- **Python**: 3.8+ (alternative examples for rapid prototyping)

**Build System:**
- **Cargo**: Rust workspace with multiple binary crates
- **Python**: Standard pip/venv setup

**Key Dependencies:**
- **Zenoh** (`zenoh 1.3.4`): High-performance pub/sub middleware for sensor data
- **edgefirst-schemas** (`2.2.0`): Zero-copy CDR message type definitions (Apache-2.0)
- **Rerun** (`0.27.2`): Optional visualization framework (feature flag)
- **openh264**: H.264 video decoding
- **ndarray**: N-dimensional array processing for masks
- **colorous**: Color mapping for point cloud visualization

**Supported Platforms:**
- **Linux**: Primary target (kernel 5.10+)
- **Windows**: Remote client applications
- **macOS**: Remote client applications
- **Tested on**: x86_64, aarch64

---

## Repository Structure

```
rust/                    # Rust examples (binary crates)
├── lib.rs              # Shared library (CLI args, Zenoh config)
├── list-topics.rs      # Topic discovery
├── gps.rs              # GPS/NavSatFix subscriber
├── imu.rs              # IMU orientation subscriber
├── camera/             # Camera examples
│   ├── camera_info.rs  # Camera calibration info
│   ├── dma.rs          # DMA zero-copy buffers (Linux-only)
│   └── h264.rs         # H.264 stream decoding
├── lidar/              # LiDAR examples
│   ├── points.rs       # 3D point cloud
│   └── clusters.rs     # Clustered point cloud
├── radar/              # Radar examples
│   ├── targets.rs      # Radar target detections
│   ├── clusters.rs     # Radar clusters
│   ├── cube.rs         # Range-Doppler-Azimuth cube
│   └── info.rs         # Radar configuration
├── model/              # ML inference output examples
│   ├── boxes2d.rs      # 2D bounding boxes (rt/model/output)
│   ├── boxes2d_tracked.rs  # Tracked 2D boxes with persistent IDs (rt/model/output)
│   ├── mask.rs         # Segmentation mask (rt/model/output)
│   └── model_info.rs   # Model metadata
├── fusion/             # Multi-sensor fusion examples
│   ├── boxes3d.rs      # 3D bounding boxes
│   ├── occupancy.rs    # Occupancy grid
│   ├── model_output.rs # Fused model output (segmentation)
│   ├── model_output_tracked.rs  # Fused tracked model output
│   ├── lidar.rs        # Fused LiDAR point cloud
│   └── radar.rs        # Fused radar point cloud
└── combined/           # Multi-topic examples
    └── mega_sample.rs  # Complete pipeline demo

python/                 # Python examples (parallel structure)
├── list-topics.py
├── gps.py
├── imu.py
├── camera/             # Camera (dma, h264, jpeg, camera_info)
├── lidar/              # LiDAR (points, clusters)
├── radar/              # Radar (targets, clusters, cube, info)
├── model/              # ML models (boxes2d, boxes2d_tracked, mask, model_info)
├── fusion/             # Fusion (boxes3d, occupancy, model_output, model_output_tracked, lidar, radar)
└── combined/           # Combined (mega_sample, camera_model, camera_lidar, camera_radar)
```

**Note:** Python has additional combined examples (`camera_lidar.py`, `camera_radar.py`, `camera_model.py`) and a JPEG camera example (`camera/jpeg.py`) that do not yet have Rust equivalents.

---

## Message Serialization — Zero-Copy CDR API

All messages are serialized with **ROS2 CDR** (Common Data Representation). The `edgefirst-schemas` crate (v2.2.0) provides a **zero-copy** deserialization API where message types wrap borrowed byte buffers and expose fields via accessor methods.

### Current API Pattern (edgefirst-schemas 2.2.0)

```rust
use edgefirst_schemas::edgefirst_msgs::Detect;

let bytes = msg.payload().to_bytes();
let detection = Detect::from_cdr(&bytes)?;

// Access fields via accessor methods (not direct field access)
for b in detection.boxes() {
    println!("label={} center=({}, {})", b.label, b.center_x, b.center_y);
}
```

**Key points:**
- Use `Type::from_cdr(&bytes)?` — the type wraps a borrowed buffer, no heap allocation
- The `bytes` variable must outlive the deserialized view
- Top-level fields use accessor methods: `msg.field()` not `msg.field`
- Inner/nested types (e.g., box fields from `detection.boxes()`) may use direct public fields
- Error handling: Use `?` operator, not `.unwrap()`, for `from_cdr` calls

### Message Type Locations

| Module | Types |
|--------|-------|
| `edgefirst_schemas::sensor_msgs` | `Image`, `CompressedImage`, `Imu`, `NavSatFix`, `PointCloud2`, `CameraInfo` |
| `edgefirst_schemas::edgefirst_msgs` | `Detect`, `Mask`, `DmaBuffer`, `RadarCube`, `RadarInfo`, `ModelInfo`, `Model` |
| `edgefirst_schemas::foxglove_msgs` | `FoxgloveCompressedVideo` |

> **Note:** The `rt/model/output` topic uses the unified `Model` type, which combines detection boxes and segmentation masks in a single message. The legacy topics `rt/model/boxes2d` and `rt/model/mask` are disabled by default and should not be used in new code.

### PointCloud2 — DynPointCloud API

For `PointCloud2` messages, use the zero-copy `DynPointCloud` view instead of the removed `decode_pcd` helper:

```rust
use edgefirst_schemas::sensor_msgs::PointCloud2;
use edgefirst_schemas::sensor_msgs::pointcloud::DynPointCloud;

let pcd = PointCloud2::from_cdr(&bytes)?;
let cloud = DynPointCloud::from_pointcloud2(&pcd)?;

// Type-coercing reads — automatically handles any stored numeric type
for point in cloud.iter() {
    let x = point.read_as_f32("x").unwrap_or(0.0);
    let y = point.read_as_f32("y").unwrap_or(0.0);
    let z = point.read_as_f32("z").unwrap_or(0.0);
    let class = point.read_as_f64("vision_class").unwrap_or(0.0);
}
```

For hot-loop performance, resolve field descriptors once and read per-point:

```rust
let x_desc = cloud.field("x").expect("missing x field");
let y_desc = cloud.field("y").expect("missing y field");
let z_desc = cloud.field("z").expect("missing z field");

for point in cloud.iter() {
    let x = x_desc.read_as_f32(point.data()).unwrap_or(0.0);
    let y = y_desc.read_as_f32(point.data()).unwrap_or(0.0);
    let z = z_desc.read_as_f32(point.data()).unwrap_or(0.0);
}
```

**Important:** The old `decode_pcd()` function no longer exists. All point cloud access must use `DynPointCloud` with `read_as_f32`/`read_as_f64` for type-safe, type-coercing field access.

---

## Zenoh Communication Patterns

### Shared Library (`lib.rs`)

All samples share `Args` from `lib.rs` which provides:
- `--mode` (peer/client) — Zenoh connection mode
- `--remote <endpoint>` — connect to remote Zenoh endpoints
- `--listen <endpoint>` — listen on Zenoh endpoints
- `--no-multicast-scouting` — disable multicast discovery
- Rerun visualization args (via `rerun::clap::RerunArgs`)

`Args` implements `From<Args> for zenoh::Config`, so session creation is:

```rust
let args = Args::parse();
let session = zenoh::open(args.clone()).await.unwrap();
```

### Subscriber Pattern

```rust
use edgefirst_schemas::sensor_msgs::NavSatFix;

let subscriber = session.declare_subscriber("rt/gps").await.unwrap();

while let Ok(msg) = subscriber.recv_async().await {
    let bytes = msg.payload().to_bytes();
    let gps = NavSatFix::from_cdr(&bytes)?;
    println!("lat={} lon={}", gps.latitude(), gps.longitude());
}
```

### Topic Naming

- Format: `rt/<sensor>/<message_type>`
- Examples: `rt/camera/h264`, `rt/lidar/points`, `rt/model/boxes2d`, `rt/fusion/boxes3d`
- Prefix `rt/` = "real-time"
- Wildcard: `rt/**` matches all topics

---

## Rerun Visualization

### Feature Flag

Rerun is enabled by default but can be disabled:

```toml
[features]
default = ["rerun"]
rerun = ["dep:rerun"]
```

### Usage Pattern

```rust
let (rr, _serve_guard) = args.rerun.init("sample-name")?;
rr.log("entity/path", &rerun::Image::from_rgb24(data, [w, h]))?;
```

### Build Commands

```bash
cargo build --release                    # With Rerun (default)
cargo build --release --no-default-features  # Without Rerun
```

---

## Code Style

### Rust

- **Edition**: 2024
- **Formatting**: `cargo fmt` (required before commit)
- **Linting**: `cargo clippy -- -D warnings`
- **Error handling**: Use `Result<(), Box<dyn Error>>` for `main()`, propagate with `?`
- **Async runtime**: `tokio` with `#[tokio::main]`
- **Avoid**: bare `.unwrap()` on CDR deserialization — use `?` or `.expect()` with context

### Python

- **Formatting**: `black` (88 character line length)
- **Linting**: `flake8`
- **Style**: PEP 8, type hints recommended for public functions

### SPDX Headers (Required)

All source files must include:

**Rust:**
```rust
// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.
```

**Python:**
```python
# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.
```

---

## Adding New Examples

1. Create the Rust binary in the appropriate `rust/<category>/` directory
2. Add a `[[bin]]` entry in `Cargo.toml`
3. Create a parallel Python example in `python/<category>/`
4. Add SPDX license headers to all new files
5. Follow the established subscriber pattern from existing samples
6. Use `?` for error propagation, not `.unwrap()`
7. Update README.md Examples Overview table

### Sample Binary Template

```rust
// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::sensor_msgs::YourType;
use std::error::Error;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    let subscriber = session.declare_subscriber("rt/your/topic").await.unwrap();

    // Create Rerun logger using the provided parameters
    let (rr, _serve_guard) = args.rerun.init("your-sample-name")?;

    while let Ok(msg) = subscriber.recv_async().await {
        let bytes = msg.payload().to_bytes();
        let data = YourType::from_cdr(&bytes)?;
        // Process and visualize data...
    }

    Ok(())
}
```

---

## Git Workflow

### Branch Naming

**Format**: `<type>/<PROJECTKEY-###>[-optional-description]`

- `feature/EDGEAI-123-add-authentication`
- `bugfix/STUDIO-456-fix-memory-leak`
- `hotfix/MAIVIN-789-security-patch`

### Commit Messages

**Format**: `PROJECTKEY-###: Brief description`

```
EDGEAI-123: Add temperature sensor sample
EDGEAI-456: Fix memory leak in radar cube processing
```

- 50-72 character subject line
- No type prefixes (`feat:`, `fix:`, etc.) — JIRA provides context
- Focus on WHAT changed, not HOW

### Pull Request Requirements

- **2 approvals** for merging to `main`, **1 approval** for `develop`
- All CI/CD checks must pass
- Title: `PROJECTKEY-### Brief description`
- Link to JIRA ticket in description

---

## License Policy

**Project License:** Apache-2.0

### Allowed Dependencies

- MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, 0BSD, Unlicense, MPL-2.0

### Strictly Disallowed

- GPL (any version), AGPL, SSPL, BSL, CC-NC, CC-ND, OSL-3.0

### Verification

```bash
# Generate and validate SBOM
.github/scripts/generate_sbom.sh
```

---

## Quality Verification

```bash
# Build all targets
cargo build --all-targets

# Lint
cargo clippy -- -D warnings

# Format check
cargo fmt -- --check

# SBOM compliance
.github/scripts/generate_sbom.sh
```

---

## Platform-Specific Notes

### DMA Buffers (Linux-only)

```rust
#![cfg_attr(not(target_os = "linux"), allow(dead_code, unused_imports))]
// ... Linux-specific code ...
#[cfg(not(target_os = "linux"))]
#[tokio::main]
async fn main() {
    eprintln!("Only Linux is supported for camera DMA example");
}
```

### Remote vs. Local Execution

- Samples autodiscover topics on EdgeFirst platforms (Maivin, Raivin)
- Remote connections: `--remote <IP:PORT>`
- Ensure `zenohd` is running on the device for remote access

---

## Common Pitfalls

1. **Do NOT use `serde_cdr::deserialize`** — it was removed. Use `Type::from_cdr(&bytes)?`
2. **Do NOT use `decode_pcd()`** — it was removed. Use `DynPointCloud::from_pointcloud2(&pcd)?`
3. **Do NOT call `.to_vec()` on payload bytes** unless required — it defeats zero-copy
4. **Do NOT use `.unwrap()` on `from_cdr`** — use `?` for proper error propagation
5. **Zenoh multicast**: Disable for remote connections with `--no-multicast-scouting`
6. **DMA samples**: Only work on-device with matching permissions — not over remote
7. **Edition 2024**: Requires Rust 1.85+ — `unsafe_op_in_unsafe_fn` is a hard error
8. **Do NOT subscribe to `rt/model/boxes2d` or `rt/model/mask`** — these legacy topics are disabled by default. Use `rt/model/output` with the unified `Model` type instead.

---

## Security

- Never hardcode credentials or API keys
- Validate external inputs at system boundaries
- Report vulnerabilities to `support@au-zone.com` (see SECURITY.md)

---

## Performance Considerations

- **Zero-copy first**: Use borrowed views (`from_cdr`) over allocating deserializers
- **Minimize allocations** in message processing loops
- **Reuse buffers**: Use `Vec::with_capacity()` for known sizes
- **DMA buffers**: Use `camera/dma.rs` pattern for highest-performance camera access
- **Profile**: Optional Tracy integration via `cargo build --features tracy`

---

*Document version 2.0 — March 2026*
*Organization: Au-Zone Technologies*
*License: Apache-2.0*
