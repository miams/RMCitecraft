"""Data models for census form rendering.

These models represent census data structured for HTML template rendering,
separate from the database storage models in census_extraction_db.py.

The key difference is that these models are optimized for presentation:
- Flattened person data with all fields accessible
- Quality indicators attached to fields
- Page-level groupings for multi-page families
- Schema-aware column definitions for dynamic layouts
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class FieldQualityLevel(Enum):
    """Quality level for a field value."""

    VERIFIED = "verified"  # Human-verified, high confidence
    CLEAR = "clear"  # Machine-extracted, clearly legible
    UNCERTAIN = "uncertain"  # Readable but uncertain interpretation
    DAMAGED = "damaged"  # Source is damaged/faded
    ILLEGIBLE = "illegible"  # Cannot be read


@dataclass
class FieldValue:
    """A field value with optional quality metadata.

    Attributes:
        value: The actual field value
        quality: Quality assessment level
        confidence: Confidence score (0.0-1.0)
        note: Transcription note or comment
        original_label: Original label from source (e.g., FamilySearch)
        is_sample_line_field: True if this is a sample-line-only field (1950)
    """

    value: str | int | None
    quality: FieldQualityLevel = FieldQualityLevel.CLEAR
    confidence: float = 1.0
    note: str = ""
    original_label: str = ""
    is_sample_line_field: bool = False

    def __str__(self) -> str:
        """Return string representation of value."""
        if self.value is None:
            return ""
        return str(self.value)

    @property
    def has_quality_issue(self) -> bool:
        """Check if this field has quality concerns."""
        return self.quality in (
            FieldQualityLevel.UNCERTAIN,
            FieldQualityLevel.DAMAGED,
            FieldQualityLevel.ILLEGIBLE,
        )

    @property
    def css_class(self) -> str:
        """Get CSS class for quality indicator."""
        return f"quality-{self.quality.value}"


@dataclass
class FormPersonRow:
    """A person row ready for form rendering.

    Contains all fields (core + extended) flattened for easy template access.
    Field values are wrapped in FieldValue for quality tracking.

    Attributes:
        person_id: Database person ID
        line_number: Line number on census form (1-30 typically)
        is_target: Whether this person is the target of the search
        is_sample_person: Whether this person has sample line data (1950)
        is_head_of_household: Whether this is the household head
        familysearch_ark: FamilySearch ARK URL
        fields: Dict of field_name -> FieldValue
        notes: User notes/comments for this person
    """

    person_id: int | None = None
    line_number: int | None = None
    is_target: bool = False
    is_sample_person: bool = False
    is_head_of_household: bool = False
    familysearch_ark: str = ""
    fields: dict[str, FieldValue] = field(default_factory=dict)
    notes: str = ""

    def get_field(self, name: str, default: str = "") -> str:
        """Get a field value as string, with default."""
        fv = self.fields.get(name)
        if fv is None or fv.value is None:
            return default
        return str(fv.value)

    def get_field_value(self, name: str) -> FieldValue | None:
        """Get a FieldValue object for quality access."""
        return self.fields.get(name)

    def has_field(self, name: str) -> bool:
        """Check if a field exists and has a value."""
        fv = self.fields.get(name)
        return fv is not None and fv.value is not None and str(fv.value).strip() != ""


@dataclass
class FormPageData:
    """A census page ready for form rendering.

    Attributes:
        page_id: Database page ID
        census_year: Census year (1790-1950)
        state: State name
        county: County name
        township_city: Township or city name
        enumeration_district: ED number
        sheet_number: Sheet number (1880-1940)
        sheet_letter: Sheet letter (A/B)
        page_number: Page number (1790-1870, 1950)
        stamp_number: Stamp number (1950 citations)
        enumeration_date: Date of enumeration
        enumerator_name: Name of enumerator
        familysearch_image_url: URL to FamilySearch image
        persons: List of persons on this page
        page_notes: User notes for the page
    """

    page_id: int | None = None
    census_year: int = 0
    state: str = ""
    county: str = ""
    township_city: str = ""
    enumeration_district: str = ""
    sheet_number: str = ""
    sheet_letter: str = ""
    page_number: str = ""
    stamp_number: str = ""
    enumeration_date: str = ""
    enumerator_name: str = ""
    checked_by: str = ""
    familysearch_image_url: str = ""
    persons: list[FormPersonRow] = field(default_factory=list)
    page_notes: str = ""

    @property
    def location_display(self) -> str:
        """Get formatted location string."""
        parts = []
        if self.township_city:
            parts.append(self.township_city)
        if self.county:
            parts.append(f"{self.county} County")
        if self.state:
            parts.append(self.state)
        return ", ".join(parts)

    @property
    def sheet_or_page_display(self) -> str:
        """Get sheet/page reference for display."""
        if self.census_year >= 1880 and self.census_year <= 1940:
            # Sheet format
            sheet = self.sheet_number
            if self.sheet_letter:
                sheet += self.sheet_letter
            return f"Sheet {sheet}" if sheet else ""
        elif self.census_year == 1950:
            # Stamp/page format
            if self.stamp_number:
                return f"Stamp {self.stamp_number}"
            elif self.page_number:
                return f"Page {self.page_number}"
            return ""
        else:
            # Pre-1880 page format
            return f"Page {self.page_number}" if self.page_number else ""

    @property
    def ed_display(self) -> str:
        """Get ED for display (1880+ only)."""
        if self.census_year >= 1880 and self.enumeration_district:
            return f"E.D. {self.enumeration_district}"
        return ""


@dataclass
class FormColumnDef:
    """Column definition for dynamic form layout.

    Derived from census year schema, drives template column rendering.

    Attributes:
        name: Field name (matches schema and database)
        column_number: Physical column number on form (for header)
        label: Display label for column header
        short_label: Abbreviated label for narrow columns
        width: Suggested CSS width class (narrow, medium, wide)
        is_sample_only: True if this column only appears for sample persons
        tooltip: Hover text explaining the column
    """

    name: str
    column_number: str | None = None
    label: str = ""
    short_label: str = ""
    width: str = "medium"
    is_sample_only: bool = False
    tooltip: str = ""

    @property
    def header_display(self) -> str:
        """Get column header display text."""
        if self.column_number:
            return f"{self.column_number}. {self.short_label or self.label}"
        return self.short_label or self.label


@dataclass
class FormHousehold:
    """A household grouping within a page.

    Groups persons by dwelling/family number for visual distinction.

    Attributes:
        dwelling_number: Dwelling unit number
        family_number: Family number within dwelling
        persons: Persons in this household
    """

    dwelling_number: int | None = None
    family_number: int | None = None
    persons: list[FormPersonRow] = field(default_factory=list)

    @property
    def head(self) -> FormPersonRow | None:
        """Get the head of household."""
        for person in self.persons:
            if person.is_head_of_household:
                return person
        return self.persons[0] if self.persons else None


@dataclass
class CensusFormContext:
    """Complete context for rendering a census form.

    This is the top-level object passed to Jinja2 templates.

    Attributes:
        census_year: The census year
        pages: List of pages to render (usually 1, but can span pages)
        columns: Column definitions for the form layout
        households: Persons grouped by household
        title: Form title (e.g., "1950 U.S. Census - Noble County, Ohio")
        target_person_name: Name of the target person (for highlighting)
        show_quality_indicators: Whether to show quality badges
        show_sample_columns: Whether to show sample line columns
        extracted_at: When the data was extracted
        familysearch_url: URL to the FamilySearch page
        notes: General notes for the form
    """

    census_year: int = 0
    pages: list[FormPageData] = field(default_factory=list)
    columns: list[FormColumnDef] = field(default_factory=list)
    households: list[FormHousehold] = field(default_factory=list)
    title: str = ""
    target_person_name: str = ""
    show_quality_indicators: bool = True
    show_sample_columns: bool = True
    extracted_at: datetime | None = None
    familysearch_url: str = ""
    notes: str = ""

    @property
    def primary_page(self) -> FormPageData | None:
        """Get the primary (first) page."""
        return self.pages[0] if self.pages else None

    @property
    def all_persons(self) -> list[FormPersonRow]:
        """Get all persons across all pages."""
        persons = []
        for page in self.pages:
            persons.extend(page.persons)
        return persons

    @property
    def target_person(self) -> FormPersonRow | None:
        """Get the target person if present."""
        for page in self.pages:
            for person in page.persons:
                if person.is_target:
                    return person
        return None

    def get_sample_columns(self) -> list[FormColumnDef]:
        """Get only sample-line columns."""
        return [col for col in self.columns if col.is_sample_only]

    def get_main_columns(self) -> list[FormColumnDef]:
        """Get non-sample columns (shown for all persons)."""
        return [col for col in self.columns if not col.is_sample_only]


# =============================================================================
# Column Definitions by Census Year
# =============================================================================

# 1950 Census Column Definitions
COLUMNS_1950 = [
    # Location columns
    FormColumnDef(
        name="line_number",
        column_number=None,
        label="Line",
        short_label="LINE",
        width="narrow",
    ),
    FormColumnDef(
        name="street_name",
        column_number="1",
        label="Street Name",
        short_label="STREET",
        width="wide",
        tooltip="Street, avenue, road, etc.",
    ),
    FormColumnDef(
        name="household_number",
        column_number="2",
        label="House Number",
        short_label="HOUSE#",
        width="narrow",
        tooltip="Serial number of household",
    ),
    FormColumnDef(
        name="dwelling_number",
        column_number="3",
        label="Dwelling",
        short_label="DWELL#",
        width="narrow",
        tooltip="Serial number of dwelling unit",
    ),
    # Personal information
    FormColumnDef(
        name="full_name",
        column_number="7",
        label="Name",
        short_label="NAME",
        width="wide",
        tooltip="Full name of person",
    ),
    FormColumnDef(
        name="relationship_to_head",
        column_number="8",
        label="Relationship",
        short_label="REL",
        width="narrow",
        tooltip="Relationship to head of household",
    ),
    FormColumnDef(
        name="race",
        column_number="9",
        label="Race",
        short_label="RACE",
        width="narrow",
    ),
    FormColumnDef(
        name="sex",
        column_number="10",
        label="Sex",
        short_label="SEX",
        width="narrow",
    ),
    FormColumnDef(
        name="age",
        column_number="11",
        label="Age",
        short_label="AGE",
        width="narrow",
    ),
    FormColumnDef(
        name="marital_status",
        column_number="12",
        label="Marital Status",
        short_label="MAR",
        width="narrow",
    ),
    FormColumnDef(
        name="birthplace",
        column_number="13",
        label="Birthplace",
        short_label="BIRTHPL",
        width="medium",
    ),
    # Employment
    FormColumnDef(
        name="occupation",
        column_number="20a",
        label="Occupation",
        short_label="OCCUP",
        width="medium",
    ),
    FormColumnDef(
        name="industry",
        column_number="20b",
        label="Industry",
        short_label="INDUST",
        width="medium",
    ),
    # Sample line columns (cols 21-33)
    FormColumnDef(
        name="highest_grade_attended",
        column_number="26",
        label="Highest Grade",
        short_label="GRADE",
        width="narrow",
        is_sample_only=True,
        tooltip="Highest grade of school attended",
    ),
    FormColumnDef(
        name="completed_grade",
        column_number="27",
        label="Completed Grade",
        short_label="COMPL",
        width="narrow",
        is_sample_only=True,
    ),
    FormColumnDef(
        name="weeks_worked_1949",
        column_number="30",
        label="Weeks Worked 1949",
        short_label="WKS49",
        width="narrow",
        is_sample_only=True,
    ),
    FormColumnDef(
        name="income_wages_1949",
        column_number="31",
        label="Wage Income 1949",
        short_label="WAGES",
        width="narrow",
        is_sample_only=True,
    ),
    FormColumnDef(
        name="income_self_employment_1949",
        column_number="32",
        label="Self-Employment Income",
        short_label="SELF",
        width="narrow",
        is_sample_only=True,
    ),
    FormColumnDef(
        name="income_other_1949",
        column_number="33",
        label="Other Income",
        short_label="OTHER",
        width="narrow",
        is_sample_only=True,
    ),
    FormColumnDef(
        name="veteran_status",
        column_number=None,
        label="Veteran",
        short_label="VET",
        width="narrow",
        is_sample_only=True,
    ),
]


def get_columns_for_year(year: int) -> list[FormColumnDef]:
    """Get column definitions for a census year.

    Args:
        year: Census year (1790-1950)

    Returns:
        List of column definitions for template rendering
    """
    if year == 1950:
        return COLUMNS_1950
    # TODO: Add definitions for other years
    return []
