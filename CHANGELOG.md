# Changelog

All notable changes to EdgeFirst Samples will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial open source release preparation
- Apache-2.0 license headers on all source files
- Comprehensive documentation (README, CONTRIBUTING, ARCHITECTURE, SECURITY)
- SBOM generation and license compliance tooling
- CI/CD workflows for build, lint, and SBOM validation
- Code of Conduct (Contributor Covenant 2.1)
- Pull request templates and issue templates
- cargo-release configuration for version management

### Changed
- Updated to edgefirst-schemas 1.4.0 (Apache-2.0 licensed)
- Migrated from proprietary to open source licensing
- Version bumped from 0.0.0 to 0.1.0 for initial release

### Security
- Established vulnerability reporting process in SECURITY.md
- Added license compliance checking in CI/CD pipeline

## [0.1.0] - TBD

First public release of EdgeFirst Perception Middleware samples.

### Added
- Comprehensive Rust examples for camera, LiDAR, radar, and sensor fusion
- Python examples paralleling Rust functionality
- Camera integration examples (DMA, H.264, info, camera_info)
- LiDAR examples (points, depth, clusters, reflect)
- Radar examples (targets, clusters, cube, info)
- ML inference examples (boxes2d, masks, tracked objects)
- Sensor fusion examples (radar, lidar, 3D boxes, occupancy)
- IMU and GPS examples
- Zenoh-based communication patterns
- Optional Rerun visualization integration
- Support for Linux, Windows, and macOS platforms
- Cross-platform build support in CI/CD

---

## Version History Format

Each release documents changes in these categories:

- **Added**: New features and capabilities
- **Changed**: Changes in existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security vulnerability fixes
