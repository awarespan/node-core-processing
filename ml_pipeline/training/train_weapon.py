"""Compatibility entry point; all training is manifest-driven and local-only."""
from ml_pipeline.training.train_from_manifest import main, run_job


def train_weapon(job_id: str = "weapon_finetune_pi", execute: bool = False):
    """Run the registered weapon job; never downloads datasets or weights."""
    return run_job(job_id, execute=execute)


if __name__ == "__main__":
    main()
