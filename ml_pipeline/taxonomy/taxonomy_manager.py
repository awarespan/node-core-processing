"""
AWARESPAN — Threat Taxonomy Manager
Provides typed querying, validation, and label mapping for the comprehensive threat taxonomy.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from shared.logging.logger import get_logger

log = get_logger("ml_pipeline.taxonomy")

DEFAULT_TAXONOMY_PATH = Path(__file__).parent / "taxonomy.json"


@dataclass
class TaxonomyClass:
    class_id: str
    parent_category: str
    display_name: str
    definition: str
    modality: str
    task: str
    severity: int
    default_confidence_threshold: float
    evidence_requirements: str
    threat_tier: int
    allowed_actions: List[str] = field(default_factory=list)


class TaxonomyManager:
    """Manages the versioned threat taxonomy definition."""

    def __init__(self, taxonomy_path: Optional[Path] = None):
        self.path = taxonomy_path or DEFAULT_TAXONOMY_PATH
        self._data: Dict = {}
        self._classes: Dict[str, TaxonomyClass] = {}
        self.version: str = "1.0.0"
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            log.warning("Taxonomy file not found at %s; initializing empty.", self.path)
            return

        with open(self.path, "r", encoding="utf-8") as f:
            self._data = json.load(f)

        self.version = self._data.get("version", "1.0.0")
        raw_classes = self._data.get("classes", {})

        for cid, info in raw_classes.items():
            self._classes[cid] = TaxonomyClass(
                class_id=cid,
                parent_category=info.get("parent_category", "unknown"),
                display_name=info.get("display_name", cid),
                definition=info.get("definition", ""),
                modality=info.get("modality", "visual"),
                task=info.get("task", "object_detection"),
                severity=int(info.get("severity", 1)),
                default_confidence_threshold=float(info.get("default_confidence_threshold", 0.5)),
                evidence_requirements=info.get("evidence_requirements", ""),
                threat_tier=int(info.get("threat_tier", 0)),
                allowed_actions=info.get("allowed_actions", ["log_only"]),
            )

        log.debug("Loaded taxonomy v%s with %d classes", self.version, len(self._classes))

    def get_class(self, class_id: str) -> Optional[TaxonomyClass]:
        """Retrieve taxonomy definition for class ID."""
        return self._classes.get(class_id)

    def is_valid_class(self, class_id: str) -> bool:
        """Check if class ID is defined in taxonomy."""
        return class_id in self._classes

    def list_classes(self, category: Optional[str] = None, modality: Optional[str] = None) -> List[TaxonomyClass]:
        """List classes filtered by parent category and/or modality."""
        results = list(self._classes.values())
        if category:
            results = [c for c in results if c.parent_category == category]
        if modality:
            results = [c for c in results if c.modality == modality]
        return results

    def map_raw_label(self, raw_label: str, modality: str = "visual") -> str:
        """
        Map upstream model labels (e.g., 'gun', 'knife', 'dog', 'gunshot') to standard taxonomy IDs.
        """
        norm = raw_label.lower().strip().replace(" ", "_")

        # Visual mappings
        if modality == "visual":
            if norm in ("gun", "handgun", "pistol", "revolver", "firearm"):
                return "weapon.firearm.handgun"
            elif norm in ("rifle", "shotgun", "long_gun", "carbine"):
                return "weapon.firearm.rifle"
            elif norm in ("knife", "dagger", "switchblade", "pocketknife"):
                return "weapon.edged.knife"
            elif norm in ("machete", "sword"):
                return "weapon.edged.machete"
            elif norm in ("fight", "fighting", "assault", "violence"):
                return "human_activity.violence.fighting"
            elif norm in ("fall", "falling", "collapse", "fallen_person"):
                return "human_activity.distress.fall"
            elif norm in ("fire", "flame", "blaze"):
                return "hazard.fire.flame"
            elif norm in ("smoke", "smoke_plume"):
                return "hazard.fire.smoke"
            elif norm in (
                "bird", "cat", "dog", "horse", "sheep", "cow", "elephant",
                "zebra", "giraffe", "animal", "wildlife", "deer"
            ):
                return "animal.wildlife.general"
            elif norm in ("bear", "boar", "wild_boar", "tiger", "lion", "predator"):
                return "animal.wildlife.predator"

        # Acoustic mappings
        elif modality == "acoustic":
            if norm in ("gunshot", "gunfire", "machine_gun", "shotgun_blast"):
                return "audio.threat.gunshot"
            elif norm in ("scream", "screaming", "shriek", "yell"):
                return "audio.threat.scream"
            elif norm in ("glass", "glass_breaking", "breaking_glass", "shatter"):
                return "audio.threat.glass_break"
            elif norm in ("alarm", "siren", "smoke_detector", "fire_alarm"):
                return "audio.threat.alarm"

        # Fallback to general unknown category if unrecognized
        if norm.startswith("weapon.") or norm.startswith("audio.") or norm.startswith("animal.") or norm.startswith("human_activity."):
            return norm
        return f"{modality}.unknown.{norm}"


_GLOBAL_TAXONOMY: Optional[TaxonomyManager] = None


def get_taxonomy_manager() -> TaxonomyManager:
    """Singleton getter for TaxonomyManager."""
    global _GLOBAL_TAXONOMY
    if _GLOBAL_TAXONOMY is None:
        _GLOBAL_TAXONOMY = TaxonomyManager()
    return _GLOBAL_TAXONOMY
