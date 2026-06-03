#!/usr/bin/env python3
"""
Analyze 1930 Census media with only 1 link (to Event).

For each such media, traces the chain:
  Media -> Event -> Citation -> Source

Outputs a CSV showing which Sources and Citations should be linked to the Media.

Usage:
    uv run python scripts/analyze_1930_single_link_media.py

Output:
    data/1930_census_single_link_media_analysis.csv
"""

import csv
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rmcitecraft.database.connection import connect_rmtree


def main():
    database_path = 'data/Iiams.rmtree'
    output_path = 'data/1930_census_single_link_media_analysis.csv'

    print("=" * 70)
    print("1930 Census Single-Link Media Analysis")
    print("=" * 70)
    print(f"Database: {database_path}")
    print(f"Output: {output_path}")
    print()

    conn = connect_rmtree(database_path, read_only=True)
    cursor = conn.cursor()

    # Find all 1930 Census media with exactly 1 link
    print("Finding media with exactly 1 link...")
    cursor.execute('''
    SELECT m.MediaID, m.MediaFile, m.Caption, ml.OwnerType, ml.OwnerID
    FROM MultimediaTable m
    JOIN MediaLinkTable ml ON ml.MediaID = m.MediaID
    WHERE m.MediaPath LIKE '%1930 Federal%'
    GROUP BY m.MediaID
    HAVING COUNT(ml.LinkID) = 1
    ''')

    single_link_media = cursor.fetchall()
    print(f"  Found {len(single_link_media)} media with exactly 1 link")
    print()

    results = []
    event_linked = 0
    source_linked = 0
    citation_linked = 0
    other_linked = 0

    for media_id, media_file, caption, owner_type, owner_id in single_link_media:
        owner_type_name = {0: 'Person', 1: 'Family', 2: 'Event', 3: 'Source', 4: 'Citation'}.get(owner_type, f'Unknown({owner_type})')

        if owner_type == 2:  # Event
            event_linked += 1

            # Get event details
            cursor.execute('''
            SELECT e.EventID, e.OwnerID, e.Date, n.Given, n.Surname, f.Name as EventType
            FROM EventTable e
            JOIN NameTable n ON e.OwnerID = n.OwnerID AND n.IsPrimary = 1
            JOIN FactTypeTable f ON e.EventType = f.FactTypeID
            WHERE e.EventID = ?
            ''', (owner_id,))
            event_row = cursor.fetchone()

            if event_row:
                event_id, person_id, event_date, given, surname, event_type = event_row

                # Get citations linked to this event that are 1930 Census
                cursor.execute('''
                SELECT cl.CitationID, c.SourceID, s.SourceID, s.Name
                FROM CitationLinkTable cl
                JOIN CitationTable c ON cl.CitationID = c.CitationID
                JOIN SourceTable s ON c.SourceID = s.SourceID
                WHERE cl.OwnerType = 2 AND cl.OwnerID = ?
                  AND s.Name LIKE 'Fed Census: 1930%'
                ''', (event_id,))
                citations = cursor.fetchall()

                for cit_row in citations:
                    cit_id, _, source_id, source_name = cit_row

                    # Check if source already has this media linked
                    cursor.execute('''
                    SELECT 1 FROM MediaLinkTable
                    WHERE MediaID = ? AND OwnerType = 3 AND OwnerID = ?
                    ''', (media_id, source_id))
                    source_has_media = cursor.fetchone() is not None

                    # Check if citation already has this media linked
                    cursor.execute('''
                    SELECT 1 FROM MediaLinkTable
                    WHERE MediaID = ? AND OwnerType = 4 AND OwnerID = ?
                    ''', (media_id, cit_id))
                    citation_has_media = cursor.fetchone() is not None

                    results.append({
                        'media_id': media_id,
                        'media_file': media_file,
                        'media_caption': caption,
                        'current_link_type': owner_type_name,
                        'event_id': event_id,
                        'event_type': event_type,
                        'person_id': person_id,
                        'person_name': f'{given} {surname}',
                        'citation_id': cit_id,
                        'source_id': source_id,
                        'source_name': source_name,
                        'source_has_media': source_has_media,
                        'citation_has_media': citation_has_media,
                        'needs_source_link': not source_has_media,
                        'needs_citation_link': not citation_has_media
                    })

        elif owner_type == 3:  # Source
            source_linked += 1
        elif owner_type == 4:  # Citation
            citation_linked += 1
        else:
            other_linked += 1

    print(f"Link type breakdown:")
    print(f"  Event: {event_linked}")
    print(f"  Source: {source_linked}")
    print(f"  Citation: {citation_linked}")
    print(f"  Other: {other_linked}")
    print()

    # Count what needs to be linked
    needs_source = sum(1 for r in results if r['needs_source_link'])
    needs_citation = sum(1 for r in results if r['needs_citation_link'])

    print(f"Analysis results:")
    print(f"  Total records with Event->Citation->Source chain: {len(results)}")
    print(f"  Need Source link added: {needs_source}")
    print(f"  Need Citation link added: {needs_citation}")
    print()

    # Write CSV
    print(f"Writing to {output_path}...")

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        writer.writerow([
            'Add Source Link',
            'Add Citation Link',
            'Media ID',
            'Media File',
            'Media Caption',
            'Event ID',
            'Event Type',
            'Person ID',
            'Person Name',
            'Citation ID',
            'Source ID',
            'Source Already Linked',
            'Citation Already Linked',
            'Source Name'
        ])

        for r in results:
            writer.writerow([
                'Y' if r['needs_source_link'] else 'N',
                'Y' if r['needs_citation_link'] else 'N',
                r['media_id'],
                r['media_file'],
                r['media_caption'],
                r['event_id'],
                r['event_type'],
                r['person_id'],
                r['person_name'],
                r['citation_id'],
                r['source_id'],
                'N' if r['needs_source_link'] else 'Y',
                'N' if r['needs_citation_link'] else 'Y',
                r['source_name']
            ])

    conn.close()

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Media with single link (Event only): {event_linked}")
    print(f"Records analyzed: {len(results)}")
    print(f"Sources needing link to media: {needs_source}")
    print(f"Citations needing link to media: {needs_citation}")
    print()
    print(f"Output written to: {output_path}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
