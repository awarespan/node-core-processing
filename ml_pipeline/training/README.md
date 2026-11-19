# Model training (workstation only)

This package contains the model-training entrypoints. Production Raspberry Pi nodes perform inference only; the Pi installer does not install or enable a training service.

Use the dedicated training dependency set from the repository root. The Pi remains inference-only:

The supported interpreter is CPython 3.11. Create the environment and install the pinned CPU stack from the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip==24.3.1
python -m pip install --only-binary=:all: --index-url https://download.pytorch.org/whl/cpu -c requirements/constraints-py311.txt -r requirements/torch-cpu.txt
python -m pip install --only-binary=:all: -r requirements/training.txt
python -m pip install --only-binary=:all: --no-deps -r requirements/ultralytics.txt
python -m ml_pipeline.training.train_from_manifest --help
```

Inspect `training_jobs.json` and the dataset manifests before a run. Keep datasets, intermediate runs and checkpoints out of Git unless an artifact is intentionally promoted for deployment. Promoted `.pt` weights belong in `shared/models/` and must have a SHA-256 entry in `models/deployed/manifest.json`.
