# AWARESPAN Scalable ML Architecture

## Current deployment

The Raspberry Pi 5 runs local inference. The current `pi5_edge` profile is defined in `models/deployed/manifest.json` and loads two sequential visual specialists:

- `awarespan-weapon-yolov8n`: the existing fine-tuned weapon checkpoint at `shared/models/yolov8n_best_weapon.pt`, filtered to `gun` and `knife`.
- `awarespan-general-yolov8n`: the repository-local COCO-pretrained `yolov8n.pt`, filtered to `person` and `dog`. This is a baseline and still requires real Pi camera validation.

`node_runtime/detection/visual/ensemble.py` reads the deployment manifest, verifies local artifact checksums, loads the configured specialists, and runs them sequentially on each frame. Sequential inference is intentional for the Pi's CPU and memory budget. New specialists are added through the manifest and do not require rewriting the runtime processor.

## Model lifecycle and responsibilities

- `ml_pipeline/registry/model_registry.py`: versioned model metadata and lifecycle states.
- `models/deployed/manifest.json`: currently selected runtime artifacts and class filters.
- `models/deployed/manifest.json -> profiles.pi5_edge`: current on-device execution selection.
- `models/deployed/manifest.json -> profiles.cloud_full`: planned future cloud model selection; it is not an active cloud inference service and has no runtime model IDs until a cloud executor is implemented.
- `ml_pipeline/adapters/`: framework-specific adapters for normalized predictions.
- `ml_pipeline/schema/`: shared prediction contracts.
- `ml_pipeline/taxonomy/`: stable semantic labels independent of upstream model class IDs.
- `ml_pipeline/inference/router.py`: model routing and resource-budget abstraction.

## Edge now, cloud later

The deployment profile separates model selection from the runtime. In the current phase, Pi inference remains local and internet-independent. In the future, `cloud_full` can contain larger video-action and audio specialists while `pi5_edge` retains compact detectors for immediate, low-latency decisions. A cloud inference provider, transport contract, authentication, timeout policy, and fallback behaviour must be implemented before that profile is activated. The current profile file is a preparation/configuration contract, not a claim that cloud inference already exists.

Do not move the only working threat detector off the Pi. Edge inference must continue if the central backend or cloud is unavailable.

## Dataset integration

Dataset contracts are stored under `datasets/manifests/`. They contain metadata and local paths only; no dataset assets are downloaded by these manifests. Every dataset must specify modality, task, annotation format, splits, canonical classes, taxonomy mapping, provenance, and licence.

Current manifests cover:

- Existing local weapon dataset (one class in its current YAML; audit compatibility before fine-tuning a two-class weapon model).
- Person/dog detection (waiting for an approved local labelled dataset).
- Human video actions (future temporal dataset and adapter).
- Audio events (future audio dataset and adapter).

See `docs/ML_DATASETS_AND_TRAINING.md` before adding data.

## Training location and safety

The current training target is the Raspberry Pi, not Box. Training is never run by the node runtime automatically. `ml_pipeline/training/train_from_manifest.py` reads `training_jobs.json`, validates that datasets and weights already exist locally, and defaults to validation-only. Real training requires both `--execute` and `ML_TRAINING_ENABLED=true`, runs with CPU-oriented Pi settings, and writes only to the git-ignored `models/working/training_runs/`. It never overwrites deployed checkpoints or downloads datasets/weights.

Audio and video use separate task-specific trainers; the YOLO object-detection trainer must not be reused for temporal video or audio classification.

## Detection and deterrence

The current visual runtime can detect person and dog using the local COCO baseline. `ThreatAssessor` classifies these as presence events. `ResponseSelector` only considers configured target labels. Speaker output is separately gated by `SPEAKER_ENABLED`; it defaults off until a physical speaker is installed and tested.

The speaker controller generates a short, low-amplitude audible warning locally, applies a cooldown, and returns actual playback metadata. It does not claim playback success when `aplay` or the output device is unavailable. The Telegram notifier reports a real playback start, nominal frequency range, duration, and emission count. It explicitly notes that acoustic sound pressure is not measured. No ultrasonic or deliberately painful output is used.
