#!/usr/bin/env python3
"""
[COMPATIBILITY SHIM]
This script has moved to ml_pipeline/datasets/register_datasets.py as part of the modular architecture.
Forwarding imports to ml_pipeline.datasets.register_datasets...
"""

import sys
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from ml_pipeline.datasets.register_datasets import *

if __name__ == "__main__":
    register_known()
    print_registry_summary()
