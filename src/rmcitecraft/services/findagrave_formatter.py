"""
Find a Grave Citation Formatter

Formats Find a Grave memorial citations according to Evidence Explained style.
"""

from datetime import datetime


def format_findagrave_citation(
    memorial_data: dict,
    person_name: str,
    birth_year: int | None,
    death_year: int | None,
    maiden_name: str | None = None,
) -> dict[str, str]:
    """
    Format Find a Grave memorial citation in Evidence Explained style.

    Args:
        memorial_data: Extracted memorial data from Find a Grave page
        person_name: Full person name (Given Surname)
        birth_year: Birth year
        death_year: Death year
        maiden_name: Maiden name (for females)

    Returns:
        Dict with 'footnote', 'short_footnote', 'bibliography' keys
    """
    memorial_id = memorial_data.get('memorialId', '')
    url = memorial_data.get('url', f"https://www.findagrave.com/memorial/{memorial_id}")
    access_date = memorial_data.get('accessDate', datetime.now().strftime("%B %d, %Y"))

    # Cemetery location
    cemetery_name = memorial_data.get('cemeteryName', '')
    cemetery_city = memorial_data.get('cemeteryCity', '')
    cemetery_county = memorial_data.get('cemeteryCounty', '')
    cemetery_state = memorial_data.get('cemeteryState', '')
    cemetery_country = memorial_data.get('cemeteryCountry', '')

    # Build location string
    location_parts = []
    if cemetery_city:
        location_parts.append(cemetery_city)
    if cemetery_county:
        location_parts.append(f"{cemetery_county} County")
    if cemetery_state:
        location_parts.append(cemetery_state)
    if cemetery_country and cemetery_country != "USA":
        location_parts.append(cemetery_country)

    location_str = ", ".join(location_parts)

    # Format person name with maiden name in italics
    if maiden_name:
        person_display = person_name.replace(maiden_name, f"<i>{maiden_name}</i>")
    else:
        person_display = person_name

    # Build date range
    date_range = ""
    if birth_year and death_year:
        # Format: "15 Feb 1937–24 Nov 2021" (use memorial data if available)
        # For now, just use years
        date_range = f"{birth_year}–{death_year}"
    elif birth_year:
        date_range = f"{birth_year}–"
    elif death_year:
        date_range = f"d. {death_year}"

    # Creator and maintainer info (lowercase field names)
    created_by = memorial_data.get('createdBy', '')
    maintained_by = memorial_data.get('maintainedBy', '')

    contributor_parts = []

    # Parse "Originally Created by: Tim Gruber (47185765)" format
    if created_by:
        creator_match = created_by.replace("Originally Created by:", "").replace("Originally created by:", "").strip()
        if creator_match:
            contributor_parts.append(f"originally created by {creator_match}")

    # Parse "Maintained by: Debbie Day (47210776)" format
    if maintained_by:
        maintainer_match = maintained_by.replace("Maintained by:", "").strip()
        if maintainer_match:
            contributor_parts.append(f"maintained by {maintainer_match}")

    contributor_info = ""
    if contributor_parts:
        contributor_info = f"; {', '.join(contributor_parts)}"

    # FOOTNOTE
    # Format: Find a Grave, database and images (URL: accessed DATE),
    # memorial page for PERSON (DATES), Find a Grave Memorial ID XXXXX,
    # citing CEMETERY, LOCATION; CONTRIBUTOR.
    footnote = (
        f'<i>Find a Grave</i>, database and images ({url}: accessed {access_date}), '
        f'memorial page for {person_display} ({date_range}), '
        f'Find a Grave Memorial ID {memorial_id}'
    )

    if cemetery_name:
        footnote += f', citing {cemetery_name}'
        if location_str:
            footnote += f', {location_str}'

    if contributor_info:
        footnote += contributor_info

    footnote += '.'

    # SHORT FOOTNOTE
    # Format: Find a Grave, "PERSON" (YEARS), memorial #XXXXX.
    short_footnote = (
        f'<i>Find a Grave,</i> "{person_display}" ({birth_year or ""}–{death_year or ""}), '
        f'memorial #{memorial_id}.'
    )

    # BIBLIOGRAPHY
    # Format: Find a Grave. Database with images. URL : YEAR.
    access_year = datetime.now().year
    bibliography = (
        f'<i>Find a Grave</i>. Database with images. '
        f'{url} : {access_year}.'
    )

    return {
        'footnote': footnote,
        'short_footnote': short_footnote,
        'bibliography': bibliography,
    }


def generate_source_name(
    surname: str,
    given_name: str,
    maiden_name: str | None,
    birth_year: int | None,
    death_year: int | None,
    person_id: int,
) -> str:
    """
    Generate Find a Grave source name following RootsMagic pattern.

    Pattern: "Find a Grave: Surname, GivenName (MaidenName) (BirthYear-DeathYear) RIN PersonID"

    Args:
        surname: Person surname
        given_name: Person given name
        maiden_name: Maiden name (optional)
        birth_year: Birth year
        death_year: Death year
        person_id: RootsMagic Person ID (RIN)

    Returns:
        Formatted source name
    """
    # Build name part
    name_part = f"{surname}, {given_name}"

    if maiden_name:
        name_part += f" ({maiden_name})"

    # Build date part
    date_part = ""
    if birth_year and death_year:
        date_part = f" ({birth_year}-{death_year})"
    elif birth_year:
        date_part = f" ({birth_year}-)"
    elif death_year:
        date_part = f" (-{death_year})"

    return f"Find a Grave: {name_part}{date_part} RIN {person_id}"


def generate_image_filename(
    surname: str,
    given_name: str,
    maiden_name: str | None,
    birth_year: int | None,
    death_year: int | None,
) -> str:
    """
    Generate image filename for Find a Grave photos.

    Pattern: "Surname, GivenName (MaidenName) (BirthYear-DeathYear).jpg"

    Args:
        surname: Person surname
        given_name: Person given name
        maiden_name: Maiden name (optional, only for females)
        birth_year: Birth year
        death_year: Death year

    Returns:
        Filename (without extension)
    """
    # Build name part
    name_part = f"{surname}, {given_name}"

    if maiden_name:
        name_part += f" ({maiden_name})"

    # Build date part
    date_part = ""
    if birth_year and death_year:
        date_part = f" ({birth_year}-{death_year})"
    elif birth_year:
        date_part = f" ({birth_year}-)"
    elif death_year:
        date_part = f" (-{death_year})"

    return f"{name_part}{date_part}.jpg"
