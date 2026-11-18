# ML development and model lifecycle

`ml_pipeline/` is the workstation-side ML workspace. It is not imported as a production training service on the Raspberry Pi.

- `training/` — model training jobs, checkpoint resume and training configuration.
- `datasets/` — dataset registration, acquisition, manifest validation and audits.
- `evaluation/` — offline batch evaluation.
- `inference/` and `adapters/` — reusable model adapters and benchmark utilities.
- `registry/`, `taxonomy/`, `schema/` — model metadata and output contracts.
- `packaging/` — deployment artifact packaging and release metadata.

Install training dependencies on a workstation:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/training.txt
```

Training entrypoints live under `ml_pipeline/training/`. They must not be invoked by the production Pi installer. Export a validated checkpoint, package it, then update the deployed model manifest and checksum before deploying it.
