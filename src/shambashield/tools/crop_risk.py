"""Deterministic crop/stage risk assessment.

Escalation rule (from docs/PHASE1_ARCHITECTURE.md §6.3-6.4):
- sensitivity "high" may escalate a hazard by ONE level (low->moderate, moderate->high);
- the engine never de-escalates below the raw measured weather severity;
- insufficient data (data_gap hazards) forces risk_level "unknown", never "low".

The functions here are pure: no I/O, no LLM. The Crop Risk Agent later wraps
this engine with an LLM that only EXPLAINS the result.
"""

from __future__ import annotations

from ..contracts import (
    CropRiskAssessment,
    HazardKind,
    RiskLevel,
    Stage,
    WeatherFindings,
)
from ..crops import CropProfile, get_crop
from .hazard_rules import hazard_kind_label

_ESCALATION: dict[str, str] = {"low": "moderate", "moderate": "high", "high": "high"}
_SEVERITY_ORDER: dict[str, int] = {"low": 0, "moderate": 1, "high": 2}
_STAGE_LABELS: dict[str, str] = {
    "land_preparation": "land preparation",
    "planting": "planting",
    "emergence": "emergence",
    "vegetative": "vegetative growth",
    "flowering": "flowering",
    "grain_filling": "grain filling / tuber bulking",
    "maturity": "maturity",
    "harvest": "harvest",
}

# Hazards that describe data quality, not the crop itself.
_DATA_KINDS: tuple[str, ...] = ("data_gap",)


def _stage_label(stage: Stage) -> str:
    return _STAGE_LABELS.get(stage, stage)


def _sensitivity_phrase(sensitivity: str) -> str:
    return {
        "high": "highly sensitive",
        "moderate": "moderately sensitive",
        "low": "less sensitive",
    }.get(sensitivity, sensitivity)


def assess_crop_risk(
    findings: WeatherFindings,
    crop: str,
    stage: str,
    profile: CropProfile | None = None,
) -> CropRiskAssessment:
    """Produce the crop/stage view of the weather findings. Pure function."""
    crop_profile = profile or get_crop(crop)
    crop_name = crop_profile.crop
    stage_name: Stage = stage  # type: ignore[assignment]

    drivers: list[tuple[str, str, int]] = []  # (driver_text, final_severity, rank_key)
    uncertainty: list[str] = []

    for hazard in findings.hazards:
        if hazard.kind in _DATA_KINDS:
            uncertainty.extend(f"Limited data: {line}" for line in hazard.evidence)
            continue

        sensitivity = crop_profile.sensitivity(stage_name, hazard.kind)
        final_severity = _ESCALATION[hazard.severity] if sensitivity == "high" else hazard.severity
        text = (
            f"{hazard_kind_label(hazard.kind)}: weather severity {hazard.severity}"
            f" -> crop risk {final_severity}"
        )
        if final_severity != hazard.severity:
            text += (
                f" ({crop_profile.label.lower()} at {_stage_label(stage_name)} is "
                f"{_sensitivity_phrase(sensitivity)} to {hazard.kind})"
            )
        elif sensitivity == "low":
            text += (
                f" ({crop_profile.label.lower()} at {_stage_label(stage_name)} is "
                f"less sensitive, so the weather severity stands)"
            )
        drivers.append((text, final_severity, _SEVERITY_ORDER[hazard.severity]))

    # Rank by raw weather severity, then final severity: worst first.
    drivers.sort(key=lambda item: (item[2], _SEVERITY_ORDER[item[1]]), reverse=True)
    driver_texts = [text for text, _severity, _rank in drivers]
    final_severities = [severity for _text, severity, _rank in drivers]
    weather_drivers = [item for item in drivers if item[1] in ("moderate", "high")]

    # ---- Aggregate tier (§6.4): possibly-escalated severity wins ---- #
    weather_hazards = [h for h in findings.hazards if h.kind not in _DATA_KINDS]
    if any(severity == "high" for severity in final_severities):
        risk_level: RiskLevel = "high"
    elif any(severity == "moderate" for severity in final_severities):
        risk_level = "moderate"
    elif weather_hazards:
        risk_level = "low"
    else:
        # No weather hazard at all: unknown if data is thin, else genuinely low.
        risk_level = "unknown" if findings.hazards else "low"

    # ---- Impact explanation (deterministic text, no numbers) ---- #
    explanation_parts: list[str] = []
    kinds_seen: set[str] = set()
    for hazard in findings.hazards:
        if hazard.kind in _DATA_KINDS or hazard.kind in kinds_seen:
            continue
        kinds_seen.add(hazard.kind)
        relevance = crop_profile.sensitivity(stage_name, hazard.kind)
        explanation_parts.append(
            f"{crop_profile.label} at {_stage_label(stage_name)} is "
            f"{_sensitivity_phrase(relevance)} to {hazard_kind_label(hazard.kind).lower()}: "
            f"{crop_profile.impact(hazard.kind)}"
        )
    if not explanation_parts:
        explanation_parts.append(
            f"No weather hazards were detected for {crop_profile.label.lower()} at "
            f"{_stage_label(stage_name)} in the current forecast window."
        )

    # ---- Stage sensitivity summary ---- #
    parts = []
    for kind in ("drought", "excess_rain", "heat", "wind"):
        level = _sensitivity_phrase(crop_profile.sensitivity(stage_name, kind))
        parts.append(f"{kind.replace('_', ' ')} = {level}")
    stage_sensitivity = f"{crop_profile.label} at {_stage_label(stage_name)}: " + ", ".join(parts)

    # Uncertainty: drainage/soil always unknown for excess rain.
    for hazard in findings.hazards:
        if hazard.kind == "excess_rain":
            uncertainty.append(
                "Soil drainage and slope are unknown, so waterlogging impact varies by field."
            )

    if not weather_drivers and risk_level == "low":
        uncertainty.append(
            "No crop-specific hazards were flagged; thresholds may still miss local factors."
        )

    return CropRiskAssessment(
        crop=crop_name,
        stage=stage_name,
        risk_level=risk_level,
        drivers=driver_texts,
        impact_explanation=" ".join(explanation_parts),
        uncertainty=sorted(set(uncertainty)),
        stage_sensitivity=stage_sensitivity,
    )


__all__ = ["assess_crop_risk", "HazardKind"]
