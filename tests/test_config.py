"""Tests for configuration loading. No AWS calls."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shambashield.config import Settings


def test_defaults_are_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)

    settings = Settings(_env_file=None)

    assert settings.aws_region == "us-east-1"
    assert settings.open_meteo_timeout_seconds > 0
    assert settings.bedrock_model_id is None
    assert settings.force_demo_data is False


def test_orchestrator_falls_back_to_default_model() -> None:
    settings = Settings(_env_file=None, bedrock_model_id="test-model")
    assert settings.orchestrator_model_id == "test-model"


def test_orchestrator_uses_explicit_model() -> None:
    settings = Settings(
        _env_file=None,
        bedrock_model_id="small-model",
        bedrock_orchestrator_model_id="large-model",
    )
    assert settings.orchestrator_model_id == "large-model"


def test_invalid_log_level_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, log_level="LOUD")


def test_region_is_normalised() -> None:
    settings = Settings(_env_file=None, aws_region="  US-EAST-1  ")
    assert settings.aws_region == "us-east-1"
