"""
Database queries for Find a Grave batch processing.
"""

import re
import sqlite3
import xml.etree.ElementTree as ET
from typing import Any

from loguru import logger


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


def _check_existing_citation(cursor: sqlite3.Cursor, person_id: int) -> bool:
    """
    Check if person already has a Find a Grave source with formatted citations.

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
    from datetime import datetime, timezone

    conn = connect_rmtree(db_path)
    cursor = conn.cursor()

    try:
        # Get current UTC timestamp for RootsMagic
        utc_now = datetime.now(timezone.utc)
        utc_mod_date = int(utc_now.timestamp())

        # Create XML for SourceTable.Fields (free-form source, TemplateID=0)
        source_fields_xml = _build_source_fields_xml(footnote, short_footnote, bibliography)

        # Insert Source record
        cursor.execute("""
            INSERT INTO SourceTable (
                TemplateID,
                Name,
                RefNumber,
                ActualText,
                Comments,
                Fields,
                UTCModDate
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            0,  # TemplateID=0 for free-form sources
            source_name,
            '',  # RefNumber (blank - URL is in footnote)
            memorial_text,  # ActualText (memorial biography/veteran info)
            source_comment,  # Comments (biographical summary, photos, family)
            source_fields_xml.encode('utf-8'),  # Fields BLOB
            utc_mod_date,
        ))

        source_id = cursor.lastrowid
        logger.info(f"Created SourceID {source_id}: {source_name}")

        # Create XML for CitationTable.Fields (empty for Find a Grave)
        citation_fields_xml = _build_citation_fields_xml()

        # Insert Citation record
        cursor.execute("""
            INSERT INTO CitationTable (
                SourceID,
                Comments,
                ActualText,
                RefNumber,
                Footnote,
                ShortFootnote,
                Bibliography,
                Fields,
                CitationName,
                UTCModDate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            source_id,
            '',  # Comments
            '',  # ActualText (not used for free-form)
            '',  # RefNumber (blank - URL is in footnote)
            '',  # Footnote (stored in SourceTable.Fields for TemplateID=0)
            '',  # ShortFootnote (stored in SourceTable.Fields)
            '',  # Bibliography (stored in SourceTable.Fields)
            citation_fields_xml.encode('utf-8'),  # Fields BLOB
            source_name,  # CitationName (same as source name)
            utc_mod_date,
        ))

        citation_id = cursor.lastrowid
        logger.info(f"Created CitationID {citation_id} for SourceID {source_id}")

        conn.commit()

        return {
            'source_id': source_id,
            'citation_id': citation_id,
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to create source/citation: {e}", exc_info=True)
        raise

    finally:
        conn.close()


def _build_source_fields_xml(footnote: str, short_footnote: str, bibliography: str) -> str:
    """
    Build XML for SourceTable.Fields (free-form source).

    Args:
        footnote: Formatted footnote citation
        short_footnote: Formatted short footnote
        bibliography: Formatted bibliography

    Returns:
        XML string for Fields BLOB
    """
    # RootsMagic stores free-form citation fields in XML format
    root = ET.Element('Root')
    fields = ET.SubElement(root, 'Fields')

    # Footnote field
    footnote_field = ET.SubElement(fields, 'Field')
    footnote_name = ET.SubElement(footnote_field, 'Name')
    footnote_name.text = 'Footnote'
    footnote_value = ET.SubElement(footnote_field, 'Value')
    footnote_value.text = footnote

    # ShortFootnote field
    short_field = ET.SubElement(fields, 'Field')
    short_name = ET.SubElement(short_field, 'Name')
    short_name.text = 'ShortFootnote'
    short_value = ET.SubElement(short_field, 'Value')
    short_value.text = short_footnote

    # Bibliography field
    bib_field = ET.SubElement(fields, 'Field')
    bib_name = ET.SubElement(bib_field, 'Name')
    bib_name.text = 'Bibliography'
    bib_value = ET.SubElement(bib_field, 'Value')
    bib_value.text = bibliography

    # Convert to string (RootsMagic expects compact XML)
    return ET.tostring(root, encoding='unicode')


def _build_citation_fields_xml() -> str:
    """
    Build XML for CitationTable.Fields (empty for Find a Grave citations).

    Find a Grave citations store all information in the footnote text.
    The URL is not stored in reference fields.

    Returns:
        XML string for Fields BLOB (empty fields structure)
    """
    root = ET.Element('Root')
    ET.SubElement(root, 'Fields')  # Empty Fields element

    return ET.tostring(root, encoding='unicode')
