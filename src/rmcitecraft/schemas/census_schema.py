"""
Census Schema Loader

Provides programmatic access to census schema definitions stored in YAML files.
This is the single source of truth for census column definitions, valid values,
form structure, and historical context.

Usage:
    from rmcitecraft.schemas.census_schema import (
        load_schema,
        get_valid_fields,
        get_field_info,
        validate_field_value,
        get_form_structure,
        get_era_capabilities,
    )

    # Load full schema
    schema = load_schema(1880)

    # Get valid fields for a year
    fields = get_valid_fields(1790)
    # ['head_of_household', 'free_white_males_16_plus', ...]

    # Check if a field exists for a year
    if has_field(1880, 'relationship'):
        print("1880 was first to ask relationship!")

    # Validate a value
    if not validate_field_value(1850, 'sex', 'X'):
        print("Invalid sex value")
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# Schema directory location
SCHEMA_DIR = Path(__file__).parent / "census"

# Supported census years
SUPPORTED_YEARS = [1790, 1800, 1810, 1820, 1830, 1840, 1850, 1860, 1870, 1880, 1900, 1910, 1920, 1930, 1940, 1950]

# Era definitions
ERAS = {
    "household_only": {
        "years": [1790, 1800, 1810, 1820, 1830, 1840],
        "description": "Only head of household named; others counted in tally columns",
        "has_individual_names": False,
    },
    "individual_no_ed": {
        "years": [1850, 1860, 1870],
        "description": "All individuals named; no enumeration districts",
        "has_individual_names": True,
    },
    "individual_with_ed": {
        "years": [1880, 1900, 1910, 1920, 1930, 1940, 1950],
        "description": "All individuals named; enumeration districts used",
        "has_individual_names": True,
    },
}


@dataclass
class ColumnInfo:
    """Information about a census column."""
    name: str
    data_type: str
    description: str
    required: bool = False
    column_number: int | None = None
    valid_values: list[str] | None = None
    is_metadata: bool = False
    familysearch_label: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "ColumnInfo":
        return cls(
            name=data.get("name", ""),
            data_type=data.get("data_type", "string"),
            description=data.get("description", ""),
            required=data.get("required", False),
            column_number=data.get("column_number"),
            valid_values=data.get("valid_values"),
            is_metadata=data.get("is_metadata", False),
            familysearch_label=data.get("familysearch_label"),
        )


@dataclass
class FormStructure:
    """Census form physical structure."""
    lines_per_side: int
    sides: list[str] | None  # e.g., ["A", "B"] for sheets
    uses_page: bool
    uses_sheet: bool
    uses_stamp: bool
    supplemental_lines: int | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "FormStructure":
        return cls(
            lines_per_side=data.get("lines_per_side", 0),
            sides=data.get("sides"),
            uses_page=data.get("uses_page", False),
            uses_sheet=data.get("uses_sheet", False),
            uses_stamp=data.get("uses_stamp", False),
            supplemental_lines=data.get("supplemental_lines"),
        )

    @property
    def location_type(self) -> str:
        """Return the location identifier type for this form."""
        if self.uses_stamp:
            return "stamp"
        elif self.uses_sheet:
            return "sheet"
        else:
            return "page"


@dataclass
class CensusSchema:
    """Complete schema for a census year."""
    year: int
    era: str
    nara_publication: str
    form_structure: FormStructure
    columns: list[ColumnInfo]
    abbreviations: dict[str, str]
    valid_values: dict[str, list[str]]
    instructions: str

    @classmethod
    def from_dict(cls, data: dict) -> "CensusSchema":
        return cls(
            year=data.get("year", 0),
            era=data.get("era", ""),
            nara_publication=data.get("nara_publication", ""),
            form_structure=FormStructure.from_dict(data.get("form_structure", {})),
            columns=[ColumnInfo.from_dict(c) for c in data.get("columns", [])],
            abbreviations=data.get("abbreviations", {}),
            valid_values=data.get("valid_values", {}),
            instructions=data.get("instructions", ""),
        )

    def get_column(self, name: str) -> ColumnInfo | None:
        """Get column info by name."""
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def get_field_names(self) -> list[str]:
        """Get list of all field names."""
        return [col.name for col in self.columns]

    def get_person_fields(self) -> list[ColumnInfo]:
        """Get columns that apply to persons (not metadata)."""
        return [col for col in self.columns if not col.is_metadata]

    def get_required_fields(self) -> list[str]:
        """Get list of required field names."""
        return [col.name for col in self.columns if col.required]


# =============================================================================
# Core Loading Functions
# =============================================================================

@lru_cache(maxsize=20)
def load_schema(year: int) -> CensusSchema:
    """
    Load census schema for a year.

    Args:
        year: Census year (1790, 1800, ..., 1950)

    Returns:
        CensusSchema object with full schema information

    Raises:
        ValueError: If no schema exists for the year
        FileNotFoundError: If YAML file is missing
    """
    if year not in SUPPORTED_YEARS:
        raise ValueError(f"No schema for year {year}. Supported: {SUPPORTED_YEARS}")

    path = SCHEMA_DIR / f"{year}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    return CensusSchema.from_dict(data)


@lru_cache(maxsize=20)
def load_schema_raw(year: int) -> dict:
    """
    Load raw YAML schema as dictionary.

    Useful when you need access to the original structure.
    """
    if year not in SUPPORTED_YEARS:
        raise ValueError(f"No schema for year {year}")

    path = SCHEMA_DIR / f"{year}.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def get_supported_years() -> list[int]:
    """Return list of supported census years."""
    return SUPPORTED_YEARS.copy()


# =============================================================================
# Field Information Functions
# =============================================================================

def get_valid_fields(year: int) -> list[str]:
    """
    Get list of valid field names for a census year.

    Args:
        year: Census year

    Returns:
        List of field names valid for this census
    """
    schema = load_schema(year)
    return schema.get_field_names()


def get_field_info(year: int, field_name: str) -> ColumnInfo | None:
    """
    Get detailed information about a field.

    Args:
        year: Census year
        field_name: Name of the field

    Returns:
        ColumnInfo object or None if field doesn't exist
    """
    schema = load_schema(year)
    return schema.get_column(field_name)


def has_field(year: int, field_name: str) -> bool:
    """
    Check if a field exists for a census year.

    Args:
        year: Census year
        field_name: Name of the field

    Returns:
        True if field exists for this year
    """
    return field_name in get_valid_fields(year)


def get_field_description(year: int, field_name: str) -> str | None:
    """
    Get the description of a field.

    Args:
        year: Census year
        field_name: Name of the field

    Returns:
        Description string or None
    """
    info = get_field_info(year, field_name)
    return info.description if info else None


# =============================================================================
# Validation Functions
# =============================================================================

def validate_field_name(year: int, field_name: str) -> bool:
    """
    Check if a field name is valid for a census year.

    Args:
        year: Census year
        field_name: Field name to validate

    Returns:
        True if valid, False otherwise
    """
    return has_field(year, field_name)


def validate_field_value(year: int, field_name: str, value: Any) -> bool:
    """
    Validate a field value against the schema.

    Args:
        year: Census year
        field_name: Field name
        value: Value to validate

    Returns:
        True if valid, False if invalid or field doesn't exist
    """
    info = get_field_info(year, field_name)
    if not info:
        return False

    # Check valid_values constraint
    if info.valid_values:
        return value in info.valid_values

    # Check data type
    if info.data_type == "integer":
        try:
            int(value)
            return True
        except (ValueError, TypeError):
            return value is None or value == ""

    return True


def get_valid_values(year: int, field_name: str) -> list[str] | None:
    """
    Get the list of valid values for a field.

    Args:
        year: Census year
        field_name: Field name

    Returns:
        List of valid values, or None if any value is allowed
    """
    info = get_field_info(year, field_name)
    return info.valid_values if info else None


def validate_census_record(year: int, fields: dict[str, Any]) -> list[str]:
    """
    Validate a complete census record.

    Args:
        year: Census year
        fields: Dictionary of field_name -> value

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    schema = load_schema(year)
    valid_field_names = set(schema.get_field_names())

    # Check for unknown fields
    for field_name in fields.keys():
        if field_name not in valid_field_names:
            errors.append(f"Unknown field '{field_name}' for {year} census")

    # Check required fields
    for required_field in schema.get_required_fields():
        if required_field not in fields or not fields[required_field]:
            errors.append(f"Missing required field '{required_field}'")

    # Validate values
    for field_name, value in fields.items():
        if field_name in valid_field_names and value:
            if not validate_field_value(year, field_name, value):
                valid = get_valid_values(year, field_name)
                errors.append(f"Invalid value '{value}' for '{field_name}' (valid: {valid})")

    return errors


# =============================================================================
# Form Structure Functions
# =============================================================================

def get_form_structure(year: int) -> FormStructure:
    """
    Get the physical form structure for a census year.

    Args:
        year: Census year

    Returns:
        FormStructure object with form details
    """
    schema = load_schema(year)
    return schema.form_structure


def get_location_type(year: int) -> str:
    """
    Get the location identifier type (page, sheet, or stamp).

    Args:
        year: Census year

    Returns:
        'page', 'sheet', or 'stamp'
    """
    form = get_form_structure(year)
    return form.location_type


def get_lines_per_page(year: int) -> int:
    """
    Get the number of lines per page/sheet side.

    Args:
        year: Census year

    Returns:
        Number of lines
    """
    form = get_form_structure(year)
    return form.lines_per_side


# =============================================================================
# Era and Capability Functions
# =============================================================================

def get_era(year: int) -> str:
    """
    Get the census era identifier.

    Args:
        year: Census year

    Returns:
        Era string (e.g., 'household_only', 'individual_with_ed')
    """
    schema = load_schema(year)
    return schema.era


def get_era_info(year: int) -> dict:
    """
    Get information about the census era.

    Args:
        year: Census year

    Returns:
        Dictionary with era description and capabilities
    """
    era = get_era(year)
    for era_name, era_data in ERAS.items():
        if year in era_data["years"]:
            return {
                "era": era_name,
                "description": era_data["description"],
                "has_individual_names": era_data["has_individual_names"],
            }
    return {"era": era, "description": "", "has_individual_names": True}


def has_individual_names(year: int) -> bool:
    """
    Check if census lists individual names (vs. just head of household).

    Args:
        year: Census year

    Returns:
        True if individuals are named (1850+)
    """
    return year >= 1850


def has_enumeration_districts(year: int) -> bool:
    """
    Check if census uses enumeration districts.

    Args:
        year: Census year

    Returns:
        True if EDs are used (1880+)
    """
    return year >= 1880


def has_relationship_column(year: int) -> bool:
    """
    Check if census asks for relationship to head.

    Args:
        year: Census year

    Returns:
        True if relationship is asked (1880+)
    """
    return has_field(year, "relationship")


def has_parents_birthplace(year: int) -> bool:
    """
    Check if census asks for parents' birthplaces.

    Args:
        year: Census year

    Returns:
        True if parents' birthplaces are asked (1880+)
    """
    return has_field(year, "father_birthplace") or has_field(year, "birthplace_father")


def get_era_capabilities(year: int) -> dict[str, bool]:
    """
    Get a summary of what data is available for a census year.

    Args:
        year: Census year

    Returns:
        Dictionary of capability -> boolean
    """
    return {
        "individual_names": has_individual_names(year),
        "enumeration_districts": has_enumeration_districts(year),
        "relationship_to_head": has_relationship_column(year),
        "parents_birthplace": has_parents_birthplace(year),
        "occupation": has_field(year, "occupation"),
        "birthplace": has_field(year, "birthplace"),
        "marital_status": has_field(year, "marital_status"),
        "real_estate_value": has_field(year, "value_real_estate"),
        "personal_estate_value": has_field(year, "value_personal_estate"),
    }


# =============================================================================
# Research Helpers
# =============================================================================

def get_instructions(year: int) -> str:
    """
    Get research instructions/tips for a census year.

    Args:
        year: Census year

    Returns:
        Instructions text from schema
    """
    schema = load_schema(year)
    return schema.instructions


def get_abbreviations(year: int) -> dict[str, str]:
    """
    Get common abbreviations used in a census.

    Args:
        year: Census year

    Returns:
        Dictionary of abbreviation -> meaning
    """
    schema = load_schema(year)
    return schema.abbreviations


def get_nara_publication(year: int) -> str:
    """
    Get the NARA microfilm publication number.

    Args:
        year: Census year

    Returns:
        NARA publication ID (e.g., 'M637', 'T9')
    """
    schema = load_schema(year)
    return schema.nara_publication


# =============================================================================
# Field Normalization
# =============================================================================

# Common field name variations to normalize
FIELD_ALIASES = {
    # FamilySearch variations
    "birthplace_father": "father_birthplace",
    "birthplace_mother": "mother_birthplace",
    "birth_place": "birthplace",
    "birth place": "birthplace",

    # 90-60 Workbook variations
    "fwm_16_plus": "free_white_males_16_plus",
    "fwm_under_16": "free_white_males_under_16",
    "fwf": "free_white_females",

    # Common typos/variations
    "slavs": "slaves",
    "ocupation": "occupation",
    "occup": "occupation",
}


def normalize_field_name(field_name: str) -> str:
    """
    Normalize a field name to the canonical form.

    Args:
        field_name: Raw field name

    Returns:
        Normalized field name
    """
    # Lowercase and convert spaces to underscores
    normalized = field_name.lower().strip().replace(" ", "_").replace("-", "_")

    # Check aliases
    if normalized in FIELD_ALIASES:
        return FIELD_ALIASES[normalized]

    return normalized


def normalize_field_name_for_year(year: int, field_name: str) -> str | None:
    """
    Normalize a field name and verify it's valid for the year.

    Args:
        year: Census year
        field_name: Raw field name

    Returns:
        Normalized field name if valid, None if not valid for year
    """
    normalized = normalize_field_name(field_name)

    if has_field(year, normalized):
        return normalized

    # Try to find a close match in the schema
    valid_fields = get_valid_fields(year)
    for valid in valid_fields:
        if normalized in valid or valid in normalized:
            return valid

    return None


# =============================================================================
# Citation Helpers
# =============================================================================

def get_citation_location_format(year: int) -> str:
    """
    Get the location format string for citations.

    Args:
        year: Census year

    Returns:
        Format string like 'p. {page}' or 'ED {ed}, sheet {sheet}'
    """
    form = get_form_structure(year)

    if year < 1880:
        return "p. {page}"
    elif form.uses_stamp:
        return "enumeration district (ED) {ed}, stamp {stamp}"
    else:
        return "enumeration district (ED) {ed}, sheet {sheet}"


def format_census_location(year: int, **kwargs) -> str:
    """
    Format the location portion of a census citation.

    Args:
        year: Census year
        **kwargs: Location fields (page, sheet, stamp, ed, etc.)

    Returns:
        Formatted location string
    """
    form = get_form_structure(year)

    parts = []

    # Add ED if applicable
    if year >= 1880 and kwargs.get("ed"):
        parts.append(f"enumeration district (ED) {kwargs['ed']}")

    # Add page/sheet/stamp
    if form.uses_stamp and kwargs.get("stamp"):
        parts.append(f"stamp {kwargs['stamp']}")
    elif form.uses_sheet and kwargs.get("sheet"):
        sheet = kwargs["sheet"]
        if kwargs.get("sheet_letter"):
            sheet = f"{sheet}{kwargs['sheet_letter']}"
        parts.append(f"sheet {sheet}")
    elif kwargs.get("page"):
        parts.append(f"p. {kwargs['page']}")

    # Add line if provided
    if kwargs.get("line"):
        parts.append(f"line {kwargs['line']}")

    return ", ".join(parts)


# =============================================================================
# Comparison Functions
# =============================================================================

def compare_schemas(year1: int, year2: int) -> dict:
    """
    Compare two census schemas to show differences.

    Args:
        year1: First census year
        year2: Second census year

    Returns:
        Dictionary with added, removed, and common fields
    """
    fields1 = set(get_valid_fields(year1))
    fields2 = set(get_valid_fields(year2))

    return {
        "added": sorted(fields2 - fields1),
        "removed": sorted(fields1 - fields2),
        "common": sorted(fields1 & fields2),
    }


def get_field_first_year(field_name: str) -> int | None:
    """
    Find the first census year that included a field.

    Args:
        field_name: Field name to search for

    Returns:
        First year the field appears, or None if never
    """
    normalized = normalize_field_name(field_name)

    for year in SUPPORTED_YEARS:
        if has_field(year, normalized):
            return year

    return None


# =============================================================================
# Bulk Operations
# =============================================================================

def get_all_field_names() -> set[str]:
    """Get all unique field names across all census years."""
    all_fields = set()
    for year in SUPPORTED_YEARS:
        all_fields.update(get_valid_fields(year))
    return all_fields


def get_field_availability() -> dict[str, list[int]]:
    """
    Get which years each field is available.

    Returns:
        Dictionary of field_name -> list of years
    """
    availability = {}

    for year in SUPPORTED_YEARS:
        for field in get_valid_fields(year):
            if field not in availability:
                availability[field] = []
            availability[field].append(year)

    return availability
