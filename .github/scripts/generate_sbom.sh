#!/bin/bash
# Generate complete SBOM by merging cargo-cyclonedx (dependencies) and scancode (source)
# This script runs in ~17 seconds and provides a comprehensive audit trail

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

# Step 2: Generate source code SBOM with scancode (~15 seconds)
echo "[2/6] Generating source code SBOM with scancode..."
if [ ! -f "venv/bin/scancode" ]; then
    echo "Error: scancode not found. Please install: python3 -m venv venv && venv/bin/pip install scancode-toolkit"
    exit 1
fi

# Scan source directories: rust/, python/, and configuration files
venv/bin/scancode -clpieu \
    --cyclonedx source-sbom-raw.json \
    --only-findings \
    rust/ python/ Cargo.toml requirements.txt

echo "✓ Generated source-sbom-raw.json (source code audit)"
echo

# Step 3: Clean scancode output for CycloneDX compatibility
echo "[3/6] Cleaning scancode output..."
python3 << 'EOF'
import json
import sys

# Load scancode output
with open('source-sbom-raw.json', 'r') as f:
    sbom = json.load(f)

# Remove problematic metadata (non-string properties violate CycloneDX spec)
if 'metadata' in sbom and 'properties' in sbom['metadata']:
    sbom['metadata']['properties'] = [
        p for p in sbom['metadata']['properties']
        if isinstance(p.get('value'), str)
    ]

# Save cleaned version
with open('source-sbom.json', 'w') as f:
    json.dump(sbom, f, indent=2)

sys.exit(0)
EOF
echo "✓ Generated source-sbom.json (cleaned)"
echo

# Step 4: Merge both SBOMs using cyclonedx-cli
echo "[4/6] Merging dependency and source SBOMs..."
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

# Step 5: Check license policy
echo "[5/6] Checking license policy compliance..."
python3 .github/scripts/check_license_policy.py sbom.json
POLICY_EXIT=$?
echo

# Step 6: Generate NOTICE file
echo "[6/6] Generating NOTICE file..."
python3 .github/scripts/generate_notice.py sbom.json > NOTICE
echo "✓ Generated NOTICE (third-party attributions)"
echo

# Cleanup temporary files
rm -f source-sbom-raw.json source-sbom.json edgefirst-samples.cdx.json

echo "=================================================="
echo "SBOM Generation Complete"
echo "=================================================="
echo "Files generated:"
echo "  - sbom.json (merged SBOM)"
echo "  - NOTICE (third-party attributions)"
echo

# Exit with license policy check result
exit $POLICY_EXIT
