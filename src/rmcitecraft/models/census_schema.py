"""Data models for census year schemas.

These models define the structure of census form schemas loaded from YAML files,
providing type-safe access to column definitions, form structure, and year-specific
instructions for LLM prompts.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CensusEra(Enum):
    """Census eras with distinct data collection methodologies.

    Each era requires different citation formats and field handling.
    """

    HOUSEHOLD_ONLY = "household_only"  # 1790-1840: Only head of household named
    INDIVIDUAL_NO_ED = "individual_no_ed"  # 1850-1870: Individual names, no ED
    INDIVIDUAL_WITH_ED_SHEET = "individual_with_ed_sheet"  # 1880-1940: ED + sheet
    INDIVIDUAL_WITH_ED_PAGE = "individual_with_ed_page"  # 1950: ED + page (stamp)


@dataclass
class CensusColumn:
    """Definition of a single census form column.

    Attributes:
        name: Field name (e.g., "line_number", "name", "age")
        data_type: Expected type ("string", "integer", "boolean")
        description: Human-readable description for LLM prompt
        column_number: Physical column number on form (1-based, None if N/A)
        required: Whether this field must be extracted
        abbreviations: Common abbreviations used (e.g., {"do": "same as above"})
        valid_values: List of allowed values if constrained (e.g., ["M", "F"])
        is_metadata: Whether this is a metadata field (sheet, ED, page) vs person field
    """

    name: str
    data_type: str
    description: str
    column_number: int | None = None
    required: bool = False
    abbreviations: dict[str, str] | None = None
    valid_values: list[str] | None = None
    is_metadata: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CensusColumn":
        """Create CensusColumn from YAML dictionary."""
        return cls(
            name=data["name"],
            data_type=data["data_type"],
            description=data["description"],
            column_number=data.get("column_number"),
            required=data.get("required", False),
            abbreviations=data.get("abbreviations"),
            valid_values=data.get("valid_values"),
            is_metadata=data.get("is_metadata", False),
        )


@dataclass
class FormStructure:
    """Physical structure of a census form.

    Attributes:
        lines_per_side: Number of lines per sheet side (e.g., 40 for 1940)
        sides: Sheet side identifiers (e.g., ["A", "B"])
        supplemental_lines: Lines with extra questions (e.g., [14, 29] for 1940)
        uses_page: Whether this era uses page numbers
        uses_sheet: Whether this era uses sheet numbers
        uses_stamp: Whether citations use "stamp" (1950 only)
    """

    lines_per_side: int | None = None
    sides: list[str] | None = None
    supplemental_lines: list[int] | None = None
    uses_page: bool = False
    uses_sheet: bool = False
    uses_stamp: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FormStructure":
        """Create FormStructure from YAML dictionary."""
        return cls(
            lines_per_side=data.get("lines_per_side"),
            sides=data.get("sides"),
            supplemental_lines=data.get("supplemental_lines"),
            uses_page=data.get("uses_page", False),
            uses_sheet=data.get("uses_sheet", False),
            uses_stamp=data.get("uses_stamp", False),
        )


@dataclass
class CensusYearSchema:
    """Complete schema definition for a census year.

    Attributes:
        year: Census year (1790, 1800, ..., 1950)
        era: Census era classification
        columns: List of column definitions
        instructions: Year-specific LLM instructions
        form_structure: Physical form structure
        abbreviations: Global abbreviations for this year
        valid_values: Global valid value constraints
        nara_publication: NARA microfilm publication number (e.g., "T623")
    """

    year: int
    era: CensusEra
    columns: list[CensusColumn]
    instructions: str
    form_structure: FormStructure
    abbreviations: dict[str, str] = field(default_factory=dict)
    valid_values: dict[str, list[str]] = field(default_factory=dict)
    nara_publication: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CensusYearSchema":
        """Create CensusYearSchema from YAML dictionary."""
        return cls(
            year=data["year"],
            era=CensusEra(data["era"]),
            columns=[CensusColumn.from_dict(c) for c in data.get("columns", [])],
            instructions=data.get("instructions", ""),
            form_structure=FormStructure.from_dict(data.get("form_structure", {})),
            abbreviations=data.get("abbreviations", {}),
            valid_values=data.get("valid_values", {}),
            nara_publication=data.get("nara_publication"),
        )

    def get_column(self, name: str) -> CensusColumn | None:
        """Get column definition by name."""
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def get_required_columns(self) -> list[CensusColumn]:
        """Get all required person-level columns (excludes metadata columns)."""
        return [col for col in self.columns if col.required and not col.is_metadata]

    def get_column_names(self) -> list[str]:
        """Get list of all column names."""
        return [col.name for col in self.columns]

    def to_json_schema(self) -> dict[str, str]:
        """Convert columns to JSON schema format for LLM prompt."""
        schema = {}
        for col in self.columns:
            type_str = col.data_type
            if col.valid_values:
                type_str = f"{col.data_type} ({'/'.join(col.valid_values)})"
            if col.description:
                type_str = f"{type_str} - {col.description}"
            schema[col.name] = type_str
        return schema
