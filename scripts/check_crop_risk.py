"""Live demo of the deterministic weather + crop risk pipeline (no AWS needed).

Examples::

    python scripts/check_crop_risk.py --county Machakos --crop maize --stage flowering
    python scripts/check_crop_risk.py --demo machakos_drought --crop maize --stage flowering
"""

from __future__ import annotations

import argparse

from shambashield.config import get_settings
from shambashield.contracts import WeatherFindings
from shambashield.demo import load_demo_snapshot
from shambashield.geo import UnknownCountyError
from shambashield.logging_setup import configure_logging, get_logger, new_request_id
from shambashield.tools.action_planner import plan_actions
from shambashield.tools.crop_risk import assess_crop_risk
from shambashield.tools.hazard_rules import detect_hazards, hazard_kind_label
from shambashield.tools.open_meteo import (
    ForecastAPIError,
    ForecastUnavailableError,
    get_forecast,
    resolve_location,
)

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_FORECAST = 3

log = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_crop_risk",
        description="Run the deterministic weather + crop risk engine for one farm.",
    )
    parser.add_argument("--county", help="one of the 47 Kenyan counties")
    parser.add_argument("--location", help="optional place label, e.g. Kangundo")
    parser.add_argument("--crop", default="maize", help="maize | beans | potatoes | other")
    parser.add_argument(
        "--stage",
        default="vegetative",
        help="land_preparation | planting | emergence | vegetative | flowering | "
        "grain_filling | maturity | harvest",
    )
    parser.add_argument("--demo", help="use a labelled demo snapshot instead of live API")
    parser.add_argument("--verbose", action="store_true")
    return parser


def _print_findings(findings: WeatherFindings) -> None:
    for hazard in findings.hazards:
        print(f"\n  [{hazard.severity.upper():<8}] {hazard_kind_label(hazard.kind)}")
        for line in hazard.evidence:
            print(f"            - {line}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging("DEBUG" if args.verbose else settings.log_level)
    new_request_id()

    try:
        if args.demo:
            snapshot = load_demo_snapshot(args.demo)
            print(f"Using labelled demo snapshot: {args.demo}\n")
        else:
            if not args.county:
                parser.print_help()
                print("\nUse --demo machakos_drought for offline data.")
                return EXIT_USAGE
            location = resolve_location(args.county, args.location)
            snapshot = get_forecast(location)
    except UnknownCountyError as exc:
        log.error("%s", exc)
        return EXIT_USAGE
    except (
        ForecastUnavailableError,
        ForecastAPIError,
    ):
        log.exception("Forecast unavailable")
        return EXIT_FORECAST

    findings = WeatherFindings(
        snapshot=snapshot, hazards=detect_hazards(snapshot), summary="CLI demo run"
    )
    assessment = assess_crop_risk(findings, crop=args.crop, stage=args.stage)

    print(f"Crop / stage: {assessment.crop} × {assessment.stage}")
    print(f"Risk level:   {assessment.risk_level.upper()}")
    print(f"Sensitivity:  {assessment.stage_sensitivity}")

    print("\nWeather hazards (deterministic):")
    if not findings.hazards:
        print("  none detected")
    else:
        _print_findings(findings)

    print("\nCrop drivers (raw weather -> crop risk):")
    if not assessment.drivers:
        print("  none")
    for driver in assessment.drivers:
        print(f"  - {driver}")

    print(f"\nImpact explanation:\n  {assessment.impact_explanation}")
    if assessment.uncertainty:
        print("\nUncertainty:")
        for note in assessment.uncertainty:
            print(f"  - {note}")

    plan = plan_actions(findings, assessment)
    print(f"\nRecommended actions (curated catalog, top {len(plan.actions)}):")
    for i, action in enumerate(plan.actions, start=1):
        print(f"  {i}. [{action.urgency.upper():<9}] {action.title} ({action.cost_tier})")
        print(f"     Why: {action.why}")
        print(f"     When: {action.when}")
    if plan.deferred:
        print("\nConsidered but not prioritised:")
        for title in plan.deferred:
            print(f"  - {title}")
    for assumption in plan.assumptions:
        print(f"Assumption: {assumption}")

    if snapshot.source == "demo":
        print("\nNOTE: LABELLED DEMONSTRATION DATA, not a live forecast.")

    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
