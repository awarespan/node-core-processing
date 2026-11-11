"""
AWARESPAN — Adapters Subsystem
"""

from ml_pipeline.adapters.audio_adapter import AudioThreatAdapter
from ml_pipeline.adapters.base import ThreatModelAdapter
from ml_pipeline.adapters.mock_adapter import MockThreatAdapter
from ml_pipeline.adapters.yolo_adapter import YOLOv8Adapter

__all__ = ["ThreatModelAdapter", "YOLOv8Adapter", "AudioThreatAdapter", "MockThreatAdapter"]
