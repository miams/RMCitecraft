#!/usr/bin/env python3
"""
Fix 1880 Census State Abbreviations

Fixes incorrect state abbreviations in short footnotes for 1880 census sources.

Corrections:
- Source 856: Oh. -> Ohio
- Source 1499: KA -> Kans.
- Source 2202: PE -> Pa.
- Source 3163: Mich. -> Mo.
- Source 3265: KE -> Ky.
- Source 4557: PE -> Pa.
- Source 7434: Nebr. -> N.Y.

Usage:
    python scripts/fix_1880_state_abbreviations.py --dry-run    # Preview changes
    python scripts/fix_1880_state_abbreviations.py              # Apply changes
"""

import argparse
import re
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rmcitecraft.database.connection import connect_rmtree

# State abbreviation fixes: {source_id: (wrong_abbrev, correct_abbrev)}
STATE_FIXES = {
    856: ("Oh.", "Ohio"),
    1499: ("KA", "Kans."),
    2202: ("PE", "Pa."),
    3163: ("Mich.", "Mo."),
    3265: ("KE", "Ky."),
    4557: ("PE", "Pa."),
    7434: ("Nebr.", "N.Y."),
}


def extract_field(fields_text: str, field_name: str) -> str:
    """Extract a field value from Fields XML."""
    pattern = rf'<Name>{field_name}</Name>\s*<Value>(.*?)</Value>'
    match = re.search(pattern, fields_text, re.DOTALL)
    return match.group(1) if match else ""


def update_field(fields_text: str, field_name: str, new_value: str) -> str:
    """Update a field value in Fields XML using safe replacement."""
    pattern = rf'(<Name>{re.escape(field_name)}</Name>\s*<Value>)(.*?)(</Value>)'

    def replacer(m):
        return m.group(1) + new_value + m.group(3)

    return re.sub(pattern, replacer, fields_text, flags=re.DOTALL)


def main():
    parser = argparse.ArgumentParser(
        description="Fix 1880 census state abbreviations in short footnotes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying database"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/Iiams.rmtree"),
        help="Path to RootsMagic database"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("FIX 1880 CENSUS STATE ABBREVIATIONS")
    print("=" * 70)
    print()
    print(f"Database: {args.db}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY CHANGES'}")
    print()

    conn = connect_rmtree(str(args.db), read_only=args.dry_run)
    cursor = conn.cursor()

    updates = []

    for source_id, (wrong_abbrev, correct_abbrev) in STATE_FIXES.items():
        cursor.execute(
            "SELECT Name, CAST(Fields AS TEXT) FROM SourceTable WHERE SourceID = ?",
            (source_id,)
        )
        row = cursor.fetchone()
        if not row:
            print(f"Source {source_id}: NOT FOUND")
            continue

        name, fields_text = row
        short_fn = extract_field(fields_text, "ShortFootnote")

        if not short_fn:
            print(f"Source {source_id}: No ShortFootnote field")
            continue

        # Check if the wrong abbreviation is present
        # Match pattern like "County Co., XX" or "County Co., XX.,"
        pattern = rf'(\b[\w\s]+\s+Co\.,\s*){re.escape(wrong_abbrev)}(\s*,|\s*\.|\s+)'

        if not re.search(pattern, short_fn):
            # Try simpler pattern
            if wrong_abbrev not in short_fn:
                print(f"Source {source_id}: '{wrong_abbrev}' not found in short footnote")
                continue

        # Replace the abbreviation
        new_short_fn = short_fn.replace(wrong_abbrev, correct_abbrev, 1)

        if new_short_fn == short_fn:
            print(f"Source {source_id}: No change needed")
            continue

        new_fields = update_field(fields_text, "ShortFootnote", new_short_fn)

        print(f"\nSource {source_id}: {name[:60]}...")
        print(f"  Old: ...{wrong_abbrev}...")
        print(f"  New: ...{correct_abbrev}...")

        updates.append((source_id, new_fields))

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Sources to update: {len(updates)}")

    if updates and not args.dry_run:
        print()
        print("=" * 70)
        print("APPLYING CHANGES")
        print("=" * 70)

        for source_id, new_fields in updates:
            cursor.execute(
                "UPDATE SourceTable SET Fields = ? WHERE SourceID = ?",
                (new_fields.encode('utf-8'), source_id)
            )

        conn.commit()
        print(f"Updated {len(updates)} sources")

        # Verify
        print()
        print("Verification:")
        for source_id, _ in updates[:3]:
            cursor.execute(
                "SELECT CAST(Fields AS TEXT) FROM SourceTable WHERE SourceID = ?",
                (source_id,)
            )
            row = cursor.fetchone()
            if row:
                short_fn = extract_field(row[0], "ShortFootnote")
                print(f"  Source {source_id}: {short_fn[:80]}...")
    elif args.dry_run:
        print()
        print("DRY RUN COMPLETE - No changes made")
        print("Run without --dry-run to apply changes")

    conn.close()


if __name__ == "__main__":
    main()
