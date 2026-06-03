#!/usr/bin/env python3
"""
Fix 1930 Census sources missing media attachments.

This script identifies 1930 Census sources without media links and creates
the necessary MediaLinkTable entries to connect them to existing media records.

Usage:
    # Dry run (default) - shows what would be changed
    uv run python scripts/fix_1930_census_media.py

    # Actually apply changes
    uv run python scripts/fix_1930_census_media.py --apply

The script:
1. Finds 1930 Census sources without media attached
2. Matches them to existing media records by county name
3. Creates MediaLinkTable entries to link them
"""

import argparse
import re
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rmcitecraft.database.connection import connect_rmtree


def extract_location(source_name: str) -> tuple[str, str] | None:
    """Extract state and county from source name."""
    match = re.search(r'Fed Census: 1930, ([^,]+), ([^\[]+)', source_name)
    if match:
        state = match.group(1).strip()
        county = match.group(2).strip()
        return state, county
    return None


def find_matching_media(cursor, state: str, county: str) -> tuple[int, str] | None:
    """Find existing media record for a county."""
    # Try exact match first
    cursor.execute('''
    SELECT MediaID, Caption
    FROM MultimediaTable
    WHERE Caption LIKE ?
      AND MediaPath LIKE '%1930 Federal%'
    LIMIT 1
    ''', (f'%{county}, {state[:2].upper()}%',))

    row = cursor.fetchone()
    if row:
        return row[0], row[1]

    # Try partial match on county name
    cursor.execute('''
    SELECT MediaID, Caption
    FROM MultimediaTable
    WHERE Caption LIKE ?
      AND MediaPath LIKE '%1930 Federal%'
    LIMIT 1
    ''', (f'%{county}%',))

    row = cursor.fetchone()
    if row:
        return row[0], row[1]

    return None


def get_sources_without_media(cursor) -> list[dict]:
    """Get all 1930 Census sources without media attachments."""
    cursor.execute('''
    SELECT
      s.SourceID,
      s.Name
    FROM SourceTable s
    WHERE s.Name LIKE '%1930%' AND s.Name LIKE '%Census%'
      AND s.Name NOT LIKE '%citing family 1930%'
      AND NOT EXISTS (
        SELECT 1 FROM MediaLinkTable ml
        WHERE ml.OwnerID = s.SourceID AND ml.OwnerType = 3
      )
      AND NOT EXISTS (
        SELECT 1 FROM CitationTable c
        JOIN MediaLinkTable ml ON ml.OwnerID = c.CitationID AND ml.OwnerType = 4
        WHERE c.SourceID = s.SourceID
      )
    ORDER BY s.Name
    ''')

    sources = []
    for row in cursor.fetchall():
        source_id, name = row
        location = extract_location(name)
        if location:
            state, county = location
            sources.append({
                'source_id': source_id,
                'name': name,
                'state': state,
                'county': county
            })
    return sources


def get_max_link_id(cursor) -> int:
    """Get the current maximum LinkID."""
    cursor.execute('SELECT MAX(LinkID) FROM MediaLinkTable')
    result = cursor.fetchone()[0]
    return result if result else 0


def create_media_link(cursor, link_id: int, media_id: int, source_id: int) -> None:
    """Create a MediaLinkTable entry."""
    utc_mod_date = time.time()
    cursor.execute('''
    INSERT INTO MediaLinkTable (
        LinkID, MediaID, OwnerType, OwnerID, IsPrimary,
        Include1, Include2, Include3, Include4,
        SortOrder, RectLeft, RectTop, RectRight, RectBottom,
        Comments, UTCModDate
    ) VALUES (?, ?, 3, ?, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, '', ?)
    ''', (link_id, media_id, source_id, utc_mod_date))


def main():
    parser = argparse.ArgumentParser(
        description='Fix 1930 Census sources missing media attachments'
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

    print("=" * 60)
    print("1930 Census Media Link Fixer")
    print("=" * 60)
    print(f"Database: {args.database}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'APPLY CHANGES'}")
    print()

    # Connect (read-only for dry run, read-write for apply)
    conn = connect_rmtree(args.database, read_only=dry_run)
    cursor = conn.cursor()

    # Get sources without media
    print("Scanning for 1930 Census sources without media...")
    sources = get_sources_without_media(cursor)
    print(f"Found {len(sources)} sources without media attachments")
    print()

    # Categorize by whether we can find matching media
    can_link = []
    cannot_link = []

    for src in sources:
        media = find_matching_media(cursor, src['state'], src['county'])
        if media:
            src['media_id'] = media[0]
            src['media_caption'] = media[1]
            can_link.append(src)
        else:
            cannot_link.append(src)

    print(f"Can link to existing media: {len(can_link)}")
    print(f"No matching media found: {len(cannot_link)}")
    print()

    # Report on sources that can be linked
    if can_link:
        print("-" * 60)
        print("SOURCES THAT WILL BE LINKED:")
        print("-" * 60)
        for i, src in enumerate(can_link[:20], 1):
            print(f"{i:3d}. SourceID {src['source_id']}: {src['county']}, {src['state']}")
            print(f"     -> MediaID {src['media_id']}: {src['media_caption']}")
        if len(can_link) > 20:
            print(f"     ... and {len(can_link) - 20} more")
        print()

    # Report on sources without matching media
    if cannot_link:
        print("-" * 60)
        print("SOURCES WITHOUT MATCHING MEDIA (manual review needed):")
        print("-" * 60)
        for src in cannot_link:
            print(f"  SourceID {src['source_id']}: {src['county']}, {src['state']}")
            print(f"    Name: {src['name'][:80]}...")
        print()

    # Apply changes if requested
    if not dry_run and can_link:
        print("-" * 60)
        print("APPLYING CHANGES...")
        print("-" * 60)

        link_id = get_max_link_id(cursor)
        created = 0

        for src in can_link:
            link_id += 1
            create_media_link(cursor, link_id, src['media_id'], src['source_id'])
            created += 1
            if created % 50 == 0:
                print(f"  Created {created} links...")

        conn.commit()
        print(f"Successfully created {created} MediaLink entries")
        print()

    conn.close()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total sources checked: {len(sources)}")
    print(f"Sources linked to media: {len(can_link)}")
    print(f"Sources needing manual review: {len(cannot_link)}")

    if dry_run and can_link:
        print()
        print("To apply changes, run:")
        print(f"  uv run python scripts/fix_1930_census_media.py --apply")

    return 0


if __name__ == '__main__':
    sys.exit(main())
