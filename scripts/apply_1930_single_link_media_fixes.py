#!/usr/bin/env python3
"""
Apply missing Source and Citation links for 1930 Census media.

This script adds MediaLinkTable entries to connect Sources and Citations
to their associated Media records, based on the Event->Citation->Source chain.

Usage:
    # Dry run (default)
    uv run python scripts/apply_1930_single_link_media_fixes.py

    # Apply changes
    uv run python scripts/apply_1930_single_link_media_fixes.py --apply
"""

import argparse
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rmcitecraft.database.connection import connect_rmtree


def get_max_link_id(cursor) -> int:
    """Get the current maximum LinkID from MediaLinkTable."""
    cursor.execute('SELECT MAX(LinkID) FROM MediaLinkTable')
    result = cursor.fetchone()[0]
    return result if result else 0


def create_media_link(cursor, link_id: int, media_id: int, owner_type: int, owner_id: int) -> None:
    """Create a MediaLinkTable entry."""
    utc_mod_date = time.time()
    cursor.execute('''
    INSERT INTO MediaLinkTable (
        LinkID, MediaID, OwnerType, OwnerID, IsPrimary,
        Include1, Include2, Include3, Include4,
        SortOrder, RectLeft, RectTop, RectRight, RectBottom,
        Comments, UTCModDate
    ) VALUES (?, ?, ?, ?, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, '', ?)
    ''', (link_id, media_id, owner_type, owner_id, utc_mod_date))


def main():
    parser = argparse.ArgumentParser(
        description='Apply missing Source and Citation links for 1930 Census media'
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Actually apply changes (default is dry run)'
    )
    parser.add_argument(
        '--database',
        default='data/Iiams.rmtree',
        help='Path to RootsMagic database'
    )
    args = parser.parse_args()

    dry_run = not args.apply

    print("=" * 70)
    print("1930 Census Single-Link Media Fix")
    print("=" * 70)
    print(f"Database: {args.database}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'APPLY CHANGES'}")
    print()

    conn = connect_rmtree(args.database, read_only=dry_run)
    cursor = conn.cursor()

    # Find all 1930 Census media with exactly 1 link (to Event)
    print("Finding media with exactly 1 link to Event...")
    cursor.execute('''
    SELECT m.MediaID, m.MediaFile, ml.OwnerID as EventID
    FROM MultimediaTable m
    JOIN MediaLinkTable ml ON ml.MediaID = m.MediaID
    WHERE m.MediaPath LIKE '%1930 Federal%'
      AND ml.OwnerType = 2
    GROUP BY m.MediaID
    HAVING COUNT(ml.LinkID) = 1
    ''')

    single_link_media = cursor.fetchall()
    print(f"  Found {len(single_link_media)} media with single Event link")
    print()

    # Collect all the links we need to create
    links_to_create = []

    for media_id, media_file, event_id in single_link_media:
        # Get citations linked to this event that are 1930 Census
        cursor.execute('''
        SELECT cl.CitationID, c.SourceID, s.Name
        FROM CitationLinkTable cl
        JOIN CitationTable c ON cl.CitationID = c.CitationID
        JOIN SourceTable s ON c.SourceID = s.SourceID
        WHERE cl.OwnerType = 2 AND cl.OwnerID = ?
          AND s.Name LIKE 'Fed Census: 1930%'
        ''', (event_id,))
        citations = cursor.fetchall()

        for cit_id, source_id, source_name in citations:
            # Check if source already has this media linked
            cursor.execute('''
            SELECT 1 FROM MediaLinkTable
            WHERE MediaID = ? AND OwnerType = 3 AND OwnerID = ?
            ''', (media_id, source_id))
            if not cursor.fetchone():
                links_to_create.append({
                    'media_id': media_id,
                    'media_file': media_file,
                    'owner_type': 3,  # Source
                    'owner_type_name': 'Source',
                    'owner_id': source_id,
                    'owner_name': source_name[:60] + '...'
                })

            # Check if citation already has this media linked
            cursor.execute('''
            SELECT 1 FROM MediaLinkTable
            WHERE MediaID = ? AND OwnerType = 4 AND OwnerID = ?
            ''', (media_id, cit_id))
            if not cursor.fetchone():
                links_to_create.append({
                    'media_id': media_id,
                    'media_file': media_file,
                    'owner_type': 4,  # Citation
                    'owner_type_name': 'Citation',
                    'owner_id': cit_id,
                    'owner_name': f'Citation {cit_id} of Source {source_id}'
                })

    # Count by type
    source_links = [l for l in links_to_create if l['owner_type'] == 3]
    citation_links = [l for l in links_to_create if l['owner_type'] == 4]

    print(f"Links to create:")
    print(f"  Source links: {len(source_links)}")
    print(f"  Citation links: {len(citation_links)}")
    print(f"  Total: {len(links_to_create)}")
    print()

    # Show sample
    print("-" * 70)
    print("SAMPLE OF LINKS TO CREATE (first 10):")
    print("-" * 70)
    for link in links_to_create[:10]:
        print(f"  Media {link['media_id']} -> {link['owner_type_name']} {link['owner_id']}")
        print(f"    {link['media_file']}")
        print(f"    {link['owner_name']}")
        print()

    if len(links_to_create) > 10:
        print(f"  ... and {len(links_to_create) - 10} more")
    print()

    # Apply changes if not dry run
    if not dry_run and links_to_create:
        print("-" * 70)
        print("APPLYING CHANGES...")
        print("-" * 70)

        link_id = get_max_link_id(cursor)
        created = 0

        for link in links_to_create:
            link_id += 1
            create_media_link(
                cursor,
                link_id,
                link['media_id'],
                link['owner_type'],
                link['owner_id']
            )
            created += 1
            if created % 50 == 0:
                print(f"  Created {created} links...")

        conn.commit()
        print(f"  Successfully created {created} MediaLink entries")
        print()

    conn.close()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Media records processed: {len(single_link_media)}")
    print(f"Source links {'created' if not dry_run else 'to create'}: {len(source_links)}")
    print(f"Citation links {'created' if not dry_run else 'to create'}: {len(citation_links)}")
    print(f"Total links {'created' if not dry_run else 'to create'}: {len(links_to_create)}")

    if dry_run and links_to_create:
        print()
        print("To apply changes, run:")
        print(f"  uv run python scripts/apply_1930_single_link_media_fixes.py --apply")

    return 0


if __name__ == '__main__':
    sys.exit(main())
