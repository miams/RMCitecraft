"""Component extraction for census citation fields.

Extracts structured data from source names, footnotes, short footnotes,
and bibliographies using regex patterns.
"""

import re

from .models import CensusComponents


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
        if (match := re.search(cls.PATTERNS["source_ed_bracket"], name)) or (match := re.search(cls.PATTERNS["source_ed_citing"], name)):
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
