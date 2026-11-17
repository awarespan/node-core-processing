"""Load and validate AWARESPAN dataset manifests without downloading data."""

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

SUPPORTED_MODALITIES = {"visual", "video", "audio"}
SUPPORTED_TASKS = {
    "object_detection",
    "temporal_action_recognition",
    "audio_event_classification",
}


class DatasetManifestError(ValueError):
    pass


def load_manifest(path: Path, repo_root: Optional[Path] = None) -> Dict:
    path = Path(path).resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetManifestError(f"Cannot read dataset manifest {path}: {exc}") from exc

    required = ("schema_version", "dataset_id", "modality", "task", "format", "status", "license")
    missing = [key for key in required if not payload.get(key)]
    if missing:
        raise DatasetManifestError(f"{path}: missing required fields: {', '.join(missing)}")
    if payload["modality"] not in SUPPORTED_MODALITIES:
        raise DatasetManifestError(f"{path}: unsupported modality {payload['modality']!r}")
    if payload["task"] not in SUPPORTED_TASKS:
        raise DatasetManifestError(f"{path}: unsupported task {payload['task']!r}")
    if not payload.get("classes"):
        raise DatasetManifestError(f"{path}: at least one class is required")

    # Manifests may describe remote provenance, but the actual training data path
    # must remain local. This loader never fetches or follows remote URLs.
    root = Path(repo_root).resolve() if repo_root else path.parents[2]
    local_values = [payload.get("local_data_yaml"), payload.get("local_root")]
    for value in local_values:
        if not value:
            continue
        text = str(value)
        if text.startswith(("http://", "https://", "ftp://")):
            raise DatasetManifestError(f"{path}: remote dataset path is prohibited: {text}")
        candidate = Path(text)
        if candidate.is_absolute():
            candidate = candidate.resolve()
        else:
            candidate = (root / candidate).resolve()
            if root not in candidate.parents and candidate != root:
                raise DatasetManifestError(f"{path}: relative dataset path escapes the repository root: {candidate}")
        payload.setdefault("resolved_local_paths", []).append(str(candidate))

    return payload


def iter_manifests(directory: Path, repo_root: Optional[Path] = None) -> Iterable[Dict]:
    directory = Path(directory)
    seen = set()
    for path in sorted(directory.glob("*.json")):
        entry = load_manifest(path, repo_root=repo_root)
        dataset_id = entry["dataset_id"]
        if dataset_id in seen:
            raise DatasetManifestError(f"Duplicate dataset_id in {directory}: {dataset_id}")
        seen.add(dataset_id)
        yield entry


def validate_directory(directory: Path, repo_root: Optional[Path] = None) -> List[Dict]:
    return list(iter_manifests(directory, repo_root=repo_root))


if __name__ == "__main__":
    import argparse
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Validate local AWARESPAN dataset manifests (no downloads)")
    parser.add_argument("--directory", default=str(root / "datasets" / "manifests"))
    args = parser.parse_args()
    manifests = validate_directory(Path(args.directory), repo_root=root)
    print(f"Validated {len(manifests)} dataset manifest(s); no dataset files were downloaded or opened.")
    for item in manifests:
        print(f"- {item['dataset_id']}: {item['modality']}/{item['task']} [{item['status']}]")
