"""Selection tests for the catalog-bound action planner."""

from __future__ import annotations

from shambashield.action_catalog import load_catalog
from shambashield.contracts import ActionPlan, WeatherFindings
from shambashield.tools.action_planner import plan_actions
from shambashield.tools.crop_risk import assess_crop_risk
from shambashield.tools.hazard_rules import detect_hazards
from tests.helpers import make_snapshot


def _findings(rain: list[float], **kwargs: list[float]) -> WeatherFindings:
    snapshot = make_snapshot(rain=rain, **kwargs)
    return WeatherFindings(snapshot=snapshot, hazards=detect_hazards(snapshot), summary="test")


def plan_for(rain: list[float], crop: str, stage: str, **kwargs: list[float]) -> ActionPlan:
    findings = _findings(rain, **kwargs)
    assessment = assess_crop_risk(findings, crop=crop, stage=stage)
    return plan_actions(findings, assessment)


def test_every_recommended_id_exists_in_catalog() -> None:
    plan = plan_for(rain=[0.0] * 7, et0=[5.0] * 7, crop="maize", stage="vegetative")
    catalog = load_catalog()
    assert plan.actions
    assert all(a.action_id in catalog for a in plan.actions)


def test_plan_is_capped_and_packed_with_best_match() -> None:
    plan = plan_for(rain=[0.0] * 7, et0=[5.0] * 7, crop="maize", stage="vegetative")
    assert len(plan.actions) <= 5
    urgencies = [a.urgency for a in plan.actions]
    ranks = [{"now": 0, "this_week": 1, "monitor": 2}[u] for u in urgencies]
    assert ranks == sorted(ranks), "actions must be urgency-ordered"


def test_drought_suggests_water_measures_not_drainage() -> None:
    plan = plan_for(rain=[0.0] * 7, et0=[5.0] * 7, crop="maize", stage="vegetative")
    chosen_ids = {a.action_id for a in plan.actions}
    assert "mulch_between_rows" in chosen_ids
    assert "open_drainage_channels" not in chosen_ids


def test_planting_drought_waits_for_moist_soil_first() -> None:
    # Moderate drought (5-day dry run) at planting: 'wait' is 'now' urgency.
    plan = plan_for(
        rain=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 4.0],
        et0=[4.0] * 7,
        crop="maize",
        stage="planting",
    )
    assert plan.actions[0].action_id == "wait_for_moist_soil"


def test_harvest_excess_rain_prioritises_early_harvest() -> None:
    plan = plan_for(
        rain=[30.0, 30.0, 30.0, 0.0, 0.0, 0.0, 0.0],
        et0=[2.0] * 7,
        crop="beans",
        stage="harvest",
    )
    first = plan.actions[0]
    assert first.action_id == "harvest_ripe_beyond_rain"
    assert first.urgency == "now"


def test_deferred_are_overflown_matches_only() -> None:
    plan = plan_for(rain=[0.0] * 7, et0=[5.0] * 7, crop="maize", stage="vegetative")
    assert set(plan.deferred).isdisjoint({a.title for a in plan.actions})


def test_data_gap_suggests_field_verification() -> None:
    plan = plan_for(rain=[0.0] * 3, et0=[1.0] * 3, crop="maize", stage="vegetative")
    chosen_ids = {a.action_id for a in plan.actions}
    assert {"verify_field_conditions", "listen_kmd_forecast"} <= chosen_ids


def test_plan_contract_shape() -> None:
    plan = plan_for(rain=[0.0] * 7, et0=[5.0] * 7, crop="potatoes", stage="flowering")
    assert isinstance(plan, ActionPlan)
    assert any("Catalog version" in a for a in plan.assumptions)


def test_stage_matching_is_explicit() -> None:
    # Mulch is curated for emergence..flowering, NOT harvest.
    plan = plan_for(rain=[0.0] * 7, et0=[5.0] * 7, crop="maize", stage="harvest")
    chosen_ids = {a.action_id for a in plan.actions}
    assert "mulch_between_rows" not in chosen_ids
