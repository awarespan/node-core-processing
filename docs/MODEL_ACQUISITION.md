# AWARESPAN Pretrained Model Acquisition Catalogue & Audit

**Project:** AWARESPAN  
**Tagline:** Awareness Without Boundaries.  
**Official Problem Statement:** An AI-Powered Safety Device.  
**Contact:** awarespan@bchbenjamin.in  

---

## 1. Candidate Research Catalogue

| Model Identifier | Domain | Upstream Source | License | Redistributable | Architecture | Params | Size | Status |
| :--- | :--- | :--- | :--- | :---: | :--- | :---: | :---: | :---: |
| `awarespan-weapon-yolov8n` | Weapon Detection | Internal / Roboflow | AGPL-3.0 | Yes | YOLOv8n | 3.2M | 11.77 MB | **VERIFIED_LOCAL** |
| `awarespan-weapon-yolov8n-epoch80` | Weapon Detection | Internal Benchmark | Internal | Yes | YOLOv8n | 3.2M | 11.76 MB | **VERIFIED_LOCAL** |
| `awarespan-general-yolov8n` | Fauna / COCO | Ultralytics Official | AGPL-3.0 | Yes | YOLOv8n | 3.2M | 6.25 MB | **VERIFIED_LOCAL** |
| `yamnet-audioset` | Acoustic Events | Google Research / TFHub | Apache-2.0 | Yes | MobileNetV1 | 3.7M | 14.59 MB | **VERIFIED_LOCAL** |
| `megadetector-v5a` | Animal Localizer | Microsoft / AgentMorris | MIT | Yes | YOLOv5x | 86.7M | 174.0 MB | **RESEARCH_CANDIDATE** |
| `openvino-action-recognition` | Human Activity / Violence | Intel OpenVINO OMZ | Apache-2.0 | Yes | MobileNetV3 3D | 14.2M | 56.0 MB | **RESEARCH_CANDIDATE** |
| `fire-smoke-yolov8n` | Fire & Smoke | Hugging Face / Roboflow | CC-BY-4.0 | Yes | YOLOv8n | 3.2M | 6.3 MB | **RESEARCH_CANDIDATE** |

---

## 2. Hardware Suitability on Raspberry Pi 5 (4 GB RAM)

1. **Ultralytics YOLOv8n (Weapon & General)**:
   - Inference latency on Pi 5 CPU: **~45-75 ms** at `416x416` resolution, **~70-95 ms** at `640x640`.
   - Memory footprint (RSS): **~280 MB**.
   - Throughput: **12-16 FPS** on single frame ingest.
   - Suitability: **EXCELLENT**.

2. **YAMNet Acoustic Threat Classifier**:
   - Inference latency on Pi 5 CPU: **~10-18 ms** per 0.96s audio patch.
   - Memory footprint: **~85 MB**.
   - Suitability: **EXCELLENT** (runs concurrently with visual detector without causing undervoltage throttles).

3. **MegaDetector v5a (86.7M params)**:
   - Inference latency on Pi 5 CPU: **~850-1200 ms** per frame.
   - Suitability: **POOR FOR REAL-TIME EDGE**. Recommended for scheduled / burst inspection or replaced by compact YOLOv8n animal fine-tune.

---

## 3. License & Redistribution Compliance

- **Weights Redistribution**: Only models with verified permissive open-source licenses (MIT, Apache-2.0, AGPL-3.0, CC-BY-4.0) are packaged into published GitHub Release bundles.
- **Third-Party Research Weights**: Models with non-commercial (NC) or ambiguous redistribution clauses must be obtained via documented acquisition scripts ([`ml_pipeline/acquisition/downloader.py`](file:///mnt/WindowsDrive/Shared/Projects/SIP/node-backend/ml_pipeline/acquisition/downloader.py)) rather than bundled in public releases.
