#!/usr/bin/env python3
"""
[COMPATIBILITY SHIM]
This script has moved to node_runtime/monitoring/telegram_bot.py as part of the modular architecture.
Forwarding invocation to node_runtime.monitoring.telegram_bot...
"""

import sys
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

print("[AWARESPAN] [DEPRECATED] pi/telegram_bot.py has migrated to node_runtime.monitoring.telegram_bot. Forwarding call...", file=sys.stderr)

from node_runtime.monitoring.telegram_bot import main

if __name__ == "__main__":
    main()
