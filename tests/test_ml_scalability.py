"""Static contract tests for scalable AWARESPAN model and dataset manifests."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_pi_profile_uses_existing_specialist_artifacts():
    manifest = _read("models/deployed/manifest.json")
    profile = manifest["profiles"]["pi5_edge"]
    assert profile["execution_target"] == "edge"
    assert profile["model_ids"] == ["awarespan-weapon-yolov8n", "awarespan-general-yolov8n"]
    entries = {item["model_id"]: item for item in manifest["active_models"]}
    for model_id in profile["model_ids"]:
        item = entries[model_id]
        assert item["enabled"] is True
        assert (ROOT / item["artifact_path"]).is_file()
    assert entries["awarespan-general-yolov8n"]["allowed_labels"] == ["person", "dog"]


def test_cloud_profile_is_prepared_but_not_claimed_active():
    manifest = _read("models/deployed/manifest.json")
    assert manifest["profiles"]["cloud_full"]["status"] == "planned_not_active"
    planned = manifest["profiles"]["cloud_full"]["planned_model_ids"]
    assert "awarespan-weapon-yolov8l" in planned
    assert "awarespan-general-yolov8m" in planned
    assert "awarespan-human-video-actions" in planned
    assert "awarespan-audio-events" in planned


def test_audio_and_video_datasets_are_contracts_not_downloads():
    audio = _read("datasets/manifests/audio_events.json")
    video = _read("datasets/manifests/human_video_actions.json")
    assert audio["status"] == "PLANNED_DATASET_NOT_PRESENT"
    assert video["status"] == "PLANNED_DATASET_NOT_PRESENT"
    assert audio["download_policy"] == "manual_only_no_automatic_download"
    assert video["download_policy"] == "manual_only_no_automatic_download"


def test_workstation_training_is_explicit_and_outputs_are_staged():
    jobs = _read("ml_pipeline/training/training_jobs.json")
    policy = jobs["execution_policy"]
    assert policy["training_host"] == "dedicated_workstation"
    assert policy["download_datasets"] is False
    assert policy["download_weights"] is False
    assert policy["require_explicit_execute_flag"] is True
    assert policy["never_overwrite_deployed_weights"] is True


def test_all_dataset_manifests_validate_without_fetching():
    from ml_pipeline.datasets.manifest_loader import validate_directory
    manifests = validate_directory(ROOT / "datasets" / "manifests", repo_root=ROOT)
    assert len(manifests) == 4
    assert {entry["modality"] for entry in manifests} == {"visual", "audio", "video"}


def test_missing_audio_model_is_not_marked_loaded():
    registry = _read("ml_pipeline/registry/models.json")
    audio = registry["models"]["awarespan-yamnet-audio:1.0.0"]
    assert audio["state"] == "DISCOVERED"
    assert audio["sha256"] == ""
    assert audio["metadata"]["status"] == "BLOCKED_WEIGHTS_NOT_PRESENT"


def test_training_is_confined_to_workstation_package():
    entrypoint = ROOT / "ml_pipeline" / "training" / "train_from_manifest.py"
    assert entrypoint.is_file()
    source = entrypoint.read_text(encoding="utf-8")
    assert "workstation-only" in source.lower()
    assert "Raspberry Pi devices are inference-only" in source
    assert not (ROOT / "pi" / "train_weapon.py").exists()
    assert not (ROOT / "pi" / "train_autonomous.py").exists()


def test_unified_setup_replaces_the_fedora_only_profile():
    setup = ROOT / "scripts" / "setup.sh"
    assert setup.is_file()
    source = setup.read_text(encoding="utf-8")
    assert 'assigned by backend during enrollment' in source
    assert '--node-id' not in source
    assert 'BACKEND_API_KEY' in source
    assert '--production' in source and '--no-production' in source
    assert '--train' in source and '--no-train' in source
    assert 'DEVICE_API_KEY' in source
    assert not (ROOT / "scripts" / "fedora.sh").exists()
    assert not (ROOT / "config" / "fedora.env").exists()


def test_production_installer_excludes_training_and_optional_bot():
    units = {path.name for path in (ROOT / "deployment" / "systemd").glob("*")}
    assert "awarespan-node.service" in units
    assert "awarespan-power-monitor.service" in units
    assert "awarespan-updater.timer" in units
    assert "awarespan-training.service" not in units
    assert "awarespan-bot.service" not in units
