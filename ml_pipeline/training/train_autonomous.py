"""Deprecated compatibility entry point.

Use `python -m ml_pipeline.training.train_from_manifest --job JOB_ID`.
Training is Pi-only, local-files-only, dry-run by default, and explicitly gated.
"""
from ml_pipeline.training.train_from_manifest import main, run_job

if __name__ == "__main__":
    main()
