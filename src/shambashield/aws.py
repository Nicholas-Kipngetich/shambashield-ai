"""AWS session and Bedrock model factories.

Keeping this in one place means agents never read credentials or construct
clients themselves. If a named profile is configured, we set ``AWS_PROFILE``
before constructing any Strands model so the SDK's internal boto3 session
uses the same profile.
"""

from __future__ import annotations

import os
from typing import Any

import boto3
from strands.models import BedrockModel

from .config import Settings, get_settings

DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = 2048


def get_boto_session(settings: Settings | None = None) -> boto3.Session:
    """Create a boto3 session using the configured profile and region."""
    settings = settings or get_settings()
    if settings.aws_profile:
        # boto3.Session uses this explicitly; setting it also helps libraries
        # that build their own default session (e.g. Strands internals).
        os.environ.setdefault("AWS_PROFILE", settings.aws_profile)
        return boto3.Session(
            profile_name=settings.aws_profile,
            region_name=settings.aws_region,
        )
    return boto3.Session(region_name=settings.aws_region)


def build_bedrock_model(
    model_id: str | None = None,
    *,
    settings: Settings | None = None,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    **model_kwargs: Any,
) -> BedrockModel:
    """Build a Strands Bedrock model, failing clearly when unconfigured."""
    settings = settings or get_settings()
    resolved_id = model_id or settings.bedrock_model_id
    if not resolved_id:
        raise ValueError(
            "No Bedrock model configured. Run `python scripts/check_bedrock.py --list`, "
            "then set BEDROCK_MODEL_ID in .env."
        )

    if settings.bedrock_api_key is not None:
        # Bedrock API keys are bearer tokens for the runtime endpoint; they are
        # an alternative to SigV4 credentials, not a replacement for listing
        # models. See docs/PHASE2_SETUP.md.
        return BedrockModel(
            model_id=resolved_id,
            region_name=settings.aws_region,
            api_key=settings.bedrock_api_key.get_secret_value(),
            temperature=temperature,
            max_tokens=max_tokens,
            **model_kwargs,
        )

    session = get_boto_session(settings)
    return BedrockModel(
        model_id=resolved_id,
        boto_session=session,
        temperature=temperature,
        max_tokens=max_tokens,
        **model_kwargs,
    )
