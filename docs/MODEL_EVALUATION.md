# AWARESPAN Model Evaluation & Benchmark Record

## 1. Scope and evidence status

This document preserves historical performance figures that were recorded in earlier project notes. They were **not independently reproduced in the current Box workspace**. The Pi is not connected to this Box session, and the historical epoch-80 checkpoint is not present in the cloned repository. Treat the figures below as historical claims to revalidate, not as current acceptance results.

## 2. Historical weapon checkpoint report

An earlier report recorded the following epoch-80 metrics for `awarespan-weapon-yolov8n-epoch80`:

| Metric | Historical reported value | Current verification status |
|---|---:|---|
| mAP@50 | 0.81557 | Not revalidated; checkpoint absent from this checkout |
| mAP@50–95 | 0.60915 | Not revalidated; checkpoint absent from this checkout |
| Precision | 0.84800 | Not revalidated; checkpoint absent from this checkout |
| Recall | 0.72536 | Not revalidated; checkpoint absent from this checkout |

The earlier note referenced a `unified_weapon_dataset` training corpus and a `416x416` input size. The weight file `artifacts/model-checkpoints/recovered/epoch80_best_map.pt` is not present under the current repository clone, so its checksum, class map, loading behaviour and metrics cannot be verified here. It is therefore marked `DISCOVERED`, not approved or deployed.

## 3. Current Pi profile

The current `pi5_edge` profile uses two repository-local artifacts:

| Model | Artifact | Allowed labels | Current status |
|---|---|---|---|
| Weapon detector | `shared/models/yolov8n_best_weapon.pt` | `gun`, `knife` | Existing production checkpoint; checksum matches manifest |
| General detector | `yolov8n.pt` | `person`, `dog` | Provisional COCO baseline; Pi camera validation pending |

Both artifact checksums were verified against `models/deployed/manifest.json`. This verifies file identity only; it does not prove successful model loading or real-time performance on the Pi.

## 4. Audio and video status

- The YAMNet weight file referenced by the registry is absent. YAMNet is not active in the Pi deployment profile.
- `AudioThreatAdapter` is a rule-based spectral DSP baseline, not a trained audio neural network.
- `TemporalVideoAdapter` defines a future sequence-level interface only. No temporal action model weights or training dataset are present.

## 5. Required re-benchmark on the Raspberry Pi

When the Pi is available, capture a new report containing:

1. Pi model, OS, Python, Ultralytics, PyTorch and OpenCV versions.
2. Exact Git commit and model SHA-256 values.
3. Actual model load result and class names.
4. Warm-up count and measured sample count.
5. Mean, median, p95 latency and achieved FPS for each model independently.
6. Combined sequential profile latency and peak RSS.
7. CPU temperature, throttling and undervoltage observations.
8. Person/dog precision and recall on a locally held-out, labelled set, including difficult negatives.
9. False deterrence rate and speaker output verification after hardware installation.

Do not promote the person/dog baseline to a safety-validated model until camera validation and representative evaluation are complete. Do not use the historical epoch-80 figures as evidence for the currently deployed weapon checkpoint.
