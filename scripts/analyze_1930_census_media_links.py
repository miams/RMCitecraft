#!/usr/bin/env python3
"""
Analyze 1930 Census sources and recommend media links.

This script identifies 1930 Census sources without media attachments and
matches them to existing media files based on State, County, and Person name.

Outputs a CSV spreadsheet for manual review before applying changes.

Usage:
    uv run python scripts/analyze_1930_census_media_links.py

Output:
    data/1930_census_media_link_recommendations.csv
"""

import csv
import re
import sys
from pathlib import Path
from dataclasses import dataclass

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rmcitecraft.database.connection import connect_rmtree


@dataclass
class SourceInfo:
    """Parsed information from a 1930 Census source."""
    source_id: int
    source_name: str
    state: str
    county: str
    surname: str
    given: str
    ed: str
    sheet: str
    line: str
    family: str


@dataclass
class MediaInfo:
    """Parsed information from a 1930 Census media file."""
    media_id: int
    media_file: str
    caption: str
    state: str
    county: str
    surname: str
    given: str


@dataclass
class EventInfo:
    """Information about a 1930 Census event."""
    event_id: int
    person_id: int
    person_surname: str
    person_given: str
    date: str


@dataclass
class LinkRecommendation:
    """A recommended link between source/event and media."""
    source_id: int
    source_name: str
    source_state: str
    source_county: str
    source_person: str
    source_ed: str
    source_sheet: str
    media_id: int
    media_file: str
    media_state: str
    media_county: str
    media_person: str
    match_type: str  # 'exact', 'surname_only', 'fuzzy', 'county_only'
    match_score: int  # 0-100
    event_id: int | None
    event_person: str | None
    has_existing_source_link: bool
    has_existing_event_link: bool
    notes: str


def parse_source_name(source_id: int, source_name: str) -> SourceInfo | None:
    """Parse a 1930 Census source name into components."""
    # Pattern: Fed Census: 1930, {State}, {County} [citing enumeration district (ED) {N}, sheet {N}, line {N}, family {N}] {Surname}, {Given}
    # Some variations exist

    # Main pattern
    match = re.match(
        r'Fed Census: 1930, ([^,]+), ([^\[]+)\s*\[citing\s+(?:enumeration district \(ED\)|ED)\s*(\d+)?[,\s]*(?:sheet\s*(\d*\w*))?[,\s]*(?:line\s*(\d+))?[,\s]*(?:family\s*(\d+))?\]\s*(.+)',
        source_name,
        re.IGNORECASE
    )

    if not match:
        return None

    state = match.group(1).strip()
    county = match.group(2).strip()
    ed = match.group(3) or ''
    sheet = match.group(4) or ''
    line = match.group(5) or ''
    family = match.group(6) or ''
    person = match.group(7).strip()

    # Parse person name (Surname, Given)
    if ',' in person:
        parts = person.split(',', 1)
        surname = parts[0].strip()
        given = parts[1].strip() if len(parts) > 1 else ''
    else:
        surname = person
        given = ''

    return SourceInfo(
        source_id=source_id,
        source_name=source_name,
        state=state,
        county=county,
        surname=surname,
        given=given,
        ed=ed,
        sheet=sheet,
        line=line,
        family=family
    )


def parse_media_filename(media_id: int, media_file: str, caption: str) -> MediaInfo | None:
    """Parse a 1930 Census media filename into components."""
    # Pattern: 1930, {State}, {County} - {Surname}, {Given}.jpg
    # Some variations: 1930, {State} {County} - ...

    match = re.match(
        r'1930,\s*([^,]+),?\s*([^-]+)\s*-\s*(.+)\.(?:jpg|jpeg|png|tif|tiff)$',
        media_file,
        re.IGNORECASE
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

    return MediaInfo(
        media_id=media_id,
        media_file=media_file,
        caption=caption,
        state=state,
        county=county,
        surname=surname,
        given=given
    )


def normalize_name(name: str) -> str:
    """Normalize a name for comparison."""
    # Remove parenthetical maiden names, punctuation, extra spaces
    name = re.sub(r'\([^)]*\)', '', name)  # Remove (maiden name)
    name = re.sub(r'[^\w\s]', '', name)  # Remove punctuation
    name = ' '.join(name.split())  # Normalize whitespace
    return name.lower().strip()


def normalize_county(county: str) -> str:
    """Normalize county name for comparison."""
    county = county.lower().strip()
    # Remove common suffixes
    county = re.sub(r'\s+(county|co\.?)$', '', county, flags=re.IGNORECASE)
    return county


def normalize_state(state: str) -> str:
    """Normalize state name for comparison."""
    return state.lower().strip()


def calculate_match_score(source: SourceInfo, media: MediaInfo) -> tuple[int, str, str]:
    """
    Calculate how well a source matches a media file.
    Returns (score, match_type, notes).
    """
    notes = []

    # Normalize for comparison
    src_state = normalize_state(source.state)
    src_county = normalize_county(source.county)
    src_surname = normalize_name(source.surname)
    src_given = normalize_name(source.given)

    med_state = normalize_state(media.state)
    med_county = normalize_county(media.county)
    med_surname = normalize_name(media.surname)
    med_given = normalize_name(media.given)

    # State must match (or be close)
    state_match = src_state == med_state or src_state[:3] == med_state[:3]
    if not state_match:
        return 0, 'no_match', 'State mismatch'

    # County should match
    county_match = src_county == med_county or src_county in med_county or med_county in src_county
    if not county_match:
        return 0, 'no_match', f'County mismatch: {source.county} vs {media.county}'

    # Now check person name
    surname_match = src_surname == med_surname
    given_exact = src_given == med_given
    given_partial = (src_given and med_given and
                     (src_given.startswith(med_given[:3]) or med_given.startswith(src_given[:3])))

    if surname_match and given_exact:
        return 100, 'exact', 'Exact match on state, county, surname, given'

    if surname_match and given_partial:
        notes.append(f'Given name partial: {source.given} vs {media.given}')
        return 90, 'given_partial', '; '.join(notes)

    if surname_match and (not src_given or not med_given):
        notes.append('One or both given names empty')
        return 80, 'surname_only', '; '.join(notes)

    if surname_match:
        notes.append(f'Given name mismatch: {source.given} vs {media.given}')
        return 70, 'surname_match_given_diff', '; '.join(notes)

    # Check if surnames are similar (typos, spelling variations)
    if src_surname and med_surname:
        # Simple Levenshtein-like check
        if (src_surname[:4] == med_surname[:4] or
            src_surname in med_surname or
            med_surname in src_surname):
            notes.append(f'Surname similar: {source.surname} vs {media.surname}')
            return 50, 'fuzzy_surname', '; '.join(notes)

    return 0, 'no_match', f'Person mismatch: {source.surname}, {source.given} vs {media.surname}, {media.given}'


def get_sources_without_media(cursor) -> list[SourceInfo]:
    """Get all 1930 Census sources without direct media links."""
    cursor.execute('''
    SELECT s.SourceID, s.Name
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
        source_id, name = row
        parsed = parse_source_name(source_id, name)
        if parsed:
            sources.append(parsed)

    return sources


def get_all_media(cursor) -> list[MediaInfo]:
    """Get all 1930 Census media records."""
    cursor.execute('''
    SELECT MediaID, MediaFile, Caption
    FROM MultimediaTable
    WHERE MediaPath LIKE '%1930 Federal%'
    ''')

    media_list = []
    for row in cursor.fetchall():
        media_id, media_file, caption = row
        parsed = parse_media_filename(media_id, media_file, caption or '')
        if parsed:
            media_list.append(parsed)

    return media_list


def get_census_events_for_person(cursor, surname: str, given: str, year: str = '1930') -> list[EventInfo]:
    """Find 1930 Census events for a person by name."""
    cursor.execute('''
    SELECT e.EventID, e.OwnerID, n.Surname, n.Given, e.Date
    FROM EventTable e
    JOIN NameTable n ON e.OwnerID = n.OwnerID AND n.IsPrimary = 1
    WHERE e.EventType = 18
      AND e.Date LIKE ?
      AND n.Surname LIKE ?
      AND n.Given LIKE ?
    ''', (f'%{year}%', f'{surname}%', f'{given}%'))

    events = []
    for row in cursor.fetchall():
        events.append(EventInfo(
            event_id=row[0],
            person_id=row[1],
            person_surname=row[2],
            person_given=row[3],
            date=row[4]
        ))

    return events


def check_existing_event_media_link(cursor, event_id: int, media_id: int) -> bool:
    """Check if an event already has a link to this media."""
    cursor.execute('''
    SELECT 1 FROM MediaLinkTable
    WHERE OwnerType = 2 AND OwnerID = ? AND MediaID = ?
    ''', (event_id, media_id))
    return cursor.fetchone() is not None


def main():
    database_path = 'data/Iiams.rmtree'
    output_path = 'data/1930_census_media_link_recommendations.csv'

    print("=" * 70)
    print("1930 Census Media Link Analysis")
    print("=" * 70)
    print(f"Database: {database_path}")
    print(f"Output: {output_path}")
    print()

    conn = connect_rmtree(database_path, read_only=True)
    cursor = conn.cursor()

    # Get sources without media
    print("Loading sources without media links...")
    sources = get_sources_without_media(cursor)
    print(f"  Found {len(sources)} sources without media")

    # Get all media
    print("Loading media records...")
    media_list = get_all_media(cursor)
    print(f"  Found {len(media_list)} media records")

    # Build media index by state+county for faster lookup
    media_by_location: dict[str, list[MediaInfo]] = {}
    for media in media_list:
        key = f"{normalize_state(media.state)}|{normalize_county(media.county)}"
        if key not in media_by_location:
            media_by_location[key] = []
        media_by_location[key].append(media)

    print()
    print("Analyzing matches...")

    recommendations: list[LinkRecommendation] = []
    no_match_sources: list[SourceInfo] = []

    for source in sources:
        # Find candidate media in same state/county
        key = f"{normalize_state(source.state)}|{normalize_county(source.county)}"
        candidates = media_by_location.get(key, [])

        best_match = None
        best_score = 0
        best_type = ''
        best_notes = ''

        for media in candidates:
            score, match_type, notes = calculate_match_score(source, media)
            if score > best_score:
                best_score = score
                best_match = media
                best_type = match_type
                best_notes = notes

        if best_match and best_score >= 50:
            # Find associated census event
            events = get_census_events_for_person(
                cursor, source.surname, source.given[:3] if source.given else ''
            )

            event_id = None
            event_person = None
            has_existing_event_link = False

            if events:
                # Pick first matching event
                event = events[0]
                event_id = event.event_id
                event_person = f"{event.person_given} {event.person_surname}"
                has_existing_event_link = check_existing_event_media_link(
                    cursor, event_id, best_match.media_id
                )

            recommendations.append(LinkRecommendation(
                source_id=source.source_id,
                source_name=source.source_name,
                source_state=source.state,
                source_county=source.county,
                source_person=f"{source.surname}, {source.given}",
                source_ed=source.ed,
                source_sheet=source.sheet,
                media_id=best_match.media_id,
                media_file=best_match.media_file,
                media_state=best_match.state,
                media_county=best_match.county,
                media_person=f"{best_match.surname}, {best_match.given}",
                match_type=best_type,
                match_score=best_score,
                event_id=event_id,
                event_person=event_person,
                has_existing_source_link=False,  # We only queried sources without links
                has_existing_event_link=has_existing_event_link,
                notes=best_notes
            ))
        else:
            no_match_sources.append(source)

    conn.close()

    # Sort recommendations by match score (best first)
    recommendations.sort(key=lambda r: (-r.match_score, r.source_state, r.source_county))

    # Write CSV
    print(f"Writing {len(recommendations)} recommendations to CSV...")

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            'Recommend',  # For user to mark Y/N
            'Match Score',
            'Match Type',
            'Source ID',
            'Source State',
            'Source County',
            'Source Person',
            'Source ED',
            'Source Sheet',
            'Media ID',
            'Media File',
            'Media Person',
            'Event ID',
            'Event Person',
            'Event Already Linked',
            'Notes',
            'Full Source Name'
        ])

        for rec in recommendations:
            writer.writerow([
                'Y' if rec.match_score >= 80 else '?',  # Pre-fill recommendation
                rec.match_score,
                rec.match_type,
                rec.source_id,
                rec.source_state,
                rec.source_county,
                rec.source_person,
                rec.source_ed,
                rec.source_sheet,
                rec.media_id,
                rec.media_file,
                rec.media_person,
                rec.event_id or '',
                rec.event_person or '',
                'Y' if rec.has_existing_event_link else 'N',
                rec.notes,
                rec.source_name
            ])

    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Sources without media: {len(sources)}")
    print(f"Recommendations generated: {len(recommendations)}")
    print(f"No match found: {len(no_match_sources)}")
    print()

    # Breakdown by match type
    by_type: dict[str, int] = {}
    by_score: dict[str, int] = {'100': 0, '90-99': 0, '80-89': 0, '70-79': 0, '50-69': 0}

    for rec in recommendations:
        by_type[rec.match_type] = by_type.get(rec.match_type, 0) + 1
        if rec.match_score == 100:
            by_score['100'] += 1
        elif rec.match_score >= 90:
            by_score['90-99'] += 1
        elif rec.match_score >= 80:
            by_score['80-89'] += 1
        elif rec.match_score >= 70:
            by_score['70-79'] += 1
        else:
            by_score['50-69'] += 1

    print("By Match Type:")
    for mtype, count in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {mtype}: {count}")

    print()
    print("By Match Score:")
    for score_range, count in by_score.items():
        print(f"  {score_range}: {count}")

    if no_match_sources:
        print()
        print("-" * 70)
        print("SOURCES WITH NO MATCHING MEDIA (manual review needed):")
        print("-" * 70)
        for src in no_match_sources[:20]:
            print(f"  SourceID {src.source_id}: {src.state}, {src.county} - {src.surname}, {src.given}")
        if len(no_match_sources) > 20:
            print(f"  ... and {len(no_match_sources) - 20} more")

    print()
    print(f"Output written to: {output_path}")
    print()
    print("Next steps:")
    print("1. Open the CSV in a spreadsheet application")
    print("2. Review the 'Recommend' column (Y=recommended, ?=needs review)")
    print("3. Change 'Recommend' to 'N' for any incorrect matches")
    print("4. Save the CSV")
    print("5. Run the apply script with the reviewed CSV")

    return 0


if __name__ == '__main__':
    sys.exit(main())
