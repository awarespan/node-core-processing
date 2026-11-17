# Raspberry Pi ML Runtime Quick Start

This workflow uses model weights already tracked by the repository. It does not download datasets or weights.

## 1. Pull the repository

```bash
cd /path/to/node-core-processing
git pull --ff-only origin main
```

Preserve the existing `/etc/awarespan/node.env` file. Do not replace it with `.env.example`.

## 2. Validate the profile and local weights

```bash
python3 scripts/validate_ml_deployment.py --profile pi5_edge
python3 -m ml_pipeline.datasets.manifest_loader
```

The current edge profile uses: the existing fine-tuned weapon checkpoint (`gun`, `knife`) and the local COCO-pretrained YOLOv8n baseline filtered to `person`, `dog`. Person/dog uses the COCO baseline immediately; it does not require a new fine-tuning run to start inference. It still requires field validation with the actual camera. The detector recognises the COCO `person` class; it does not infer gender.

## 3. Set runtime environment

In the existing untracked Pi environment file, confirm:

```dotenv
ML_DEPLOYMENT_PROFILE=pi5_edge
ML_DEPLOYMENT_MANIFEST=models/deployed/manifest.json
ML_TRAINING_ENABLED=false
SPEAKER_ENABLED=false
SIREN_ENABLED=false
PRESENCE_DETERRENCE_ENABLED=false
DETERRENCE_TARGET_LABELS=person
```

Keep all speaker flags disabled until the physical transducer/amplifier is verified and acoustic SPL is measured at representative listener positions. ALSA card detection and digital waveform amplitude do not establish a safe SPL.

## 4. Start inference

```bash
sudo systemctl restart awarespan-node.service
sudo systemctl status awarespan-node.service --no-pager
sudo journalctl -u awarespan-node.service -f
```

At startup the runtime loads the `pi5_edge` profile. It verifies each model file's checksum and loads specialists sequentially to limit Pi CPU/memory pressure. If the person/dog model is absent or fails to load, startup logs the issue and continues with the weapon model if that model is available. If no selected visual model loads, startup fails rather than silently pretending inference is active.

## 5. Pi-side training (only after data is ready)

Training is separate from the node runtime. The runner validates local files and defaults to dry-run. It refuses URLs, missing split paths, and a class-name mismatch. It writes only to the ignored `models/working/training_runs/` directory.

```bash
python3 -m ml_pipeline.training.train_from_manifest --job person_dog_finetune_pi
```

The person/dog dataset does not currently exist in the repository; this command therefore reports that it is not ready. After an approved dataset is placed locally, audited, and both its dataset manifest and training job status are set to `TRAINING_ELIGIBLE` (with a verified licence), training can be explicitly enabled on the Pi:

```bash
ML_TRAINING_ENABLED=true python3 -m ml_pipeline.training.train_from_manifest --job person_dog_finetune_pi --execute
```

Do not train on the Box workspace. Do not enable training in the always-on node service. New checkpoints remain staged and require evaluation and explicit promotion; deployed weights are never overwritten by this runner.

## 6. Speaker installation later

The code can generate a short, local audible alert tone, but audio output is disabled by default. After physically verifying the transducer/amplifier, measure acoustic SPL with calibrated equipment at representative listener positions. Only then should an operator deliberately enable both `SPEAKER_ENABLED=true` and `SIREN_ENABLED=true`; presence-triggered alerts additionally require `PRESENCE_DETERRENCE_ENABLED=true`. Do not target dogs with audio.

The default pitch variation is within 900–1100 Hz for up to 1.5 seconds at 8% digital full scale, with a 30-second cooldown. This is a generic audible alert-pitch range, not a research-validated deterrence/irritation band. The waveform is one randomized single-frequency tone per emission, not a sweep. Randomization is not proven to prevent habituation. Acoustic SPL is not measured by the software. The cumulative emission counter persists under `/var/lib/awarespan/deterrence_state.json`.

## 7. Current limitations

- The general COCO model is a starting person/dog detector, not a dedicated, field-validated AWARESPAN animal/person model.
- No usable YAMNet weight file is currently present; the YAMNet registry entry is disabled.
- The `AudioThreatAdapter` DSP heuristic is not a trained audio neural network and is not enabled in the runtime threat path.
- Temporal video action recognition has a plugin contract and dataset schema only; no video model weights or trainer are currently available.
- `cloud_full` is a planning profile only. No cloud inference executor is implemented yet. The Pi remains the active inference target.
