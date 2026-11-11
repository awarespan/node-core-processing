"""
AWARESPAN — Local Model Registry
Tracks registered models, lifecycle states, checksums, compatibility, and evaluation metrics.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.logging.logger import get_logger

log = get_logger("ml_pipeline.registry")

DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parent / "models.json"


class ModelState(str, Enum):
    DISCOVERED = "DISCOVERED"
    DOWNLOADED = "DOWNLOADED"
    AUDITED = "AUDITED"
    LOADED = "LOADED"
    EVALUATED = "EVALUATED"
    APPROVED = "APPROVED"
    DEPLOYED = "DEPLOYED"
    DEPRECATED = "DEPRECATED"


VALID_TRANSITIONS = {
    ModelState.DISCOVERED: {ModelState.DOWNLOADED, ModelState.DEPRECATED},
    ModelState.DOWNLOADED: {ModelState.AUDITED, ModelState.DEPRECATED},
    ModelState.AUDITED: {ModelState.LOADED, ModelState.DEPRECATED},
    ModelState.LOADED: {ModelState.EVALUATED, ModelState.DEPRECATED},
    ModelState.EVALUATED: {ModelState.APPROVED, ModelState.DEPRECATED},
    ModelState.APPROVED: {ModelState.DEPLOYED, ModelState.DEPRECATED},
    ModelState.DEPLOYED: {ModelState.DEPRECATED, ModelState.APPROVED},
    ModelState.DEPRECATED: {ModelState.DISCOVERED},
}


@dataclass
class LicenseInfo:
    license_name: str
    redistributable: bool
    commercial_use: bool
    source_url: str
    notes: str = ""


@dataclass
class ModelRegistryEntry:
    model_id: str
    version: str
    display_name: str
    artifact_path: str
    sha256: str
    framework: str
    supported_classes: List[str]
    modality: str
    task: str
    input_requirements: Dict[str, Any]
    output_schema_version: str = "1.0.0"
    taxonomy_version: str = "1.0.0"
    state: str = ModelState.DISCOVERED.value
    license_info: Optional[Dict[str, Any]] = None
    evaluation_summary: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LocalModelRegistry:
    """Manages the lifecycle and catalogue of models on the node."""

    def __init__(self, registry_path: Optional[Path] = None):
        self.path = registry_path or DEFAULT_REGISTRY_PATH
        self._entries: Dict[str, ModelRegistryEntry] = {}
        self.load()

    def load(self) -> None:
        """Load registry from JSON file."""
        if not self.path.exists():
            log.debug("Registry file does not exist at %s; starting clean.", self.path)
            return

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._entries.clear()
            for key, val in data.get("models", {}).items():
                self._entries[key] = ModelRegistryEntry(**val)

            log.debug("Loaded %d model entries from registry %s", len(self._entries), self.path)
        except Exception as exc:
            log.warning("Failed to load model registry from %s: %s", self.path, exc)

    def save(self) -> bool:
        """Persist registry to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            payload = {
                "registry_version": "1.0.0",
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "models": {k: v.to_dict() for k, v in self._entries.items()},
            }
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            log.debug("Saved model registry to %s", self.path)
            return True
        except Exception as exc:
            log.error("Failed to save model registry: %s", exc)
            return False

    def _make_key(self, model_id: str, version: str) -> str:
        return f"{model_id}:{version}"

    def register_model(self, entry: ModelRegistryEntry) -> bool:
        """Add or update a model entry in the registry."""
        key = self._make_key(entry.model_id, entry.version)
        entry.updated_at = datetime.now(timezone.utc).isoformat()
        self._entries[key] = entry
        self.save()
        log.info("Registered model %s v%s (state: %s)", entry.model_id, entry.version, entry.state)
        return True

    def transition_state(
        self,
        model_id: str,
        version: str,
        target_state: ModelState,
        reason: str = "",
        force: bool = False,
    ) -> bool:
        """Transition a model to a new lifecycle state."""
        key = self._make_key(model_id, version)
        entry = self._entries.get(key)
        if not entry:
            log.error("Cannot transition state: model %s v%s not found in registry", model_id, version)
            return False

        current = ModelState(entry.state)
        if not force and target_state not in VALID_TRANSITIONS.get(current, set()):
            log.error("Invalid state transition for %s: %s -> %s", key, current.value, target_state.value)
            return False

        entry.state = target_state.value
        entry.updated_at = datetime.now(timezone.utc).isoformat()
        entry.metadata["last_transition"] = {
            "from": current.value,
            "to": target_state.value,
            "reason": reason,
            "timestamp": entry.updated_at,
        }
        self.save()
        log.info("Model %s transitioned %s -> %s (reason: %s)", key, current.value, target_state.value, reason)
        return True

    def get_model(self, model_id: str, version: Optional[str] = None) -> Optional[ModelRegistryEntry]:
        """Get model by ID and optional version. Defaults to latest version or deployed."""
        if version:
            return self._entries.get(self._make_key(model_id, version))

        # Look for deployed first
        matching = [e for e in self._entries.values() if e.model_id == model_id]
        if not matching:
            return None

        deployed = [e for e in matching if e.state == ModelState.DEPLOYED.value]
        if deployed:
            return deployed[-1]

        approved = [e for e in matching if e.state == ModelState.APPROVED.value]
        if approved:
            return approved[-1]

        return matching[-1]

    def list_models(
        self,
        modality: Optional[str] = None,
        state: Optional[ModelState] = None,
        task: Optional[str] = None,
    ) -> List[ModelRegistryEntry]:
        """Filter models by modality, state, or task."""
        results = list(self._entries.values())
        if modality:
            results = [e for e in results if e.modality == modality]
        if state:
            results = [e for e in results if e.state == state.value]
        if task:
            results = [e for e in results if e.task == task]
        return results

    def get_deployed_models(self) -> List[ModelRegistryEntry]:
        """Return all models marked DEPLOYED."""
        return self.list_models(state=ModelState.DEPLOYED)


_GLOBAL_REGISTRY: Optional[LocalModelRegistry] = None


def get_model_registry() -> LocalModelRegistry:
    """Singleton getter for LocalModelRegistry."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = LocalModelRegistry()
    return _GLOBAL_REGISTRY
