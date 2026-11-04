"""Rule-based farmer message composer.

This is the LLM-FREE baseline for the Farmer Communication stage:
- works with or without Bedrock, so the farmer never gets nothing;
- fills templates ONLY with measured values (hazard metrics) and curated
  labels (crop/stage/place names, action titles);
- carries the uncertainty note and demo-data disclaimers verbatim from the
  upstream assessment, so wording can never silently soften facts.

The Strands translator agent (Phase 7) later rephrases this message for warmth
and clarity. It must not change numbers: the Phase 10 grounding validator
compares its output against this baseline's `ground_numbers` answer key.
"""

from __future__ import annotations

from ..action_catalog import load_catalog
from ..contracts import (
    ActionPlan,
    CropRiskAssessment,
    FarmerMessage,
    Language,
    WeatherFindings,
)
from ..crops import get_crop
from ..messaging import load_phrasebook, templates_for

_STAGE_LABELS = {
    "land_preparation": ("land preparation", "utayarishaji wa shamba"),
    "planting": ("planting", "kupanda"),
    "emergence": ("emergence", "kuchipuka"),
    "vegetative": ("vegetative growth", "ukuaji wa majani"),
    "flowering": ("flowering", "kutoa maua"),
    "grain_filling": ("grain filling / tuber bulking", "kujaza nafaka"),
    "maturity": ("maturity", "kukomaa"),
    "harvest": ("harvest", "kuvuna"),
}
_SEVERITY_RANK = {"low": 0, "moderate": 1, "high": 2}
_MAX_HAZARD_LINES = 4
_MAX_ACTION_TITLES = 3
_MAX_UNCERTAINTY_NOTES = 2


def _stage_label(stage: str, language: str) -> str:
    pair = _STAGE_LABELS.get(stage, (stage, stage))
    return pair[1] if language == "sw" else pair[0]


def _hazard_lines(findings: WeatherFindings, t: dict) -> list[str]:
    """Format one deterministic sentence per hazard, worst first."""
    lines: list[str] = []
    kinds = templates_section(t, "hazard_lines")
    for hazard in sorted(findings.hazards, key=lambda h: _SEVERITY_RANK[h.severity], reverse=True)[
        :_MAX_HAZARD_LINES
    ]:
        metrics = hazard.metrics
        if hazard.kind == "drought":
            if "deficit_mm" in metrics:
                lines.append(kinds["drought"].format(deficit_mm=metrics["deficit_mm"]))
            else:
                lines.append(kinds["drought_dry"])
        elif hazard.kind == "excess_rain":
            lines.append(kinds["excess_rain"].format(max_daily_mm=metrics.get("max_daily_mm", 0.0)))
        elif hazard.kind == "heat":
            lines.append(kinds["heat"].format(peak_tmax_c=metrics.get("peak_tmax_c", 0.0)))
        elif hazard.kind == "wind":
            lines.append(kinds["wind"].format(peak_wind_kmh=metrics.get("peak_wind_kmh", 0.0)))
        elif hazard.kind == "data_gap":
            lines.append(kinds["data_gap"])
    return lines


def templates_section(t: dict, name: str) -> dict:
    section = t.get(name)
    if not isinstance(section, dict):
        raise ValueError(f"Phrasebook is missing the {name!r} section")
    return section


def ground_numbers(findings: WeatherFindings) -> dict[str, float]:
    """Answer key for grounding: every number the message may legitimately show."""
    answer: dict[str, float] = {}
    for hazard in findings.hazards:
        for metric, value in hazard.metrics.items():
            answer[metric] = float(value)
    return answer


def build_farmer_message(
    findings: WeatherFindings,
    assessment: CropRiskAssessment,
    plan: ActionPlan,
    language: str = "en",
) -> FarmerMessage:
    """Compose the farmer-facing message with zero free-form text generation."""
    language = language if language in load_phrasebook() else "en"
    t = templates_for(language)
    snap = findings.snapshot
    place = snap.location_name
    crop_label = get_crop(assessment.crop).label

    headlines = templates_section(t, "headlines")
    headline = headlines[assessment.risk_level].format(crop=crop_label.lower(), place=place)

    lead = t["lead"].format(
        place=place, crop=crop_label.lower(), stage=_stage_label(assessment.stage, language)
    )
    hazard_sentences = _hazard_lines(findings, t)
    body = f"{lead} {' '.join(hazard_sentences)}".strip()

    action_sentence = ""
    if plan.actions:
        catalog = load_catalog()
        titles = []
        for action in plan.actions[:_MAX_ACTION_TITLES]:
            entry = catalog.get(action.action_id, {})
            title_field = "title_sw" if language == "sw" else "title_en"
            titles.append(t["act_item"].format(title=entry.get(title_field) or action.title))
        action_sentence = f"{t['act_lead']} {t['act_join'].join(titles)}{t['act_end']}"

    uncertainty_notes = list(assessment.uncertainty[:_MAX_UNCERTAINTY_NOTES])
    if snap.source == "demo":
        uncertainty_notes.append(t["demo_note"])
    uncertainty_notes.append(t["closing"])
    uncertainty_note = t["uncertainty_lead"] + t["uncertainty_join"].join(uncertainty_notes)

    return FarmerMessage(
        language=language,  # type: ignore[arg-type]
        headline=headline,
        body=body,
        action_sentence=action_sentence,
        uncertainty_note=uncertainty_note,
    )


__all__ = ["build_farmer_message", "ground_numbers", "Language"]
