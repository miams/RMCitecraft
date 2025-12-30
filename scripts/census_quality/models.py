"""Data classes for census quality checking.

Contains the core data structures used throughout the census quality check system.
"""

from dataclasses import dataclass


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
    source_name_requires_family: bool  # Require "family X" or "household ID X"

    # Footnote validation
    footnote_census_ref: str  # e.g., "1940 U.S. census"
    footnote_requires_ed: bool
    footnote_ed_pattern: str | None  # e.g., "enumeration district (ED)"
    footnote_requires_sheet: bool
    footnote_requires_stamp: bool
    footnote_allows_sheet_or_stamp: bool
    footnote_requires_line: bool
    footnote_line_required_with_sheet_only: bool
    footnote_requires_family: bool  # Require "family X"
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
    short_requires_family: bool  # Require "family X"
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
