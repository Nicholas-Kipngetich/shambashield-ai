"""Bedrock-backed narrators with graceful degradation.

Each specialist is a thin wrapper around a Strands agent (agents-as-tools
pattern): the orchestrator calls the specialist, the specialist calls Bedrock,
and every specialist can FAIL SOFT — returning a rule-based fallback plus a
`degraded` flag so the UI can show the appropriate banner.

Hard rules enforced in every prompt:
- never introduce a number not present in the passed data,
- never change the risk tier or the actions selected by the engine.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from strands import Agent
from strands.models import BedrockModel

from ..aws import build_bedrock_model
from ..config import get_settings
from ..tools.hazard_rules import hazard_kind_label

log = logging.getLogger(__name__)

NEVER_INVENT = (
    "You may only rephrase and explain. You must NOT: introduce any number that "
    "does not appear in the data; change, soften or escalate the risk tier; "
    "add, remove or replace the recommended actions; remove any disclaimer or "
    "data-source note."
)


@dataclass
class Narration:
    """Result of one specialist call."""

    text: str
    degraded: bool
    error: str | None = None


def build_model(settings: Any = None, *, system: bool = True) -> BedrockModel | None:
    """Return a BedrockModel, or None when Bedrock is not configured."""
    settings = settings or get_settings()
    try:
        model = build_bedrock_model(settings=settings)
        _ = system
        return model
    except Exception as exc:  # noqa: BLE001 - any config problem degrades us
        log.info("Bedrock unavailable (%s); using rule-based fallback", exc)
        return None


def run_agent(model: BedrockModel, system_prompt: str, user_prompt: str) -> Narration:
    """Call a Strands agent once; any failure becomes a degraded narration."""
    try:
        agent = Agent(model=model, system_prompt=system_prompt)
        result = agent(user_prompt)
        text = (getattr(result, "message", None) or {}).get("content") or []
        plain = "".join(block.get("text", "") for block in text if isinstance(block, dict)).strip()
        if not plain:
            return Narration(text="", degraded=True, error="empty model response")
        return Narration(text=plain, degraded=False)
    except Exception as exc:  # noqa: BLE001 - degrade, never crash the app
        log.warning("Agent call failed (%s); falling back to rule-based text", exc)
        return Narration(text="", degraded=True, error=str(exc))


def hazards_payload(hazards: list) -> str:
    """Compact JSON of hazards for prompts: kinds, severities, evidence."""
    return json.dumps(
        [
            {
                "kind": hazard_kind_label(h.kind),
                "severity": h.severity,
                "evidence": h.evidence,
            }
            for h in hazards
        ],
        indent=1,
    )
