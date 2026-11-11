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
    """Selects deterrence actions and alerting responses based on threat assessment."""

    def __init__(self, siren_enabled: bool = True, led_enabled: bool = True):
        self.siren_enabled = siren_enabled
        self.led_enabled = led_enabled

    def select_response(self, assessment: ThreatAssessment) -> Dict[str, bool]:
        """
        Decide on operational actions:
        - siren: trigger audio deterrence
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
            # Tier 1: Nuisance/animals - siren deterrence, log event, no emergency dispatch
            return {
                "siren": self.siren_enabled,
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
