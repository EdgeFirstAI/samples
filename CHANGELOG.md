# Changelog

All notable changes to EdgeFirst Samples will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

<!--
IMPORTANT: Before creating a release, document all user-visible changes here.
Empty releases should be avoided - ensure meaningful changes are listed.
-->

### Added
- Unified `Model` message type support (`rt/model/output`) combining detection boxes and segmentation masks in a single message
- `required-features` gating on `[[bin]]` entries — `cargo build --no-default-features` builds only non-visualization binaries
- Release profile optimizations: `lto = true`, `codegen-units = 1`, `strip = true`

### Changed
- Updated to edgefirst-schemas 2.2.0 zero-copy CDR API with native type-coercing point cloud field access (`Type::from_cdr(&bytes)?`)
- Model samples (`boxes2d`, `boxes2d_tracked`, `mask`) rewritten for unified `rt/model/output` topic
- Mega sample updated to subscribe to `rt/model/output` instead of legacy `rt/model/boxes2d`
- Point cloud samples migrated from `decode_pcd()` to `DynPointCloud::from_pointcloud2()`
- All single-topic samples switched from blocking `recv()` to async `recv_async().await`
- `Arc<Mutex<RecordingStream>>` replaced with `Arc<RecordingStream>` in mega_sample (RecordingStream is Send+Sync)
- Vec allocations hoisted above hot loops for improved embedded performance
- Rerun variable naming standardized to `rr` across all samples
- AGENTS.md replaced by `.github/copilot-instructions.md`
- ARCHITECTURE.md completely rewritten for current API and patterns

### Removed
- `model-compressed_mask` sample (compressed mask topic obsoleted by on-the-wire compression)
- `lidar-depth` sample (depth image topic removed for multi-lidar sensor support)
- `lidar-reflect` sample (reflectivity image topic removed for multi-lidar sensor support)
- `zstd` dependency (only used by removed compressed_mask sample)
- `rust/hal/decoder.rs` work-in-progress file (unregistered, with undeclared dependencies)

### Fixed
- Array shape `[width, height]` corrected to `[height, width]` in fusion model_output samples
- `.unwrap()` calls replaced with `?` operator in fusion model_output samples
- `let _ = rr.log(...)` replaced with `rr.log(...)?` for proper error propagation across 9 files
- Unnecessary `.to_vec()` and `.clone()` copies removed in zero-copy context

## [0.1.2] - 2025-11-19

### Added
- **QUICKSTART.md**: New quick start guide designed for ZIP archive distribution
  - Focused user onboarding with clear architecture diagrams
  - Usage examples for local and remote EdgeFirst platform connections
  - Highlights key examples: `list-topics` (Hello World) and `mega-sample` (complete pipeline)

### Changed
- **README.md restructuring**: Priority-based organization for better learning progression
  - Quick start section moved to top with download links
  - Sample applications organized by complexity and use case
  - Enhanced Examples Overview table with clearer descriptions
- **Release workflow improvements**: 
  - ZIP archives now include QUICKSTART.md instead of README.md
  - Release notes combine QUICKSTART + CHANGELOG for better context
  - Added platform download table to GitHub releases

### Documentation
- Improved user onboarding experience for distributed archives
- Better separation between end-user quick start and developer documentation

## [0.1.1] - 2025-11-19

### Added
- **Automated GitHub release workflow**: 
  - Creates releases automatically on version tags
  - Generates platform-specific ZIP archives (Linux x86_64/aarch64, Windows, macOS)
  - Uploads artifacts to GitHub Releases

### Fixed
- Corrected all GitHub repository URLs from placeholder to `EdgeFirstAI/samples`
- Updated README badges to point to correct repository

## [0.1.0] - 2025-11-19

**First public release** of EdgeFirst Perception Middleware samples repository.

This release represents the initial open-source publication of comprehensive Rust and Python examples demonstrating EdgeFirst Perception capabilities across camera, LiDAR, radar, and sensor fusion use cases.

### Highlights

- **Comprehensive Examples**: 28+ Rust examples with parallel Python implementations
  - Camera: DMA, H.264, info, camera_info
  - LiDAR: points, depth, clusters, reflectivity
  - Radar: targets, clusters, cube, info
  - ML Inference: 2D boxes, masks, tracked objects
  - Sensor Fusion: radar fusion, lidar fusion, 3D boxes, occupancy grids
  - Navigation: IMU, GPS

- **Production-Ready CI/CD**
  - Multi-platform testing (Linux, Windows, macOS)
  - Rust: cargo fmt, clippy, build, test
  - Python: black, flake8, import verification
  - SBOM generation with license compliance checking
  - SonarQube integration for code quality

- **Open Source Infrastructure**
  - Apache-2.0 licensed with full SPDX headers
  - Comprehensive documentation (README, CONTRIBUTING, ARCHITECTURE, SECURITY)
  - GitHub Actions workflows optimized for cross-platform development
  - Community guidelines (Code of Conduct, issue templates, PR templates)

### Added

- Zenoh-based pub/sub communication patterns for all sensor types
- Optional Rerun visualization integration (feature-gated)
- Cross-platform build support (Linux primary, Windows/macOS client apps)
- Automated SBOM generation and license policy enforcement
- Version management with cargo-release
- Python import verification script for CI/CD reliability

### Documentation

- Architecture guide explaining Zenoh patterns and message schemas
- Contributing guide with Rust and Python development setup
- Security policy with vulnerability reporting process
- AGENTS.md guide for AI-assisted development with project conventions

### Infrastructure

- GitHub Actions workflows for continuous integration
- SBOM generation using scancode-toolkit (22s optimized performance)
- License policy compliance with automated checking
- Support for edgefirst-schemas 1.4.0 (Apache-2.0)

### Notes

- This is a samples repository for demonstration and learning
- Not published to crates.io (publish = false)
- Versions track sample evolution and documentation improvements
- Previous development history considered legacy and not detailed here

---

## Version History Format

Each release documents changes in these categories:

- **Added**: New features and capabilities
- **Changed**: Changes in existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security vulnerability fixes
