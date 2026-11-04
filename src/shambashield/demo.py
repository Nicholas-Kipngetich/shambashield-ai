"""Labelled demo snapshots, used for offline demos and tests.

Demo data is clearly marked (`source == "demo"`) and is never a substitute for
a live forecast without explicit UI labelling.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .contracts import WeatherSnapshot

_DEMO_DIR = Path(__file__).parent / "data" / "demo_forecasts"


@lru_cache(maxsize=1)
def demo_names() -> tuple[str, ...]:
    return tuple(sorted(path.stem for path in _DEMO_DIR.glob("*.json")))


def load_demo_snapshot(name: str = "machakos_drought") -> WeatherSnapshot:
    path = _DEMO_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Unknown demo snapshot {name!r}. Available: {', '.join(demo_names())}"
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    snapshot = WeatherSnapshot.model_validate(payload)
    if snapshot.source != "demo":
        snapshot = snapshot.model_copy(update={"source": "demo"})
    return snapshot
