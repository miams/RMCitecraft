"""
Reference data for US Independent Cities.

Independent cities are cities that are not part of any county. They function
as county-equivalents for census and other governmental purposes.

For citation purposes, these should be identified as "(Independent City)" to
distinguish them from counties with similar names (e.g., Baltimore City vs
Baltimore County).

References:
- https://www.census.gov/library/reference/code-lists/ansi.html
- https://www.familysearch.org/en/wiki/Baltimore_(Independent_City),_Maryland_Genealogy
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class IndependentCity:
    """Reference data for an independent city."""
    city: str
    state: str
    # Year the city became independent (for historical validation)
    independent_since: Optional[int] = None
    # Related county that might be confused with this city
    related_county: Optional[str] = None
    # Locality pattern used in census (e.g., "Ward" for Baltimore City)
    locality_pattern: Optional[str] = None
    # Locality pattern used by the related county (e.g., "Election District")
    county_locality_pattern: Optional[str] = None


# Comprehensive list of US Independent Cities
# Note: Virginia has 38 independent cities, but we list only those likely
# to appear in genealogical research or cause confusion with counties.

INDEPENDENT_CITIES: dict[tuple[str, str], IndependentCity] = {
    # Maryland (1 independent city)
    ("Baltimore", "Maryland"): IndependentCity(
        city="Baltimore",
        state="Maryland",
        independent_since=1851,
        related_county="Baltimore County",
        locality_pattern="Ward",
        county_locality_pattern="Election District",
    ),

    # Missouri (1 independent city)
    ("St. Louis", "Missouri"): IndependentCity(
        city="St. Louis",
        state="Missouri",
        independent_since=1876,
        related_county="St. Louis County",
        locality_pattern="Ward",
        county_locality_pattern=None,
    ),

    # Nevada (1 independent city - consolidated city-county)
    ("Carson City", "Nevada"): IndependentCity(
        city="Carson City",
        state="Nevada",
        independent_since=1969,
        related_county=None,  # Was Ormsby County, dissolved
        locality_pattern=None,
        county_locality_pattern=None,
    ),

    # Virginia (38 independent cities - listing major ones)
    ("Alexandria", "Virginia"): IndependentCity(
        city="Alexandria",
        state="Virginia",
        independent_since=1870,
        related_county="Arlington County",  # Nearby, not same name
        locality_pattern="Ward",
        county_locality_pattern=None,
    ),
    ("Bristol", "Virginia"): IndependentCity(
        city="Bristol",
        state="Virginia",
        independent_since=1890,
        related_county="Washington County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Charlottesville", "Virginia"): IndependentCity(
        city="Charlottesville",
        state="Virginia",
        independent_since=1888,
        related_county="Albemarle County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Chesapeake", "Virginia"): IndependentCity(
        city="Chesapeake",
        state="Virginia",
        independent_since=1963,
        related_county=None,  # Formed from Norfolk County
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Danville", "Virginia"): IndependentCity(
        city="Danville",
        state="Virginia",
        independent_since=1890,
        related_county="Pittsylvania County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Fairfax", "Virginia"): IndependentCity(
        city="Fairfax",
        state="Virginia",
        independent_since=1961,
        related_county="Fairfax County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Falls Church", "Virginia"): IndependentCity(
        city="Falls Church",
        state="Virginia",
        independent_since=1948,
        related_county="Fairfax County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Franklin", "Virginia"): IndependentCity(
        city="Franklin",
        state="Virginia",
        independent_since=1961,
        related_county="Southampton County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Fredericksburg", "Virginia"): IndependentCity(
        city="Fredericksburg",
        state="Virginia",
        independent_since=1879,
        related_county="Spotsylvania County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Hampton", "Virginia"): IndependentCity(
        city="Hampton",
        state="Virginia",
        independent_since=1908,
        related_county=None,  # Was Elizabeth City County
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Harrisonburg", "Virginia"): IndependentCity(
        city="Harrisonburg",
        state="Virginia",
        independent_since=1916,
        related_county="Rockingham County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Hopewell", "Virginia"): IndependentCity(
        city="Hopewell",
        state="Virginia",
        independent_since=1916,
        related_county="Prince George County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Lexington", "Virginia"): IndependentCity(
        city="Lexington",
        state="Virginia",
        independent_since=1874,
        related_county="Rockbridge County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Lynchburg", "Virginia"): IndependentCity(
        city="Lynchburg",
        state="Virginia",
        independent_since=1852,
        related_county="Campbell County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Manassas", "Virginia"): IndependentCity(
        city="Manassas",
        state="Virginia",
        independent_since=1975,
        related_county="Prince William County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Manassas Park", "Virginia"): IndependentCity(
        city="Manassas Park",
        state="Virginia",
        independent_since=1975,
        related_county="Prince William County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Martinsville", "Virginia"): IndependentCity(
        city="Martinsville",
        state="Virginia",
        independent_since=1928,
        related_county="Henry County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Newport News", "Virginia"): IndependentCity(
        city="Newport News",
        state="Virginia",
        independent_since=1896,
        related_county=None,  # Was Warwick County
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Norfolk", "Virginia"): IndependentCity(
        city="Norfolk",
        state="Virginia",
        independent_since=1845,
        related_county="Norfolk County",  # County dissolved 1963
        locality_pattern="Ward",
        county_locality_pattern=None,
    ),
    ("Norton", "Virginia"): IndependentCity(
        city="Norton",
        state="Virginia",
        independent_since=1954,
        related_county="Wise County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Petersburg", "Virginia"): IndependentCity(
        city="Petersburg",
        state="Virginia",
        independent_since=1850,
        related_county="Dinwiddie County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Poquoson", "Virginia"): IndependentCity(
        city="Poquoson",
        state="Virginia",
        independent_since=1975,
        related_county="York County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Portsmouth", "Virginia"): IndependentCity(
        city="Portsmouth",
        state="Virginia",
        independent_since=1858,
        related_county="Norfolk County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Radford", "Virginia"): IndependentCity(
        city="Radford",
        state="Virginia",
        independent_since=1892,
        related_county="Montgomery County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Richmond", "Virginia"): IndependentCity(
        city="Richmond",
        state="Virginia",
        independent_since=1871,
        related_county="Henrico County",
        locality_pattern="Ward",
        county_locality_pattern=None,
    ),
    ("Roanoke", "Virginia"): IndependentCity(
        city="Roanoke",
        state="Virginia",
        independent_since=1884,
        related_county="Roanoke County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Salem", "Virginia"): IndependentCity(
        city="Salem",
        state="Virginia",
        independent_since=1968,
        related_county="Roanoke County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Staunton", "Virginia"): IndependentCity(
        city="Staunton",
        state="Virginia",
        independent_since=1871,
        related_county="Augusta County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Suffolk", "Virginia"): IndependentCity(
        city="Suffolk",
        state="Virginia",
        independent_since=1910,
        related_county="Nansemond County",  # Merged 1974
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Virginia Beach", "Virginia"): IndependentCity(
        city="Virginia Beach",
        state="Virginia",
        independent_since=1963,
        related_county="Princess Anne County",  # Merged
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Waynesboro", "Virginia"): IndependentCity(
        city="Waynesboro",
        state="Virginia",
        independent_since=1948,
        related_county="Augusta County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Williamsburg", "Virginia"): IndependentCity(
        city="Williamsburg",
        state="Virginia",
        independent_since=1884,
        related_county="James City County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
    ("Winchester", "Virginia"): IndependentCity(
        city="Winchester",
        state="Virginia",
        independent_since=1874,
        related_county="Frederick County",
        locality_pattern=None,
        county_locality_pattern=None,
    ),
}


def is_independent_city(city: str, state: str) -> bool:
    """Check if a city/state combination is an independent city."""
    return (city, state) in INDEPENDENT_CITIES


def get_independent_city(city: str, state: str) -> IndependentCity | None:
    """Get independent city reference data, or None if not an independent city."""
    return INDEPENDENT_CITIES.get((city, state))


def get_independent_cities_for_state(state: str) -> list[IndependentCity]:
    """Get all independent cities in a given state."""
    return [ic for (city, st), ic in INDEPENDENT_CITIES.items() if st == state]


def has_related_county(city: str, state: str) -> bool:
    """Check if an independent city has a related county with similar name."""
    ic = get_independent_city(city, state)
    return ic is not None and ic.related_county is not None


def get_related_county(city: str, state: str) -> str | None:
    """Get the related county name for an independent city."""
    ic = get_independent_city(city, state)
    return ic.related_county if ic else None


# Cities that have both an independent city AND a county with similar names
# These are the most likely to cause citation confusion
CONFUSABLE_JURISDICTIONS = {
    ("Baltimore", "Maryland"): "Baltimore County",
    ("St. Louis", "Missouri"): "St. Louis County",
    ("Fairfax", "Virginia"): "Fairfax County",
    ("Roanoke", "Virginia"): "Roanoke County",
    ("Richmond", "Virginia"): "Henrico County",  # Different name but adjacent
    ("Norfolk", "Virginia"): "Norfolk County",  # County dissolved 1963
}


def is_confusable_jurisdiction(city: str, state: str) -> bool:
    """Check if this independent city could be confused with a nearby county."""
    return (city, state) in CONFUSABLE_JURISDICTIONS
