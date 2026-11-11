#!/usr/bin/env python3
"""
[COMPATIBILITY SHIM]
This script has moved to ml_pipeline/evaluation/app_batch.py as part of the modular architecture.
Forwarding imports to ml_pipeline.evaluation.app_batch...
"""

import sys
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from ml_pipeline.evaluation.app_batch import *

if __name__ == "__main__":
    main()
