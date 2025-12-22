#!/usr/bin/env python3
"""
Census Quality Check Tool for RMCitecraft.

Performs comprehensive quality checks on Federal Census sources (1790-1950)
in a RootsMagic database. Designed to be used as a tool by Claude Code.

Each census year has explicit, self-contained validation rules with no
implicit assumptions or inheritance between years.

Checks include:
- Source Name format and consistency
- Footnote completeness and format (including schedule type requirement)
- Short Footnote completeness and format
- Bibliography format
- Cross-field consistency (state, county, ED, sheet matching)
- Independent city validation
- Citation Quality settings
- Media attachments

Usage:
    python scripts/census_quality_check.py 1940
    python scripts/census_quality_check.py 1940 --format json
    python scripts/census_quality_check.py 1940 --format text --detailed
    python scripts/census_quality_check.py --help

Output:
    JSON (default): Structured output for programmatic parsing
    Text: Human-readable report

Exit Codes:
    0: Success (issues may still be found, check output)
    1: Error (script failed to run)
"""

import argparse
import json
import logging
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from rmcitecraft.config.independent_cities import (
        is_independent_city,
        get_independent_city,
        is_confusable_jurisdiction,
    )
    HAS_INDEPENDENT_CITIES = True
except ImportError:
    HAS_INDEPENDENT_CITIES = False

# Configure logging to stderr only
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


# =============================================================================
# Constants and Enums
# =============================================================================

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
    "Alabama": "Ala.", "Alaska": "Alaska", "Arizona": "Ariz.", "Arkansas": "Ark.",
    "California": "Calif.", "Colorado": "Colo.", "Connecticut": "Conn.",
    "Delaware": "Del.", "District of Columbia": "D.C.", "Florida": "Fla.",
    "Georgia": "Ga.", "Hawaii": "Hawaii", "Idaho": "Idaho", "Illinois": "Ill.",
    "Indiana": "Ind.", "Iowa": "Iowa", "Kansas": "Kans.", "Kentucky": "Ky.",
    "Louisiana": "La.", "Maine": "Maine", "Maryland": "Md.", "Massachusetts": "Mass.",
    "Michigan": "Mich.", "Minnesota": "Minn.", "Mississippi": "Miss.",
    "Missouri": "Mo.", "Montana": "Mont.", "Nebraska": "Nebr.", "Nevada": "Nev.",
    "New Hampshire": "N.H.", "New Jersey": "N.J.", "New Mexico": "N.Mex.",
    "New York": "N.Y.", "North Carolina": "N.C.", "North Dakota": "N.Dak.",
    "Ohio": "Ohio", "Oklahoma": "Okla.", "Oregon": "Oreg.", "Pennsylvania": "Pa.",
    "Rhode Island": "R.I.", "South Carolina": "S.C.", "South Dakota": "S.Dak.",
    "Tennessee": "Tenn.", "Texas": "Tex.", "Utah": "Utah", "Vermont": "Vt.",
    "Virginia": "Va.", "Washington": "Wash.", "West Virginia": "W.Va.",
    "Wisconsin": "Wis.", "Wyoming": "Wyo.",
}

VALID_STATE_NAMES = set(STATE_ABBREVIATIONS.keys())


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class Issue:
    """A single validation issue."""
    source_id: int
    issue_type: str
    severity: str  # "error", "warning", "info"
    message: str
    field: str
    current_value: str = ""
    expected_value: str = ""
    category: str = "format"

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "issue_type": self.issue_type,
            "severity": self.severity,
            "message": self.message,
            "field": self.field,
            "current_value": self.current_value,
            "expected_value": self.expected_value,
            "category": self.category,
        }


@dataclass
class CensusComponents:
    """Extracted components from a census citation field."""
    year: int | None = None
    state: str | None = None
    county: str | None = None
    locality: str | None = None
    ed: str | None = None
    sheet: str | None = None
    stamp: str | None = None
    line: int | None = None
    family: int | None = None
    dwelling: int | None = None
    person_name: str | None = None
    quoted_title: str | None = None
    schedule_type: str | None = None  # "population schedule", etc.
    raw_text: str = ""


@dataclass
class CensusYearConfig:
    """Explicit configuration for a specific census year's validation rules.

    Each field must be explicitly set - no defaults are inherited.
    """
    year: int

    # Source name validation
    source_name_prefix: str  # e.g., "Fed Census: 1940,"
    source_name_requires_ed: bool
    source_name_ed_pattern: str | None  # Regex for ED format, None if not required
    source_name_requires_sheet: bool
    source_name_requires_stamp: bool
    source_name_allows_sheet_or_stamp: bool  # If True, either sheet or stamp is valid
    source_name_requires_line: bool
    source_name_line_required_with_sheet_only: bool  # Line only required if sheet format used

    # Footnote validation
    footnote_census_ref: str  # e.g., "1940 U.S. census"
    footnote_requires_ed: bool
    footnote_ed_pattern: str | None  # e.g., "enumeration district (ED)"
    footnote_requires_sheet: bool
    footnote_requires_stamp: bool
    footnote_allows_sheet_or_stamp: bool
    footnote_requires_line: bool
    footnote_line_required_with_sheet_only: bool
    footnote_quoted_title: str  # Expected title in quotes
    footnote_requires_schedule: bool  # Require "population schedule" or similar
    footnote_schedule_patterns: list[str] | None  # Acceptable schedule patterns

    # Short footnote validation
    short_census_ref: str  # e.g., "1940 U.S. census"
    short_requires_ed: bool
    short_ed_abbreviation: str | None  # e.g., "E.D." - None if ED not required
    short_requires_sheet: bool
    short_requires_stamp: bool
    short_allows_sheet_or_stamp: bool
    short_requires_line: bool
    short_line_required_with_sheet_only: bool
    short_requires_ending_period: bool
    short_requires_schedule: bool  # Require "pop. sch." or similar
    short_schedule_patterns: list[str] | None  # Acceptable short schedule patterns

    # Bibliography validation
    bibliography_quoted_title: str  # Expected title in quotes

    # Citation quality
    expected_citation_quality: str  # e.g., "PDO"

    # Description for output
    description: str

    # Optional: Alternative acceptable bibliography titles (e.g., Ancestry vs FamilySearch)
    bibliography_alt_titles: list[str] | None = None


# =============================================================================
# Component Extraction
# =============================================================================

class ComponentExtractor:
    """Extract census components from citation fields."""

    # Patterns for extracting components
    PATTERNS = {
        # Source name patterns
        "source_year": r"Fed Census:\s*(\d{4})",
        "source_state_county": r"Fed Census:\s*\d{4},\s*([^,\[]+),\s*([^,\[]+?)(?:\s*\[|,)",
        "source_ed_bracket": r"\[ED\s+(\d+[A-Z]?(?:-\d+[A-Z]?)?)",
        "source_ed_citing": r"\[citing\s+enumeration\s+district\s+\(ED\)\s+(\d+(?:-\d+)?)",
        "source_sheet": r"sheet\s+(\d+[AB]?)",
        "source_stamp": r"stamp\s+(\d+(?:-\d+)?)",
        "source_line": r"line\s+(\d+)",
        "source_family": r"family\s+(\d+)",
        "source_person": r"\]\s+([^,\]]+(?:,\s*[^,\]]+)?)\s*$",

        # Footnote patterns
        "fn_year": r"(\d{4})\s+U\.S\.\s+census",
        "fn_county_state": r"([\w\.]+(?:\s+[\w\.]+)*)\s+County,\s+([\w\s]+?)(?:,|$)",
        "fn_ed": r"enumeration\s+district\s+\(ED\)\s+(\d+[A-Z]?(?:-\d+[A-Z]?)?)",
        "fn_sheet": r"sheet\s+(\d+[AB]?)",
        "fn_stamp": r"stamp\s+(\d+)",
        "fn_line": r"line\s+(\d+)",
        "fn_schedule": r"(population schedule|slave schedule|mortality schedule|agricultural schedule|manufacturing schedule)",

        # Quoted title (for both footnote and bibliography)
        "quoted_title": r'"([^"]+)"',

        # Short footnote patterns
        "short_year": r"(\d{4})\s+U\.S\.\s+census",
        "short_county_state": r"([\w\.]+(?:\s+[\w\.]+)*)\s+Co\.,\s+([^,]+),",
        "short_ed": r"E\.D\.\s+(\d+[A-Z]?(?:-\d+[A-Z]?)?)",
        "short_sheet": r"sheet\s+(\d+[AB]?)",
        "short_stamp": r"stamp\s+(\d+)",
        "short_line": r"line\s+(\d+)",
        "short_schedule": r"(pop\. sch\.|slave sch\.|mort\. sch\.|agri\. sch\.|mfg\. sch\.)",

        # Bibliography patterns
        "bib_state": r"U\.S\.\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)\.",
        "bib_county": r"([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+County\.",
    }

    @classmethod
    def extract_from_source_name(cls, name: str, year: int) -> CensusComponents:
        """Extract components from source name."""
        components = CensusComponents(raw_text=name)

        # Year
        if match := re.search(cls.PATTERNS["source_year"], name):
            components.year = int(match.group(1))

        # State and County
        if match := re.search(cls.PATTERNS["source_state_county"], name):
            components.state = match.group(1).strip()
            components.county = match.group(2).strip()

        # ED - try bracket format first, then citing format
        if match := re.search(cls.PATTERNS["source_ed_bracket"], name):
            components.ed = match.group(1)
        elif match := re.search(cls.PATTERNS["source_ed_citing"], name):
            components.ed = match.group(1)

        # Sheet
        if match := re.search(cls.PATTERNS["source_sheet"], name, re.IGNORECASE):
            components.sheet = match.group(1)

        # Stamp (1950)
        if match := re.search(cls.PATTERNS["source_stamp"], name, re.IGNORECASE):
            components.stamp = match.group(1)

        # Line
        if match := re.search(cls.PATTERNS["source_line"], name, re.IGNORECASE):
            components.line = int(match.group(1))

        # Family
        if match := re.search(cls.PATTERNS["source_family"], name, re.IGNORECASE):
            components.family = int(match.group(1))

        # Person name
        if match := re.search(cls.PATTERNS["source_person"], name):
            components.person_name = match.group(1).strip()

        return components

    @classmethod
    def extract_from_footnote(cls, footnote: str) -> CensusComponents:
        """Extract components from footnote."""
        components = CensusComponents(raw_text=footnote)

        # Year
        if match := re.search(cls.PATTERNS["fn_year"], footnote):
            components.year = int(match.group(1))

        # County and State
        if match := re.search(cls.PATTERNS["fn_county_state"], footnote):
            components.county = match.group(1)
            components.state = match.group(2)

        # ED
        if match := re.search(cls.PATTERNS["fn_ed"], footnote):
            components.ed = match.group(1)

        # Sheet
        if match := re.search(cls.PATTERNS["fn_sheet"], footnote, re.IGNORECASE):
            components.sheet = match.group(1)

        # Stamp
        if match := re.search(cls.PATTERNS["fn_stamp"], footnote, re.IGNORECASE):
            components.stamp = match.group(1)

        # Line
        if match := re.search(cls.PATTERNS["fn_line"], footnote, re.IGNORECASE):
            components.line = int(match.group(1))

        # Schedule type
        if match := re.search(cls.PATTERNS["fn_schedule"], footnote, re.IGNORECASE):
            components.schedule_type = match.group(1).lower()

        # Quoted title
        if match := re.search(cls.PATTERNS["quoted_title"], footnote):
            components.quoted_title = match.group(1)

        return components

    @classmethod
    def extract_from_short_footnote(cls, short: str) -> CensusComponents:
        """Extract components from short footnote."""
        components = CensusComponents(raw_text=short)

        # Year
        if match := re.search(cls.PATTERNS["short_year"], short):
            components.year = int(match.group(1))

        # County and State abbreviation
        if match := re.search(cls.PATTERNS["short_county_state"], short):
            components.county = match.group(1).strip()
            components.state = match.group(2).strip()

        # ED
        if match := re.search(cls.PATTERNS["short_ed"], short):
            components.ed = match.group(1)

        # Sheet
        if match := re.search(cls.PATTERNS["short_sheet"], short, re.IGNORECASE):
            components.sheet = match.group(1)

        # Stamp
        if match := re.search(cls.PATTERNS["short_stamp"], short, re.IGNORECASE):
            components.stamp = match.group(1)

        # Line
        if match := re.search(cls.PATTERNS["short_line"], short, re.IGNORECASE):
            components.line = int(match.group(1))

        # Schedule type
        if match := re.search(cls.PATTERNS["short_schedule"], short, re.IGNORECASE):
            components.schedule_type = match.group(1).lower()

        return components

    @classmethod
    def extract_from_bibliography(cls, bibliography: str) -> CensusComponents:
        """Extract components from bibliography."""
        components = CensusComponents(raw_text=bibliography)

        # State (from "U.S. California." or "U.S. New York.")
        if match := re.search(cls.PATTERNS["bib_state"], bibliography):
            components.state = match.group(1)

        # County
        if match := re.search(cls.PATTERNS["bib_county"], bibliography):
            components.county = match.group(1)

        # Quoted title
        if match := re.search(cls.PATTERNS["quoted_title"], bibliography):
            components.quoted_title = match.group(1)

        return components


# =============================================================================
# Census Year Configurations - Explicit per-year definitions
# =============================================================================

def build_census_configs() -> dict[int, CensusYearConfig]:
    """Build explicit configurations for each census year.

    Each year is fully defined with no inheritance or implicit defaults.
    """
    configs = {}

    # =========================================================================
    # 1790 Census
    # =========================================================================
    configs[1790] = CensusYearConfig(
        year=1790,
        description="First U.S. Census - heads of household only",
        # Source name
        source_name_prefix="Fed Census: 1790,",
        source_name_requires_ed=False,
        source_name_ed_pattern=None,
        source_name_requires_sheet=False,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=False,
        source_name_line_required_with_sheet_only=False,
        # Footnote
        footnote_census_ref="1790 U.S. census",
        footnote_requires_ed=False,
        footnote_ed_pattern=None,
        footnote_requires_sheet=False,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=False,
        footnote_line_required_with_sheet_only=False,
        footnote_quoted_title="United States Census, 1790,",
        footnote_requires_schedule=False,
        footnote_schedule_patterns=None,
        # Short footnote
        short_census_ref="1790 U.S. census",
        short_requires_ed=False,
        short_ed_abbreviation=None,
        short_requires_sheet=False,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=False,
        short_line_required_with_sheet_only=False,
        short_requires_ending_period=True,
        short_requires_schedule=False,
        short_schedule_patterns=None,
        # Bibliography
        bibliography_quoted_title="United States Census, 1790.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1800-1840 Censuses (similar structure, heads of household)
    # =========================================================================
    for year in [1800, 1810, 1820, 1830, 1840]:
        ordinal = {1800: "Second", 1810: "Third", 1820: "Fourth",
                   1830: "Fifth", 1840: "Sixth"}[year]
        configs[year] = CensusYearConfig(
            year=year,
            description=f"{ordinal} U.S. Census - heads of household only",
            # Source name
            source_name_prefix=f"Fed Census: {year},",
            source_name_requires_ed=False,
            source_name_ed_pattern=None,
            source_name_requires_sheet=False,
            source_name_requires_stamp=False,
            source_name_allows_sheet_or_stamp=False,
            source_name_requires_line=False,
            source_name_line_required_with_sheet_only=False,
            # Footnote
            footnote_census_ref=f"{year} U.S. census",
            footnote_requires_ed=False,
            footnote_ed_pattern=None,
            footnote_requires_sheet=False,
            footnote_requires_stamp=False,
            footnote_allows_sheet_or_stamp=False,
            footnote_requires_line=False,
            footnote_line_required_with_sheet_only=False,
            footnote_quoted_title=f"United States Census, {year},",
            footnote_requires_schedule=False,
            footnote_schedule_patterns=None,
            # Short footnote
            short_census_ref=f"{year} U.S. census",
            short_requires_ed=False,
            short_ed_abbreviation=None,
            short_requires_sheet=False,
            short_requires_stamp=False,
            short_allows_sheet_or_stamp=False,
            short_requires_line=False,
            short_line_required_with_sheet_only=False,
            short_requires_ending_period=True,
            short_requires_schedule=False,
            short_schedule_patterns=None,
            # Bibliography
            bibliography_quoted_title=f"United States Census, {year}.",
            # Quality
            expected_citation_quality="PDO",
        )

    # =========================================================================
    # 1850-1870 Censuses - All persons named, but no ED
    # =========================================================================
    for year in [1850, 1860, 1870]:
        ordinal = {1850: "Seventh", 1860: "Eighth", 1870: "Ninth"}[year]
        configs[year] = CensusYearConfig(
            year=year,
            description=f"{ordinal} U.S. Census - all persons named, no ED",
            # Source name
            source_name_prefix=f"Fed Census: {year},",
            source_name_requires_ed=False,
            source_name_ed_pattern=None,
            source_name_requires_sheet=True,
            source_name_requires_stamp=False,
            source_name_allows_sheet_or_stamp=False,
            source_name_requires_line=True,
            source_name_line_required_with_sheet_only=False,
            # Footnote
            footnote_census_ref=f"{year} U.S. census",
            footnote_requires_ed=False,
            footnote_ed_pattern=None,
            footnote_requires_sheet=True,
            footnote_requires_stamp=False,
            footnote_allows_sheet_or_stamp=False,
            footnote_requires_line=True,
            footnote_line_required_with_sheet_only=False,
            footnote_quoted_title=f"United States Census, {year},",
            footnote_requires_schedule=True,
            footnote_schedule_patterns=["population schedule", "slave schedule"],
            # Short footnote
            short_census_ref=f"{year} U.S. census",
            short_requires_ed=False,
            short_ed_abbreviation=None,
            short_requires_sheet=True,
            short_requires_stamp=False,
            short_allows_sheet_or_stamp=False,
            short_requires_line=True,
            short_line_required_with_sheet_only=False,
            short_requires_ending_period=True,
            short_requires_schedule=True,
            short_schedule_patterns=["pop. sch.", "slave sch."],
            # Bibliography
            bibliography_quoted_title=f"United States Census, {year}.",
            # Quality
            expected_citation_quality="PDO",
        )

    # =========================================================================
    # 1880 Census - ED introduced, uses stamped page numbers (not sheet)
    # =========================================================================
    configs[1880] = CensusYearConfig(
        year=1880,
        description="Tenth U.S. Census - ED introduced, stamped page numbers",
        # Source name: uses "page" not "sheet"
        source_name_prefix="Fed Census: 1880,",
        source_name_requires_ed=True,
        source_name_ed_pattern=r'\[ED (\d+),',
        source_name_requires_sheet=False,  # 1880 uses page, not sheet
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=True,
        source_name_line_required_with_sheet_only=False,
        # Footnote: uses "page X (stamped)" not "sheet"
        footnote_census_ref="1880 U.S. census",
        footnote_requires_ed=True,
        footnote_ed_pattern=r'enumeration district \(ED\)',
        footnote_requires_sheet=False,  # 1880 uses page (stamped)
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=True,
        footnote_line_required_with_sheet_only=False,
        footnote_quoted_title="United States, Census, 1880,",
        footnote_requires_schedule=True,
        footnote_schedule_patterns=["population schedule"],
        # Short footnote: uses "p. X (stamped)" not "sheet"
        short_census_ref="1880 U.S. census",
        short_requires_ed=True,
        short_ed_abbreviation="E.D.",
        short_requires_sheet=False,  # 1880 uses p. (stamped)
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=True,
        short_line_required_with_sheet_only=False,
        short_requires_ending_period=True,
        short_requires_schedule=True,
        short_schedule_patterns=["pop. sch."],
        # Bibliography
        bibliography_quoted_title="United States, Census, 1880.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1890 Census - Mostly destroyed
    # =========================================================================
    configs[1890] = CensusYearConfig(
        year=1890,
        description="Eleventh U.S. Census - mostly destroyed by fire",
        # Source name
        source_name_prefix="Fed Census: 1890,",
        source_name_requires_ed=True,
        source_name_ed_pattern=r'\[ED (\d+),',
        source_name_requires_sheet=True,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=True,
        source_name_line_required_with_sheet_only=False,
        # Footnote
        footnote_census_ref="1890 U.S. census",
        footnote_requires_ed=True,
        footnote_ed_pattern=r'enumeration district \(ED\)',
        footnote_requires_sheet=True,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=True,
        footnote_line_required_with_sheet_only=False,
        footnote_quoted_title="United States Census, 1890,",
        footnote_requires_schedule=True,
        footnote_schedule_patterns=["population schedule"],
        # Short footnote
        short_census_ref="1890 U.S. census",
        short_requires_ed=True,
        short_ed_abbreviation="E.D.",
        short_requires_sheet=True,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=True,
        short_line_required_with_sheet_only=False,
        short_requires_ending_period=True,
        short_requires_schedule=True,
        short_schedule_patterns=["pop. sch."],
        # Bibliography
        bibliography_quoted_title="United States Census, 1890.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1900 Census - ED format, requires population schedule
    # =========================================================================
    configs[1900] = CensusYearConfig(
        year=1900,
        description="Twelfth U.S. Census - requires population schedule",
        # Source name
        source_name_prefix="Fed Census: 1900,",
        source_name_requires_ed=True,
        source_name_ed_pattern=r'\[ED (\d+),',
        source_name_requires_sheet=True,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=True,
        source_name_line_required_with_sheet_only=False,
        # Footnote
        footnote_census_ref="1900 U.S. census",
        footnote_requires_ed=True,
        footnote_ed_pattern=r'enumeration district \(ED\)',
        footnote_requires_sheet=True,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=True,
        footnote_line_required_with_sheet_only=False,
        footnote_quoted_title="United States, Census, 1900,",
        footnote_requires_schedule=True,
        footnote_schedule_patterns=["population schedule"],
        # Short footnote
        short_census_ref="1900 U.S. census",
        short_requires_ed=True,
        short_ed_abbreviation="E.D.",
        short_requires_sheet=True,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=True,
        short_line_required_with_sheet_only=False,
        short_requires_ending_period=True,
        short_requires_schedule=True,
        short_schedule_patterns=["pop. sch."],
        # Bibliography
        bibliography_quoted_title="United States, Census, 1900.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1910 Census - FamilySearch does NOT extract line numbers
    # =========================================================================
    configs[1910] = CensusYearConfig(
        year=1910,
        description="Thirteenth U.S. Census (no line numbers from FamilySearch)",
        # Source name
        source_name_prefix="Fed Census: 1910,",
        source_name_requires_ed=True,
        source_name_ed_pattern=r'\[ED (\d+),',
        source_name_requires_sheet=True,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=False,  # FamilySearch doesn't provide line numbers
        source_name_line_required_with_sheet_only=False,
        # Footnote
        footnote_census_ref="1910 U.S. census",
        footnote_requires_ed=True,
        footnote_ed_pattern=r'enumeration district \(ED\)',
        footnote_requires_sheet=True,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=False,
        footnote_line_required_with_sheet_only=False,
        footnote_quoted_title="United States, Census, 1910,",
        footnote_requires_schedule=False,
        footnote_schedule_patterns=None,
        # Short footnote
        short_census_ref="1910 U.S. census",
        short_requires_ed=True,
        short_ed_abbreviation="E.D.",
        short_requires_sheet=True,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=False,
        short_line_required_with_sheet_only=False,
        short_requires_ending_period=True,
        short_requires_schedule=False,
        short_schedule_patterns=None,
        # Bibliography
        bibliography_quoted_title="United States, Census, 1910.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1920 Census
    # =========================================================================
    configs[1920] = CensusYearConfig(
        year=1920,
        description="Fourteenth U.S. Census",
        # Source name
        source_name_prefix="Fed Census: 1920,",
        source_name_requires_ed=True,
        source_name_ed_pattern=r'\[ED (\d+(-\d+)?),',  # Accepts both "ED 29" and "ED 13-22"
        source_name_requires_sheet=True,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=True,
        source_name_line_required_with_sheet_only=False,
        # Footnote
        footnote_census_ref="1920 U.S. census",
        footnote_requires_ed=True,
        footnote_ed_pattern=r'enumeration district \(ED\)',
        footnote_requires_sheet=True,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=True,
        footnote_line_required_with_sheet_only=False,
        footnote_quoted_title="United States, Census, 1920,",
        footnote_requires_schedule=False,
        footnote_schedule_patterns=None,
        # Short footnote
        short_census_ref="1920 U.S. census",
        short_requires_ed=True,
        short_ed_abbreviation="E.D.",
        short_requires_sheet=True,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=True,
        short_line_required_with_sheet_only=False,
        short_requires_ending_period=True,
        short_requires_schedule=False,
        short_schedule_patterns=None,
        # Bibliography
        bibliography_quoted_title="United States, Census, 1920.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1930 Census
    # =========================================================================
    configs[1930] = CensusYearConfig(
        year=1930,
        description="Fifteenth U.S. Census",
        # Source name
        source_name_prefix="Fed Census: 1930,",
        source_name_requires_ed=True,
        source_name_ed_pattern=r'\[ED (\d+(-\d+)?),',  # Accepts both "ED 29" and "ED 20-14"
        source_name_requires_sheet=True,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=True,
        source_name_line_required_with_sheet_only=False,
        # Footnote
        footnote_census_ref="1930 U.S. census",
        footnote_requires_ed=True,
        footnote_ed_pattern=r'enumeration district \(ED\)',
        footnote_requires_sheet=True,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=True,
        footnote_line_required_with_sheet_only=False,
        footnote_quoted_title="United States, Census, 1930,",
        footnote_requires_schedule=False,
        footnote_schedule_patterns=None,
        # Short footnote
        short_census_ref="1930 U.S. census",
        short_requires_ed=True,
        short_ed_abbreviation="E.D.",
        short_requires_sheet=True,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=True,
        short_line_required_with_sheet_only=False,
        short_requires_ending_period=True,
        short_requires_schedule=False,
        short_schedule_patterns=None,
        # Bibliography
        bibliography_quoted_title="United States, Census, 1930.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1940 Census
    # =========================================================================
    configs[1940] = CensusYearConfig(
        year=1940,
        description="Sixteenth U.S. Census",
        # Source name
        source_name_prefix="Fed Census: 1940,",
        source_name_requires_ed=True,
        source_name_ed_pattern=r'\[ED (\d+[A-Z]?-\d+[A-Z]?),',
        source_name_requires_sheet=True,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=True,
        source_name_line_required_with_sheet_only=False,
        # Footnote
        footnote_census_ref="1940 U.S. census",
        footnote_requires_ed=True,
        footnote_ed_pattern=r'enumeration district \(ED\)',
        footnote_requires_sheet=True,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=True,
        footnote_line_required_with_sheet_only=False,
        footnote_quoted_title="United States, Census, 1940,",
        footnote_requires_schedule=False,
        footnote_schedule_patterns=None,
        # Short footnote
        short_census_ref="1940 U.S. census",
        short_requires_ed=True,
        short_ed_abbreviation="E.D.",
        short_requires_sheet=True,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=True,
        short_line_required_with_sheet_only=False,
        short_requires_ending_period=True,
        short_requires_schedule=False,
        short_schedule_patterns=None,
        # Bibliography
        bibliography_quoted_title="United States, Census, 1940.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1950 Census - Can use stamp instead of sheet
    # =========================================================================
    configs[1950] = CensusYearConfig(
        year=1950,
        description="Seventeenth U.S. Census - stamp format available",
        # Source name
        source_name_prefix="Fed Census: 1950,",
        source_name_requires_ed=True,
        source_name_ed_pattern=r'\[ED (\d+[A-Z]?-\d+[A-Z]?),',
        source_name_requires_sheet=False,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=True,  # Either sheet or stamp
        source_name_requires_line=True,
        source_name_line_required_with_sheet_only=True,  # Line only with sheet format
        # Footnote
        footnote_census_ref="1950 U.S. census",
        footnote_requires_ed=True,
        footnote_ed_pattern=r'enumeration district \(ED\)',
        footnote_requires_sheet=False,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=True,
        footnote_requires_line=True,
        footnote_line_required_with_sheet_only=True,
        footnote_quoted_title="United States, Census, 1950,",
        footnote_requires_schedule=False,
        footnote_schedule_patterns=None,
        # Short footnote
        short_census_ref="1950 U.S. census",
        short_requires_ed=True,
        short_ed_abbreviation="E.D.",
        short_requires_sheet=False,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=True,
        short_requires_line=True,
        short_line_required_with_sheet_only=True,
        short_requires_ending_period=True,
        short_requires_schedule=False,
        short_schedule_patterns=None,
        # Bibliography
        bibliography_quoted_title="United States, Census, 1950.",
        # Quality
        expected_citation_quality="PDO",
    )

    return configs


# =============================================================================
# Validation Functions
# =============================================================================

def check_source_name(
    source_id: int,
    name: str,
    config: CensusYearConfig
) -> list[Issue]:
    """Check source name for issues."""
    issues = []

    # Check prefix
    if not name.startswith(config.source_name_prefix):
        issues.append(Issue(
            source_id=source_id,
            issue_type="wrong_source_prefix",
            severity="error",
            message=f"Source name should start with '{config.source_name_prefix}'",
            field="source_name",
            current_value=name[:50],
            expected_value=config.source_name_prefix,
            category="format",
        ))

    # Check ED
    if config.source_name_requires_ed:
        if config.source_name_ed_pattern:
            if not re.search(config.source_name_ed_pattern, name):
                issues.append(Issue(
                    source_id=source_id,
                    issue_type="missing_ed",
                    severity="error",
                    message="Missing or malformed ED in source name",
                    field="source_name",
                    current_value=name[:80],
                    category="missing",
                ))

    # Check sheet/stamp/page (1880 uses page, not sheet)
    has_sheet = bool(re.search(r'sheet\s+\d+[AB]?', name, re.IGNORECASE))
    has_stamp = bool(re.search(r'stamp\s+\d+', name, re.IGNORECASE))
    has_page = bool(re.search(r'page\s+\d+', name, re.IGNORECASE))

    # 1880 uses stamped page numbers
    if config.year == 1880:
        if not has_page:
            issues.append(Issue(
                source_id=source_id,
                issue_type="missing_page",
                severity="error",
                message="Missing page number in source name (1880 uses stamped pages)",
                field="source_name",
                current_value=name[:80],
                category="missing",
            ))
    elif config.source_name_allows_sheet_or_stamp:
        if not has_sheet and not has_stamp:
            issues.append(Issue(
                source_id=source_id,
                issue_type="missing_sheet_or_stamp",
                severity="error",
                message="Missing sheet or stamp number in source name",
                field="source_name",
                current_value=name[:80],
                category="missing",
            ))
    elif config.source_name_requires_sheet and not has_sheet:
        issues.append(Issue(
            source_id=source_id,
            issue_type="missing_sheet",
            severity="error",
            message="Missing sheet number in source name",
            field="source_name",
            current_value=name[:80],
            category="missing",
        ))

    # Check line
    has_line = bool(re.search(r'line\s+\d+', name, re.IGNORECASE))
    if config.source_name_requires_line:
        if config.source_name_line_required_with_sheet_only:
            if has_sheet and not has_line:
                issues.append(Issue(
                    source_id=source_id,
                    issue_type="missing_line",
                    severity="error",
                    message="Missing line number (required with sheet format)",
                    field="source_name",
                    current_value=name[:80],
                    category="missing",
                ))
        elif not has_line:
            issues.append(Issue(
                source_id=source_id,
                issue_type="missing_line",
                severity="error",
                message="Missing line number in source name",
                field="source_name",
                current_value=name[:80],
                category="missing",
            ))

    # Check state name
    components = ComponentExtractor.extract_from_source_name(name, config.year)
    if components.state and components.state not in VALID_STATE_NAMES:
        similar = find_similar_state(components.state)
        issues.append(Issue(
            source_id=source_id,
            issue_type="state_name_typo",
            severity="error",
            message=f"Invalid state name: '{components.state}'",
            field="source_name",
            current_value=components.state,
            expected_value=similar or "",
            category="typo",
        ))

    return issues


def check_footnote(
    source_id: int,
    footnote: str,
    config: CensusYearConfig
) -> list[Issue]:
    """Check footnote for issues."""
    issues = []

    if not footnote:
        issues.append(Issue(
            source_id=source_id,
            issue_type="empty_footnote",
            severity="error",
            message="Footnote is empty",
            field="footnote",
            category="missing",
        ))
        return issues

    # Check census reference
    if config.footnote_census_ref not in footnote:
        issues.append(Issue(
            source_id=source_id,
            issue_type="missing_census_ref",
            severity="error",
            message=f"Missing '{config.footnote_census_ref}' in footnote",
            field="footnote",
            current_value=footnote[:80],
            category="format",
        ))

    # Check ED
    if config.footnote_requires_ed and config.footnote_ed_pattern:
        if not re.search(config.footnote_ed_pattern, footnote, re.IGNORECASE):
            issues.append(Issue(
                source_id=source_id,
                issue_type="missing_ed_in_footnote",
                severity="error",
                message="Missing enumeration district reference in footnote",
                field="footnote",
                current_value=footnote[:80],
                category="missing",
            ))

    # Check sheet/stamp/page (1880 uses "page X (stamped)")
    has_sheet = bool(re.search(r'sheet\s+\d+[AB]?', footnote, re.IGNORECASE))
    has_stamp = bool(re.search(r'stamp\s+\d+', footnote, re.IGNORECASE))
    has_page_stamped = bool(re.search(r'page\s+\d+\s*\(stamped\)', footnote, re.IGNORECASE))

    # 1880 uses stamped page numbers
    if config.year == 1880:
        if not has_page_stamped:
            issues.append(Issue(
                source_id=source_id,
                issue_type="missing_page_stamped_footnote",
                severity="error",
                message="Missing 'page X (stamped)' in footnote (1880 format)",
                field="footnote",
                category="missing",
            ))
    elif config.footnote_allows_sheet_or_stamp:
        if not has_sheet and not has_stamp:
            issues.append(Issue(
                source_id=source_id,
                issue_type="missing_sheet_or_stamp_footnote",
                severity="error",
                message="Missing sheet or stamp in footnote",
                field="footnote",
                category="missing",
            ))
    elif config.footnote_requires_sheet and not has_sheet:
        issues.append(Issue(
            source_id=source_id,
            issue_type="missing_sheet_footnote",
            severity="error",
            message="Missing sheet number in footnote",
            field="footnote",
            category="missing",
        ))

    # Check line
    has_line = bool(re.search(r'line\s+\d+', footnote, re.IGNORECASE))
    if config.footnote_requires_line:
        if config.footnote_line_required_with_sheet_only:
            if has_sheet and not has_line:
                issues.append(Issue(
                    source_id=source_id,
                    issue_type="missing_line_footnote",
                    severity="error",
                    message="Missing line number in footnote (required with sheet)",
                    field="footnote",
                    category="missing",
                ))
        elif not has_line:
            issues.append(Issue(
                source_id=source_id,
                issue_type="missing_line_footnote",
                severity="error",
                message="Missing line number in footnote",
                field="footnote",
                category="missing",
            ))

    # Check schedule type requirement
    if config.footnote_requires_schedule:
        schedule_found = False
        if config.footnote_schedule_patterns:
            for pattern in config.footnote_schedule_patterns:
                if pattern.lower() in footnote.lower():
                    schedule_found = True
                    break
        if not schedule_found:
            expected = ", ".join(config.footnote_schedule_patterns or [])
            issues.append(Issue(
                source_id=source_id,
                issue_type="missing_schedule_type",
                severity="error",
                message=f"Missing schedule type in footnote (expected: {expected})",
                field="footnote",
                current_value=footnote[:80],
                expected_value=expected,
                category="missing",
            ))

    # Check quoted title
    title_match = re.search(r'"([^"]+)"', footnote)
    if title_match:
        found_title = title_match.group(1)
        if found_title != config.footnote_quoted_title:
            issues.append(Issue(
                source_id=source_id,
                issue_type="wrong_footnote_title",
                severity="warning",
                message="Wrong quoted title in footnote",
                field="footnote",
                current_value=found_title,
                expected_value=config.footnote_quoted_title,
                category="title",
            ))

    # Check for double spaces
    if "  " in footnote:
        issues.append(Issue(
            source_id=source_id,
            issue_type="double_space",
            severity="warning",
            message="Double space found in footnote",
            field="footnote",
            category="format",
        ))

    return issues


def check_short_footnote(
    source_id: int,
    short_footnote: str,
    config: CensusYearConfig
) -> list[Issue]:
    """Check short footnote for issues."""
    issues = []

    if not short_footnote:
        return issues  # Short footnote may be optional

    # Check census reference
    if config.short_census_ref not in short_footnote:
        issues.append(Issue(
            source_id=source_id,
            issue_type="short_missing_census_ref",
            severity="error",
            message=f"Missing '{config.short_census_ref}' in short footnote",
            field="short_footnote",
            current_value=short_footnote[:80],
            category="format",
        ))

    # Check ED abbreviation
    if config.short_requires_ed and config.short_ed_abbreviation:
        if config.short_ed_abbreviation not in short_footnote:
            issues.append(Issue(
                source_id=source_id,
                issue_type="short_missing_ed",
                severity="error",
                message=f"Missing '{config.short_ed_abbreviation}' in short footnote",
                field="short_footnote",
                current_value=short_footnote[:80],
                category="missing",
            ))

    # Check sheet/stamp/page (1880 uses "p. X (stamped)")
    has_sheet = bool(re.search(r'sheet\s+\d+[AB]?', short_footnote, re.IGNORECASE))
    has_stamp = bool(re.search(r'stamp\s+\d+', short_footnote, re.IGNORECASE))
    has_page_stamped = bool(re.search(r'p\.\s+\d+\s*\(stamped\)', short_footnote, re.IGNORECASE))

    # 1880 uses stamped page numbers
    if config.year == 1880:
        if not has_page_stamped:
            issues.append(Issue(
                source_id=source_id,
                issue_type="short_missing_page_stamped",
                severity="error",
                message="Missing 'p. X (stamped)' in short footnote (1880 format)",
                field="short_footnote",
                category="missing",
            ))
    elif config.short_allows_sheet_or_stamp:
        if not has_sheet and not has_stamp:
            issues.append(Issue(
                source_id=source_id,
                issue_type="short_missing_sheet_or_stamp",
                severity="error",
                message="Missing sheet or stamp in short footnote",
                field="short_footnote",
                category="missing",
            ))
    elif config.short_requires_sheet and not has_sheet:
        issues.append(Issue(
            source_id=source_id,
            issue_type="short_missing_sheet",
            severity="error",
            message="Missing sheet number in short footnote",
            field="short_footnote",
            category="missing",
        ))

    # Check line (matches "line 41" or "ln. 41")
    has_line = bool(re.search(r'(?:line|ln\.?)\s*\d+', short_footnote, re.IGNORECASE))
    if config.short_requires_line:
        if config.short_line_required_with_sheet_only:
            if has_sheet and not has_line:
                issues.append(Issue(
                    source_id=source_id,
                    issue_type="short_missing_line",
                    severity="error",
                    message="Missing line in short footnote (required with sheet)",
                    field="short_footnote",
                    category="missing",
                ))
        elif not has_line:
            issues.append(Issue(
                source_id=source_id,
                issue_type="short_missing_line",
                severity="error",
                message="Missing line number in short footnote",
                field="short_footnote",
                category="missing",
            ))

    # Check schedule type requirement
    if config.short_requires_schedule:
        schedule_found = False
        if config.short_schedule_patterns:
            for pattern in config.short_schedule_patterns:
                if pattern.lower() in short_footnote.lower():
                    schedule_found = True
                    break
        if not schedule_found:
            expected = ", ".join(config.short_schedule_patterns or [])
            issues.append(Issue(
                source_id=source_id,
                issue_type="short_missing_schedule_type",
                severity="error",
                message=f"Missing schedule type in short footnote (expected: {expected})",
                field="short_footnote",
                current_value=short_footnote[:80],
                expected_value=expected,
                category="missing",
            ))

    # Check ending period
    if config.short_requires_ending_period:
        stripped = short_footnote.rstrip()
        if stripped and not stripped.endswith("."):
            issues.append(Issue(
                source_id=source_id,
                issue_type="short_no_ending_period",
                severity="warning",
                message="Short footnote should end with period",
                field="short_footnote",
                current_value=short_footnote[-30:] if len(short_footnote) > 30 else short_footnote,
                category="format",
            ))

    return issues


def check_bibliography(
    source_id: int,
    bibliography: str,
    config: CensusYearConfig
) -> list[Issue]:
    """Check bibliography for issues."""
    issues = []

    if not bibliography:
        issues.append(Issue(
            source_id=source_id,
            issue_type="empty_bibliography",
            severity="error",
            message="Bibliography is empty",
            field="bibliography",
            category="missing",
        ))
        return issues

    # Check quoted title
    title_match = re.search(r'"([^"]+)"', bibliography)
    if title_match:
        found_title = title_match.group(1)
        expected = config.bibliography_quoted_title
        alt_titles = config.bibliography_alt_titles or []

        if found_title != expected and found_title not in alt_titles:
            issues.append(Issue(
                source_id=source_id,
                issue_type="wrong_bibliography_title",
                severity="warning",
                message="Wrong quoted title in bibliography",
                field="bibliography",
                current_value=found_title,
                expected_value=expected,
                category="title",
            ))

    # Check for double spaces
    if "  " in bibliography:
        issues.append(Issue(
            source_id=source_id,
            issue_type="bibliography_double_space",
            severity="warning",
            message="Double space found in bibliography",
            field="bibliography",
            category="format",
        ))

    return issues


def check_cross_field_consistency(
    source_id: int,
    name: str,
    footnote: str,
    short_footnote: str,
    bibliography: str,
    config: CensusYearConfig
) -> list[Issue]:
    """Check consistency between source name, footnote, short footnote, and bibliography."""
    issues = []

    # Extract components
    name_comp = ComponentExtractor.extract_from_source_name(name, config.year)
    fn_comp = ComponentExtractor.extract_from_footnote(footnote)
    short_comp = ComponentExtractor.extract_from_short_footnote(short_footnote)
    bib_comp = ComponentExtractor.extract_from_bibliography(bibliography)

    # Check ED consistency
    if name_comp.ed and fn_comp.ed:
        # Normalize EDs for comparison (strip trailing letters, leading zeros)
        name_ed_base = re.sub(r'[A-Z]$', '', name_comp.ed).lstrip('0') or '0'
        fn_ed_base = re.sub(r'[A-Z]$', '', fn_comp.ed).lstrip('0') or '0'

        if name_ed_base != fn_ed_base and name_comp.ed != fn_comp.ed:
            issues.append(Issue(
                source_id=source_id,
                issue_type="ed_mismatch",
                severity="warning",
                message="ED in source name doesn't match ED in footnote",
                field="consistency",
                current_value=f"Name: {name_comp.ed}, Footnote: {fn_comp.ed}",
                category="consistency",
            ))

    # Check sheet consistency
    if name_comp.sheet and fn_comp.sheet:
        if name_comp.sheet != fn_comp.sheet:
            issues.append(Issue(
                source_id=source_id,
                issue_type="sheet_mismatch",
                severity="warning",
                message="Sheet in source name doesn't match sheet in footnote",
                field="consistency",
                current_value=f"Name: {name_comp.sheet}, Footnote: {fn_comp.sheet}",
                category="consistency",
            ))

    # Check state consistency (source name vs footnote)
    if name_comp.state and fn_comp.state:
        if name_comp.state.lower() != fn_comp.state.lower():
            issues.append(Issue(
                source_id=source_id,
                issue_type="footnote_state_mismatch",
                severity="error",
                message="State in footnote doesn't match state in source name",
                field="footnote",
                current_value=fn_comp.state,
                expected_value=name_comp.state,
                category="consistency",
            ))

    # Check county consistency (source name vs footnote)
    if name_comp.county and fn_comp.county:
        if name_comp.county.lower() != fn_comp.county.lower():
            issues.append(Issue(
                source_id=source_id,
                issue_type="footnote_county_mismatch",
                severity="error",
                message="County in footnote doesn't match county in source name",
                field="footnote",
                current_value=fn_comp.county,
                expected_value=name_comp.county,
                category="consistency",
            ))

    # Check state abbreviation in short footnote
    if name_comp.state and short_comp.state:
        expected_abbrev = STATE_ABBREVIATIONS.get(name_comp.state)
        if expected_abbrev and short_comp.state != expected_abbrev:
            issues.append(Issue(
                source_id=source_id,
                issue_type="short_state_mismatch",
                severity="error",
                message="State abbreviation in short footnote doesn't match",
                field="short_footnote",
                current_value=short_comp.state,
                expected_value=expected_abbrev,
                category="consistency",
            ))

    # Check bibliography state consistency
    if name_comp.state and bib_comp.state:
        if bib_comp.state != name_comp.state:
            issues.append(Issue(
                source_id=source_id,
                issue_type="bibliography_state_mismatch",
                severity="error",
                message="State in bibliography doesn't match source name",
                field="bibliography",
                current_value=bib_comp.state,
                expected_value=name_comp.state,
                category="consistency",
            ))

    # Independent city validation (if module available)
    if HAS_INDEPENDENT_CITIES and name_comp.state and name_comp.county:
        issues.extend(check_independent_city(
            source_id, name_comp.county, name_comp.state, fn_comp.raw_text
        ))

    return issues


def check_independent_city(
    source_id: int,
    county_name: str,
    state_name: str,
    footnote_text: str
) -> list[Issue]:
    """Check for independent city / county confusion."""
    issues = []

    if is_independent_city(county_name, state_name):
        ic_info = get_independent_city(county_name, state_name)

        county_pattern = f"{county_name} County"
        has_county_in_footnote = county_pattern in footnote_text
        has_independent_city = "(Independent City)" in footnote_text

        if has_county_in_footnote and not has_independent_city:
            # Check for patterns that suggest it's actually the county
            county_pattern_found = False
            city_pattern_found = False

            if ic_info and ic_info.county_locality_pattern:
                if ic_info.county_locality_pattern in footnote_text:
                    county_pattern_found = True

            if ic_info and ic_info.locality_pattern:
                if ic_info.locality_pattern in footnote_text:
                    city_pattern_found = True

            if county_pattern_found and not city_pattern_found:
                issues.append(Issue(
                    source_id=source_id,
                    issue_type="independent_city_is_county",
                    severity="error",
                    message=f"Source Name says '{county_name}' but footnote indicates this is {ic_info.related_county}",
                    field="source_name",
                    current_value=county_name,
                    expected_value=ic_info.related_county if ic_info else f"{county_name} County",
                    category="jurisdiction",
                ))
            else:
                issues.append(Issue(
                    source_id=source_id,
                    issue_type="independent_city_ambiguous",
                    severity="warning",
                    message=f"Source Name says '{county_name}' but footnote says '{county_name} County'",
                    field="footnote",
                    current_value=f"{county_name} County",
                    expected_value=f"{county_name} (Independent City)",
                    category="jurisdiction",
                ))

    return issues


def find_similar_state(name: str) -> str | None:
    """Find a similar valid state name (for typo detection)."""
    name_lower = name.lower()
    for state in VALID_STATE_NAMES:
        if name_lower == state.lower():
            return state
        # Simple character difference check
        if len(name) == len(state):
            diffs = sum(1 for a, b in zip(name_lower, state.lower()) if a != b)
            if diffs <= 2:
                return state
    return None


# =============================================================================
# Database Functions
# =============================================================================

def extract_field_from_blob(fields_blob: bytes | str | None, field_name: str) -> str:
    """Extract a field value from the Fields BLOB."""
    if not fields_blob:
        return ""
    try:
        if isinstance(fields_blob, bytes):
            text = fields_blob.decode("utf-8", errors="ignore")
        else:
            text = fields_blob
        pattern = rf'<Name>{field_name}</Name>\s*<Value>(.*?)</Value>'
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1) if match else ""
    except Exception:
        return ""


def get_sources_for_year(conn: sqlite3.Connection, year: int) -> list[dict]:
    """Get all census sources for a specific year with media counts."""
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            s.SourceID,
            s.Name,
            s.Fields,
            (SELECT COUNT(*) FROM MediaLinkTable ml
             WHERE ml.OwnerID = s.SourceID AND ml.OwnerType = 3) as media_count
        FROM SourceTable s
        WHERE s.Name LIKE ?
        ORDER BY s.SourceID
    ''', (f'Fed Census: {year},%',))

    sources = []
    for row in cursor.fetchall():
        source_id, name, fields_blob, media_count = row

        footnote = extract_field_from_blob(fields_blob, "Footnote")
        short_footnote = extract_field_from_blob(fields_blob, "ShortFootnote")
        bibliography = extract_field_from_blob(fields_blob, "Bibliography")

        sources.append({
            'source_id': source_id,
            'name': name,
            'footnote': footnote,
            'short_footnote': short_footnote,
            'bibliography': bibliography,
            'media_count': media_count,
        })

    return sources


def get_citation_quality_counts(conn: sqlite3.Connection, year: int) -> dict[str, int]:
    """Get citation quality value counts for a census year."""
    cursor = conn.cursor()

    cursor.execute('''
        SELECT cl.Quality, COUNT(*) as cnt
        FROM CitationLinkTable cl
        JOIN CitationTable c ON c.CitationID = cl.CitationID
        JOIN SourceTable s ON s.SourceID = c.SourceID
        WHERE s.Name LIKE ?
        GROUP BY cl.Quality
    ''', (f'Fed Census: {year},%',))

    return {row[0]: row[1] for row in cursor.fetchall()}


# =============================================================================
# Main Quality Check
# =============================================================================

def run_quality_check(db_path: Path, year: int, include_all: bool = False) -> dict:
    """Run quality check for a specific census year."""
    configs = build_census_configs()

    if year not in configs:
        return {
            "error": f"No configuration for census year {year}",
            "supported_years": sorted(configs.keys())
        }

    config = configs[year]

    conn = sqlite3.connect(db_path)
    sources = get_sources_for_year(conn, year)
    quality_counts = get_citation_quality_counts(conn, year)
    conn.close()

    all_issues = []
    media_counts = {"no_media": 0, "single": 0, "multiple": 0}
    source_names = {}

    for source in sources:
        source_id = source['source_id']
        name = source['name']
        footnote = source['footnote']
        short_footnote = source['short_footnote']
        bibliography = source['bibliography']
        media_count = source['media_count']

        source_names[source_id] = name

        # Run all checks
        all_issues.extend(check_source_name(source_id, name, config))
        all_issues.extend(check_footnote(source_id, footnote, config))
        all_issues.extend(check_short_footnote(source_id, short_footnote, config))
        all_issues.extend(check_bibliography(source_id, bibliography, config))
        all_issues.extend(check_cross_field_consistency(
            source_id, name, footnote, short_footnote, bibliography, config
        ))

        # Track media counts
        if media_count == 0:
            media_counts["no_media"] += 1
            all_issues.append(Issue(
                source_id=source_id,
                issue_type="no_media",
                severity="warning",
                message="Source has no media attachments",
                field="media",
                category="media",
            ))
        elif media_count == 1:
            media_counts["single"] += 1
        else:
            media_counts["multiple"] += 1
            if include_all:
                all_issues.append(Issue(
                    source_id=source_id,
                    issue_type="multiple_media",
                    severity="info",
                    message=f"Source has {media_count} media attachments",
                    field="media",
                    category="media",
                ))

    # Check citation quality
    wrong_quality_issues = []
    for quality, count in quality_counts.items():
        if quality != config.expected_citation_quality:
            wrong_quality_issues.append(Issue(
                source_id=0,  # Aggregate issue
                issue_type="wrong_citation_quality",
                severity="warning",
                message=f"Citation quality should be '{config.expected_citation_quality}'",
                field="quality",
                current_value=quality,
                expected_value=config.expected_citation_quality,
                category="quality",
            ))

    # Compile results
    by_severity = Counter(i.severity for i in all_issues)
    by_type = Counter(i.issue_type for i in all_issues)

    result = {
        "year": year,
        "description": config.description,
        "total_sources": len(sources),
        "total_issues": len(all_issues),
        "by_severity": dict(by_severity),
        "by_type": dict(by_type),
        "quality_counts": quality_counts,
        "media_counts": media_counts,
        "issues": [i.to_dict() for i in all_issues],
        "source_names": source_names,
    }

    return result


# =============================================================================
# Output Formatting
# =============================================================================

def format_text_output(result: dict, detailed: bool = False) -> str:
    """Format result as human-readable text."""
    lines = []

    lines.append("=" * 60)
    lines.append(f"CENSUS QUALITY CHECK: {result['year']}")
    lines.append("=" * 60)
    lines.append(f"Description: {result.get('description', '')}")
    lines.append("")
    lines.append(f"Total sources: {result['total_sources']}")
    lines.append(f"Total issues: {result['total_issues']}")
    lines.append("")

    if result.get('by_severity'):
        lines.append("Issues by severity:")
        for severity in ["error", "warning", "info"]:
            count = result['by_severity'].get(severity, 0)
            if count:
                lines.append(f"  {severity}: {count}")
        lines.append("")

    if result.get('by_type'):
        lines.append("Issues by type:")
        for issue_type, count in sorted(result['by_type'].items(), key=lambda x: -x[1]):
            lines.append(f"  {issue_type}: {count}")
        lines.append("")

    if result.get('quality_counts'):
        lines.append("Citation quality values:")
        for quality, count in result['quality_counts'].items():
            status = "✓" if quality == "PDO" else "✗"
            lines.append(f"  {status} {quality}: {count}")
        lines.append("")

    if result.get('media_counts'):
        lines.append("Media attachments:")
        lines.append(f"  No media: {result['media_counts'].get('no_media', 0)}")
        lines.append(f"  Single media: {result['media_counts'].get('single', 0)}")
        lines.append(f"  Multiple media: {result['media_counts'].get('multiple', 0)}")
        lines.append("")

    if result.get('issues'):
        if detailed:
            lines.append("All issues:")
            source_names = result.get('source_names', {})
            for issue in result['issues']:
                sid = issue['source_id']
                name = source_names.get(sid, f"Source {sid}")
                lines.append(f"  Source {sid}: [{issue['severity']}] {issue['issue_type']}")
                lines.append(f"    {issue['message']}")
                if issue.get('current_value'):
                    lines.append(f"    Current: {issue['current_value']}")
        else:
            lines.append(f"Sample issues (first 10):")
            for issue in result['issues'][:10]:
                lines.append(f"  Source {issue['source_id']}: [{issue['severity']}] {issue['issue_type']}")
                lines.append(f"    {issue['message']}")
                if issue.get('current_value'):
                    lines.append(f"    Current: {issue['current_value']}")
            if len(result['issues']) > 10:
                lines.append(f"  ... and {len(result['issues']) - 10} more issues")

    return "\n".join(lines)


# =============================================================================
# CLI Entry Point
# =============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Census Quality Check - Validate Federal Census sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "year",
        type=int,
        help="Census year to check (1790-1950)"
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/Iiams.rmtree"),
        help="Path to RootsMagic database"
    )

    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="Output format (default: text)"
    )

    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show all issues with full details"
    )

    parser.add_argument(
        "--include-all-issues",
        action="store_true",
        help="Include informational issues (multiple media, etc.)"
    )

    args = parser.parse_args()

    # Validate year
    if args.year < 1790 or args.year > 1950 or args.year % 10 != 0:
        print(f"Error: Invalid census year: {args.year}", file=sys.stderr)
        print("Valid years: 1790, 1800, ..., 1950", file=sys.stderr)
        return 1

    # Run check
    result = run_quality_check(args.db, args.year, args.include_all_issues)

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(format_text_output(result, args.detailed))

    return 0


if __name__ == "__main__":
    sys.exit(main())
