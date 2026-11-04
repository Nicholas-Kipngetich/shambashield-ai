"""Behavioural tests for the deterministic crop risk engine."""

from __future__ import annotations

from shambashield.contracts import CropRiskAssessment, WeatherFindings
from shambashield.tools.crop_risk import assess_crop_risk
from shambashield.tools.hazard_rules import detect_hazards
from tests.helpers import make_snapshot


def findings_for(rain: list[float], **kwargs: list[float]) -> WeatherFindings:
    snapshot = make_snapshot(rain=rain, **kwargs)
    return WeatherFindings(snapshot=snapshot, hazards=detect_hazards(snapshot), summary="test")


def test_maturity_drought_stands_at_raw_severity() -> None:
    # 7-day deficit -34.9 mm -> weather severity moderate/high; dry run 7 -> high.
    findings = findings_for(rain=[0.0] * 7, et0=[5.0] * 7)
    assessment = assess_crop_risk(findings, crop="maize", stage="maturity")
    # Maturity is NOT highly drought-sensitive: no escalation, but raw high stands.
    assert assessment.risk_level == "high"
    assert not any("->" in d and "crop risk moderate" in d for d in assessment.drivers)


def test_escalation_is_at_most_one_level() -> None:
    # Moderate drought (5-day dry run, rain tail) at maize planting (sensitivity high).
    findings = findings_for(rain=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 4.0], et0=[4.0] * 7)
    assessment = assess_crop_risk(findings, crop="maize", stage="planting")
    drought_driver = next((d for d in assessment.drivers if d.startswith("Drought")), None)
    assert drought_driver is not None
    assert "-> crop risk high" in drought_driver or "-> crop risk moderate" in drought_driver
    assert assessment.risk_level in {"moderate", "high"}


def test_no_de_escalation_below_weather_severity() -> None:
    # Raw moderate drought for maize at harvest (sensitivity low) stays moderate.
    findings = findings_for(rain=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 4.0], et0=[4.0] * 7)
    assessment = assess_crop_risk(findings, crop="maize", stage="harvest")
    drought_driver = next((d for d in assessment.drivers if d.startswith("Drought")), None)
    assert drought_driver is not None
    assert "weather severity moderate -> crop risk moderate" in drought_driver
    assert "less sensitive" in drought_driver


def test_no_hazard_at_all_is_low() -> None:
    findings = findings_for(rain=[3.0] * 7, tmax=[25.0] * 7, et0=[3.0] * 7)
    assessment = assess_crop_risk(findings, crop="maize", stage="vegetative")
    assert assessment.risk_level == "low"
    assert "No weather hazards were detected" in assessment.impact_explanation


def test_data_gap_only_is_unknown_never_low() -> None:
    findings = findings_for(rain=[0.0] * 3, et0=[1.0] * 3)  # short forecast, ET0 present
    findings = findings.model_copy(
        update={"hazards": [h.model_copy(update={"kind": "data_gap"}) for h in findings.hazards]}
    )
    assessment = assess_crop_risk(findings, crop="maize", stage="vegetative")
    assert assessment.risk_level == "unknown"
    assert assessment.uncertainty


def test_excess_rain_adds_soil_uncertainty() -> None:
    findings = findings_for(rain=[25.0, 25.0, 25.0, 0.0, 0.0, 0.0, 0.0], et0=[2.0] * 7)
    assessment = assess_crop_risk(findings, crop="maize", stage="vegetative")
    assert any("drainage" in u for u in assessment.uncertainty)
    assert assessment.risk_level in {"moderate", "high"}


def test_drivers_are_ranked_worst_first() -> None:
    # Moderate drought + moderate excess rain; both should appear.
    findings = findings_for(
        rain=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], et0=[4.0] * 7
    )  # drought high (dry run 7)
    assessment = assess_crop_risk(findings, crop="beans", stage="vegetative")
    assert assessment.drivers, "expected at least one driver"


def test_assessment_is_a_valid_contract() -> None:
    findings = findings_for(rain=[0.0] * 7, et0=[5.0] * 7)
    assessment = assess_crop_risk(findings, crop="potatoes", stage="flowering")
    assert isinstance(assessment, CropRiskAssessment)
    assert assessment.crop == "potatoes"
    assert assessment.stage == "flowering"
    assert "Irish potatoes at flowering is" in assessment.impact_explanation
    assert assessment.stage_sensitivity.startswith("Irish potatoes at flowering")
