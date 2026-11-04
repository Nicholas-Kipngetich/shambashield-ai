"""Demo snapshot and contract behaviour tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shambashield.contracts import WeatherSnapshot
from shambashield.demo import demo_names, load_demo_snapshot
from tests.helpers import make_snapshot


def test_demo_snapshot_loads_and_is_labelled() -> None:
    snapshot = load_demo_snapshot("machakos_drought")
    assert snapshot.source == "demo"
    assert snapshot.county == "Machakos"
    assert len(snapshot.days) == 7
    assert all(d.rain_mm <= 0.5 for d in snapshot.days)


def test_demo_snapshot_forced_to_demo_source() -> None:
    snapshot = load_demo_snapshot("machakos_drought")
    assert snapshot.source == "demo"


def test_unknown_demo_snapshot_lists_available() -> None:
    with pytest.raises(FileNotFoundError, match="machakos_drought"):
        load_demo_snapshot("does_not_exist")
    assert "machakos_drought" in demo_names()


def test_rain_probability_bounds() -> None:
    with pytest.raises(ValidationError):
        make_snapshot(rain=[0.0], probability=[101])


def test_snapshot_helper_aggregations() -> None:
    snapshot = make_snapshot(rain=[1.0, 2.0, 3.0], et0=[10.0, 5.0, 5.0])
    assert snapshot.total_rain_mm(window_days=2) == 3.0
    assert snapshot.total_rain_mm() == 6.0
    assert isinstance(snapshot, WeatherSnapshot)
