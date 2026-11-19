# AWARESPAN threat testing guide

The active edge profile is defined in `models/deployed/manifest.json` and currently uses:

- `shared/models/yolov8n_best_weapon.pt` — fine-tuned gun/knife detector.
- `shared/models/yolov8n.pt` — COCO baseline filtered to person/dog.

The person/dog baseline remains provisional until validated using representative camera footage. A model file and a successful inference call do not establish safety-critical accuracy.

## Linux software demonstration

Prepare the host with the unified setup wizard:

```bash
./scripts/setup.sh --profile linux
```

Verify model files, run inference smoke tests and execute the automated tests:

```bash
.venv/bin/python ml_pipeline/tools/validate_deployment.py --profile pi5_edge
.venv/bin/python ml_pipeline/tools/smoke_test_models.py
.venv/bin/python -m pytest -q
```

For production REST demonstration, explicitly enable it during setup and provide the backend's device API key. Use a distinct workstation node ID; never impersonate the physical Pi concurrently. MQTT remains a separately configured integration.

See [`EVALUATION_GUIDE.md`](EVALUATION_GUIDE.md) for runtime and webcam commands.

## Raspberry Pi hardware acceptance

When the Pi is available, verify the actual camera, microphone, GPIO, power/thermal monitor, speaker/amplifier, backend connectivity and sustained inference. Do not claim those hardware paths were tested on a workstation.

Speaker output is fail-closed by default (`SPEAKER_ENABLED=false`, `SIREN_ENABLED=false`, `PRESENCE_DETERRENCE_ENABLED=false`). Do not enable it until the installed speaker/amplifier has been physically verified and acoustic SPL measured at representative listener positions. The current audible tone is not a validated deterrent.

## Training and model promotion

Do not train on the Pi. Run the manifest-driven trainer on a dedicated workstation only, after dataset provenance, licence, labels and splits have been audited. New checkpoints are staged under the ignored training output directory; they do not replace deployed weights automatically. Promote only evaluated, checksummed artifacts into `shared/models/` and update the deployment manifest.
