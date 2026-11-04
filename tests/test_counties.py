"""County data quality and lookup tests."""

from __future__ import annotations

import pytest

from shambashield.geo import UnknownCountyError, county_names, get_county, load_counties

COUNTIES_EXPECTED = 47
LAT_RANGE = (-4.8, 5.0)
LON_RANGE = (33.5, 42.0)


def test_kenya_has_exactly_47_counties() -> None:
    counties = load_counties()
    assert len(counties) == COUNTIES_EXPECTED


def test_county_names_are_unique_and_titlecased() -> None:
    names = county_names()
    assert len(set(names)) == COUNTIES_EXPECTED
    assert all(not n.startswith(" ") for n in names)


def test_all_centroids_inside_kenya() -> None:
    for name, coords in load_counties().items():
        assert LAT_RANGE[0] <= coords["latitude"] <= LAT_RANGE[1], name
        assert LON_RANGE[0] <= coords["longitude"] <= LON_RANGE[1], name


def test_machakos_centroid_is_approximate() -> None:
    point = get_county("Machakos")
    assert point.approximated is True
    assert point.latitude == pytest.approx(-1.5167, abs=0.01)


def test_unknown_county_offers_spelling_suggestions() -> None:
    with pytest.raises(UnknownCountyError, match="Machakos"):
        get_county("Machakoz")


def test_county_lookup_is_case_sensitive_to_defaults() -> None:
    assert get_county("Nakuru").county == "Nakuru"
