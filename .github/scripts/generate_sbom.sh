#!/bin/bash
# Generate complete SBOM by merging cargo-cyclonedx (dependencies) and scancode (source)
# Fast execution (~5-6 seconds) using parent directory scanning to avoid scancode path bugs

set -e  # Exit on error

echo "=================================================="
echo "Generating Complete SBOM"
echo "=================================================="
echo

# Step 1: Generate dependency SBOM with cargo-cyclonedx (~1 second)
echo "[1/6] Generating dependency SBOM with cargo-cyclonedx..."
cargo cyclonedx --format json --all
echo "✓ Generated edgefirst-samples.cdx.json (Rust dependencies)"
echo

# Step 2: Generate source code SBOM with scancode (~5 seconds)
echo "[2/6] Generating source code SBOM with scancode..."
if [ ! -f "venv/bin/scancode" ]; then
    echo "Error: scancode not found. Please install: python3 -m venv venv && venv/bin/pip install scancode-toolkit"
    exit 1
fi

# Workaround for scancode path resolution bugs (GitHub issues #2966, #4459):
# - Scanning from project directory causes recursive traversal into target/ and venv/ (29K+ files)
# - Scanning MULTIPLE paths together triggers inefficient traversal (even just 2-3 paths)
# Solution: Run scancode ONCE PER ASSET from parent directory, then merge with cyclonedx-cli
ORIGINAL_DIR=$(pwd)
PROJECT_NAME=$(basename "$ORIGINAL_DIR")
cd ..

# Scan each source directory separately (each scan takes ~2-3 seconds)
echo "  Scanning Rust sources..."
"$ORIGINAL_DIR/venv/bin/scancode" -clpieu \
    --cyclonedx "$ORIGINAL_DIR/source-rust-raw.json" \
    --only-findings \
    "$PROJECT_NAME/rust/"

echo "  Scanning Python sources..."
"$ORIGINAL_DIR/venv/bin/scancode" -clpieu \
    --cyclonedx "$ORIGINAL_DIR/source-python-raw.json" \
    --only-findings \
    "$PROJECT_NAME/python/"

echo "  Scanning Cargo.toml..."
"$ORIGINAL_DIR/venv/bin/scancode" -clpieu \
    --cyclonedx "$ORIGINAL_DIR/source-cargo-toml-raw.json" \
    --only-findings \
    "$PROJECT_NAME/Cargo.toml"

echo "  Scanning Cargo.lock..."
"$ORIGINAL_DIR/venv/bin/scancode" -clpieu \
    --cyclonedx "$ORIGINAL_DIR/source-cargo-lock-raw.json" \
    --only-findings \
    "$PROJECT_NAME/Cargo.lock"

echo "  Scanning requirements.txt..."
"$ORIGINAL_DIR/venv/bin/scancode" -clpieu \
    --cyclonedx "$ORIGINAL_DIR/source-requirements-raw.json" \
    --only-findings \
    "$PROJECT_NAME/requirements.txt"

# Return to original directory
cd "$ORIGINAL_DIR"

echo "✓ Generated raw source SBOM files"
echo

# Step 3: Clean and convert scancode outputs to CycloneDX
echo "[3/7] Cleaning and converting scancode outputs..."
python3 << 'PYCLEAN'
import json
import subprocess
import sys

# Clean each scancode JSON and convert to CycloneDX
files_to_convert = [
    'source-rust-raw.json',
    'source-python-raw.json',
    'source-cargo-toml-raw.json',
    'source-cargo-lock-raw.json',
    'source-requirements-raw.json'
]

for raw_file in files_to_convert:
    # Read raw scancode output
    with open(raw_file) as f:
        data = json.load(f)
    
    # Convert to CycloneDX using scancode (it has --cyclonedx but we need to re-run or use conversion)
    # For now, save as cleaned JSON (the merge will handle CycloneDX format)
    output_file = raw_file.replace('-raw.json', '.json')
    
    # Clean the metadata properties
    if 'metadata' in data and 'properties' in data['metadata']:
        data['metadata']['properties'] = [
            p for p in data['metadata']['properties']
            if isinstance(p.get('value'), str)
        ]
    
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)

sys.exit(0)
PYCLEAN

echo "✓ Cleaned scancode outputs"
echo

# Step 4: Merge source SBOMs using cyclonedx-cli
echo "[4/7] Merging source SBOMs..."
if ! command -v cyclonedx &> /dev/null; then
    if ! command -v ~/.local/bin/cyclonedx &> /dev/null; then
        echo "Error: cyclonedx CLI not found. Please install from https://github.com/CycloneDX/cyclonedx-cli"
        exit 1
    fi
    CYCLONEDX=~/.local/bin/cyclonedx
else
    CYCLONEDX=cyclonedx
fi

$CYCLONEDX merge \
    --input-files source-rust.json source-python.json source-cargo-toml.json source-cargo-lock.json source-requirements.json \
    --output-file source-sbom.json

# Clean up individual source SBOMs
rm -f source-*-raw.json source-rust.json source-python.json source-cargo-toml.json source-cargo-lock.json source-requirements.json

echo "✓ Merged source SBOMs into source-sbom.json"
echo

# Step 5: Merge dependency and source SBOMs using cyclonedx-cli
echo "[5/7] Merging dependency and source SBOMs..."
if ! command -v cyclonedx &> /dev/null; then
    if ! command -v ~/.local/bin/cyclonedx &> /dev/null; then
        echo "Error: cyclonedx CLI not found. Please install from https://github.com/CycloneDX/cyclonedx-cli"
        exit 1
    fi
    CYCLONEDX=~/.local/bin/cyclonedx
else
    CYCLONEDX=cyclonedx
fi

$CYCLONEDX merge \
    --input-files edgefirst-samples.cdx.json source-sbom.json \
    --output-file sbom.json

echo "✓ Generated sbom.json (merged: dependencies + source)"
echo

# Step 6: Check license policy
echo "[6/7] Checking license policy compliance..."
python3 .github/scripts/check_license_policy.py sbom.json
POLICY_EXIT=$?
echo

# Step 7: Generate NOTICE file
echo "[7/7] Generating NOTICE file..."
python3 .github/scripts/generate_notice.py sbom.json > NOTICE
echo "✓ Generated NOTICE (third-party attributions)"
echo

# Cleanup temporary files
rm -f source-sbom.json edgefirst-samples.cdx.json

echo "=================================================="
echo "SBOM Generation Complete"
echo "=================================================="
echo "Files generated:"
echo "  - sbom.json (merged SBOM)"
echo "  - NOTICE (third-party attributions)"
echo

# Exit with license policy check result
exit $POLICY_EXIT
