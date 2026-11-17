"""
AWARESPAN — Response Selector
Determines deterrence actions, siren playback, silent alarms, or emergency escalation.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

from typing import Dict, List

from shared.logging.logger import get_logger
from node_runtime.processing.threat_assessment import ThreatAssessment

log = get_logger("node_runtime.response_selector")


class ResponseSelector:
    """Select alerting responses; animal detections never trigger speaker output."""

    AUDIO_EXCLUDED_LABELS = {"dog"}

    def __init__(
        self,
        siren_enabled: bool = False,
        led_enabled: bool = True,
        presence_deterrence_enabled: bool = False,
        presence_deterrence_labels=None,
    ):
        self.siren_enabled = siren_enabled
        self.led_enabled = led_enabled
        self.presence_deterrence_enabled = presence_deterrence_enabled
        labels = {"person"} if presence_deterrence_labels is None else presence_deterrence_labels
        self.presence_deterrence_labels = {
            str(label).strip().lower() for label in labels
            if str(label).strip() and str(label).strip().lower() not in self.AUDIO_EXCLUDED_LABELS
        }

    def select_response(self, assessment: ThreatAssessment) -> Dict[str, bool]:
        """
        Decide on operational actions:
        - siren: trigger a configured audible warning (never for dog detections)
        - strobe: trigger visual LED strobe
        - alert_backend: dispatch incident to cloud/MQTT
        - alert_telegram: dispatch priority notification to operator
        - escalate_emergency: flag for 911/police/EMS response
        """
        if assessment.tier == "tier2":
            # Tier 2: Weapons/vehicles - emergency alert + siren + strobe
            return {
                "siren": self.siren_enabled,
                "strobe": self.led_enabled,
                "alert_backend": True,
                "alert_telegram": True,
                "escalate_emergency": assessment.threat_level == "CRITICAL",
            }
        elif assessment.tier == "tier1":
            # Presence detections are deterrence candidates only for explicitly configured labels.
            # Merely detecting an unrelated animal must not activate the speaker.
            target_present = bool(self.presence_deterrence_labels.intersection(
                label.lower() for label in assessment.labels
            ))
            return {
                "siren": self.siren_enabled and self.presence_deterrence_enabled and target_present,
                "strobe": False,
                "alert_backend": True,
                "alert_telegram": False,
                "escalate_emergency": False,
            }
        else:
            return {
                "siren": False,
                "strobe": False,
                "alert_backend": False,
                "alert_telegram": False,
                "escalate_emergency": False,
            }
