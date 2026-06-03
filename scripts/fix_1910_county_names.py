#!/usr/bin/env python3
"""
Fix 1910 Census County Name Errors

Fixes typos and incorrect county names in 1910 census source names.

Corrections:
- Source 631, 632: Greene → Washington (wrong county, footnote is correct)
- Source 758: Benton → Marion (wrong county, footnote is correct)
- Source 866: Findlay → Hancock (city used instead of county)
- Source 901: Miultnomah → Multnomah (typo)
- Source 1326: McLean is correct, fix footnote Mc Lean → McLean
- Source 1331: Cuyahoa → Cuyahoga (typo)
- Source 2105: Aurora → Cloud (city used instead of county)
- Source 3020, 4110: San Bernadino → San Bernardino (typo)
- Source 3083: Vaca → Baca (typo)
- Source 3386: St. Charles is correct, fix footnote St Charles → St. Charles
- Source 3584: Pulask → Pulaski (typo)

Usage:
    python scripts/fix_1910_county_names.py --dry-run    # Preview changes
    python scripts/fix_1910_county_names.py              # Apply changes
"""

import argparse
import re
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rmcitecraft.database.connection import connect_rmtree

# Source name corrections: {source_id: (old_pattern, new_pattern)}
SOURCE_NAME_FIXES = {
    631: ("Pennsylvania, Greene", "Pennsylvania, Washington"),
    632: ("Pennsylvania, Greene", "Pennsylvania, Washington"),
    758: ("Oregon, Benton", "Oregon, Marion"),
    866: ("Ohio, Findlay", "Ohio, Hancock"),
    901: ("Oregon, Miultnomah", "Oregon, Multnomah"),
    1331: ("Ohio, Cuyahoa", "Ohio, Cuyahoga"),
    2105: ("Kansas, Aurora", "Kansas, Cloud"),
    3020: ("California, San Bernadino", "California, San Bernardino"),
    3083: ("Colorado, Vaca", "Colorado, Baca"),
    3584: ("Indiana, Pulask", "Indiana, Pulaski"),
    4110: ("California, San Bernadino", "California, San Bernardino"),
}

# Footnote corrections: {source_id: [(old_pattern, new_pattern, field_names), ...]}
FOOTNOTE_FIXES = {
    1326: [
        ("Mc Lean County", "McLean County", ["Footnote", "Bibliography"]),
        ("Mc Lean Co.", "McLean Co.", ["ShortFootnote"]),
    ],
    3386: [
        ("St Charles County", "St. Charles County", ["Footnote", "Bibliography"]),
        ("St Charles Co.", "St. Charles Co.", ["ShortFootnote"]),
    ],
}


def update_field(fields_text: str, field_name: str, new_value: str) -> str:
    """Update a field value in Fields XML using safe replacement."""
    pattern = rf'(<Name>{re.escape(field_name)}</Name>\s*<Value>)(.*?)(</Value>)'

    def replacer(m):
        return m.group(1) + new_value + m.group(3)

    return re.sub(pattern, replacer, fields_text, flags=re.DOTALL)


def extract_field(fields_text: str, field_name: str) -> str:
    """Extract a field value from Fields XML."""
    pattern = rf'<Name>{field_name}</Name>\s*<Value>(.*?)</Value>'
    match = re.search(pattern, fields_text, re.DOTALL)
    return match.group(1) if match else ""


def main():
    parser = argparse.ArgumentParser(
        description="Fix 1910 census county name errors",
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

    print(f"Database: {args.db}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY CHANGES'}")
    print()

    conn = connect_rmtree(str(args.db), read_only=args.dry_run)
    cursor = conn.cursor()

    # Process source name fixes
    print("=" * 70)
    print("SOURCE NAME FIXES")
    print("=" * 70)

    source_updates = []
    for source_id, (old_pattern, new_pattern) in SOURCE_NAME_FIXES.items():
        cursor.execute("SELECT Name FROM SourceTable WHERE SourceID = ?", (source_id,))
        row = cursor.fetchone()
        if row:
            old_name = row[0]
            new_name = old_name.replace(old_pattern, new_pattern)
            if old_name != new_name:
                print(f"\nSource {source_id}:")
                print(f"  Old: {old_name}")
                print(f"  New: {new_name}")
                source_updates.append((source_id, new_name))
            else:
                print(f"\nSource {source_id}: Pattern not found (already fixed?)")

    # Process footnote fixes
    print()
    print("=" * 70)
    print("FOOTNOTE FIXES")
    print("=" * 70)

    footnote_updates = []
    for source_id, fixes in FOOTNOTE_FIXES.items():
        cursor.execute(
            "SELECT Name, CAST(Fields AS TEXT) FROM SourceTable WHERE SourceID = ?",
            (source_id,)
        )
        row = cursor.fetchone()
        if row:
            name, fields_text = row
            new_fields = fields_text
            changed = False

            print(f"\nSource {source_id}: {name[:60]}...")

            for old_pattern, new_pattern, field_names in fixes:
                for field_name in field_names:
                    field_value = extract_field(new_fields, field_name)
                    if old_pattern in field_value:
                        new_value = field_value.replace(old_pattern, new_pattern)
                        new_fields = update_field(new_fields, field_name, new_value)
                        changed = True
                        print(f"  {field_name}: '{old_pattern}' → '{new_pattern}'")

            if changed:
                footnote_updates.append((source_id, new_fields))

    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Source names to update: {len(source_updates)}")
    print(f"Footnotes to update: {len(footnote_updates)}")

    # Apply changes
    if not args.dry_run:
        print()
        print("=" * 70)
        print("APPLYING CHANGES")
        print("=" * 70)

        # Update source names
        for source_id, new_name in source_updates:
            cursor.execute(
                "UPDATE SourceTable SET Name = ? WHERE SourceID = ?",
                (new_name, source_id)
            )
        print(f"Updated {len(source_updates)} source names")

        # Update footnotes
        for source_id, new_fields in footnote_updates:
            cursor.execute(
                "UPDATE SourceTable SET Fields = ? WHERE SourceID = ?",
                (new_fields.encode('utf-8'), source_id)
            )
        print(f"Updated {len(footnote_updates)} footnote fields")

        conn.commit()
        print("\nChanges committed successfully")
    else:
        print()
        print("DRY RUN COMPLETE - No changes made")
        print("Run without --dry-run to apply changes")

    conn.close()


if __name__ == "__main__":
    main()
