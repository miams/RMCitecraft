#!/usr/bin/env python3
"""
Census Quality Check Tool for RMCitecraft.

Performs comprehensive quality checks on Federal Census sources (1790-1950)
in a RootsMagic database. Designed to be used as a tool by Claude Code.

Each census year has explicit, self-contained validation rules with no
implicit assumptions or inheritance between years.

Checks include:
- Source Name format and consistency
- Footnote completeness and format
- Short Footnote completeness and format
- Bibliography format
- Citation Quality settings
- Media attachments

Usage:
    python scripts/census_quality_check.py 1940
    python scripts/census_quality_check.py 1940 --format json
    python scripts/census_quality_check.py 1940 --format text --verbose
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
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable

# Configure logging to stderr only
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


# =============================================================================
# Census Year Configuration - Explicit per-year definitions
# =============================================================================

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

    # Bibliography validation
    bibliography_quoted_title: str  # Expected title in quotes

    # Citation quality
    expected_citation_quality: str  # e.g., "PDO"

    # Description for output
    description: str


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
        # Bibliography
        bibliography_quoted_title="United States Census, 1790.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1800 Census
    # =========================================================================
    configs[1800] = CensusYearConfig(
        year=1800,
        description="Second U.S. Census - heads of household only",
        # Source name
        source_name_prefix="Fed Census: 1800,",
        source_name_requires_ed=False,
        source_name_ed_pattern=None,
        source_name_requires_sheet=False,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=False,
        source_name_line_required_with_sheet_only=False,
        # Footnote
        footnote_census_ref="1800 U.S. census",
        footnote_requires_ed=False,
        footnote_ed_pattern=None,
        footnote_requires_sheet=False,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=False,
        footnote_line_required_with_sheet_only=False,
        footnote_quoted_title="United States Census, 1800,",
        # Short footnote
        short_census_ref="1800 U.S. census",
        short_requires_ed=False,
        short_ed_abbreviation=None,
        short_requires_sheet=False,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=False,
        short_line_required_with_sheet_only=False,
        short_requires_ending_period=True,
        # Bibliography
        bibliography_quoted_title="United States Census, 1800.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1810 Census
    # =========================================================================
    configs[1810] = CensusYearConfig(
        year=1810,
        description="Third U.S. Census - heads of household only",
        # Source name
        source_name_prefix="Fed Census: 1810,",
        source_name_requires_ed=False,
        source_name_ed_pattern=None,
        source_name_requires_sheet=False,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=False,
        source_name_line_required_with_sheet_only=False,
        # Footnote
        footnote_census_ref="1810 U.S. census",
        footnote_requires_ed=False,
        footnote_ed_pattern=None,
        footnote_requires_sheet=False,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=False,
        footnote_line_required_with_sheet_only=False,
        footnote_quoted_title="United States Census, 1810,",
        # Short footnote
        short_census_ref="1810 U.S. census",
        short_requires_ed=False,
        short_ed_abbreviation=None,
        short_requires_sheet=False,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=False,
        short_line_required_with_sheet_only=False,
        short_requires_ending_period=True,
        # Bibliography
        bibliography_quoted_title="United States Census, 1810.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1820 Census
    # =========================================================================
    configs[1820] = CensusYearConfig(
        year=1820,
        description="Fourth U.S. Census - heads of household only",
        # Source name
        source_name_prefix="Fed Census: 1820,",
        source_name_requires_ed=False,
        source_name_ed_pattern=None,
        source_name_requires_sheet=False,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=False,
        source_name_line_required_with_sheet_only=False,
        # Footnote
        footnote_census_ref="1820 U.S. census",
        footnote_requires_ed=False,
        footnote_ed_pattern=None,
        footnote_requires_sheet=False,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=False,
        footnote_line_required_with_sheet_only=False,
        footnote_quoted_title="United States Census, 1820,",
        # Short footnote
        short_census_ref="1820 U.S. census",
        short_requires_ed=False,
        short_ed_abbreviation=None,
        short_requires_sheet=False,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=False,
        short_line_required_with_sheet_only=False,
        short_requires_ending_period=True,
        # Bibliography
        bibliography_quoted_title="United States Census, 1820.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1830 Census
    # =========================================================================
    configs[1830] = CensusYearConfig(
        year=1830,
        description="Fifth U.S. Census - heads of household only",
        # Source name
        source_name_prefix="Fed Census: 1830,",
        source_name_requires_ed=False,
        source_name_ed_pattern=None,
        source_name_requires_sheet=False,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=False,
        source_name_line_required_with_sheet_only=False,
        # Footnote
        footnote_census_ref="1830 U.S. census",
        footnote_requires_ed=False,
        footnote_ed_pattern=None,
        footnote_requires_sheet=False,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=False,
        footnote_line_required_with_sheet_only=False,
        footnote_quoted_title="United States Census, 1830,",
        # Short footnote
        short_census_ref="1830 U.S. census",
        short_requires_ed=False,
        short_ed_abbreviation=None,
        short_requires_sheet=False,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=False,
        short_line_required_with_sheet_only=False,
        short_requires_ending_period=True,
        # Bibliography
        bibliography_quoted_title="United States Census, 1830.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1840 Census
    # =========================================================================
    configs[1840] = CensusYearConfig(
        year=1840,
        description="Sixth U.S. Census - heads of household only",
        # Source name
        source_name_prefix="Fed Census: 1840,",
        source_name_requires_ed=False,
        source_name_ed_pattern=None,
        source_name_requires_sheet=False,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=False,
        source_name_line_required_with_sheet_only=False,
        # Footnote
        footnote_census_ref="1840 U.S. census",
        footnote_requires_ed=False,
        footnote_ed_pattern=None,
        footnote_requires_sheet=False,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=False,
        footnote_line_required_with_sheet_only=False,
        footnote_quoted_title="United States Census, 1840,",
        # Short footnote
        short_census_ref="1840 U.S. census",
        short_requires_ed=False,
        short_ed_abbreviation=None,
        short_requires_sheet=False,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=False,
        short_line_required_with_sheet_only=False,
        short_requires_ending_period=True,
        # Bibliography
        bibliography_quoted_title="United States Census, 1840.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1850 Census - First census to enumerate all individuals
    # =========================================================================
    configs[1850] = CensusYearConfig(
        year=1850,
        description="Seventh U.S. Census - first to enumerate all individuals",
        # Source name
        source_name_prefix="Fed Census: 1850,",
        source_name_requires_ed=False,
        source_name_ed_pattern=None,
        source_name_requires_sheet=True,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=True,
        source_name_line_required_with_sheet_only=False,
        # Footnote
        footnote_census_ref="1850 U.S. census",
        footnote_requires_ed=False,
        footnote_ed_pattern=None,
        footnote_requires_sheet=True,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=True,
        footnote_line_required_with_sheet_only=False,
        footnote_quoted_title="United States Census, 1850,",
        # Short footnote
        short_census_ref="1850 U.S. census",
        short_requires_ed=False,
        short_ed_abbreviation=None,
        short_requires_sheet=True,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=True,
        short_line_required_with_sheet_only=False,
        short_requires_ending_period=True,
        # Bibliography
        bibliography_quoted_title="United States Census, 1850.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1860 Census
    # =========================================================================
    configs[1860] = CensusYearConfig(
        year=1860,
        description="Eighth U.S. Census",
        # Source name
        source_name_prefix="Fed Census: 1860,",
        source_name_requires_ed=False,
        source_name_ed_pattern=None,
        source_name_requires_sheet=True,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=True,
        source_name_line_required_with_sheet_only=False,
        # Footnote
        footnote_census_ref="1860 U.S. census",
        footnote_requires_ed=False,
        footnote_ed_pattern=None,
        footnote_requires_sheet=True,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=True,
        footnote_line_required_with_sheet_only=False,
        footnote_quoted_title="United States Census, 1860,",
        # Short footnote
        short_census_ref="1860 U.S. census",
        short_requires_ed=False,
        short_ed_abbreviation=None,
        short_requires_sheet=True,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=True,
        short_line_required_with_sheet_only=False,
        short_requires_ending_period=True,
        # Bibliography
        bibliography_quoted_title="United States Census, 1860.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1870 Census
    # =========================================================================
    configs[1870] = CensusYearConfig(
        year=1870,
        description="Ninth U.S. Census",
        # Source name
        source_name_prefix="Fed Census: 1870,",
        source_name_requires_ed=False,
        source_name_ed_pattern=None,
        source_name_requires_sheet=True,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=True,
        source_name_line_required_with_sheet_only=False,
        # Footnote
        footnote_census_ref="1870 U.S. census",
        footnote_requires_ed=False,
        footnote_ed_pattern=None,
        footnote_requires_sheet=True,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=True,
        footnote_line_required_with_sheet_only=False,
        footnote_quoted_title="United States Census, 1870,",
        # Short footnote
        short_census_ref="1870 U.S. census",
        short_requires_ed=False,
        short_ed_abbreviation=None,
        short_requires_sheet=True,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=True,
        short_line_required_with_sheet_only=False,
        short_requires_ending_period=True,
        # Bibliography
        bibliography_quoted_title="United States Census, 1870.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1880 Census - First census with Enumeration Districts
    # =========================================================================
    configs[1880] = CensusYearConfig(
        year=1880,
        description="Tenth U.S. Census - first with Enumeration Districts (ED)",
        # Source name
        source_name_prefix="Fed Census: 1880,",
        source_name_requires_ed=True,
        source_name_ed_pattern=r'\[ED (\d+[A-Z]?),',  # Simple ED number, e.g., ED 95
        source_name_requires_sheet=True,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=True,
        source_name_line_required_with_sheet_only=False,
        # Footnote
        footnote_census_ref="1880 U.S. census",
        footnote_requires_ed=True,
        footnote_ed_pattern=r'enumeration district \(ED\)',
        footnote_requires_sheet=True,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=True,
        footnote_line_required_with_sheet_only=False,
        footnote_quoted_title="United States Census, 1880,",
        # Short footnote
        short_census_ref="1880 U.S. census",
        short_requires_ed=True,
        short_ed_abbreviation="E.D.",
        short_requires_sheet=True,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=True,
        short_line_required_with_sheet_only=False,
        short_requires_ending_period=True,
        # Bibliography
        bibliography_quoted_title="United States Census, 1880.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1890 Census - Mostly destroyed by fire
    # =========================================================================
    configs[1890] = CensusYearConfig(
        year=1890,
        description="Eleventh U.S. Census - mostly destroyed by 1921 fire",
        # Source name
        source_name_prefix="Fed Census: 1890,",
        source_name_requires_ed=True,
        source_name_ed_pattern=r'\[ED (\d+[A-Z]?),',
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
        # Bibliography
        bibliography_quoted_title="United States Census, 1890.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1900 Census - ED format changes to XX-YY
    # =========================================================================
    configs[1900] = CensusYearConfig(
        year=1900,
        description="Twelfth U.S. Census - ED format XX-YY",
        # Source name
        source_name_prefix="Fed Census: 1900,",
        source_name_requires_ed=True,
        source_name_ed_pattern=r'\[ED (\d+[A-Z]?-\d+[A-Z]?),',  # ED format like 7-36A
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
        footnote_quoted_title="United States Census, 1900,",
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
        # Bibliography
        bibliography_quoted_title="United States Census, 1900.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1910 Census
    # =========================================================================
    configs[1910] = CensusYearConfig(
        year=1910,
        description="Thirteenth U.S. Census",
        # Source name
        source_name_prefix="Fed Census: 1910,",
        source_name_requires_ed=True,
        source_name_ed_pattern=r'\[ED (\d+[A-Z]?-\d+[A-Z]?),',
        source_name_requires_sheet=True,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=True,
        source_name_line_required_with_sheet_only=False,
        # Footnote
        footnote_census_ref="1910 U.S. census",
        footnote_requires_ed=True,
        footnote_ed_pattern=r'enumeration district \(ED\)',
        footnote_requires_sheet=True,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=True,
        footnote_line_required_with_sheet_only=False,
        footnote_quoted_title="United States Census, 1910,",
        # Short footnote
        short_census_ref="1910 U.S. census",
        short_requires_ed=True,
        short_ed_abbreviation="E.D.",
        short_requires_sheet=True,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=True,
        short_line_required_with_sheet_only=False,
        short_requires_ending_period=True,
        # Bibliography
        bibliography_quoted_title="United States Census, 1910.",
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
        source_name_ed_pattern=r'\[ED (\d+[A-Z]?-\d+[A-Z]?),',
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
        footnote_quoted_title="United States Census, 1920,",
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
        # Bibliography
        bibliography_quoted_title="United States Census, 1920.",
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
        source_name_ed_pattern=r'\[ED (\d+[A-Z]?-\d+[A-Z]?),',
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
        footnote_quoted_title="United States Census, 1930,",
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
        # Bibliography
        bibliography_quoted_title="United States Census, 1930.",
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
        footnote_quoted_title="United States Census, 1940,",
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
        # Bibliography
        bibliography_quoted_title="United States Census, 1940.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1950 Census - Dual format: sheet/line OR stamp
    # =========================================================================
    configs[1950] = CensusYearConfig(
        year=1950,
        description="Seventeenth U.S. Census - uses sheet/line OR stamp format",
        # Source name
        source_name_prefix="Fed Census: 1950,",
        source_name_requires_ed=True,
        source_name_ed_pattern=r'\[ED (\d+-\d+),',  # ED format like 10-93
        source_name_requires_sheet=False,  # Not strictly required
        source_name_requires_stamp=False,  # Not strictly required
        source_name_allows_sheet_or_stamp=True,  # Either format is valid
        source_name_requires_line=False,  # Not strictly required
        source_name_line_required_with_sheet_only=True,  # Line only required with sheet format
        # Footnote
        footnote_census_ref="1950 U.S. census",
        footnote_requires_ed=True,
        footnote_ed_pattern=r'enumeration district \(ED\)',
        footnote_requires_sheet=False,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=True,  # Either format is valid
        footnote_requires_line=False,
        footnote_line_required_with_sheet_only=True,  # Line only required with sheet format
        footnote_quoted_title="United States Census, 1950,",
        # Short footnote
        short_census_ref="1950 U.S. census",
        short_requires_ed=True,
        short_ed_abbreviation="E.D.",
        short_requires_sheet=False,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=True,  # Either format is valid
        short_requires_line=False,
        short_line_required_with_sheet_only=True,  # Line only required with sheet format
        short_requires_ending_period=True,
        # Bibliography
        bibliography_quoted_title="United States Census, 1950.",
        # Quality
        expected_citation_quality="PDO",
    )

    return configs


# Build configs once at module load
CENSUS_CONFIGS = build_census_configs()

# Valid census years
VALID_CENSUS_YEARS = set(CENSUS_CONFIGS.keys())


def get_census_config(year: int) -> CensusYearConfig | None:
    """Get configuration for a specific census year.

    Returns None if year is not a valid census year.
    """
    return CENSUS_CONFIGS.get(year)


# Known valid US state names
VALID_STATES = {
    'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado',
    'Connecticut', 'Delaware', 'Florida', 'Georgia', 'Hawaii', 'Idaho',
    'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky', 'Louisiana',
    'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota',
    'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada',
    'New Hampshire', 'New Jersey', 'New Mexico', 'New York',
    'North Carolina', 'North Dakota', 'Ohio', 'Oklahoma', 'Oregon',
    'Pennsylvania', 'Rhode Island', 'South Carolina', 'South Dakota',
    'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia', 'Washington',
    'West Virginia', 'Wisconsin', 'Wyoming', 'District of Columbia'
}


# =============================================================================
# Data Classes for Results
# =============================================================================

@dataclass
class Issue:
    """Represents a single quality issue."""
    source_id: int
    issue_type: str
    severity: str  # error, warning, info
    message: str
    field: str  # source_name, footnote, short_footnote, bibliography, quality, media
    current_value: str = ""
    expected_value: str = ""


@dataclass
class QualityCheckResult:
    """Complete result of quality check."""
    success: bool
    census_year: int
    total_sources: int
    issues: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


# =============================================================================
# Database Connection
# =============================================================================

def connect_database(db_path: Path) -> sqlite3.Connection:
    """Connect to RootsMagic database with ICU extension."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)

    # Try to load ICU extension for RMNOCASE collation
    script_dir = Path(__file__).parent.parent
    possible_paths = [
        script_dir / 'sqlite-extension/icu.dylib',
        Path('sqlite-extension/icu.dylib'),
        Path.cwd() / 'sqlite-extension/icu.dylib',
    ]

    icu_loaded = False
    for icu_path in possible_paths:
        if icu_path.exists():
            try:
                conn.enable_load_extension(True)
                conn.load_extension(str(icu_path))
                conn.execute(
                    "SELECT icu_load_collation("
                    "'en_US@colStrength=primary;caseLevel=off;normalization=on',"
                    "'RMNOCASE')"
                )
                conn.enable_load_extension(False)
                logger.debug(f"Loaded ICU extension from {icu_path}")
                icu_loaded = True
                break
            except Exception as e:
                logger.warning(f"Could not load ICU extension from {icu_path}: {e}")

    if not icu_loaded:
        logger.warning("ICU extension not loaded - RMNOCASE collation may fail")

    return conn


# =============================================================================
# Validation Functions
# =============================================================================

def extract_field_from_blob(fields_blob: bytes, field_name: str) -> str:
    """Extract a field value from the Fields BLOB XML structure."""
    if not fields_blob:
        return ""

    try:
        fields_text = fields_blob.decode('utf-8', errors='ignore')
        pattern = rf'<Name>{field_name}</Name>\s*<Value>(.*?)</Value>'
        match = re.search(pattern, fields_text, re.DOTALL)
        return match.group(1) if match else ""
    except Exception:
        return ""


def check_source_name(source_id: int, name: str, config: CensusYearConfig) -> list[Issue]:
    """Check source name format and content using explicit config rules."""
    issues = []
    year = config.year

    # Check prefix
    if not name.startswith(config.source_name_prefix):
        issues.append(Issue(
            source_id=source_id,
            issue_type="source_name_format",
            severity="error",
            message=f"Source name doesn't start with '{config.source_name_prefix}'",
            field="source_name",
            current_value=name[:50]
        ))
        return issues

    # Extract and validate state name
    state_match = re.match(rf'Fed Census: {year}, ([^,]+),', name)
    if state_match:
        state = state_match.group(1).strip()
        if state not in VALID_STATES:
            issues.append(Issue(
                source_id=source_id,
                issue_type="state_name_typo",
                severity="error",
                message=f"Invalid state name: '{state}'",
                field="source_name",
                current_value=state
            ))

    # Check ED requirement
    if config.source_name_requires_ed:
        if '[ED' not in name:
            issues.append(Issue(
                source_id=source_id,
                issue_type="source_name_missing_ed",
                severity="error",
                message="Missing ED (enumeration district) in source name",
                field="source_name",
                current_value=name[:80]
            ))

    # Check sheet/stamp requirements
    has_sheet = 'sheet' in name.lower()
    has_stamp = 'stamp' in name.lower()

    if config.source_name_allows_sheet_or_stamp:
        # Either format is acceptable
        if not has_sheet and not has_stamp:
            issues.append(Issue(
                source_id=source_id,
                issue_type="source_name_missing_sheet_or_stamp",
                severity="error",
                message=f"Missing sheet or stamp number in source name ({year} census)",
                field="source_name",
                current_value=name[:80]
            ))
    else:
        # Specific format required
        if config.source_name_requires_sheet and not has_sheet:
            issues.append(Issue(
                source_id=source_id,
                issue_type="source_name_missing_sheet",
                severity="error",
                message="Missing sheet number in source name",
                field="source_name",
                current_value=name[:80]
            ))
        if config.source_name_requires_stamp and not has_stamp:
            issues.append(Issue(
                source_id=source_id,
                issue_type="source_name_missing_stamp",
                severity="error",
                message=f"Missing stamp number in source name ({year} census)",
                field="source_name",
                current_value=name[:80]
            ))

    # Check line requirement
    has_line = 'line' in name.lower()

    if config.source_name_line_required_with_sheet_only:
        # Line only required if using sheet format
        if has_sheet and not has_line:
            issues.append(Issue(
                source_id=source_id,
                issue_type="source_name_missing_line",
                severity="error",
                message="Missing line number in source name (required with sheet format)",
                field="source_name",
                current_value=name[:80]
            ))
    elif config.source_name_requires_line and not has_line:
        issues.append(Issue(
            source_id=source_id,
            issue_type="source_name_missing_line",
            severity="error",
            message="Missing line number in source name",
            field="source_name",
            current_value=name[:80]
        ))

    return issues


def check_footnote(source_id: int, footnote: str, config: CensusYearConfig) -> list[Issue]:
    """Check footnote format and content using explicit config rules."""
    issues = []
    year = config.year

    if not footnote:
        issues.append(Issue(
            source_id=source_id,
            issue_type="empty_footnote",
            severity="error",
            message="Footnote is empty",
            field="footnote"
        ))
        return issues

    # Check census reference
    if not re.search(rf'{year} U\.S\. census', footnote):
        issues.append(Issue(
            source_id=source_id,
            issue_type="footnote_missing_census_ref",
            severity="error",
            message=f"Missing '{config.footnote_census_ref}' reference",
            field="footnote",
            current_value=footnote[:100]
        ))

    # Check ED requirement
    if config.footnote_requires_ed:
        if config.footnote_ed_pattern and not re.search(config.footnote_ed_pattern, footnote, re.IGNORECASE):
            issues.append(Issue(
                source_id=source_id,
                issue_type="footnote_missing_ed",
                severity="error",
                message="Missing 'enumeration district (ED)' in footnote",
                field="footnote",
                current_value=footnote[:100]
            ))

    # Check sheet/stamp requirements
    has_sheet = bool(re.search(r'sheet \d+', footnote, re.IGNORECASE))
    has_stamp = bool(re.search(r'stamp \d+', footnote, re.IGNORECASE))

    if config.footnote_allows_sheet_or_stamp:
        if not has_sheet and not has_stamp:
            issues.append(Issue(
                source_id=source_id,
                issue_type="footnote_missing_sheet_or_stamp",
                severity="error",
                message=f"Missing sheet or stamp number in footnote ({year} census)",
                field="footnote",
                current_value=footnote[:100]
            ))
    else:
        if config.footnote_requires_sheet and not has_sheet:
            issues.append(Issue(
                source_id=source_id,
                issue_type="footnote_missing_sheet",
                severity="error",
                message="Missing sheet number in footnote",
                field="footnote",
                current_value=footnote[:100]
            ))
        if config.footnote_requires_stamp and not has_stamp:
            issues.append(Issue(
                source_id=source_id,
                issue_type="footnote_missing_stamp",
                severity="error",
                message=f"Missing stamp number in footnote ({year} census)",
                field="footnote",
                current_value=footnote[:100]
            ))

    # Check line requirement
    has_line = bool(re.search(r'line \d+', footnote, re.IGNORECASE))

    if config.footnote_line_required_with_sheet_only:
        if has_sheet and not has_line:
            issues.append(Issue(
                source_id=source_id,
                issue_type="footnote_missing_line",
                severity="error",
                message="Missing line number in footnote (required with sheet format)",
                field="footnote",
                current_value=footnote[:100]
            ))
    elif config.footnote_requires_line and not has_line:
        issues.append(Issue(
            source_id=source_id,
            issue_type="footnote_missing_line",
            severity="error",
            message="Missing line number in footnote",
            field="footnote",
            current_value=footnote[:100]
        ))

    # Check quoted title
    title_match = re.search(r'["\u201c]([^"\u201d]+)["\u201d]', footnote) or \
                  re.search(r'&quot;([^&]+)&quot;', footnote)
    if title_match:
        title = title_match.group(1)
        if title != config.footnote_quoted_title:
            issues.append(Issue(
                source_id=source_id,
                issue_type="footnote_wrong_title",
                severity="warning",
                message="Wrong quoted title in footnote",
                field="footnote",
                current_value=title,
                expected_value=config.footnote_quoted_title
            ))

    # Check for double spaces
    if '  ' in footnote:
        issues.append(Issue(
            source_id=source_id,
            issue_type="footnote_double_space",
            severity="warning",
            message="Double space found in footnote",
            field="footnote"
        ))

    return issues


def check_short_footnote(source_id: int, short_footnote: str, config: CensusYearConfig) -> list[Issue]:
    """Check short footnote format and content using explicit config rules."""
    issues = []
    year = config.year

    if not short_footnote:
        issues.append(Issue(
            source_id=source_id,
            issue_type="empty_short_footnote",
            severity="error",
            message="Short footnote is empty",
            field="short_footnote"
        ))
        return issues

    # Check census reference
    if not re.search(rf'{year} U\.S\. census', short_footnote):
        issues.append(Issue(
            source_id=source_id,
            issue_type="short_missing_census_ref",
            severity="error",
            message=f"Missing '{config.short_census_ref}' reference",
            field="short_footnote",
            current_value=short_footnote[:100]
        ))

    # Check ED abbreviation
    if config.short_requires_ed and config.short_ed_abbreviation:
        if not re.search(rf'{re.escape(config.short_ed_abbreviation)}\s+\d+', short_footnote):
            if 'enumeration district' in short_footnote.lower():
                issues.append(Issue(
                    source_id=source_id,
                    issue_type="short_ed_not_abbreviated",
                    severity="warning",
                    message=f"Short footnote should use '{config.short_ed_abbreviation}' not 'enumeration district'",
                    field="short_footnote",
                    current_value=short_footnote[:100]
                ))
            else:
                issues.append(Issue(
                    source_id=source_id,
                    issue_type="short_missing_ed",
                    severity="error",
                    message=f"Missing '{config.short_ed_abbreviation}' in short footnote",
                    field="short_footnote",
                    current_value=short_footnote[:100]
                ))

    # Check sheet/stamp requirements
    has_sheet = bool(re.search(r'sheet \d+', short_footnote, re.IGNORECASE))
    has_stamp = bool(re.search(r'stamp \d+', short_footnote, re.IGNORECASE))

    if config.short_allows_sheet_or_stamp:
        if not has_sheet and not has_stamp:
            issues.append(Issue(
                source_id=source_id,
                issue_type="short_missing_sheet_or_stamp",
                severity="error",
                message=f"Missing sheet or stamp number in short footnote ({year} census)",
                field="short_footnote",
                current_value=short_footnote[:100]
            ))
    else:
        if config.short_requires_sheet and not has_sheet:
            issues.append(Issue(
                source_id=source_id,
                issue_type="short_missing_sheet",
                severity="error",
                message="Missing sheet number in short footnote",
                field="short_footnote",
                current_value=short_footnote[:100]
            ))
        if config.short_requires_stamp and not has_stamp:
            issues.append(Issue(
                source_id=source_id,
                issue_type="short_missing_stamp",
                severity="error",
                message=f"Missing stamp number in short footnote ({year} census)",
                field="short_footnote",
                current_value=short_footnote[:100]
            ))

    # Check line requirement
    has_line = bool(re.search(r'line \d+', short_footnote, re.IGNORECASE))

    if config.short_line_required_with_sheet_only:
        if has_sheet and not has_line:
            issues.append(Issue(
                source_id=source_id,
                issue_type="short_missing_line",
                severity="error",
                message="Missing line number in short footnote (required with sheet format)",
                field="short_footnote",
                current_value=short_footnote[:100]
            ))
    elif config.short_requires_line and not has_line:
        issues.append(Issue(
            source_id=source_id,
            issue_type="short_missing_line",
            severity="error",
            message="Missing line number in short footnote",
            field="short_footnote",
            current_value=short_footnote[:100]
        ))

    # Check ending period
    if config.short_requires_ending_period and not short_footnote.strip().endswith('.'):
        issues.append(Issue(
            source_id=source_id,
            issue_type="short_no_ending_period",
            severity="warning",
            message="Short footnote doesn't end with period",
            field="short_footnote",
            current_value=short_footnote[-30:]
        ))

    # Check for double spaces
    if '  ' in short_footnote:
        issues.append(Issue(
            source_id=source_id,
            issue_type="short_double_space",
            severity="warning",
            message="Double space found in short footnote",
            field="short_footnote"
        ))

    return issues


def check_bibliography(source_id: int, bibliography: str, config: CensusYearConfig) -> list[Issue]:
    """Check bibliography format and content using explicit config rules."""
    issues = []

    if not bibliography:
        issues.append(Issue(
            source_id=source_id,
            issue_type="empty_bibliography",
            severity="error",
            message="Bibliography is empty",
            field="bibliography"
        ))
        return issues

    # Check quoted title
    title_match = re.search(r'["\u201c]([^"\u201d]+)["\u201d]', bibliography) or \
                  re.search(r'&quot;([^&]+)&quot;', bibliography)
    if title_match:
        title = title_match.group(1)
        if title != config.bibliography_quoted_title:
            issues.append(Issue(
                source_id=source_id,
                issue_type="bibliography_wrong_title",
                severity="warning",
                message="Wrong quoted title in bibliography",
                field="bibliography",
                current_value=title,
                expected_value=config.bibliography_quoted_title
            ))

    # Check for trailing period after closing quote (common error)
    if f'"{config.bibliography_quoted_title}".' in bibliography or \
       f'&quot;{config.bibliography_quoted_title}&quot;.' in bibliography:
        issues.append(Issue(
            source_id=source_id,
            issue_type="bibliography_trailing_period",
            severity="warning",
            message="Trailing period after closing quote in bibliography",
            field="bibliography"
        ))

    # Check for double spaces
    if '  ' in bibliography:
        issues.append(Issue(
            source_id=source_id,
            issue_type="bibliography_double_space",
            severity="warning",
            message="Double space found in bibliography",
            field="bibliography"
        ))

    return issues


def check_citation_quality(conn: sqlite3.Connection, year: int, config: CensusYearConfig) -> tuple[list[Issue], dict]:
    """Check citation quality settings."""
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            cl.LinkID,
            cl.CitationID,
            cl.Quality,
            c.SourceID,
            s.Name
        FROM CitationLinkTable cl
        JOIN CitationTable c ON c.CitationID = cl.CitationID
        JOIN SourceTable s ON s.SourceID = c.SourceID
        WHERE s.Name LIKE ?
    ''', (f'Fed Census: {year},%',))

    issues = []
    quality_counts = Counter()

    for link_id, cit_id, quality, source_id, source_name in cursor.fetchall():
        quality_counts[quality or '(empty)'] += 1

        if quality != config.expected_citation_quality:
            issues.append(Issue(
                source_id=source_id,
                issue_type="wrong_citation_quality",
                severity="warning",
                message=f"Citation quality should be '{config.expected_citation_quality}'",
                field="quality",
                current_value=quality or '(empty)',
                expected_value=config.expected_citation_quality
            ))

    return issues, dict(quality_counts)


def check_media(conn: sqlite3.Connection, year: int) -> tuple[list[Issue], dict]:
    """Check media attachments for census sources."""
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            s.SourceID,
            s.Name,
            COUNT(ml.LinkID) as media_count
        FROM SourceTable s
        LEFT JOIN MediaLinkTable ml ON ml.OwnerID = s.SourceID AND ml.OwnerType = 3
        WHERE s.Name LIKE ?
        GROUP BY s.SourceID, s.Name
    ''', (f'Fed Census: {year},%',))

    issues = []
    no_media = 0
    single_media = 0
    multiple_media = 0

    for source_id, name, count in cursor.fetchall():
        if count == 0:
            no_media += 1
            issues.append(Issue(
                source_id=source_id,
                issue_type="no_media",
                severity="warning",
                message="Source has no media attachment",
                field="media",
                current_value=name[:60]
            ))
        elif count == 1:
            single_media += 1
        else:
            multiple_media += 1
            issues.append(Issue(
                source_id=source_id,
                issue_type="multiple_media",
                severity="info",
                message=f"Source has {count} media attachments",
                field="media",
                current_value=name[:60]
            ))

    return issues, {
        "no_media": no_media,
        "single_media": single_media,
        "multiple_media": multiple_media
    }


# =============================================================================
# Main Quality Check Function
# =============================================================================

def run_quality_check(db_path: Path, year: int) -> QualityCheckResult:
    """Run comprehensive quality check on census sources."""

    config = get_census_config(year)

    result = QualityCheckResult(
        success=True,
        census_year=year,
        total_sources=0,
        issues=[],
        summary={},
        metadata={}
    )

    if config is None:
        result.success = False
        result.metadata["error"] = f"No configuration defined for census year {year}"
        result.metadata["valid_years"] = sorted(VALID_CENSUS_YEARS)
        return result

    result.metadata["config"] = {
        "year": config.year,
        "description": config.description,
        "requires_ed": config.source_name_requires_ed,
        "requires_sheet": config.source_name_requires_sheet,
        "requires_stamp": config.source_name_requires_stamp,
        "allows_sheet_or_stamp": config.source_name_allows_sheet_or_stamp,
    }

    try:
        conn = connect_database(db_path)
    except FileNotFoundError as e:
        result.success = False
        result.metadata["error"] = str(e)
        return result

    cursor = conn.cursor()

    # Get all sources for this census year
    cursor.execute('''
        SELECT SourceID, Name, Fields
        FROM SourceTable
        WHERE Name LIKE ?
    ''', (f'Fed Census: {year},%',))

    sources = cursor.fetchall()
    result.total_sources = len(sources)

    if result.total_sources == 0:
        result.metadata["warning"] = f"No sources found for census year {year}"
        conn.close()
        return result

    # Check each source
    all_issues = []

    for source_id, name, fields_blob in sources:
        all_issues.extend(check_source_name(source_id, name, config))

        footnote = extract_field_from_blob(fields_blob, "Footnote")
        short_footnote = extract_field_from_blob(fields_blob, "ShortFootnote")
        bibliography = extract_field_from_blob(fields_blob, "Bibliography")

        all_issues.extend(check_footnote(source_id, footnote, config))
        all_issues.extend(check_short_footnote(source_id, short_footnote, config))
        all_issues.extend(check_bibliography(source_id, bibliography, config))

    # Citation quality checks
    quality_issues, quality_summary = check_citation_quality(conn, year, config)
    all_issues.extend(quality_issues)

    # Media checks
    media_issues, media_summary = check_media(conn, year)
    all_issues.extend(media_issues)

    conn.close()

    # Compile results
    result.issues = [asdict(issue) for issue in all_issues]

    issue_summary = Counter(issue.issue_type for issue in all_issues)
    severity_summary = Counter(issue.severity for issue in all_issues)
    field_summary = Counter(issue.field for issue in all_issues)

    result.summary = {
        "total_issues": len(all_issues),
        "by_type": dict(issue_summary),
        "by_severity": dict(severity_summary),
        "by_field": dict(field_summary),
        "quality": quality_summary,
        "media": media_summary
    }

    return result


# =============================================================================
# Output Formatting
# =============================================================================

def format_text_output(result: QualityCheckResult) -> str:
    """Format result as human-readable text."""
    lines = []

    lines.append(f"{'=' * 60}")
    lines.append(f"CENSUS QUALITY CHECK: {result.census_year}")
    lines.append(f"{'=' * 60}")

    # Show config info
    if result.metadata.get('config'):
        cfg = result.metadata['config']
        lines.append(f"Description: {cfg.get('description', 'N/A')}")
        lines.append(f"Requires ED: {cfg.get('requires_ed', 'N/A')}")
        if cfg.get('allows_sheet_or_stamp'):
            lines.append("Reference format: sheet/line OR stamp")
        elif cfg.get('requires_sheet'):
            lines.append("Reference format: sheet/line")
        elif cfg.get('requires_stamp'):
            lines.append("Reference format: stamp")
        lines.append("")

    lines.append(f"Total sources: {result.total_sources}")
    lines.append(f"Total issues: {result.summary.get('total_issues', 0)}")
    lines.append("")

    if result.summary.get('by_severity'):
        lines.append("Issues by severity:")
        for severity, count in sorted(result.summary['by_severity'].items()):
            lines.append(f"  {severity}: {count}")
        lines.append("")

    if result.summary.get('by_type'):
        lines.append("Issues by type:")
        for issue_type, count in sorted(result.summary['by_type'].items(), key=lambda x: -x[1]):
            lines.append(f"  {issue_type}: {count}")
        lines.append("")

    if result.summary.get('quality'):
        lines.append("Citation quality values:")
        for quality, count in result.summary['quality'].items():
            status = '✓' if quality == 'PDO' else '✗'
            lines.append(f"  {status} {quality}: {count}")
        lines.append("")

    if result.summary.get('media'):
        media = result.summary['media']
        lines.append("Media attachments:")
        lines.append(f"  No media: {media.get('no_media', 0)}")
        lines.append(f"  Single media: {media.get('single_media', 0)}")
        lines.append(f"  Multiple media: {media.get('multiple_media', 0)}")
        lines.append("")

    if result.issues:
        lines.append("Sample issues (first 10):")
        for issue in result.issues[:10]:
            lines.append(f"  Source {issue['source_id']}: [{issue['severity']}] {issue['issue_type']}")
            lines.append(f"    {issue['message']}")
            if issue.get('current_value'):
                lines.append(f"    Current: {issue['current_value'][:60]}")
        if len(result.issues) > 10:
            lines.append(f"  ... and {len(result.issues) - 10} more issues")

    return "\n".join(lines)


# =============================================================================
# Main Entry Point
# =============================================================================

def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "year",
        type=int,
        nargs='?',  # Make optional when using --list-years
        help=f"Census year to check. Valid years: {sorted(VALID_CENSUS_YEARS)}"
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/Iiams.rmtree"),
        help="Path to RootsMagic database (default: data/Iiams.rmtree)"
    )

    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    parser.add_argument(
        "--include-all-issues",
        action="store_true",
        help="Include all issues in output (default: summary only for JSON)"
    )

    parser.add_argument(
        "--list-years",
        action="store_true",
        help="List all supported census years and exit"
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    if args.list_years:
        print("Supported census years:")
        for year in sorted(VALID_CENSUS_YEARS):
            config = get_census_config(year)
            if config:
                print(f"  {year}: {config.description}")
        return 0

    # Require year if not listing
    if args.year is None:
        parser.error("year is required (use --list-years to see valid years)")

    # Validate year
    if args.year not in VALID_CENSUS_YEARS:
        error = {
            "success": False,
            "error": f"Invalid census year: {args.year}",
            "error_type": "ValueError",
            "valid_years": sorted(VALID_CENSUS_YEARS)
        }
        print(json.dumps(error, indent=2), file=sys.stderr)
        return 1

    # Run quality check
    logger.debug(f"Running quality check for {args.year} census")
    result = run_quality_check(args.db, args.year)

    # Format output
    if args.format == "json":
        output = asdict(result)
        if not args.include_all_issues and len(output.get('issues', [])) > 20:
            output['issues'] = output['issues'][:20]
            output['metadata']['issues_truncated'] = True
            output['metadata']['total_issues'] = result.summary.get('total_issues', 0)
        print(json.dumps(output, indent=2))
    else:
        print(format_text_output(result))

    return 0


if __name__ == "__main__":
    sys.exit(main())
