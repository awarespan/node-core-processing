# Raspberry Pi ML Runtime Quick Start

This workflow uses model weights already tracked by the repository. It does not download datasets or weights.

## 1. Pull the repository

```bash
cd /path/to/node-core-processing
git pull --ff-only origin main
```

Preserve any existing legacy `/etc/awarespan/node.env` values. The setup wizard migrates them into the single repository-root `.env`; do not overwrite an existing `.env` with a blank template.

## 2. Validate the profile and local weights

```bash
python3 ml_pipeline/tools/validate_deployment.py --profile pi5_edge
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

## 5. Training policy

The production Pi is inference-only. Do not install training dependencies, enable `ML_TRAINING_ENABLED`, or run training jobs on the Pi. Dataset preparation, training, evaluation and checkpoint promotion happen on a workstation; see [`ml_pipeline/training/README.md`](../ml_pipeline/training/README.md). Only validated, checksummed deployment weights are copied into `shared/models/`.

## 6. Speaker installation later

The code can generate a short, local audible alert tone, but audio output is disabled by default. After physically verifying the transducer/amplifier, measure acoustic SPL with calibrated equipment at representative listener positions. Only then should an operator deliberately enable both `SPEAKER_ENABLED=true` and `SIREN_ENABLED=true`; presence-triggered alerts additionally require `PRESENCE_DETERRENCE_ENABLED=true`. Do not target dogs with audio.

The default pitch variation is within 900–1100 Hz for up to 1.5 seconds at 8% digital full scale, with a 30-second cooldown. This is a generic audible alert-pitch range, not a research-validated deterrence/irritation band. The waveform is one randomized single-frequency tone per emission, not a sweep. Randomization is not proven to prevent habituation. Acoustic SPL is not measured by the software. The cumulative emission counter persists under `/var/lib/awarespan/deterrence_state.json`.

## 7. Current limitations

- The general COCO model is a starting person/dog detector, not a dedicated, field-validated AWARESPAN animal/person model.
- No usable YAMNet weight file is currently present; the YAMNet registry entry is disabled.
- The `AudioThreatAdapter` DSP heuristic is not a trained audio neural network and is not enabled in the runtime threat path.
- Temporal video action recognition has a plugin contract and dataset schema only; no video model weights or trainer are currently available.
- `cloud_full` is a planning profile only. No cloud inference executor is implemented yet. The Pi remains the active inference target.
