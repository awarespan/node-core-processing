#!/usr/bin/env python3
"""
[COMPATIBILITY SHIM]
This script has moved to node_runtime/monitoring/power_monitor.py as part of the modular architecture.
Forwarding invocation to node_runtime.monitoring.power_monitor...
"""

import sys
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

print("[AWARESPAN] [DEPRECATED] pi/power_monitor.py has migrated to node_runtime.monitoring.power_monitor. Forwarding call...", file=sys.stderr)

from node_runtime.monitoring.power_monitor import main

if __name__ == "__main__":
    main()
