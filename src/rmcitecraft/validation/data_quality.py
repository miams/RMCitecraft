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
    REQUIRED_FIELDS = {
        'state': 'State name',
        'county': 'County name',
        'person_name': 'Person name',
        'familysearch_url': 'FamilySearch URL',
        'sheet': 'Sheet/Page number',
        'line': 'Line number',
    }

    # Required fields by census year range
    REQUIRED_BY_YEAR = {
        (1900, 1950): {
            'enumeration_district': 'Enumeration District (ED)',
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
        for field, description in cls.OPTIONAL_FIELDS.items():
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
