#!/usr/bin/env python3
"""
Dataset registry for SIP Pi.
Persistent JSON registry tracking every dataset's source, status, and training history.
Atomic updates via temp-file + rename to survive crashes and reboots.
"""

import os
import json
import hashlib
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

HOME = os.path.expanduser("~")
REGISTRY_PATH = os.path.join(HOME, "edge-ai", "dataset_registry.json")
RUNS_PATH = os.path.join(HOME, "edge-ai", "training_runs.json")
STATE_DIR = os.path.join(HOME, "edge-ai", "state")
os.makedirs(STATE_DIR, exist_ok=True)


# ── Atomic JSON helpers ───────────────────────────────────────────────────────

def _read_json(path: str) -> Dict:
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}


def _write_json_atomic(path: str, data: Dict) -> None:
    """Write JSON atomically via temp file + rename."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


# ── Registry API ──────────────────────────────────────────────────────────────

def get_registry() -> Dict[str, Any]:
    """Load the dataset registry."""
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
    """
    Register a new dataset source. Returns the dataset record.
    """
    reg = get_registry()
    if dataset_id in reg.get("datasets", {}):
        return reg["datasets"][dataset_id]

    if "datasets" not in reg:
        reg["datasets"] = {}
    if "last_updated" not in reg:
        reg["last_updated"] = datetime.now().isoformat()

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
        "registered_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
    }

    reg["datasets"][dataset_id] = record
    reg["last_updated"] = datetime.now().isoformat()
    _write_json_atomic(REGISTRY_PATH, reg)
    return record


def update_dataset(dataset_id: str, **fields) -> bool:
    """Update fields on an existing dataset record."""
    reg = get_registry()
    if dataset_id not in reg.get("datasets", {}):
        return False

    reg["datasets"][dataset_id].update(fields)
    reg["datasets"][dataset_id]["last_updated"] = datetime.now().isoformat()
    reg["last_updated"] = datetime.now().isoformat()
    _write_json_atomic(REGISTRY_PATH, reg)
    return True


def get_dataset(dataset_id: str) -> Optional[Dict]:
    """Get a dataset record by ID."""
    reg = get_registry()
    return reg.get("datasets", {}).get(dataset_id)


def get_datasets_by_status(status: str) -> List[Dict]:
    """Get all datasets with a given status."""
    reg = get_registry()
    return [
        ds for ds in reg.get("datasets", {}).values()
        if ds.get("status") == status
    ]


def get_eligible_datasets(task: str) -> List[Dict]:
    """Get datasets eligible for training a specific task."""
    reg = get_registry()
    return [
        ds for ds in reg.get("datasets", {}).values()
        if ds.get("status") == "TRAINING_ELIGIBLE" and ds.get("target_task") == task
    ]


def add_training_run_to_dataset(dataset_id: str, run_id: str) -> bool:
    """Record that a dataset was used in a training run."""
    reg = get_registry()
    if dataset_id not in reg.get("datasets", {}):
        return False
    ds = reg["datasets"][dataset_id]
    if "training_runs" not in ds:
        ds["training_runs"] = []
    if run_id not in ds["training_runs"]:
        ds["training_runs"].append(run_id)
    ds["last_updated"] = datetime.now().isoformat()
    reg["last_updated"] = datetime.now().isoformat()
    _write_json_atomic(REGISTRY_PATH, reg)
    return True


# ── Training run history ──────────────────────────────────────────────────────

def get_runs() -> List[Dict]:
    """Load the training runs history."""
    return _read_json(RUNS_PATH).get("runs", [])


def append_run(run_record: Dict) -> str:
    """
    Append a new training run record. Returns the run_id.
    Never rewrites existing entries.
    """
    runs_data = _read_json(RUNS_PATH)
    if "runs" not in runs_data:
        runs_data["runs"] = []

    # Assign run ID
    run_id = run_record.get("run_id") or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_record["run_id"] = run_id
    run_record["recorded_at"] = datetime.now().isoformat()

    runs_data["runs"].append(run_record)
    runs_data["last_updated"] = datetime.now().isoformat()
    _write_json_atomic(RUNS_PATH, runs_data)
    return run_id


def get_run(run_id: str) -> Optional[Dict]:
    """Get a specific run by ID."""
    for run in get_runs():
        if run.get("run_id") == run_id:
            return run
    return None


def update_run(run_id: str, **fields) -> bool:
    """Update fields on an existing run record."""
    runs_data = _read_json(RUNS_PATH)
    for run in runs_data.get("runs", []):
        if run.get("run_id") == run_id:
            run.update(fields)
            runs_data["last_updated"] = datetime.now().isoformat()
            _write_json_atomic(RUNS_PATH, runs_data)
            return True
    return False


# ── Query utilities ───────────────────────────────────────────────────────────

def query_datasets(
    status: Optional[str] = None,
    task: Optional[str] = None,
    trained: Optional[bool] = None,
) -> List[Dict]:
    """Query datasets by criteria."""
    reg = get_registry()
    results = list(reg.get("datasets", {}).values())

    if status is not None:
        results = [ds for ds in results if ds.get("status") == status]
    if task is not None:
        results = [ds for ds in results if ds.get("target_task") == task]
    if trained is not None:
        if trained:
            results = [ds for ds in results if ds.get("training_runs")]
        else:
            results = [ds for ds in results if not ds.get("training_runs")]

    return results


def print_registry_summary():
    """Print a human-readable registry summary."""
    reg = get_registry()
    runs = get_runs()
    datasets = reg.get("datasets", {})

    print("\n=== SIP Dataset Registry Summary ===")
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

    print("\nRecent training runs:")
    for run in runs[-5:]:
        outcome = run.get("outcome", "UNKNOWN")
        epochs = run.get("epochs_completed", "?")
        print(f"  [{run['run_id']}] {run.get('model_family','?')} {run.get('target_schema','?')} — "
              f"epochs={epochs} outcome={outcome}")

    print()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "summary":
        print_registry_summary()
    else:
        print_registry_summary()