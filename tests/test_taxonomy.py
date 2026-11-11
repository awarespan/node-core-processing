"""
Unit tests for AWARESPAN Threat Taxonomy Subsystem.
"""

from ml_pipeline.taxonomy.taxonomy_manager import TaxonomyManager, get_taxonomy_manager


def test_taxonomy_loading():
    tm = get_taxonomy_manager()
    assert tm.version == "1.0.0"
    assert len(tm.list_classes()) > 5


def test_taxonomy_querying():
    tm = get_taxonomy_manager()
    c = tm.get_class("weapon.firearm.handgun")
    assert c is not None
    assert c.parent_category == "weapon"
    assert c.severity == 4
    assert c.threat_tier == 2


def test_taxonomy_filtering():
    tm = get_taxonomy_manager()
    weapon_classes = tm.list_classes(category="weapon")
    assert len(weapon_classes) >= 3
    for wc in weapon_classes:
        assert wc.parent_category == "weapon"

    audio_classes = tm.list_classes(modality="acoustic")
    assert len(audio_classes) >= 3
    for ac in audio_classes:
        assert ac.modality == "acoustic"


def test_taxonomy_label_mapping():
    tm = get_taxonomy_manager()
    assert tm.map_raw_label("gun", modality="visual") == "weapon.firearm.handgun"
    assert tm.map_raw_label("knife", modality="visual") == "weapon.edged.knife"
    assert tm.map_raw_label("dog", modality="visual") == "animal.wildlife.general"
    assert tm.map_raw_label("bear", modality="visual") == "animal.wildlife.predator"
    assert tm.map_raw_label("gunshot", modality="acoustic") == "audio.threat.gunshot"
    assert tm.map_raw_label("scream", modality="acoustic") == "audio.threat.scream"
    assert tm.map_raw_label("glass_breaking", modality="acoustic") == "audio.threat.glass_break"
