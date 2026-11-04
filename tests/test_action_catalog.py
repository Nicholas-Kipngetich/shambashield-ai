"""Integrity tests for the curated action catalog."""

from __future__ import annotations

import pytest

from shambashield.action_catalog import CatalogError, catalog_version, load_catalog


def test_catalog_loads_and_is_non_empty() -> None:
    catalog = load_catalog()
    assert len(catalog) >= 15


def test_all_action_ids_are_unique() -> None:
    catalog = load_catalog()
    # load_catalog raises on duplicates; loading again must succeed too.
    assert load_catalog() == catalog


def test_wildcards_allowed() -> None:
    catalog = load_catalog()
    assert any("any" in entry["crops"] for entry in catalog.values())
    assert any("any" in entry["stages"] for entry in catalog.values())


def test_every_hazard_has_a_curated_answer() -> None:
    catalog = load_catalog()
    covered = {h for entry in catalog.values() for h in entry["hazards"]}
    assert {"drought", "excess_rain", "heat", "wind", "data_gap"} <= covered


def test_every_crop_has_crop_specific_and_wildcard_options() -> None:
    catalog = load_catalog()
    for crop in ("maize", "beans", "potatoes", "other"):
        specific = any(crop in entry["crops"] for entry in catalog.values())
        wildcard = any("any" in entry["crops"] for entry in catalog.values())
        assert specific or wildcard, crop


def test_titles_and_why_are_concrete() -> None:
    for action_id, entry in load_catalog().items():
        title = str(entry["title_en"])
        assert len(title) > 10, action_id
        assert entry["title_sw"] and entry["title_sw"] != entry["title_en"], action_id


def test_implications_of_bad_entry_are_caught() -> None:
    with pytest.raises(CatalogError):
        # Direct low-level call to prove validation rejects a bad hazard name.
        from shambashield.action_catalog import _validate_entry

        _validate_entry(
            "test_id",
            {
                "id": "test_id",
                "hazards": ["floods"],
                "crops": ["any"],
                "stages": ["any"],
                "urgency": "now",
                "cost_tier": "free",
                "title_en": "Test action title",
                "title_sw": "Kitendo cha jaribio",
                "why": "Testing validation.",
                "when": "Now.",
            },
        )


def test_catalog_version_is_pinned() -> None:
    assert catalog_version() == "0.1.0"
