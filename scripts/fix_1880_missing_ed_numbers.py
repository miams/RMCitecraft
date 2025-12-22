#!/usr/bin/env python3
"""
Fix 1880 Census Missing ED Numbers in Footnotes

Some 1880 census sources have the ED number in the source name but missing
from the footnote and short footnote. This script extracts the ED from the
source name and inserts it into the citation fields.

Usage:
    python scripts/fix_1880_missing_ed_numbers.py --dry-run    # Preview changes
    python scripts/fix_1880_missing_ed_numbers.py              # Apply changes
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rmcitecraft.database.connection import connect_rmtree


def extract_ed_from_name(name: str) -> str | None:
    """Extract ED number from source name like '[ED 4, page 81, line 57]'."""
    match = re.search(r'\[ED\s+(\d+)', name)
    return match.group(1) if match else None


def fix_footnote(fields: str, ed_number: str) -> str:
    """Fix footnote to include ED number."""
    # Pattern: enumeration district (ED) , -> enumeration district (ED) 123,
    pattern = r'enumeration district \(ED\)\s*,'
    replacement = f'enumeration district (ED) {ed_number},'
    return re.sub(pattern, replacement, fields)


def fix_short_footnote(fields: str, ed_number: str) -> str:
    """Fix short footnote to include ED number."""
    # Pattern: E.D. , -> E.D. 123,
    pattern = r'E\.D\.\s*,'
    replacement = f'E.D. {ed_number},'
    return re.sub(pattern, replacement, fields)


def main():
    parser = argparse.ArgumentParser(description='Fix 1880 census missing ED numbers')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--db', type=Path, default=Path('data/Iiams.rmtree'))
    args = parser.parse_args()

    print("=" * 70)
    print("FIX 1880 CENSUS MISSING ED NUMBERS")
    print("=" * 70)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY CHANGES'}")
    print()

    conn = connect_rmtree(str(args.db), read_only=args.dry_run)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT SourceID, Name, CAST(Fields AS TEXT)
        FROM SourceTable
        WHERE Name LIKE '%1880%' AND Name LIKE '%Census%'
        ORDER BY SourceID
    ''')

    updates = []

    for row in cursor.fetchall():
        source_id, name, fields = row
        if not fields:
            continue

        # Check if footnote is missing ED number
        has_missing_ed = bool(re.search(r'enumeration district \(ED\)\s*,', fields))

        if has_missing_ed:
            ed_number = extract_ed_from_name(name)
            if ed_number:
                new_fields = fix_footnote(fields, ed_number)
                new_fields = fix_short_footnote(new_fields, ed_number)

                if new_fields != fields:
                    updates.append((source_id, name, new_fields, ed_number))

    print(f"Sources to fix: {len(updates)}")
    print()

    if args.dry_run:
        print("Sources to update:")
        for source_id, name, new_fields, ed_number in updates:
            print(f"\n  Source {source_id} (ED {ed_number}):")
            print(f"    {name[:70]}...")

            # Show fixed footnote snippet
            fn_match = re.search(r'enumeration district \(ED\) \d+,', new_fields)
            if fn_match:
                print(f"    Footnote: ...{fn_match.group(0)}...")

            # Show fixed short footnote snippet
            sfn_match = re.search(r'E\.D\. \d+,', new_fields)
            if sfn_match:
                print(f"    Short fn: ...{sfn_match.group(0)}...")

        print("\nDRY RUN - No changes made")
    else:
        print("Applying changes...")
        for source_id, name, new_fields, ed_number in updates:
            cursor.execute(
                "UPDATE SourceTable SET Fields = ? WHERE SourceID = ?",
                (new_fields.encode('utf-8'), source_id)
            )
        conn.commit()
        print(f"Updated {len(updates)} sources")

    conn.close()


if __name__ == '__main__':
    main()
