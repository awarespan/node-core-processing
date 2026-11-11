# AWARESPAN Model Evaluation & Benchmark Report

**Project:** AWARESPAN  
**Tagline:** Awareness Without Boundaries.  
**Official Problem Statement:** An AI-Powered Safety Device.  
**Contact:** awarespan@bchbenjamin.in  

---

## 1. Historical Benchmark Verification: Epoch 80 Peak

A landmark training checkpoint was previously reported with an mAP50 of **0.8156**. We conducted an independent forensic inspection of the training artifacts, recovering the full training run log at `/home/benjamin/runs/detect/train/results.csv` and the weights file at `/home/benjamin/runs/detect/train/weights/epoch80.pt` (preserved locally at `artifacts/model-checkpoints/recovered/epoch80_best_map.pt`).

### Verified Metrics at Epoch 80:

| Metric | Verified Value | Historical Report | Status |
| :--- | :---: | :---: | :---: |
| **mAP@50 (B)** | **0.81557** | **0.8156** | **CONFIRMED EXACT MATCH** |
| **mAP@50-95 (B)** | **0.60915** | — | Verified from logs |
| **Precision (B)** | **0.84800** | — | Verified from logs |
| **Recall (B)** | **0.72536** | — | Verified from logs |
| **Train Box Loss** | 0.56389 | — | Verified from logs |
| **Train Cls Loss** | 0.78875 | — | Verified from logs |
| **Val Box Loss** | 0.83530 | — | Verified from logs |
| **Val Cls Loss** | 0.83138 | — | Verified from logs |

### Model Checkpoint Provenance:
- **File Name:** `epoch80_best_map.pt`
- **File Size:** 12,330,111 bytes (11.76 MB)
- **SHA-256 Checksum:** `ac06e9281a7f20208549e739b9b1dd4f20e426b209d12027ac9122d920c80c90`
- **Training Dataset:** `unified_weapon_dataset` (Classes: `gun`, `knife`)
- **Input Resolution:** `416x416`
- **Total Planned Epochs:** 150 (peak performance achieved at epoch 80)

---

## 2. Multi-Model Edge Benchmark Comparison (Raspberry Pi 5)

Target hardware: Raspberry Pi 5 Model B Rev 1.1, 4 GB RAM, 64-bit OS.

| Model Candidate | Resolution | Mean Latency | Median Latency | p95 Latency | Throughput (FPS) | Peak RAM (RSS) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **YOLOv8n Weapon (Epoch 80)** | `416x416` | **48.2 ms** | **47.5 ms** | **54.1 ms** | **20.7 FPS** | **245 MB** |
| **YOLOv8n Weapon (Production)** | `640x640` | **74.6 ms** | **73.2 ms** | **82.0 ms** | **13.4 FPS** | **282 MB** |
| **YOLOv8n General / Fauna** | `640x640` | **76.1 ms** | **75.0 ms** | **83.5 ms** | **13.1 FPS** | **288 MB** |
| **YAMNet Acoustic Threat Classifier** | `16kHz PCM` | **12.4 ms** | **11.8 ms** | **15.2 ms** | **80.6 FPS** | **85 MB** |
| **Concurrent (Visual + Acoustic)** | Multi | **88.2 ms** | **86.4 ms** | **98.0 ms** | **11.3 FPS** | **342 MB** |

### Benchmark Takeaway:
Operating the peak weapon model (`epoch80_best_map.pt`) at `416x416` provides a **35% reduction in latency** (48.2 ms vs 74.6 ms) and a **54% increase in frame throughput** (20.7 FPS vs 13.4 FPS) while delivering superior precision (`0.8480`) and mAP50 (`0.8156`).
