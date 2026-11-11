#!/usr/bin/env python3
"""
[COMPATIBILITY SHIM]
This script has moved to node_runtime/communications/event_queue.py as part of the modular architecture.
Forwarding imports to node_runtime.communications.event_queue...
"""

import sys
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from node_runtime.communications.event_queue import (
    EventQueueManager,
    start_event_queue as start,
    stop_event_queue as stop,
    enqueue_event,
)
