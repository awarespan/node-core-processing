"""Explicit, manifest-driven workstation training jobs.

Production Raspberry Pi nodes are inference-only. This module never downloads
datasets or model weights and defaults to validation-only; real training requires
--execute and ML_TRAINING_ENABLED=true on a workstation.
"""

import argparse
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _validate_local_yolo_dataset(data_yaml: Path) -> Dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required for training-job validation") from exc

    data = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
    if data.get("download"):
        raise ValueError("Dataset YAML contains a download action; automatic downloads are prohibited")
    dataset_root = Path(data.get("path") or data_yaml.parent)
    if not dataset_root.is_absolute():
        dataset_root = (data_yaml.parent / dataset_root).resolve()

    checked = {}
    for split in ("train", "val", "test"):
        value = data.get(split)
        if value is None:
            if split in ("train", "val"):
                raise ValueError(f"Dataset YAML is missing required '{split}' split")
            continue
        values = value if isinstance(value, list) else [value]
        resolved = []
        for item in values:
            item_text = str(item)
            if item_text.startswith(("http://", "https://")):
                raise ValueError(f"Remote dataset path is prohibited: {item_text}")
            path = Path(item_text)
            if not path.is_absolute():
                path = (dataset_root / path).resolve()
            if not path.exists():
                raise FileNotFoundError(f"Local {split} data path does not exist: {path}")
            resolved.append(str(path))
        checked[split] = resolved

    return {"names": data.get("names", []), "nc": data.get("nc"), "splits": checked}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_job(job_id: str, execute: bool = False) -> Dict[str, Any]:
    from shared.config.settings import get_settings

    settings = get_settings()
    root = settings.repo_root
    jobs_path = root / "ml_pipeline" / "training" / "training_jobs.json"
    manifest = _load_json(jobs_path)
    job = manifest.get("jobs", {}).get(job_id)
    if not job:
        raise KeyError(f"Unknown training job: {job_id}")
    status = job.get("status")
    if status not in {"READY_FOR_OPERATOR_REVIEW", "TRAINING_ELIGIBLE"}:
        raise RuntimeError(f"Training job '{job_id}' is not ready: {status}")
    if execute and status != "TRAINING_ELIGIBLE":
        raise RuntimeError("Training is blocked until the dataset has been audited and the job status is TRAINING_ELIGIBLE")
    if job.get("modality") != "visual" or job.get("task") != "object_detection":
        raise NotImplementedError("This runner currently supports local visual object-detection jobs only")

    dataset_manifest_path = _resolve(root, job["dataset_manifest"])
    if not dataset_manifest_path.is_file():
        raise FileNotFoundError(f"Dataset manifest is not present locally: {dataset_manifest_path}")
    dataset_manifest = _load_json(dataset_manifest_path)
    if execute:
        if dataset_manifest.get("status") not in {"TRAINING_ELIGIBLE", "LOCAL_DATASET_READY"}:
            raise RuntimeError(
                f"Dataset manifest is not training-eligible: {dataset_manifest.get('status')}"
            )
        if str(dataset_manifest.get("license", "")).upper() in {
            "", "REQUIRED_BEFORE_TRAINING", "UNKNOWN", "UNVERIFIED"
        }:
            raise RuntimeError("Dataset licence/provenance must be verified before training")

    data_yaml = _resolve(root, job["data_yaml"])
    manifest_yaml = dataset_manifest.get("local_data_yaml")
    if manifest_yaml and _resolve(root, manifest_yaml) != data_yaml:
        raise ValueError("Training job data_yaml does not match the dataset manifest local_data_yaml")
    if not data_yaml.is_file():
        raise FileNotFoundError(f"Dataset YAML is not present locally: {data_yaml}")
    dataset_report = _validate_local_yolo_dataset(data_yaml)
    expected_classes = [str(value).strip().lower() for value in job.get("target_classes", [])]
    actual_names = dataset_report.get("names", [])
    if isinstance(actual_names, dict):
        actual_classes = [str(actual_names[key]).strip().lower() for key in sorted(actual_names, key=lambda k: int(k))]
    else:
        actual_classes = [str(value).strip().lower() for value in actual_names]
    if expected_classes and actual_classes != expected_classes:
        raise ValueError(
            f"Dataset class mapping {actual_classes!r} does not match job target_classes {expected_classes!r}. "
            "Create and audit an explicit local label mapping before training."
        )

    base_weights = _resolve(root, job["base_weights"])
    if not base_weights.is_file():
        raise FileNotFoundError(f"Base weights must already exist locally: {base_weights}")

    report = {
        "job_id": job_id,
        "execute": execute,
        "training_host": platform.machine(),
        "data_yaml": str(data_yaml),
        "dataset": dataset_report,
        "dataset_manifest": {
            "dataset_id": dataset_manifest.get("dataset_id"),
            "status": dataset_manifest.get("status"),
            "license": dataset_manifest.get("license"),
        },
        "base_weights": str(base_weights),
        "base_weights_sha256": _sha256(base_weights),
        "settings_training_enabled": bool(settings.ml_training_enabled),
        "downloads_performed": False,
    }
    if not execute:
        return report
    if not settings.ml_training_enabled:
        raise RuntimeError("Set ML_TRAINING_ENABLED=true in the workstation environment before explicit training")
    machine = platform.machine().lower()
    if machine.startswith(("aarch64", "arm64", "armv7", "armv6")):
        raise RuntimeError("Model training is workstation-only. Raspberry Pi devices are inference-only.")

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Ultralytics is not installed in the workstation training environment") from exc

    run_id = f"{job_id}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    output_root = _resolve(root, manifest["execution_policy"]["output_root"])
    output_root.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(base_weights))
    results = model.train(
        data=str(data_yaml),
        epochs=int(job.get("epochs", 40)),
        imgsz=int(job.get("imgsz", 416)),
        batch=1,
        workers=0,
        device=str(job.get("device", "cpu")),
        project=str(output_root),
        name=run_id,
        exist_ok=False,
        plots=False,
        verbose=True,
    )
    run_dir = output_root / run_id
    best = run_dir / "weights" / "best.pt"
    if not best.is_file():
        raise RuntimeError("Training completed without producing best.pt; deployed weights were not changed")

    metadata = {
        **report,
        "run_id": run_id,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "trained_weights": str(best),
        "trained_weights_sha256": _sha256(best),
        "metrics": str(getattr(results, "results_dict", {})),
        "deployment_status": "STAGED_NOT_DEPLOYED",
    }
    (run_dir / "awarespan_training_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an explicitly selected AWARESPAN ML training job")
    parser.add_argument("--job", required=True, help="Job ID from training_jobs.json")
    parser.add_argument("--execute", action="store_true", help="Actually train; without this flag the command only validates local inputs")
    args = parser.parse_args()
    result = run_job(args.job, execute=args.execute)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
