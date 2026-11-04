"""Orchestrator agent — one farmer request, in, out.

Agents-as-tools pattern: the orchestrator calls each specialist, each
specialist may call Bedrock internally, and every handoff is a typed contract
validated with Pydantic. Nothing controversial is decided here: the risk tier
comes from the deterministic engine; agents only narrate/explain/polish.

Degradation matrix implemented below:
- Bedrock not configured -> specialists narrate rule-based text, `degraded=True`.
- Open-Meteo unreachable -> clearly LABELLED demo snapshot, amber banner duty.
- force_demo_data setting -> same labelled-demo path (used in tests and demos).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..aws import build_bedrock_model
from ..config import Settings, get_settings
from ..contracts import (
    ActionPlan,
    CropRiskAssessment,
    FarmerProfile,
    FinalReport,
    WeatherFindings,
)
from ..demo import load_demo_snapshot
from ..logging_setup import get_logger
from ..tools.action_planner import plan_actions
from ..tools.crop_risk import assess_crop_risk
from ..tools.farmers_comms import build_farmer_message
from ..tools.hazard_rules import detect_hazards
from ..tools.open_meteo import (
    ForecastAPIError,
    ForecastUnavailableError,
    get_forecast,
    resolve_location,
)
from .comms_agent import run as polish_message
from .crop_agent import run as narrate_crop
from .planner_agent import run as narrate_plan
from .scaffolding import Narration
from .weather_agent import run as narrate_weather

log = get_logger(__name__)

DISCLAIMER = (
    "Generated from Open-Meteo forecast data, deterministic risk rules and a "
    "curated action catalog, with optional Amazon Bedrock narrative assistance. "
    "This is a hackathon prototype: verify with Kenya Meteorological Department "
    "bulletins and your local agricultural extension officer before acting."
)


@dataclass
class PipelineResult:
    """Full report plus per-agent insight (shown in the UI when Bedrock runs)."""

    report: FinalReport
    insights: list[tuple[str, Narration]] = field(default_factory=list)


def _rationale(
    findings: WeatherFindings,
    assessment: CropRiskAssessment,
    plan: ActionPlan,
) -> list[str]:
    lines = [f"Data source: {findings.snapshot.source}; days: {len(findings.snapshot.days)}."]
    for hazard in findings.hazards:
        key = next(iter(hazard.metrics), None)
        value = hazard.metrics.get(key) if key else None
        detail = f" ({key}: {value})" if key and value is not None else ""
        lines.append(f"Weather hazard: {hazard.kind} [{hazard.severity}]{detail}")
    lines.append(f"Crop tier: {assessment.risk_level} for {assessment.crop} at {assessment.stage}.")
    for driver in assessment.drivers:
        lines.append(f"- {driver}")
    lines.append(f"Plan: {len(plan.actions)} curated action(s), {len(plan.deferred)} deferred.")
    return lines


def run_shambashield(
    county: str,
    crop: str,
    stage: str,
    location: str | None = None,
    language: str = "en",
    settings: Settings | None = None,
    demo_snapshot: str | None = None,
    profile: FarmerProfile | None = None,
) -> PipelineResult:
    """Run the full pipeline for one farmer request and return a FinalReport."""
    settings = settings or get_settings()
    degraded = False
    insights: list[tuple[str, Narration]] = []

    model = None
    if settings.bedrock_configured:
        model = build_bedrock_model(settings=settings)
    else:
        log.info("Bedrock is not configured; running fully rule-based.")

    # ---- 1. Weather data -------------------------------------------- #
    if demo_snapshot or settings.force_demo_data:
        snapshot = load_demo_snapshot(demo_snapshot or "machakos_drought")
        degraded = True  # labelled demo data
    else:
        try:
            point = resolve_location(county, location)
            snapshot = get_forecast(point)
        except (ForecastUnavailableError, ForecastAPIError) as exc:
            log.error("Live forecast unavailable (%s); using labelled demo data", exc)
            snapshot = load_demo_snapshot("machakos_drought")
            degraded = True

    farmer = profile or FarmerProfile(
        county=snapshot.county,
        location=location,
        crop=crop,
        stage=stage,
        language=language,
    )
    if farmer.crop not in {"maize", "beans", "potatoes", "other"}:  # defensive validation
        raise ValueError(f"Unsupported crop: {farmer.crop}")

    findings = WeatherFindings(snapshot=snapshot, hazards=detect_hazards(snapshot), summary="")
    assessment = assess_crop_risk(findings, crop=farmer.crop, stage=farmer.stage)
    plan = plan_actions(findings, assessment)

    # ---- 2. Specialist narrations (agents-as-tools delegation) ------ #
    weather_narration = narrate_weather(findings, model)
    crop_narration = narrate_crop(assessment, model)
    plan_narration = narrate_plan(plan, model)
    insights += [
        ("Weather Intelligence Agent", weather_narration),
        ("Crop Risk Agent", crop_narration),
        ("Action Planner Agent", plan_narration),
    ]
    if any(n.degraded for _name, n in insights):
        degraded = True

    findings = findings.model_copy(update={"summary": weather_narration.text})
    draft_message = build_farmer_message(findings, assessment, plan, language=farmer.language)

    # ---- 3. Communication polish (validated, grounded) -------------- #
    comms_status, final_message = polish_message(draft_message, findings, model)
    insights.append(("Farmer Communication Agent", comms_status))
    if comms_status.degraded:
        degraded = True

    report = FinalReport(
        assessment_id=f"ssa-{uuid.uuid4().hex[:12]}",
        generated_at=datetime.now(timezone.utc).replace(microsecond=0),
        farmer=farmer,
        weather=snapshot,
        weather_findings=findings,
        crop_risk=assessment,
        action_plan=plan,
        farmer_message=final_message,
        risk_level=assessment.risk_level,
        risk_rationale=_rationale(findings, assessment, plan),
        degraded_mode=degraded,
        disclaimer=DISCLAIMER,
    )
    return PipelineResult(report=report, insights=insights)


__all__ = ["DISCLAIMER", "PipelineResult", "run_shambashield"]
