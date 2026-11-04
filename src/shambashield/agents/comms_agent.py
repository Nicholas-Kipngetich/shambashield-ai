"""Farmer Communication Agent — polishes the deterministic message in-language.

The baseline message is the rule-based FarmerMessage; this agent rephrases it
for warmth and clarity WITHOUT changing any fact. Its JSON output is
validated against the hard caps (<=120 words) and the numeric grounding
answer key; any violation or failure returns the baseline unchanged.
"""

from __future__ import annotations

import json
import re

from ..contracts import FarmerMessage, WeatherFindings
from ..tools.farmers_comms import ground_numbers
from .scaffolding import NEVER_INVENT, Narration, run_agent

_SYSTEM = (
    "You are ShambaShield's Farmer Communication Agent. You receive a draft "
    "farmer message in JSON. Rewrite headline, body (at most 120 words), "
    "action_sentence and uncertainty_note in the requested language, keeping "
    "every fact identical. Reply with ONLY a JSON object using keys: "
    "headline, body, action_sentence, uncertainty_note. " + NEVER_INVENT
)

_NUMBERS = re.compile(r"-?\d+(?:\.\d+)?")


def parse_model_response(text: str) -> dict | None:
    """Parse the model's JSON object out of a possibly fenced reply."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) and "body" in parsed else None


def _grounded(message: dict, answer: dict[str, float]) -> bool:
    """Every number in the polished text must round-trip to a metric."""
    for token in _NUMBERS.findall(
        " ".join(
            str(message.get(k, ""))
            for k in ("headline", "body", "action_sentence", "uncertainty_note")
        )
    ):
        if not any(abs(float(token) - value) <= 1.0 for value in answer.values()):
            return False
    return True


def message_from_polished(message: dict, language: str) -> FarmerMessage:
    """Build a validated FarmerMessage from the model's JSON."""
    return FarmerMessage(
        language=language,  # type: ignore[arg-type]
        headline=str(message.get("headline") or "").strip(),
        body=str(message.get("body") or "").strip(),
        action_sentence=str(message.get("action_sentence") or "").strip(),
        uncertainty_note=str(message.get("uncertainty_note") or "").strip(),
    )


def run(
    draft: FarmerMessage,
    findings: WeatherFindings,
    model=None,
) -> tuple[Narration, FarmerMessage]:
    """Return (narration_status, final_message). Never returns a broken message."""
    baseline = draft.model_copy(deep=True)
    if model is None:
        return Narration(text=draft.body, degraded=True, error="Bedrock not configured"), baseline

    answer = ground_numbers(findings)
    payload = json.dumps(draft.model_dump(exclude={"language"}), ensure_ascii=False)
    narration = run_agent(model, _SYSTEM, payload + f"\n\nTarget language: {draft.language}")

    if narration.degraded or not narration.text:
        return narration.model_copy(update={"text": baseline.body}), baseline

    parsed = parse_model_response(narration.text)
    if parsed is None:
        return Narration(
            text=baseline.body, degraded=True, error="unparseable model output"
        ), baseline
    try:
        polished = message_from_polished(parsed, draft.language)
    except Exception:  # noqa: BLE001 - contract validation failed
        return Narration(
            text=baseline.body, degraded=True, error="invalid polished message"
        ), baseline

    if not polished.headline or not polished.body:
        return Narration(text=baseline.body, degraded=True, error="empty polished fields"), baseline
    if not _grounded(parsed, answer):
        return (
            Narration(
                text=baseline.body, degraded=True, error="polished message failed numeric grounding"
            ),
            baseline,
        )
    return Narration(text=polished.body, degraded=False), polished


__all__ = ["message_from_polished", "parse_model_response", "run"]
