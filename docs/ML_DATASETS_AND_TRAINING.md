# AWARESPAN Dataset, Weights & Training Workflow

## The rule

Add data and model weights through manifests and registries. Do not hardcode dataset paths or model class IDs throughout the runtime. Do not download datasets or weights on the Box workspace. The workstation-side training command only consumes files already present locally. Production Raspberry Pi nodes never train models.

## Add a visual dataset

1. Put the approved dataset on the dedicated training workstation or attached storage, outside Git where appropriate.
2. Create a JSON manifest under `datasets/manifests/` describing dataset ID, modality, task, format, local `data.yaml`, train/val/test splits, canonical classes, taxonomy IDs, source, provenance, and licence.
3. Audit class names, annotation format, empty labels, train/validation leakage, and licence/redistribution terms.
4. Ensure the YOLO `data.yaml` refers only to local directories. The training runner rejects remote URLs and missing paths, checks the dataset class names against the job’s explicit target classes, and requires the dataset manifest itself to be marked training-eligible with verified licence/provenance before an actual run. Local dataset folders under `datasets/registered/`, `datasets/raw/`, and `datasets/processed/` are Git-ignored.
5. Add or update a job in `ml_pipeline/training/training_jobs.json`. Use a new job ID for each task/profile.
6. Run validation first with a job whose local dataset is present, for example: `python3 -m ml_pipeline.training.train_from_manifest --job weapon_finetune_workstation`. This is dry-run by default. The person/dog job remains blocked until its dataset exists and has been audited.
7. After the person/dog dataset is installed locally, audited, its dataset manifest licence/status is verified, and both the dataset manifest and job status are changed to `TRAINING_ELIGIBLE`, run training on a dedicated workstation only: set `ML_TRAINING_ENABLED=true` in that workstation environment and execute `python3 -m ml_pipeline.training.train_from_manifest --job person_dog_finetune_workstation --execute`.
8. Review the generated weights, evaluation metrics, model class map, latency, memory, and checksum. Training outputs are staged under `models/working/training_runs/`; they are not automatically deployed.
9. Promote an approved artifact by adding a new versioned registry entry and updating a deployment profile after validation. Never overwrite the current deployed checkpoint in place.

The current `Samples/weapon-detection-1/data.yaml` declares a single `weapon` class. It is not automatically compatible with the active two-class (`gun`, `knife`) checkpoint. Audit or remap labels before training.

## Add a model weight

1. Add a model entry to the model registry with model ID, semantic classes, framework, modality, task, exact artifact path, version, source/revision, licence, checksum, input requirements, and validation status.
2. Stage weights under `models/working/` (git-ignored) during evaluation. Do not commit large training checkpoints as ordinary source files.
3. Verify checksum, model loading, class names, test metrics, latency, CPU/RAM, and licence.
4. Add the artifact to `models/deployed/manifest.json` only after review. Define an allow-list for the model's output labels so unrelated pretrained classes cannot trigger AWARESPAN actions.
5. Include the model ID in `profiles.pi5_edge` for Pi inference, `profiles.cloud_full` for future cloud inference, or both.
6. Retain the previous artifact and manifest for rollback.

## Audio and video

Audio and video are separate learning problems. They need task-specific data contracts and adapters:

- Audio: labelled audio segments, sample rate, channel count, clip duration, class mapping, and background/noise negatives. The existing runtime `AudioClassifier` is currently a placeholder; the YAMNet registry entry is disabled because the referenced weight file is not present.
- Video: temporally grouped clips or frame sequences with sequence-level annotations. A collection of independent still images is not a substitute for temporal action labels.

Dataset paths may be relative to the repository or absolute paths on workstation-attached local storage; remote URLs are rejected by the training runner. The manifests `audio_events.json` and `human_video_actions.json` are prepared as schemas only. They do not claim that models or datasets are present. Implement dedicated training and inference adapters before enabling these profiles.

## Edge/cloud split

- `pi5_edge`: compact models for low-latency local detection and operation during internet loss.
- `cloud_full`: future, larger specialists for high-capacity video/audio reasoning and historical analysis.
- The Pi must retain a functional lightweight detector and local threat response. Cloud outages must not stop the node.
- Cloud routing is not active in this repository yet; add it only with an authenticated provider interface, explicit timeout/fallback policy, and deployment tests.

## Person/dog deterrence hardware preparation

The current COCO `shared/models/yolov8n.pt` baseline is selected for `person` and `dog` detection by the Pi profile. Validate detections with the actual Pi camera before relying on it. Speaker output is fail-closed by default (`SPEAKER_ENABLED=false`, `SIREN_ENABLED=false`, `PRESENCE_DETERRENCE_ENABLED=false`). Do not enable it until the installed speaker/amplifier has been physically verified and acoustic SPL measured at the relevant positions. The current 900–1100 Hz range is only a generic audible alert-pitch range; it is not a research-validated deterrent or irritation band. A fresh pitch is selected per warning, but this does not prove that habituation is prevented. The current waveform is a short single-frequency tone, not a sweep. Digital amplitude is not an SPL limit.

The cumulative emission count is persisted under the configured state directory so it survives a node-runtime restart. Telegram deterrence notices are emitted only when the playback process successfully starts. Each notice includes the detected target, emission count, nominal frequency range, and duration.
