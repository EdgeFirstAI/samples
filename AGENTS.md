# AGENTS.md - AI Assistant Development Guidelines

This document provides instructions for AI coding assistants (GitHub Copilot, Cursor, Claude Code, etc.) working on the **EdgeFirst Samples** repository. These guidelines ensure consistent code quality, proper workflow adherence, and maintainable contributions.

**Project:** EdgeFirst Samples (https://github.com/au-zone/edgefirst-samples)  
**Organization:** Au-Zone Technologies  
**Version:** 1.0  
**Last Updated:** November 2025

---

## Table of Contents

1. [Overview](#overview)
2. [Git Workflow](#git-workflow)
3. [Code Quality Standards](#code-quality-standards)
4. [Testing Requirements](#testing-requirements)
5. [Documentation Expectations](#documentation-expectations)
6. [License Policy](#license-policy)
7. [Security Practices](#security-practices)
8. [Project-Specific Guidelines](#project-specific-guidelines)

---

## Overview

Au-Zone Technologies develops edge AI and computer vision solutions for resource-constrained embedded devices. Our software spans:
- Edge AI inference engines and model optimization tools
- Computer vision processing pipelines
- Embedded Linux device drivers and system software
- MLOps platform (EdgeFirst Studio) for model deployment and management
- Open source libraries and tools (Apache-2.0 licensed)

When contributing to Au-Zone projects, AI assistants should prioritize:
- **Resource efficiency**: Memory, CPU, and power consumption matter on embedded devices
- **Code quality**: Maintainability, readability, and adherence to established patterns
- **Testing**: Comprehensive coverage with unit, integration, and edge case tests
- **Documentation**: Clear explanations for complex logic and public APIs
- **License compliance**: Strict adherence to approved open source licenses

---

## Git Workflow

### Branch Naming Convention

**REQUIRED FORMAT**: `<type>/<PROJECTKEY-###>[-optional-description]`

**Branch Types:**
- `feature/` - New features and enhancements
- `bugfix/` - Non-critical bug fixes
- `hotfix/` - Critical production issues requiring immediate fix

**Examples:**
```bash
feature/EDGEAI-123-add-authentication
bugfix/STUDIO-456-fix-memory-leak
hotfix/MAIVIN-789-security-patch

# Minimal format (JIRA key only)
feature/EDGEAI-123
bugfix/STUDIO-456
```

**Rules:**
- JIRA key is REQUIRED (format: `PROJECTKEY-###`)
- Description is OPTIONAL but recommended for clarity
- Use kebab-case for descriptions (lowercase with hyphens)
- Branch from `develop` for features/bugfixes, from `main` for hotfixes

### Commit Message Format

**REQUIRED FORMAT**: `PROJECTKEY-###: Brief description of what was done`

**Rules:**
- Subject line: 50-72 characters ideal
- Focus on WHAT changed, not HOW (implementation details belong in code)
- No type prefixes (`feat:`, `fix:`, etc.) - JIRA provides context
- Optional body: Use bullet points for additional detail

**Examples of Good Commits:**
```bash
EDGEAI-123: Add JWT authentication to user API

STUDIO-456: Fix memory leak in CUDA kernel allocation

MAIVIN-789: Optimize tensor operations for inference
- Implemented tiled memory access pattern
- Reduced memory bandwidth by 40%
- Added benchmarks to verify improvements
```

**Examples of Bad Commits:**
```bash
fix bug                           # Missing JIRA key, too vague
feat(auth): add OAuth2           # Has type prefix (not our convention)
EDGEAI-123                       # Missing description
edgeai-123: update code          # Lowercase key, vague description
```

### Pull Request Process

**Requirements:**
- **2 approvals required** for merging to `main`
- **1 approval required** for merging to `develop`
- All CI/CD checks must pass
- PR title: `PROJECTKEY-### Brief description of changes`
- PR description must link to JIRA ticket

**PR Description Template:**
```markdown
## JIRA Ticket
Link: [PROJECTKEY-###](https://au-zone.atlassian.net/browse/PROJECTKEY-###)

## Changes
Brief summary of what changed and why

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows project conventions
- [ ] Documentation updated
- [ ] No secrets or credentials committed
- [ ] License policy compliance verified
```

**Process:**
1. Create PR via GitHub/Bitbucket web interface
2. Link to JIRA ticket in description
3. Wait for CI/CD to complete successfully
4. Address reviewer feedback through additional commits
5. Obtain required approvals
6. Merge using squash or rebase to keep history clean

### JIRA Integration

While full JIRA details are internal, contributors should know:
- **Branch naming triggers automation**: Creating a branch with format `<type>/PROJECTKEY-###` automatically updates the linked JIRA ticket
- **PR creation triggers status updates**: Opening a PR moves tickets to review status
- **Merge triggers closure**: Merging a PR to main/develop closes the associated ticket
- **Commit messages link to JIRA**: Format `PROJECTKEY-###: Description` creates automatic linkage

**Note**: External contributors without JIRA access can use branch naming like `feature/issue-123-description` referencing GitHub issue numbers instead.

---

## Code Quality Standards

### General Principles

- **Consistency**: Follow existing codebase patterns and conventions
- **Readability**: Code is read more often than written - optimize for comprehension
- **Simplicity**: Prefer simple, straightforward solutions over clever ones
- **Error Handling**: Validate inputs, sanitize outputs, provide actionable error messages
- **Performance**: Consider time/space complexity, especially for edge deployment

### Language-Specific Standards

Follow established conventions for each language:
- **Rust**: Use `cargo fmt` and `cargo clippy`; follow Rust API guidelines
- **Python**: Follow PEP 8; use autopep8 formatter (or project-specified tool); type hints preferred
- **C/C++**: Follow project's .clang-format; use RAII patterns
- **Go**: Use `go fmt`; follow Effective Go guidelines
- **JavaScript/TypeScript**: Use ESLint; Prettier formatter; prefer TypeScript

### Code Quality Tools

**SonarQube Integration:**
- Projects with `sonar-project.properties` must follow SonarQube guidelines
- Verify code quality using:
  - MCP integration for automated checks
  - VSCode SonarLint plugin for real-time feedback
  - SonarCloud reports in CI/CD pipeline
- Address critical and high-severity issues before submitting PR
- Maintain or improve project quality gate scores

### Code Review Checklist

Before submitting code, verify:
- [ ] Code follows project style guidelines (check `.editorconfig`, `CONTRIBUTING.md`)
- [ ] No commented-out code or debug statements
- [ ] Error handling is comprehensive and provides useful messages
- [ ] Complex logic has explanatory comments
- [ ] Public APIs have documentation
- [ ] No hardcoded values that should be configuration
- [ ] Resource cleanup (memory, file handles, connections) is proper
- [ ] No obvious security vulnerabilities (SQL injection, XSS, etc.)
- [ ] SonarQube quality checks pass (if applicable)

### Performance Considerations

For edge AI applications, always consider:
- **Memory footprint**: Minimize allocations; reuse buffers where possible
- **CPU efficiency**: Profile critical paths; optimize hot loops
- **Power consumption**: Reduce wake-ups; batch operations
- **Latency**: Consider real-time requirements for vision processing
- **Hardware acceleration**: Leverage NPU/GPU/DSP when available

---

## Testing Requirements

### Coverage Standards

- **Minimum coverage**: 70% (project-specific thresholds may vary)
- **Critical paths**: 90%+ coverage for core functionality
- **Edge cases**: Explicit tests for boundary conditions
- **Error paths**: Validate error handling and recovery

### Test Types

**Unit Tests:**
- Test individual functions/methods in isolation
- Mock external dependencies
- Fast execution (< 1 second per test suite)
- Use property-based testing where applicable

**Integration Tests:**
- Test component interactions
- Use real dependencies when feasible
- Validate API contracts and data flows
- Test configuration and initialization

**Edge Case Tests:**
- Null/empty inputs
- Boundary values (min, max, overflow)
- Concurrent access and race conditions
- Resource exhaustion scenarios
- Platform-specific behaviors

### Test Organization

**Test layout follows language/framework conventions. Each project should define specific practices.**

**Rust (common pattern):**
```rust
// Unit tests at end of implementation file
// src/module/component.rs
pub fn process_data(input: &[u8]) -> Result<Vec<u8>, Error> {
    // implementation
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_process_data_valid_input() {
        // test implementation
    }
}
```

```
# Integration tests in separate directory
tests/
├── integration_test.rs
└── common/
    └── mod.rs
```

**Python (depends on pytest vs unittest):**
```
# Common patterns - follow project conventions
project/
├── src/
│   └── mypackage/
│       └── module.py
└── tests/
    ├── unit/
    │   └── test_module.py
    └── integration/
        └── test_api_workflow.py
```

**General guidance:**
- Follow common patterns for your language and testing framework
- Consult project's `CONTRIBUTING.md` for specific conventions
- Keep test organization consistent within the project
- Co-locate unit tests or separate - project decides

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make coverage

# Language-specific examples
cargo test --workspace              # Rust
pytest tests/                       # Python with pytest
python -m unittest discover tests/  # Python with unittest
go test ./...                       # Go
```

---

## Documentation Expectations

### Code Documentation

**When to document:**
- Public APIs, functions, and classes (ALWAYS)
- Complex algorithms or non-obvious logic
- Performance considerations or optimization rationale
- Edge cases and error conditions
- Thread safety and concurrency requirements
- Hardware-specific code or platform dependencies

**Documentation style:**
```python
def preprocess_image(image: np.ndarray, target_size: tuple[int, int]) -> np.ndarray:
    """
    Resize and normalize image for model inference.

    Args:
        image: Input image as HWC numpy array (uint8)
        target_size: Target dimensions as (width, height)

    Returns:
        Preprocessed image as CHW float32 array normalized to [0, 1]

    Raises:
        ValueError: If image dimensions are invalid or target_size is negative

    Performance:
        Uses bilinear interpolation. For better quality with 2x cost,
        use bicubic interpolation via config.interpolation = 'bicubic'
    """
```

### Project Documentation

**Essential files for public repositories:**
- `README.md` - Project overview, quick start, documentation links
- `CONTRIBUTING.md` - Development setup, contribution process, coding standards
- `CODE_OF_CONDUCT.md` - Community standards (Contributor Covenant)
- `SECURITY.md` - Vulnerability reporting process
- `LICENSE` - Complete license text (Apache-2.0 for open source)

**Additional documentation:**
- User guides for features and workflows
- API reference documentation
- Migration guides for breaking changes

### Documentation Updates

When modifying code, update corresponding documentation:
- README if user-facing behavior changes
- API docs if function signatures or semantics change
- CHANGELOG for all user-visible changes
- Configuration guides if new options added

---

## License Policy

**CRITICAL**: Au-Zone has strict license policy for all dependencies.

### Allowed Licenses

✅ **Permissive licenses (APPROVED)**:
- MIT
- Apache-2.0
- BSD-2-Clause, BSD-3-Clause
- ISC
- 0BSD
- Unlicense

### Review Required

⚠️ **Weak copyleft (REQUIRES LEGAL REVIEW)**:
- LGPL-2.1-or-later, LGPL-3.0-or-later (if statically linked)

**Note on MPL-2.0:** Moved to ALLOWED licenses. MPL-2.0 is file-level copyleft - acceptable for dependencies as long as we don't modify MPL-2.0 source files. Safe to use libraries with MPL-2.0 license.

### Strictly Disallowed

❌ **NEVER USE THESE LICENSES**:
- GPL (any version)
- AGPL (any version)
- Creative Commons with NC (Non-Commercial) or ND (No Derivatives)
- SSPL (Server Side Public License)
- BSL (Business Source License, before conversion)
- OSL-3.0 (Open Software License)

### Verification Process

**Before adding dependencies:**
1. Check license compatibility with project license (typically Apache-2.0)
2. Verify no GPL/AGPL in dependency tree
3. Review project's SBOM (Software Bill of Materials) if available
4. Document third-party licenses in NOTICE file

**CI/CD will automatically:**
- Generate SBOM using scancode-toolkit
- Validate CycloneDX SBOM schema
- Check for disallowed licenses
- Block PR merges if violations detected

**If you need a library with incompatible license:**
- Search for alternatives with permissive licenses
- Consider implementing functionality yourself
- Escalate to technical leadership for approval (rare exceptions)

---

## Security Practices

### Vulnerability Reporting

**For security issues**, use project's SECURITY.md process:
- Email: `support@au-zone.com` with subject "Security Vulnerability"
- Expected acknowledgment: 48 hours
- Expected assessment: 7 days
- Fix timeline based on severity

### Secure Coding Guidelines

**Input Validation:**
- Validate all external inputs (API requests, file uploads, user input)
- Use allowlists rather than blocklists
- Enforce size/length limits
- Sanitize for appropriate context (HTML, SQL, shell)

**Authentication & Authorization:**
- Never hardcode credentials or API keys
- Use environment variables or secure vaults for secrets
- Implement proper session management
- Follow principle of least privilege

**Data Protection:**
- Encrypt sensitive data at rest and in transit
- Use secure protocols (HTTPS, TLS 1.2+)
- Implement proper key management
- Sanitize logs (no passwords, tokens, PII)

**Common Vulnerabilities to Avoid:**
- SQL Injection: Use parameterized queries
- XSS (Cross-Site Scripting): Escape output, use CSP headers
- CSRF (Cross-Site Request Forgery): Use tokens
- Path Traversal: Validate and sanitize file paths
- Command Injection: Avoid shell execution; use safe APIs
- Buffer Overflows: Use safe string functions; bounds checking

### Dependencies

- Keep dependencies up to date
- Monitor for security advisories
- Use dependency scanning tools (Dependabot, Snyk)
- Audit new dependencies before adding

---

## Project-Specific Guidelines

This section should be customized per repository. Common customizations:

## Project-Specific Guidelines

This section is customized for the **EdgeFirst Samples** repository.

### Technology Stack

**Languages:**
- **Rust**: 2024 edition (primary language for examples)
- **Python**: 3.8+ (alternative examples for rapid prototyping)

**Build System:**
- **Cargo**: Rust workspace with multiple binary crates
- **Python**: Standard pip/venv setup

**Key Dependencies:**
- **Zenoh**: 1.3.4 - High-performance pub/sub middleware for sensor data
- **Rerun**: 0.27.2 - Optional visualization framework (feature flag)
- **edgefirst-schemas**: 1.4.0 - Message type definitions (Apache-2.0)
- **ROS2 CDR**: Message serialization format

**Supported Platforms:**
- **Linux**: Primary target (kernel 5.10+)
- **Windows**: Remote client applications
- **macOS**: Remote client applications
- **Tested on**: x86_64, aarch64

### Repository Purpose

This repository provides **sample applications** demonstrating EdgeFirst Perception Middleware:
- Sensor data subscription examples (camera, LiDAR, radar, IMU, GPS)
- Multi-sensor fusion examples
- ML inference result visualization
- Zenoh communication patterns
- Optional Rerun integration for data visualization

**Target Audience:**
- Developers learning EdgeFirst Perception
- Platform integrators building edge AI systems
- Engineers evaluating EdgeFirst for projects

### Architecture

**Workspace Structure:**
```
rust/               # Rust examples (binary crates)
├── lib.rs         # Shared library (CLI args, Zenoh config)
├── camera/        # Camera examples (DMA, H.264, info)
├── lidar/         # LiDAR examples (points, depth, clusters)
├── radar/         # Radar examples (targets, clusters, cube)
├── model/         # ML inference examples (boxes, masks)
├── fusion/        # Sensor fusion examples
└── combined/      # Multi-sensor examples

python/            # Python examples (parallel structure)
```

**Communication Pattern:**
- All examples use **Zenoh pub/sub** for sensor data
- Topics follow `rt/<sensor>/<message_type>` naming convention
- Messages serialized with ROS2 CDR format
- Autodiscovery on local EdgeFirst platforms (Maivin, Raivin)
- Remote connections via `--remote <IP:PORT>` argument

### Code Style

**Rust:**
- Use `rustfmt` for formatting (required before commit)
- Use `clippy` for linting: `cargo clippy -- -D warnings`
- Follow Rust API Guidelines: https://rust-lang.github.io/api-guidelines/
- Error handling: Prefer `anyhow::Result` for applications
- Async runtime: Use `tokio` with `#[tokio::main]`

**Python:**
- Use `black` for formatting (88 character line length)
- Use `flake8` for linting
- Follow PEP 8: https://peps.python.org/pep-0008/
- Type hints recommended for public functions

**SPDX Headers (REQUIRED):**

All source files must include SPDX license headers:

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

### Zenoh Communication Patterns

**Session Creation:**
```rust
use zenoh::config::{Config, WhatAmI};

let mut config = if args.remote.is_empty() {
    Config::default()  // Autodiscovery
} else {
    let mut config = Config::default();
    config.connect.endpoints = vec![args.remote.parse()?];
    config.scouting.multicast.set_enabled(Some(false))?;
    config
};

config.set_mode(Some(WhatAmI::Client))?;
let session = zenoh::open(config).await?;
```

**Subscriber Pattern:**
```rust
let subscriber = session
    .declare_subscriber(&args.topic)
    .callback(|sample| {
        let msg: MessageType = cdr::deserialize(&sample.payload().to_bytes()).unwrap();
        process_message(msg);
    })
    .await?;

tokio::signal::ctrl_c().await?;
```

**Topic Naming:**
- Use format: `rt/<sensor>/<message_type>`
- Examples: `rt/camera/image`, `rt/lidar/points`, `rt/model/boxes2d`
- Prefix `rt/` = "real-time"

### Message Schemas

**Using edgefirst-schemas:**
```rust
use edgefirst_schemas::{CompressedImage, PointCloud2, BoundingBox2DArray};
use cdr::{CdrLe, Infinite};

// Deserialize
let msg: CompressedImage = cdr::deserialize_from(
    &*sample.payload().to_bytes(),
    cdr::size::Infinite,
)?;
```

**Common message types:**
- Camera: `Image`, `CompressedImage`, `DmaBuf`, `CameraInfo`
- LiDAR: `PointCloud2`, `LaserScan`
- Radar: `RadarTarget`, `RadarCluster`, `RadarCube`
- ML: `BoundingBox2D`, `BoundingBox2DArray`, `Mask`
- Fusion: `BoundingBox3D`, `OccupancyGrid`
- Navigation: `Imu`, `NavSatFix` (GPS)

### Rerun Integration

**Feature Flag Pattern:**
```toml
[dependencies]
rerun = { version = "0.27.2", optional = true }

[features]
default = []
rerun = ["dep:rerun"]
```

**Usage:**
```rust
#[cfg(feature = "rerun")]
{
    let rec = rerun::RecordingStreamBuilder::new("edgefirst-sample").spawn()?;
    rec.log("camera/image", &rerun::Image::new(data, [h, w]))?;
}
```

**Build with Rerun:**
```bash
cargo build --features rerun --release
```

### Error Handling

**Pattern:**
```rust
use anyhow::{Context, Result};

fn main() -> Result<()> {
    let session = zenoh::open(config)
        .await
        .context("Failed to open Zenoh session")?;
    Ok(())
}
```

**Guidelines:**
- Use `anyhow::Result` for application code
- Use `.context()` for error context
- Avoid bare `.unwrap()` - use `.expect()` with message or proper error handling
- Handle Ctrl+C gracefully: `tokio::signal::ctrl_c().await?`

### Common Pitfalls

**Zenoh Multicast:**
- Default config uses multicast for local discovery
- Disable for remote connections: `config.scouting.multicast.set_enabled(Some(false))`
- Use `--remote` argument pattern from `lib.rs`

**DMA Buffers (Linux-only):**
- Mark with `#[cfg(target_os = "linux")]`
- Use file descriptor carefully (lifetime management)
- Examples: `rust/camera/dma.rs`

**Platform-Specific Code:**
- Use `#[cfg(target_os = "linux")]` for Linux-only features
- Provide graceful degradation for other platforms
- Document hardware requirements

### Testing Conventions

**Testing approach for sample code:**
- Unit tests: Not applicable - samples demonstrate client integration
- Integration tests: Manual testing against running EdgeFirst Perception instance
- Test platforms: x86_64 and aarch64 Linux, Windows and macOS clients
- Manual testing checklist in CONTRIBUTING.md

**Quality verification:**
- Build verification: `cargo build --all-targets` must succeed
- Lint compliance: `cargo clippy -- -D warnings` must pass
- SBOM compliance: `.github/scripts/generate_sbom.sh` must complete without license violations
- Platform testing: Verify on Linux (primary), Windows and macOS (client apps)

**When adding tests:**
- Unit tests: Co-locate with implementation or separate `tests/` directory
- Use `#[cfg(test)]` for Rust unit tests
- Mock Zenoh sessions for testing (avoid real network I/O)

### Performance Considerations

**Resource Efficiency:**
- Target: Edge devices with limited resources
- Minimize allocations in message processing loops
- Reuse buffers where possible
- Use `Vec::with_capacity()` for known sizes

**Zero-Copy Patterns:**
- DMA buffers: See `camera/dma.rs` example
- Avoid copying image/point cloud data when possible

**Profiling:**
- Optional Tracy integration: `cargo build --features tracy`
- Use `cargo flamegraph` for performance analysis

### Documentation Standards

**Code Comments:**
- Document public APIs with doc comments (`///`)
- Explain non-obvious logic or EdgeFirst-specific patterns
- Document hardware dependencies and platform requirements

**README Updates:**
- Avoid specific counts (use "comprehensive examples" not "28 examples")
- Focus on supported OS (Linux, Windows, macOS) not architectures
- Don't reference TODO.md or STATUS.md (internal tracking only)
- Keep directory structures concise

**Adding New Examples:**
1. Create binary in appropriate `rust/<category>/` directory
2. Add parallel Python example in `python/<category>/`
3. Update `Cargo.toml` with new `[[bin]]` entry
4. Add SPDX headers to new files
5. Document usage in README (keep concise)
6. Follow existing patterns (see `lib.rs` for shared code)

### Remote vs. Local Execution

**Important:**
- Samples autodiscover topics on EdgeFirst platforms (Maivin, Raivin)
- Remote connections require `--remote <IP:PORT>` argument
- Document this in examples: see README Quick Start section

**Example:**
```bash
# Local (autodiscovery)
cargo run --bin list-topics

# Remote
cargo run --bin list-topics -- --remote 192.168.1.100:7447
```

---

## Working with AI Assistants

### For GitHub Copilot / Cursor

These tools provide inline suggestions. Ensure:
- Suggestions match project conventions (run linters after accepting)
- Complex logic has explanatory comments
- Generated tests have meaningful assertions
- Security best practices are followed

### For Claude Code / Chat-Based Assistants

When working with conversational AI:
1. **Provide context**: Share relevant files, error messages, and requirements
2. **Verify outputs**: Review generated code critically before committing
3. **Iterate**: Refine solutions through follow-up questions
4. **Document decisions**: Capture architectural choices and tradeoffs
5. **Test thoroughly**: AI-generated code needs human verification

### Common AI Assistant Pitfalls

- **Hallucinated APIs**: Verify library functions exist before using
- **Outdated patterns**: Check if suggestions match current best practices
- **Over-engineering**: Prefer simple solutions over complex ones
- **Missing edge cases**: Explicitly test boundary conditions
- **License violations**: AI may suggest code with incompatible licenses

---

## Workflow Example

**Adding a new sensor example:**

```bash
# 1. Create branch
git checkout -b feature/EDGEAI-456-add-temperature-sensor

# 2. Create Rust example
cat > rust/temperature.rs << 'EOF'
// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use anyhow::Result;
use edgefirst_samples::Args;
use edgefirst_schemas::Temperature;
use clap::Parser;

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();
    let config = edgefirst_samples::create_config(&args)?;
    let session = zenoh::open(config).await?;
    
    let subscriber = session
        .declare_subscriber(&args.topic)
        .callback(|sample| {
            let msg: Temperature = cdr::deserialize(&sample.payload().to_bytes()).unwrap();
            println!("Temperature: {:.2}°C", msg.celsius);
        })
        .await?;
    
    tokio::signal::ctrl_c().await?;
    Ok(())
}
EOF

# 3. Create parallel Python example
cat > python/temperature.py << 'EOF'
# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

from edgefirst_schemas import Temperature
import zenoh
import cdr

# Implementation...
EOF

# 4. Update Cargo.toml
# Add [[bin]] entry for new example

# 5. Format and lint
cargo fmt
cargo clippy -- -D warnings
black python/

# 6. Test build
cargo build --release
python python/temperature.py --help

# 7. Commit
git add rust/temperature.rs python/temperature.py Cargo.toml
git commit -m "EDGEAI-456: Add temperature sensor example

- Added Rust and Python examples for temperature sensor
- Follows rt/temperature/data topic convention
- Tested on x86_64 and aarch64"

# 8. Push and create PR
git push -u origin feature/EDGEAI-456-add-temperature-sensor
```

---

## Getting Help

**For development questions:**
- Check project's `CONTRIBUTING.md` for setup instructions
- Review existing code for patterns and conventions
- Search GitHub Issues for similar problems
- Ask in GitHub Discussions (for public repos)

**For security concerns:**
- Email `support@au-zone.com` with subject "Security Vulnerability"
- Do not disclose vulnerabilities publicly

**For license questions:**
- Review license policy section above
- Check project's `LICENSE` file
- Contact technical leadership if unclear

**For contribution guidelines:**
- Read project's `CONTRIBUTING.md`
- Review recent merged PRs for examples
- Follow PR template and checklist

---

## Document Maintenance

**Project maintainers should:**
- Update [Project-Specific Guidelines](#project-specific-guidelines) with repository details
- Add technology stack, architecture patterns, and performance targets
- Document build/test/deployment procedures specific to the project
- Specify testing conventions (unit test location, framework choice, etc.)
- Keep examples and code snippets current
- Review and update annually or when major changes occur

**This template version**: 1.0 (November 2025)
**Organization**: Au-Zone Technologies
**License**: Apache-2.0 (for open source projects)

---

*This document helps AI assistants contribute effectively to Au-Zone projects while maintaining quality, security, and consistency. For questions or suggestions, contact `support@au-zone.com`.*

### Understanding MPL-2.0

**Mozilla Public License 2.0 is ALLOWED for dependencies** because:

1. **File-level copyleft**: Only applies to the specific MPL-2.0 files, not entire codebase
2. **Linkage freedom**: Can link with code under any license (even proprietary)
3. **Safe usage pattern**: As long as we:
   - Use as external dependency (via Cargo.toml)
   - Don't copy/modify MPL-2.0 source files
   - Don't distribute modified versions of MPL-2.0 code

**When MPL-2.0 requires caution:**
- ❌ Copying code from MPL-2.0 files into our codebase
- ❌ Modifying MPL-2.0 source files directly
- ❌ Creating derivative works of MPL-2.0 code

**Acceptable use:**
- ✅ Using MPL-2.0 crates as dependencies
- ✅ Linking against MPL-2.0 libraries
- ✅ Distributing binaries that use MPL-2.0 dependencies
