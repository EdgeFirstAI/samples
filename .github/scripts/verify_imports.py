#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""Verify that required packages are installed and importable."""

import sys
import importlib.metadata

def main():
    """Check that edgefirst.schemas and zenoh can be imported."""
    try:
        import edgefirst.schemas as schemas
        print(f"schemas version: {schemas.__version__}")
    except ImportError as e:
        print(f"ERROR: Failed to import edgefirst.schemas: {e}", file=sys.stderr)
        sys.exit(1)
    
    try:
        import zenoh
        zenoh_version = importlib.metadata.version("eclipse-zenoh")
        print(f"zenoh version: {zenoh_version}")
    except ImportError as e:
        print(f"ERROR: Failed to import zenoh: {e}", file=sys.stderr)
        sys.exit(1)
    except importlib.metadata.PackageNotFoundError as e:
        print(f"ERROR: zenoh package metadata not found: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
