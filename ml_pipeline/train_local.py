"""Compatibility entry point for manifest-driven local training.

No implicit dataset or weight downloads are performed.
"""
from ml_pipeline.training.train_from_manifest import main

if __name__ == "__main__":
    main()
