"""Fetch a live (or clearly labelled demo) forecast and run hazard detection.

This CLI is the Phase 3 gate. It exercises the Open-Meteo integration end to
end without needing any AWS credentials.

Examples::

    python scripts/check_forecast.py --county Machakos
    python scripts/check_forecast.py --county Machakos --location Kangundo
    python scripts/check_forecast.py --demo machakos_drought
    python scripts/check_forecast.py --county Kisumu --json
"""

from __future__ import annotations

import argparse
import sys

from shambashield.config import get_settings
from shambashield.contracts import WeatherSnapshot
from shambashield.demo import demo_names, load_demo_snapshot
from shambashield.geo import UnknownCountyError, county_names
from shambashield.logging_setup import configure_logging, get_logger, new_request_id
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
        prog="check_forecast",
        description="Retrieve a forecast for a Kenyan county and detect weather hazards.",
        epilog="Hazards come from deterministic rules in config/thresholds.yaml.",
    )
    parser.add_argument(
        "--county",
        help="one of the 47 Kenyan counties, e.g. Machakos (see --list-counties)",
    )
    parser.add_argument("--location", help="optional place label, e.g. Kangundo")
    parser.add_argument("--demo", help="use a labelled demo snapshot instead of the live API")
    parser.add_argument("--list-counties", action="store_true", help="print supported counties")
    parser.add_argument("--json", action="store_true", help="print the WeatherSnapshot as JSON")
    parser.add_argument("--verbose", action="store_true")
    return parser


def _print_report(snapshot: WeatherSnapshot) -> None:
    print(f"Location:    {snapshot.location_name} ({snapshot.county} County)")
    print(f"Coordinates: {snapshot.latitude:.4f}, {snapshot.longitude:.4f}")
    print(f"Source:      {snapshot.source}")
    print(f"Retrieved:   {snapshot.retrieved_at.isoformat()}")
    print(f"Timezone:    {snapshot.timezone}\n")

    print("Day    Date         Tmax (C)  Tmin (C)  Rain (mm)  ET0 (mm)  Wind (km/h)")
    print("-" * 78)
    for i, day in enumerate(snapshot.days, start=1):
        et0 = f"{day.et0_mm:8.1f}" if day.et0_mm is not None else "     -  "
        wind = f"{day.wind_max_kmh:10.1f}" if day.wind_max_kmh is not None else "        - "
        print(
            f"{i:2}     {day.date.isoformat()}  {day.tmax_c:7.1f}  {day.tmin_c:7.1f}  "
            f"{day.rain_mm:9.1f}  {et0}  {wind}"
        )
    print()

    hazards = detect_hazards(snapshot)
    if not hazards:
        print("Hazards: none detected with the current thresholds.")
    else:
        print("Detected hazards (deterministic rules):")
        for hazard in hazards:
            print(f"\n  [{hazard.severity.upper():<8}] {hazard_kind_label(hazard.kind)}")
            for line in hazard.evidence:
                print(f"            - {line}")

    if snapshot.source == "demo":
        print("\nNOTE: This is LABELLED DEMONSTRATION DATA, not a live forecast.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging("DEBUG" if args.verbose else settings.log_level)
    new_request_id()

    if args.list_counties:
        print("Supported counties (47):")
        for name in county_names():
            print(f"  {name}")
        return EXIT_OK

    try:
        if args.demo:
            available = ", ".join(demo_names())
            print(f"Using labelled demo snapshot: {args.demo}")
            print(f"Available demo snapshots: {available}\n")
            snapshot = load_demo_snapshot(args.demo)
        else:
            if not args.county:
                parser.print_help()
                print(
                    "\nUse --list-counties to see supported counties, or --demo for offline data."
                )
                return EXIT_USAGE
            location = resolve_location(args.county, args.location)
            snapshot = get_forecast(location)
    except UnknownCountyError as exc:
        log.error("%s", exc)
        return EXIT_USAGE
    except (ForecastUnavailableError, ForecastAPIError) as exc:
        log.error("%s", exc)
        print(
            "\nFix: check internet access and retry. The app will later fall back to a\n"
            "clearly labelled demo snapshot; never fabricate live values.",
            file=sys.stderr,
        )
        return EXIT_FORECAST

    detect_hazards(snapshot)  # validates the rules run on live data
    if args.json:
        print(snapshot.model_dump_json(indent=2))
    else:
        _print_report(snapshot)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
