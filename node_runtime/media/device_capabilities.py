"""Local camera and microphone discovery for capability negotiation."""
from __future__ import annotations

import glob
import os
import subprocess
from typing import Dict, List


def _video_devices() -> List[str]:
    devices = []
    for path in sorted(glob.glob('/dev/video*')):
        if os.path.exists(path) and os.access(path, os.R_OK | os.W_OK):
            devices.append(path)
    return devices


def _capture_devices() -> List[str]:
    """Return ALSA capture PCM devices without confusing playback-only cards."""
    devices: List[str] = []
    try:
        with open('/proc/asound/pcm', encoding='utf-8') as pcm:
            for line in pcm:
                if 'capture' in line.lower():
                    devices.append(line.strip())
    except OSError:
        pass
    if not devices:
        try:
            result = subprocess.run(
                ['arecord', '-l'], capture_output=True, text=True,
                timeout=2, check=False,
            )
            if result.returncode == 0:
                devices = [line.strip() for line in result.stdout.splitlines()
                           if line.strip().startswith('card ')]
        except (OSError, subprocess.SubprocessError):
            pass
    return devices


def detect_media_capabilities() -> Dict[str, object]:
    """Detect physical capture devices; never infer microphone from speaker output."""
    cameras = _video_devices()
    microphones = _capture_devices()
    return {
        'camera_available': bool(cameras),
        'camera_devices': cameras,
        'microphone_available': bool(microphones),
        'microphone_devices': microphones,
    }
