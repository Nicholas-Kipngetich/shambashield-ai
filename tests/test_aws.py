"""Tests for the AWS session factory. No network calls."""

from __future__ import annotations

import pytest

from shambashield.aws import build_bedrock_model, get_boto_session
from shambashield.config import Settings


def test_session_uses_configured_region() -> None:
    settings = Settings(_env_file=None, aws_region="eu-west-1")
    session = get_boto_session(settings)
    assert session.region_name == "eu-west-1"


def test_model_requires_configuration() -> None:
    settings = Settings(_env_file=None, bedrock_model_id=None)
    with pytest.raises(ValueError, match="No Bedrock model configured"):
        build_bedrock_model(settings=settings)


def test_api_key_is_not_exposed_in_repr() -> None:
    settings = Settings(_env_file=None, bedrock_api_key="super-secret-value")
    assert "super-secret-value" not in repr(settings)
    assert settings.bedrock_api_key is not None
    assert settings.bedrock_api_key.get_secret_value() == "super-secret-value"


def test_api_key_model_builds_without_profile() -> None:
    settings = Settings(
        _env_file=None,
        aws_region="us-east-1",
        bedrock_api_key="test-api-key",
    )
    model = build_bedrock_model("test-model-id", settings=settings)
    assert model.config["model_id"] == "test-model-id"
