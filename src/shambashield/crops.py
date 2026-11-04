"""Loader for the curated crop/stage sensitivity profile (data/crops.yaml)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .contracts import Crop, Stage

_CROPS_FILE = Path(__file__).parent / "data" / "crops.yaml"
_HAZARD_KEYS = ("drought", "excess_rain", "heat", "wind")
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


class UnknownCropError(ValueError):
    """The crop is not in the curated allow-list."""


class CropProfile:
    """Typed view of one crop's sensitivities and impact texts."""

    def __init__(self, crop: Crop, raw: dict[str, Any]) -> None:
        self.crop: Crop = crop
        self.label: str = str(raw.get("label", crop))
        self.stages: dict[str, dict[str, str]] = {
            stage: dict(raw.get("stages", {}).get(stage, {})) for stage in _ALL_STAGES
        }
        self.impacts: dict[str, str] = dict(raw.get("impacts", {}))

    def sensitivity(self, stage: Stage, hazard_kind: str) -> str:
        """Sensitivity of this crop/stage to a hazard: high | moderate | low."""
        return str(self.stages.get(stage, {}).get(hazard_kind, "moderate"))

    def impact(self, hazard_kind: str) -> str:
        return self.impacts.get(hazard_kind, "This hazard can affect the crop at this stage.")


@lru_cache(maxsize=1)
def load_crops() -> dict[Crop, CropProfile]:
    with _CROPS_FILE.open(encoding="utf-8") as file:
        payload: dict[str, Any] = yaml.safe_load(file)
    profiles: dict[Crop, CropProfile] = {}
    for name, raw in payload.get("crops", {}).items():
        profiles[name] = CropProfile(name, raw)  # type: ignore[arg-type]
    return profiles


def crop_names() -> list[str]:
    return sorted(load_crops())


def get_crop(crop: str) -> CropProfile:
    clean = crop.strip()
    profiles = load_crops()
    if clean in profiles:
        return profiles[clean]
    raise UnknownCropError(
        f"Unknown crop {crop!r}. Supported crops: {', '.join(sorted(profiles))}."
    )
