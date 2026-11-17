#!/usr/bin/env python3
"""Validate selected Pi deployment artifacts and checksums without ML dependencies."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="pi5_edge")
    args = parser.parse_args()
    manifest_path = ROOT / "models" / "deployed" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    profile = manifest.get("profiles", {}).get(args.profile)
    if not isinstance(profile, dict):
        raise SystemExit(f"Unknown deployment profile: {args.profile}")
    if profile.get("execution_enabled") is False:
        raise SystemExit(f"Profile {args.profile} is a planning contract and cannot be executed")
    if profile.get("status") == "planned_not_active":
        raise SystemExit(f"Profile {args.profile} is not active")
    entries = {item.get("model_id"): item for item in manifest.get("active_models", [])}
    model_ids = profile.get("model_ids", [])
    if not model_ids:
        raise SystemExit(f"Profile {args.profile} contains no model IDs")

    failures = []
    print(f"AWARESPAN deployment profile: {args.profile}")
    for model_id in model_ids:
        item = entries.get(model_id)
        if not item or not item.get("enabled", True):
            failures.append(f"{model_id}: missing or disabled in manifest")
            continue
        artifact = Path(item.get("artifact_path", ""))
        if not artifact.is_absolute():
            artifact = ROOT / artifact
        if not artifact.is_file():
            failures.append(f"{model_id}: artifact missing: {artifact}")
            continue
        expected = str(item.get("sha256", "")).lower()
        actual = sha256(artifact)
        if expected and actual != expected:
            failures.append(f"{model_id}: SHA-256 mismatch")
            continue
        labels = ", ".join(item.get("allowed_labels", [])) or "all model labels"
        print(f"  OK  {model_id}: {artifact.relative_to(ROOT)} ({artifact.stat().st_size:,} bytes; labels: {labels})")

    if failures:
        print("Validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print("All selected model artifacts exist and match their declared checksums.")
    print("This validates files and configuration only; model loading and Pi inference still require the Pi runtime environment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
