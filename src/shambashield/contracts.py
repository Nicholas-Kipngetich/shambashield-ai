"""Typed data contracts shared by agents, tools, and the UI.

Every handoff between agents is a Pydantic model so that:
- agent failures become explicit validation failures,
- the UI renders facts separately from narrative,
- numbers can only originate from measured data.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

RiskLevel = Literal["low", "moderate", "high", "unknown"]
Language = Literal["en", "sw"]
Crop = Literal["maize", "beans", "potatoes", "other"]
Stage = Literal[
    "land_preparation",
    "planting",
    "emergence",
    "vegetative",
    "flowering",
    "grain_filling",
    "maturity",
    "harvest",
]
DataMode = Literal["open-meteo", "demo"]
ForecastWindowDays = 7


class FarmerProfile(BaseModel):
    """Validated farmer input. No PII is required in v1."""

    county: str
    location: str | None = None
    crop: Crop
    stage: Stage
    language: Language = "en"
    latitude: float | None = None
    longitude: float | None = None


class LocationPoint(BaseModel):
    """A resolved place, either from the curated county list or geocoding."""

    county: str
    name: str
    latitude: float
    longitude: float
    approximated: bool = False
    note: str | None = None

    @property
    def label(self) -> str:
        return f"{self.name}, {self.county} County"


class DailyForecast(BaseModel):
    date: date
    tmax_c: float
    tmin_c: float
    rain_mm: float
    rain_probability_pct: int | None = Field(default=None, ge=0, le=100)
    et0_mm: float | None = None
    wind_max_kmh: float | None = None


class WeatherSnapshot(BaseModel):
    """Normalised forecast exactly as used downstream. One source of truth."""

    county: str
    location_name: str
    latitude: float
    longitude: float
    timezone: str
    retrieved_at: datetime
    source: DataMode
    days: list[DailyForecast]
    hourly_rain_mm: list[float] | None = None

    def total_rain_mm(self, window_days: int | None = None) -> float:
        days = self.days if window_days is None else self.days[:window_days]
        return round(sum(d.rain_mm for d in days), 2)

    def max_tmax_c(self) -> float:
        return max((d.tmax_c for d in self.days), default=0.0)


HazardKind = Literal["drought", "excess_rain", "heat", "wind", "data_gap"]
HazardSeverity = Literal["low", "moderate", "high"]


class Hazard(BaseModel):
    kind: HazardKind
    severity: HazardSeverity
    window_start: date
    window_end: date
    evidence: list[str]
    metrics: dict[str, float]


class WeatherFindings(BaseModel):
    """Deterministic output of the weather stage. The agent explains it later."""

    snapshot: WeatherSnapshot
    hazards: list[Hazard]
    summary: str

    @property
    def top_severity(self) -> HazardSeverity | None:
        order: dict[str, int] = {"low": 0, "moderate": 1, "high": 2}
        ranked = sorted(self.hazards, key=lambda h: order[h.severity], reverse=True)
        return ranked[0].severity if ranked else None


class CropRiskAssessment(BaseModel):
    """Deterministic crop/stage view over the weather findings.

    `drivers` carry the severity trail (raw -> final) so every escalation is
    traceable; `impact_explanation` contains no numbers.
    """

    crop: Crop
    stage: Stage
    risk_level: RiskLevel
    drivers: list[str]
    impact_explanation: str
    uncertainty: list[str]
    stage_sensitivity: str
