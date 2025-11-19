"""
Database queries for Find a Grave batch processing.
"""

import re
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any
from pathlib import Path

from loguru import logger

try:
    from rmcitecraft.utils.gazetteer_search import GazetteerSearch
    GAZETTEER_AVAILABLE = True
except ImportError:
    GAZETTEER_AVAILABLE = False
    logger.warning("Gazetteer search not available - place validation disabled")


def find_findagrave_people(db_path: str, limit: int | None = None, offset: int = 0) -> dict[str, Any]:
    """
    Find all people with Find a Grave URLs but no associated formatted citations.

    Args:
        db_path: Path to RootsMagic database
        limit: Optional limit on number of results
        offset: Number of results to skip (for pagination)

    Returns:
        Dictionary with:
            - 'people': List of person dictionaries
            - 'total': Total count
            - 'examined': Number examined
            - 'excluded': Number excluded (already have citations)
    """
    from rmcitecraft.database.connection import connect_rmtree

    conn = connect_rmtree(db_path)
    cursor = conn.cursor()

    try:
        # Find all people with "Find a Grave" URLs
        cursor.execute("""
            SELECT
                u.LinkID,
                u.OwnerID as PersonID,
                u.URL,
                u.Note,
                n.Surname,
                n.Given,
                n.BirthYear,
                n.DeathYear,
                p.Sex
            FROM URLTable u
            JOIN PersonTable p ON u.OwnerID = p.PersonID
            JOIN NameTable n ON p.PersonID = n.OwnerID
            WHERE u.OwnerType = 0
            AND u.Name = 'Find a Grave'
            ORDER BY n.Surname COLLATE RMNOCASE, n.Given COLLATE RMNOCASE
        """)

        all_urls = cursor.fetchall()
        examined = len(all_urls)

        logger.info(f"Found {examined} people with Find a Grave URLs")

        # Filter out people who already have formatted citations
        people = []
        excluded = 0
        skipped = 0  # Track offset skipping

        for url_row in all_urls:
            (
                link_id,
                person_id,
                url,
                note,
                surname,
                given,
                birth_year,
                death_year,
                sex,
            ) = url_row

            # Check if person already has a Find a Grave source with formatted citations
            has_citation = _check_existing_citation(cursor, person_id)

            if has_citation:
                excluded += 1
                continue

            # Skip offset number of people
            if skipped < offset:
                skipped += 1
                continue

            # Extract memorial ID from URL
            memorial_id = _extract_memorial_id(url)

            people.append({
                'link_id': link_id,
                'person_id': person_id,
                'url': url,
                'note': note,
                'surname': surname,
                'given_name': given,
                'birth_year': birth_year,
                'death_year': death_year,
                'sex': sex,
                'memorial_id': memorial_id,
                'full_name': f"{given} {surname}",
            })

            if limit and len(people) >= limit:
                break

        logger.info(
            f"Find a Grave query: examined {examined}, "
            f"found {len(people)} without citations, excluded {excluded}"
        )

        return {
            'people': people,
            'total': len(people),
            'examined': examined,
            'excluded': excluded,
        }

    finally:
        conn.close()


def get_findagrave_people_by_ids(db_path: str, person_ids: list[int]) -> list[dict[str, Any]]:
    """
    Get Find a Grave information for specific people by their IDs.

    Used when resuming a batch session to reconstruct batch items.

    Args:
        db_path: Path to RootsMagic database
        person_ids: List of person IDs to retrieve

    Returns:
        List of person dictionaries with Find a Grave data
    """
    from rmcitecraft.database.connection import connect_rmtree

    if not person_ids:
        return []

    conn = connect_rmtree(db_path)
    cursor = conn.cursor()

    try:
        # Create placeholders for SQL IN clause
        placeholders = ','.join('?' * len(person_ids))

        # Query for people with their Find a Grave URLs
        cursor.execute(f"""
            SELECT
                u.LinkID,
                u.OwnerID as PersonID,
                u.URL,
                u.Note,
                n.Surname,
                n.Given,
                n.BirthYear,
                n.DeathYear,
                p.Sex
            FROM URLTable u
            JOIN PersonTable p ON u.OwnerID = p.PersonID
            JOIN NameTable n ON p.PersonID = n.OwnerID
            WHERE u.OwnerType = 0
            AND u.Name = 'Find a Grave'
            AND p.PersonID IN ({placeholders})
            ORDER BY n.Surname COLLATE RMNOCASE, n.Given COLLATE RMNOCASE
        """, person_ids)

        rows = cursor.fetchall()

        people = []
        for row in rows:
            (
                link_id,
                person_id,
                url,
                note,
                surname,
                given,
                birth_year,
                death_year,
                sex,
            ) = row

            # Extract memorial ID from URL
            memorial_id = _extract_memorial_id(url)

            people.append({
                'link_id': link_id,
                'person_id': person_id,
                'url': url,
                'note': note,
                'surname': surname,
                'given_name': given,
                'birth_year': birth_year,
                'death_year': death_year,
                'sex': sex,
                'memorial_id': memorial_id,
                'full_name': f"{given} {surname}",
            })

        logger.info(f"Retrieved {len(people)} people for resume operation")

        return people

    finally:
        conn.close()


def _check_existing_citation(cursor: sqlite3.Cursor, person_id: int) -> bool:
    """
    Check if person already has a Find a Grave source with formatted citations.

    This is the legacy check used during pre-filtering. For more robust duplicate
    detection during batch processing, use check_citation_exists_detailed().

    Args:
        cursor: Database cursor
        person_id: Person ID

    Returns:
        True if formatted citation exists, False otherwise
    """
    # Find sources linked to this person's events that are Find a Grave sources
    cursor.execute("""
        SELECT DISTINCT
            s.SourceID,
            s.TemplateID,
            s.Fields
        FROM EventTable e
        JOIN CitationLinkTable cl ON e.EventID = cl.OwnerID AND cl.OwnerType = 2
        JOIN CitationTable c ON cl.CitationID = c.CitationID
        JOIN SourceTable s ON c.SourceID = s.SourceID
        WHERE e.OwnerID = ?
        AND e.OwnerType = 0
        AND s.Name LIKE '%Find a Grave%'
        AND s.TemplateID = 0
    """, (person_id,))

    sources = cursor.fetchall()

    for source_row in sources:
        source_id, template_id, fields_blob = source_row

        if not fields_blob:
            continue

        # Parse Fields BLOB to check for formatted citations
        try:
            root = ET.fromstring(fields_blob.decode('utf-8'))

            # Check if Footnote exists and is not empty
            footnote_elem = root.find('.//Field[Name="Footnote"]/Value')
            if footnote_elem is not None and footnote_elem.text:
                # Check if it's an Evidence Explained format (not FamilySearch original)
                footnote = footnote_elem.text.strip()
                # Find a Grave citations start with "<i>Find a Grave</i>"
                if footnote.startswith('<i>Find a Grave</i>'):
                    logger.debug(f"Person {person_id} already has Find a Grave citation")
                    return True

        except Exception as e:
            logger.warning(f"Error parsing Fields BLOB for source {source_id}: {e}")
            continue

    return False


def check_citation_exists_detailed(
    db_path: str,
    person_id: int,
    memorial_id: str | None = None,
    memorial_url: str | None = None,
) -> dict[str, Any]:
    """
    Enhanced duplicate checking for Find a Grave citations during batch processing.

    Checks multiple criteria to detect existing citations:
    1. Person has formatted Find a Grave citation (legacy check)
    2. Citation with matching memorial ID in RefNumber field
    3. Citation with matching memorial URL in RefNumber field

    This is more robust than the pre-filter check and should be called
    BEFORE creating a citation during batch processing.

    Args:
        db_path: Path to RootsMagic database
        person_id: Person ID to check
        memorial_id: Optional memorial ID to check for duplicates
        memorial_url: Optional memorial URL to check for duplicates

    Returns:
        Dict with duplicate check results:
        {
            'exists': bool,  # True if any duplicate found
            'citation_id': int | None,  # Existing citation ID if found
            'source_id': int | None,  # Existing source ID if found
            'match_type': str | None,  # 'formatted', 'memorial_id', 'url'
            'details': str,  # Human-readable explanation
        }
    """
    from rmcitecraft.database.connection import connect_rmtree

    conn = connect_rmtree(db_path)
    try:
        cursor = conn.cursor()

        result = {
            'exists': False,
            'citation_id': None,
            'source_id': None,
            'match_type': None,
            'details': 'No existing citation found',
        }

        # Check 1: Legacy formatted citation check
        if _check_existing_citation(cursor, person_id):
            result['exists'] = True
            result['match_type'] = 'formatted'
            result['details'] = 'Person already has formatted Find a Grave citation'
            logger.info(f"Duplicate found for person {person_id}: {result['details']}")
            return result

        # Check 2 & 3: Check for memorial ID or URL in RefNumber field
        if memorial_id or memorial_url:
            # Build URL patterns to match
            url_patterns = []
            if memorial_url:
                url_patterns.append(memorial_url)
            if memorial_id:
                # Find a Grave URLs can be in multiple formats
                url_patterns.extend([
                    f"https://www.findagrave.com/memorial/{memorial_id}",
                    f"https://findagrave.com/memorial/{memorial_id}",
                    f"www.findagrave.com/memorial/{memorial_id}",
                    f"findagrave.com/memorial/{memorial_id}",
                ])

            # Query citations by RefNumber
            for pattern in url_patterns:
                cursor.execute("""
                    SELECT c.CitationID, c.SourceID, c.RefNumber
                    FROM CitationTable c
                    JOIN CitationLinkTable cl ON c.CitationID = cl.CitationID
                    JOIN EventTable e ON cl.OwnerID = e.EventID AND cl.OwnerType = 2
                    WHERE e.OwnerID = ? AND e.OwnerType = 0
                    AND c.RefNumber LIKE ?
                """, (person_id, f"%{pattern}%"))

                row = cursor.fetchone()
                if row:
                    citation_id, source_id, ref_number = row
                    result['exists'] = True
                    result['citation_id'] = citation_id
                    result['source_id'] = source_id
                    result['match_type'] = 'memorial_id' if memorial_id else 'url'
                    result['details'] = (
                        f"Citation {citation_id} already exists with matching memorial "
                        f"(RefNumber: {ref_number})"
                    )
                    logger.warning(
                        f"Duplicate citation found for person {person_id}, memorial {memorial_id}: "
                        f"CitationID {citation_id}"
                    )
                    return result

        return result
    finally:
        conn.close()


def _extract_memorial_id(url: str) -> str:
    """
    Extract memorial ID from Find a Grave URL.

    Args:
        url: Find a Grave URL

    Returns:
        Memorial ID or empty string
    """
    match = re.search(r'/memorial/(\d+)', url)
    return match.group(1) if match else ''


def get_utc_mod_date() -> int:
    """
    Get current UTC timestamp for RootsMagic UTCModDate fields.

    Returns:
        Integer Unix timestamp (seconds since epoch)
    """
    utc_now = datetime.now(timezone.utc)
    return int(utc_now.timestamp())


def _build_source_fields_xml(footnote: str, short_footnote: str, bibliography: str) -> str:
    """
    Build XML for SourceTable.Fields BLOB.

    For free-form sources (TemplateID=0), RootsMagic stores Footnote, ShortFootnote,
    and Bibliography in SourceTable.Fields as XML, not in CitationTable TEXT fields.

    Args:
        footnote: Full footnote citation
        short_footnote: Short form citation
        bibliography: Bibliography entry

    Returns:
        XML string for SourceTable.Fields BLOB
    """
    def escape_xml(text: str) -> str:
        """Escape special XML characters."""
        if not text:
            return ''
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&apos;')
        return text

    return f"""<Root><Fields>
<Field><Name>Footnote</Name><Value>{escape_xml(footnote)}</Value></Field>
<Field><Name>ShortFootnote</Name><Value>{escape_xml(short_footnote)}</Value></Field>
<Field><Name>Bibliography</Name><Value>{escape_xml(bibliography)}</Value></Field>
</Fields></Root>"""


def _build_citation_fields_xml() -> str:
    """
    Build XML for CitationTable.Fields BLOB.

    For free-form sources (TemplateID=0), citation fields are empty because
    all citation text is stored in SourceTable.Fields.

    Returns:
        Empty XML structure for CitationTable.Fields BLOB
    """
    return '<Root><Fields></Fields></Root>'


def validate_place_with_gazetteer(location_name: str) -> dict[str, Any]:
    """
    Validate a place location against the RootsMagic gazetteer (PlaceDB.dat).

    Parses the location into components and validates each against the worldwide
    gazetteer to verify spelling and existence.

    Args:
        location_name: Full location hierarchy (e.g., "Princeton, Mercer, New Jersey, United States")

    Returns:
        Dictionary with validation results:
        {
            'validated': bool,  # Overall validation status
            'confidence': str,  # 'high', 'medium', 'low'
            'components': {
                'city': {'name': str, 'exists': bool, 'fuzzy': bool},
                'county': {'name': str, 'exists': bool, 'fuzzy': bool},
                'state': {'name': str, 'exists': bool, 'fuzzy': bool},
                'country': {'name': str, 'exists': bool, 'fuzzy': bool}
            },
            'normalized_name': str,  # Corrected location name based on gazetteer
            'issues': list[str]  # Any validation issues found
        }
    """
    if not GAZETTEER_AVAILABLE:
        return {
            'validated': False,
            'confidence': 'low',
            'components': {},
            'normalized_name': location_name,
            'issues': ['Gazetteer validation not available']
        }

    try:
        gazetteer = GazetteerSearch()
        result = gazetteer.validate_location(location_name)

        # Log validation results for debugging
        if result.get('validated'):
            logger.debug(f"Place validated with {result['confidence']} confidence: {location_name}")
        else:
            logger.warning(f"Place validation failed: {location_name}")
            for issue in result.get('issues', []):
                logger.warning(f"  - {issue}")

        return result

    except Exception as e:
        logger.error(f"Error validating place with gazetteer: {e}")
        return {
            'validated': False,
            'confidence': 'low',
            'components': {},
            'normalized_name': location_name,
            'issues': [f'Error during validation: {str(e)}']
        }


def load_people_for_findagrave_batch(db_path: str) -> list[dict[str, Any]]:
    """
    Load people without Find a Grave citations (for batch processing).

    Looks for people who:
    1. Don't have a Find a Grave source (even if they have Find a Grave references)
    2. Have birth, death, or burial events

    Args:
        db_path: Path to RootsMagic database

    Returns:
        List of person dictionaries with:
            - person_id
            - surname
            - given_name
            - birth_year
            - death_year
            - memorial_id (if found in WebTagTable RefNumber field)
    """
    from rmcitecraft.database.connection import connect_rmtree

    conn = connect_rmtree(db_path, read_only=True)
    cursor = conn.cursor()

    try:
        # Query for people with birth, death, or burial events
        # but WITHOUT Find a Grave sources
        cursor.execute("""
            WITH person_names AS (
                SELECT
                    p.PersonID,
                    n.Surname,
                    n.Given,
                    n.IsPrimary
                FROM PersonTable p
                LEFT JOIN NameTable n ON p.PersonID = n.OwnerID
                WHERE n.IsPrimary = 1
            ),
            birth_years AS (
                SELECT
                    e.OwnerID AS PersonID,
                    SUBSTR(e.SortDate, 1, 4) AS BirthYear
                FROM EventTable e
                JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
                WHERE ft.Name = 'Birth' AND e.OwnerType = 0
            ),
            death_years AS (
                SELECT
                    e.OwnerID AS PersonID,
                    SUBSTR(e.SortDate, 1, 4) AS DeathYear
                FROM EventTable e
                JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
                WHERE ft.Name = 'Death' AND e.OwnerType = 0
            ),
            findagrave_sources AS (
                -- People who already have Find a Grave sources
                SELECT DISTINCT ct.PersonID
                FROM CitationTable c
                JOIN SourceTable s ON c.SourceID = s.SourceID
                JOIN CitationLinkTable cl ON c.CitationID = cl.CitationID
                JOIN (
                    -- Link to person directly or through events
                    SELECT cl2.CitationID, e.OwnerID AS PersonID
                    FROM CitationLinkTable cl2
                    JOIN EventTable e ON cl2.OwnerID = e.EventID AND cl2.OwnerType = 2
                    WHERE e.OwnerType = 0  -- Person events

                    UNION

                    SELECT cl2.CitationID, cl2.OwnerID AS PersonID
                    FROM CitationLinkTable cl2
                    WHERE cl2.OwnerType = 0  -- Direct person links
                ) ct ON cl.CitationID = ct.CitationID
                WHERE UPPER(s.Name) LIKE '%FIND A GRAVE%'
                   OR UPPER(s.Name) LIKE '%FINDAGRAVE%'
            ),
            memorial_ids AS (
                -- Extract memorial IDs from WebTagTable RefNumber field
                SELECT
                    wt.OwnerID AS PersonID,
                    wt.RefNumber AS MemorialID
                FROM WebTagTable wt
                WHERE wt.OwnerType = 0  -- Person
                  AND wt.URL LIKE '%findagrave.com%'
                  AND wt.RefNumber IS NOT NULL
                  AND wt.RefNumber != ''
            )
            SELECT
                pn.PersonID,
                pn.Surname,
                pn.Given AS GivenName,
                by.BirthYear,
                dy.DeathYear,
                mi.MemorialID
            FROM person_names pn
            LEFT JOIN birth_years by ON pn.PersonID = by.PersonID
            LEFT JOIN death_years dy ON pn.PersonID = dy.PersonID
            LEFT JOIN memorial_ids mi ON pn.PersonID = mi.PersonID
            LEFT JOIN findagrave_sources fs ON pn.PersonID = fs.PersonID
            WHERE fs.PersonID IS NULL  -- No Find a Grave source yet
              AND (by.BirthYear IS NOT NULL OR dy.DeathYear IS NOT NULL)  -- Has vital dates
            ORDER BY pn.Surname COLLATE RMNOCASE, pn.Given COLLATE RMNOCASE
        """)

        people = []
        for row in cursor.fetchall():
            people.append({
                'person_id': row[0],
                'surname': row[1] or '',
                'given_name': row[2] or '',
                'birth_year': row[3],
                'death_year': row[4],
                'memorial_id': row[5],
            })

        logger.info(f"Loaded {len(people)} people for Find a Grave batch processing")
        return people

    finally:
        conn.close()


def get_spouse_surname(db_path: str, person_id: int) -> str | None:
    """
    Get spouse's surname for a person (for women who may have changed names).

    Args:
        db_path: Path to RootsMagic database
        person_id: Person ID

    Returns:
        Spouse's surname or None if not found
    """
    from rmcitecraft.database.connection import connect_rmtree

    conn = connect_rmtree(db_path, read_only=True)
    cursor = conn.cursor()

    try:
        # Query for spouse surname through FamilyTable
        cursor.execute("""
            SELECT n.Surname
            FROM FamilyTable f
            JOIN NameTable n ON
                (f.FatherID = ? AND n.OwnerID = f.MotherID AND n.IsPrimary = 1)
                OR
                (f.MotherID = ? AND n.OwnerID = f.FatherID AND n.IsPrimary = 1)
            WHERE n.Surname IS NOT NULL AND n.Surname != ''
            ORDER BY f.FamilyID
            LIMIT 1
        """, (person_id, person_id))

        row = cursor.fetchone()
        return row[0] if row else None

    finally:
        conn.close()


def create_findagrave_source_and_citation(
    db_path: str,
    person_id: int,
    source_name: str,
    memorial_url: str,
    footnote: str,
    short_footnote: str,
    bibliography: str,
    memorial_text: str = '',
    source_comment: str = '',
) -> dict[str, int]:
    """
    Create Find a Grave source and citation in database.

    Args:
        db_path: Path to RootsMagic database
        person_id: Person ID
        source_name: Source name (e.g., "Find a Grave: Surname, GivenName...")
        memorial_url: Find a Grave memorial URL (stored in footnote, not in ref fields)
        footnote: Formatted footnote citation
        short_footnote: Formatted short footnote
        bibliography: Formatted bibliography
        memorial_text: Memorial text from Find a Grave (biography, veteran info, etc.)
        source_comment: Source comment (biographical summary, photos, family members)

    Returns:
        Dictionary with created IDs:
            - 'source_id': Created SourceID
            - 'citation_id': Created CitationID
    """
    from rmcitecraft.database.connection import connect_rmtree

    # Connect with read_only=False
    conn = connect_rmtree(db_path, read_only=False)
    cursor = conn.cursor()

    try:
        utc_mod_date = get_utc_mod_date()

        # Create source with formatted citations in Fields XML
        # Set TemplateID=0 (free-form source)
        cursor.execute("""
            INSERT INTO SourceTable (
                Name, RefNumber, ActualText, Comments, IsPrivate,
                TemplateID, Fields, UTCModDate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            source_name,
            '',  # RefNumber empty (URL is in footnote)
            memorial_text,  # ActualText = memorial biography (displays as "Source Text" in RM)
            source_comment,
            0,  # IsPrivate
            0,  # TemplateID = 0 for free-form source
            b'<Root><Fields></Fields></Root>',  # Empty Fields XML initially
            utc_mod_date,
        ))

        source_id = cursor.lastrowid
        logger.info(f"Created Find a Grave source ID {source_id}: {source_name}")

        # Now update the source with formatted citations in Fields XML
        # URL is already embedded in the formatted footnote, don't prepend it
        xml_content = _build_source_fields_xml(footnote, short_footnote, bibliography)

        cursor.execute("""
            UPDATE SourceTable
            SET Fields = ?
            WHERE SourceID = ?
        """, (xml_content.encode('utf-8'), source_id))

        # Create citation linking to person
        # For free-form sources, leave citation fields empty (they're in source)
        citation_fields_xml = _build_citation_fields_xml()

        cursor.execute("""
            INSERT INTO CitationTable (
                SourceID, Comments, ActualText, RefNumber,
                Footnote, ShortFootnote, Bibliography,
                Fields, UTCModDate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            source_id,
            '',  # Comments
            memorial_text,  # ActualText = memorial transcription
            '',  # RefNumber empty (URL is in footnote)
            '',  # Footnote empty for free-form source
            '',  # ShortFootnote empty for free-form source
            '',  # Bibliography empty for free-form source
            citation_fields_xml.encode('utf-8'),  # Empty Fields XML
            utc_mod_date,
        ))

        citation_id = cursor.lastrowid
        logger.info(f"Created Find a Grave citation ID {citation_id}")

        # NOTE: Citation is NOT automatically linked to person here.
        # Linking is done separately via create_burial_event_and_link_citation()
        # or link_citation_to_families() depending on workflow.

        conn.commit()
        logger.info(f"Successfully created Find a Grave source and citation for person ID {person_id}")

        return {
            'source_id': source_id,
            'citation_id': citation_id,
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to create Find a Grave source and citation: {e}", exc_info=True)
        raise

    finally:
        conn.close()


def create_burial_event_and_link_citation(
    db_path: str,
    person_id: int,
    citation_id: int,
    cemetery_name: str,
    cemetery_city: str,
    cemetery_county: str,
    cemetery_state: str,
    cemetery_country: str,
) -> dict[str, int | None]:
    """
    Create burial event for Find a Grave memorial and link citation to it.

    Args:
        db_path: Path to RootsMagic database
        person_id: Person ID
        citation_id: Citation ID to link to burial event
        cemetery_name: Cemetery name (e.g., "Mentor Municipal Cemetery")
        cemetery_city: City name
        cemetery_county: County name
        cemetery_state: State name
        cemetery_country: Country name

    Returns:
        Dictionary with created IDs:
            - 'burial_event_id': Created EventID
            - 'place_id': PlaceID for location (PlaceType=0)
            - 'cemetery_id': PlaceID for cemetery (PlaceType=2) or None
    """
    from rmcitecraft.database.connection import connect_rmtree
    from difflib import SequenceMatcher

    conn = connect_rmtree(db_path, read_only=False)
    cursor = conn.cursor()

    try:
        utc_mod_date = get_utc_mod_date()

        # 1. Build normalized location name (city, county, state, country)
        location_parts = []
        if cemetery_city:
            location_parts.append(cemetery_city)
        if cemetery_county:
            # Remove "County" suffix for matching (RootsMagic uses "Mercer" not "Mercer County")
            county_normalized = cemetery_county.replace(' County', '').replace(' Parish', '')
            location_parts.append(county_normalized)
        if cemetery_state:
            location_parts.append(cemetery_state)
        if cemetery_country:
            # Normalize country name (USA → United States)
            country_normalized = cemetery_country
            if cemetery_country in ('USA', 'US', 'U.S.A.', 'U.S.'):
                country_normalized = 'United States'
            location_parts.append(country_normalized)

        location_name = ", ".join(location_parts)

        if not location_name:
            logger.warning("No location information provided for burial event")
            return {
                'burial_event_id': None,
                'place_id': None,
                'cemetery_id': None,
            }

        # 2. Find or create location place (PlaceType=0)
        cursor.execute("""
            SELECT PlaceID, Name, Normalized
            FROM PlaceTable
            WHERE PlaceType = 0
            AND Normalized LIKE ?
        """, (f"%{cemetery_state}%",))  # Pre-filter by state

        place_id = None
        best_match_ratio = 0.0
        best_place_id = None
        best_place_name = None

        for row in cursor.fetchall():
            existing_place_id, existing_name, existing_normalized = row
            # Use normalized name for comparison
            compare_name = existing_normalized if existing_normalized else existing_name

            # Calculate similarity ratio
            ratio = SequenceMatcher(None, location_name.lower(), compare_name.lower()).ratio()

            if ratio > best_match_ratio:
                best_match_ratio = ratio
                best_place_id = existing_place_id
                best_place_name = existing_name

        # Require >95% match to use existing place
        if best_match_ratio >= 0.95:
            place_id = best_place_id
            logger.info(f"Found existing place: PlaceID {place_id} '{best_place_name}' (match: {best_match_ratio:.2%})")
        else:
            # Create new place
            # Build Reverse field (reversed hierarchy: "Country, State, County, City")
            reverse_parts = list(reversed(location_parts))
            reverse_name = ", ".join(reverse_parts)

            cursor.execute("""
                INSERT INTO PlaceTable (
                    PlaceType, Name, Normalized, Reverse, Latitude, Longitude,
                    MasterID, fsID, anID, UTCModDate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                0,  # PlaceType=0 for location
                location_name,
                location_name,  # Normalized same as Name
                reverse_name,  # Reverse hierarchy
                0,  # Latitude (0, not NULL)
                0,  # Longitude (0, not NULL)
                0,  # MasterID (0 for top-level location)
                0,  # fsID (0, not NULL)
                0,  # anID (0, not NULL)
                utc_mod_date,
            ))

            place_id = cursor.lastrowid
            logger.info(f"Created new place: PlaceID {place_id} - {location_name}")
            if best_place_name:
                logger.info(f"  (Best existing match was '{best_place_name}' at {best_match_ratio:.1%}, below 95% threshold)")

        # 3. Find or create cemetery (PlaceType=2)
        cemetery_id = None
        if cemetery_name:
            # Search for existing cemetery
            cursor.execute("""
                SELECT PlaceID
                FROM PlaceTable
                WHERE PlaceType = 2
                AND Name = ?
                AND MasterID = ?
            """, (cemetery_name, place_id))

            existing_cemetery = cursor.fetchone()

            if existing_cemetery:
                cemetery_id = existing_cemetery[0]
                logger.info(f"Found existing cemetery: PlaceID {cemetery_id}")
            else:
                # Create new cemetery linked to location
                cursor.execute("""
                    INSERT INTO PlaceTable (
                        PlaceType, Name, Normalized, Reverse, Latitude, Longitude,
                        MasterID, fsID, anID, UTCModDate
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    2,  # PlaceType=2 for cemetery
                    cemetery_name,
                    cemetery_name,  # Same as Name for cemeteries
                    cemetery_name,  # Reverse same as Name for cemeteries
                    0,  # Latitude (0, not NULL)
                    0,  # Longitude (0, not NULL)
                    place_id,  # Link to parent location
                    0,  # fsID (0, not NULL)
                    0,  # anID (0, not NULL)
                    utc_mod_date,
                ))

                cemetery_id = cursor.lastrowid
                logger.info(f"Created cemetery: PlaceID {cemetery_id} - {cemetery_name}")

        # 4. Get death date for burial "after" date
        cursor.execute("""
            SELECT Date
            FROM EventTable
            WHERE OwnerID = ?
            AND OwnerType = 0
            AND EventType = 2
        """, (person_id,))

        death_event = cursor.fetchone()
        burial_date = ""
        sort_date = 0

        if death_event and death_event[0]:
            # Extract date from death event (format: D.+YYYYMMDD..)
            death_date_str = death_event[0]
            if '+' in death_date_str:
                # Extract YYYYMMDD portion
                date_part = death_date_str.split('+')[1].split('.')[0]
                if date_part and len(date_part) >= 8:
                    # Check if death date is precise (has day, not just year or year-month)
                    # Format: YYYYMMDD
                    month = date_part[4:6]
                    day = date_part[6:8]

                    # Only use date if both month and day are specified (non-zero)
                    if month != "00" and day != "00":
                        # RootsMagic "after" date format: DA+YYYYMMDD..+00000000..
                        # Position 2 'A' = After modifier
                        burial_date = f"DA+{date_part}..+00000000.."

                        # SortDate = death date + 1 day (for chronological sorting)
                        from datetime import datetime, timedelta
                        death_dt = datetime.strptime(date_part, "%Y%m%d")
                        burial_dt = death_dt + timedelta(days=1)
                        sort_date = int(burial_dt.strftime("%Y%m%d"))

                        logger.info(f"Burial date (after death): {burial_date}, SortDate: {sort_date}")
                    else:
                        logger.info(f"Death date not precise (YYYY-MM-DD: {date_part[:4]}-{month}-{day}), leaving burial date blank")

        # 5. Look up Burial FactTypeID
        cursor.execute("""
            SELECT FactTypeID FROM FactTypeTable
            WHERE Name = 'Burial'
        """)
        burial_fact_type = cursor.fetchone()
        if not burial_fact_type:
            raise ValueError("Burial fact type not found in database")
        burial_fact_type_id = burial_fact_type[0]

        # 6. Check if person already has a burial event
        cursor.execute("""
            SELECT EventID FROM EventTable
            WHERE OwnerID = ? AND OwnerType = 0 AND EventType = ?
        """, (person_id, burial_fact_type_id))
        existing_burial = cursor.fetchone()

        if existing_burial:
            burial_event_id = existing_burial[0]
            logger.info(f"Person {person_id} already has burial event ID {burial_event_id}")
        else:
            # Create new burial event with PlaceID and SiteID
            cursor.execute("""
                INSERT INTO EventTable (
                    EventType, OwnerType, OwnerID, Date, SortDate,
                    PlaceID, SiteID, Details, IsPrimary, IsPrivate,
                    Proof, Status, Sentence, UTCModDate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                burial_fact_type_id,
                0,  # OwnerType = 0 for PersonTable
                person_id,
                burial_date,  # Date string (DA+ prefix for "after")
                sort_date,  # SortDate for chronological sorting
                place_id,  # PlaceID = location
                cemetery_id if cemetery_id else 0,  # SiteID = cemetery
                "",  # Details (empty)
                0,  # IsPrimary
                0,  # IsPrivate
                0,  # Proof
                0,  # Status
                '',  # Sentence
                utc_mod_date,
            ))

            burial_event_id = cursor.lastrowid
            logger.info(f"Created burial event ID {burial_event_id} for person {person_id}")

        # 7. Link citation to burial event
        cursor.execute("""
            INSERT OR IGNORE INTO CitationLinkTable (
                CitationID, OwnerType, OwnerID, SortOrder, Quality, IsPrivate, Flags, UTCModDate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            citation_id,
            2,  # OwnerType = 2 for EventTable
            burial_event_id,
            0,  # SortOrder
            '~~~',  # Quality: default rating
            0,  # IsPrivate
            0,  # Flags
            utc_mod_date,
        ))

        logger.info(f"Linked CitationID {citation_id} to burial EventID {burial_event_id}")

        conn.commit()
        logger.info(f"Successfully created/linked burial event {burial_event_id} with citation {citation_id}")

        return {
            'burial_event_id': burial_event_id,
            'place_id': place_id,
            'cemetery_id': cemetery_id,
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to create burial event: {e}", exc_info=True)
        raise

    finally:
        conn.close()


def link_citation_to_families(
    db_path: str,
    person_id: int,
    citation_id: int,
) -> list[int]:
    """
    Link Find a Grave citation to all families where person is parent.

    Args:
        db_path: Path to RootsMagic database
        person_id: Person ID
        citation_id: Citation ID to link to families

    Returns:
        List of family IDs that were linked
    """
    from rmcitecraft.database.connection import connect_rmtree

    conn = connect_rmtree(db_path, read_only=False)
    cursor = conn.cursor()

    try:
        utc_mod_date = get_utc_mod_date()

        # Find all families where person is a parent
        cursor.execute("""
            SELECT FamilyID FROM FamilyTable
            WHERE FatherID = ? OR MotherID = ?
        """, (person_id, person_id))

        family_ids = []
        for row in cursor.fetchall():
            family_id = row[0]

            # Check if link already exists
            cursor.execute("""
                SELECT LinkID FROM CitationLinkTable
                WHERE CitationID = ? AND OwnerType = 1 AND OwnerID = ?
            """, (citation_id, family_id))

            if cursor.fetchone():
                logger.debug(f"Citation {citation_id} already linked to family {family_id}, skipping")
                continue

            # Link citation to family (OwnerType = 1 for FamilyTable)
            cursor.execute("""
                INSERT INTO CitationLinkTable (
                    CitationID, OwnerType, OwnerID, SortOrder, Quality, IsPrivate, Flags, UTCModDate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                citation_id,
                1,  # OwnerType = 1 for FamilyTable
                family_id,
                0,  # SortOrder: 0 for consistency with recent records
                '~~~',  # Quality: default rating (no specific rating provided)
                0,  # IsPrivate
                0,  # Flags
                utc_mod_date,
            ))

            family_ids.append(family_id)

        conn.commit()

        if family_ids:
            logger.info(f"Linked citation {citation_id} to {len(family_ids)} families")
        else:
            logger.info(f"No families found for person {person_id}")

        return family_ids

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to link citation to families: {e}", exc_info=True)
        raise

    finally:
        conn.close()


def get_names_by_surname(db_path: str, surname: str, given_name: str | None = None) -> list[dict[str, Any]]:
    """
    Get all names in database matching surname (and optionally given name).

    Used for spouse name matching in Find a Grave batch processing.

    Args:
        db_path: Path to RootsMagic database
        surname: Surname to search for
        given_name: Optional given name to filter by

    Returns:
        List of name dictionaries with:
            - person_id
            - surname
            - given_name
            - birth_year
            - death_year
    """
    from rmcitecraft.database.connection import connect_rmtree

    conn = connect_rmtree(db_path, read_only=True)
    cursor = conn.cursor()

    try:
        # Build query based on whether given name is provided
        if given_name:
            # Strip parenthetical info for comparison
            given_base = re.sub(r'\s*\([^)]*\)', '', given_name).strip()

            # Search for exact surname and similar given name
            cursor.execute("""
                WITH birth_years AS (
                    SELECT
                        e.OwnerID AS PersonID,
                        SUBSTR(e.SortDate, 1, 4) AS BirthYear
                    FROM EventTable e
                    JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
                    WHERE ft.Name = 'Birth' AND e.OwnerType = 0
                ),
                death_years AS (
                    SELECT
                        e.OwnerID AS PersonID,
                        SUBSTR(e.SortDate, 1, 4) AS DeathYear
                    FROM EventTable e
                    JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
                    WHERE ft.Name = 'Death' AND e.OwnerType = 0
                )
                SELECT
                    n.OwnerID AS PersonID,
                    n.Surname,
                    n.Given,
                    by.BirthYear,
                    dy.DeathYear
                FROM NameTable n
                LEFT JOIN birth_years by ON n.OwnerID = by.PersonID
                LEFT JOIN death_years dy ON n.OwnerID = dy.PersonID
                WHERE n.IsPrimary = 1
                  AND n.Surname COLLATE RMNOCASE = ?
                  AND (
                      n.Given COLLATE RMNOCASE = ?
                      OR n.Given COLLATE RMNOCASE LIKE ?
                      OR n.Given COLLATE RMNOCASE LIKE ?
                  )
                ORDER BY
                    CASE WHEN n.Given COLLATE RMNOCASE = ? THEN 0 ELSE 1 END,
                    n.Given COLLATE RMNOCASE
            """, (
                surname,
                given_base,
                f"{given_base}%",  # Starts with given name
                f"% {given_base}%",  # Contains given name as middle/last
                given_base,  # For ordering exact matches first
            ))
        else:
            # Just search by surname
            cursor.execute("""
                WITH birth_years AS (
                    SELECT
                        e.OwnerID AS PersonID,
                        SUBSTR(e.SortDate, 1, 4) AS BirthYear
                    FROM EventTable e
                    JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
                    WHERE ft.Name = 'Birth' AND e.OwnerType = 0
                ),
                death_years AS (
                    SELECT
                        e.OwnerID AS PersonID,
                        SUBSTR(e.SortDate, 1, 4) AS DeathYear
                    FROM EventTable e
                    JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
                    WHERE ft.Name = 'Death' AND e.OwnerType = 0
                )
                SELECT
                    n.OwnerID AS PersonID,
                    n.Surname,
                    n.Given,
                    by.BirthYear,
                    dy.DeathYear
                FROM NameTable n
                LEFT JOIN birth_years by ON n.OwnerID = by.PersonID
                LEFT JOIN death_years dy ON n.OwnerID = dy.PersonID
                WHERE n.IsPrimary = 1
                  AND n.Surname COLLATE RMNOCASE = ?
                ORDER BY n.Given COLLATE RMNOCASE
            """, (surname,))

        results = []
        for row in cursor.fetchall():
            results.append({
                'person_id': row[0],
                'surname': row[1] or '',
                'given_name': row[2] or '',
                'birth_year': row[3],
                'death_year': row[4],
            })

        logger.info(f"Found {len(results)} people with surname '{surname}'")
        return results

    finally:
        conn.close()


def create_location_and_cemetery(
    db_path: str,
    burial_event_id: int,
    cemetery_name: str,
    cemetery_location: str,
) -> dict[str, int]:
    """
    Create location and cemetery places in database, linked to burial event.

    Creates two PlaceTable records:
    1. Location (city/county/state)
    2. Cemetery (linked to location via MasterID)

    Args:
        db_path: Path to RootsMagic database
        burial_event_id: Burial event ID to link cemetery to
        cemetery_name: Cemetery name
        cemetery_location: Location string (e.g., "Princeton, Mercer, New Jersey, United States")

    Returns:
        Dictionary with created IDs:
            - 'location_id': Created location PlaceID
            - 'cemetery_id': Created cemetery PlaceID
    """
    from rmcitecraft.database.connection import connect_rmtree

    conn = connect_rmtree(db_path, read_only=False)
    cursor = conn.cursor()

    try:
        utc_mod_date = get_utc_mod_date()

        # First, create the location (city/county/state)
        # PlaceType: 0 = Place, 2 = Place Detail
        # For locations, use PlaceType = 0

        # Reverse the location for the Reverse field (RootsMagic convention)
        # "Princeton, Mercer, New Jersey, United States" -> "United States, New Jersey, Mercer, Princeton"
        parts = [p.strip() for p in cemetery_location.split(',')]
        reverse_location = ', '.join(reversed(parts))

        # Normalize location (expand county abbreviations)
        normalized_location = cemetery_location
        if 'Co.' in cemetery_location:
            normalized_location = cemetery_location.replace(' Co.', ' County')

        cursor.execute("""
            INSERT INTO PlaceTable (
                PlaceType, Name, Abbrev, Normalized, Latitude, Longitude,
                LatLongExact, MasterID, Reverse, Note, fsID, anID, UTCModDate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            0,  # PlaceType = 0 for Place
            cemetery_location,  # Name
            '',  # Abbrev (empty)
            normalized_location,  # Normalized
            0,  # Latitude (0 = unknown)
            0,  # Longitude (0 = unknown)
            0,  # LatLongExact (0 = not exact)
            0,  # MasterID (0 = this is a master location)
            reverse_location,  # Reverse
            '',  # Note (empty)
            0,  # fsID (FamilySearch ID - 0 = none)
            0,  # anID (Ancestry ID - 0 = none)
            utc_mod_date,
        ))

        location_id = cursor.lastrowid
        logger.info(f"Created location PlaceID {location_id}: {cemetery_location}")

        # Now create the cemetery (place detail)
        # PlaceType: 2 = Place Detail
        # MasterID links to the location we just created

        cursor.execute("""
            INSERT INTO PlaceTable (
                PlaceType, Name, Abbrev, Normalized, Latitude, Longitude,
                LatLongExact, MasterID, Reverse, Note, fsID, anID, UTCModDate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            2,  # PlaceType = 2 for Place Detail
            cemetery_name,  # Name
            '',  # Abbrev (empty)
            cemetery_name,  # Normalized
            0,  # Latitude (0 = unknown)
            0,  # Longitude (0 = unknown)
            0,  # LatLongExact (0 = not exact)
            location_id,  # MasterID links to location
            None,  # Reverse (NULL for place details, not empty string)
            '',  # Note (empty)
            None,  # fsID (NULL for cemeteries - no FamilySearch link)
            None,  # anID (NULL for cemeteries - no Ancestry link)
            utc_mod_date,
        ))

        cemetery_id = cursor.lastrowid
        logger.info(f"Created cemetery PlaceID {cemetery_id}: {cemetery_name} (linked to location {location_id})")

        # Link location to burial event
        # NOTE: Event PlaceID should reference the location (PlaceType=0), not cemetery (PlaceType=2)
        # Cemetery is linked via its MasterID pointing to the location
        cursor.execute("""
            UPDATE EventTable
            SET PlaceID = ?, UTCModDate = ?
            WHERE EventID = ?
        """, (location_id, utc_mod_date, burial_event_id))

        conn.commit()
        logger.info(f"Successfully created location and cemetery places for burial event {burial_event_id}")

        return {
            'location_id': location_id,
            'cemetery_id': cemetery_id,
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to create location and cemetery: {e}", exc_info=True)
        raise

    finally:
        conn.close()


def create_cemetery_for_existing_location(
    db_path: str,
    burial_event_id: int,
    cemetery_name: str,
    location_id: int,
) -> int:
    """
    Create cemetery place detail for an existing location.

    Args:
        db_path: Path to RootsMagic database
        burial_event_id: Burial event ID to link cemetery to
        cemetery_name: Cemetery name
        location_id: Existing location PlaceID to link cemetery to

    Returns:
        Created cemetery PlaceID
    """
    from rmcitecraft.database.connection import connect_rmtree

    conn = connect_rmtree(db_path, read_only=False)
    cursor = conn.cursor()

    try:
        utc_mod_date = get_utc_mod_date()

        # Create the cemetery (place detail) linked to existing location
        cursor.execute("""
            INSERT INTO PlaceTable (
                PlaceType, Name, Abbrev, Normalized, Latitude, Longitude,
                LatLongExact, MasterID, Reverse, Note, fsID, anID, UTCModDate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            2,  # PlaceType = 2 for Place Detail
            cemetery_name,  # Name
            '',  # Abbrev (empty)
            cemetery_name,  # Normalized
            0,  # Latitude (0 = unknown)
            0,  # Longitude (0 = unknown)
            0,  # LatLongExact (0 = not exact)
            location_id,  # MasterID links to existing location
            None,  # Reverse (NULL for place details, not empty string)
            '',  # Note (empty)
            None,  # fsID (NULL for cemeteries - no FamilySearch link)
            None,  # anID (NULL for cemeteries - no Ancestry link)
            utc_mod_date,
        ))

        cemetery_id = cursor.lastrowid
        logger.info(f"Created cemetery PlaceID {cemetery_id}: {cemetery_name} (linked to location {location_id})")

        # Link location to burial event
        # NOTE: Event PlaceID should reference the location (PlaceType=0), not cemetery (PlaceType=2)
        # Cemetery is linked via its MasterID pointing to the location
        cursor.execute("""
            UPDATE EventTable
            SET PlaceID = ?, UTCModDate = ?
            WHERE EventID = ?
        """, (location_id, utc_mod_date, burial_event_id))

        conn.commit()

        return cemetery_id

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to create cemetery: {e}", exc_info=True)
        raise

    finally:
        conn.close()


def convert_path_to_rootsmagic_format(absolute_path: str | Path, media_root: str | Path) -> str:
    """
    Convert absolute file path to RootsMagic's symbolic path format.

    RootsMagic uses symbolic prefixes:
    - ? = Media folder (configured in RootsMagic)
    - ~ = User's home directory
    - * = Database folder

    Args:
        absolute_path: Absolute file path to convert
        media_root: RootsMagic media root directory

    Returns:
        Relative path with RootsMagic symbolic prefix

    Examples:
        /Users/miams/Genealogy/RootsMagic/Files/Pictures - People/file.jpg
        -> ?/Pictures - People/file.jpg
    """
    abs_path = Path(absolute_path).resolve()
    media_root_path = Path(media_root).resolve()

    try:
        # Check if path is under media root
        relative_path = abs_path.relative_to(media_root_path)
        # Convert to forward slashes (RootsMagic convention)
        return f"?/{relative_path.as_posix()}"
    except ValueError:
        # Path is not under media root, use home directory relative
        home_path = Path.home()
        try:
            relative_path = abs_path.relative_to(home_path)
            return f"~/{relative_path.as_posix()}"
        except ValueError:
            # Use absolute path as fallback
            return str(abs_path)


def create_findagrave_image_record(
    db_path: str,
    citation_id: int,
    person_id: int,
    image_path: str,
    photo_type: str = '',
    memorial_id: str = '',
    photo_id: str = '',
    contributor: str = '',
    person_name: str = '',
    cemetery_name: str = '',
    cemetery_city: str = '',
    cemetery_county: str = '',
    cemetery_state: str = '',
    media_root: str | None = None,
) -> dict[str, int]:
    """
    Create Find a Grave image record in database and link to citation.

    Args:
        db_path: Path to RootsMagic database
        citation_id: Citation ID to link image to
        person_id: Person ID to link image to (for Person/Family types)
        image_path: Absolute path to downloaded image file
        photo_type: Type of photo (Person, Grave, Family, Document, Cemetery, Other)
        memorial_id: Find a Grave memorial ID
        photo_id: Find a Grave photo ID (for photo-specific URL)
        contributor: Photo contributor name and ID from Find a Grave (e.g., "Joseph Testerman (51206732)")
        person_name: Person name as displayed on FindaGrave (for caption)
        cemetery_name: Cemetery name (for Grave/Cemetery captions)
        cemetery_city: Cemetery city (for Grave/Cemetery captions)
        cemetery_county: Cemetery county (for Grave/Cemetery captions)
        cemetery_state: Cemetery state (for Grave/Cemetery captions)
        media_root: RootsMagic media root directory (for path conversion)

    Returns:
        Dictionary with created IDs:
            - 'media_id': Created MediaID
            - 'media_link_id': Created MediaLinkID
    """
    from rmcitecraft.database.connection import connect_rmtree
    from rmcitecraft.database.image_repository import ImageRepository

    conn = connect_rmtree(db_path, read_only=False)

    try:
        # Get media root from config if not provided
        if not media_root:
            from rmcitecraft.config import get_config
            config = get_config()
            media_root = config.rm_media_root_directory

        # Convert absolute path to RootsMagic format
        image_path = Path(image_path)

        # Get the directory path (without filename) in RootsMagic format
        directory_path = convert_path_to_rootsmagic_format(image_path.parent, media_root)

        # Extract just the filename for MediaFile field
        media_file = image_path.name

        # Remap "Flower" to "Other" (legacy category removal)
        if photo_type and photo_type.lower() in ['flower', 'flowers']:
            photo_type = 'Other'
            logger.warning(f"Remapped deprecated 'Flower' photo type to 'Other' for {media_file}")

        # Generate caption based on photo type
        if photo_type == 'Grave':
            # FindaGrave-Grave: Forest Lawn Cemetery, Detroit, Wayne, Michigan
            location_parts = [cemetery_name]
            if cemetery_city:
                location_parts.append(cemetery_city)
            if cemetery_county:
                location_parts.append(cemetery_county)
            if cemetery_state:
                location_parts.append(cemetery_state)
            caption = f"FindaGrave-Grave: {', '.join(filter(None, location_parts))}"

        elif photo_type == 'Person':
            # FindaGrave-Person: I Walter Iams
            caption = f"FindaGrave-Person: {person_name}"

        elif photo_type == 'Family':
            # FindaGrave-Family: Family of I Walter Iams
            caption = f"FindaGrave-Family: Family of {person_name}"

        elif photo_type == 'Document':
            # FindaGrave-Document: Document of I Walter Iams
            caption = f"FindaGrave-Document: Document of {person_name}"

        elif photo_type == 'Cemetery':
            # FindaGrave-Cemetery: Forest Lawn Cemetery, Detroit, Wayne, Michigan
            location_parts = [cemetery_name]
            if cemetery_city:
                location_parts.append(cemetery_city)
            if cemetery_county:
                location_parts.append(cemetery_county)
            if cemetery_state:
                location_parts.append(cemetery_state)
            caption = f"FindaGrave-Cemetery: {', '.join(filter(None, location_parts))}"

        elif photo_type == 'Other' or not photo_type:
            # FindaGrave-Other
            caption = "FindaGrave-Other"

        else:
            # Unknown type - default to Other
            logger.warning(f"Unknown photo type '{photo_type}' for {media_file}, defaulting to Other")
            caption = "FindaGrave-Other"

        # Create image repository
        img_repo = ImageRepository(conn)

        # Check for existing images with old caption format
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MediaID, Caption, MediaFile
            FROM MultimediaTable
            WHERE MediaFile = ?
        """, (media_file,))

        existing_image = cursor.fetchone()
        if existing_image:
            existing_id, existing_caption, existing_file = existing_image
            # Check if existing caption uses old format
            if existing_caption and not existing_caption.startswith('FindaGrave-'):
                error_msg = (
                    f"ERROR: Existing image found with old caption format!\n"
                    f"  File: {existing_file}\n"
                    f"  Media ID: {existing_id}\n"
                    f"  Old Caption: {existing_caption}\n"
                    f"  New Caption: {caption}\n"
                    f"  Action: This image will be skipped. Please manually update the caption in RootsMagic."
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg)

        # Generate description field with FindaGrave attribution
        # Format: Photo courtesy of Findagrave and Joseph Testerman (51206732), (https://www.findagrave.com/memorial/204551436/jack-louis-iams#view-photo=251750095 : downloaded November 18, 2025)
        from datetime import datetime
        download_date = datetime.now().strftime('%B %d, %Y')

        # Build photo-specific URL
        photo_url = f"https://www.findagrave.com/memorial/{memorial_id}"
        if photo_id:
            photo_url += f"#view-photo={photo_id}"

        # Build description with contributor attribution
        description = f"Photo courtesy of Findagrave"
        if contributor:
            description += f" and {contributor}"
        description += f", ({photo_url} : downloaded {download_date})"

        # Create media record
        media_id = img_repo.create_media_record(
            media_path=directory_path,
            media_file=media_file,
            caption=caption,
            ref_number=f"https://www.findagrave.com/memorial/{memorial_id}" if memorial_id else '',
            census_date='',  # Find a Grave photos don't have census dates
            description=description,
        )

        # Link to citation (always)
        media_link_id = img_repo.link_media_to_citation(media_id, citation_id)

        # Conditional linking based on photo type
        cursor = conn.cursor()

        # Link to burial event if Grave or Cemetery type
        if photo_type in ['Grave', 'Cemetery']:
            cursor.execute("""
                SELECT cl.OwnerID
                FROM CitationLinkTable cl
                WHERE cl.CitationID = ? AND cl.OwnerType = 2
                LIMIT 1
            """, (citation_id,))
            row = cursor.fetchone()

            if row:
                burial_event_id = row[0]
                img_repo.link_media_to_event(media_id, burial_event_id)
                logger.info(f"Linked image to burial event ID {burial_event_id}")
            else:
                logger.warning(
                    f"Failed to link photo to burial event, because burial event not found "
                    f"in RootsMagic database for PersonID {person_id} (citation {citation_id})"
                )

        # Link to person if Person or Family type
        if photo_type in ['Person', 'Family']:
            img_repo.link_media_to_person(media_id, person_id)
            logger.info(f"Linked image to person ID {person_id}")

        conn.commit()
        logger.info(f"Created Find a Grave image record: MediaID {media_id} for {media_file}")

        return {
            'media_id': media_id,
            'media_link_id': media_link_id,
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to create Find a Grave image record: {e}", exc_info=True)
        raise

    finally:
        conn.close()