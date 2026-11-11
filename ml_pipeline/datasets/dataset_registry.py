"""
AWARESPAN — Dataset Registry
Persistent JSON registry tracking every dataset's source, status, and training history.
Atomic updates via temp-file + rename to survive crashes and reboots.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.config.settings import get_settings
from shared.logging.logger import get_logger

log = get_logger("ml_pipeline.dataset_registry")


def _resolve_registry_paths():
    settings = get_settings()
    # Check candidates
    candidates = [
        Path(settings.state_dir) / "dataset_registry.json",
        settings.repo_root / "datasets" / "dataset_registry.json",
        Path.home() / "edge-ai" / "dataset_registry.json",
    ]
    for c in candidates:
        if c.exists():
            return c, c.parent / "training_runs.json"

    # Default to repo root / datasets
    base = settings.repo_root / "datasets"
    base.mkdir(parents=True, exist_ok=True)
    return base / "dataset_registry.json", base / "training_runs.json"


REGISTRY_PATH, RUNS_PATH = _resolve_registry_paths()


def _read_json(path: Path) -> Dict:
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            log.warning("Failed to read JSON from %s: %s", path, exc)
    return {}


def _write_json_atomic(path: Path, data: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    tmp.replace(path)


def get_registry() -> Dict[str, Any]:
    return _read_json(REGISTRY_PATH)


def register_dataset(
    dataset_id: str,
    name: str,
    source_url: str,
    source_owner: str = "",
    license_: str = "",
    retrieval_date: str = "",
    annotation_format: str = "",
    source_classes: Optional[List[str]] = None,
    target_task: str = "",
    notes: str = "",
) -> Dict:
    reg = get_registry()
    if dataset_id in reg.get("datasets", {}):
        return reg["datasets"][dataset_id]

    if "datasets" not in reg:
        reg["datasets"] = {}
    if "last_updated" not in reg:
        reg["last_updated"] = datetime.utcnow().isoformat()

    record = {
        "dataset_id": dataset_id,
        "name": name,
        "source_url": source_url,
        "source_owner": source_owner,
        "license": license_,
        "retrieval_date": retrieval_date,
        "annotation_format": annotation_format,
        "source_classes": source_classes or [],
        "target_task": target_task,
        "notes": notes,
        "status": "REGISTERED",
        "archive_file": None,
        "archive_size_bytes": None,
        "archive_sha256": None,
        "extracted_path": None,
        "conversion_adapter": None,
        "conversion_version": None,
        "class_mapping": None,
        "mapping_hash": None,
        "validation_report_path": None,
        "visual_review_path": None,
        "audit_report_path": None,
        "clean_output_path": None,
        "clean_manifest_hash": None,
        "accepted_count": 0,
        "rejected_count": 0,
        "quarantined_count": 0,
        "excluded_count": 0,
        "train_count": 0,
        "valid_count": 0,
        "test_count": 0,
        "training_runs": [],
        "registered_at": datetime.utcnow().isoformat(),
        "last_updated": datetime.utcnow().isoformat(),
    }

    reg["datasets"][dataset_id] = record
    reg["last_updated"] = datetime.utcnow().isoformat()
    _write_json_atomic(REGISTRY_PATH, reg)
    return record


def update_dataset(dataset_id: str, **fields) -> bool:
    reg = get_registry()
    if dataset_id not in reg.get("datasets", {}):
        return False

    reg["datasets"][dataset_id].update(fields)
    reg["datasets"][dataset_id]["last_updated"] = datetime.utcnow().isoformat()
    reg["last_updated"] = datetime.utcnow().isoformat()
    _write_json_atomic(REGISTRY_PATH, reg)
    return True


def get_dataset(dataset_id: str) -> Optional[Dict]:
    reg = get_registry()
    return reg.get("datasets", {}).get(dataset_id)


def get_datasets_by_status(status: str) -> List[Dict]:
    reg = get_registry()
    return [ds for ds in reg.get("datasets", {}).values() if ds.get("status") == status]


def get_eligible_datasets(task: str) -> List[Dict]:
    reg = get_registry()
    return [
        ds for ds in reg.get("datasets", {}).values()
        if ds.get("status") == "TRAINING_ELIGIBLE" and ds.get("target_task") == task
    ]


def add_training_run_to_dataset(dataset_id: str, run_id: str) -> bool:
    reg = get_registry()
    if dataset_id not in reg.get("datasets", {}):
        return False
    ds = reg["datasets"][dataset_id]
    if "training_runs" not in ds:
        ds["training_runs"] = []
    if run_id not in ds["training_runs"]:
        ds["training_runs"].append(run_id)
    ds["last_updated"] = datetime.utcnow().isoformat()
    reg["last_updated"] = datetime.utcnow().isoformat()
    _write_json_atomic(REGISTRY_PATH, reg)
    return True


def get_runs() -> List[Dict]:
    return _read_json(RUNS_PATH).get("runs", [])


def append_run(run_record: Dict) -> str:
    runs_data = _read_json(RUNS_PATH)
    if "runs" not in runs_data:
        runs_data["runs"] = []

    run_id = run_record.get("run_id") or f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    run_record["run_id"] = run_id
    run_record["recorded_at"] = datetime.utcnow().isoformat()

    runs_data["runs"].append(run_record)
    runs_data["last_updated"] = datetime.utcnow().isoformat()
    _write_json_atomic(RUNS_PATH, runs_data)
    return run_id


def print_registry_summary():
    reg = get_registry()
    runs = get_runs()
    datasets = reg.get("datasets", {})

    print("\n=== AWARESPAN Dataset Registry Summary ===")
    print(f"Total datasets: {len(datasets)}")
    print(f"Total training runs: {len(runs)}")
    print(f"Last updated: {reg.get('last_updated', 'never')}\n")

    status_counts = {}
    for ds in datasets.values():
        s = ds.get("status", "UNKNOWN")
        status_counts[s] = status_counts.get(s, 0) + 1

    print("By status:")
    for s, c in sorted(status_counts.items()):
        print(f"  {s}: {c}")

    print("\nDatasets eligible for training:")
    for ds in datasets.values():
        if ds.get("status") == "TRAINING_ELIGIBLE":
            print(f"  [{ds['dataset_id']}] {ds['name']} — {ds['accepted_count']} samples")
    print()


if __name__ == "__main__":
    print_registry_summary()
