#!/usr/bin/env python3
"""
Census Quality Check v2 - Robust validation for Federal Census sources.

This script validates census source records against Evidence Explained standards
and FamilySearch official naming conventions. It performs:

1. Component extraction from source name, footnote, short footnote, bibliography
2. Cross-validation between fields (ED, sheet, line should be consistent)
3. Format validation per census year requirements
4. Detection of duplicates, orphans, and media issues

Usage:
    python scripts/census_quality_check_v2.py 1930              # Check 1930 census
    python scripts/census_quality_check_v2.py 1930 1940 1950    # Check multiple years
    python scripts/census_quality_check_v2.py --all             # Check all supported years
    python scripts/census_quality_check_v2.py 1930 --format md  # Markdown output
    python scripts/census_quality_check_v2.py 1930 --fix-report # Generate fix suggestions

Supported years: 1790-1950
"""

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any
from collections import Counter, defaultdict


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


# Official FamilySearch collection titles (with trailing period for bibliography)
FAMILYSEARCH_TITLES = {
    year: f"United States, Census, {year}"
    for year in range(1790, 1960, 10)
}

# State abbreviations for validation
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
    raw_text: str = ""


@dataclass
class Issue:
    """A single validation issue."""
    source_id: int
    issue_type: str
    severity: Severity
    category: IssueCategory
    message: str
    field: str
    current_value: str = ""
    expected_value: str = ""
    fix_suggestion: str = ""

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "issue_type": self.issue_type,
            "severity": self.severity.value,
            "category": self.category.value,
            "message": self.message,
            "field": self.field,
            "current_value": self.current_value,
            "expected_value": self.expected_value,
            "fix_suggestion": self.fix_suggestion,
        }


@dataclass
class SourceRecord:
    """Complete source record with all extracted components."""
    source_id: int
    name: str
    fields_blob: bytes | None
    footnote: str = ""
    short_footnote: str = ""
    bibliography: str = ""
    citation_quality: str = ""
    media_count: int = 0
    citation_count: int = 0

    # Extracted components
    name_components: CensusComponents = field(default_factory=CensusComponents)
    footnote_components: CensusComponents = field(default_factory=CensusComponents)
    short_components: CensusComponents = field(default_factory=CensusComponents)
    bibliography_components: CensusComponents = field(default_factory=CensusComponents)


@dataclass
class YearConfig:
    """Configuration for a specific census year."""
    year: int
    description: str

    # Source name patterns
    source_prefix: str  # e.g., "Fed Census: 1930,"
    ed_pattern: str  # Regex to extract ED from source name
    requires_line: bool = True
    requires_sheet: bool = True
    allows_stamp: bool = False  # 1950 can use stamp instead of sheet

    # Expected titles (FamilySearch format)
    bibliography_title: str = ""  # With trailing period
    footnote_title: str = ""  # With trailing comma

    # ED format
    ed_format: str = "simple"  # "simple" (123) or "compound" (12-34)

    def __post_init__(self):
        if not self.bibliography_title:
            self.bibliography_title = f"{FAMILYSEARCH_TITLES[self.year]}."
        if not self.footnote_title:
            self.footnote_title = f"{FAMILYSEARCH_TITLES[self.year]},"


# =============================================================================
# Text Normalization
# =============================================================================

class TextNormalizer:
    """Normalize text for consistent processing."""

    @staticmethod
    def normalize_quotes(text: str) -> str:
        """Convert all quote formats to standard double quotes."""
        # XML entities
        text = text.replace("&quot;", '"')
        # Smart quotes
        text = text.replace("\u201c", '"').replace("\u201d", '"')
        text = text.replace("\u2018", "'").replace("\u2019", "'")
        return text

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """Normalize whitespace (but preserve for double-space detection)."""
        return text.strip()

    @staticmethod
    def decode_html_entities(text: str) -> str:
        """Decode common HTML entities."""
        replacements = {
            "&lt;": "<",
            "&gt;": ">",
            "&amp;": "&",
            "&apos;": "'",
        }
        for entity, char in replacements.items():
            text = text.replace(entity, char)
        return text

    @classmethod
    def normalize(cls, text: str) -> str:
        """Apply all normalizations."""
        text = cls.normalize_quotes(text)
        text = cls.normalize_whitespace(text)
        return text


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
        "source_ed_citing": r"\[citing\s+enumeration\s+district\s+\(ED\)\s+(\d+)",
        "source_sheet": r"sheet\s+(\d+[AB]?)",
        "source_stamp": r"stamp\s+(\d+(?:-\d+)?)",
        "source_line": r"line\s+(\d+)",
        "source_family": r"family\s+(\d+)",
        "source_person": r"\]\s+([^,\]]+(?:,\s*[^,\]]+)?)\s*$",

        # Footnote patterns
        "fn_year": r"(\d{4})\s+U\.S\.\s+census",
        "fn_county_state": r"(\w+(?:\s+\w+)?)\s+County,\s+(\w+(?:\s+\w+)?)",
        "fn_ed": r"enumeration\s+district\s+\(ED\)\s+(\d+[A-Z]?(?:-\d+[A-Z]?)?)",
        "fn_sheet": r"sheet\s+(\d+[AB]?)",
        "fn_stamp": r"stamp\s+(\d+)",
        "fn_line": r"line\s+(\d+)",

        # Quoted title (for both footnote and bibliography)
        "quoted_title": r'"([^"]+)"',

        # Short footnote patterns
        "short_year": r"(\d{4})\s+U\.S\.\s+census",
        "short_county_state": r"(\w+(?:\s+\w+)?)\s+Co\.,\s+(\w+\.?)",
        "short_ed": r"E\.D\.\s+(\d+[A-Z]?(?:-\d+[A-Z]?)?)",
        "short_sheet": r"sheet\s+(\d+[AB]?)",
        "short_stamp": r"stamp\s+(\d+)",
        "short_line": r"line\s+(\d+)",
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
        footnote = TextNormalizer.normalize(footnote)
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

        # Quoted title
        if match := re.search(cls.PATTERNS["quoted_title"], footnote):
            components.quoted_title = match.group(1)

        return components

    @classmethod
    def extract_from_short_footnote(cls, short: str) -> CensusComponents:
        """Extract components from short footnote."""
        short = TextNormalizer.normalize(short)
        components = CensusComponents(raw_text=short)

        # Year
        if match := re.search(cls.PATTERNS["short_year"], short):
            components.year = int(match.group(1))

        # County and State abbreviation
        if match := re.search(cls.PATTERNS["short_county_state"], short):
            components.county = match.group(1)
            components.state = match.group(2)

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

        return components

    @classmethod
    def extract_from_bibliography(cls, bibliography: str) -> CensusComponents:
        """Extract components from bibliography."""
        bibliography = TextNormalizer.normalize(bibliography)
        components = CensusComponents(raw_text=bibliography)

        # Quoted title
        if match := re.search(cls.PATTERNS["quoted_title"], bibliography):
            components.quoted_title = match.group(1)

        return components


# =============================================================================
# Validation
# =============================================================================

class CensusValidator:
    """Validate census source records."""

    def __init__(self, config: YearConfig):
        self.config = config
        self.year = config.year

    def validate(self, record: SourceRecord) -> list[Issue]:
        """Run all validations on a source record."""
        issues = []

        # Source name validation
        issues.extend(self._validate_source_name(record))

        # Footnote validation
        issues.extend(self._validate_footnote(record))

        # Short footnote validation
        issues.extend(self._validate_short_footnote(record))

        # Bibliography validation
        issues.extend(self._validate_bibliography(record))

        # Cross-field consistency
        issues.extend(self._validate_consistency(record))

        # Citation quality
        issues.extend(self._validate_quality(record))

        return issues

    def _validate_source_name(self, record: SourceRecord) -> list[Issue]:
        """Validate source name format."""
        issues = []
        name = record.name
        components = record.name_components
        sid = record.source_id

        # Check prefix
        if not name.startswith(self.config.source_prefix):
            issues.append(Issue(
                source_id=sid,
                issue_type="wrong_source_prefix",
                severity=Severity.ERROR,
                category=IssueCategory.FORMAT,
                message=f"Source name should start with '{self.config.source_prefix}'",
                field="source_name",
                current_value=name[:50],
                expected_value=self.config.source_prefix,
            ))

        # Check state name
        if components.state:
            if components.state not in VALID_STATE_NAMES:
                # Check for common typos
                similar = self._find_similar_state(components.state)
                issues.append(Issue(
                    source_id=sid,
                    issue_type="invalid_state_name",
                    severity=Severity.WARNING,
                    category=IssueCategory.TYPO,
                    message=f"Invalid or misspelled state name",
                    field="source_name",
                    current_value=components.state,
                    expected_value=similar or "",
                    fix_suggestion=f"Change '{components.state}' to '{similar}'" if similar else "",
                ))

        # Check ED presence
        if not components.ed:
            # Check for typos in the ED pattern
            if "[iting" in name or "numeration" in name:
                issues.append(Issue(
                    source_id=sid,
                    issue_type="ed_pattern_typo",
                    severity=Severity.ERROR,
                    category=IssueCategory.TYPO,
                    message="Typo in enumeration district pattern",
                    field="source_name",
                    current_value=name[:80],
                    fix_suggestion="Fix '[iting' to '[citing' or 'numeration' to 'enumeration'",
                ))
            else:
                issues.append(Issue(
                    source_id=sid,
                    issue_type="missing_ed",
                    severity=Severity.ERROR,
                    category=IssueCategory.MISSING,
                    message="Missing enumeration district (ED) in source name",
                    field="source_name",
                    current_value=name[:80],
                ))

        # Check sheet/stamp
        has_sheet = components.sheet is not None
        has_stamp = components.stamp is not None

        if self.config.allows_stamp:
            if not has_sheet and not has_stamp:
                issues.append(Issue(
                    source_id=sid,
                    issue_type="missing_sheet_or_stamp",
                    severity=Severity.ERROR,
                    category=IssueCategory.MISSING,
                    message="Missing sheet or stamp number",
                    field="source_name",
                    current_value=name[:80],
                ))
        elif self.config.requires_sheet and not has_sheet:
            issues.append(Issue(
                source_id=sid,
                issue_type="missing_sheet",
                severity=Severity.ERROR,
                category=IssueCategory.MISSING,
                message="Missing sheet number in source name",
                field="source_name",
                current_value=name[:80],
            ))

        # Check line (required if sheet format, not stamp)
        if self.config.requires_line:
            if has_sheet and not has_stamp and components.line is None:
                issues.append(Issue(
                    source_id=sid,
                    issue_type="missing_line",
                    severity=Severity.ERROR,
                    category=IssueCategory.MISSING,
                    message="Missing line number in source name",
                    field="source_name",
                    current_value=name[:80],
                ))

        return issues

    def _validate_footnote(self, record: SourceRecord) -> list[Issue]:
        """Validate footnote format."""
        issues = []
        footnote = record.footnote
        components = record.footnote_components
        sid = record.source_id

        if not footnote:
            issues.append(Issue(
                source_id=sid,
                issue_type="empty_footnote",
                severity=Severity.ERROR,
                category=IssueCategory.MISSING,
                message="Footnote is empty",
                field="footnote",
            ))
            return issues

        # Check census reference
        expected_ref = f"{self.year} U.S. census"
        if expected_ref not in footnote:
            issues.append(Issue(
                source_id=sid,
                issue_type="missing_census_ref",
                severity=Severity.ERROR,
                category=IssueCategory.FORMAT,
                message=f"Missing '{expected_ref}' reference",
                field="footnote",
                current_value=footnote[:80],
                expected_value=expected_ref,
            ))

        # Check quoted title
        if components.quoted_title:
            expected = self.config.footnote_title
            if components.quoted_title != expected:
                issues.append(Issue(
                    source_id=sid,
                    issue_type="wrong_footnote_title",
                    severity=Severity.WARNING,
                    category=IssueCategory.TITLE,
                    message="Wrong quoted title in footnote",
                    field="footnote",
                    current_value=components.quoted_title,
                    expected_value=expected,
                    fix_suggestion=f'Change "{components.quoted_title}" to "{expected}"',
                ))

        # Check for double spaces
        if "  " in footnote:
            issues.append(Issue(
                source_id=sid,
                issue_type="double_space",
                severity=Severity.WARNING,
                category=IssueCategory.FORMAT,
                message="Double space found in footnote",
                field="footnote",
            ))

        # Check ED presence
        if not components.ed and "enumeration district" not in footnote.lower():
            issues.append(Issue(
                source_id=sid,
                issue_type="missing_ed_in_footnote",
                severity=Severity.ERROR,
                category=IssueCategory.MISSING,
                message="Missing enumeration district in footnote",
                field="footnote",
                current_value=footnote[:80],
            ))

        return issues

    def _validate_short_footnote(self, record: SourceRecord) -> list[Issue]:
        """Validate short footnote format."""
        issues = []
        short = record.short_footnote
        components = record.short_components
        sid = record.source_id

        if not short:
            return issues  # Short footnote may be empty for some sources

        # Check census reference
        expected_ref = f"{self.year} U.S. census"
        if expected_ref not in short:
            issues.append(Issue(
                source_id=sid,
                issue_type="short_missing_census_ref",
                severity=Severity.ERROR,
                category=IssueCategory.FORMAT,
                message=f"Missing '{expected_ref}' reference in short footnote",
                field="short_footnote",
                current_value=short[:80],
            ))

        # Check E.D. abbreviation and number
        if "E.D." in short:
            # Check if ED number follows
            ed_match = re.search(r"E\.D\.\s+(\d+|,)", short)
            if ed_match and ed_match.group(1) == ",":
                issues.append(Issue(
                    source_id=sid,
                    issue_type="ed_number_missing",
                    severity=Severity.ERROR,
                    category=IssueCategory.MISSING,
                    message="ED number missing after 'E.D.' abbreviation",
                    field="short_footnote",
                    current_value=short[:80],
                    fix_suggestion="Add ED number after 'E.D.'",
                ))
        elif components.ed is None and record.name_components.ed:
            issues.append(Issue(
                source_id=sid,
                issue_type="short_ed_not_abbreviated",
                severity=Severity.WARNING,
                category=IssueCategory.FORMAT,
                message="Short footnote should use 'E.D.' abbreviation",
                field="short_footnote",
                current_value=short[:80],
            ))

        # Check ending period
        stripped = short.rstrip()
        if stripped and not stripped.endswith("."):
            issues.append(Issue(
                source_id=sid,
                issue_type="short_no_ending_period",
                severity=Severity.WARNING,
                category=IssueCategory.FORMAT,
                message="Short footnote should end with period",
                field="short_footnote",
                current_value=short[-30:] if len(short) > 30 else short,
            ))

        return issues

    def _validate_bibliography(self, record: SourceRecord) -> list[Issue]:
        """Validate bibliography format."""
        issues = []
        bibliography = record.bibliography
        components = record.bibliography_components
        sid = record.source_id

        if not bibliography:
            issues.append(Issue(
                source_id=sid,
                issue_type="empty_bibliography",
                severity=Severity.ERROR,
                category=IssueCategory.MISSING,
                message="Bibliography is empty",
                field="bibliography",
            ))
            return issues

        # Check quoted title
        if components.quoted_title:
            expected = self.config.bibliography_title
            if components.quoted_title != expected:
                issues.append(Issue(
                    source_id=sid,
                    issue_type="wrong_bibliography_title",
                    severity=Severity.WARNING,
                    category=IssueCategory.TITLE,
                    message="Wrong quoted title in bibliography",
                    field="bibliography",
                    current_value=components.quoted_title,
                    expected_value=expected,
                    fix_suggestion=f'Change "{components.quoted_title}" to "{expected}"',
                ))

        # Check for double spaces
        if "  " in bibliography:
            issues.append(Issue(
                source_id=sid,
                issue_type="bibliography_double_space",
                severity=Severity.WARNING,
                category=IssueCategory.FORMAT,
                message="Double space found in bibliography",
                field="bibliography",
            ))

        return issues

    def _validate_consistency(self, record: SourceRecord) -> list[Issue]:
        """Cross-validate consistency between fields."""
        issues = []
        sid = record.source_id

        name_comp = record.name_components
        fn_comp = record.footnote_components

        # Check ED consistency (allow for suffix differences like 116-128 vs 116-128A)
        if name_comp.ed and fn_comp.ed:
            # Normalize EDs for comparison (strip trailing letters)
            name_ed_base = re.sub(r'[A-Z]$', '', name_comp.ed)
            fn_ed_base = re.sub(r'[A-Z]$', '', fn_comp.ed)

            if name_ed_base != fn_ed_base and name_comp.ed != fn_comp.ed:
                issues.append(Issue(
                    source_id=sid,
                    issue_type="ed_mismatch",
                    severity=Severity.WARNING,
                    category=IssueCategory.CONSISTENCY,
                    message="ED in source name doesn't match ED in footnote",
                    field="consistency",
                    current_value=f"Name: {name_comp.ed}, Footnote: {fn_comp.ed}",
                ))

        # Check sheet consistency
        if name_comp.sheet and fn_comp.sheet:
            if name_comp.sheet != fn_comp.sheet:
                issues.append(Issue(
                    source_id=sid,
                    issue_type="sheet_mismatch",
                    severity=Severity.WARNING,
                    category=IssueCategory.CONSISTENCY,
                    message="Sheet in source name doesn't match sheet in footnote",
                    field="consistency",
                    current_value=f"Name: {name_comp.sheet}, Footnote: {fn_comp.sheet}",
                ))

        return issues

    def _validate_quality(self, record: SourceRecord) -> list[Issue]:
        """Validate citation quality setting."""
        issues = []

        if record.citation_quality and record.citation_quality != "PDO":
            issues.append(Issue(
                source_id=record.source_id,
                issue_type="wrong_citation_quality",
                severity=Severity.WARNING,
                category=IssueCategory.QUALITY,
                message=f"Citation quality is '{record.citation_quality}' instead of 'PDO'",
                field="quality",
                current_value=record.citation_quality,
                expected_value="PDO",
            ))

        return issues

    def _find_similar_state(self, name: str) -> str | None:
        """Find a similar valid state name (for typo detection)."""
        name_lower = name.lower()
        for state in VALID_STATE_NAMES:
            if name_lower == state.lower():
                return state
            # Simple Levenshtein-like check
            if len(name) == len(state):
                diffs = sum(1 for a, b in zip(name_lower, state.lower()) if a != b)
                if diffs <= 2:
                    return state
        return None


# =============================================================================
# Database Access
# =============================================================================

class DatabaseAccess:
    """Database access for census sources."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """Connect to database with ICU extension."""
        if self.conn:
            return self.conn

        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

        self.conn = sqlite3.connect(self.db_path)

        # Try to load ICU extension
        icu_paths = [
            Path("sqlite-extension/icu.dylib"),
            Path(__file__).parent.parent / "sqlite-extension/icu.dylib",
        ]

        for icu_path in icu_paths:
            if icu_path.exists():
                try:
                    self.conn.enable_load_extension(True)
                    self.conn.load_extension(str(icu_path))
                    self.conn.execute(
                        "SELECT icu_load_collation("
                        "'en_US@colStrength=primary;caseLevel=off;normalization=on',"
                        "'RMNOCASE')"
                    )
                    self.conn.enable_load_extension(False)
                    break
                except Exception:
                    pass

        return self.conn

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def get_sources_for_year(self, year: int) -> list[SourceRecord]:
        """Get all census sources for a specific year."""
        conn = self.connect()
        cursor = conn.cursor()

        # Get sources with media count and citation count
        cursor.execute('''
            SELECT
                s.SourceID,
                s.Name,
                s.Fields,
                (SELECT COUNT(*) FROM MediaLinkTable ml
                 WHERE ml.OwnerID = s.SourceID AND ml.OwnerType = 3) as media_count,
                (SELECT COUNT(*) FROM CitationTable c
                 WHERE c.SourceID = s.SourceID) as citation_count
            FROM SourceTable s
            WHERE s.Name LIKE ?
            ORDER BY s.SourceID
        ''', (f'Fed Census: {year},%',))

        records = []
        for row in cursor.fetchall():
            source_id, name, fields_blob, media_count, citation_count = row

            # Extract fields from blob
            footnote = self._extract_field(fields_blob, "Footnote")
            short_footnote = self._extract_field(fields_blob, "ShortFootnote")
            bibliography = self._extract_field(fields_blob, "Bibliography")

            record = SourceRecord(
                source_id=source_id,
                name=name,
                fields_blob=fields_blob,
                footnote=footnote,
                short_footnote=short_footnote,
                bibliography=bibliography,
                media_count=media_count,
                citation_count=citation_count,
            )

            # Extract components
            record.name_components = ComponentExtractor.extract_from_source_name(name, year)
            record.footnote_components = ComponentExtractor.extract_from_footnote(footnote)
            record.short_components = ComponentExtractor.extract_from_short_footnote(short_footnote)
            record.bibliography_components = ComponentExtractor.extract_from_bibliography(bibliography)

            # Extract citation quality from Fields BLOB
            record.citation_quality = self._extract_field(fields_blob, "Quality") or ""

            records.append(record)

        return records

    def _extract_field(self, fields_blob: bytes | None, field_name: str) -> str:
        """Extract a field value from Fields BLOB."""
        if not fields_blob:
            return ""
        try:
            text = fields_blob.decode("utf-8", errors="ignore")
            pattern = rf'<Name>{field_name}</Name>\s*<Value>(.*?)</Value>'
            match = re.search(pattern, text, re.DOTALL)
            return match.group(1) if match else ""
        except Exception:
            return ""

    def find_duplicates(self, year: int) -> list[tuple[int, str, list[int]]]:
        """Find duplicate sources (same ED/sheet/line)."""
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT s.SourceID, s.Name
            FROM SourceTable s
            WHERE s.Name LIKE ?
            ORDER BY s.Name
        ''', (f'Fed Census: {year},%',))

        # Group by location key
        location_groups: dict[str, list[tuple[int, str]]] = defaultdict(list)
        for source_id, name in cursor.fetchall():
            # Extract location key (everything up to person name)
            match = re.search(r'^(Fed Census: \d+, [^[]+\[[^\]]+line \d+)', name)
            if match:
                location_key = match.group(1)
                location_groups[location_key].append((source_id, name))

        # Find duplicates
        duplicates = []
        for location_key, sources in location_groups.items():
            if len(sources) > 1:
                source_ids = [s[0] for s in sources]
                duplicates.append((location_key, sources[0][1], source_ids))

        return duplicates

    def find_unused_sources(self, year: int) -> list[tuple[int, str]]:
        """Find sources with no citations."""
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT s.SourceID, s.Name
            FROM SourceTable s
            WHERE s.Name LIKE ?
            AND NOT EXISTS (SELECT 1 FROM CitationTable c WHERE c.SourceID = s.SourceID)
        ''', (f'Fed Census: {year},%',))

        return cursor.fetchall()


# =============================================================================
# Configuration Factory
# =============================================================================

def get_year_config(year: int) -> YearConfig:
    """Get configuration for a specific census year."""

    # Base configurations by era
    if year < 1880:
        # Pre-1880: No ED
        return YearConfig(
            year=year,
            description=f"{year} U.S. Census (pre-ED era)",
            source_prefix=f"Fed Census: {year},",
            ed_pattern="",
            requires_line=False,
            requires_sheet=True,
        )
    elif year == 1950:
        # 1950: Can use stamp instead of sheet
        return YearConfig(
            year=year,
            description="1950 U.S. Census (sheet/line OR stamp format)",
            source_prefix=f"Fed Census: {year},",
            ed_pattern=r'\[ED (\d+-\d+)',
            ed_format="compound",
            requires_line=True,
            requires_sheet=False,
            allows_stamp=True,
        )
    elif year >= 1940:
        # 1940+: Compound ED format (XX-YY)
        return YearConfig(
            year=year,
            description=f"{year} U.S. Census",
            source_prefix=f"Fed Census: {year},",
            ed_pattern=r'\[ED (\d+[A-Z]?-\d+[A-Z]?)',
            ed_format="compound",
            requires_line=True,
            requires_sheet=True,
        )
    elif year >= 1930:
        # 1930: Simple ED format, citing enumeration district pattern
        return YearConfig(
            year=year,
            description=f"{year} U.S. Census (simple ED format)",
            source_prefix=f"Fed Census: {year},",
            ed_pattern=r'\[citing enumeration district \(ED\) (\d+)',
            ed_format="simple",
            requires_line=True,
            requires_sheet=True,
        )
    else:
        # 1880-1920: ED introduced
        return YearConfig(
            year=year,
            description=f"{year} U.S. Census",
            source_prefix=f"Fed Census: {year},",
            ed_pattern=r'\[ED (\d+)',
            ed_format="simple",
            requires_line=True,
            requires_sheet=True,
        )


# =============================================================================
# Report Generation
# =============================================================================

@dataclass
class QualityReport:
    """Complete quality check report."""
    year: int
    total_sources: int
    issues: list[Issue]
    duplicates: list[tuple[str, str, list[int]]]
    unused_sources: list[tuple[int, str]]
    quality_counts: dict[str, int]
    media_counts: dict[str, int]

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics."""
        by_severity = Counter(i.severity.value for i in self.issues)
        by_type = Counter(i.issue_type for i in self.issues)
        by_category = Counter(i.category.value for i in self.issues)

        return {
            "total_sources": self.total_sources,
            "total_issues": len(self.issues),
            "by_severity": dict(by_severity),
            "by_type": dict(by_type),
            "by_category": dict(by_category),
            "duplicates": len(self.duplicates),
            "unused_sources": len(self.unused_sources),
            "quality": self.quality_counts,
            "media": self.media_counts,
        }


class ReportFormatter:
    """Format quality reports in various formats."""

    @staticmethod
    def format_text(report: QualityReport) -> str:
        """Format as plain text."""
        lines = []
        summary = report.get_summary()

        lines.append("=" * 70)
        lines.append(f"CENSUS QUALITY CHECK: {report.year}")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"Total Sources: {report.total_sources}")
        lines.append(f"Total Issues: {summary['total_issues']}")
        lines.append("")

        # Severity breakdown
        lines.append("Issues by Severity:")
        for severity in ["error", "warning", "info"]:
            count = summary["by_severity"].get(severity, 0)
            if count:
                lines.append(f"  {severity}: {count}")
        lines.append("")

        # Type breakdown
        if summary["by_type"]:
            lines.append("Issues by Type:")
            for issue_type, count in sorted(summary["by_type"].items(), key=lambda x: -x[1]):
                lines.append(f"  {issue_type}: {count}")
            lines.append("")

        # Quality
        lines.append("Citation Quality:")
        for quality, count in report.quality_counts.items():
            status = "✓" if quality == "PDO" else "✗"
            lines.append(f"  {status} {quality}: {count}")
        lines.append("")

        # Media
        lines.append("Media Attachments:")
        lines.append(f"  No media: {report.media_counts.get('no_media', 0)}")
        lines.append(f"  Single: {report.media_counts.get('single', 0)}")
        lines.append(f"  Multiple: {report.media_counts.get('multiple', 0)}")
        lines.append("")

        # Duplicates
        if report.duplicates:
            lines.append(f"Duplicate Sources: {len(report.duplicates)} groups")
            for _, name, source_ids in report.duplicates[:5]:
                lines.append(f"  Sources {source_ids}: {name[:60]}...")
            lines.append("")

        # Unused
        if report.unused_sources:
            lines.append(f"Unused Sources (no citations): {len(report.unused_sources)}")
            for sid, name in report.unused_sources[:5]:
                lines.append(f"  {sid}: {name[:60]}...")
            lines.append("")

        # Sample issues
        if report.issues:
            lines.append("Sample Issues (first 15):")
            for issue in report.issues[:15]:
                lines.append(f"  [{issue.severity.value.upper()}] Source {issue.source_id}: {issue.issue_type}")
                lines.append(f"    {issue.message}")
                if issue.current_value:
                    lines.append(f"    Current: {issue.current_value[:60]}")
                if issue.fix_suggestion:
                    lines.append(f"    Fix: {issue.fix_suggestion}")
            if len(report.issues) > 15:
                lines.append(f"  ... and {len(report.issues) - 15} more issues")

        return "\n".join(lines)

    @staticmethod
    def format_markdown(report: QualityReport) -> str:
        """Format as Markdown."""
        lines = []
        summary = report.get_summary()

        lines.append(f"# {report.year} Census Quality Report")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Sources | {report.total_sources} |")
        lines.append(f"| Total Issues | {summary['total_issues']} |")
        lines.append(f"| Errors | {summary['by_severity'].get('error', 0)} |")
        lines.append(f"| Warnings | {summary['by_severity'].get('warning', 0)} |")
        lines.append(f"| Info | {summary['by_severity'].get('info', 0)} |")
        lines.append("")

        # Quality
        lines.append("## Citation Quality")
        lines.append("")
        lines.append("| Status | Quality | Count |")
        lines.append("|--------|---------|-------|")
        for quality, count in report.quality_counts.items():
            status = "✓" if quality == "PDO" else "✗"
            lines.append(f"| {status} | {quality} | {count} |")
        lines.append("")

        # Issues by type
        if summary["by_type"]:
            lines.append("## Issues by Type")
            lines.append("")
            lines.append("| Issue Type | Count |")
            lines.append("|------------|-------|")
            for issue_type, count in sorted(summary["by_type"].items(), key=lambda x: -x[1]):
                lines.append(f"| {issue_type} | {count} |")
            lines.append("")

        # Detailed issues grouped by category
        lines.append("## Detailed Issues")
        lines.append("")

        issues_by_category = defaultdict(list)
        for issue in report.issues:
            issues_by_category[issue.category].append(issue)

        category_names = {
            IssueCategory.TITLE: "Title Issues",
            IssueCategory.FORMAT: "Format Issues",
            IssueCategory.MISSING: "Missing Data",
            IssueCategory.CONSISTENCY: "Consistency Issues",
            IssueCategory.DUPLICATE: "Duplicates",
            IssueCategory.QUALITY: "Quality Issues",
            IssueCategory.TYPO: "Typos",
            IssueCategory.MEDIA: "Media Issues",
        }

        for category, issues in issues_by_category.items():
            if not issues:
                continue
            lines.append(f"### {category_names.get(category, category.value)} ({len(issues)})")
            lines.append("")
            lines.append("| Source | Type | Message |")
            lines.append("|--------|------|---------|")
            for issue in issues[:20]:
                lines.append(f"| {issue.source_id} | {issue.issue_type} | {issue.message} |")
            if len(issues) > 20:
                lines.append(f"| ... | ... | {len(issues) - 20} more |")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_json(report: QualityReport) -> str:
        """Format as JSON."""
        data = {
            "year": report.year,
            "total_sources": report.total_sources,
            "summary": report.get_summary(),
            "issues": [i.to_dict() for i in report.issues],
            "duplicates": [
                {"location": loc, "name": name, "source_ids": ids}
                for loc, name, ids in report.duplicates
            ],
            "unused_sources": [
                {"source_id": sid, "name": name}
                for sid, name in report.unused_sources
            ],
        }
        return json.dumps(data, indent=2)


# =============================================================================
# Main Runner
# =============================================================================

class CensusQualityChecker:
    """Main quality checker orchestrator."""

    def __init__(self, db_path: Path):
        self.db = DatabaseAccess(db_path)

    def check_year(self, year: int) -> QualityReport:
        """Run quality check for a specific year."""
        config = get_year_config(year)
        validator = CensusValidator(config)

        # Get all sources
        records = self.db.get_sources_for_year(year)

        # Validate each source
        all_issues = []
        quality_counts: Counter = Counter()
        media_counts = {"no_media": 0, "single": 0, "multiple": 0}

        for record in records:
            issues = validator.validate(record)
            all_issues.extend(issues)

            # Count quality values
            if record.citation_quality:
                quality_counts[record.citation_quality] += 1

            # Count media
            if record.media_count == 0:
                media_counts["no_media"] += 1
            elif record.media_count == 1:
                media_counts["single"] += 1
            else:
                media_counts["multiple"] += 1
                all_issues.append(Issue(
                    source_id=record.source_id,
                    issue_type="multiple_media",
                    severity=Severity.INFO,
                    category=IssueCategory.MEDIA,
                    message=f"Source has {record.media_count} media attachments",
                    field="media",
                    current_value=record.name[:60],
                ))

        # Find duplicates
        duplicates = self.db.find_duplicates(year)
        for _, name, source_ids in duplicates:
            for sid in source_ids:
                all_issues.append(Issue(
                    source_id=sid,
                    issue_type="duplicate_source",
                    severity=Severity.ERROR,
                    category=IssueCategory.DUPLICATE,
                    message=f"Duplicate source ({len(source_ids)} share same ED/sheet/line)",
                    field="source",
                    current_value=name[:60],
                ))

        # Find unused sources
        unused = self.db.find_unused_sources(year)
        for sid, name in unused:
            all_issues.append(Issue(
                source_id=sid,
                issue_type="unused_source",
                severity=Severity.WARNING,
                category=IssueCategory.QUALITY,
                message="Source has no citations attached",
                field="source",
                current_value=name[:60],
            ))

        # Sort issues by severity then source ID
        all_issues.sort(key=lambda i: (i.severity, i.source_id))

        return QualityReport(
            year=year,
            total_sources=len(records),
            issues=all_issues,
            duplicates=duplicates,
            unused_sources=unused,
            quality_counts=dict(quality_counts),
            media_counts=media_counts,
        )

    def close(self):
        """Close database connection."""
        self.db.close()


# =============================================================================
# CLI Entry Point
# =============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Census Quality Check v2 - Validate Federal Census sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 1930                    Check 1930 census
  %(prog)s 1930 1940 1950          Check multiple years
  %(prog)s --all                   Check all supported years (1880-1950)
  %(prog)s 1930 --format md        Output as Markdown
  %(prog)s 1930 --format json      Output as JSON
        """
    )
    parser.add_argument(
        "years",
        nargs="*",
        type=int,
        help="Census year(s) to check (e.g., 1930 1940)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Check all supported years (1880-1950)"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/Iiams.rmtree"),
        help="Path to RootsMagic database"
    )
    parser.add_argument(
        "--format",
        choices=["text", "md", "json"],
        default="text",
        help="Output format (default: text)"
    )

    args = parser.parse_args()

    # Determine years to check
    if args.all:
        years = list(range(1880, 1960, 10))
    elif args.years:
        years = args.years
    else:
        parser.print_help()
        return 1

    # Validate years
    for year in years:
        if year < 1790 or year > 1950 or year % 10 != 0:
            print(f"Error: Invalid census year: {year}", file=sys.stderr)
            print("Valid years: 1790, 1800, ..., 1950", file=sys.stderr)
            return 1

    # Run checks
    checker = CensusQualityChecker(args.db)

    try:
        for year in years:
            report = checker.check_year(year)

            if args.format == "text":
                print(ReportFormatter.format_text(report))
            elif args.format == "md":
                print(ReportFormatter.format_markdown(report))
            elif args.format == "json":
                print(ReportFormatter.format_json(report))

            if len(years) > 1:
                print("\n")

    finally:
        checker.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
