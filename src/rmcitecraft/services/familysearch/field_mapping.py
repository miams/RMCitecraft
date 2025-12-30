"""Unified field mapping from FamilySearch labels to internal schema.

This is the single source of truth for mapping FamilySearch HTML labels
to our internal CensusPerson and CensusPage field names.

IMPORTANT: FamilySearch labels use spaces (e.g., "Given Name"), but extraction
stores keys with underscores. Lookup should normalize to spaces before matching.

Example lookup:
    # Raw extracted key has underscores
    raw_key = "given_name"

    # Convert to space format for lookup
    lookup_key = raw_key.replace("_", " ")  # -> "given name"

    # Look up in map
    internal_field = FAMILYSEARCH_FIELD_MAP.get(lookup_key)  # -> "given_name"
"""

from typing import Final

# =============================================================================
# FamilySearch Label to Internal Field Name Mapping
# =============================================================================
#
# Keys: FamilySearch HTML labels (lowercase, spaces between words)
# Values: Internal field names (lowercase, underscores between words)
#
# Field categories:
# - Person fields: go to CensusPerson model
# - Page fields: go to CensusPage model
# - Extended fields: go to census_person_field table (EAV pattern)
#
# =============================================================================

FAMILYSEARCH_FIELD_MAP: Final[dict[str, str]] = {
    # -------------------------------------------------------------------------
    # Core Person Fields (CensusPerson model)
    # -------------------------------------------------------------------------
    # Name fields
    "name": "full_name",
    "given name": "given_name",
    "surname": "surname",
    "name suffix": "name_suffix",

    # Demographics
    "race": "race",
    "sex": "sex",
    "age": "age",
    "relationship to head of household": "relationship_to_head",
    "relationship to head": "relationship_to_head",
    "marital status": "marital_status",

    # Birthplace
    "birthplace": "birthplace",
    "birth place": "birthplace",
    "place": "birthplace",  # FamilySearch sometimes uses generic "Place"
    "father's birth place": "birthplace_father",
    "father's birthplace": "birthplace_father",
    "mother's birth place": "birthplace_mother",
    "mother's birthplace": "birthplace_mother",

    # Occupation
    "occupation": "occupation",
    "industry": "industry",
    "occupation industry": "industry",
    "worker class": "worker_class",
    "class of worker": "worker_class",

    # Family/dwelling numbers
    # NOTE: "household id" and "household identifier" map to dwelling_number by default.
    # For 1850, 1860, 1870, 1900, 1910 Census, YearSpecificHandler remaps to family_number.
    "household id": "dwelling_number",
    "household identifier": "dwelling_number",  # 1850 uses "Household Identifier"
    "dwelling number": "dwelling_number",
    "family number": "family_number",

    # -------------------------------------------------------------------------
    # Page/Location Fields (CensusPage model)
    # -------------------------------------------------------------------------
    "state": "state",
    "county": "county",
    "city": "township_city",
    "township": "township_city",

    # Enumeration district
    # NOTE: 1910 uses "District: ED 340" format - parsed by YearSpecificHandler
    "enumeration district": "enumeration_district",
    "district": "enumeration_district",
    "supervisor district field": "supervisor_district",

    # Page/sheet/stamp reference
    "page number": "page_number",
    "source page number": "page_number",
    "sheet number": "sheet_number",
    "source sheet number": "sheet_number",
    "source sheet letter": "sheet_letter",  # 1910: A or B side
    "stamp number": "stamp_number",  # 1950
    "line number": "line_number",
    "source line number": "line_number",

    # Enumeration date
    "date": "enumeration_date",
    "event date": "event_date",
    "event place": "event_place",
    "event place (original)": "event_place_original",

    # -------------------------------------------------------------------------
    # Extended Fields (census_person_field EAV table)
    # -------------------------------------------------------------------------
    # Address
    "house number": "house_number",
    "apartment number": "apartment_number",
    "street name": "street_name",

    # Digital reference
    "digital folder number": "digital_folder_number",
    "image number": "image_number",

    # Enumerator
    "enumerator name": "enumerator_name",

    # Farm/dwelling details
    "lived on farm": "is_dwelling_on_farm",
    "3 plus acres": "farm_3_plus_acres",
    "agricultural questionnaire": "agricultural_questionnaire",

    # Naturalization
    "naturalized": "naturalized",
    "citizen status flag": "naturalized",

    # Employment (for persons 14+)
    "employed": "employment_status",
    "worked last week": "any_work_last_week",
    "seeking work": "looking_for_work",
    "has job": "has_job_not_at_work",
    "hours worked": "hours_worked",

    # 1950 Sample: Residence April 1, 1949
    "same house": "residence_1949_same_house",
    "same house 1949": "residence_1949_same_house",
    "lived on farm last year": "residence_1949_on_farm",
    "on farm 1949": "residence_1949_on_farm",
    "same county": "residence_1949_same_county",
    "same county 1949": "residence_1949_same_county",
    "different location 1949": "residence_1949_different_location",

    # 1950 Sample: Education
    "attended school": "school_attendance",
    "highest grade": "highest_grade_attended",
    "grade completed": "highest_grade_attended",
    "completed grade": "completed_grade",

    # 1950 Sample: Employment/income history
    "weeks out of work": "weeks_looking_for_work",
    "weeks worked": "weeks_worked_1949",
    "income": "income_wages_1949",
    "income from other sources": "income_other_1949",
    "self employment income": "income_self_employment_1949",

    # Veteran status
    "veteran": "veteran_status",
    "world war i vet": "veteran_ww1",
    "world war ii vet": "veteran_ww2",

    # Other demographics
    "children born count": "children_born",
    "married more than once": "married_more_than_once",
    "years since marital status change": "years_marital_change",
}

# =============================================================================
# Extended Fields (EAV storage)
# =============================================================================
# Fields that should be stored in census_person_field table instead of
# CensusPerson core fields. These are typically sample-line fields or
# supplementary data not needed for primary census record processing.

EXTENDED_FIELDS: Final[frozenset[str]] = frozenset({
    # Location/event details
    "event_date",
    "event_place",
    "event_place_original",
    "digital_folder_number",
    "image_number",
    "house_number",
    "apartment_number",
    "street_name",
    "enumerator_name",

    # Dwelling info
    "is_dwelling_on_farm",
    "farm_3_plus_acres",
    "agricultural_questionnaire",

    # Naturalization
    "naturalized",

    # Employment details
    "employment_status",
    "any_work_last_week",
    "looking_for_work",
    "has_job_not_at_work",
    "hours_worked",

    # 1949 residence (sample)
    "residence_1949_same_house",
    "residence_1949_on_farm",
    "residence_1949_same_county",
    "residence_1949_different_location",

    # Education (sample)
    "school_attendance",
    "highest_grade_attended",
    "completed_grade",

    # Income (sample)
    "weeks_looking_for_work",
    "weeks_worked_1949",
    "income_wages_1949",
    "income_other_1949",
    "income_self_employment_1949",

    # Veteran status
    "veteran_status",
    "veteran_ww1",
    "veteran_ww2",

    # Other
    "children_born",
    "married_more_than_once",
    "years_marital_change",
})

# =============================================================================
# Page Fields (CensusPage model)
# =============================================================================
# Fields that belong to CensusPage rather than CensusPerson

PAGE_FIELDS: Final[frozenset[str]] = frozenset({
    "state",
    "county",
    "township_city",
    "enumeration_district",
    "supervisor_district",
    "page_number",
    "sheet_number",
    "sheet_letter",  # Temporary; combined into sheet_number by YearSpecificHandler
    "stamp_number",
    "enumeration_date",
})


def map_familysearch_field(fs_label: str) -> str | None:
    """Map a FamilySearch label to internal field name.

    Handles normalization of the label before lookup:
    - Converts to lowercase
    - Converts underscores to spaces
    - Strips whitespace

    Args:
        fs_label: FamilySearch label (may have underscores or spaces)

    Returns:
        Internal field name or None if not mapped
    """
    # Normalize: lowercase, underscores to spaces, strip
    normalized = fs_label.lower().replace("_", " ").strip()

    # Direct lookup
    if normalized in FAMILYSEARCH_FIELD_MAP:
        return FAMILYSEARCH_FIELD_MAP[normalized]

    # Partial match for parenthetical variations
    # e.g., "birth year (estimated)" should match "birth year"
    for fs_key, mapped in FAMILYSEARCH_FIELD_MAP.items():
        if normalized.startswith(fs_key):
            return mapped

    return None


def is_extended_field(field_name: str) -> bool:
    """Check if a field should be stored as extended (EAV) data.

    Args:
        field_name: Internal field name

    Returns:
        True if field should go to census_person_field table
    """
    return field_name in EXTENDED_FIELDS


def is_page_field(field_name: str) -> bool:
    """Check if a field belongs to CensusPage.

    Args:
        field_name: Internal field name

    Returns:
        True if field should go to CensusPage
    """
    return field_name in PAGE_FIELDS
