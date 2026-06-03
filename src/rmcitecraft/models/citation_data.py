"""Data models for citation building and formatting."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class FamilySearchMetadata:
    """Metadata extracted from FamilySearch URL or citation text.

    Attributes:
        ark_id: FamilySearch ARK identifier (e.g., "61903/1:1:ABC123")
        state: State name (e.g., "Pennsylvania")
        state_abbr: State abbreviation (e.g., "PA")
        county: County name (optional)
        collection_name: Full collection name
        year: Primary year of registration
        registration_type: Type of registration ("WW1", "WW2", etc.)
        registration_date: Specific date if known
        url: Full FamilySearch URL
    """

    ark_id: Optional[str] = None
    state: Optional[str] = None
    state_abbr: Optional[str] = None
    county: Optional[str] = None
    collection_name: str = ""
    year: Optional[int] = None
    registration_type: str = "WW2"  # Default to WW2
    registration_date: Optional[str] = None
    url: Optional[str] = None

    @property
    def is_ww1(self) -> bool:
        """Check if this is a WW1 draft registration."""
        return self.registration_type == "WW1" or (self.year and 1917 <= self.year <= 1918)

    @property
    def is_ww2(self) -> bool:
        """Check if this is a WW2 draft registration."""
        return self.registration_type == "WW2" or (self.year and 1940 <= self.year <= 1947)

    @property
    def state_citation_form(self) -> str:
        """Return state name in citation form (full name for footnote)."""
        return self.state or ""

    @property
    def state_short_form(self) -> str:
        """Return state in short form (abbreviation for short footnote)."""
        return self.state_abbr or self.state or ""

    @property
    def county_citation_form(self) -> str:
        """Return county in citation form (e.g., 'Noble County')."""
        if not self.county:
            return ""
        if self.county.lower().endswith(' county'):
            return self.county
        return f"{self.county} County"

    @property
    def county_short_form(self) -> str:
        """Return county in short form (e.g., 'Noble Co.')."""
        if not self.county:
            return ""
        county_name = self.county.replace(' County', '').replace(' county', '')
        return f"{county_name} Co."


@dataclass
class SourceData:
    """Data for creating a Source record in RootsMagic.

    Attributes:
        name: Source name/title
        ref_number: Reference number (optional)
        comments: Comments/notes about the source
        bibliography: Bibliography entry
        footnote_template: Template for footnote (if using template)
        short_footnote_template: Template for short footnote
        fields_blob: XML-encoded BLOB for SourceTable.Fields
        template_id: TemplateID (0 for free-form)
    """

    name: str
    ref_number: str = ""
    comments: str = ""
    bibliography: str = ""
    footnote_template: str = ""
    short_footnote_template: str = ""
    fields_blob: Optional[bytes] = None
    template_id: int = 0  # 0 = free-form citation


@dataclass
class CitationData:
    """Data for creating a Citation record in RootsMagic.

    Attributes:
        source_id: SourceID this citation belongs to
        comments: Citation-specific comments
        ref_number: Reference number for this citation
        footnote: Full footnote text
        short_footnote: Abbreviated footnote text
        bibliography: Bibliography entry (usually from source)
        fields_blob: XML-encoded BLOB for CitationTable.Fields
        actual_text: Actual text from the record (optional)
        quality: Quality score (0-3)
    """

    source_id: int
    comments: str = ""
    ref_number: str = ""
    footnote: str = ""
    short_footnote: str = ""
    bibliography: str = ""
    fields_blob: Optional[bytes] = None
    actual_text: str = ""
    quality: int = 0  # 0 = uncategorized


# State name to abbreviation mapping
STATE_ABBREVIATIONS = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
    'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
    'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
    'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
    'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
    'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
    'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
    'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY',
    'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
    'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
    'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
    'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV',
    'wisconsin': 'WI', 'wyoming': 'WY', 'district of columbia': 'DC',
}

# Reverse mapping
ABBREVIATION_TO_STATE = {v: k.title() for k, v in STATE_ABBREVIATIONS.items()}


def get_state_abbreviation(state_name: str) -> Optional[str]:
    """Get state abbreviation from state name.

    Args:
        state_name: Full state name or abbreviation

    Returns:
        Two-letter state abbreviation or None
    """
    if not state_name:
        return None

    state_lower = state_name.lower().strip()

    # Check if already an abbreviation
    if len(state_lower) == 2 and state_lower.upper() in ABBREVIATION_TO_STATE:
        return state_lower.upper()

    # Look up full name
    return STATE_ABBREVIATIONS.get(state_lower)


def get_state_full_name(state_abbr: str) -> Optional[str]:
    """Get full state name from abbreviation.

    Args:
        state_abbr: Two-letter state abbreviation

    Returns:
        Full state name or None
    """
    if not state_abbr:
        return None

    abbr_upper = state_abbr.upper().strip()
    return ABBREVIATION_TO_STATE.get(abbr_upper)
