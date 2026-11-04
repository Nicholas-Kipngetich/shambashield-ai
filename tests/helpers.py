"""Shared helpers for constructing snapshots in tests. Deterministic dates."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from shambashield.contracts import DailyForecast, WeatherSnapshot

_START = date(2026, 1, 1)


def make_snapshot(
    *,
    rain: list[float],
    tmax: list[float] | None = None,
    tmin: list[float] | None = None,
    et0: list[float] | None = None,
    wind: list[float] | None = None,
    probability: list[int] | None = None,
    county: str = "Test",
) -> WeatherSnapshot:
    """Build a snapshot from per-day series lists; missing series become None."""
    count = len(rain)
    tmax = tmax if tmax is not None else [25.0] * count
    tmin = tmin if tmin is not None else [12.0] * count
    probability = probability if probability is not None else ([10] * count)

    days = [
        DailyForecast(
            date=_START + timedelta(days=i),
            tmax_c=float(tmax[i]),
            tmin_c=float(tmin[i]),
            rain_mm=float(rain[i]),
            rain_probability_pct=int(probability[i]),
            et0_mm=float(et0[i]) if et0 is not None else None,
            wind_max_kmh=float(wind[i]) if wind is not None else None,
        )
        for i in range(count)
    ]
    return WeatherSnapshot(
        county=county,
        location_name=county,
        latitude=-1.5,
        longitude=37.25,
        timezone="Africa/Nairobi",
        retrieved_at=datetime(2026, 1, 1, 6, 0, tzinfo=timezone.utc),
        source="open-meteo",
        days=days,
        hourly_rain_mm=None,
    )
