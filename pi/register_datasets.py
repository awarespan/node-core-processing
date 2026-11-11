#!/usr/bin/env python3
"""Register all SIP datasets in the persistent registry."""
import sys
sys.path.insert(0, "/home/benjamin/edge-ai")
import dataset_registry as reg

datasets = [
    {
        "dataset_id": "roboflow-gun-knife-v1",
        "name": "Gun and Knife Detection (Roboflow)",
        "source_url": "https://universe.roboflow.com/mahad-ahmed/gun-and-knife-detection",
        "source_owner": "mahad-ahmed",
        "license": "CC BY 4.0",
        "retrieval_date": "2026-08-31",
        "annotation_format": "YOLO",
        "source_classes": ["gun", "knife"],
        "target_task": "weapon",
        "status": "TRAINING_ELIGIBLE",
        "accepted_count": 8623,
        "train_count": 5654,
        "valid_count": 1207,
        "test_count": 762,
        "notes": "Original source. 828 empty negative examples.",
    },
    {
        "dataset_id": "unified-weapon-dataset-v1",
        "name": "Unified Weapon + Animal Dataset",
        "source_url": "merged: roboflow + kaggle + github + zenodo + tigdog",
        "source_owner": "multiple",
        "license": "mixed",
        "retrieval_date": "2026-09-12",
        "annotation_format": "YOLO",
        "source_classes": ["gun", "knife", "dangerous_animal"],
        "target_task": "weapon",
        "status": "TRAINING_ELIGIBLE",
        "accepted_count": 8427,
        "train_count": 6283,
        "valid_count": 1291,
        "test_count": 853,
        "notes": "Forensic audit PASSED: 0 malformed, 0 invalid class, 0 bad images. 301 cross-dataset duplicates (not in same split). 1046 empty negative examples.",
    },
    {
        "dataset_id": "zenodo-nestler-safari",
        "name": "NESTLER Safari Wild Animal Detection",
        "source_url": "https://zenodo.org/records/17036940/files/Safari_Wild_Animal_Detection.zip",
        "source_owner": "NESTLER Project",
        "license": "Research use — verify before production",
        "retrieval_date": "pending",
        "annotation_format": "YOLO",
        "source_classes": ["animal"],
        "target_task": "animal",
        "status": "REGISTERED",
        "notes": "Wild animal detection from NESTLER project. Download via download_and_merge.py.",
    },
    {
        "dataset_id": "zenodo-nestler-elephants",
        "name": "NESTLER Elephants Gorillas Kobs Detection",
        "source_url": "https://zenodo.org/records/17036940/files/Elephants-Gorillas-Kobs_Detection_Dataset.zip",
        "source_owner": "NESTLER Project",
        "license": "Research use — verify before production",
        "retrieval_date": "pending",
        "annotation_format": "YOLO",
        "source_classes": ["animal"],
        "target_task": "animal",
        "status": "REGISTERED",
    },
    {
        "dataset_id": "zenodo-nestler-foxes",
        "name": "NESTLER Foxes Vultures Ravens Jackals",
        "source_url": "https://zenodo.org/records/17036940/files/Foxes-Vultures-Ravens-Jackals_Classification.zip",
        "source_owner": "NESTLER Project",
        "license": "Research use — verify before production",
        "retrieval_date": "pending",
        "annotation_format": "YOLO",
        "source_classes": ["animal"],
        "target_task": "animal",
        "status": "REGISTERED",
        "notes": "May be classification-only, not object detection. Requires format validation.",
    },
    {
        "dataset_id": "kaggle-pet-detection",
        "name": "Weather-Proof Pet Detection App",
        "source_url": "https://www.kaggle.com/datasets/farzadnekouei/weather-proof-pet-detection-app",
        "source_owner": "farzadnekouei",
        "license": "CC BY 4.0",
        "retrieval_date": "pending",
        "annotation_format": "YOLO",
        "source_classes": ["dog", "cat"],
        "target_task": "animal",
        "status": "REGISTERED",
        "notes": "Download via kagglehub in download_and_merge.py.",
    },
    {
        "dataset_id": "tigdog",
        "name": "TigDog Dataset (Tiger/Dog/Horse)",
        "source_url": "http://work.thaslwanter.at/TigDog/data/TigDog_Dataset.zip",
        "source_owner": "Calvin-Vision",
        "license": "Research/non-commercial — verify before production",
        "retrieval_date": "pending",
        "annotation_format": "YOLO",
        "source_classes": ["tiger", "dog", "horse"],
        "target_task": "animal",
        "status": "REGISTERED",
        "notes": "Non-commercial license. Behavior/landmark annotations may not be object detection boxes. Requires format validation.",
    },
]

for ds in datasets:
    result = reg.register_dataset(
        dataset_id=ds["dataset_id"],
        name=ds["name"],
        source_url=ds["source_url"],
        source_owner=ds.get("source_owner", ""),
        license_=ds.get("license", ""),
        retrieval_date=ds.get("retrieval_date", ""),
        annotation_format=ds.get("annotation_format", ""),
        source_classes=ds.get("source_classes", []),
        target_task=ds.get("target_task", ""),
        notes=ds.get("notes", ""),
    )
    updates = {k: v for k, v in ds.items() if k not in [
        "dataset_id", "name", "source_url", "source_owner", "license",
        "retrieval_date", "annotation_format", "source_classes", "target_task", "notes"
    ]}
    if updates:
        reg.update_dataset(ds["dataset_id"], **updates)
    print(f"Registered: {ds['dataset_id']} -> {ds['status']}")

print()
reg.print_registry_summary()