"""County lookup and geocoding helpers for location resolution.

Ordering guarantees a usable answer even when geocoding is offline:
1. If the user supplied a location label, try Open-Meteo geocoding and require
   Kenyan results where possible.
2. Otherwise use the curated approximate county centroid.
Never silently use coordinates without recording how they were obtained.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .contracts import LocationPoint

_COUNTIES_FILE = Path(__file__).parent / "data" / "counties.yaml"
_KENYA_COUNTRY_CODE = "KE"


class UnknownCountyError(ValueError):
    """The given county is not in the curated list of Kenya's 47 counties."""


@lru_cache(maxsize=1)
def load_counties() -> dict[str, dict[str, float]]:
    """Return a mapping of county name -> {"latitude": ..., "longitude": ...}."""
    with _COUNTIES_FILE.open(encoding="utf-8") as file:
        payload: dict[str, Any] = yaml.safe_load(file)
    rows = payload.get("counties", [])
    return {
        row["name"]: {"latitude": row["latitude"], "longitude": row["longitude"]} for row in rows
    }


def county_names() -> list[str]:
    return sorted(load_counties())


def get_county(county: str) -> LocationPoint:
    """Look up a county by name, raising a helpful error with suggestions."""
    counties = load_counties()
    clean = county.strip()
    if clean in counties:
        coords = counties[clean]
        return LocationPoint(
            county=clean,
            name=clean,
            latitude=coords["latitude"],
            longitude=coords["longitude"],
            approximated=True,
            note="Approximate county centroid",
        )
    matches = _suggest(clean, counties)
    raise UnknownCountyError(
        f"Unknown county {county!r}. Known counties: {', '.join(sorted(counties))}."
        + (f" Did you mean: {', '.join(matches)}?" if matches else "")
    )


def _suggest(name: str, counties: dict[str, Any], limit: int = 3) -> list[str]:
    import difflib

    return difflib.get_close_matches(name.strip(), sorted(counties), n=limit, cutoff=0.7)
