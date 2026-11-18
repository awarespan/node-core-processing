# AWARESPAN threat testing guide

The production Raspberry Pi performs inference only. Model training and dataset preparation are workstation-side activities. The active edge profile is defined in `models/deployed/manifest.json` and currently uses:

- `shared/models/yolov8n_best_weapon.pt` — fine-tuned gun/knife detector.
- `shared/models/yolov8n.pt` — COCO baseline filtered to person/dog.

The person/dog baseline remains provisional until validated using representative camera footage. A model file and a successful inference call do not establish safety-critical accuracy.

## Fedora software demonstration

Use the documented local fallback rather than legacy Pi scripts:

```bash
./scripts/fedora.sh setup
./scripts/fedora.sh models
./scripts/fedora.sh test

# Terminal 1
./scripts/fedora.sh run

# Terminal 2
./scripts/fedora.sh camera --camera 0 --fps 8
```

For a one-shot fixture-based inference and local queue demonstration:

```bash
./scripts/fedora.sh demo
```

See [`EVALUATION_GUIDE.md`](EVALUATION_GUIDE.md) for the exact scope and limitations.

## Raspberry Pi hardware acceptance

When the Pi is available, verify the actual camera, microphone, GPIO, power/thermal monitor, speaker/amplifier, backend connectivity and sustained inference. Do not claim those hardware paths were tested on Fedora.

Speaker output is fail-closed by default (`SPEAKER_ENABLED=false`, `SIREN_ENABLED=false`, `PRESENCE_DETERRENCE_ENABLED=false`). Do not enable it until the installed speaker/amplifier has been physically verified and acoustic SPL measured at representative listener positions. The current audible tone is not a validated deterrent.

## Training and model promotion

Do not train on the Pi. Run the manifest-driven trainer on a dedicated workstation only, after dataset provenance, licence, labels and splits have been audited. New checkpoints are staged under the ignored training output directory; they do not replace deployed weights automatically. Promote only evaluated, checksummed artifacts into `shared/models/` and update the deployment manifest.
