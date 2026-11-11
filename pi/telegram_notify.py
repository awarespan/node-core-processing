#!/usr/bin/env python3
"""
[COMPATIBILITY SHIM]
This script has moved to node_runtime/monitoring/telegram_notify.py as part of the modular architecture.
Forwarding invocation to node_runtime.monitoring.telegram_notify...
"""

import sys
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from node_runtime.monitoring.telegram_notify import send_message, main

# Compatibility export
def send_telegram(text: str, chat_id=None):
    return send_message(text, chat_id=chat_id)

def format_progress_message():
    return "AWARESPAN Node Core is active."

if __name__ == "__main__":
    main()
