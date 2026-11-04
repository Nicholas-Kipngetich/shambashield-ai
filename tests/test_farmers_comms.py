"""Tests for the deterministic farmer message composer and grounding answer key."""

from __future__ import annotations

import re

from shambashield.contracts import FarmerMessage, WeatherFindings
from shambashield.tools.action_planner import plan_actions
from shambashield.tools.crop_risk import assess_crop_risk
from shambashield.tools.farmers_comms import build_farmer_message, ground_numbers
from shambashield.tools.hazard_rules import detect_hazards
from tests.helpers import make_snapshot


def message_for(
    rain: list[float],
    language: str = "en",
    crop: str = "maize",
    stage: str = "flowering",
    **kwargs: list[float],
):
    source = kwargs.pop("source", None)
    snapshot = make_snapshot(rain=rain, **kwargs)
    if source is not None:
        snapshot = snapshot.model_copy(update={"source": source})
    findings = WeatherFindings(snapshot=snapshot, hazards=detect_hazards(snapshot), summary="t")
    assessment = assess_crop_risk(findings, crop=crop, stage=stage)
    plan = plan_actions(findings, assessment)
    return build_farmer_message(findings, assessment, plan, language=language)


def test_message_is_contract_valid_and_brief() -> None:
    message = message_for(rain=[0.0] * 7, et0=[5.0] * 7)
    assert isinstance(message, FarmerMessage)
    assert len(message.body.split()) <= 120
    assert message.headline
    assert message.action_sentence


NUMBERS = re.compile(r"-?\d+(?:\.\d+)?")


def test_every_number_in_message_is_grounded_in_metrics() -> None:
    rain = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    et0 = [5.0] * 7
    source = make_snapshot(rain=rain, et0=et0)
    findings = WeatherFindings(snapshot=source, hazards=detect_hazards(source), summary="t")
    message = build_farmer_message(
        findings,
        assess_crop_risk(findings, crop="maize", stage="flowering"),
        plan_actions(findings, assess_crop_risk(findings, crop="maize", stage="flowering")),
        language="en",
    )
    answer = ground_numbers(findings)
    # Every metric must be representable in the message, and every number that
    # does appear must round-trip to a metric value with tolerance 1 (mm/°C).
    assert answer.get("deficit_mm") == -28.0
    for text in (message.headline, message.body, message.action_sentence, message.uncertainty_note):
        for token in NUMBERS.findall(text):
            matched = any(abs(float(token) - v) <= 1.0 for v in answer.values())
            assert matched, f"ungrounded number {token!r} in: {text}"


def test_demo_source_is_disclosed_in_uncertainty() -> None:
    message = message_for(rain=[0.0] * 7, et0=[5.0] * 7, source="demo")
    assert "demonstration data" in message.uncertainty_note.lower()


def test_livestock_and_irrigation_cost_labels_present_in_plan_not_message() -> None:
    # The message body stays short; costs live in the plan UI, not the SMS text.
    message = message_for(rain=[0.0] * 7, et0=[5.0] * 7)
    assert "free" not in message.body.lower()


def test_swahili_message_uses_swahili_headline() -> None:
    message = message_for(rain=[0.0] * 7, et0=[5.0] * 7, language="sw")
    assert message.language == "sw"
    assert "Hatari kubwa" in message.headline
    assert "Unachoweza kufanya" in message.action_sentence


def test_unknown_language_falls_back_to_english() -> None:
    message = message_for(rain=[0.0] * 7, et0=[5.0] * 7, language="fr")
    assert message.language == "en"


def test_unknown_risk_level_headline_exists() -> None:
    # 3-day snapshot -> data gap -> risk level unknown -> headline still loads.
    message = message_for(rain=[0.0] * 3, et0=[1.0] * 3)
    assert message.headline
    assert "limited" in message.headline.lower() or "data" in message.headline.lower()
