"""
AWARESPAN — Pretrained Model Acquisition Catalogue & Audit
Maintains detailed provenance, license audits, and acquisition profiles for candidate pretrained models.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ModelCandidateAudit:
    candidate_id: str
    display_name: str
    domain: str
    upstream_repository: str
    revision: str
    weights_source_url: str
    license_code: str
    redistributable: bool
    commercial_friendly: bool
    architecture: str
    parameter_count_millions: float
    file_size_mb: float
    framework: str
    modality: str
    task: str
    input_resolution: str
    supported_classes: List[str]
    required_dependencies: List[str]
    hardware_suitability: str
    reported_metrics: Dict[str, Any]
    known_limitations: str
    sha256: str
    download_status: str                   # "VERIFIED_LOCAL", "DOWNLOADED", "AVAILABLE_UPSTREAM", "BLOCKED"
    integration_status: str                # "INTEGRATED", "ADAPTER_READY", "RESEARCH_CANDIDATE"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


CANDIDATE_MODELS_CATALOGUE: List[ModelCandidateAudit] = [
    # 1. Existing Production Weapon Model
    ModelCandidateAudit(
        candidate_id="awarespan-weapon-yolov8n",
        display_name="AWARESPAN Fine-tuned YOLOv8n Weapon Detector",
        domain="weapon_detection",
        upstream_repository="https://github.com/awarespan/node-core-processing",
        revision="main-b6c5906",
        weights_source_url="local://shared/models/yolov8n_best_weapon.pt",
        license_code="AGPL-3.0",
        redistributable=True,
        commercial_friendly=False,
        architecture="Ultralytics YOLOv8n",
        parameter_count_millions=3.2,
        file_size_mb=11.77,
        framework="ultralytics_yolov8",
        modality="visual",
        task="object_detection",
        input_resolution="640x640",
        supported_classes=["gun", "knife"],
        required_dependencies=["ultralytics", "torch", "torchvision"],
        hardware_suitability="Raspberry Pi 5 CPU (~65-85ms latency)",
        reported_metrics={"fitness": 0.33656, "classes": 2},
        known_limitations="Trained on focused handgun and knife data; long firearms require wider dataset.",
        sha256="e817da6a6bd08861095bf456f10bbad19dc3eda46669282fc266ddc47dca3e34",
        download_status="VERIFIED_LOCAL",
        integration_status="INTEGRATED",
    ),

    # 2. Historical Benchmark Weapon Model (Epoch 80 Peak)
    ModelCandidateAudit(
        candidate_id="awarespan-weapon-yolov8n-epoch80",
        display_name="AWARESPAN Peak Benchmark Epoch 80 (Recovered)",
        domain="weapon_detection",
        upstream_repository="https://github.com/awarespan/node-core-processing",
        revision="checkpoint-epoch80",
        weights_source_url="local://artifacts/model-checkpoints/recovered/epoch80_best_map.pt",
        license_code="Internal / AWARESPAN",
        redistributable=True,
        commercial_friendly=True,
        architecture="Ultralytics YOLOv8n",
        parameter_count_millions=3.2,
        file_size_mb=11.76,
        framework="ultralytics_yolov8",
        modality="visual",
        task="object_detection",
        input_resolution="416x416",
        supported_classes=["gun", "knife"],
        required_dependencies=["ultralytics", "torch", "torchvision"],
        hardware_suitability="Raspberry Pi 5 CPU (~45-65ms latency at 416x416)",
        reported_metrics={"mAP50": 0.81557, "mAP50_95": 0.60915, "precision": 0.8480, "recall": 0.72536},
        known_limitations="Optimized at 416x416 resolution; high precision on test split.",
        sha256="ac06e9281a7f20208549e739b9b1dd4f20e426b209d12027ac9122d920c80c90",
        download_status="VERIFIED_LOCAL",
        integration_status="INTEGRATED",
    ),

    # 3. MegaDetector v5 / Animal Localizer
    ModelCandidateAudit(
        candidate_id="megadetector-v5a",
        display_name="Microsoft MegaDetector v5a (Animal/Person/Vehicle)",
        domain="animal_detection",
        upstream_repository="https://github.com/agentmorris/MegaDetector",
        revision="v5.0.0",
        weights_source_url="https://github.com/agentmorris/MegaDetector/releases/download/v5.0/md_v5a.0.0.pt",
        license_code="MIT",
        redistributable=True,
        commercial_friendly=True,
        architecture="YOLOv5x / YOLOv8 compatible",
        parameter_count_millions=86.7,
        file_size_mb=174.0,
        framework="ultralytics_yolo",
        modality="visual",
        task="object_detection",
        input_resolution="1280x1280 (can downsample to 640x640)",
        supported_classes=["animal", "person", "vehicle"],
        required_dependencies=["torch", "ultralytics"],
        hardware_suitability="Heavy on Pi 5 CPU (v5a is 86M params; compact v5u/n required for real-time edge)",
        reported_metrics={"mAP50": 0.892, "dataset": "Camera Traps WCS"},
        known_limitations="v5a is heavy for 4GB Pi 5 real-time 30fps. Compact YOLOv8n animal slice recommended.",
        sha256="unknown_upstream",
        download_status="AVAILABLE_UPSTREAM",
        integration_status="ADAPTER_READY",
    ),

    # 4. YOLOv8n COCO Animal & General Detector
    ModelCandidateAudit(
        candidate_id="awarespan-general-yolov8n",
        display_name="Ultralytics YOLOv8n General & Fauna Detector",
        domain="general_animal_detection",
        upstream_repository="https://github.com/ultralytics/ultralytics",
        revision="v8.3.0",
        weights_source_url="local://yolov8n.pt",
        license_code="AGPL-3.0",
        redistributable=True,
        commercial_friendly=False,
        architecture="Ultralytics YOLOv8n",
        parameter_count_millions=3.2,
        file_size_mb=6.25,
        framework="ultralytics_yolov8",
        modality="visual",
        task="object_detection",
        input_resolution="640x640",
        supported_classes=["bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"],
        required_dependencies=["ultralytics", "torch"],
        hardware_suitability="Raspberry Pi 5 CPU (~65ms latency)",
        reported_metrics={"mAP50_95": 0.373, "dataset": "COCO val2017"},
        known_limitations="General COCO classes; does not distinguish specific rare wild carnivores.",
        sha256="f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36",
        download_status="VERIFIED_LOCAL",
        integration_status="INTEGRATED",
    ),

    # 5. YAMNet Acoustic Threat Classifier
    ModelCandidateAudit(
        candidate_id="yamnet-audioset",
        display_name="Google YAMNet AudioSet Threat Classifier",
        domain="audio_events",
        upstream_repository="https://github.com/tensorflow/models/tree/master/research/audioset/yamnet",
        revision="v1",
        weights_source_url="local://edge-ai/Real-Time-Sound-Event-Detection/keras_yamnet/yamnet.h5",
        license_code="Apache-2.0",
        redistributable=True,
        commercial_friendly=True,
        architecture="MobileNetV1-Depthwise",
        parameter_count_millions=3.7,
        file_size_mb=14.59,
        framework="yamnet_acoustic_dsp",
        modality="acoustic",
        task="audio_classification",
        input_resolution="16000Hz 1-channel PCM",
        supported_classes=["gunshot", "scream", "glass_breaking", "alarm", "explosion", "crying"],
        required_dependencies=["numpy", "scipy"],
        hardware_suitability="Raspberry Pi 5 CPU (~8-15ms per 0.96s audio patch)",
        reported_metrics={"mAP": 0.306, "dataset": "AudioSet (521 classes)"},
        known_limitations="Sensitive to heavy ambient wind noise; impulse crest-factor gate prevents false triggers.",
        sha256="13c3308955bbfaef262f175ac9c40e47b134573a93984f009220dd7cc12a1744",
        download_status="VERIFIED_LOCAL",
        integration_status="INTEGRATED",
    ),

    # 6. Intel Fight/Violence Detection Action Classifier
    ModelCandidateAudit(
        candidate_id="openvino-action-recognition",
        display_name="Intel OpenVINO Action Recognition / Violence Detector",
        domain="human_activity",
        upstream_repository="https://github.com/openvinotoolkit/open_model_zoo",
        revision="2024.0",
        weights_source_url="https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/action-recognition-0001",
        license_code="Apache-2.0",
        redistributable=True,
        commercial_friendly=True,
        architecture="ResNet-34 / MobileNetV3 3D-CNN",
        parameter_count_millions=14.2,
        file_size_mb=56.0,
        framework="openvino_onnx",
        modality="visual",
        task="action_recognition",
        input_resolution="16 frames x 224x224",
        supported_classes=["fighting", "walking", "running", "falling"],
        required_dependencies=["onnxruntime", "numpy", "cv2"],
        hardware_suitability="Raspberry Pi 5 (~90-120ms per 16-frame clip)",
        reported_metrics={"accuracy": 0.842, "dataset": "UCF101 / Kinetics-400"},
        known_limitations="Requires continuous sliding window buffer of 16 frames.",
        sha256="upstream_pending",
        download_status="AVAILABLE_UPSTREAM",
        integration_status="RESEARCH_CANDIDATE",
    ),

    # 7. Fire & Smoke Visual Detector
    ModelCandidateAudit(
        candidate_id="fire-smoke-yolov8n",
        display_name="YOLOv8n Fire and Smoke Hazard Detector",
        domain="fire_and_smoke",
        upstream_repository="https://huggingface.co/models?search=yolov8-fire",
        revision="v1.0",
        weights_source_url="https://huggingface.co/keremberke/yolov8n-fire-detection",
        license_code="CC-BY-4.0",
        redistributable=True,
        commercial_friendly=True,
        architecture="Ultralytics YOLOv8n",
        parameter_count_millions=3.2,
        file_size_mb=6.3,
        framework="ultralytics_yolov8",
        modality="visual",
        task="object_detection",
        input_resolution="640x640",
        supported_classes=["fire", "smoke"],
        required_dependencies=["ultralytics", "torch"],
        hardware_suitability="Raspberry Pi 5 CPU (~65ms)",
        reported_metrics={"mAP50": 0.812, "dataset": "Roboflow Fire/Smoke Dataset"},
        known_limitations="Cloud reflections and orange vehicle tail lights can cause false positives without temporal persistence.",
        sha256="upstream_pending",
        download_status="AVAILABLE_UPSTREAM",
        integration_status="RESEARCH_CANDIDATE",
    )
]


def get_candidate_catalogue() -> List[ModelCandidateAudit]:
    """Retrieve full audit catalogue of candidate models."""
    return CANDIDATE_MODELS_CATALOGUE
