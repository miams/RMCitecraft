"""
Data Quality Validation for Census Citations

Validates that extracted census data meets quality standards before
updating the database.
"""
from dataclasses import dataclass
from typing import Any


@dataclass
class ValidationResult:
    """Result of data quality validation."""

    is_valid: bool
    errors: list[str]
    warnings: list[str]
    missing_required: list[str]
    missing_optional: list[str]

    def __bool__(self) -> bool:
        """Allow using as boolean (valid/invalid)."""
        return self.is_valid

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = []

        if self.is_valid:
            lines.append("✅ Data quality validation PASSED")
            if self.warnings:
                lines.append(f"   ⚠️  {len(self.warnings)} warnings")
            if self.missing_optional:
                lines.append(f"   ℹ️  {len(self.missing_optional)} optional fields missing")
        else:
            lines.append("❌ Data quality validation FAILED")
            lines.append(f"   {len(self.errors)} critical errors")
            if self.missing_required:
                lines.append(f"   Missing required fields: {', '.join(self.missing_required)}")

        return "\n".join(lines)


class CensusDataValidator:
    """Validates census citation data quality."""

    # Required fields for all census years
    # Note: 'sheet' is validated separately due to year-specific naming (sheet vs page)
    REQUIRED_FIELDS = {
        'state': 'State name',
        'county': 'County name',
        'person_name': 'Person name',
        'familysearch_url': 'FamilySearch URL',
    }

    # Required fields by census year range
    REQUIRED_BY_YEAR = {
        (1900, 1950): {
            'enumeration_district': 'Enumeration District (ED)',
        },
    }

    # Fields that are required for most years but optional for specific years
    # Key: field name, Value: dict with 'description' and 'optional_years' list
    #
    # IMPORTANT: Census year extraction must be completely independent with no cross-year dependencies.
    # Each census year has different fields available in FamilySearch:
    # - 1850-1870: No enumeration districts, FamilySearch doesn't index line numbers
    # - 1880: First year with enumeration districts, line numbers from detail page
    # - 1900-1940: Enumeration districts, sheet numbers (not page numbers)
    # - 1910: Line numbers not indexed by FamilySearch
    # - 1950: Uses stamp numbers instead of sheet numbers
    YEAR_SPECIFIC_OPTIONAL = {
        'line': {
            'description': 'Line number',
            # Line number is optional for years where FamilySearch doesn't index it
            'optional_years': [1850, 1860, 1870, 1910],
        },
    }

    # Optional but recommended fields
    OPTIONAL_FIELDS = {
        'town_ward': 'Town/Ward/Township',
        'family_number': 'Family number',
        'dwelling_number': 'Dwelling number',
    }

    @classmethod
    def validate(cls, citation_data: dict[str, Any], census_year: int) -> ValidationResult:
        """
        Validate census citation data quality.

        Args:
            citation_data: Extracted citation data from FamilySearch
            census_year: Census year (1790-1950)

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        missing_required = []
        missing_optional = []

        # Check required fields for all years
        for field, description in cls.REQUIRED_FIELDS.items():
            value = citation_data.get(field, '').strip()
            if not value or value == 'Unknown':
                missing_required.append(field)
                errors.append(f"Missing required field: {description} ({field})")

        # Check sheet/page - year-specific field name
        # Pre-1880 censuses use "page", 1880-1940 use "sheet", 1950 uses "stamp"
        if census_year < 1880:
            # 1870 and earlier use page number
            page_value = citation_data.get('page', '').strip()
            if not page_value or page_value == 'Unknown':
                missing_required.append('page')
                errors.append("Missing required field: Page number (page)")
        elif census_year == 1950:
            # 1950 uses stamp number
            stamp_value = citation_data.get('stamp', '').strip()
            sheet_value = citation_data.get('sheet', '').strip()
            if (not stamp_value or stamp_value == 'Unknown') and (not sheet_value or sheet_value == 'Unknown'):
                missing_required.append('stamp')
                errors.append("Missing required field: Stamp number (stamp)")
        else:
            # 1880-1940 use sheet number
            sheet_value = citation_data.get('sheet', '').strip()
            if not sheet_value or sheet_value == 'Unknown':
                missing_required.append('sheet')
                errors.append("Missing required field: Sheet number (sheet)")

        # Check year-specific optional fields (required for most years, optional for specific years)
        for field, config in cls.YEAR_SPECIFIC_OPTIONAL.items():
            value = citation_data.get(field, '').strip()
            if not value or value == 'Unknown':
                if census_year in config['optional_years']:
                    # Optional for this year - just add to optional missing
                    missing_optional.append(field)
                else:
                    # Required for this year
                    missing_required.append(field)
                    errors.append(f"Missing required field: {config['description']} ({field})")

        # Check year-specific required fields
        for (start_year, end_year), required_fields in cls.REQUIRED_BY_YEAR.items():
            if start_year <= census_year <= end_year:
                for field, description in required_fields.items():
                    value = citation_data.get(field, '').strip()
                    if not value:
                        # ED is critical for 1900-1950
                        if field == 'enumeration_district':
                            missing_required.append(field)
                            errors.append(f"Missing required field for {census_year}: {description} ({field})")
                        else:
                            missing_optional.append(field)
                            warnings.append(f"Missing recommended field: {description} ({field})")

        # Check optional fields
        for field in cls.OPTIONAL_FIELDS:
            if field not in missing_required:  # Don't double-count
                value = citation_data.get(field, '').strip()
                if not value:
                    missing_optional.append(field)

        # Validate data quality (not just presence)
        cls._validate_data_quality(citation_data, census_year, warnings)

        # Determine overall validity
        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            missing_required=missing_required,
            missing_optional=missing_optional
        )

    @classmethod
    def _validate_data_quality(cls, data: dict[str, Any], year: int, warnings: list[str]) -> None:
        """Validate quality of extracted data (not just presence)."""

        # Check state name length (should be reasonable)
        state = data.get('state', '')
        if state and len(state) < 2:
            warnings.append(f"State name seems invalid: '{state}'")

        # Check county name length
        county = data.get('county', '')
        if county and len(county) < 3:
            warnings.append(f"County name seems invalid: '{county}'")

        # Check person name
        person_name = data.get('person_name', '')
        if person_name and len(person_name) < 2:
            warnings.append(f"Person name seems invalid: '{person_name}'")

        # Check year is reasonable
        if not (1790 <= year <= 1950) or year % 10 != 0:
            warnings.append(f"Census year seems invalid: {year} (should be 1790-1950, multiples of 10)")

        # Check FamilySearch URL format
        url = data.get('familysearch_url', '')
        if url and 'familysearch.org/ark:' not in url:
            warnings.append(f"FamilySearch URL format seems invalid: {url}")


def validate_before_update(
    citation_data: dict[str, Any],
    census_year: int,
    strict: bool = True
) -> ValidationResult:
    """
    Convenience function to validate data before database update.

    Args:
        citation_data: Extracted citation data
        census_year: Census year
        strict: If True, fail on any errors. If False, allow warnings.

    Returns:
        ValidationResult

    Example:
        >>> result = validate_before_update(citation_data, 1940)
        >>> if not result:
        ...     print(result.summary())
        ...     raise ValueError("Data quality check failed")
    """
    return CensusDataValidator.validate(citation_data, census_year)


class FormattedCitationValidator:
    """
    Validates formatted citation text (footnote, short_footnote, bibliography)
    to ensure essential elements are present.

    Used to determine if a citation has been properly processed or still needs
    processing in batch workflows.
    """

    @classmethod
    def validate_footnote(cls, footnote: str | None, census_year: int) -> bool:
        """
        Validate that a footnote contains essential elements.

        Args:
            footnote: The formatted footnote text
            census_year: The census year (1790-1950)

        Returns:
            True if footnote contains all essential elements, False otherwise
        """
        if not footnote or not footnote.strip():
            return False

        text = footnote.lower()

        # Reject old FamilySearch citation format
        # Old format starts with: "United States Census, YYYY," database with images
        # Proper Evidence Explained format starts with: YYYY U.S. census,
        if 'database with images' in text:
            return False
        if text.startswith('"united states census'):
            return False

        # Must contain census year and "census" reference
        if str(census_year) not in footnote:
            return False

        if 'census' not in text:
            return False

        # Must contain FamilySearch reference (URL or FamilySearch mention)
        if 'familysearch' not in text:
            return False

        # Must contain sheet/page reference (1950 census uses "stamp" instead)
        if 'sheet' not in text and 'page' not in text and 'stamp' not in text:
            return False

        # For 1900-1950 censuses, must contain ED reference
        if 1900 <= census_year <= 1950:
            if not cls._has_enumeration_district_reference(text):
                return False

        return True

    @classmethod
    def _has_enumeration_district_reference(cls, text: str) -> bool:
        """
        Check if text contains a valid enumeration district reference.

        Looks for patterns like:
        - "enumeration district"
        - "e.d. 95" or "e.d.95"
        - "E.D. 95" or "E.D.95"
        - "(ed) 95"
        - ", ed 95,"
        - "district (ed)"

        Args:
            text: Lowercase text to search

        Returns:
            True if a valid ED reference is found
        """
        import re

        # Check for full phrase
        if 'enumeration district' in text:
            return True

        # Check for E.D. abbreviation (with periods)
        if 'e.d.' in text:
            return True

        # Check for ED followed by a number (standalone, not part of another word)
        # Patterns: ", ed 95" or "(ed) 95" or "ed 95," etc.
        # Must have a word boundary before "ed" to avoid matching "united", "accessed", etc.
        ed_pattern = r'(?:^|[,\(\s])ed\s*\d'
        if re.search(ed_pattern, text):
            return True

        # Check for "district (ed)" pattern
        if 'district (ed)' in text:
            return True

        return False

    @classmethod
    def validate_short_footnote(cls, short_footnote: str | None, census_year: int) -> bool:
        """
        Validate that a short footnote contains essential elements.

        Args:
            short_footnote: The formatted short footnote text
            census_year: The census year (1790-1950)

        Returns:
            True if short footnote contains all essential elements, False otherwise
        """
        if not short_footnote or not short_footnote.strip():
            return False

        text = short_footnote.lower()

        # Reject old FamilySearch citation format
        if 'database with images' in text:
            return False
        if text.startswith('"united states census'):
            return False

        # Must contain census year
        if str(census_year) not in short_footnote:
            return False

        # Must contain "census" or "pop. sch." abbreviation
        if 'census' not in text and 'pop. sch.' not in text:
            return False

        # Must contain sheet/page/stamp reference depending on census year
        # Pre-1880: page, 1880-1940: sheet, 1950: stamp
        if census_year < 1880:
            if 'page' not in text:
                return False
        elif census_year == 1950:
            if 'stamp' not in text and 'sheet' not in text:
                return False
        else:
            if 'sheet' not in text:
                return False

        return True

    @classmethod
    def validate_bibliography(cls, bibliography: str | None, census_year: int) -> bool:
        """
        Validate that a bibliography contains essential elements.

        Args:
            bibliography: The formatted bibliography text
            census_year: The census year (1790-1950)

        Returns:
            True if bibliography contains all essential elements, False otherwise
        """
        if not bibliography or not bibliography.strip():
            return False

        text = bibliography.lower()

        # Reject old FamilySearch citation format
        if 'database with images' in text:
            return False
        if text.startswith('"united states census'):
            return False

        # Must contain census year
        if str(census_year) not in bibliography:
            return False

        # Must contain "Census" reference
        if 'census' not in text:
            return False

        # Must contain FamilySearch reference
        if 'familysearch' not in text:
            return False

        return True

    @classmethod
    def is_citation_processed(
        cls,
        footnote: str | None,
        short_footnote: str | None,
        bibliography: str | None,
        census_year: int
    ) -> bool:
        """
        Determine if a citation has been properly processed.

        A citation is considered processed if:
        1. Footnote != short_footnote (they're different after processing)
        2. All three citation forms pass validation

        Args:
            footnote: The formatted footnote text
            short_footnote: The formatted short footnote text
            bibliography: The formatted bibliography text
            census_year: The census year (1790-1950)

        Returns:
            True if citation appears to be properly processed, False otherwise
        """
        # Criterion 5: If footnote == short_footnote, it hasn't been processed
        # (RootsMagic defaults both to the same initial value)
        if footnote and short_footnote:
            # Normalize for comparison:
            # - Strip leading/trailing whitespace
            # - Replace non-breaking spaces (char 160) with regular spaces
            # - Collapse multiple spaces into single space
            import re
            fn_normalized = re.sub(r'\s+', ' ', footnote.replace('\xa0', ' ')).strip()
            sf_normalized = re.sub(r'\s+', ' ', short_footnote.replace('\xa0', ' ')).strip()
            if fn_normalized == sf_normalized:
                return False

        # Criterion 6: All three citations must pass validation
        footnote_valid = cls.validate_footnote(footnote, census_year)
        short_valid = cls.validate_short_footnote(short_footnote, census_year)
        bib_valid = cls.validate_bibliography(bibliography, census_year)

        # All three must be valid for the citation to be considered processed
        return footnote_valid and short_valid and bib_valid


def is_citation_needs_processing(
    footnote: str | None,
    short_footnote: str | None,
    bibliography: str | None,
    census_year: int
) -> bool:
    """
    Convenience function to check if a citation needs processing.

    Returns True if the citation should be included in the batch queue
    (i.e., it needs processing). Returns False if it's already properly processed.

    Args:
        footnote: The formatted footnote text
        short_footnote: The formatted short footnote text
        bibliography: The formatted bibliography text
        census_year: The census year (1790-1950)

    Returns:
        True if citation needs processing, False if already processed
    """
    # If already processed, it doesn't need processing
    is_processed = FormattedCitationValidator.is_citation_processed(
        footnote, short_footnote, bibliography, census_year
    )
    return not is_processed
