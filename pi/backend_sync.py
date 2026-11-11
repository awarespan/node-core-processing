#!/usr/bin/env python3
"""
[COMPATIBILITY SHIM]
This script has moved to node_runtime/communications/backend_sync.py as part of the modular architecture.
Forwarding imports to node_runtime.communications.backend_sync...
"""

import sys
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from node_runtime.communications.backend_sync import (
    BackendSync,
    IncidentQueue,
    build_threat_event,
    ThreatEvent,
)
from shared.config.settings import get_settings

settings = get_settings()
NODE_ID = settings.node_id
DEVICE_SECRET = settings.device_secret
BACKEND_API_URL = settings.backend_api_url
BACKEND_API_KEY = settings.backend_api_key
