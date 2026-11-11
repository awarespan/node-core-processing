#!/usr/bin/env python3
"""
[COMPATIBILITY SHIM]
This script has moved to ml_pipeline/training/train_autonomous.py as part of the modular architecture.
Forwarding invocation to ml_pipeline.training.train_autonomous...
"""

import sys
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

print("[AWARESPAN] [DEPRECATED] pi/train_autonomous.py has migrated to ml_pipeline.training.train_autonomous. Forwarding call...", file=sys.stderr)

from ml_pipeline.training.train_autonomous import main

if __name__ == "__main__":
    main()
