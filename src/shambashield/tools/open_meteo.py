"""HTTP client for the Open-Meteo forecast and geocoding APIs.

Design rules:
- Never fabricate data: if the API is unreachable we raise, and callers decide
  whether to fall back to a labelled demo snapshot.
- Retry only transient failures (network, 5xx). Client errors prevent retrying.
- All numeric values are returned through the typed contracts so every
  downstream consumer sees one normalised shape.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from datetime import timezone as dt_timezone
from functools import lru_cache
from typing import Any

import httpx
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_fixed

from ..config import get_settings
from ..contracts import DailyForecast, LocationPoint, WeatherSnapshot
from ..geo import get_county

DEFAULT_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DEFAULT_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
KENYA_TIMEZONE = "Africa/Nairobi"
KENYA_COUNTRY_CODE = "KE"
FORECAST_DAYS = 7

_DAILY_VARIABLES = ",".join(
    [
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_sum",
        "precipitation_probability_max",
        "et0_fao_evapotranspiration",
        "wind_speed_10m_max",
    ]
)


class ForecastAPIError(Exception):
    """A permanent problem with the API request (bad params, provider error)."""


class ForecastUnavailableError(Exception):
    """The forecast could not be retrieved (network down, provider outage)."""


class TransientForecastError(Exception):
    """A retryable transport/server failure. Internal to this module."""


class OpenMeteoClient:
    """Small wrapper around httpx with typed parsing and polite retries."""

    def __init__(
        self,
        timeout_seconds: float = 15.0,
        *,
        forecast_url: str = DEFAULT_FORECAST_URL,
        geocoding_url: str = DEFAULT_GEOCODING_URL,
        max_attempts: int = 3,
        backoff_seconds: float = 0.5,
    ) -> None:
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout_seconds),
            headers={"User-Agent": "ShambaShieldAI/0.1 (+https://github.com/aws)"},
        )
        self._forecast_url = forecast_url
        self._geocoding_url = geocoding_url
        self._max_attempts = max_attempts
        self._backoff_seconds = backoff_seconds

    # ------------------------------------------------------------------ #
    # Context manager plumbing so callers never leave sockets open
    # ------------------------------------------------------------------ #
    def __enter__(self) -> OpenMeteoClient:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------------ #
    # Low-level request
    # ------------------------------------------------------------------ #
    def _request_json(self, url: str, params: dict[str, Any]) -> Any:
        retrying = Retrying(
            retry=retry_if_exception_type(TransientForecastError),
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_fixed(self._backoff_seconds),
            reraise=True,
        )
        try:
            return retrying(self._request_once, url, params)
        except TransientForecastError as exc:
            raise ForecastUnavailableError(
                f"Open-Meteo unreachable after {self._max_attempts} attempts: {exc}"
            ) from exc

    def _request_once(self, url: str, params: dict[str, Any]) -> Any:
        try:
            response = self._client.get(url, params=params)
        except httpx.TransportError as exc:
            raise TransientForecastError(f"transport error: {exc}") from exc

        if response.status_code >= 500:
            raise TransientForecastError(f"server error {response.status_code}")
        if response.status_code != 200:
            raise ForecastAPIError(
                f"Open-Meteo returned HTTP {response.status_code}: {response.text[:200]}"
            )
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise ForecastAPIError("Open-Meteo returned invalid JSON") from exc

        if isinstance(payload, dict) and payload.get("error"):
            raise ForecastAPIError(str(payload.get("reason") or "API error"))
        return payload

    # ------------------------------------------------------------------ #
    # Geocoding
    # ------------------------------------------------------------------ #
    def geocode(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        payload = self._request_json(
            self._geocoding_url,
            {"name": query, "count": limit, "language": "en", "format": "json"},
        )
        return list(payload.get("results") or [])

    # ------------------------------------------------------------------ #
    # Forecast
    # ------------------------------------------------------------------ #
    def get_forecast_raw(
        self,
        latitude: float,
        longitude: float,
        forecast_timezone: str = KENYA_TIMEZONE,
    ) -> dict[str, Any]:
        return self._request_json(
            self._forecast_url,
            {
                "latitude": latitude,
                "longitude": longitude,
                "daily": _DAILY_VARIABLES,
                "hourly": "precipitation",
                "forecast_days": FORECAST_DAYS,
                "timezone": forecast_timezone,
                "temperature_unit": "celsius",
                "precipitation_unit": "mm",
                "wind_speed_unit": "kmh",
            },
        )


def normalise_forecast(
    payload: dict[str, Any],
    *,
    location: LocationPoint,
    snapshot_timezone: str = KENYA_TIMEZONE,
    source: str = "open-meteo",
) -> WeatherSnapshot:
    """Turn an Open-Meteo payload into a WeatherSnapshot without guessing."""
    daily = payload.get("daily") or {}
    times = daily.get("time") or []
    if not times:
        raise ForecastUnavailableError("Open-Meteo returned no forecast days")

    hourly_rain: list[float] | None = None
    hourly = payload.get("hourly") or {}
    if hourly.get("precipitation") is not None:
        hourly_rain = [float(v) for v in (hourly.get("precipitation") or [])]

    days = [
        DailyForecast(
            date=date.fromisoformat(str(times[i])),
            tmax_c=_number(daily.get("temperature_2m_max"), i),
            tmin_c=_number(daily.get("temperature_2m_min"), i),
            rain_mm=_number(daily.get("precipitation_sum"), i) or 0.0,
            rain_probability_pct=_optional_int(daily.get("precipitation_probability_max"), i),
            et0_mm=_optional_number(daily.get("et0_fao_evapotranspiration"), i),
            wind_max_kmh=_optional_number(daily.get("wind_speed_10m_max"), i),
        )
        for i in range(len(times))
    ]

    return WeatherSnapshot(
        county=location.county,
        location_name=location.name,
        latitude=location.latitude,
        longitude=location.longitude,
        timezone=snapshot_timezone,
        retrieved_at=datetime.now(dt_timezone.utc).replace(microsecond=0),
        source=source,
        days=days,
        hourly_rain_mm=hourly_rain,
    )


def _number(series: Any, index: int) -> float:
    value = (series or [])[index] if isinstance(series, list) else None
    if value is None:
        raise ForecastAPIError("Open-Meteo response is missing required daily values")
    return float(value)


def _optional_number(series: Any, index: int) -> float | None:
    value = (series or [])[index] if isinstance(series, list) else None
    return None if value is None else float(value)


def _optional_int(series: Any, index: int) -> int | None:
    value = _optional_number(series, index)
    return None if value is None else int(round(value))


# ---------------------------------------------------------------------- #
# High-level helpers used by the app
# ---------------------------------------------------------------------- #
@lru_cache(maxsize=256)
def _geocode_cached(url: str, query: str) -> tuple[dict[str, Any], ...]:
    """Module-level cached geocoding so repeated assessments are cheap."""
    settings = get_settings()
    with OpenMeteoClient(
        timeout_seconds=settings.open_meteo_timeout_seconds,
        geocoding_url=url,
    ) as client:
        return tuple(client.geocode(query))


def resolve_location(county: str, location: str | None = None) -> LocationPoint:
    """Resolve a farmer's county/location into a LocationPoint."""
    county_point = get_county(county)
    if not location or not location.strip():
        return county_point

    settings = get_settings()
    results = _geocode_cached(settings.open_meteo_geocoding_url, location.strip())
    kenyan = [r for r in results if (r.get("country_code") or "").upper() == KENYA_COUNTRY_CODE]
    chosen = kenyan[0] if kenyan else (results[0] if results else None)
    if chosen is None:
        return county_point

    return LocationPoint(
        county=county_point.county,
        name=str(chosen.get("name") or location.strip()),
        latitude=float(chosen["latitude"]),
        longitude=float(chosen["longitude"]),
        approximated=False,
        note=None if kenyan else "Geocoded place outside Kenya; using best match",
    )


def get_forecast(location: LocationPoint) -> WeatherSnapshot:
    """Fetch and normalise the 7-day forecast for a resolved location."""
    settings = get_settings()
    with OpenMeteoClient(timeout_seconds=settings.open_meteo_timeout_seconds) as client:
        payload = client.get_forecast_raw(location.latitude, location.longitude)
    return normalise_forecast(payload, location=location)
