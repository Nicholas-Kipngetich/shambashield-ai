"""Application settings loaded from environment variables and ``.env``.

Phase 2 only needs AWS and model configuration. Forecast and risk settings are
added in later phases, but the structure is already in place so secrets never
appear in code.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["development", "test", "production"]


class Settings(BaseSettings):
    """Runtime configuration.

    Environment variables take precedence over values in ``.env``.
    Field names map case-insensitively, so ``aws_region`` reads ``AWS_REGION``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: AppEnv = "development"
    log_level: str = "INFO"

    # AWS / Bedrock
    aws_region: str = Field(default="us-east-1", min_length=2)
    aws_profile: str | None = None
    bedrock_model_id: str | None = None
    bedrock_orchestrator_model_id: str | None = None
    # Optional bearer token generated in the Bedrock console. Prefer SSO for
    # anything beyond a local hackathon demo. Never commit this value.
    bedrock_api_key: SecretStr | None = None

    # Open-Meteo (used from Phase 3)
    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    open_meteo_geocoding_url: str = "https://geocoding-api.open-meteo.com/v1/search"
    open_meteo_timeout_seconds: float = Field(default=15.0, gt=0, le=60)

    # Safety switches
    force_demo_data: bool = False

    @field_validator("log_level")
    @classmethod
    def _normalise_log_level(cls, value: str) -> str:
        level = value.upper().strip()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}, got {value!r}")
        return level

    @field_validator("aws_region")
    @classmethod
    def _normalise_region(cls, value: str) -> str:
        return value.strip().lower()

    @property
    def orchestrator_model_id(self) -> str | None:
        """Use the stronger orchestrator model when configured, else the default."""
        return self.bedrock_orchestrator_model_id or self.bedrock_model_id

    @property
    def bedrock_configured(self) -> bool:
        return bool(self.bedrock_model_id)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return one cached settings instance for the process."""
    return Settings()
