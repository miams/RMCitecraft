"""Year-specific handler for census extraction logic.

This module provides the single source of truth for all year-specific
census extraction behavior. It wraps CensusSchemaRegistry and adds
parsing logic for FamilySearch-specific field formats.

All year-specific conditionals for extraction should live here.
"""

import re
from dataclasses import dataclass
from typing import ClassVar

from loguru import logger

from rmcitecraft.models.census_schema import CensusEra
from rmcitecraft.services.census.schema_registry import CensusSchemaRegistry


@dataclass(frozen=True)
class ExtractionFlags:
    """Flags indicating what data to extract for a census year.

    These flags are derived from the census schema and era, determining
    which fields are meaningful for extraction.
    """

    uses_enumeration_district: bool
    uses_sheet: bool
    uses_page: bool
    uses_stamp: bool
    uses_dwelling_number: bool
    uses_family_number: bool
    uses_line_number: bool
    has_individual_records: bool

    def __str__(self) -> str:
        flags = []
        if self.uses_enumeration_district:
            flags.append("ED")
        if self.uses_sheet:
            flags.append("sheet")
        if self.uses_page:
            flags.append("page")
        if self.uses_stamp:
            flags.append("stamp")
        if self.uses_dwelling_number:
            flags.append("dwelling")
        if self.uses_family_number:
            flags.append("family")
        if self.uses_line_number:
            flags.append("line")
        return f"ExtractionFlags({', '.join(flags)})"


class YearSpecificHandler:
    """Handler for census year-specific extraction logic.

    This class is the single source of truth for:
    - Which fields to extract for each census year
    - How to parse year-specific field formats
    - Era classification and capabilities

    Uses CensusSchemaRegistry for schema data and adds FamilySearch-specific
    parsing logic on top.

    Example:
        handler = YearSpecificHandler(1910)
        flags = handler.get_extraction_flags()
        ed = handler.parse_enumeration_district("ED 340")  # Returns "340"
        sheet = handler.parse_sheet("5", "A")  # Returns "5A"
    """

    # Cache for ExtractionFlags by year
    _flags_cache: ClassVar[dict[int, ExtractionFlags]] = {}

    def __init__(self, census_year: int):
        """Initialize handler for a specific census year.

        Args:
            census_year: The census year (1790-1950, excluding 1890)

        Raises:
            ValueError: If census_year is not valid
        """
        if not CensusSchemaRegistry.is_valid_year(census_year):
            raise ValueError(
                f"Invalid census year: {census_year}. "
                f"Valid years: {CensusSchemaRegistry.list_years()}"
            )

        self._year = census_year
        self._era = CensusSchemaRegistry.get_era(census_year)
        self._schema = CensusSchemaRegistry.get_schema(census_year)

    @property
    def year(self) -> int:
        """The census year this handler is configured for."""
        return self._year

    @property
    def era(self) -> CensusEra:
        """The census era for this year."""
        return self._era

    def get_extraction_flags(self) -> ExtractionFlags:
        """Get extraction flags for this census year.

        Returns cached flags if available.

        Returns:
            ExtractionFlags indicating what to extract
        """
        if self._year not in self._flags_cache:
            self._flags_cache[self._year] = self._compute_extraction_flags()

        return self._flags_cache[self._year]

    def _compute_extraction_flags(self) -> ExtractionFlags:
        """Compute extraction flags based on era and schema.

        Returns:
            ExtractionFlags for this census year
        """
        era = self._era

        # Individual records exist from 1850 onward
        has_individual = era != CensusEra.HOUSEHOLD_ONLY

        # Enumeration districts introduced in 1880
        uses_ed = era in (
            CensusEra.INDIVIDUAL_WITH_ED_SHEET,
            CensusEra.INDIVIDUAL_WITH_ED_PAGE,
        )

        # Sheet vs page vs stamp depends on year
        # 1880: uses stamped page numbers, not sheets
        # 1890-1940: uses sheet numbers with letter suffix (e.g., 5A, 12B)
        # 1950: uses stamp numbers
        uses_sheet = self._year >= 1890 and self._year < 1950
        uses_page = self._year <= 1880 or self._year == 1950
        uses_stamp = self._year == 1950 or self._year == 1880  # 1880 uses "(stamped)"

        # Dwelling and family numbers exist for individual-era censuses
        uses_dwelling = has_individual
        uses_family = has_individual

        # Line numbers vary by year/era
        # Note: FamilySearch doesn't always index line numbers
        uses_line = has_individual

        return ExtractionFlags(
            uses_enumeration_district=uses_ed,
            uses_sheet=uses_sheet,
            uses_page=uses_page,
            uses_stamp=uses_stamp,
            uses_dwelling_number=uses_dwelling,
            uses_family_number=uses_family,
            uses_line_number=uses_line,
            has_individual_records=has_individual,
        )

    def parse_enumeration_district(self, raw_value: str | None) -> str | None:
        """Parse enumeration district from FamilySearch format.

        Handles year-specific formats:
        - 1910: "ED 340" -> "340"
        - 1940: "23-45" (supervisor district-ED) -> "23-45" (kept as-is)
        - Most years: numeric value returned as-is

        Args:
            raw_value: Raw ED value from FamilySearch

        Returns:
            Parsed ED value or None if not parseable
        """
        if not raw_value:
            return None

        raw_str = str(raw_value).strip()
        if not raw_str:
            return None

        # 1910: FamilySearch uses "ED 340" format
        if self._year == 1910:
            ed_match = re.search(r"ED\s*(\d+)", raw_str, re.IGNORECASE)
            if ed_match:
                parsed = ed_match.group(1)
                logger.debug(f"1910 ED parsed: '{raw_str}' -> '{parsed}'")
                return parsed

        # 1940: FamilySearch provides ED number followed by description in one field
        # e.g., "103-2336 Chicago City Ward 37 (Tract 338 - part), Apartments at 5952-62 W Fulton"
        # We only want the hyphenated number: "103-2336"
        if self._year == 1940:
            # Extract just the ED number (format: digits-digits at start)
            ed_match = re.match(r"^(\d+-\d+)", raw_str)
            if ed_match:
                parsed = ed_match.group(1)
                logger.debug(f"1940 ED parsed: '{raw_str[:50]}...' -> '{parsed}'")
                return parsed
            # Fallback: return as-is if no match
            return raw_str

        # Default: return cleaned value
        # Try to extract just the number if prefixed
        ed_match = re.search(r"E\.?D\.?\s*(\d+)", raw_str, re.IGNORECASE)
        if ed_match:
            return ed_match.group(1)

        # Return as-is if it looks like a number
        if raw_str.replace("-", "").isdigit():
            return raw_str

        return raw_str

    def parse_sheet(
        self,
        sheet_number: str | None,
        sheet_letter: str | None = None,
    ) -> str | None:
        """Parse sheet number, combining with letter if needed.

        Handles year-specific formats:
        - 1910: Combines "5" + "A" -> "5A"
        - Most years: Returns sheet_number as-is

        Args:
            sheet_number: The sheet number
            sheet_letter: Optional sheet letter (A/B)

        Returns:
            Combined sheet value or None
        """
        if not sheet_number:
            return None

        sheet_str = str(sheet_number).strip()
        if not sheet_str:
            return None

        # 1910 and some other years: combine number and letter
        if sheet_letter:
            letter = str(sheet_letter).strip().upper()
            # Only add letter if not already present
            if letter and not sheet_str[-1].isalpha():
                combined = f"{sheet_str}{letter}"
                logger.debug(f"Sheet combined: '{sheet_str}' + '{letter}' -> '{combined}'")
                return combined

        return sheet_str

    def parse_household_id(self, raw_value: str | None) -> tuple[str | None, str | None]:
        """Parse household ID into dwelling and family numbers.

        Year-specific behavior (MUST be independent per year - no cross-year dependencies):
        - 1850-1870: HOUSEHOLD_ID is from column 2 = family_number
                     (FamilySearch doesn't extract line numbers for these years)
        - 1880: Ignore Source Household Id - not used for dwelling/family number
        - 1900, 1910: HOUSEHOLD_ID is the family number
        - Other years: Returned as dwelling_number

        Args:
            raw_value: Raw household ID from FamilySearch

        Returns:
            Tuple of (dwelling_number, family_number)
        """
        if not raw_value:
            return (None, None)

        value = str(raw_value).strip()
        if not value:
            return (None, None)

        # 1850, 1860, 1870: FamilySearch's HOUSEHOLD_ID is from column 2 = family_number
        # Per census schemas: Col 1 = dwelling_number, Col 2 = family_number
        # FamilySearch indexes column 2 as HOUSEHOLD_ID
        # Note: FamilySearch doesn't extract line numbers for these years
        if self._year in (1850, 1860, 1870):
            logger.debug(f"{self._year}: household_id '{value}' mapped to family_number (column 2)")
            return (None, value)

        # 1880: Ignore Source Household Id - not used for dwelling/family number
        if self._year == 1880:
            logger.debug(f"1880: household_id '{value}' ignored (Source Household Id not used)")
            return (None, None)

        # 1900: FamilySearch's Household Identifier is the family number
        if self._year == 1900:
            logger.debug(f"1900: household_id '{value}' mapped to family_number")
            return (None, value)

        # 1910: FamilySearch's Household Identifier is the family number
        if self._year == 1910:
            logger.debug(f"1910: household_id '{value}' mapped to family_number")
            return (None, value)

        # Default: treat as dwelling number
        return (value, None)

    def uses_enumeration_district(self) -> bool:
        """Whether this census year uses enumeration districts."""
        return self.get_extraction_flags().uses_enumeration_district

    def uses_sheet(self) -> bool:
        """Whether this census year uses sheet numbers."""
        return self.get_extraction_flags().uses_sheet

    def uses_stamp(self) -> bool:
        """Whether this census year uses stamp numbers (1950 only)."""
        return self.get_extraction_flags().uses_stamp

    def has_individual_records(self) -> bool:
        """Whether this census year has individual person records."""
        return self.get_extraction_flags().has_individual_records

    @classmethod
    def for_year(cls, census_year: int) -> "YearSpecificHandler":
        """Factory method to create handler for a year.

        Convenience method equivalent to YearSpecificHandler(census_year).

        Args:
            census_year: The census year

        Returns:
            YearSpecificHandler configured for the year
        """
        return cls(census_year)

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the flags cache (mainly for testing)."""
        cls._flags_cache.clear()
