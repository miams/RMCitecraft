"""Pydantic models for census citation extraction and validation."""

from pydantic import BaseModel, Field, field_validator


class CensusExtraction(BaseModel):
    """Structured data extracted from FamilySearch census citation.

    This model represents the parsed components of a FamilySearch citation
    before template rendering. The LLM populates this model from the raw
    FamilySearch citation text.
    """

    year: int = Field(ge=1790, le=1950, description="Census year (1790-1950)")
    schedule_type: str = Field(
        default="population",
        description="Schedule type: population, slave, mortality, etc."
    )
    state: str = Field(min_length=2, description="US state or territory")
    county: str = Field(min_length=1, description="County name (without 'County' suffix)")
    locality: str | None = Field(
        None, description="Township/City/Village/etc. name (without type)"
    )
    locality_type: str | None = Field(
        None,
        description="Place type: Township, City, Village, Borough, etc.",
    )
    enumeration_district: str | None = Field(
        None, description="Enumeration district number (may be incomplete in source)"
    )
    page: str | None = Field(
        None, description="Page number (used for 1790-1870 censuses)"
    )
    sheet: str | None = Field(
        None, description="Sheet number with suffix (e.g., 13-A, 7B) for 1880-1940"
    )
    line: str | None = Field(None, description="Line number on the sheet")
    family_number: str | None = Field(
        None, description="Family number (extracted but not used in citations)"
    )
    dwelling_number: str | None = Field(
        None, description="Dwelling number (extracted but not used in 1930+ citations)"
    )
    column: str | None = Field(
        None, description="Column number for slave schedules (1 or 2)"
    )
    person_name: str = Field(description="Person's name as it appears in census")
    person_role: str | None = Field(
        None, description="Person's role for slave schedules (typically 'owner')"
    )
    familysearch_url: str = Field(
        description="FamilySearch ARK URL (query parameters stripped)"
    )
    access_date: str = Field(
        description="Access date in format: 'D Month YYYY' (e.g., '7 November 2020')"
    )
    nara_publication: str | None = Field(
        None, description="NARA microfilm publication (not used in 1930+ citations)"
    )
    fhl_microfilm: str | None = Field(
        None, description="FHL microfilm number (not used in 1930+ citations)"
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Required fields that LLM could not extract from source",
    )

    @field_validator("year")
    @classmethod
    def validate_census_year(cls, v: int) -> int:
        """Validate census year is a valid decennial year."""
        if v % 10 != 0:
            raise ValueError(
                f"Invalid census year: {v}. Federal census years are every 10 years (1790-1950)."
            )
        return v

    @field_validator("familysearch_url")
    @classmethod
    def strip_query_params(cls, v: str) -> str:
        """Remove query parameters from URL (e.g., ?lang=en)."""
        if "?" in v:
            return v.split("?")[0]
        return v

    @field_validator("sheet")
    @classmethod
    def normalize_sheet_format(cls, v: str | None) -> str | None:
        """Normalize sheet format: '13A' → '13-A', '7B' → '7-B'."""
        if not v:
            return v
        # If sheet is just numbers and letters with no hyphen, add hyphen
        if len(v) >= 2 and v[-1].isalpha() and v[-2].isdigit():
            return f"{v[:-1]}-{v[-1]}"
        return v


class PlaceDetails(BaseModel):
    """Place information extracted from EventTable → PlaceTable.

    This model represents the parsed location from RootsMagic's PlaceTable,
    which provides authoritative place names and types.
    """

    locality: str | None = Field(None, description="Township/City/Village name")
    locality_type: str | None = Field(None, description="Township/City/Village/etc.")
    county: str = Field(description="County name (without 'County' suffix)")
    state: str = Field(description="State name")
    country: str | None = Field(None, description="Country (usually 'United States')")

    @classmethod
    def from_place_string(cls, place_string: str) -> "PlaceDetails":
        """Parse RootsMagic place string into components.

        Expected format: "Locality [Type], County, State, Country"
        Examples:
            "Jefferson Township, Greene, Pennsylvania, United States"
            "Baltimore (Independent City), Maryland, United States"
            "Greene, Pennsylvania, United States" (no locality)

        Args:
            place_string: Comma-delimited place string from PlaceTable.Name

        Returns:
            PlaceDetails with parsed components
        """
        parts = [p.strip() for p in place_string.split(",")]

        if len(parts) < 3:
            raise ValueError(
                f"Invalid place string format: '{place_string}'. "
                f"Expected at least County, State, Country"
            )

        # Handle different place string lengths
        if len(parts) == 3:
            # "County, State, Country" (no locality)
            county, state, country = parts
            locality = None
            locality_type = None
        elif len(parts) == 4:
            # "Locality [Type], County, State, Country"
            locality_full, county, state, country = parts
            locality, locality_type = cls._parse_locality(locality_full)
        else:
            # More than 4 parts - treat first N-3 as locality, last 3 as county/state/country
            locality_parts = parts[:-3]
            locality_full = ", ".join(locality_parts)
            county, state, country = parts[-3:]
            locality, locality_type = cls._parse_locality(locality_full)

        return cls(
            locality=locality,
            locality_type=locality_type,
            county=county,
            state=state,
            country=country,
        )

    @staticmethod
    def _parse_locality(locality_full: str) -> tuple[str | None, str | None]:
        """Parse locality name and type from combined string.

        Examples:
            "Jefferson Township" → ("Jefferson", "Township")
            "Baltimore (Independent City)" → ("Baltimore", "Independent City")
            "New York" → ("New York", None)

        Returns:
            Tuple of (locality_name, locality_type)
        """
        # Check for parenthetical type: "Baltimore (Independent City)"
        if "(" in locality_full and locality_full.endswith(")"):
            locality = locality_full[: locality_full.index("(")].strip()
            locality_type = locality_full[locality_full.index("(") + 1 : -1].strip()
            return locality, locality_type

        # Check for space-separated type: "Jefferson Township"
        type_keywords = [
            "Township",
            "City",
            "Village",
            "Borough",
            "Town",
            "Parish",
            "District",
            "Precinct",
            "Ward",
            "Hundred",
        ]

        for keyword in type_keywords:
            if locality_full.endswith(f" {keyword}"):
                locality = locality_full[: -len(keyword) - 1].strip()
                return locality, keyword

        # No recognized type found
        return locality_full, None


class CensusCitation(BaseModel):
    """Complete census citation with all three Evidence Explained formats.

    This model represents the final generated citations ready to be written
    to the database (SourceTable.Fields BLOB).
    """

    footnote: str = Field(description="Full Evidence Explained footnote")
    short_footnote: str = Field(description="Short footnote for subsequent references")
    bibliography: str = Field(description="Bibliography entry")

    # Metadata
    citation_id: int = Field(description="RootsMagic CitationID")
    source_id: int = Field(description="RootsMagic SourceID")
    person_id: int | None = Field(None, description="PersonID (if event owner)")
    event_id: int = Field(description="EventID for the census event")
