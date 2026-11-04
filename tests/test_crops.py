"""Integrity tests for the curated crop/stage sensitivity table."""

from __future__ import annotations

import pytest

from shambashield.contracts import Stage
from shambashield.crops import (
    UnknownCropError,
    crop_names,
    get_crop,
    load_crops,
)

_ALL_STAGES: tuple[Stage, ...] = (
    "land_preparation",
    "planting",
    "emergence",
    "vegetative",
    "flowering",
    "grain_filling",
    "maturity",
    "harvest",
)
_HAZARD_KEYS = {"drought", "excess_rain", "heat", "wind"}


def test_four_crops_are_curated() -> None:
    assert crop_names() == ["beans", "maize", "other", "potatoes"]


def test_every_crop_covers_every_stage_and_hazard() -> None:
    for crop, profile in load_crops().items():
        assert set(profile.stages) == set(_ALL_STAGES), crop
        for stage, sensitivities in profile.stages.items():
            assert _HAZARD_KEYS <= set(sensitivities), (crop, stage)
            assert all(v in {"high", "moderate", "low"} for v in sensitivities.values()), (
                crop,
                stage,
            )


def test_impact_texts_exist_for_every_hazard() -> None:
    for crop, profile in load_crops().items():
        for kind in _HAZARD_KEYS:
            text = profile.impact(kind)
            assert text and text.strip(), (crop, kind)


def test_maize_flowering_is_most_sensitive() -> None:
    maize = get_crop("maize")
    assert maize.sensitivity("flowering", "drought") == "high"
    assert maize.sensitivity("flowering", "excess_rain") == "high"
    assert maize.sensitivity("flowering", "heat") == "high"
    # Maturity drought must NOT be high (escalation would make no sense).
    assert maize.sensitivity("maturity", "drought") != "high"


def test_potatoes_cannot_rot_because_of_drought() -> None:
    potatoes = get_crop("potatoes")
    # Excess rain (rot) must stay sensitive at every potato stage.
    for stage in _ALL_STAGES:
        assert potatoes.sensitivity(stage, "excess_rain") != "low", stage


def test_unknown_crop_lists_supported() -> None:
    with pytest.raises(UnknownCropError, match="beans"):
        get_crop("sorghum")
