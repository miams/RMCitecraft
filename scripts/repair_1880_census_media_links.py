#!/usr/bin/env python3
"""
Repair Missing 1880 Census Media Links

This script adds missing MediaLinkTable entries for 1880 Census media files.
Each census media should have 3 links: Event, Citation, and Source.

Issues addressed:
- Media linked only to Source (missing Event and Citation links)
- Media linked only to Event (missing Source and Citation links)
- Media linked only to Citation (missing Event and Source links)

Usage:
    # Test mode (no changes made)
    python scripts/repair_1880_census_media_links.py --test

    # Apply changes
    python scripts/repair_1880_census_media_links.py --apply

    # Specify custom database path
    python scripts/repair_1880_census_media_links.py --test --database data/Iiams.rmtree
"""

import argparse
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rmcitecraft.database.connection import connect_rmtree

# OwnerType values from schema-reference.md
OWNER_TYPE_PERSON = 0
OWNER_TYPE_FAMILY = 1
OWNER_TYPE_EVENT = 2
OWNER_TYPE_SOURCE = 3
OWNER_TYPE_CITATION = 4

OWNER_TYPE_NAMES = {
    OWNER_TYPE_PERSON: "Person",
    OWNER_TYPE_FAMILY: "Family",
    OWNER_TYPE_EVENT: "Event",
    OWNER_TYPE_SOURCE: "Source",
    OWNER_TYPE_CITATION: "Citation",
}


@dataclass
class MissingLink:
    """Represents a missing MediaLinkTable entry to be added."""
    media_id: int
    media_file: str
    owner_type: int
    owner_id: int
    reason: str

    @property
    def owner_type_name(self) -> str:
        return OWNER_TYPE_NAMES.get(self.owner_type, f"Unknown({self.owner_type})")


def get_1880_census_media(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    """Get all 1880 Census media files."""
    cur = conn.cursor()
    cur.execute("""
        SELECT MediaID, MediaFile
        FROM MultimediaTable
        WHERE MediaPath LIKE '%1880 Federal%'
        ORDER BY MediaFile
    """)
    return cur.fetchall()


def get_media_links(conn: sqlite3.Connection, media_id: int) -> dict[int, int]:
    """Get existing links for a media file.

    Returns:
        Dict mapping OwnerType -> OwnerID
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT OwnerType, OwnerID
        FROM MediaLinkTable
        WHERE MediaID = ?
    """, (media_id,))
    return {row[0]: row[1] for row in cur.fetchall()}


def find_citation_from_source(conn: sqlite3.Connection, source_id: int) -> int | None:
    """Find a Citation linked to this Source (for 1880 Census)."""
    cur = conn.cursor()
    cur.execute("""
        SELECT CitationID
        FROM CitationTable
        WHERE SourceID = ?
        LIMIT 1
    """, (source_id,))
    row = cur.fetchone()
    return row[0] if row else None


def find_event_from_citation(conn: sqlite3.Connection, citation_id: int) -> int | None:
    """Find an Event linked to this Citation (OwnerType=2 means Event)."""
    cur = conn.cursor()
    cur.execute("""
        SELECT OwnerID
        FROM CitationLinkTable
        WHERE CitationID = ? AND OwnerType = 2
        LIMIT 1
    """, (citation_id,))
    row = cur.fetchone()
    return row[0] if row else None


def find_citation_from_event(conn: sqlite3.Connection, event_id: int) -> int | None:
    """Find a Citation linked to this Event."""
    cur = conn.cursor()
    cur.execute("""
        SELECT CitationID
        FROM CitationLinkTable
        WHERE OwnerID = ? AND OwnerType = 2
        LIMIT 1
    """, (event_id,))
    row = cur.fetchone()
    return row[0] if row else None


def find_source_from_citation(conn: sqlite3.Connection, citation_id: int) -> int | None:
    """Find the Source for this Citation."""
    cur = conn.cursor()
    cur.execute("""
        SELECT SourceID
        FROM CitationTable
        WHERE CitationID = ?
    """, (citation_id,))
    row = cur.fetchone()
    return row[0] if row else None


def find_missing_links(conn: sqlite3.Connection) -> list[MissingLink]:
    """Find all missing MediaLinkTable entries for 1880 Census media."""
    missing = []
    media_files = get_1880_census_media(conn)

    for media_id, media_file in media_files:
        existing_links = get_media_links(conn, media_id)

        has_event = OWNER_TYPE_EVENT in existing_links
        has_source = OWNER_TYPE_SOURCE in existing_links
        has_citation = OWNER_TYPE_CITATION in existing_links

        # Skip if already complete
        if has_event and has_source and has_citation:
            continue

        # Determine what we have and find the missing links
        event_id = existing_links.get(OWNER_TYPE_EVENT)
        source_id = existing_links.get(OWNER_TYPE_SOURCE)
        citation_id = existing_links.get(OWNER_TYPE_CITATION)

        # Try to find missing IDs by following the relationship chain
        if has_source and not has_citation:
            # Source -> Citation
            citation_id = find_citation_from_source(conn, source_id)

        if has_source and not has_event and citation_id:
            # Citation -> Event
            event_id = find_event_from_citation(conn, citation_id)

        if has_event and not has_citation:
            # Event -> Citation
            citation_id = find_citation_from_event(conn, event_id)

        if has_event and not has_source and citation_id:
            # Citation -> Source
            source_id = find_source_from_citation(conn, citation_id)

        if has_citation and not has_source:
            # Citation -> Source
            source_id = find_source_from_citation(conn, citation_id)

        if has_citation and not has_event:
            # Citation -> Event
            event_id = find_event_from_citation(conn, citation_id)

        # Now add missing links if we found the IDs
        if not has_event and event_id:
            missing.append(MissingLink(
                media_id=media_id,
                media_file=media_file,
                owner_type=OWNER_TYPE_EVENT,
                owner_id=event_id,
                reason="Event link missing (found via Citation)"
            ))

        if not has_source and source_id:
            missing.append(MissingLink(
                media_id=media_id,
                media_file=media_file,
                owner_type=OWNER_TYPE_SOURCE,
                owner_id=source_id,
                reason="Source link missing (found via Citation)"
            ))

        if not has_citation and citation_id:
            missing.append(MissingLink(
                media_id=media_id,
                media_file=media_file,
                owner_type=OWNER_TYPE_CITATION,
                owner_id=citation_id,
                reason="Citation link missing (found via Event/Source)"
            ))

    return missing


def get_next_link_id(conn: sqlite3.Connection) -> int:
    """Get the next available LinkID for MediaLinkTable."""
    cur = conn.cursor()
    cur.execute("SELECT MAX(LinkID) FROM MediaLinkTable")
    row = cur.fetchone()
    return (row[0] or 0) + 1


def apply_missing_links(
    conn: sqlite3.Connection,
    missing: list[MissingLink],
    dry_run: bool = True
) -> tuple[int, int]:
    """Apply missing links to database.

    Returns:
        Tuple of (success_count, error_count)
    """
    if dry_run:
        print("\n" + "=" * 60)
        print("TEST MODE - No changes will be made")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("APPLY MODE - Adding missing links")
        print("=" * 60)

    success = 0
    errors = 0

    cur = conn.cursor()
    next_link_id = get_next_link_id(conn)

    # Group by media file for cleaner output
    by_media = {}
    for link in missing:
        if link.media_file not in by_media:
            by_media[link.media_file] = []
        by_media[link.media_file].append(link)

    print(f"\nMedia files to update: {len(by_media)}")
    print(f"Total links to add: {len(missing)}")

    for media_file, links in sorted(by_media.items()):
        print(f"\n  {media_file}")
        for link in links:
            action = "Would add" if dry_run else "Adding"
            print(f"    {action}: {link.owner_type_name} (ID={link.owner_id})")

            if dry_run:
                success += 1
                continue

            try:
                # Check if link already exists (safety check)
                cur.execute("""
                    SELECT 1 FROM MediaLinkTable
                    WHERE MediaID = ? AND OwnerType = ? AND OwnerID = ?
                """, (link.media_id, link.owner_type, link.owner_id))

                if cur.fetchone():
                    print(f"      SKIP: Link already exists")
                    continue

                # Insert new link
                # MediaLinkTable schema: LinkID, MediaID, OwnerType, OwnerID,
                #                        IsPrimary, Include1, Include2, Include3, Include4,
                #                        SortOrder, UTCModDate
                cur.execute("""
                    INSERT INTO MediaLinkTable
                    (LinkID, MediaID, OwnerType, OwnerID, IsPrimary,
                     Include1, Include2, Include3, Include4, SortOrder, UTCModDate)
                    VALUES (?, ?, ?, ?, 0, 1, 1, 1, 1, 0, 0)
                """, (next_link_id, link.media_id, link.owner_type, link.owner_id))

                next_link_id += 1
                success += 1
                print(f"      OK: Added LinkID {next_link_id - 1}")

            except sqlite3.Error as e:
                errors += 1
                print(f"      ERROR: {e}")

    if not dry_run:
        conn.commit()
        print(f"\n  Database changes committed.")

    return success, errors


def main():
    parser = argparse.ArgumentParser(
        description="Repair missing 1880 Census media links in RootsMagic database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Test mode (no changes):
    python scripts/repair_1880_census_media_links.py --test

  Apply changes:
    python scripts/repair_1880_census_media_links.py --apply
        """
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        '--test',
        action='store_true',
        help='Test mode - analyze and report changes without modifying anything'
    )
    mode_group.add_argument(
        '--apply',
        action='store_true',
        help='Apply mode - add missing links to database'
    )

    parser.add_argument(
        '--database',
        type=Path,
        default=Path('data/Iiams.rmtree'),
        help='Path to RootsMagic database (default: data/Iiams.rmtree)'
    )

    args = parser.parse_args()

    print("=" * 60)
    print("1880 Census Media Link Repair")
    print("=" * 60)
    print(f"\nDatabase: {args.database}")
    print(f"Mode: {'TEST (no changes)' if args.test else 'APPLY (will modify database)'}")

    # Connect to database using connect_rmtree for proper RMNOCASE support
    icu_path = Path(__file__).parent.parent / "sqlite-extension" / "icu.dylib"

    try:
        conn = connect_rmtree(args.database, icu_path, read_only=args.test)
        print(f"Connected to database with RMNOCASE collation support")
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)

    # Find missing links
    print("\n" + "-" * 60)
    print("Analyzing media links...")
    print("-" * 60)

    missing = find_missing_links(conn)

    if not missing:
        print("\nNo missing links found! All 1880 Census media files have complete links.")
        conn.close()
        return 0

    # Categorize by what's missing
    by_type = {}
    for link in missing:
        if link.owner_type_name not in by_type:
            by_type[link.owner_type_name] = []
        by_type[link.owner_type_name].append(link)

    print(f"\nFound {len(missing)} missing links:")
    for owner_type, links in sorted(by_type.items()):
        print(f"  {owner_type}: {len(links)} links")
        # Show examples
        unique_files = list(set(l.media_file for l in links))[:3]
        for f in unique_files:
            print(f"    - {f}")
        if len(unique_files) < len(set(l.media_file for l in links)):
            print(f"    ... and {len(set(l.media_file for l in links)) - 3} more files")

    # Apply changes
    success, errors = apply_missing_links(conn, missing, dry_run=args.test)

    conn.close()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if args.test:
        print(f"\n  Links that would be added: {success}")
        print(f"\n  Run with --apply to make these changes.")
    else:
        print(f"\n  Links added: {success}")
        print(f"  Errors: {errors}")

    return 0 if errors == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
