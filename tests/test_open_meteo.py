"""Open-Meteo client tests (mocked HTTP via respx)."""

from __future__ import annotations

from datetime import date

import httpx
import pytest
import respx

from shambashield.contracts import LocationPoint
from shambashield.tools.open_meteo import (
    DEFAULT_FORECAST_URL,
    ForecastAPIError,
    ForecastUnavailableError,
    OpenMeteoClient,
    normalise_forecast,
)

LAGOS = LocationPoint(county="Kisumu", name="Kisumu", latitude=-0.09, longitude=34.77)


def forecast_payload(count: int = 7) -> dict:
    return {
        "latitude": -0.09,
        "longitude": 34.77,
        "timezone": "Africa/Nairobi",
        "daily": {
            "time": [f"2026-01-{d:02d}" for d in range(1, count + 1)],
            "temperature_2m_max": [30.0 + i for i in range(count)],
            "temperature_2m_min": [18.0] * count,
            "precipitation_sum": [0.0, 2.0, 5.0, 0.0, 0.5, 0.0, 1.5][:count],
            "precipitation_probability_max": [5, 20, 35, 10, 12, 8, 25][:count],
            "et0_fao_evapotranspiration": [5.0] * count,
            "wind_speed_10m_max": [12.0] * count,
        },
        "hourly": {"time": ["2026-01-01T00:00"], "precipitation": [0.0]},
    }


@respx.mock
def test_get_forecast_parses_into_snapshot() -> None:
    respx.get(DEFAULT_FORECAST_URL).respond(json=forecast_payload())
    with OpenMeteoClient(timeout_seconds=1) as client:
        payload = client.get_forecast_raw(LAGOS.latitude, LAGOS.longitude)
    snapshot = normalise_forecast(payload, location=LAGOS)

    assert snapshot.county == "Kisumu"
    assert snapshot.source == "open-meteo"
    assert len(snapshot.days) == 7
    assert snapshot.days[0].date == date(2026, 1, 1)
    assert snapshot.days[0].tmax_c == 30.0
    assert snapshot.days[0].et0_mm == 5.0
    assert snapshot.total_rain_mm() == 9.0
    assert snapshot.max_tmax_c() == 36.0


@respx.mock
def test_transient_500_is_retried() -> None:
    route = respx.get(DEFAULT_FORECAST_URL)
    route.side_effect = [
        httpx.Response(500, json={"error": "boom"}),
        httpx.Response(200, json=forecast_payload()),
    ]
    with OpenMeteoClient(timeout_seconds=1, max_attempts=3, backoff_seconds=0.0) as client:
        payload = client.get_forecast_raw(LAGOS.latitude, LAGOS.longitude)
    assert payload["daily"]["time"]  # second attempt succeeded


@respx.mock
def test_persistent_500_becomes_forecast_unavailable() -> None:
    route = respx.get(DEFAULT_FORECAST_URL)
    route.side_effect = [httpx.Response(500, json={"error": "down"})] * 2
    with OpenMeteoClient(timeout_seconds=1, max_attempts=2, backoff_seconds=0.0) as client:
        with pytest.raises(ForecastUnavailableError):
            client.get_forecast_raw(LAGOS.latitude, LAGOS.longitude)


@respx.mock
def test_client_error_is_not_retried() -> None:
    respx.get(DEFAULT_FORECAST_URL).mock(
        side_effect=httpx.Response(400, json={"reason": "bad params"})
    )
    with OpenMeteoClient(timeout_seconds=1, max_attempts=3, backoff_seconds=0.0) as client:
        with pytest.raises(ForecastAPIError):
            client.get_forecast_raw(LAGOS.latitude, LAGOS.longitude)


@respx.mock
def test_empty_daily_cannot_be_normalised() -> None:
    respx.get(DEFAULT_FORECAST_URL).respond(
        json={"latitude": 0, "longitude": 0, "daily": {"time": []}}
    )
    with OpenMeteoClient(timeout_seconds=1) as client:
        payload = client.get_forecast_raw(LAGOS.latitude, LAGOS.longitude)
    assert payload["daily"]["time"] == []
    with pytest.raises(ForecastUnavailableError):
        normalise_forecast(payload, location=LAGOS)


def test_missing_required_value_is_api_error() -> None:
    payload = forecast_payload(count=3)
    payload["daily"].pop("temperature_2m_max")
    with pytest.raises(ForecastAPIError):
        normalise_forecast(payload, location=LAGOS)


def test_missing_et0_is_allowed() -> None:
    payload = forecast_payload(count=3)
    payload["daily"].pop("et0_fao_evapotranspiration")
    snapshot = normalise_forecast(payload, location=LAGOS)
    assert snapshot.days[0].et0_mm is None
