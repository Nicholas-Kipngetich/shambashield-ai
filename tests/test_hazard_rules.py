"""Hazard rule boundary tests. Pure functions, no network."""

from __future__ import annotations

from shambashield.contracts import WeatherSnapshot
from shambashield.tools.hazard_rules import detect_hazards, load_thresholds
from tests.helpers import make_snapshot


def hazards_by_kind(snapshot: WeatherSnapshot) -> dict[str, str]:
    return {h.kind: h.severity for h in detect_hazards(snapshot)}


# ---------------------------------------------------------------------- #
# Drought
# ---------------------------------------------------------------------- #
def test_severe_deficit_and_full_dry_spell_is_high() -> None:
    snapshot = make_snapshot(rain=[0.0] * 7, et0=[8.0] * 7)
    kinds = hazards_by_kind(snapshot)
    assert kinds.get("drought") == "high"


def test_long_dry_spell_without_et0_is_moderate() -> None:
    # 5-day dry run then a rain day; ET0 missing so deficit cannot be computed.
    snapshot = make_snapshot(rain=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 4.0], et0=None)
    kinds = hazards_by_kind(snapshot)
    assert kinds.get("drought") == "moderate"


def test_no_cold_no_heat_no_drought_is_unflagged() -> None:
    snapshot = make_snapshot(
        rain=[3.0] * 7,
        tmax=[27.0] * 7,
        et0=[3.5] * 7,  # 0.8 * 24.5 = 19.6; deficit 21 - 19.6 = 1.4 -> safe
        wind=[10.0] * 7,
    )
    hazards = detect_hazards(snapshot)
    kinds = {h.kind for h in hazards}
    assert not kinds, kinds


def test_drought_deficit_boundary_is_exact() -> None:
    """Verify the water-balance arithmetic, not just that a hazard fires."""
    th = load_thresholds()
    et0 = [5.0] * 7
    # Sum(rain)=3.0; 0.8 * sum(et0)=28.0 -> deficit exactly -25.0 (moderate boundary).
    rain = [0.4, 0.4, 0.4, 0.4, 0.4, 0.5, 0.5]
    snapshot = make_snapshot(rain=rain, et0=et0)

    droughts = [h for h in detect_hazards(snapshot) if h.kind == "drought"]
    assert droughts, "expected a drought hazard at the moderate boundary"
    assert droughts[0].metrics.get("deficit_mm") == -25.0
    assert th.deficit_moderate == -25.0


# ---------------------------------------------------------------------- #
# Excess rain
# ---------------------------------------------------------------------- #
def test_three_day_downpour_is_high() -> None:
    snapshot = make_snapshot(
        rain=[5.0, 5.0, 110.0, 0.0, 0.0, 0.0, 0.0],
        et0=[2.0] * 7,
    )
    kinds = hazards_by_kind(snapshot)
    assert kinds.get("excess_rain") == "high"


def test_moderate_total_is_moderate() -> None:
    snapshot = make_snapshot(
        rain=[25.0, 25.0, 25.0, 0.0, 0.0, 0.0, 0.0],  # 75 mm in 3 days
        et0=[2.0] * 7,
    )
    kinds = hazards_by_kind(snapshot)
    assert kinds.get("excess_rain") == "moderate"


def test_big_single_day_rain_triggers_even_with_low_total() -> None:
    snapshot = make_snapshot(
        rain=[45.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        et0=[2.0] * 7,
    )
    kinds = hazards_by_kind(snapshot)
    assert kinds.get("excess_rain") == "moderate"


# ---------------------------------------------------------------------- #
# Heat
# ---------------------------------------------------------------------- #
def test_two_hot_days_is_moderate() -> None:
    snapshot = make_snapshot(
        rain=[3.0] * 7,
        tmax=[35.5, 36.0, 30.0, 30.0, 30.0, 30.0, 30.0],
        et0=[3.0] * 7,
    )
    kinds = hazards_by_kind(snapshot)
    assert kinds.get("heat") == "moderate"


def test_three_extreme_days_is_high() -> None:
    snapshot = make_snapshot(
        rain=[3.0] * 7,
        tmax=[39.0, 39.5, 39.0, 30.0, 30.0, 30.0, 30.0],
        et0=[2.0] * 7,
    )
    kinds = hazards_by_kind(snapshot)
    assert kinds.get("heat") == "high"


# ---------------------------------------------------------------------- #
# Wind
# ---------------------------------------------------------------------- #
def test_wind_moderate_and_high() -> None:
    moderate = make_snapshot(rain=[0.0] * 7, et0=[1.0] * 7, wind=[32.0] * 7)
    high = make_snapshot(
        rain=[0.0] * 7, et0=[1.0] * 7, wind=[46.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    )
    kinds = hazards_by_kind(moderate)
    assert kinds.get("wind") == "moderate"
    assert hazards_by_kind(high).get("wind") == "high"


# ---------------------------------------------------------------------- #
# Data gaps
# ---------------------------------------------------------------------- #
def test_short_forecast_is_a_data_gap_not_low_risk() -> None:
    snapshot = make_snapshot(rain=[0.0] * 3, et0=[1.0] * 3)
    kinds = hazards_by_kind(snapshot)
    assert kinds.get("data_gap") == "moderate"


def test_empty_forecast_is_high_data_gap() -> None:
    snapshot = make_snapshot(rain=[])
    kinds = hazards_by_kind(snapshot)
    assert kinds.get("data_gap") == "high"


def test_missing_et0_only_adds_data_gap_once() -> None:
    snapshot = make_snapshot(rain=[1.0] * 7, et0=None)
    gaps = [h for h in detect_hazards(snapshot) if h.kind == "data_gap"]
    assert len(gaps) == 1


# ---------------------------------------------------------------------- #
# Threshold loading
# ---------------------------------------------------------------------- #
def test_thresholds_file_loads() -> None:
    th = load_thresholds()
    assert th.version == "0.1.0"
    assert th.deficit_high < th.deficit_moderate
    assert th.excess_total_high > th.excess_total_moderate
    assert 0.0 < th.et0_fraction <= 1.0
