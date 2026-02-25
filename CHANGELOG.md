# Changelog

All notable changes to EdgeFirst Samples will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

<!-- 
IMPORTANT: Before creating a release, document all user-visible changes here.
Empty releases should be avoided - ensure meaningful changes are listed.
-->

## [0.2.0] - 2026-02-27

### Added
- Local camera examples for reading from the video4linux camera using either GStreamer or OpenCV
- Local combined examples for running the YOLOv8 Ultralytics for inference and visualization support on the monitor using either PyCairo (GStreamer example) or OpenCV
- Local and Zenoh HAL examples for demonstrating resizing and letterbox transformations using HAL vs OpenCV
- Local model examples for demonstrating how to read the model embedded metadata, run YOLOv8 Ultralytics (ONNX and TFLite) on a sample image using either HAL or OpenCV
- Added small description docstrings of each sample at the top of the script
- Extended support for TFLite models for decoder.py script, not just ONNX models.

### Fixed
- Rust applications now automatically adds `tcp/` before the IP for the `--remote` CMD argument to avoid the user having to add this themselves
- list-topics.py and list-topics.rs now uses try_recv rather than recv for recieving topic messages so that the timeout argument (default to 5 seconds) has an effect
- Updates to HAL are now reflected such as changes to `ImageConverter` to `ImageProcessor`
- Cargo.toml now uses released edgefirst_hal package rather than searching for a local edgefirst directory
- Applied latest changes to EdgeFirst Schemas which renames `DmaBuf` to `DmaBuffer`
- Applied latest [migrations from 0.27 to 0.28 in rerun-sdk](https://rerun.io/docs/reference/migration/migration-0-28) which now uses `TransformAxes3D` instead of `Transform3D` for imu.rs
- Fixed stuttered outputs when using H264 which is due to the loss of key frames. Process only if the keyframe is available, but may result in occasional drop in FPS.

### Changed
- Structural changes to the Python examples to have a split "local" and "zenoh" examples
- camera_info.rs has been renamed to info.rs to maintain naming pattern of other scripts
- Avoid usage of edgefirst_hal.Decoder.decode_yolo_det found in decoder.py and tracking.py scripts since this function is scheduled for deprecation. Furthermore, it returned unexpected outputs when tested. Using edgefirst_hal.Decoder.decode instead. 

### Documentation
- Added sub README.md files under each Python group example to show usage of the "local" and "zenoh" examples
- ReadMe structural changes to have build instructions at the top. Updated contents to include latest additions
- ReadMe now shows local and remote command variants

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
