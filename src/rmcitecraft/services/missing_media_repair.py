"""
Service to download and link missing 1930 Census images.

This is temporary repair code to process sources that have FamilySearch URLs
in their footnotes but no media attached.
"""

import asyncio
import re
import time
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from rmcitecraft.database.connection import connect_rmtree
from rmcitecraft.database.image_repository import ImageRepository
from rmcitecraft.services.familysearch_automation import FamilySearchAutomation


@dataclass
class SourceMediaInfo:
    """Information about a source needing media."""
    source_id: int
    source_name: str
    state: str
    county: str
    surname: str
    given_name: str
    familysearch_url: str
    citation_id: int | None
    event_id: int | None
    person_id: int | None
    person_given: str | None
    person_surname: str | None


def extract_url_from_fields(fields_blob: bytes | None) -> str | None:
    """Extract FamilySearch URL from source Fields blob."""
    if not fields_blob:
        return None

    try:
        fields_text = fields_blob.decode('utf-8')
        # Find FamilySearch ARK URLs
        urls = re.findall(r'https?://(?:www\.)?familysearch\.org/ark:/61903/1:1:[A-Z0-9-]+', fields_text)
        return urls[0] if urls else None
    except Exception:
        return None


def parse_source_name(source_name: str) -> dict | None:
    """Parse source name to extract state, county, surname, given."""
    # Pattern: Fed Census: 1930, {State}, {County} [...] {Surname}, {Given}
    match = re.match(
        r'Fed Census: 1930, ([^,]+), ([^\[]+)\s*\[.*\]\s*(.+)',
        source_name
    )
    if not match:
        return None

    state = match.group(1).strip()
    county = match.group(2).strip()
    person = match.group(3).strip()

    # Parse person name
    if ',' in person:
        parts = person.split(',', 1)
        surname = parts[0].strip()
        given = parts[1].strip() if len(parts) > 1 else ''
    else:
        surname = person
        given = ''

    return {
        'state': state,
        'county': county,
        'surname': surname,
        'given': given
    }


def get_sources_without_media(db_path: str) -> list[SourceMediaInfo]:
    """Get 1930 Census sources without media, with their Event/Citation chain."""
    conn = connect_rmtree(db_path, read_only=True)
    cursor = conn.cursor()

    # Find 1930 Census sources without media
    cursor.execute('''
    SELECT s.SourceID, s.Name, s.Fields
    FROM SourceTable s
    WHERE s.Name LIKE 'Fed Census: 1930%'
      AND NOT EXISTS (
        SELECT 1 FROM MediaLinkTable ml
        WHERE ml.OwnerID = s.SourceID AND ml.OwnerType = 3
      )
    ORDER BY s.Name
    ''')

    sources = []
    for row in cursor.fetchall():
        source_id, source_name, fields_blob = row

        # Extract URL from fields
        url = extract_url_from_fields(fields_blob)
        if not url:
            logger.warning(f"No FamilySearch URL found for SourceID {source_id}")
            continue

        # Parse source name
        parsed = parse_source_name(source_name)
        if not parsed:
            logger.warning(f"Could not parse source name: {source_name}")
            continue

        # Trace Source -> Citation -> Event -> Person
        cursor.execute('''
        SELECT c.CitationID
        FROM CitationTable c
        WHERE c.SourceID = ?
        LIMIT 1
        ''', (source_id,))
        cit_row = cursor.fetchone()
        citation_id = cit_row[0] if cit_row else None

        event_id = None
        person_id = None
        person_given = None
        person_surname = None

        if citation_id:
            # Find event linked to this citation
            cursor.execute('''
            SELECT cl.OwnerID
            FROM CitationLinkTable cl
            WHERE cl.CitationID = ? AND cl.OwnerType = 2
            LIMIT 1
            ''', (citation_id,))
            evt_row = cursor.fetchone()
            event_id = evt_row[0] if evt_row else None

            if event_id:
                # Get person from event
                cursor.execute('''
                SELECT e.OwnerID, n.Given, n.Surname
                FROM EventTable e
                JOIN NameTable n ON e.OwnerID = n.OwnerID AND n.IsPrimary = 1
                WHERE e.EventID = ?
                ''', (event_id,))
                person_row = cursor.fetchone()
                if person_row:
                    person_id = person_row[0]
                    person_given = person_row[1]
                    person_surname = person_row[2]

        sources.append(SourceMediaInfo(
            source_id=source_id,
            source_name=source_name,
            state=parsed['state'],
            county=parsed['county'],
            surname=parsed['surname'],
            given_name=parsed['given'],
            familysearch_url=url,
            citation_id=citation_id,
            event_id=event_id,
            person_id=person_id,
            person_given=person_given,
            person_surname=person_surname
        ))

    conn.close()
    return sources


async def download_and_link_missing_images(
    db_path: str,
    media_root: Path,
    progress_callback=None
) -> dict:
    """
    Download and link missing 1930 Census images.

    Args:
        db_path: Path to RootsMagic database
        media_root: Root directory for media files
        progress_callback: Optional callback(current, total, message)

    Returns:
        Dict with counts: downloaded, skipped, errors
    """
    results = {
        'downloaded': 0,
        'skipped': 0,
        'errors': [],
        'details': []
    }

    # Get sources needing media
    sources = get_sources_without_media(db_path)
    if not sources:
        logger.info("No sources found needing media")
        return results

    logger.info(f"Found {len(sources)} sources needing media")

    # Initialize FamilySearch automation
    fs_automation = FamilySearchAutomation()
    connected = await fs_automation.connect_to_chrome()
    if not connected:
        results['errors'].append("Could not connect to Chrome")
        return results

    try:
        for i, source in enumerate(sources):
            logger.info(f"=== Processing source {i+1}/{len(sources)}: SourceID {source.source_id} ===")
            logger.info(f"  URL: {source.familysearch_url}")

            if progress_callback:
                progress_callback(i, len(sources), f"Processing {source.surname}, {source.given_name}")

            try:
                # Use person name from RootsMagic if available, otherwise from source
                if source.person_given and source.person_surname:
                    given_name = source.person_given
                    surname = source.person_surname
                else:
                    given_name = source.given_name
                    surname = source.surname

                logger.info(f"  Person: {given_name} {surname}")

                # Generate filename
                filename = f"1930, {source.state}, {source.county} - {surname}, {given_name}.jpg"

                # Destination path
                dest_dir = media_root / "Records - Census" / "1930 Federal"
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_path = dest_dir / filename

                # Check if file already exists
                if dest_path.exists():
                    logger.info(f"Image already exists: {dest_path}")
                    # Just need to create database records
                    await _create_media_records(
                        db_path, source, dest_path, filename
                    )
                    results['downloaded'] += 1
                    results['details'].append({
                        'source_id': source.source_id,
                        'status': 'linked_existing',
                        'filename': filename
                    })
                    continue

                # Navigate to FamilySearch record page to get image viewer URL
                logger.info(f"Extracting image URL for {surname}, {given_name}")
                logger.info(f"  Navigating to: {source.familysearch_url}")

                citation_data = await fs_automation.extract_citation_data(
                    source.familysearch_url, census_year=1930
                )

                if citation_data:
                    logger.info(f"  Citation data keys: {list(citation_data.keys())}")
                    logger.info(f"  image_viewer_url: {citation_data.get('image_viewer_url', 'NOT FOUND')}")

                if not citation_data:
                    results['errors'].append(f"SourceID {source.source_id}: Could not extract citation data")
                    continue

                # The transformed citation data uses snake_case keys
                image_viewer_url = citation_data.get('image_viewer_url')
                if not image_viewer_url:
                    logger.warning(f"SourceID {source.source_id}: No image_viewer_url in citation_data. Keys: {list(citation_data.keys())}")
                    results['errors'].append(f"SourceID {source.source_id}: No image viewer URL found")
                    continue

                # Download the image
                logger.info(f"Downloading image to {dest_path}")
                success = await fs_automation.download_census_image(image_viewer_url, dest_path)

                if not success:
                    results['errors'].append(f"SourceID {source.source_id}: Download failed")
                    continue

                # Create database records
                await _create_media_records(
                    db_path, source, dest_path, filename
                )

                results['downloaded'] += 1
                results['details'].append({
                    'source_id': source.source_id,
                    'status': 'downloaded',
                    'filename': filename
                })

                logger.info(f"Successfully processed {surname}, {given_name}")

                # Small delay between downloads to avoid rate limiting
                await asyncio.sleep(2.0)

            except Exception as e:
                logger.error(f"Error processing SourceID {source.source_id}: {e}")
                results['errors'].append(f"SourceID {source.source_id}: {str(e)}")

    finally:
        await fs_automation.disconnect()

    return results


async def _create_media_records(
    db_path: str,
    source: SourceMediaInfo,
    file_path: Path,
    filename: str
) -> None:
    """Create MultimediaTable and MediaLinkTable records."""
    conn = connect_rmtree(db_path, read_only=False)

    try:
        repo = ImageRepository(conn)

        # Generate caption
        state_abbrevs = {
            'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
            'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE',
            'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID',
            'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS',
            'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
            'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS',
            'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
            'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
            'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK',
            'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
            'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT',
            'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
            'Wisconsin': 'WI', 'Wyoming': 'WY'
        }
        state_abbr = state_abbrevs.get(source.state, source.state[:2].upper())
        caption = f"Census: 1930 Fed Census - {source.county}, {state_abbr}"

        # Media path for RootsMagic (symbolic)
        media_path = "?\\Records - Census\\1930 Federal"

        # Census date in RootsMagic format
        census_date = "D.+19300401..+00000000.."

        # Create media record
        media_id = repo.create_media_record(
            media_path=media_path,
            media_file=filename,
            caption=caption,
            ref_number=source.familysearch_url,
            census_date=census_date,
            description=""
        )

        logger.info(f"Created MediaID {media_id} for {filename}")

        # Link to source
        repo.link_media_to_source(media_id, source.source_id)
        logger.info(f"Linked media to SourceID {source.source_id}")

        # Link to citation if available
        if source.citation_id:
            repo.link_media_to_citation(media_id, source.citation_id)
            logger.info(f"Linked media to CitationID {source.citation_id}")

        # Link to event if available
        if source.event_id:
            repo.link_media_to_event(media_id, source.event_id)
            logger.info(f"Linked media to EventID {source.event_id}")

        conn.commit()

    finally:
        conn.close()
