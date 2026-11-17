# AWARESPAN Pretrained Model Acquisition Catalogue & Audit

## Current checkout status

The table below reflects files actually present in this repository checkout. “Verified local” means the file exists and its SHA-256 matches the repository's current manifest. It does not mean the model has been re-benchmarked on the Pi during this work session.

| Model ID | Purpose | Local artifact | Status | Notes |
|---|---|---|---|---|
| `awarespan-weapon-yolov8n` | Weapon detection | `shared/models/yolov8n_best_weapon.pt` | **VERIFIED LOCAL** | Existing production checkpoint; `gun`, `knife` |
| `awarespan-general-yolov8n` | General COCO detection | `yolov8n.pt` | **VERIFIED LOCAL** | Used as a provisional baseline with `person`, `dog` class allow-list |
| `awarespan-weapon-yolov8n-epoch80` | Historical weapon candidate | `artifacts/model-checkpoints/recovered/epoch80_best_map.pt` | **MISSING FROM CHECKOUT** | Registry reference only; cannot load or deploy until the actual file is restored and re-hashed |
| `awarespan-yamnet-audio` | Audio event classification | `models/working/audio/yamnet.h5` | **MISSING FROM CHECKOUT** | Disabled in the Pi profile; no YAMNet inference is active |
| `megadetector-v5a` | Animal/person/vehicle localisation | Upstream only | **RESEARCH CANDIDATE** | Too large for the current Pi 5 CPU target; audit licence and benchmark before use |
| `openvino-action-recognition` | Temporal human activity | Upstream only | **RESEARCH CANDIDATE** | Needs a sequence-level video dataset and a compatible runtime adapter |
| `fire-smoke-yolov8n` | Fire/smoke | Upstream only | **RESEARCH CANDIDATE** | Needs provenance, redistribution review, local weights and evaluation |

## 1. Deployment policy

- `models/deployed/manifest.json` is the runtime source of truth for selected model IDs, artifact paths, class allow-lists, input size, confidence threshold, and checksums.
- `pi5_edge` selects the local weapon model and the COCO person/dog baseline.
- `cloud_full` is a planning profile only; it is not an active inference backend.
- Registry states and the deployment manifest must not claim a model is loaded when its artifact is absent.
- The `AudioThreatAdapter` currently implements a handcrafted spectral DSP heuristic. It is not a trained YAMNet network.

## 2. Pi suitability

The numbers in older project notes (latency, FPS, and RAM) are historical estimates/reports. They were not re-measured during this Box work session. The current Pi 5 profile intentionally runs visual specialists sequentially to bound CPU and memory use. Re-measure on the actual Pi with the current runtime, current OS, current model weights, and representative camera input before making performance claims.

## 3. License and redistribution review

Before adding a dataset or weight package:

1. Record upstream owner, immutable revision, licence text/URL, retrieval date and checksum.
2. Distinguish permission to use from permission to redistribute.
3. Record commercial-use restrictions and attribution obligations.
4. Do not bundle weights into a GitHub Release unless redistribution is explicitly permitted.
5. Keep unverified or restricted weights out of production profiles.

See [`ml_pipeline/acquisition/catalogue.py`](../ml_pipeline/acquisition/catalogue.py), [`models/deployed/manifest.json`](../models/deployed/manifest.json), and [`docs/ML_DATASETS_AND_TRAINING.md`](ML_DATASETS_AND_TRAINING.md).
