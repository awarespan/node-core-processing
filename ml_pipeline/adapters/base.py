"""
AWARESPAN — Abstract Threat Model Adapter
Defines the unified lifecycle and inference contract for all ML framework adapters.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from ml_pipeline.schema.predictions import StandardModelPrediction


class ThreatModelAdapter(ABC):
    """Abstract base class for all AWARESPAN model adapters."""

    def __init__(
        self,
        model_id: str,
        model_version: str = "1.0.0",
        taxonomy_version: str = "1.0.0",
    ):
        self.model_id = model_id
        self.model_version = model_version
        self.taxonomy_version = taxonomy_version
        self.is_loaded: bool = False
        self.artifact_path: Optional[str] = None
        self.config: Dict[str, Any] = {}

    @abstractmethod
    def load(self, artifact_path: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """Load model weights and initialize runtime engine. Returns True if successful."""
        pass

    @abstractmethod
    def predict(self, input_data: Any) -> StandardModelPrediction:
        """Execute inference on input data and return standardized prediction."""
        pass

    @abstractmethod
    def metadata(self) -> Dict[str, Any]:
        """Return adapter and underlying framework metadata."""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Verify model integrity and engine readiness."""
        pass

    def unload(self) -> None:
        """Release underlying model resources."""
        self.is_loaded = False
