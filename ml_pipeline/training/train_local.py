"""Compatibility entry point for explicit manifest-driven local training.

No dataset or weights are downloaded. Use --job and optionally --execute.
"""
from ml_pipeline.training.train_from_manifest import main

if __name__ == "__main__":
    main()
