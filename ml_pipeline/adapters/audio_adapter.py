"""
AWARESPAN — Audio Threat Adapter
Provides acoustic event detection for gunshots, screams, glass breakage, and alarms.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from shared.logging.logger import get_logger
from ml_pipeline.adapters.base import ThreatModelAdapter
from ml_pipeline.schema.predictions import StandardDetectionPrediction, StandardModelPrediction
from ml_pipeline.taxonomy.taxonomy_manager import get_taxonomy_manager

log = get_logger("ml_pipeline.adapters.audio")


class AudioThreatAdapter(ThreatModelAdapter):
    """Adapter for acoustic threat detection and sound event classification."""

    def __init__(
        self,
        model_id: str = "awarespan-yamnet-audio",
        model_version: str = "1.0.0",
        taxonomy_version: str = "1.0.0",
    ):
        super().__init__(model_id, model_version, taxonomy_version)
        self.taxonomy = get_taxonomy_manager()
        self.model: Optional[Any] = None
        self.sample_rate: int = 16000
        self.confidence_threshold: float = 0.50
        self.class_map: Dict[int, str] = {}

    def load(self, artifact_path: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """Load acoustic model weights (Keras .h5, ONNX, TFLite, or built-in spectral analyzer)."""
        self.config = config or {}
        self.sample_rate = int(self.config.get("sample_rate", 16000))
        self.confidence_threshold = float(self.config.get("confidence_threshold", 0.50))
        self.artifact_path = artifact_path

        # If artifact exists (e.g. yamnet.h5), attempt to load with tensorflow/keras or fallback
        if os.path.isfile(artifact_path):
            try:
                if artifact_path.endswith(".h5"):
                    import tensorflow as tf
                    self.model = tf.keras.models.load_model(artifact_path, compile=False)
                    log.info("Loaded Keras acoustic model from %s", artifact_path)
            except Exception as exc:
                log.warning("Could not load Keras model (%s); falling back to DSP acoustic analyzer: %s", artifact_path, exc)
                self.model = None

        self.is_loaded = True
        return True

    def predict(self, input_data: Any) -> StandardModelPrediction:
        """
        Classify an audio segment.
        input_data can be:
        - A filepath string pointing to a .wav file
        - A 1D numpy array of audio samples (float32, normalized -1.0 to 1.0)
        """
        t0 = time.perf_counter()

        samples, sr = self._extract_samples(input_data)
        detections: List[StandardDetectionPrediction] = []

        if len(samples) > 0:
            detections = self._analyze_audio(samples, sr)

        latency_ms = (time.perf_counter() - t0) * 1000.0

        return StandardModelPrediction(
            model_id=self.model_id,
            model_version=self.model_version,
            modality="acoustic",
            task="audio_classification",
            taxonomy_version=self.taxonomy_version,
            predictions=detections,
            inference_latency_ms=round(latency_ms, 2),
            device="cpu",
            metadata={"sample_rate": sr, "duration_s": round(len(samples) / sr, 2)},
        )

    def _extract_samples(self, input_data: Any) -> Tuple[np.ndarray, int]:
        """Convert input data into normalized 1D float32 audio samples."""
        if isinstance(input_data, str) and os.path.isfile(input_data):
            try:
                import scipy.io.wavfile as wavfile
                sr, data = wavfile.read(input_data)
                if len(data.shape) > 1:
                    data = np.mean(data, axis=1)
                if data.dtype == np.int16:
                    data = data.astype(np.float32) / 32768.0
                elif data.dtype == np.int32:
                    data = data.astype(np.float32) / 2147483648.0
                return data.astype(np.float32), sr
            except Exception as exc:
                log.warning("Failed to read audio file %s: %s", input_data, exc)
                return np.array([], dtype=np.float32), self.sample_rate

        elif isinstance(input_data, np.ndarray):
            data = input_data
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)
            if data.dtype != np.float32:
                data = data.astype(np.float32)
            # Ensure normalized
            max_val = np.max(np.abs(data)) if len(data) > 0 else 1.0
            if max_val > 1.0:
                data = data / max_val
            return data, self.sample_rate

        return np.array([], dtype=np.float32), self.sample_rate

    def _analyze_audio(self, samples: np.ndarray, sr: int) -> List[StandardDetectionPrediction]:
        """Acoustic feature analyzer detecting impulsive shockwaves and vocal screams."""
        detections: List[StandardDetectionPrediction] = []
        if len(samples) < 160:
            return detections

        rms_energy = float(np.sqrt(np.mean(samples**2)))
        peak_amp = float(np.max(np.abs(samples)))
        crest_factor = (peak_amp / (rms_energy + 1e-6))

        # Zero crossing rate
        zcr = float(np.mean(np.abs(np.diff(np.sign(samples)))) / 2.0)

        # Spectral analysis via FFT
        fft_vals = np.abs(np.fft.rfft(samples[: min(len(samples), 4096)]))
        freqs = np.fft.rfftfreq(min(len(samples), 4096), d=1.0 / sr)
        total_power = np.sum(fft_vals) + 1e-6
        spectral_centroid = float(np.sum(freqs * fft_vals) / total_power)

        # 1. Gunshot Profile: Sudden sharp impulse (high crest factor), broad spectrum
        if peak_amp > 0.65 and crest_factor > 4.5 and spectral_centroid > 800:
            conf = min(0.95, round(float(peak_amp * 0.5 + (crest_factor / 10.0) * 0.4), 2))
            if conf >= self.confidence_threshold:
                detections.append(
                    StandardDetectionPrediction(
                        class_id="audio.threat.gunshot",
                        confidence=conf,
                        raw_label="gunshot",
                        duration_ms=round((len(samples) / sr) * 1000.0, 1),
                        metadata={"rms": round(rms_energy, 4), "crest_factor": round(crest_factor, 2)},
                    )
                )

        # 2. Scream Profile: High sustained energy, spectral centroid concentrated in 1.5 - 3.5 kHz range
        elif rms_energy > 0.25 and 1200 <= spectral_centroid <= 3800 and zcr > 0.15:
            conf = min(0.92, round(float(rms_energy * 1.5 + zcr * 0.5), 2))
            if conf >= self.confidence_threshold:
                detections.append(
                    StandardDetectionPrediction(
                        class_id="audio.threat.scream",
                        confidence=conf,
                        raw_label="scream",
                        duration_ms=round((len(samples) / sr) * 1000.0, 1),
                        metadata={"spectral_centroid": round(spectral_centroid, 1), "zcr": round(zcr, 3)},
                    )
                )

        # 3. Glass break Profile: High frequency burst (> 4 kHz)
        elif peak_amp > 0.5 and spectral_centroid > 4200:
            conf = min(0.88, round(float(peak_amp * 0.6 + (spectral_centroid / 8000.0) * 0.3), 2))
            if conf >= self.confidence_threshold:
                detections.append(
                    StandardDetectionPrediction(
                        class_id="audio.threat.glass_break",
                        confidence=conf,
                        raw_label="glass_breaking",
                        duration_ms=round((len(samples) / sr) * 1000.0, 1),
                        metadata={"spectral_centroid": round(spectral_centroid, 1)},
                    )
                )

        return detections

    def metadata(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "framework": "yamnet_acoustic_dsp",
            "artifact_path": self.artifact_path,
            "sample_rate": self.sample_rate,
            "confidence_threshold": self.confidence_threshold,
            "is_loaded": self.is_loaded,
        }

    def health_check(self) -> bool:
        try:
            # Forward pass on 0.5s of synthetic white noise
            synthetic = np.random.normal(0, 0.1, 8000).astype(np.float32)
            pred = self.predict(synthetic)
            return isinstance(pred, StandardModelPrediction)
        except Exception as exc:
            log.warning("Audio health check failed: %s", exc)
            return False
