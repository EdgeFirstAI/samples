# Changelog

All notable changes to EdgeFirst Samples will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.2] - 2025-11-19

## [0.1.1] - 2025-11-19

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
