"""
AWARESPAN — Multi-Modal Classifier
Integrates visual inference, acoustic classifications, and physical sensor triggers.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

from typing import List, Optional

from shared.logging.logger import get_logger
from shared.models.events import Detection
from node_runtime.detection.audio.audio_classifier import AudioDetection
from node_runtime.detection.sensors.hardware import SensorReading
from node_runtime.processing.threat_assessment import ThreatAssessor, ThreatAssessment

log = get_logger("node_runtime.classifier")


class MultiModalClassifier:
    """Combines multi-modal inputs into a coherent threat assessment."""

    def __init__(self, assessor: Optional[ThreatAssessor] = None):
        self.assessor = assessor or ThreatAssessor()

    def process_frame(
        self,
        visual_detections: List[Detection],
        audio_detections: Optional[List[AudioDetection]] = None,
        sensor_reading: Optional[SensorReading] = None,
    ) -> ThreatAssessment:
        """
        Evaluate multimodal inputs. Visual weapon detections take primary precedence.
        Acoustic gunshot or scream boosts threat priority.
        """
        assessment = self.assessor.evaluate(visual_detections)

        # Acoustic sensor fusion
        if audio_detections:
            for ad in audio_detections:
                if ad.label in ("gunshot", "explosion") and ad.confidence >= 0.5:
                    assessment.tier = "tier2"
                    assessment.threat_level = "CRITICAL"
                    if ad.label not in assessment.labels:
                        assessment.labels.append(ad.label)

        # Physical sensor fusion (tamper trigger)
        if sensor_reading and sensor_reading.tamper_active:
            if assessment.tier == "none":
                assessment.tier = "tier1"
                assessment.threat_level = "MEDIUM"
                assessment.labels.append("device_tamper")

        return assessment
