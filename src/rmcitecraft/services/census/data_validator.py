"""Census data validator for validating extracted data against schemas.

This module validates that extracted census data meets schema requirements
and provides warnings for potential data quality issues.
"""

from typing import Any

from loguru import logger

from rmcitecraft.models.census_schema import CensusEra, CensusYearSchema


class CensusDataValidator:
    """Validates extracted census data against schema requirements.

    Performs validation including:
    - Required field presence
    - Value type checking
    - Valid value constraints
    - Era-appropriate field presence
    """

    def validate(
        self,
        data: dict[str, Any],
        schema: CensusYearSchema,
    ) -> list[str]:
        """Validate data against schema, return warnings.

        Args:
            data: Extracted census data
            schema: Census year schema

        Returns:
            List of warning messages (empty if all valid)
        """
        warnings: list[str] = []

        # Validate metadata
        metadata = data.get("metadata", {})
        warnings.extend(self._validate_metadata(metadata, schema))

        # Validate persons
        persons = data.get("persons", [])
        if not persons and schema.era != CensusEra.HOUSEHOLD_ONLY:
            warnings.append("No persons found in transcription")

        for i, person in enumerate(persons):
            person_warnings = self._validate_person(person, schema, i + 1)
            warnings.extend(person_warnings)

        return warnings

    def _validate_metadata(
        self,
        metadata: dict[str, Any],
        schema: CensusYearSchema,
    ) -> list[str]:
        """Validate metadata fields."""
        warnings: list[str] = []

        # Check enumeration district for eras that require it
        if schema.era in (
            CensusEra.INDIVIDUAL_WITH_ED_SHEET,
            CensusEra.INDIVIDUAL_WITH_ED_PAGE,
        ):
            if not metadata.get("enumeration_district"):
                warnings.append(
                    f"{schema.year} census requires enumeration_district but none found"
                )

        # Check sheet for 1880-1940
        if schema.era == CensusEra.INDIVIDUAL_WITH_ED_SHEET:
            if not metadata.get("sheet"):
                warnings.append(
                    f"{schema.year} census requires sheet number but none found"
                )

        # Check page for 1850-1870 and 1950
        if schema.era in (CensusEra.INDIVIDUAL_NO_ED, CensusEra.INDIVIDUAL_WITH_ED_PAGE):
            if not metadata.get("page_number"):
                warnings.append(
                    f"{schema.year} census requires page_number but none found"
                )

        return warnings

    def _validate_person(
        self,
        person: dict[str, Any],
        schema: CensusYearSchema,
        person_number: int,
    ) -> list[str]:
        """Validate a single person record."""
        warnings: list[str] = []
        prefix = f"Person {person_number}"

        # Check required fields
        required_warnings = self._validate_required_fields(person, schema, prefix)
        warnings.extend(required_warnings)

        # Check field values
        value_warnings = self._validate_field_values(person, schema, prefix)
        warnings.extend(value_warnings)

        # Check era-appropriate fields
        era_warnings = self._validate_era_fields(person, schema, prefix)
        warnings.extend(era_warnings)

        return warnings

    def _validate_required_fields(
        self,
        person: dict[str, Any],
        schema: CensusYearSchema,
        prefix: str,
    ) -> list[str]:
        """Check that all required fields are present."""
        warnings: list[str] = []

        for col in schema.get_required_columns():
            value = person.get(col.name)
            if value is None or value == "":
                warnings.append(f"{prefix}: missing required field '{col.name}'")

        return warnings

    def _validate_field_values(
        self,
        person: dict[str, Any],
        schema: CensusYearSchema,
        prefix: str,
    ) -> list[str]:
        """Validate field values against constraints."""
        warnings: list[str] = []

        for col in schema.columns:
            value = person.get(col.name)
            if value is None:
                continue

            # Check valid values constraint
            if col.valid_values:
                if value not in col.valid_values:
                    warnings.append(
                        f"{prefix}: field '{col.name}' has invalid value '{value}' "
                        f"(expected one of: {col.valid_values})"
                    )

            # Check type constraints
            if col.data_type == "integer":
                if not isinstance(value, int):
                    try:
                        int(value)
                    except (ValueError, TypeError):
                        warnings.append(
                            f"{prefix}: field '{col.name}' should be integer, got '{value}'"
                        )

            # Age sanity check
            if col.name == "age":
                try:
                    age = int(value)
                    if age < 0:
                        warnings.append(f"{prefix}: negative age ({age})")
                    elif age > 120:
                        warnings.append(f"{prefix}: unusually high age ({age})")
                except (ValueError, TypeError):
                    pass

        return warnings

    def _validate_era_fields(
        self,
        person: dict[str, Any],
        schema: CensusYearSchema,
        prefix: str,
    ) -> list[str]:
        """Check that fields are appropriate for the census era."""
        warnings: list[str] = []

        # Check for fields that shouldn't exist in certain eras
        if schema.era == CensusEra.HOUSEHOLD_ONLY:
            # Household-only censuses shouldn't have individual age
            if person.get("age") and person.get("relationship") != "Head":
                warnings.append(
                    f"{prefix}: individual age found in household-only census"
                )

        elif schema.era == CensusEra.INDIVIDUAL_NO_ED:
            # 1850-1870 shouldn't have enumeration district
            if person.get("enumeration_district"):
                warnings.append(
                    f"{prefix}: enumeration_district found in pre-ED census"
                )
            # 1850-1870 shouldn't have relationship (not asked until 1880)
            # Actually 1870 starts to show some relationship data
            if schema.year < 1870 and person.get("relationship"):
                logger.debug(
                    f"{prefix}: relationship found in {schema.year} census "
                    "(not officially asked until 1880)"
                )

        return warnings

    def validate_household(
        self,
        persons: list[dict[str, Any]],
        schema: CensusYearSchema,
    ) -> list[str]:
        """Validate a complete household."""
        warnings: list[str] = []

        if not persons:
            return ["Empty household"]

        # Check that first person is head
        if schema.era != CensusEra.HOUSEHOLD_ONLY:
            first_person = persons[0]
            relationship = first_person.get("relationship", "").lower()
            if relationship and relationship not in ("head", "h"):
                warnings.append(
                    f"First person in household is not head: {relationship}"
                )

        # Check for duplicate line numbers
        line_numbers = [p.get("line_number") for p in persons if p.get("line_number")]
        if len(line_numbers) != len(set(line_numbers)):
            warnings.append("Duplicate line numbers in household")

        # Check line number sequence (should be consecutive)
        if line_numbers:
            sorted_lines = sorted(line_numbers)
            for i in range(1, len(sorted_lines)):
                if sorted_lines[i] != sorted_lines[i - 1] + 1:
                    warnings.append(
                        f"Non-consecutive line numbers: {sorted_lines[i-1]} to {sorted_lines[i]}"
                    )

        return warnings
