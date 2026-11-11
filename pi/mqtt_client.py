#!/usr/bin/env python3
"""
[COMPATIBILITY SHIM]
This script has moved to node_runtime/communications/mqtt_client.py as part of the modular architecture.
Forwarding imports to node_runtime.communications.mqtt_client...
"""

import sys
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from node_runtime.communications.mqtt_client import (
    PiMqttClient,
    get_mqtt_client,
    init_mqtt,
)
