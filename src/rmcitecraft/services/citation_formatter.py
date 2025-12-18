"""Evidence Explained citation formatting for US Federal Census records.

This module implements deterministic template-based formatting following
Elizabeth Shown Mills' Evidence Explained citation style for census records.
"""

from rmcitecraft.models.census_citation import CensusCitation, CensusExtraction, PlaceDetails

# State abbreviations for short footnotes (Evidence Explained style)
# Reference: Mills, Elizabeth Shown. Evidence Explained, 4th Edition.
# Note: These are traditional abbreviations, NOT postal codes
STATE_ABBREVIATIONS = {
    "Alabama": "Ala.",
    "Alaska": "Alaska",
    "Arizona": "Ariz.",
    "Arkansas": "Ark.",
    "California": "Calif.",
    "Colorado": "Colo.",
    "Connecticut": "Conn.",
    "Delaware": "Del.",
    "Florida": "Fla.",
    "Georgia": "Ga.",
    "Hawaii": "Hawaii",
    "Idaho": "Idaho",
    "Illinois": "Ill.",
    "Indiana": "Ind.",
    "Iowa": "Iowa",
    "Kansas": "Kans.",
    "Kentucky": "Ky.",
    "Louisiana": "La.",
    "Maine": "Maine",
    "Maryland": "Md.",
    "Massachusetts": "Mass.",
    "Michigan": "Mich.",
    "Minnesota": "Minn.",
    "Mississippi": "Miss.",
    "Missouri": "Mo.",
    "Montana": "Mont.",
    "Nebraska": "Nebr.",
    "Nevada": "Nev.",
    "New Hampshire": "N.H.",
    "New Jersey": "N.J.",
    "New Mexico": "N.Mex.",
    "New York": "N.Y.",
    "North Carolina": "N.C.",
    "North Dakota": "N.Dak.",
    "Ohio": "Ohio",
    "Oklahoma": "Okla.",
    "Oregon": "Oreg.",
    "Pennsylvania": "Pa.",
    "Rhode Island": "R.I.",
    "South Carolina": "S.C.",
    "South Dakota": "S.Dak.",
    "Tennessee": "Tenn.",
    "Texas": "Tex.",
    "Utah": "Utah",
    "Vermont": "Vt.",
    "Virginia": "Va.",
    "Washington": "Wash.",
    "West Virginia": "W.Va.",
    "Wisconsin": "Wis.",
    "Wyoming": "Wyo.",
}


def format_1930_census_footnote(
    extraction: CensusExtraction, place: PlaceDetails
) -> str:
    """Generate Evidence Explained full footnote for 1930 census.

    Format:
        1930 U.S. census, Greene County, Pennsylvania, Jefferson Township,
        enumeration district (ED) 30-17, sheet 13-A, line 15, George B Iams;
        imaged, "United States Census, 1930," <i>FamilySearch</i>,
        (https://www.familysearch.org/ark:/61903/1:1:XH3Z-4J8 : accessed 7 November 2020).

    Args:
        extraction: Parsed citation data from FamilySearch
        place: Place details from RootsMagic PlaceTable

    Returns:
        Formatted footnote string
    """
    # Use place details from PlaceTable (authoritative source)
    locality_str = ""
    if place.locality:
        if place.locality_type:
            locality_str = f", {place.locality} {place.locality_type}"
        else:
            locality_str = f", {place.locality}"

    # ED component (required for 1900-1950)
    ed_str = ""
    if extraction.enumeration_district:
        ed_str = f", enumeration district (ED) {extraction.enumeration_district}"

    # Line component (optional but preferred)
    line_str = ""
    if extraction.line:
        line_str = f", line {extraction.line}"

    # Build footnote
    footnote = (
        f"{extraction.year} U.S. census, "
        f"{place.county} County, {place.state}"
        f"{locality_str}"
        f"{ed_str}, "
        f"sheet {extraction.sheet}"
        f"{line_str}, "
        f"{extraction.person_name}; "
        f'imaged, "United States Census, {extraction.year}," '
        f"<i>FamilySearch</i>, "
        f"({extraction.familysearch_url} : accessed {extraction.access_date})."
    )

    return footnote


def format_1930_census_short_footnote(
    extraction: CensusExtraction, place: PlaceDetails
) -> str:
    """Generate Evidence Explained short footnote for 1930 census.

    Format:
        1930 U.S. census, Greene Co., Pa., Jefferson Twp., E.D. 30-17,
        sheet 13-A, George B Iams.

    Note: "pop. sch." is omitted for 1910-1940 (only population schedules survived).
    Township/locality type is abbreviated (Twp., Vill., etc.).

    Reference: Mills, Elizabeth Shown. Evidence Explained: Citing History Sources
    from Artifacts to Cyberspace: 4th Edition (p. 253).

    Args:
        extraction: Parsed citation data from FamilySearch
        place: Place details from RootsMagic PlaceTable

    Returns:
        Formatted short footnote string
    """
    from rmcitecraft.config.constants import LOCALITY_TYPE_ABBREVIATIONS

    # Abbreviated state
    state_abbrev = STATE_ABBREVIATIONS.get(place.state, place.state)

    # Locality with abbreviated type
    locality_str = ""
    if place.locality:
        if place.locality_type:
            # Abbreviate the locality type
            type_abbrev = LOCALITY_TYPE_ABBREVIATIONS.get(
                place.locality_type, place.locality_type
            )
            locality_str = f", {place.locality} {type_abbrev}"
        else:
            locality_str = f", {place.locality}"

    # ED (use "E.D." abbreviation in short form)
    ed_str = ""
    if extraction.enumeration_district:
        ed_str = f", E.D. {extraction.enumeration_district}"

    # Line number (optional but preferred)
    line_str = ""
    if extraction.line:
        line_str = f", line {extraction.line}"

    # Build short footnote
    # Note: No "pop. sch." for 1910-1940 (only population schedules survived)
    short_footnote = (
        f"{extraction.year} U.S. census, "
        f"{place.county} Co., {state_abbrev}"
        f"{locality_str}"
        f"{ed_str}, "
        f"sheet {extraction.sheet}"
        f"{line_str}, "
        f"{extraction.person_name}."
    )

    return short_footnote


def format_1930_census_bibliography(
    extraction: CensusExtraction, place: PlaceDetails
) -> str:
    """Generate Evidence Explained bibliography entry for 1930 census.

    Format:
        U.S. Pennsylvania. Greene County. 1930 U.S Census.
        Imaged. "1930 United States Federal Census". <i>FamilySearch</i>
        https://www.familysearch.org/ark:/61903/1:1:XH3Z-4J8 : 2020.

    Note: "Population Schedule" is omitted for 1910-1940 because only population
    schedules survived for these years, making it redundant to specify.

    Reference: Mills, Elizabeth Shown. Evidence Explained: Citing History Sources
    from Artifacts to Cyberspace: 4th Edition (p. 253).

    Args:
        extraction: Parsed citation data from FamilySearch
        place: Place details from RootsMagic PlaceTable

    Returns:
        Formatted bibliography entry
    """
    # Extract year from access date for bibliography
    access_year = extraction.access_date.split()[-1]

    # For 1910-1940: Omit "Population Schedule" (only schedules that survived)
    # For 1900 and 1950: Include "Population Schedule" (multiple schedule types)
    bibliography = (
        f"U.S. {place.state}. {place.county} County. "
        f"{extraction.year} U.S Census. "
        f"Imaged. "
        f'"{extraction.year} United States Federal Census." '
        f"<i>FamilySearch</i> "
        f"{extraction.familysearch_url} : {access_year}."
    )

    return bibliography


def format_census_citation(
    extraction: CensusExtraction,
    place: PlaceDetails,
    citation_id: int,
    source_id: int,
    event_id: int,
    person_id: int | None = None,
) -> CensusCitation:
    """Generate all three Evidence Explained citation formats for a census record.

    This is the main entry point for citation formatting. It delegates to
    year-specific formatters based on the census year.

    Args:
        extraction: Parsed citation data from FamilySearch
        place: Place details from RootsMagic PlaceTable
        citation_id: RootsMagic CitationID
        source_id: RootsMagic SourceID
        event_id: RootsMagic EventID
        person_id: RootsMagic PersonID (if event owner, None if witness)

    Returns:
        CensusCitation with all three formatted citations

    Raises:
        ValueError: If census year is not supported
    """
    # Route to year-specific formatters
    # Currently only 1930 is implemented
    if extraction.year == 1930:
        footnote = format_1930_census_footnote(extraction, place)
        short_footnote = format_1930_census_short_footnote(extraction, place)
        bibliography = format_1930_census_bibliography(extraction, place)
    else:
        raise ValueError(
            f"Census year {extraction.year} not yet implemented. "
            f"Currently supported: 1930"
        )

    return CensusCitation(
        footnote=footnote,
        short_footnote=short_footnote,
        bibliography=bibliography,
        citation_id=citation_id,
        source_id=source_id,
        person_id=person_id,
        event_id=event_id,
    )


def format_census_citation_preview(data: dict, year: int) -> dict[str, str]:
    """Generate quick citation preview for live UI (no database queries required).

    This is a simplified formatter for the live preview in the data entry form.
    It generates approximate citations from incomplete data without requiring
    PlaceDetails from the database or full validation.

    For final citation generation, use format_census_citation() instead.

    Args:
        data: Dictionary with census data (may be incomplete)
        year: Census year

    Returns:
        Dictionary with 'footnote', 'short_footnote', 'bibliography' keys
    """
    from datetime import datetime

    # Get data with fallbacks for preview
    state = data.get('state', '[State]')
    county = data.get('county', '[County]')
    locality = data.get('town_ward', data.get('locality', ''))
    person = data.get('person_name', '[Person Name]')

    # 1860 Census: Use family number (column 2 per schema) instead of line number
    # FamilySearch doesn't index line numbers for 1860, but does extract HOUSEHOLD_ID
    # which maps to family_number per src/rmcitecraft/schemas/census/1860.yaml
    if year == 1860:
        family_number = data.get('family_number', '')
        household_label = "family"
        household_value = family_number if family_number else '[family]'
    else:
        line = data.get('line', '[line]')
        household_label = "line"
        household_value = line

    # Clean URL: Remove query parameters (e.g., ?lang=en) if not already cleaned
    raw_url = data.get('familysearch_url', '[URL]')
    url = raw_url.split('?')[0] if raw_url and raw_url != '[URL]' else raw_url

    # Use provided access date or generate current date in Evidence Explained format
    access_date = data.get('access_date') or datetime.now().strftime("%d %B %Y")

    # Year-specific field handling
    # Pre-1880: No enumeration district, uses "page" instead of "sheet"
    # 1880-1940: Uses enumeration district and "sheet"
    # 1950: Uses enumeration district and "stamp"
    uses_ed = year >= 1880
    if year < 1880:
        page_label = "page"
        page_value = data.get('page', '[page]')
    elif year == 1950:
        page_label = "stamp"
        page_value = data.get('stamp', data.get('sheet', '[stamp]'))
    else:
        page_label = "sheet"
        page_value = data.get('sheet', '[sheet]')

    ed = data.get('enumeration_district', '[ED]') if uses_ed else None

    # Footnote
    locality_str = f", {locality}" if locality else ""
    if uses_ed:
        ed_str = f", enumeration district (ED) {ed}"
    else:
        ed_str = ""

    footnote = (
        f"{year} U.S. census, {county} County, {state}{locality_str}"
        f"{ed_str}, {page_label} {page_value}, {household_label} {household_value}, {person}; "
        f"imaged, \"United States Census, {year},\" <i>FamilySearch</i> "
        f"({url} : accessed {access_date})."
    )

    # Short Footnote
    state_abbr = STATE_ABBREVIATIONS.get(state, state)
    # For 1910-1940: Omit "pop. sch." (only population schedules survived)
    pop_sch_str = "" if 1910 <= year <= 1940 else "pop. sch., "

    # Locality (optional - only include if available)
    locality_str = f", {locality}" if locality else ""

    # Household identifier: line number for most years, family number for 1860
    # For 1860: FamilySearch doesn't index line numbers, uses HOUSEHOLD_ID -> family_number
    household_str = f", {household_label} {household_value}" if household_value and household_value not in ('[line]', '[family]') else ""

    # ED string for short footnote
    if uses_ed:
        ed_short_str = f", E.D. {ed}"
    else:
        ed_short_str = ""

    short_footnote = (
        f"{year} U.S. census, {county} Co., {state_abbr}{locality_str}"
        f"{ed_short_str}, {page_label} {page_value}{household_str}, {person}."
    )

    # Bibliography
    # For 1910-1940: Omit "Population Schedule" (only schedules that survived)
    schedule_str = "" if 1910 <= year <= 1940 else "Population Schedule. "
    # Extract year from access_date for bibliography (e.g., "24 July 2015" -> "2015")
    access_year = access_date.split()[-1] if access_date else str(datetime.now().year)
    bibliography = (
        f"U.S. {state}. {county} County. {year} U.S Census. {schedule_str}"
        f"Imaged. \"United States Census, {year}\". <i>FamilySearch</i> "
        f"{url} : {access_year}."
    )

    return {
        'footnote': footnote,
        'short_footnote': short_footnote,
        'bibliography': bibliography,
    }
