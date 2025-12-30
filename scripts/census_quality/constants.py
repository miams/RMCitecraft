"""Constants and enums for census quality checking.

Contains enumerations, lookup tables, and helper functions used throughout
the census quality check system.
"""

import re
from enum import Enum
from pathlib import Path


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    def __lt__(self, other):
        order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
        return order[self] < order[other]


class IssueCategory(Enum):
    """Categories for grouping related issues."""

    TITLE = "title"
    FORMAT = "format"
    MISSING = "missing"
    CONSISTENCY = "consistency"
    DUPLICATE = "duplicate"
    MEDIA = "media"
    QUALITY = "quality"
    TYPO = "typo"
    JURISDICTION = "jurisdiction"


# State abbreviations for validation (Evidence Explained style)
STATE_ABBREVIATIONS = {
    "Alabama": "Ala.",
    "Alaska": "Alaska",
    "Arizona": "Ariz.",
    "Arkansas": "Ark.",
    "California": "Calif.",
    "Colorado": "Colo.",
    "Connecticut": "Conn.",
    "Delaware": "Del.",
    "District of Columbia": "D.C.",
    "Florida": "Fla.",
    "Georgia": "Ga.",
    "Hawaii": "Hawaii",
    "Idaho": "Idaho",
    "Illinois": "Ill.",
    "Indiana": "Ind.",
    "Iowa": "Iowa",
    "Kansas": "Kans.",
    "Kentucky": "Ky.",
    "Louisiana": "La.",
    "Maine": "Maine",
    "Maryland": "Md.",
    "Massachusetts": "Mass.",
    "Michigan": "Mich.",
    "Minnesota": "Minn.",
    "Mississippi": "Miss.",
    "Missouri": "Mo.",
    "Montana": "Mont.",
    "Nebraska": "Nebr.",
    "Nevada": "Nev.",
    "New Hampshire": "N.H.",
    "New Jersey": "N.J.",
    "New Mexico": "N.Mex.",
    "New York": "N.Y.",
    "North Carolina": "N.C.",
    "North Dakota": "N.Dak.",
    "Ohio": "Ohio",
    "Oklahoma": "Okla.",
    "Oregon": "Oreg.",
    "Pennsylvania": "Pa.",
    "Rhode Island": "R.I.",
    "South Carolina": "S.C.",
    "South Dakota": "S.Dak.",
    "Tennessee": "Tenn.",
    "Texas": "Tex.",
    "Utah": "Utah",
    "Vermont": "Vt.",
    "Virginia": "Va.",
    "Washington": "Wash.",
    "West Virginia": "W.Va.",
    "Wisconsin": "Wis.",
    "Wyoming": "Wyo.",
}

VALID_STATE_NAMES = set(STATE_ABBREVIATIONS.keys())


def normalize_state_for_comparison(state: str) -> str:
    """Normalize state name for comparison by stripping 'Territory' suffix.

    Historical territories (e.g., 'Colorado Territory') should match their
    modern state names (e.g., 'Colorado') for consistency checking.
    """
    if not state:
        return state
    # Strip " Territory" suffix for comparison
    normalized = re.sub(r"\s+Territory$", "", state, flags=re.IGNORECASE)
    return normalized


# Media root directory for RootsMagic files
MEDIA_ROOT = Path.home() / "Genealogy" / "RootsMagic" / "Files"

# Census year to directory name mapping
CENSUS_DIRECTORIES = {
    1790: "1790 Federal",
    1800: "1800 Federal",
    1810: "1810 Federal",
    1820: "1820 Federal",
    1830: "1830 Federal",
    1840: "1840 Federal",
    1850: "1850 Federal",
    1860: "1860 Federal",
    1870: "1870 Federal",
    1880: "1880 Federal",
    1890: "1890 Federal",
    1900: "1900 Federal",
    1910: "1910 Federal",
    1920: "1920 Federal",
    1930: "1930 Federal",
    1940: "1940 Federal",
    1950: "1950 Federal",
}
