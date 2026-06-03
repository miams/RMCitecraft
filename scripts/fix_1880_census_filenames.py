#!/usr/bin/env python3
"""
Fix 1880 Census Image Filenames

This script corrects capitalization and abbreviation issues in 1880 Census
image filenames and updates the RootsMagic database to match.

Issues addressed:
- State postal abbreviations (CA, OH, PA) -> full names (California, Ohio, Pennsylvania)
- All-caps state names (ARKANSAS, ILLINOIS) -> proper case (Arkansas, Illinois)
- Misspellings (Pennyslvania -> Pennsylvania)

Usage:
    # Test mode (no changes made)
    python scripts/fix_1880_census_filenames.py --test

    # Apply changes
    python scripts/fix_1880_census_filenames.py --apply

    # Specify custom paths
    python scripts/fix_1880_census_filenames.py --test \\
        --media-dir "~/Genealogy/RootsMagic/Files/Records - Census/1880 Federal" \\
        --database data/Iiams.rmtree
"""

import argparse
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rmcitecraft.database.connection import connect_rmtree


# State postal code to full name mapping
POSTAL_TO_FULL = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
    "DC": "District of Columbia",
}

# Common misspellings
MISSPELLINGS = {
    "Pennyslvania": "Pennsylvania",
}

# Build lookup for all-caps state names
STATE_NAMES = set(POSTAL_TO_FULL.values())
STATE_UPPER_TO_PROPER = {name.upper(): name for name in STATE_NAMES}


@dataclass
class FilenameChange:
    """Represents a filename change to be made."""
    media_id: int | None
    old_filename: str
    new_filename: str
    old_path: Path
    new_path: Path
    reason: str


def normalize_state_name(state: str) -> tuple[str, str | None]:
    """
    Normalize a state name to proper format.

    Returns:
        Tuple of (normalized_name, reason) where reason is None if no change needed.
    """
    original = state.strip()

    # Check for postal abbreviation
    if original.upper() in POSTAL_TO_FULL:
        full_name = POSTAL_TO_FULL[original.upper()]
        if original != full_name:
            return full_name, f"postal abbreviation '{original}' -> '{full_name}'"

    # Check for misspelling
    if original in MISSPELLINGS:
        corrected = MISSPELLINGS[original]
        return corrected, f"misspelling '{original}' -> '{corrected}'"

    # Check for all-caps
    if original.upper() in STATE_UPPER_TO_PROPER:
        proper = STATE_UPPER_TO_PROPER[original.upper()]
        if original != proper and original == original.upper():
            return proper, f"all-caps '{original}' -> '{proper}'"

    # Check for wrong case (not all caps but not proper case)
    if original.upper() in STATE_UPPER_TO_PROPER:
        proper = STATE_UPPER_TO_PROPER[original.upper()]
        if original != proper:
            return proper, f"case fix '{original}' -> '{proper}'"

    return original, None


def parse_filename(filename: str) -> dict | None:
    """
    Parse a 1880 Census filename into components.

    Expected format: "1880, State, County - Name.jpg"

    Returns:
        Dictionary with keys: year, state, county, name, extension
        or None if filename doesn't match expected pattern.
    """
    # Pattern: 1880, State, County - Name.jpg
    # State can be: full name, abbreviation, or all caps
    # County can have spaces (e.g., "Mc Lean", "San Luis Obispo")
    # Name can have parentheses, periods, underscores

    match = re.match(
        r'^(\d{4}),\s*([^,]+),\s*([^-]+)\s*-\s*(.+)\.(\w+)$',
        filename
    )

    if not match:
        return None

    year, state, county, name, ext = match.groups()

    return {
        'year': year.strip(),
        'state': state.strip(),
        'county': county.strip(),
        'name': name.strip(),
        'extension': ext.strip(),
    }


def build_filename(components: dict) -> str:
    """Build a filename from components."""
    return f"{components['year']}, {components['state']}, {components['county']} - {components['name']}.{components['extension']}"


def analyze_files(media_dir: Path) -> list[FilenameChange]:
    """
    Analyze files in the media directory and identify needed changes.

    Returns:
        List of FilenameChange objects for files that need renaming.
    """
    changes = []

    if not media_dir.exists():
        print(f"ERROR: Media directory does not exist: {media_dir}")
        return changes

    for filepath in sorted(media_dir.iterdir()):
        if not filepath.is_file():
            continue

        filename = filepath.name

        # Skip non-image files
        if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff')):
            continue

        # Parse filename
        components = parse_filename(filename)
        if not components:
            print(f"  WARNING: Could not parse filename: {filename}")
            continue

        # Check if year is 1880
        if components['year'] != '1880':
            continue

        # Normalize state name
        normalized_state, reason = normalize_state_name(components['state'])

        if reason:
            # State needs fixing
            new_components = components.copy()
            new_components['state'] = normalized_state
            new_filename = build_filename(new_components)

            changes.append(FilenameChange(
                media_id=None,  # Will be filled in later
                old_filename=filename,
                new_filename=new_filename,
                old_path=filepath,
                new_path=filepath.parent / new_filename,
                reason=reason,
            ))

    return changes


def load_database_media(db_path: Path, changes: list[FilenameChange]) -> list[FilenameChange]:
    """
    Load media IDs from database for files that need changes.

    Updates the media_id field in each FilenameChange.

    Returns:
        Updated list with media IDs populated (or None if not found in DB).
    """
    if not db_path.exists():
        print(f"ERROR: Database does not exist: {db_path}")
        return changes

    # Connect using proper RMNOCASE collation support
    icu_path = Path(__file__).parent.parent / 'sqlite-extension' / 'icu.dylib'
    try:
        conn = connect_rmtree(db_path, icu_path, read_only=True)
    except Exception as e:
        print(f"  Warning: Could not connect to database: {e}")
        return changes

    cur = conn.cursor()

    # Build lookup of filename -> change
    filename_to_change = {c.old_filename: c for c in changes}

    # Query database for matching media files
    cur.execute("""
        SELECT MediaID, MediaFile
        FROM MultimediaTable
        WHERE MediaPath LIKE '%1880 Federal%'
    """)

    for media_id, media_file in cur.fetchall():
        if media_file in filename_to_change:
            filename_to_change[media_file].media_id = media_id

    conn.close()
    return changes


def apply_changes(
    changes: list[FilenameChange],
    db_path: Path,
    dry_run: bool = True
) -> tuple[int, int, int]:
    """
    Apply filename changes to files and database.

    Args:
        changes: List of FilenameChange objects
        db_path: Path to RootsMagic database
        dry_run: If True, don't make any changes (test mode)

    Returns:
        Tuple of (files_renamed, db_updated, errors)
    """
    files_renamed = 0
    db_updated = 0
    errors = 0

    if dry_run:
        print("\n" + "=" * 60)
        print("TEST MODE - No changes will be made")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("APPLY MODE - Making changes")
        print("=" * 60)

    # Group changes by whether they have database records
    with_db = [c for c in changes if c.media_id is not None]
    without_db = [c for c in changes if c.media_id is None]

    print(f"\nFiles to rename: {len(changes)}")
    print(f"  With database record: {len(with_db)}")
    print(f"  Without database record: {len(without_db)}")

    if without_db:
        print("\n  WARNING: These files have no database record:")
        for c in without_db[:10]:
            print(f"    {c.old_filename}")
        if len(without_db) > 10:
            print(f"    ... and {len(without_db) - 10} more")

    # Open database connection for updates
    conn = None
    cur = None
    if not dry_run and with_db:
        icu_path = Path(__file__).parent.parent / 'sqlite-extension' / 'icu.dylib'
        try:
            conn = connect_rmtree(db_path, icu_path, read_only=False)
            cur = conn.cursor()
        except Exception as e:
            print(f"ERROR: Could not connect to database: {e}")
            return 0, 0, len(changes)

    # Process each change
    print("\nProcessing changes:")
    for i, change in enumerate(changes, 1):
        action = "Would rename" if dry_run else "Renaming"
        print(f"\n  [{i}/{len(changes)}] {action}:")
        print(f"    From: {change.old_filename}")
        print(f"    To:   {change.new_filename}")
        print(f"    Reason: {change.reason}")

        if change.media_id:
            print(f"    Database MediaID: {change.media_id}")
        else:
            print(f"    Database: NOT FOUND")

        if dry_run:
            files_renamed += 1
            if change.media_id:
                db_updated += 1
            continue

        # Check if new filename already exists
        if change.new_path.exists() and change.new_path != change.old_path:
            print(f"    ERROR: Target file already exists!")
            errors += 1
            continue

        # Rename file
        try:
            if change.old_path.exists():
                change.old_path.rename(change.new_path)
                files_renamed += 1
                print(f"    File renamed successfully")
            else:
                print(f"    ERROR: Source file does not exist!")
                errors += 1
                continue
        except OSError as e:
            print(f"    ERROR: Failed to rename file: {e}")
            errors += 1
            continue

        # Update database
        if change.media_id and conn:
            try:
                cur.execute(
                    "UPDATE MultimediaTable SET MediaFile = ? WHERE MediaID = ?",
                    (change.new_filename, change.media_id)
                )
                db_updated += 1
                print(f"    Database updated successfully")
            except sqlite3.Error as e:
                print(f"    ERROR: Failed to update database: {e}")
                errors += 1

    # Commit database changes
    if conn:
        conn.commit()
        conn.close()
        print(f"\n  Database changes committed.")

    return files_renamed, db_updated, errors


def main():
    parser = argparse.ArgumentParser(
        description="Fix 1880 Census image filenames and update RootsMagic database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Test mode (no changes):
    python scripts/fix_1880_census_filenames.py --test

  Apply changes:
    python scripts/fix_1880_census_filenames.py --apply

  Custom paths:
    python scripts/fix_1880_census_filenames.py --test \\
        --media-dir ~/Genealogy/RootsMagic/Files/Records\\ -\\ Census/1880\\ Federal \\
        --database data/Iiams.rmtree
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
        help='Apply mode - rename files and update database'
    )

    parser.add_argument(
        '--media-dir',
        type=Path,
        default=Path.home() / 'Genealogy' / 'RootsMagic' / 'Files' / 'Records - Census' / '1880 Federal',
        help='Directory containing 1880 Census images (default: ~/Genealogy/RootsMagic/Files/Records - Census/1880 Federal)'
    )

    parser.add_argument(
        '--database',
        type=Path,
        default=Path('data/Iiams.rmtree'),
        help='Path to RootsMagic database (default: data/Iiams.rmtree)'
    )

    args = parser.parse_args()

    print("=" * 60)
    print("1880 Census Filename Fixer")
    print("=" * 60)
    print(f"\nMedia directory: {args.media_dir}")
    print(f"Database: {args.database}")
    print(f"Mode: {'TEST (no changes)' if args.test else 'APPLY (will modify files and database)'}")

    # Analyze files
    print("\n" + "-" * 60)
    print("Analyzing files...")
    print("-" * 60)

    changes = analyze_files(args.media_dir)

    if not changes:
        print("\nNo files need renaming!")
        return 0

    print(f"\nFound {len(changes)} files that need renaming:")

    # Categorize by reason
    by_reason = {}
    for c in changes:
        # Extract reason type
        if 'postal abbreviation' in c.reason:
            reason_type = 'Postal abbreviations'
        elif 'all-caps' in c.reason:
            reason_type = 'All-caps state names'
        elif 'misspelling' in c.reason:
            reason_type = 'Misspellings'
        elif 'case fix' in c.reason:
            reason_type = 'Case fixes'
        else:
            reason_type = 'Other'

        if reason_type not in by_reason:
            by_reason[reason_type] = []
        by_reason[reason_type].append(c)

    for reason_type, items in sorted(by_reason.items()):
        print(f"\n  {reason_type}: {len(items)}")
        for c in items[:5]:
            print(f"    {c.old_filename}")
            print(f"      -> {c.new_filename}")
        if len(items) > 5:
            print(f"    ... and {len(items) - 5} more")

    # Load database info
    print("\n" + "-" * 60)
    print("Checking database records...")
    print("-" * 60)

    changes = load_database_media(args.database, changes)

    with_db = sum(1 for c in changes if c.media_id is not None)
    without_db = len(changes) - with_db

    print(f"\n  Files with database records: {with_db}")
    print(f"  Files without database records: {without_db}")

    # Apply or report changes
    files_renamed, db_updated, errors = apply_changes(
        changes,
        args.database,
        dry_run=args.test
    )

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if args.test:
        print(f"\n  Files that would be renamed: {files_renamed}")
        print(f"  Database records that would be updated: {db_updated}")
        print(f"\n  Run with --apply to make these changes.")
    else:
        print(f"\n  Files renamed: {files_renamed}")
        print(f"  Database records updated: {db_updated}")
        print(f"  Errors: {errors}")

    return 0 if errors == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
