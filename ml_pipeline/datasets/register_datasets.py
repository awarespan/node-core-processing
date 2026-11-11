"""
AWARESPAN — Register Known Datasets
CLI tool to populate dataset registry with known weapon detection corpora.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

from ml_pipeline.datasets.dataset_registry import register_dataset, print_registry_summary


def register_known():
    register_dataset(
        dataset_id="gun-and-knife-detection-1",
        name="Gun and Knife Detection Dataset v1",
        source_url="https://universe.roboflow.com/mahad-ahmed/gun-and-knife-detection",
        source_owner="Mahad Ahmed",
        license_="CC BY 4.0",
        annotation_format="YOLOv8",
        source_classes=["gun", "knife"],
        target_task="weapon_detection",
        notes="Primary base weapon detection dataset",
    )

    register_dataset(
        dataset_id="unified_weapon_dataset",
        name="AWARESPAN Unified Weapon Corpus",
        source_url="local://unified_weapon_dataset",
        source_owner="AWARESPAN",
        license_="Proprietary",
        annotation_format="YOLOv8",
        source_classes=["gun", "knife"],
        target_task="weapon_detection",
        notes="Merged and deduplicated master weapon dataset",
    )


if __name__ == "__main__":
    register_known()
    print_registry_summary()
