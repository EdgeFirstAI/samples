# AI Assistant Development Guidelines

Instructions for AI coding assistants (GitHub Copilot, Cursor, Claude Code, etc.) working on the **EdgeFirst Samples** repository.

**Project:** EdgeFirst Samples (https://github.com/EdgeFirstAI/samples)
**Organization:** Au-Zone Technologies
**License:** Apache-2.0

---

## Overview

EdgeFirst Samples provides ready-to-run Rust and Python examples for subscribing to **EdgeFirst Perception Middleware** topics. Uses **Zenoh** pub/sub for sensor data (camera, LiDAR, radar, IMU, GPS, ML models, fusion) with **ROS2 CDR** serialization via `edgefirst-schemas`. Optional **Rerun** visualization.

Au-Zone Technologies develops edge AI and computer vision solutions for resource-constrained embedded devices. When contributing, prioritize:
- **Resource efficiency**: Memory, CPU, and power consumption matter on embedded devices
- **Code quality**: Maintainability, readability, and adherence to established patterns
- **License compliance**: Strict adherence to approved open source licenses
- **Documentation**: Clear explanations for complex logic and public APIs

---

## Build & Development Commands

```bash
# Build all examples (release)
cargo build --release --all-targets

# Build without Rerun visualization (rerun is a default feature)
cargo build --release --all-targets --no-default-features

# Run a specific example
cargo run --bin list-topics --release
cargo run --bin mega-sample --release -- --remote 192.168.1.100:7447

# Format and lint (must pass before commits)
cargo fmt
cargo fmt -- --check
cargo clippy --all-targets --all-features -- -D warnings

# Tests
cargo test --workspace --verbose

# Build documentation
cargo doc --no-deps --workspace

# Python examples (activate venv first)
source venv/bin/activate
pip install -r requirements.txt
python python/list_topics.py

# Python linting
black python/
flake8 python/

# SBOM and license compliance
.github/scripts/generate_sbom.sh
python3 .github/scripts/check_license_policy.py sbom.json

# Release (maintainers only, from main branch)
cargo release patch --execute --no-confirm
```

---

## Architecture

**Single Cargo package** with a shared library (`rust/lib.rs`) and ~25 binary crates. All binaries share one `Cargo.toml`.

```
rust/               # Rust examples (binary crates)
├── lib.rs         # Shared library (CLI args, Zenoh config)
├── camera/        # Camera examples (DMA, H.264, info)
├── lidar/         # LiDAR examples (points, depth, clusters)
├── radar/         # Radar examples (targets, clusters, cube)
├── model/         # ML inference examples (boxes, masks)
├── fusion/        # Sensor fusion examples
└── combined/      # Multi-sensor examples (mega_sample)

python/            # Python examples (parallel structure)
```

- `rust/lib.rs` — Shared `Args` struct (clap CLI) and `From<Args> for zenoh::Config`. Every binary imports this. The `Args` struct includes Rerun's clap args since `rerun` is a default feature.
- `rust/<category>/<example>.rs` — Binary crates organized by sensor domain
- `python/<category>/` — Parallel Python implementations of each example
- `.github/workflows/` — CI: `rust.yml` (fmt, clippy, build, test, docs), `python.yml`, `sbom.yml`, `sonar.yml`, `release.yml`
- `.github/scripts/` — SBOM generation, license checking, Python import verification

**Key pattern:** Every sample follows the same structure:
1. Parse `Args` with clap
2. Convert `Args` → `zenoh::Config` (via `From` impl in `lib.rs`)
3. Open Zenoh session
4. Declare subscriber on `rt/<sensor>/<type>` topic
5. Deserialize CDR messages using `edgefirst-schemas`
6. Optionally log to Rerun (`#[cfg(feature = "rerun")]`)
7. Wait for Ctrl+C

### Zenoh Communication

All examples use **Zenoh pub/sub** for sensor data with topics following the `rt/<sensor>/<message_type>` convention (`rt/` = "real-time"):
- `rt/camera/h264`, `rt/camera/dma`, `rt/camera/info`
- `rt/model/boxes2d`, `rt/model/mask`, `rt/model/compressed_mask`
- `rt/lidar/points`, `rt/lidar/depth`, `rt/lidar/clusters`
- `rt/radar/targets`, `rt/radar/clusters`, `rt/radar/cube`
- `rt/fusion/boxes3d`, `rt/fusion/occupancy`, `rt/fusion/radar`
- `rt/imu`, `rt/gps`

Samples autodiscover topics on local EdgeFirst platforms (Maivin, Raivin). Remote connections use `--remote <IP:PORT>`.

### Message Schemas

All message types come from the `edgefirst-schemas` crate with ROS2 CDR serialization:

```rust
use edgefirst_schemas::{CompressedImage, PointCloud2, BoundingBox2DArray};

// Deserialize from Zenoh sample
let msg: CompressedImage = cdr::deserialize_from(
    &*sample.payload().to_bytes(),
    cdr::size::Infinite,
)?;
```

Common types by domain:
- **Camera:** `Image`, `CompressedImage`, `DmaBuf`, `CameraInfo`
- **LiDAR:** `PointCloud2`, `LaserScan`
- **Radar:** `RadarTarget`, `RadarCluster`, `RadarCube`
- **ML:** `BoundingBox2D`, `BoundingBox2DArray`, `Mask`
- **Fusion:** `BoundingBox3D`, `OccupancyGrid`
- **Navigation:** `Imu`, `NavSatFix` (GPS)

### Rerun Visualization

Rerun is enabled by default (`default = ["rerun"]`). Build without it using `--no-default-features`.

```rust
#[cfg(feature = "rerun")]
{
    let rec = rerun::RecordingStreamBuilder::new("edgefirst-sample").spawn()?;
    rec.log("camera/image", &rerun::Image::new(data, [h, w]))?;
}
```

---

## Code Style

### Rust

- **Rust 2024 edition**
- Use `cargo fmt` for formatting (required before commit)
- Use `cargo clippy -- -D warnings` for linting
- Follow [Rust API Guidelines](https://rust-lang.github.io/api-guidelines/)
- Error handling: `anyhow::Result` with `.context()` for application code
- Avoid bare `.unwrap()` — use `.expect()` with message or proper error handling
- Async runtime: `tokio` with `#[tokio::main]`
- Graceful shutdown: `tokio::signal::ctrl_c().await?`
- Platform-specific code: Use `#[cfg(target_os = "linux")]` for DMA/pidfd features

### Python

- Use `black` for formatting (88 character line length)
- Use `flake8` for linting
- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Type hints recommended for public functions

### SPDX Headers (Required)

All source files must include SPDX license headers as the first lines:

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

### Code Quality Tools

- **SonarCloud:** Projects with `sonar-project.properties` must follow SonarQube guidelines. Address critical and high-severity issues before submitting PR.
- **Code review checklist:** No commented-out code or debug statements; comprehensive error handling; complex logic has explanatory comments; public APIs documented; no hardcoded values that should be configuration; proper resource cleanup.

---

## Git Workflow

### Branch Naming

**Format:** `<type>/<PROJECTKEY-###>[-optional-description]`

Types: `feature/`, `bugfix/`, `hotfix/`

```bash
feature/EDGEAI-123-add-authentication
bugfix/STUDIO-456-fix-memory-leak
hotfix/MAIVIN-789-security-patch
```

Rules:
- JIRA key is required (format: `PROJECTKEY-###`)
- Description is optional but recommended; use kebab-case
- Branch from `develop` for features/bugfixes, from `main` for hotfixes
- External contributors without JIRA access: use `feature/issue-123-description` with GitHub issue numbers

### Commit Messages

**Format:** `PROJECTKEY-###: Brief description of what was done`

- Subject line: 50-72 characters ideal
- Focus on WHAT changed, not HOW
- No type prefixes (`feat:`, `fix:`, etc.) — JIRA provides context
- Optional body: Use bullet points for additional detail
- **Commits must be signed** (`-s` flag)

```bash
# Good
EDGEAI-123: Add JWT authentication to user API

MAIVIN-789: Optimize tensor operations for inference
- Implemented tiled memory access pattern
- Reduced memory bandwidth by 40%

# Bad
fix bug                           # Missing JIRA key, too vague
feat(auth): add OAuth2           # Type prefix not our convention
EDGEAI-123                       # Missing description
```

### Pull Requests

- **2 approvals** for merging to `main`; **1 approval** for `develop`
- All CI/CD checks must pass
- PR title: `PROJECTKEY-### Brief description`
- PR description must link to JIRA ticket
- Merge using squash or rebase

### JIRA Integration

- Branch naming triggers JIRA automation
- PR creation moves tickets to review status
- Merge closes associated ticket
- Commit messages create automatic linkage

---

## License Policy

**CRITICAL**: Au-Zone has strict license policy for all dependencies.

### Allowed

- MIT, MIT-0, Apache-2.0
- BSD-2-Clause, BSD-3-Clause, ISC, 0BSD, Unlicense
- Zlib, BSL-1.0, CC0-1.0
- MPL-2.0 (file-level copyleft — safe as dependency; do not copy/modify MPL-2.0 source files)

### Review Required

- LGPL-2.1-or-later, LGPL-3.0-or-later (if statically linked)

### Strictly Disallowed

- GPL (any version), AGPL (any version)
- Creative Commons with NC or ND
- SSPL, BSL (before conversion), OSL-3.0

### Verification

Before adding dependencies:
1. Check license compatibility with Apache-2.0
2. Verify no GPL/AGPL in dependency tree
3. Run SBOM generation and license check:
   ```bash
   .github/scripts/generate_sbom.sh
   python3 .github/scripts/check_license_policy.py sbom.json
   ```
4. Update NOTICE file if dependencies changed
5. Commit `Cargo.lock` (binary project — ensures reproducible builds)

CI/CD automatically generates SBOM, validates schema, checks for disallowed licenses, and blocks PR merges on violations.

---

## Adding New Examples

1. Create `rust/<category>/<name>.rs` with SPDX header
2. Add `[[bin]]` entry in `Cargo.toml`
3. Create parallel `python/<category>/<name>.py` with SPDX header
4. Use `edgefirst_samples::Args` and the standard subscriber pattern from `lib.rs`
5. Deserialize with types from `edgefirst-schemas`
6. Optionally add Rerun visualization behind `#[cfg(feature = "rerun")]`
7. Format and lint: `cargo fmt && cargo clippy -- -D warnings`
8. Document usage in README (keep concise)

---

## Testing

This is a samples repository — testing is primarily manual integration testing against running EdgeFirst Perception instances.

**Quality verification (must pass):**
- `cargo build --all-targets` — build succeeds
- `cargo clippy --all-targets --all-features -- -D warnings` — no lint warnings
- `cargo test --workspace --verbose` — all tests pass
- `cargo fmt -- --check` — formatting correct
- `.github/scripts/generate_sbom.sh` — no license violations

**Platform testing:** Linux x86_64 and aarch64 (primary), Windows and macOS (client apps).

When adding unit tests, co-locate with implementation using `#[cfg(test)]` or use a separate `tests/` directory. Mock Zenoh sessions to avoid real network I/O.

---

## Performance Considerations

Target environment is edge devices with limited resources:
- Minimize allocations in message processing loops
- Reuse buffers where possible; use `Vec::with_capacity()` for known sizes
- Use zero-copy patterns (DMA buffers) — see `rust/camera/dma.rs`
- Avoid copying image/point cloud data when possible
- Optional profiling: Tracy (`cargo build --features tracy`) or `cargo flamegraph`

---

## Common Pitfalls

- **Zenoh multicast:** Default config uses multicast for local discovery. Disable for remote connections (`config.scouting.multicast.set_enabled(Some(false))`). The `--remote` argument pattern in `lib.rs` handles this.
- **DMA buffers:** Linux-only. Must use `#[cfg(target_os = "linux")]`. File descriptor lifetime management is critical.
- **Platform-specific code:** Always gate with `#[cfg(target_os = "linux")]` and provide graceful degradation for other platforms.

---

## Important Files

- `CONTRIBUTING.md` — Development setup, release process with cargo-release, PR requirements, dependency management
- `ARCHITECTURE.md` — Detailed technical overview of Zenoh patterns, message schemas, Rerun integration
- `release.toml` — cargo-release config (tag format, CHANGELOG replacement)
- `sonar-project.properties` — SonarCloud integration config
- `SECURITY.md` — Vulnerability reporting (email `support@au-zone.com`)
