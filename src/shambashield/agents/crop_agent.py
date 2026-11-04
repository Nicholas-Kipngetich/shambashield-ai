"""Crop Risk Agent — explains the deterministic crop/stage assessment."""

from __future__ import annotations

from ..contracts import CropRiskAssessment
from .scaffolding import NEVER_INVENT, Narration, run_agent

SYSTEM = (
    "You are ShambaShield's Crop Risk Agent for Kenyan smallholder farmers. "
    "Explain what the given rain/heat/wind outlook means for the crop at this "
    "specific growth stage, in 2-3 plain sentences. " + NEVER_INVENT
)


def baseline(assessment: CropRiskAssessment) -> str:
    return assessment.impact_explanation


def run(assessment: CropRiskAssessment, model=None) -> Narration:
    if model is None:
        return Narration(text=baseline(assessment), degraded=True, error="Bedrock not configured")
    prompt = (
        f"Crop: {assessment.crop}; stage: {assessment.stage}; "
        f"crop risk tier: {assessment.risk_level}\n"
        f"Drivers: {'; '.join(assessment.drivers) or 'none'}\n"
        f"Sensitivity: {assessment.stage_sensitivity}\n\n"
        "Explain the risk to this crop stage in 2-3 plain sentences."
    )
    narration = run_agent(model, SYSTEM, prompt)
    if narration.degraded or not narration.text:
        return Narration(text=baseline(assessment), degraded=True, error=narration.error)
    return narration
