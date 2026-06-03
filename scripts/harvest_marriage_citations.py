#!/usr/bin/env python3
"""Harvest marriage citations from FamilySearch notes in event records.

This script parses FamilySearch-formatted citation notes from marriage events
and creates proper Source/Citation records following Evidence Explained 4th edition.

Approach: "Emphasis on database" (EE 4th ed. p.423)
- Layer 1 (Source): The FamilySearch database collection
- Specific Item Block (Citation): Person names, dates, record details
- Location Layer: "citing..." original source info

Source Naming Convention:
    Marriage Records: [State], [Collection] - [Groom Surname], [Given] & [Bride Surname], [Given], [Year]

Example:
    Marriage Records: North Carolina, County Marriages 1762-1979 - Ijams, William & Hanes, Caty, 1812

Usage:
    python scripts/harvest_marriage_citations.py --preview
    python scripts/harvest_marriage_citations.py --execute --limit 2
"""

import argparse
import html
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rmcitecraft.database.connection import connect_rmtree


@dataclass
class ParsedFamilySearchCitation:
    """Parsed components from a FamilySearch citation note."""
    collection_name: str          # "North Carolina, County Marriages, 1762-1979"
    record_type: str              # "database with images" or "index"
    url: str                      # Full FamilySearch URL
    access_date: str              # "22 December 2016"
    subject_names: str            # "William Ijams and Caty Hanes"
    groom_name: str               # "William Ijams"
    bride_name: str               # "Caty Hanes"
    event_date: str               # "15 Feb 1812"
    event_year: str               # "1812"
    citing_info: Optional[str]    # Everything after "citing"
    state: str                    # "North Carolina"
    collection_short: str         # "County Marriages 1762-1979" (without state)
    raw_note: str                 # Original note text


@dataclass
class GeneratedCitation:
    """Generated citation components for RootsMagic."""
    source_name: str              # "Marriage Records: NC, County Marriages 1762-1979 - Ijams, William & Hanes, Caty, 1812"
    footnote: str                 # Full footnote text
    short_footnote: str           # Abbreviated footnote
    bibliography: str             # Bibliography entry
    page_value: str               # For CitationTable.Fields Page field


def parse_names(subject_names: str) -> tuple[str, str]:
    """Parse 'Groom Name and Bride Name' into separate names."""
    # Common patterns: "John Smith and Mary Jones", "John Smith & Mary Jones"
    parts = re.split(r'\s+and\s+|\s+&\s+', subject_names, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return subject_names.strip(), ""


def extract_year(date_str: str) -> str:
    """Extract 4-digit year from date string."""
    match = re.search(r'\b(\d{4})\b', date_str)
    return match.group(1) if match else ""


def clean_citing_info(citing: str) -> str:
    """Clean up superfluous content from citing info.

    Removes:
    - Empty page references like "p. ," or "p.,"
    - Trailing punctuation cleanup
    - Multiple consecutive commas/spaces
    """
    if not citing:
        return citing

    # Remove empty page references: "p. ," or "p.," or "p. , "
    citing = re.sub(r'\bp\.\s*,\s*', '', citing)

    # Clean up multiple commas/spaces that might result
    citing = re.sub(r',\s*,', ',', citing)
    citing = re.sub(r'\s+', ' ', citing)

    # Clean up leading comma if any
    citing = re.sub(r'^\s*,\s*', '', citing)

    return citing.strip()


def parse_collection_name(collection: str) -> tuple[str, str]:
    """Parse collection name into state and short collection name.

    Input: "North Carolina, County Marriages, 1762-1979"
    Output: ("North Carolina", "County Marriages 1762-1979")
    """
    # Remove trailing comma/space variations
    collection = collection.rstrip(' ,')

    # Split on first comma to get state
    parts = collection.split(',', 1)
    if len(parts) == 2:
        state = parts[0].strip()
        rest = parts[1].strip()
        # Clean up the rest - remove extra commas, normalize spacing
        rest = re.sub(r',\s*', ' ', rest)
        rest = re.sub(r'\s+', ' ', rest)
        return state, rest

    return "", collection


def format_name_for_source(full_name: str) -> str:
    """Format 'Given Surname' as 'Surname, Given' for source name."""
    parts = full_name.strip().split()
    if len(parts) >= 2:
        # Assume last word is surname, rest is given name
        surname = parts[-1]
        given = ' '.join(parts[:-1])
        return f"{surname}, {given}"
    return full_name


def parse_familysearch_note(note: str) -> Optional[ParsedFamilySearchCitation]:
    """Parse a FamilySearch-formatted citation from a note.

    Expected format:
    "Collection Name," record type, <i>FamilySearch</i> (URL : access date),
    subject names, event date; citing original source info
    """
    if not note or 'familysearch.org' not in note.lower():
        return None

    # Extract collection name (in quotes at start)
    collection_match = re.search(r'^"([^"]+)"', note.strip())
    if not collection_match:
        return None
    collection_name = collection_match.group(1).rstrip(',').strip()

    # Parse state and short collection name
    state, collection_short = parse_collection_name(collection_name)

    # Extract record type (after collection, before FamilySearch)
    record_type_match = re.search(
        r'"\s*,?\s*([^,<]+?)\s*,?\s*(?:<i>)?FamilySearch',
        note,
        re.IGNORECASE
    )
    record_type = record_type_match.group(1).strip() if record_type_match else "database"

    # Extract URL
    url_match = re.search(r'(https?://(?:www\.)?familysearch\.org[^\s\)]+)', note)
    if not url_match:
        return None
    url = url_match.group(1)

    # Extract access date
    access_date_match = re.search(
        r'familysearch\.org[^\s\)]+ : (?:accessed )?([^)]+)\)',
        note,
        re.IGNORECASE
    )
    access_date = access_date_match.group(1).strip() if access_date_match else ""

    # Extract subject names and event date
    subject_match = re.search(
        r'\)\s*,\s*([^;.]+?),\s*(\d{1,2}\s+\w+\s+\d{4}|\d{4})\s*[;.]',
        note
    )
    if subject_match:
        subject_names = subject_match.group(1).strip()
        event_date = subject_match.group(2).strip()
    else:
        subject_names = ""
        event_date = ""

    # Parse individual names
    groom_name, bride_name = parse_names(subject_names)

    # Extract year
    event_year = extract_year(event_date)

    # Extract citing info and clean up superfluous content
    citing_match = re.search(r';\s*citing\s+(.+)$', note, re.IGNORECASE | re.DOTALL)
    citing_info = clean_citing_info(citing_match.group(1).strip()) if citing_match else None

    return ParsedFamilySearchCitation(
        collection_name=collection_name,
        record_type=record_type,
        url=url,
        access_date=access_date,
        subject_names=subject_names,
        groom_name=groom_name,
        bride_name=bride_name,
        event_date=event_date,
        event_year=event_year,
        citing_info=citing_info,
        state=state,
        collection_short=collection_short,
        raw_note=note
    )


def generate_citation(parsed: ParsedFamilySearchCitation) -> GeneratedCitation:
    """Generate Evidence Explained formatted citation components.

    Following EE 4th edition "emphasis on database" approach (p.423).
    """
    # Format names for source name: "Surname, Given"
    groom_formatted = format_name_for_source(parsed.groom_name)
    bride_formatted = format_name_for_source(parsed.bride_name)

    # Source Name: Marriage Records: [State], [Collection] - [Groom] & [Bride], [Year]
    source_name = f"Marriage Records: {parsed.state}, {parsed.collection_short} - {groom_formatted} & {bride_formatted}, {parsed.event_year}"

    # Footnote: Full citation with all layers
    footnote = f'"{parsed.collection_name}," {parsed.record_type}, <i>FamilySearch</i> ({parsed.url} : {parsed.access_date}), {parsed.subject_names}, {parsed.event_date}'
    if parsed.citing_info:
        footnote += f"; citing {parsed.citing_info}"
    else:
        footnote += "."

    # Short Footnote: Abbreviated version
    short_footnote = f'"{parsed.collection_name}," FamilySearch, {parsed.subject_names}, {parsed.event_date}.'

    # Bibliography: Source-level citation (collection, not specific record)
    current_year = datetime.now().year
    bibliography = f'"{parsed.collection_name}." {parsed.record_type.capitalize()}. <i>FamilySearch</i>. https://familysearch.org : {current_year}.'

    # Page value (for CitationTable.Fields) - can be empty or contain URL
    page_value = ""

    return GeneratedCitation(
        source_name=source_name,
        footnote=footnote,
        short_footnote=short_footnote,
        bibliography=bibliography,
        page_value=page_value
    )


def build_source_fields_xml(footnote: str, short_footnote: str, bibliography: str) -> bytes:
    """Build the XML BLOB for SourceTable.Fields.

    HTML tags like <i> must be entity-encoded for storage.
    """
    # Entity-encode HTML tags
    fn_encoded = html.escape(footnote)
    sfn_encoded = html.escape(short_footnote)
    bib_encoded = html.escape(bibliography)

    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Root><Fields>
<Field><Name>Footnote</Name><Value>{fn_encoded}</Value></Field>
<Field><Name>ShortFootnote</Name><Value>{sfn_encoded}</Value></Field>
<Field><Name>Bibliography</Name><Value>{bib_encoded}</Value></Field>
</Fields></Root>'''

    return xml.encode('utf-8')


def build_citation_fields_xml(page_value: str) -> bytes:
    """Build the XML BLOB for CitationTable.Fields."""
    page_encoded = html.escape(page_value) if page_value else ""

    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Root><Fields>
<Field><Name>Page</Name><Value>{page_encoded}</Value></Field>
</Fields></Root>'''

    return xml.encode('utf-8')


def get_next_id(cursor, table: str, id_column: str) -> int:
    """Get the next available ID for a table."""
    cursor.execute(f"SELECT MAX({id_column}) FROM {table}")
    result = cursor.fetchone()[0]
    return (result or 0) + 1


def create_source(cursor, generated: GeneratedCitation) -> int:
    """Create a new Source record and return its SourceID."""
    source_id = get_next_id(cursor, "SourceTable", "SourceID")

    fields_blob = build_source_fields_xml(
        generated.footnote,
        generated.short_footnote,
        generated.bibliography
    )

    # Get current timestamp for UTCModDate
    utc_mod_date = datetime.now().timestamp() / 86400 + 25569  # Excel date format

    cursor.execute('''
        INSERT INTO SourceTable (
            SourceID, Name, RefNumber, ActualText, Comments, IsPrivate,
            TemplateID, Fields, UTCModDate
        ) VALUES (?, ?, '', '', '', 0, 0, ?, ?)
    ''', (source_id, generated.source_name, fields_blob, utc_mod_date))

    return source_id


def create_citation(cursor, source_id: int, generated: GeneratedCitation) -> int:
    """Create a new Citation record and return its CitationID."""
    citation_id = get_next_id(cursor, "CitationTable", "CitationID")

    fields_blob = build_citation_fields_xml(generated.page_value)

    utc_mod_date = datetime.now().timestamp() / 86400 + 25569

    # CitationName can be the page value or empty
    citation_name = generated.page_value if generated.page_value else ""

    cursor.execute('''
        INSERT INTO CitationTable (
            CitationID, SourceID, Comments, ActualText, RefNumber,
            Footnote, ShortFootnote, Bibliography, Fields, UTCModDate, CitationName
        ) VALUES (?, ?, '', '', '', '', '', '', ?, ?, ?)
    ''', (citation_id, source_id, fields_blob, utc_mod_date, citation_name))

    return citation_id


def link_citation_to_event(cursor, citation_id: int, event_id: int) -> int:
    """Create CitationLinkTable record to link citation to event."""
    link_id = get_next_id(cursor, "CitationLinkTable", "LinkID")

    utc_mod_date = datetime.now().timestamp() / 86400 + 25569

    cursor.execute('''
        INSERT INTO CitationLinkTable (
            LinkID, CitationID, OwnerType, OwnerID, SortOrder, Quality, IsPrivate, Flags, UTCModDate
        ) VALUES (?, ?, 2, ?, 0, '', 0, 0, ?)
    ''', (link_id, citation_id, event_id, utc_mod_date))

    return link_id


def find_uncited_marriages(cursor, collection_filter: Optional[str] = None, limit: int = 10):
    """Find marriage events with FamilySearch notes but no citations."""
    query = '''
        SELECT e.EventID, f.FamilyID, f.FatherID, f.MotherID,
               nf.Given || " " || nf.Surname as spouse1,
               nm.Given || " " || nm.Surname as spouse2,
               e.Date, e.Note
        FROM EventTable e
        JOIN FamilyTable f ON f.FamilyID = e.OwnerID AND e.OwnerType = 1
        LEFT JOIN NameTable nf ON nf.OwnerID = f.FatherID AND nf.IsPrimary = 1
        LEFT JOIN NameTable nm ON nm.OwnerID = f.MotherID AND nm.IsPrimary = 1
        LEFT JOIN CitationLinkTable cl ON cl.OwnerID = e.EventID AND cl.OwnerType = 2
        WHERE e.Note LIKE "%familysearch.org%"
          AND e.EventType = 300
          AND cl.CitationID IS NULL
    '''

    if collection_filter:
        query += f' AND e.Note LIKE "%{collection_filter}%"'

    query += f' ORDER BY e.EventID LIMIT {limit}'

    cursor.execute(query)
    return cursor.fetchall()


def preview_citation(event_id: int, spouse1: str, spouse2: str, note: str):
    """Preview what would be generated for a marriage event."""
    print(f"\n{'='*70}")
    print(f"EventID: {event_id}")
    print(f"Spouses: {spouse1} & {spouse2}")
    print(f"{'='*70}")

    parsed = parse_familysearch_note(note)
    if not parsed:
        print("  ERROR: Could not parse note")
        print(f"  Note: {note[:200]}...")
        return None

    print(f"\nParsed Components:")
    print(f"  State: {parsed.state}")
    print(f"  Collection: {parsed.collection_short}")
    print(f"  Groom: {parsed.groom_name}")
    print(f"  Bride: {parsed.bride_name}")
    print(f"  Year: {parsed.event_year}")
    print(f"  URL: {parsed.url}")
    if parsed.citing_info:
        print(f"  Citing: {parsed.citing_info[:60]}...")

    generated = generate_citation(parsed)

    print(f"\nGenerated Citation:")
    print(f"  Source Name:")
    print(f"    {generated.source_name}")
    print(f"\n  Footnote:")
    print(f"    {generated.footnote[:150]}...")
    print(f"\n  Short Footnote:")
    print(f"    {generated.short_footnote}")
    print(f"\n  Bibliography:")
    print(f"    {generated.bibliography}")

    return generated, parsed


def execute_citation(cursor, event_id: int, note: str) -> Optional[dict]:
    """Create Source and Citation records for a marriage event."""
    parsed = parse_familysearch_note(note)
    if not parsed:
        return None

    generated = generate_citation(parsed)

    # Create Source
    source_id = create_source(cursor, generated)

    # Create Citation
    citation_id = create_citation(cursor, source_id, generated)

    # Link Citation to Event
    link_id = link_citation_to_event(cursor, citation_id, event_id)

    return {
        'source_id': source_id,
        'citation_id': citation_id,
        'link_id': link_id,
        'source_name': generated.source_name
    }


def main():
    parser = argparse.ArgumentParser(
        description='Harvest marriage citations from FamilySearch notes.'
    )
    parser.add_argument(
        '--db',
        default='data/Iiams.rmtree',
        help='Path to RootsMagic database'
    )
    parser.add_argument(
        '--collection',
        default='North Carolina, County Marriages',
        help='Filter by collection name'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=2,
        help='Number of records to process'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually create records (default is preview only)'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("  MARRIAGE CITATION HARVESTER")
    print("  FamilySearch Notes → Evidence Explained Citations")
    print("=" * 70)

    # Connect to database
    conn = connect_rmtree(args.db, read_only=not args.execute)
    cursor = conn.cursor()

    # Find uncited marriages
    print(f"\nSearching for uncited marriages...")
    print(f"  Collection filter: {args.collection}")
    print(f"  Limit: {args.limit}")

    records = find_uncited_marriages(cursor, args.collection, args.limit)

    if not records:
        print("\nNo uncited marriage records found matching criteria.")
        conn.close()
        return

    print(f"\nFound {len(records)} record(s) to process.")

    if not args.execute:
        # Preview mode
        for row in records:
            event_id, fam_id, father_rin, mother_rin, spouse1, spouse2, date, note = row
            preview_citation(event_id, spouse1, spouse2, note)

        print("\n" + "=" * 70)
        print("  PREVIEW MODE - No changes made")
        print("  Run with --execute to create records")
        print("=" * 70)
    else:
        # Execute mode
        print("\nCreating records...")
        created = 0

        for row in records:
            event_id, fam_id, father_rin, mother_rin, spouse1, spouse2, date, note = row

            result = execute_citation(cursor, event_id, note)
            if result:
                print(f"\n  EventID {event_id}: Created")
                print(f"    SourceID: {result['source_id']}")
                print(f"    CitationID: {result['citation_id']}")
                print(f"    Source: {result['source_name'][:70]}...")
                created += 1
            else:
                print(f"\n  EventID {event_id}: FAILED to parse note")

        conn.commit()

        print("\n" + "=" * 70)
        print(f"  CREATED {created} SOURCE/CITATION RECORDS")
        print("=" * 70)

    conn.close()


if __name__ == '__main__':
    main()
