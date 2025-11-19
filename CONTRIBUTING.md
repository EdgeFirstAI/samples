# Contributing to EdgeFirst Samples

Thank you for your interest in contributing to EdgeFirst Samples! This document provides guidelines and instructions for contributing to this project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Ways to Contribute](#ways-to-contribute)
- [Development Setup](#development-setup)
- [Building the Project](#building-the-project)
- [Testing](#testing)
- [Contribution Process](#contribution-process)
- [Code Style](#code-style)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [License](#license)

---

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to support@au-zone.com.

---

## Ways to Contribute

There are many ways to contribute to EdgeFirst Samples:

### 🐛 Report Bugs

- Use GitHub Issues to report bugs
- Check if the bug has already been reported
- Include detailed steps to reproduce
- Provide system information (OS, Rust version, hardware)
- Include relevant error messages and logs

### ✨ Suggest Features

- Use GitHub Issues or Discussions for feature requests
- Explain the use case and benefits
- Provide examples if possible
- Consider whether it fits the project's scope

### 📝 Improve Documentation

- Fix typos and clarify existing documentation
- Add examples and tutorials
- Improve code comments
- Write guides for common use cases

### 💻 Contribute Code

- Fix bugs
- Implement new features
- Add new sensor examples
- Improve performance
- Add test coverage

### 🧪 Test and Provide Feedback

- Test on different platforms (x86_64, ARM, RISC-V)
- Try examples with different hardware
- Report edge cases and unexpected behavior
- Provide feedback on documentation clarity

---

## Development Setup

### Prerequisites

**Rust:**
```bash
# Install rustup (if not already installed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Update to latest stable
rustup update stable

# Verify installation
rustc --version
cargo --version
```

**Python (for Python examples):**
```bash
# Python 3.8 or later required
python3 --version

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**System Dependencies:**

For Debian/Ubuntu:
```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    pkg-config \
    libssl-dev \
    cmake
```

### Clone the Repository

```bash
git clone https://github.com/EdgeFirstAI/samples.git
cd samples
```

### Cross-Compilation Setup (Optional)

For ARM64 (aarch64) cross-compilation:

```bash
# Install cross
cargo install cross

# Or use cross-rs
rustup target add aarch64-unknown-linux-gnu

# Install cross-compilation toolchain
sudo apt-get install gcc-aarch64-linux-gnu
```

### Zenoh Setup

EdgeFirst Samples uses Zenoh for middleware communication. The Zenoh dependency is managed through Cargo, but for testing you may want to run a Zenoh router:

```bash
# Download and run Zenoh router (optional, for advanced testing)
# See: https://zenoh.io/docs/getting-started/quick-test/
```

---

## Building the Project

### Build All Examples (Rust)

```bash
# Debug build
cargo build

# Release build (optimized)
cargo build --release

# Build specific binary
cargo build --bin camera-dma --release
```

### Build with Rerun Visualization

```bash
# Rerun is an optional feature
cargo build --features rerun --release
```

### Run Examples

```bash
# List available examples
cargo run --bin list-topics

# Run specific example
cargo run --bin camera-dma --release

# Run with arguments
cargo run --bin camera-info -- --help
```

### Python Examples

```bash
# Activate virtual environment first
source venv/bin/activate

# Run Python example
python python/camera/dma.py --help
```

### Format Code

```bash
# Rust
cargo fmt

# Python
black python/
```

### Lint Code

```bash
# Rust
cargo clippy -- -D warnings

# Python
flake8 python/
```

---

## Testing

### Manual Testing

Since this repository provides sample applications demonstrating EdgeFirst Perception integration, testing is primarily done through integration testing as part of the EdgeFirst Perception test suite.

All samples should be manually tested to ensure they:
- Build successfully on supported platforms (Linux, Windows, macOS)
- Connect properly to EdgeFirst Perception (both local and remote)
- Handle topics and data streams correctly
- Display appropriate error messages
- Clean up resources properly

### Testing Checklist

When contributing or reviewing samples:

- [ ] Sample builds without errors on test platforms (x86_64, aarch64)
- [ ] Runtime dependencies are documented
- [ ] Connection parameters work as expected (local autodiscovery and --remote)
- [ ] Error cases are handled gracefully
- [ ] Documentation matches actual behavior
- [ ] Code follows project conventions
- [ ] SBOM generation succeeds without license violations

### Platform Testing

Samples are tested on:
- **Linux**: Primary platform (x86_64, aarch64)
- **Windows**: Client applications
- **macOS**: Client applications

For hardware-specific features, document requirements clearly in the sample's documentation.

---

## Contribution Process

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR-USERNAME/edgefirst-samples.git
cd edgefirst-samples
git remote add upstream https://github.com/EdgeFirstAI/samples.git
```

### 2. Create a Feature Branch

```bash
# Update your local main branch
git checkout main
git pull upstream main

# Create a feature branch
git checkout -b feature/your-feature-name
# Or for bugfixes:
git checkout -b bugfix/issue-number-description
```

**Branch Naming Convention:**
- `feature/description` - New features and enhancements
- `bugfix/description` - Bug fixes
- `docs/description` - Documentation changes
- `refactor/description` - Code refactoring
- `test/description` - Test additions/improvements

### 3. Make Your Changes

- Write clear, maintainable code
- Follow the code style guidelines (see below)
- Add or update tests as needed
- Update documentation for user-facing changes
- Add SPDX license headers to new files (see below)

### 4. Test Your Changes

```bash
# Format code
cargo fmt
black python/

# Lint
cargo clippy -- -D warnings
flake8 python/

# Build all samples
cargo build --all-targets

# Generate SBOM and check license compliance
.github/scripts/generate_sbom.sh
python3 .github/scripts/check_license_policy.py sbom.json

# Test on target platform if applicable
```

### 5. Commit Your Changes

See [Commit Messages](#commit-messages) section below.

### 6. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

---

## Code Style

### Rust

**Follow Rust style guidelines:**
- Use `cargo fmt` for automatic formatting
- Use `cargo clippy` for linting
- Follow [Rust API Guidelines](https://rust-lang.github.io/api-guidelines/)

**Specific conventions:**
- Use `rustfmt.toml` configuration (if present)
- Prefer explicit error handling with `Result` types
- Use `unwrap()` only when failure is impossible (document why)
- Prefer `expect()` with clear messages over `unwrap()`
- Document all public APIs with doc comments (`///`)

**Example:**
```rust
// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

/// Processes camera frames from DMA buffers.
///
/// # Arguments
///
/// * `buffer` - Raw DMA buffer containing image data
/// * `format` - Pixel format of the image
///
/// # Returns
///
/// Processed image data or error if processing fails
pub fn process_dma_frame(buffer: &[u8], format: PixelFormat) -> Result<Image, Error> {
    // Implementation
}
```

### Python

**Follow Python style guidelines:**
- Use `black` for automatic formatting
- Use `flake8` for linting
- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use type hints where helpful

**Specific conventions:**
- Line length: 88 characters (black default)
- Use double quotes for strings
- Use descriptive variable names
- Add docstrings to all public functions/classes

**Example:**
```python
# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

from typing import Optional

def process_camera_frame(
    data: bytes, width: int, height: int, format: str
) -> Optional[Image]:
    """
    Process camera frame data.

    Args:
        data: Raw image data bytes
        width: Image width in pixels
        height: Image height in pixels
        format: Pixel format string (e.g., 'RGB8', 'YUV420')

    Returns:
        Processed image or None if processing fails
    """
    # Implementation
```

### SPDX License Headers

**All new source files MUST include SPDX headers:**

**Rust files:**
```rust
// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.
```

**Python files:**
```python
# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.
```

These headers must be the first lines of the file (after shebang in Python if present).

### Zenoh Patterns

When working with Zenoh communication:

**Session creation:**
```rust
let config = Config::from_file("zenoh-config.json5")?;
let session = zenoh::open(config).await?;
```

**Subscriber pattern:**
```rust
let subscriber = session
    .declare_subscriber("rt/camera/image")
    .callback(|sample| {
        // Handle sample
    })
    .await?;
```

**Topic naming:**
- Use format: `rt/<sensor>/<message_type>`
- Examples: `rt/camera/image`, `rt/lidar/points`, `rt/radar/targets`

---

## Commit Messages

### Format

```
Brief description of what changed (50-72 characters)

Optional detailed explanation:
- Use bullet points for multiple changes
- Explain what and why, not how
- Reference issues: Fixes #123, Related to #456
```

### Guidelines

- **Subject line:**
  - Keep under 72 characters (50 ideal)
  - Use imperative mood ("Add feature" not "Added feature")
  - Capitalize first word
  - No period at the end
  - Be specific and descriptive

- **Body (optional):**
  - Wrap at 72 characters
  - Explain what and why, not how
  - Separate from subject with blank line
  - Use bullet points for multiple items

- **Footer (optional):**
  - Reference related issues
  - Breaking changes: `BREAKING CHANGE: description`
  - Closes issues: `Fixes #123` or `Closes #456`

### Examples

**Good commits:**
```
Add H.264 camera streaming example

Implements camera streaming with H.264 compression:
- Added h264.rs example for Rust
- Added h264.py example for Python
- Documented codec parameters
- Tested on Maivin platform

Fixes #42
```

```
Fix memory leak in DMA buffer handling

DMA buffers were not being released after processing, causing
memory exhaustion on long-running processes.

Updated buffer lifecycle to properly release resources in Drop
implementation.

Fixes #67
```

**Bad commits:**
```
fix bug                    # Too vague
Update code                # Not descriptive
feat: add stuff            # Unclear what was added
Fixed the camera thing.    # Unprofessional, vague
```

---

## Pull Request Process

### Before Submitting

- [ ] Code builds without errors (`cargo build`)
- [ ] Code is formatted (`cargo fmt`, `black python/`)
- [ ] Linting passes (`cargo clippy`, `flake8`)
- [ ] Tests pass (when tests exist: `cargo test`)
- [ ] SPDX headers added to all new files
- [ ] Documentation updated (README, code comments, etc.)
- [ ] Commit messages follow guidelines
- [ ] Changes are focused and atomic (one feature/fix per PR)

### PR Title

Use a clear, descriptive title:
- "Add support for JPEG camera compression"
- "Fix race condition in Zenoh subscriber"
- "Improve documentation for radar examples"

### PR Description

Use this template:

```markdown
## Description
Brief summary of changes and motivation.

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature causing existing functionality to change)
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring

## Testing
Describe how you tested your changes:
- [ ] Tested on x86_64 Linux
- [ ] Tested on ARM64 platform
- [ ] Tested with actual hardware (specify which)
- [ ] Added/updated unit tests
- [ ] Added/updated integration tests

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Code commented where necessary
- [ ] Documentation updated
- [ ] No new warnings introduced
- [ ] SPDX headers added to new files
- [ ] Cargo.lock updated (if dependencies changed)

## Related Issues
Fixes #(issue number)
Related to #(issue number)

## Screenshots/Logs (if applicable)
Add relevant screenshots or logs demonstrating the change.
```

### Review Process

1. **Automated Checks:** CI/CD will run builds, lints, and tests
2. **Code Review:** Maintainers will review your code
3. **Feedback:** Address any requested changes
4. **Approval:** Once approved, a maintainer will merge
5. **Merge:** PRs are typically merged using squash or rebase

### Approval Requirements

- **All CI/CD checks must pass**
- **At least 1 approval** from a maintainer
- **No unresolved conversations**
- **Conflicts resolved** with main branch

---

## Release Process

**For Project Maintainers Only**

EdgeFirst Samples follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html) and uses cargo-release for version management.

### Version Management

Versions follow the format `MAJOR.MINOR.PATCH`:
- **MAJOR**: Breaking changes (rare for samples repo)
- **MINOR**: New samples, features, or significant improvements
- **PATCH**: Bug fixes, documentation updates, small improvements

### Release Steps

1. **Ensure clean state**:
   ```bash
   git checkout main
   git pull origin main
   git status  # Should be clean
   ```

2. **Update CHANGELOG.md**:
   - Move items from `[Unreleased]` to new version section
   - Add release date
   - Commit: `git commit -m "Update CHANGELOG for vX.Y.Z release"`

3. **Create release with cargo-release**:
   ```bash
   # For minor release (new features)
   cargo release minor --execute
   
   # For patch release (bug fixes)
   cargo release patch --execute
   
   # For major release (breaking changes)
   cargo release major --execute
   ```

   This will:
   - Update version in `Cargo.toml`
   - Update `CHANGELOG.md` placeholders
   - Create git tag `vX.Y.Z`
   - Push changes and tag to origin

4. **Verify release**:
   - Check that tag was created: `git tag -l`
   - Verify GitHub Actions completed successfully
   - Confirm CHANGELOG looks correct

### Pre-Release Checklist

Before creating a release, verify:

- [ ] All tests pass (`cargo test --workspace`)
- [ ] All examples build (`cargo build --release --all-targets`)
- [ ] Documentation is up-to-date
- [ ] CHANGELOG.md has all changes since last release
- [ ] No uncommitted changes (`git status` clean)
- [ ] On `main` branch with latest changes pulled
- [ ] SBOM generation passes without license violations
- [ ] CI/CD workflows are green

### Manual Version Tagging (Alternative)

If not using cargo-release:

```bash
# Update version in Cargo.toml manually
# Update CHANGELOG.md manually
git add Cargo.toml CHANGELOG.md
git commit -m "Release version 0.2.0"
git tag -a v0.2.0 -m "Release version 0.2.0"
git push origin main --tags
```

### Release Notes

After pushing the tag, GitHub Actions automatically:
1. Builds release binaries for all supported platforms:
   - Linux (x86_64, aarch64)
   - macOS (x86_64, aarch64/Apple Silicon)
   - Windows (x86_64)
2. Creates ZIP archives containing all compiled binaries
3. Generates GitHub Release with changelog from CHANGELOG.md
4. Attaches all platform-specific ZIP files as release assets

The automated release workflow is triggered by tags matching `v*.*.*` pattern.

**Manual steps (if needed):**
- Edit release notes at https://github.com/EdgeFirstAI/samples/releases
- Mark as pre-release if it contains `alpha`, `beta`, or `rc`
- Add migration notes or breaking change warnings

---

## License

By contributing to EdgeFirst Samples, you agree that your contributions will be licensed under the **Apache License 2.0**.

All contributions must:
- Be your original work or properly attributed
- Not contain code from GPL/AGPL licensed projects
- Include appropriate SPDX license headers
- Comply with the project's [license policy](AGENTS.md#license-policy)

### Allowed Dependency Licenses

When adding new dependencies, ensure they use compatible licenses:

✅ **Allowed:**
- MIT, MIT-0, Apache-2.0
- BSD-2-Clause, BSD-3-Clause, ISC, 0BSD, Unlicense
- Zlib, BSL-1.0, CC0-1.0
- MPL-2.0 (file-level copyleft, safe as dependency)

❌ **Not Allowed:**
- GPL, AGPL, proprietary licenses without approval
- CC-BY-NC, CC-BY-ND (non-commercial, no-derivatives)
- SSPL, BSL

See [AGENTS.md](AGENTS.md#license-policy) for complete license policy.

### Adding New Dependencies

When adding dependencies to `Cargo.toml` or `requirements.txt`:

1. **Check License Compatibility** (see Allowed Dependency Licenses above)

2. **Update Lock Files**
   ```bash
   # Rust - update Cargo.lock
   cargo build
   git add Cargo.lock
   
   # Python - update requirements.txt if using pip-tools
   pip-compile requirements.in
   git add requirements.txt
   ```

3. **Regenerate SBOM and NOTICE**
   ```bash
   # Generate complete SBOM and updated NOTICE
   bash .github/scripts/generate_sbom.sh
   
   # Review the updated NOTICE file
   git diff NOTICE
   
   # Commit if changes are present
   git add NOTICE sbom.json
   ```

4. **Verify License Policy**
   ```bash
   # Check for license violations
   python3 .github/scripts/check_license_policy.py sbom.json
   ```

5. **Include in Commit**
   - Commit `Cargo.lock` and/or `requirements.txt`
   - Commit updated `NOTICE` and `sbom.json` files
   - Reference NOTICE update in commit message

**Example commit message:**
```
Add opencv-rust for image processing example

- Added opencv 0.88 (MIT license)
- Updated Cargo.lock and NOTICE file
- All dependencies pass license policy check
```

### Cargo.lock Policy

**This is a binary project, so Cargo.lock is committed to the repository.**

When your changes update dependencies:
- Run `cargo build` to update Cargo.lock
- Commit the updated Cargo.lock with your changes
- This ensures reproducible builds and accurate SBOM generation

---

## Additional Resources

### Documentation

- **EdgeFirst Documentation:** https://doc.edgefirst.ai/develop/perception/dev/
- **EdgeFirst Platforms:** https://doc.edgefirst.ai/develop/platforms/
- **EdgeFirst Studio:** https://doc.edgefirst.ai/test/perception/
- **Zenoh Documentation:** https://zenoh.io/docs/
- **Rerun Documentation:** https://rerun.io/docs

### Community

- **GitHub Discussions:** Ask questions and share ideas
- **GitHub Issues:** Report bugs and request features
- **Email:** support@au-zone.com for general inquiries

### Getting Help

If you need help contributing:

1. Check existing documentation and issues
2. Search GitHub Discussions
3. Ask in GitHub Discussions (preferred for public questions)
4. Email support@au-zone.com for private inquiries

---

## Recognition

We value all contributions! Contributors will be:

- Listed in release notes for their contributions
- Acknowledged in the project's Git history
- Credited in any related blog posts or announcements (with permission)

Thank you for helping make EdgeFirst Samples better! 🚀

---

**Last Updated:** 2025-11-18  
**Version:** 1.0
