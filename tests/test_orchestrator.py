"""End-to-end pipeline tests (offline: demo snapshot, no Bedrock)."""

from __future__ import annotations

import pytest

from shambashield.agents.orchestrator import DISCLAIMER, PipelineResult, run_shambashield
from shambashield.contracts import FarmerProfile, FinalReport


@pytest.fixture(name="result")
def offline_result() -> PipelineResult:
    settings = None  # no .env influence: Bedrock stays unconfigured in CI
    return run_shambashield(
        county="Machakos",
        crop="maize",
        stage="flowering",
        language="en",
        demo_snapshot="machakos_drought",
        settings=settings,
    )


def test_full_pipeline_returns_valid_report(result: PipelineResult) -> None:
    report = result.report
    assert isinstance(report, FinalReport)
    assert report.assessment_id.startswith("ssa-")
    assert report.farmer == FarmerProfile(
        county="Machakos",
        location=None,
        crop="maize",
        stage="flowering",
        language="en",
        latitude=None,
        longitude=None,
    )
    assert report.weather.county == "Machakos"
    assert report.risk_level in {"low", "moderate", "high", "unknown"}


def test_offline_run_is_fully_degraded_and_labelled(result: PipelineResult) -> None:
    report = result.report
    assert report.degraded_mode is True  # rule-based narration + demo data
    assert report.weather.source == "demo"
    names = [name for name, _ in result.insights]
    assert names == [
        "Weather Intelligence Agent",
        "Crop Risk Agent",
        "Action Planner Agent",
        "Farmer Communication Agent",
    ]
    assert all(n.degraded for _name, n in result.insights)


def test_machakos_drought_fixture_rates_high(result: PipelineResult) -> None:
    report = result.report
    assert report.weather_findings.hazards
    assert report.risk_level == "high"
    assert any(d.startswith("Weather hazard: drought") for d in report.risk_rationale)


def test_message_is_bilingual_capable() -> None:
    en = run_shambashield(
        county="Machakos",
        crop="maize",
        stage="flowering",
        language="en",
        demo_snapshot="machakos_drought",
    ).report
    sw = run_shambashield(
        county="Machakos",
        crop="maize",
        stage="flowering",
        language="sw",
        demo_snapshot="machakos_drought",
    ).report
    assert en.farmer_message.language == "en"
    assert sw.farmer_message.language == "sw"
    assert len(sw.farmer_message.body.split()) <= 120


def test_force_demo_setting_triggers_labelled_data() -> None:
    from shambashield.config import Settings

    result = run_shambashield(
        county="Garissa",
        crop="beans",
        stage="harvest",
        settings=Settings(force_demo_data=True),
    )
    assert result.report.weather.source == "demo"


def test_disclaimer_is_bundled(result: PipelineResult) -> None:
    assert result.report.disclaimer == DISCLAIMER
    assert "hackathon prototype" in result.report.disclaimer
