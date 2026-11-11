"""
AWARESPAN — Multi-Model Inference Router
Routes inference requests across specialist models based on modality, task, hardware budget, and approval states.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from shared.logging.logger import get_logger
from ml_pipeline.adapters.base import ThreatModelAdapter
from ml_pipeline.registry.model_registry import (
    LocalModelRegistry,
    ModelState,
    get_model_registry,
)
from ml_pipeline.schema.predictions import StandardModelPrediction

log = get_logger("ml_pipeline.inference.router")


@dataclass
class HardwareBudget:
    """Resource constraints for edge execution (e.g. Raspberry Pi 5)."""
    max_concurrent_visual: int = 1
    max_concurrent_acoustic: int = 1
    max_latency_budget_ms: float = 250.0
    enable_shadow_models: bool = True


class InferenceRouter:
    """Orchestrates multi-model execution and dispatch across specialist adapters."""

    def __init__(
        self,
        registry: Optional[LocalModelRegistry] = None,
        budget: Optional[HardwareBudget] = None,
    ):
        self.registry = registry or get_model_registry()
        self.budget = budget or HardwareBudget()
        self._adapters: Dict[str, ThreatModelAdapter] = {}
        self._cross_modal_trigger_timestamp: float = 0.0

    def register_adapter(self, adapter: ThreatModelAdapter) -> None:
        """Register an active model adapter instance."""
        self._adapters[adapter.model_id] = adapter
        log.info("InferenceRouter registered adapter: %s (%s)", adapter.model_id, adapter.metadata().get("framework"))

    def get_adapter(self, model_id: str) -> Optional[ThreatModelAdapter]:
        return self._adapters.get(model_id)

    def route_visual(
        self,
        frame: Any,
        required_classes: Optional[Set[str]] = None,
        allow_shadow: bool = False,
    ) -> List[StandardModelPrediction]:
        """
        Route a visual frame to active visual adapters.
        Adheres to hardware concurrency budgets to prevent Raspberry Pi CPU thrashing.
        """
        predictions: List[StandardModelPrediction] = []
        visual_adapters = [
            a for a in self._adapters.values()
            if a.is_loaded and a.metadata().get("modality", "visual") == "visual"
        ]

        # Prioritize primary deployed models
        executed_count = 0
        for adapter in visual_adapters:
            if executed_count >= self.budget.max_concurrent_visual and not allow_shadow:
                break

            entry = self.registry.get_model(adapter.model_id)
            if not entry:
                continue

            # Check model eligibility
            if entry.state == ModelState.DEPLOYED.value:
                pred = adapter.predict(frame)
                predictions.append(pred)
                executed_count += 1

            elif allow_shadow and self.budget.enable_shadow_models and entry.state in (ModelState.APPROVED.value, ModelState.EVALUATED.value):
                # Run in shadow evaluation mode
                pred = adapter.predict(frame)
                pred.metadata["execution_mode"] = "shadow"
                predictions.append(pred)

        return predictions

    def route_audio(self, audio_data: Any) -> List[StandardModelPrediction]:
        """Route an audio sample to acoustic threat adapters."""
        predictions: List[StandardModelPrediction] = []
        audio_adapters = [
            a for a in self._adapters.values()
            if a.is_loaded and (
                a.metadata().get("modality") == "acoustic" or "audio" in a.model_id.lower()
            )
        ]

        for adapter in audio_adapters[: self.budget.max_concurrent_acoustic]:
            pred = adapter.predict(audio_data)
            predictions.append(pred)

            # Check if acoustic threat should trigger high-priority cross-modal visual inspection
            for p in pred.predictions:
                if p.class_id in ("audio.threat.gunshot", "audio.threat.scream") and p.confidence >= 0.5:
                    self.signal_cross_modal_trigger(p.class_id, p.confidence)

        return predictions

    def signal_cross_modal_trigger(self, trigger_class: str, confidence: float) -> None:
        """Signal cross-modal trigger from acoustic or sensor event."""
        self._cross_modal_trigger_timestamp = time.time()
        log.warning("Cross-modal event triggered by %s (confidence=%.2f); prioritizing visual focus", trigger_class, confidence)

    def is_cross_modal_active(self, window_sec: float = 3.0) -> bool:
        """Check if an urgent cross-modal alert was triggered recently."""
        return (time.time() - self._cross_modal_trigger_timestamp) <= window_sec
