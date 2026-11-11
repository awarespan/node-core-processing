# AWARESPAN Threat & Safety Taxonomy Specification

**Project:** AWARESPAN  
**Tagline:** Awareness Without Boundaries.  
**Official Problem Statement:** An AI-Powered Safety Device.  
**Contact:** awarespan@bchbenjamin.in  
**Taxonomy Identifier:** `awarespan-threat-taxonomy`  
**Current Version:** `1.0.0`  

---

## 1. Overview & Architectural Principles

The AWARESPAN Threat Taxonomy provides a standardized, model-agnostic, and modality-independent representation of safety events. Individual machine learning models (YOLO, YAMNet, 3D-CNN action classifiers) emit raw framework labels, which are mapped to stable hierarchical taxonomy identifiers.

### Key Rules:
1. **Objective Evidence Over Subjective Profiling**: Detections represent physical objects (e.g. `weapon.firearm.handgun`) or objective kinetic events (e.g. `human_activity.distress.fall`). Appearance-based suspicion classification is strictly forbidden.
2. **Fauna Presence Is Not Inherent Danger**: General animal detections (`animal.wildlife.general`) default to passive logging. Audible deterrence is never activated unless an animal is identified as a dangerous predator near humans or exhibits critical boundary proximity.
3. **Multi-Modal Extensibility**: Supports visual bounding boxes, audio spectrogram events, and temporal action durations without shoehorning non-spatial events into rectangular coordinates.

---

## 2. Taxonomy Hierarchy & Categories

| Category ID | Display Name | Primary Modalities | Description |
| :--- | :--- | :--- | :--- |
| `weapon` | Weapons & Implements | Visual, Infrared | Visible firearms, bladed weapons, and destructive tools requiring rapid response. |
| `human_activity` | Human Activity & Distress | Visual (Temporal) | Physical altercations, sudden falls, and medical collapse. |
| `animal` | Wildlife & Animal Presence | Visual | Passive and hazardous fauna monitoring near human safety zones. |
| `hazard` | Fire & Environmental Hazards | Visual, Thermal | Open flame, combustion smoke plumes, and environmental dangers. |
| `intrusion` | Perimeter Security | Visual (Spatial) | Unauthorized tripwire crossings and restricted zone incursions. |
| `audio` | Acoustic Threat Events | Acoustic | Impulse shockwaves (gunshots), vocal distress (screams), glass shatter, alarms. |

---

## 3. Standard Class Specifications (v1.0.0)

| Stable Class ID | Modality | Task | Threat Tier | Default Conf | Evidence Criteria | Allowed Actions |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| `weapon.firearm.handgun` | Visual | Object Detection | 2 | 0.40 | Single high-confidence box or multi-frame persistence | `cloud_alert`, `telegram_alert`, `strobe` |
| `weapon.firearm.rifle` | Visual | Object Detection | 2 | 0.40 | Long-barrel firearm with shoulder stock | `cloud_alert`, `telegram_alert`, `strobe`, `siren` |
| `weapon.edged.knife` | Visual | Object Detection | 2 | 0.45 | Exposed blade in hand or ready posture | `cloud_alert`, `telegram_alert`, `strobe` |
| `weapon.edged.machete` | Visual | Object Detection | 2 | 0.40 | Large bladed tool (>25cm) in monitored zone | `cloud_alert`, `telegram_alert`, `strobe`, `siren` |
| `human_activity.violence.fighting` | Visual | Action Recognition | 2 | 0.60 | Reciprocal striking / grappling over >=1.5s window | `cloud_alert`, `telegram_alert`, `strobe` |
| `human_activity.distress.fall` | Visual | Action Recognition | 1 | 0.65 | Rapid vertical descent followed by >=3s horizontal stillness | `cloud_alert`, `telegram_alert` |
| `animal.wildlife.general` | Visual | Object Detection | 0 | 0.35 | Faunal presence (canine, bird, cattle); passive | `log_only` |
| `animal.wildlife.predator` | Visual | Object Detection | 1 | 0.50 | Dangerous carnivore (bear, big cat, boar) near perimeter | `cloud_alert`, `telegram_alert`, `soft_deterrence` |
| `hazard.fire.flame` | Visual | Object Detection | 2 | 0.55 | Visible flickering flame across >=2 consecutive frames | `cloud_alert`, `telegram_alert`, `siren`, `strobe` |
| `hazard.fire.smoke` | Visual | Object Detection | 2 | 0.50 | Volumetric rising smoke particulate plume | `cloud_alert`, `telegram_alert` |
| `intrusion.perimeter.breach` | Visual | Zone Detection | 1 | 0.50 | Centroid trajectory crossing polygon boundary line | `cloud_alert`, `telegram_alert` |
| `audio.threat.gunshot` | Acoustic | Audio Classification | 2 | 0.50 | Shockwave impulse (<5ms rise) + high crest factor | `cloud_alert`, `telegram_alert`, `visual_cue` |
| `audio.threat.scream` | Acoustic | Audio Classification | 2 | 0.55 | Vocal formant energy in 1-4 kHz range >=400ms | `cloud_alert`, `telegram_alert`, `visual_cue` |
| `audio.threat.glass_break` | Acoustic | Audio Classification | 1 | 0.50 | High-frequency shatter in 3-10 kHz range | `cloud_alert`, `telegram_alert` |
| `audio.threat.alarm` | Acoustic | Audio Classification | 1 | 0.60 | Periodic or continuous tonal harmonic siren | `cloud_alert`, `telegram_alert` |

---

## 4. Machine-Readable Schema

The definitive JSON definition resides in [`ml_pipeline/taxonomy/taxonomy.json`](file:///mnt/WindowsDrive/Shared/Projects/SIP/node-backend/ml_pipeline/taxonomy/taxonomy.json) and is mirrored in [`models/registry/taxonomy.json`](file:///mnt/WindowsDrive/Shared/Projects/SIP/node-backend/models/registry/taxonomy.json). Programmatic querying and label translation are provided by [`TaxonomyManager`](file:///mnt/WindowsDrive/Shared/Projects/SIP/node-backend/ml_pipeline/taxonomy/taxonomy_manager.py#L35-L125).
