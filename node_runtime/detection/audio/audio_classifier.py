"""
AWARESPAN — Audio Classifier
Interface for acoustic threat detection (screams, gunshots, glass breaking, aggressive noise).

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

from shared.logging.logger import get_logger

log = get_logger("node_runtime.audio_classifier")

AUDIO_THREAT_CLASSES = {
    "gunshot": 0.5,
    "explosion": 0.5,
    "screaming": 0.6,
    "glass_breaking": 0.55,
    "crying": 0.7,
}


@dataclass
class AudioDetection:
    label: str
    confidence: float
    start_time_s: float
    end_time_s: float


class AudioClassifier:
    """Classifies acoustic threat events from audio input."""

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.enabled = False
        log.info("Audio classifier initialized (passive mode)")

    def classify_wav(self, wav_path: str) -> List[AudioDetection]:
        """Classify a recorded WAV audio segment."""
        if not os.path.exists(wav_path):
            log.warning("Audio file not found: %s", wav_path)
            return []

        # Acoustic threat detection interface - extensible for YAMNet/VGGish
        detections: List[AudioDetection] = []
        return detections
