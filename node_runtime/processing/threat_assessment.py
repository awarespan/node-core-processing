"""
AWARESPAN — Threat Assessment Engine
Evaluates detection results into Tier 1 (nuisance/animal) vs Tier 2 (weapons/violent threat).

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from shared.models.events import Detection

log = get_logger("node_runtime.threat_assessment")


@dataclass
class ThreatAssessment:
    tier: str  # "tier1" | "tier2" | "none"
    threat_level: str  # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "NONE"
    labels: List[str]
    max_confidence: float
    is_weapon: bool


class ThreatAssessor:
    """Classifies detections according to the two-tier safety threat policy."""

    def __init__(
        self,
        tier1_labels: Optional[Set[str]] = None,
        tier2_labels: Optional[Set[str]] = None,
        min_confidence: Optional[float] = None,
    ):
        settings = get_settings()
        self.tier1_labels = {l.lower() for l in (tier1_labels or settings.tier1_labels)}
        self.tier2_labels = {l.lower() for l in (tier2_labels or settings.tier2_labels)}
        self.min_confidence = min_confidence if min_confidence is not None else settings.confidence_threshold

    def evaluate(self, detections: List[Detection]) -> ThreatAssessment:
        """
        Evaluate detections. Tier 2 (weapons/lethal objects) always takes priority over Tier 1.
        """
        tier2_hits = [
            d for d in detections
            if d.confidence >= self.min_confidence and d.label.lower() in self.tier2_labels
        ]
        tier1_hits = [
            d for d in detections
            if d.confidence >= self.min_confidence and d.label.lower() in self.tier1_labels
        ]

        # Tier 2 Priority: Active weapon or vehicle threat
        if tier2_hits:
            labels = sorted({d.label for d in tier2_hits})
            max_conf = max(d.confidence for d in tier2_hits)
            threat_level = "CRITICAL" if max_conf >= 0.65 else "HIGH"
            is_weapon = any(w in " ".join(labels).lower() for w in ("knife", "gun", "weapon", "pistol", "rifle"))
            return ThreatAssessment(
                tier="tier2",
                threat_level=threat_level,
                labels=labels,
                max_confidence=max_conf,
                is_weapon=is_weapon,
            )

        # Tier 1: Nuisance, animal, or non-weapon person
        if tier1_hits:
            labels = sorted({d.label for d in tier1_hits})
            max_conf = max(d.confidence for d in tier1_hits)
            threat_level = "MEDIUM" if max_conf >= 0.70 else "LOW"
            return ThreatAssessment(
                tier="tier1",
                threat_level=threat_level,
                labels=labels,
                max_confidence=max_conf,
                is_weapon=False,
            )

        # No active threat
        return ThreatAssessment(
            tier="none",
            threat_level="NONE",
            labels=[],
            max_confidence=0.0,
            is_weapon=False,
        )
