#!/usr/bin/env python3
"""
Repair script for 1880 Census filename fixes.

This script:
1. Renames any remaining files that still need fixing
2. Updates all database records to match the actual filenames on disk

Run after the initial fix script had database errors.
"""

import re
import sqlite3
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rmcitecraft.database.connection import connect_rmtree


POSTAL_TO_FULL = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}

STATE_NAMES = set(POSTAL_TO_FULL.values())
STATE_UPPER_TO_PROPER = {name.upper(): name for name in STATE_NAMES}
MISSPELLINGS = {"Pennyslvania": "Pennsylvania"}


def normalize_state(state: str) -> str | None:
    """Return normalized state name or None if no change needed."""
    state = state.strip()

    # Postal abbreviation
    if state.upper() in POSTAL_TO_FULL:
        full = POSTAL_TO_FULL[state.upper()]
        if state != full:
            return full

    # Misspelling
    if state in MISSPELLINGS:
        return MISSPELLINGS[state]

    # All-caps
    if state.upper() in STATE_UPPER_TO_PROPER and state == state.upper():
        return STATE_UPPER_TO_PROPER[state.upper()]

    return None


def parse_and_normalize(filename: str) -> str | None:
    """Parse filename and return normalized version, or None if no change needed."""
    match = re.match(r'^(\d{4}),\s*([^,]+),\s*([^-]+)\s*-\s*(.+)\.(\w+)$', filename)
    if not match:
        return None

    year, state, county, name, ext = match.groups()
    new_state = normalize_state(state)

    if new_state:
        return f"{year}, {new_state}, {county.strip()} - {name.strip()}.{ext.strip()}"

    return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Repair 1880 Census filename fixes")
    parser.add_argument("--test", action="store_true", help="Test mode - no changes")
    parser.add_argument("--apply", action="store_true", help="Apply changes")
    parser.add_argument(
        "--media-dir",
        type=Path,
        default=Path.home() / "Genealogy" / "RootsMagic" / "Files" / "Records - Census" / "1880 Federal",
    )
    parser.add_argument("--database", type=Path, default=Path("data/Iiams.rmtree"))

    args = parser.parse_args()

    if not args.test and not args.apply:
        print("ERROR: Must specify --test or --apply")
        sys.exit(1)

    dry_run = args.test

    print("=" * 60)
    print("1880 Census Filename Repair Script")
    print("=" * 60)
    print(f"Mode: {'TEST' if dry_run else 'APPLY'}")
    print(f"Media dir: {args.media_dir}")
    print(f"Database: {args.database}")

    # Step 1: Check files on disk that still need renaming
    print("\n" + "-" * 60)
    print("Step 1: Check files that still need renaming")
    print("-" * 60)

    files_to_rename = []
    if args.media_dir.exists():
        for filepath in sorted(args.media_dir.iterdir()):
            if not filepath.is_file() or not filepath.suffix.lower() in ('.jpg', '.jpeg', '.png', '.tif', '.tiff'):
                continue

            new_name = parse_and_normalize(filepath.name)
            if new_name:
                new_path = filepath.parent / new_name
                files_to_rename.append((filepath, new_path))

    print(f"\nFiles still needing renaming: {len(files_to_rename)}")
    for old_path, new_path in files_to_rename:
        print(f"  {old_path.name}")
        print(f"    -> {new_path.name}")

    # Step 2: Rename remaining files
    if files_to_rename and not dry_run:
        print("\nRenaming files...")
        for old_path, new_path in files_to_rename:
            if new_path.exists():
                print(f"  SKIP: Target exists: {new_path.name}")
                continue
            try:
                old_path.rename(new_path)
                print(f"  OK: {old_path.name}")
            except OSError as e:
                print(f"  ERROR: {old_path.name}: {e}")

    # Step 3: Build mapping of what filenames SHOULD be
    print("\n" + "-" * 60)
    print("Step 2: Build filename mapping for database update")
    print("-" * 60)

    # Get actual files on disk
    actual_files = set()
    if args.media_dir.exists():
        for filepath in args.media_dir.iterdir():
            if filepath.is_file():
                actual_files.add(filepath.name)

    print(f"Files on disk: {len(actual_files)}")

    # Step 4: Update database
    print("\n" + "-" * 60)
    print("Step 3: Update database records")
    print("-" * 60)

    # Connect to database using proper connection with RMNOCASE collation
    icu_path = Path(__file__).parent.parent / "sqlite-extension" / "icu.dylib"
    try:
        conn = connect_rmtree(args.database, icu_path, read_only=False)
        print(f"Connected to database with RMNOCASE collation")
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)

    cur = conn.cursor()

    # Get all 1880 Federal media records
    cur.execute("""
        SELECT MediaID, MediaFile
        FROM MultimediaTable
        WHERE MediaPath LIKE '%1880 Federal%'
    """)

    records = cur.fetchall()
    print(f"Database records for 1880 Federal: {len(records)}")

    # Find records that need updating
    updates = []
    for media_id, db_filename in records:
        # Calculate what the filename should be
        expected_filename = parse_and_normalize(db_filename)

        if expected_filename:
            # Check if the expected file exists on disk
            if expected_filename in actual_files:
                updates.append((media_id, db_filename, expected_filename))
            elif db_filename in actual_files:
                # File wasn't renamed, keep as-is
                pass
            else:
                print(f"  WARNING: Neither old nor new file exists: {db_filename}")

    print(f"\nRecords needing update: {len(updates)}")

    if updates:
        print("\nUpdates to apply:")
        for media_id, old_name, new_name in updates[:10]:
            print(f"  [{media_id}] {old_name}")
            print(f"         -> {new_name}")
        if len(updates) > 10:
            print(f"  ... and {len(updates) - 10} more")

    # Apply updates
    if not dry_run and updates:
        print("\nApplying database updates...")
        success = 0
        errors = 0

        for media_id, old_name, new_name in updates:
            try:
                cur.execute(
                    "UPDATE MultimediaTable SET MediaFile = ? WHERE MediaID = ?",
                    (new_name, media_id)
                )
                success += 1
            except sqlite3.Error as e:
                print(f"  ERROR [{media_id}]: {e}")
                errors += 1

        conn.commit()
        print(f"\n  Success: {success}")
        print(f"  Errors: {errors}")

    conn.close()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if dry_run:
        print(f"  Files that would be renamed: {len(files_to_rename)}")
        print(f"  Database records that would be updated: {len(updates)}")
        print("\n  Run with --apply to make changes.")
    else:
        print("  Changes applied.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
