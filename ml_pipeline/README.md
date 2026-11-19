# ML pipeline — models, datasets, training and promotion

`ml_pipeline/` is the workstation-side model lifecycle. The production Raspberry Pi is inference-only. The setup wizard installs the correct dependency set for the selected host:

```bash
./scripts/setup.sh --profile linux --train
```

The supported interpreter is CPython 3.11. For a manual install, create the venv with `python3.11`, install the CPU PyTorch pair first, then the pinned requirements and the separately pinned Ultralytics wheel:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip==24.3.1
python -m pip install --only-binary=:all: --index-url https://download.pytorch.org/whl/cpu -r requirements/torch-cpu.txt
python -m pip install --only-binary=:all: -r requirements/training.txt
python -m pip install --only-binary=:all: --no-deps -r requirements/ultralytics.txt
```

All direct runtime, development and training requirements are exact pins. `constraints-py311.txt` pins their shared transitive dependencies. Ultralytics is installed with `--no-deps` because it declares the GUI `opencv-python` distribution, while AWARESPAN uses `opencv-python-headless`; its other required dependencies are explicitly listed and pinned in `runtime.txt`. For inference-only hosts, use `requirements/runtime.txt`; for workstation development/tests without training extras, use `requirements/dev.txt`.

## Current deployed models

| Model | Artifact | Labels / scope | Status |
|---|---|---|---|
| Weapon detector | `shared/models/yolov8n_best_weapon.pt` | `gun`, `knife` | Current weapon deployment artifact |
| General detector | `shared/models/yolov8n.pt` | COCO model, runtime allow-list `person`, `dog` | Provisional general baseline; field validation pending |

`models/deployed/manifest.json` is the deployment source of truth for profile selection, artifact paths, checksums, input size and class allow-lists. The registry may also mention candidate or historical models whose weight files are not present; those are not deployable. In particular, no YAMNet weights or temporal action-recognition weights are currently deployed. The audio adapter is a spectral DSP baseline, not a trained YAMNet model.

Verify committed files and checksums:

```bash
python ml_pipeline/tools/validate_deployment.py --profile pi5_edge
```

Run a real model-load and inference smoke test (requires Ultralytics/PyTorch and may be CPU-intensive):

```bash
python ml_pipeline/tools/smoke_test_models.py
```

A checksum pass confirms file identity, not successful inference, accuracy or real-time performance. Re-benchmark on the actual target hardware before making latency or safety claims.

## Training prerequisites and current readiness

Training is not an automatic step. It requires all of the following:

1. A non-Pi Linux workstation with the training dependencies installed.
2. A locally available dataset; the trainer does not download datasets or weights.
3. Dataset provenance, licence, splits and label mapping audited.
4. A job in `ml_pipeline/training/training_jobs.json` with an eligible status.
5. `ML_TRAINING_ENABLED=true` in the private environment file.
6. An explicit `--execute` argument to the trainer.

Current job statuses in `training_jobs.json` are authoritative. At this checkout, the weapon fine-tuning job is waiting for a two-class `gun`/`knife` label mapping, the person/dog job is waiting for its approved dataset, and audio/video jobs are blocked pending adapters and datasets. Therefore installing training dependencies alone will not make these jobs executable.

Inspect and validate a job without training:

```bash
python -m ml_pipeline.training.train_from_manifest --help
python -m ml_pipeline.training.train_from_manifest --job weapon_finetune_workstation
```

Only after the dataset and job have been reviewed and marked `TRAINING_ELIGIBLE`, enable training in the private node/workstation configuration and explicitly execute the approved job using the CLI options shown by `--help`. The runner rejects Raspberry Pi/ARM hosts for execution and requires `ML_TRAINING_ENABLED=true`.

## Output and promotion

Training runs and checkpoints are staged under the ignored `models/working/training_runs/` directory. They do not overwrite deployed weights. Before promotion:

- evaluate on a held-out, labelled dataset;
- inspect class mapping and failure cases;
- record dataset/model provenance and licence;
- compute SHA-256;
- copy the approved artifact into `shared/models/`;
- update `models/deployed/manifest.json` and validate the profile;
- commit the intentionally promoted model artifact and metadata.

See [`training/README.md`](training/README.md), [`../docs/MODEL_REGISTRY.md`](../docs/MODEL_REGISTRY.md), [`../docs/MODEL_ACQUISITION.md`](../docs/MODEL_ACQUISITION.md), and [`../docs/MODEL_EVALUATION.md`](../docs/MODEL_EVALUATION.md).
