# AWARESPAN Dataset Manifests

These manifests describe dataset contracts and local paths only. They do not contain datasets and do not download anything. Do not place private or unlicensed datasets in Git.

To add a dataset, create a manifest with modality, task, annotation format, canonical classes, taxonomy mappings, split paths, provenance, licence, and a local data path. Audit labels and licences before changing status to `TRAINING_ELIGIBLE`. Training jobs must reference local manifests and local data files only.

Current ready-to-use local material: `weapon-detection-1` is present under `Samples/`. The person/dog manifest is prepared but awaits a separately approved local training dataset. The video and audio manifests are future dataset contracts only.
