"""Deterministic hazard detection for normalised forecasts.

This module is the reason an LLM cannot "decide" the risk level: the same
snapshot always produces the same hazards, given the same thresholds.

Severity values are never downgraded below the raw trigger. Crop-stage
sensitivity (Phase 4) may escalate a hazard by one level, never de-escalate.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ..contracts import Hazard, HazardKind, HazardSeverity, WeatherSnapshot

_THRESHOLDS_FILE = Path(__file__).resolve().parents[3] / "config" / "thresholds.yaml"


# ---------------------------------------------------------------------- #
# Threshold loading
# ---------------------------------------------------------------------- #
class Thresholds:
    """Typed view over config/thresholds.yaml."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw
        self.version: str = str(raw.get("version", "?"))
        self.note: str = str(raw.get("note", ""))
        self.drought: dict[str, Any] = raw.get("drought", {})
        self.excess_rain: dict[str, Any] = raw.get("excess_rain", {})
        self.heat: dict[str, Any] = raw.get("heat", {})
        self.wind: dict[str, Any] = raw.get("wind", {})
        self.data_gap: dict[str, Any] = raw.get("data_gap", {})

    @property
    def drought_window(self) -> int:
        return int(self.drought.get("window_days", 7))

    @property
    def et0_fraction(self) -> float:
        return float(self.drought.get("et0_fraction", 0.8))

    @property
    def deficit_moderate(self) -> float:
        return float(self.drought.get("deficit_moderate_mm", -25.0))

    @property
    def deficit_high(self) -> float:
        return float(self.drought.get("deficit_high_mm", -45.0))

    @property
    def dry_day_mm(self) -> float:
        return float(self.drought.get("dry_day_mm", 1.0))

    @property
    def dry_days_moderate(self) -> int:
        return int(self.drought.get("dry_days_moderate", 5))

    @property
    def dry_days_high(self) -> int:
        return int(self.drought.get("dry_days_high", 7))

    @property
    def excess_window(self) -> int:
        return int(self.excess_rain.get("window_days", 3))

    @property
    def excess_total_moderate(self) -> float:
        return float(self.excess_rain.get("total_moderate_mm", 60.0))

    @property
    def excess_total_high(self) -> float:
        return float(self.excess_rain.get("total_high_mm", 100.0))

    @property
    def excess_day_moderate(self) -> float:
        return float(self.excess_rain.get("day_moderate_mm", 40.0))

    @property
    def excess_day_high(self) -> float:
        return float(self.excess_rain.get("day_high_mm", 70.0))

    @property
    def heat_moderate_c(self) -> float:
        return float(self.heat.get("tmax_moderate_c", 35.0))

    @property
    def heat_high_c(self) -> float:
        return float(self.heat.get("tmax_high_c", 38.0))

    @property
    def heat_days_moderate(self) -> int:
        return int(self.heat.get("days_moderate", 2))

    @property
    def heat_days_high(self) -> int:
        return int(self.heat.get("days_high", 3))

    @property
    def wind_moderate_kph(self) -> float:
        return float(self.wind.get("speed_moderate_kph", 30.0))

    @property
    def wind_high_kph(self) -> float:
        return float(self.wind.get("speed_high_kph", 45.0))

    @property
    def wind_days_moderate(self) -> int:
        return int(self.wind.get("days_moderate", 2))

    @property
    def min_days(self) -> int:
        return int(self.data_gap.get("min_days", 5))


@lru_cache(maxsize=1)
def load_thresholds() -> Thresholds:
    with _THRESHOLDS_FILE.open(encoding="utf-8") as file:
        raw: dict[str, Any] = yaml.safe_load(file)
    return Thresholds(raw)


# ---------------------------------------------------------------------- #
# Detection
# ---------------------------------------------------------------------- #
def detect_hazards(
    snapshot: WeatherSnapshot,
    thresholds: Thresholds | None = None,
) -> list[Hazard]:
    """Return hazards found in the snapshot. Pure function, no I/O."""
    th = thresholds or load_thresholds()
    days = snapshot.days
    hazards: list[Hazard] = []

    if days:
        window_start: date = days[0].date
        window_end: date = days[-1].date
    else:
        window_start = window_end = date.today()

    # ---- Data gap --------------------------------------------------- #
    has_et0 = any(d.et0_mm is not None for d in days)
    if not days or len(days) < th.min_days or not has_et0:
        severity: HazardSeverity = "high" if not days else "moderate"
        evidence: list[str] = []
        if not days:
            evidence.append("No forecast days were available for this location.")
        elif len(days) < th.min_days:
            evidence.append(f"Only {len(days)} forecast days returned; {th.min_days} expected.")
        if not has_et0:
            evidence.append(
                "Reference evapotranspiration (ET0) is missing, so water-stress "
                "estimates are less reliable."
            )
        hazards.append(
            Hazard(
                kind="data_gap",
                severity=severity,
                window_start=window_start,
                window_end=window_end,
                evidence=evidence,
                metrics={
                    "days_available": float(len(days)),
                    "et0_available": float(has_et0),
                },
            )
        )

    # ---- Drought / water deficit ------------------------------------ #
    hazard = _detect_drought(days, th, window_start, window_end)
    if hazard:
        hazards.append(hazard)

    # ---- Excess rain ------------------------------------------------ #
    hazard = _detect_excess_rain(days, th, window_start, window_end)
    if hazard:
        hazards.append(hazard)

    # ---- Heat ------------------------------------------------------- #
    hazard = _detect_heat(days, th, window_start, window_end)
    if hazard:
        hazards.append(hazard)

    # ---- Wind ------------------------------------------------------- #
    hazard = _detect_wind(days, th, window_start, window_end)
    if hazard:
        hazards.append(hazard)

    return hazards


def _detect_drought(
    days: list,
    th: Thresholds,
    window_start: date,
    window_end: date,
) -> Hazard | None:
    if not days:
        return None
    window = days[: th.drought_window]
    rain = sum(d.rain_mm for d in window)
    et0_values = [d.et0_mm for d in window if d.et0_mm is not None]
    et0_weighted = sum(et0_values) * th.et0_fraction if et0_values else None
    deficit = round(rain - et0_weighted, 1) if et0_weighted is not None else None

    dry_days = 0
    longest_dry_run = 0
    for day in window:
        if day.rain_mm < th.dry_day_mm:
            dry_days += 1
            longest_dry_run = max(longest_dry_run, dry_days)
        else:
            dry_days = 0

    severity: HazardSeverity | None = None
    reasons: list[str] = []
    if deficit is not None and deficit <= th.deficit_high:
        severity = "high"
        reasons.append(f"7-day water deficit {deficit} mm (threshold {th.deficit_high} mm)")
    elif deficit is not None and deficit <= th.deficit_moderate:
        severity = "moderate"
        reasons.append(f"7-day water deficit {deficit} mm (threshold {th.deficit_moderate} mm)")
    if longest_dry_run >= th.dry_days_high:
        severity = "high"
        reasons.append(f"{longest_dry_run} consecutive days with < {th.dry_day_mm} mm rain")
    elif severity in (None, "moderate") and longest_dry_run >= th.dry_days_moderate:
        if severity is None:
            severity = "moderate"
        reasons.append(f"{longest_dry_run} consecutive days with < {th.dry_day_mm} mm rain")

    if severity is None:
        return None

    metrics: dict[str, float] = {
        "rain_window_mm": round(rain, 1),
        "dry_days_longest_run": float(longest_dry_run),
    }
    if et0_weighted is not None:
        metrics["et0_weighted_mm"] = round(et0_weighted, 1)
        metrics["deficit_mm"] = float(deficit) if deficit is not None else 0.0

    evidence = [
        f"Total rainfall over {len(window)} days: {round(rain, 1)} mm",
        f"Longest dry spell: {longest_dry_run} day(s) with under {th.dry_day_mm} mm",
    ]
    if et0_weighted is not None:
        evidence.append(
            f"Atmospheric water demand (0.8 x ET0) over the window: {round(et0_weighted, 1)} mm"
        )
        evidence.append(f"Water deficit: {deficit} mm")
    for reason in reasons:
        evidence.append(f"Trigger: {reason}")

    return Hazard(
        kind="drought",
        severity=severity,
        window_start=window_start,
        window_end=window_end,
        evidence=evidence,
        metrics=metrics,
    )


def _detect_excess_rain(
    days: list,
    th: Thresholds,
    window_start: date,
    window_end: date,
) -> Hazard | None:
    if not days:
        return None

    worst_3day = 0.0
    for index in range(len(days)):
        chunk = days[index : index + th.excess_window]
        if chunk:
            worst_3day = max(worst_3day, sum(d.rain_mm for d in chunk))
    worst_day = max((d.rain_mm for d in days), default=0.0)

    severity: HazardSeverity | None = None
    if worst_3day >= th.excess_total_high or worst_day >= th.excess_day_high:
        severity = "high"
    elif worst_3day >= th.excess_total_moderate or worst_day >= th.excess_day_moderate:
        severity = "moderate"
    if severity is None:
        return None

    metrics: dict[str, float] = {
        "max_3day_total_mm": round(worst_3day, 1),
        "max_daily_mm": round(worst_day, 1),
    }
    evidence = [
        f"Highest 3-day rainfall total: {round(worst_3day, 1)} mm",
        f"Highest single-day rainfall: {round(worst_day, 1)} mm",
        "Note: soil drainage and slope are not known, so waterlogging impact varies.",
    ]
    return Hazard(
        kind="excess_rain",
        severity=severity,
        window_start=window_start,
        window_end=window_end,
        evidence=evidence,
        metrics=metrics,
    )


def _detect_heat(
    days: list,
    th: Thresholds,
    window_start: date,
    window_end: date,
) -> Hazard | None:
    if not days:
        return None
    days_moderate = sum(1 for d in days if d.tmax_c >= th.heat_moderate_c)
    days_high = sum(1 for d in days if d.tmax_c >= th.heat_high_c)
    peak = max((d.tmax_c for d in days), default=0.0)

    severity: HazardSeverity | None = None
    if days_high >= th.heat_days_high:
        severity = "high"
    elif days_moderate >= th.heat_days_moderate:
        severity = "moderate"
    if severity is None:
        return None

    metrics: dict[str, float] = {
        "days_ge_moderate_c": float(days_moderate),
        "days_ge_high_c": float(days_high),
        "peak_tmax_c": round(peak, 1),
    }
    evidence = [
        f"Peak maximum temperature: {round(peak, 1)} °C",
        f"{days_moderate} day(s) at or above {th.heat_moderate_c:.0f} °C; "
        f"{days_high} day(s) at or above {th.heat_high_c:.0f} °C",
    ]
    return Hazard(
        kind="heat",
        severity=severity,
        window_start=window_start,
        window_end=window_end,
        evidence=evidence,
        metrics=metrics,
    )


def _detect_wind(
    days: list,
    th: Thresholds,
    window_start: date,
    window_end: date,
) -> Hazard | None:
    if not days:
        return None
    windy = [
        d for d in days if d.wind_max_kmh is not None and d.wind_max_kmh >= th.wind_moderate_kph
    ]
    windy_high = [
        d for d in windy if d.wind_max_kmh is not None and d.wind_max_kmh >= th.wind_high_kph
    ]
    peak = max((d.wind_max_kmh for d in windy), default=0.0)

    severity: HazardSeverity | None = None
    if len(windy_high) >= 1:
        severity = "high"
    elif len(windy) >= th.wind_days_moderate:
        severity = "moderate"
    if severity is None:
        return None

    metrics: dict[str, float] = {
        "peak_wind_kmh": round(peak, 1),
        "days_ge_moderate_kph": float(len(windy)),
        "days_ge_high_kph": float(len(windy_high)),
    }
    evidence = [
        f"Peak wind speed: {round(peak, 1)} km/h",
        f"{len(windy)} day(s) at or above {th.wind_moderate_kph:.0f} km/h; "
        f"{len(windy_high)} day(s) at or above {th.wind_high_kph:.0f} km/h",
        "Impacts: spray drift and lodging risk for tall crops.",
    ]
    return Hazard(
        kind="wind",
        severity=severity,
        window_start=window_start,
        window_end=window_end,
        evidence=evidence,
        metrics=metrics,
    )


def hazard_kind_label(kind: HazardKind) -> str:
    labels: dict[str, str] = {
        "drought": "Drought / water stress",
        "excess_rain": "Excessive rainfall",
        "heat": "Heat stress",
        "wind": "Strong winds",
        "data_gap": "Limited data",
    }
    return labels.get(kind, kind)
