"""Data models for census citations."""


from pydantic import BaseModel, Field, field_validator


class ParsedCitation(BaseModel):
    """Structured data extracted from FamilySearch citation."""

    # Source data
    citation_id: int
    source_name: str
    familysearch_entry: str

    # Parsed components
    census_year: int = Field(ge=1790, le=1950, description="Census year")
    schedule_type: str = Field(
        default="population",
        description="Schedule type: population, slave, mortality, etc."
    )
    state: str
    county: str
    town_ward: str | None = None
    enumeration_district: str | None = None
    sheet: str | None = None
    line: str | None = None
    family_number: str | None = None
    dwelling_number: str | None = None
    column: str | None = None  # For slave schedules: column 1 or 2

    # Person info
    person_name: str
    given_name: str
    surname: str
    person_role: str | None = None  # For slave schedules: "owner"

    # URLs and references
    familysearch_url: str
    access_date: str
    nara_publication: str | None = None  # e.g., "T623"
    fhl_microfilm: str | None = None  # e.g., "1,241,311"

    # Generated citations (populated by formatter)
    footnote: str | None = None
    short_footnote: str | None = None
    bibliography: str | None = None

    # Validation status
    is_complete: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    confidence: dict[str, float] = Field(default_factory=dict)

    @field_validator("census_year")
    @classmethod
    def validate_census_year(cls, v: int) -> int:
        """Census years are every 10 years: 1790, 1800, ..., 1950."""
        if v % 10 != 0:
            raise ValueError(f"Invalid census year: {v}")
        return v

    @field_validator("familysearch_url")
    @classmethod
    def strip_query_params(cls, v: str) -> str:
        """Remove query parameters from URL (e.g., ?lang=en)."""
        if v and "?" in v:
            return v.split("?")[0]
        return v


class CitationExtraction(BaseModel):
    """LLM extraction result with missing field detection."""

    year: int = Field(ge=1790, le=1950, description="Census year")
    state: str = Field(min_length=2, description="US state or territory")
    county: str = Field(min_length=1, description="County name")
    person_name: str
    town_ward: str | None = None
    enumeration_district: str | None = None
    sheet: str | None = None
    line: str | None = None
    family_number: str | None = None
    dwelling_number: str | None = None
    familysearch_url: str
    access_date: str
    nara_publication: str | None = None
    fhl_microfilm: str | None = None

    # Fields LLM couldn't extract
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Required fields that couldn't be extracted",
    )

    # Per-field confidence scores
    confidence: dict[str, float] = Field(
        default_factory=dict,
        description="Confidence score for each extracted field (0.0-1.0)",
    )

    @field_validator("year")
    @classmethod
    def validate_census_year(cls, v: int) -> int:
        """Census years are every 10 years: 1790, 1800, ..., 1950."""
        if v % 10 != 0:
            raise ValueError(f"Invalid census year: {v}")
        return v


class CensusMetadata(BaseModel):
    """Metadata about a specific census year."""

    year: int
    name: str  # "1900 Federal"
    folder_name: str  # "1900 Federal"
    requires_ed: bool  # True for 1880+
    schedule_type: str  # "population", "slave", "mortality", "veterans"
    template_version: str  # "1790-1840", "1850-1880", "1900-1950"
