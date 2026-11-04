"""Loader and validation for the curated action catalog (data/actions.yaml)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .contracts import CostTier, Crop, Stage, Urgency

_ACTIONS_FILE = Path(__file__).parent / "data" / "actions.yaml"
_VALID_HAZARDS = {"drought", "excess_rain", "heat", "wind", "data_gap"}
_VALID_COST: set[str] = set(CostTier.__args__)  # type: ignore[attr-defined]
_VALID_URGENCY: set[str] = set(Urgency.__args__)  # type: ignore[attr-defined]
_VALID_STAGES: set[str] = set(Stage.__args__) | {"any"}  # type: ignore[attr-defined]


class CatalogError(ValueError):
    """The action catalog is malformed."""


def catalog_version() -> str:
    return str(_load_raw().get("version", "?"))


def load_catalog() -> dict[str, dict[str, Any]]:
    """Return the raw catalog entries keyed by action id (validated)."""
    entries: dict[str, dict[str, Any]] = {}
    for raw in _entries():
        action_id = str(raw.get("id") or "")
        if not action_id:
            raise CatalogError("Every action needs an id.")
        if action_id in entries:
            raise CatalogError(f"Duplicate action id: {action_id}")
        _validate_entry(action_id, raw)
        entries[action_id] = raw
    return entries


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    with _ACTIONS_FILE.open(encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


@lru_cache(maxsize=1)
def _entries() -> tuple[dict[str, Any], ...]:
    return tuple(_load_raw().get("actions", []))


def _validate_entry(action_id: str, raw: dict[str, Any]) -> None:
    hazards = list(raw.get("hazards") or [])
    if not hazards or not set(hazards) <= _VALID_HAZARDS:
        raise CatalogError(f"{action_id}: hazards must be a non-empty subset of {_VALID_HAZARDS}")

    crops = list(raw.get("crops") or [])
    if not crops or any(c != "any" and c not in Crop.__args__ for c in crops):  # type: ignore[attr-defined]
        raise CatalogError(f"{action_id}: crops must be 'any' or known crop names")

    stages = list(raw.get("stages") or [])
    if not stages or any(s not in _VALID_STAGES for s in stages):
        raise CatalogError(f"{action_id}: stages must be 'any' or known stage names")

    if str(raw.get("urgency")) not in _VALID_URGENCY:
        raise CatalogError(f"{action_id}: urgency must be one of {sorted(_VALID_URGENCY)}")
    if str(raw.get("cost_tier")) not in _VALID_COST:
        raise CatalogError(f"{action_id}: cost_tier must be one of {sorted(_VALID_COST)}")

    for field in ("title_en", "title_sw", "why", "when"):
        if not str(raw.get(field) or "").strip():
            raise CatalogError(f"{action_id}: missing {field}")
