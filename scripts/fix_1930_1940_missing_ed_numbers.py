#!/usr/bin/env python3
"""
Fix 1930/1940 Census Missing ED Numbers in Footnotes

Some 1930/1940 census sources have the ED number in the source name but missing
from the footnote and short footnote. This script extracts the ED from the
source name and inserts it into the citation fields.

Usage:
    python scripts/fix_1930_1940_missing_ed_numbers.py --dry-run    # Preview changes
    python scripts/fix_1930_1940_missing_ed_numbers.py              # Apply changes
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rmcitecraft.database.connection import connect_rmtree


def extract_ed_from_name(name: str) -> str | None:
    """Extract ED number from source name like '[ED 16-232, sheet 10-B, line 67]'."""
    # 1930/1940 use hyphenated ED format: ED 16-232, ED 84-19
    match = re.search(r'\[ED\s+(\d+-\d+)', name)
    return match.group(1) if match else None


def fix_footnote(fields: str, ed_number: str) -> str:
    """Fix footnote to include ED number."""
    # Pattern 1: enumeration district (ED) , -> enumeration district (ED) 16-232,
    # Pattern 2: enumeration district (ED) ED X, -> enumeration district (ED) 16-232,
    #            (handles redundant "ED" prefix and wrong/partial ED numbers)

    # First try to fix "enumeration district (ED) ED X," pattern
    pattern_with_ed = r'enumeration district \(ED\) ED\s*[\d-]*,'
    if re.search(pattern_with_ed, fields):
        return re.sub(pattern_with_ed, f'enumeration district (ED) {ed_number},', fields)

    # Then try to fix "enumeration district (ED) ," pattern (missing ED)
    pattern_missing = r'enumeration district \(ED\)\s*,'
    replacement = f'enumeration district (ED) {ed_number},'
    return re.sub(pattern_missing, replacement, fields)


def fix_short_footnote(fields: str, ed_number: str) -> str:
    """Fix short footnote to include ED number."""
    # Pattern: E.D. , -> E.D. 16-232,
    pattern = r'E\.D\.\s*,'
    replacement = f'E.D. {ed_number},'
    return re.sub(pattern, replacement, fields)


def main():
    parser = argparse.ArgumentParser(description='Fix 1930/1940 census missing ED numbers')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--db', type=Path, default=Path('data/Iiams.rmtree'))
    parser.add_argument('--year', type=int, choices=[1930, 1940], help='Fix specific year only')
    args = parser.parse_args()

    print("=" * 70)
    print("FIX 1930/1940 CENSUS MISSING ED NUMBERS")
    print("=" * 70)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY CHANGES'}")
    print()

    conn = connect_rmtree(str(args.db), read_only=args.dry_run)
    cursor = conn.cursor()

    years = [args.year] if args.year else [1930, 1940]
    total_updates = 0

    for year in years:
        cursor.execute('''
            SELECT SourceID, Name, CAST(Fields AS TEXT)
            FROM SourceTable
            WHERE Name LIKE ?
            ORDER BY SourceID
        ''', (f'Fed Census: {year},%',))

        updates = []

        for row in cursor.fetchall():
            source_id, name, fields = row
            if not fields:
                continue

            # Check if footnote is missing ED number or has wrong ED format
            # Pattern 1: "enumeration district (ED) ," - completely missing
            # Pattern 2: "enumeration district (ED) ED X," - redundant ED prefix or wrong number
            has_missing_ed = bool(re.search(r'enumeration district \(ED\)\s*,', fields))
            has_wrong_ed = bool(re.search(r'enumeration district \(ED\) ED\s*[\d-]*,', fields))

            if has_missing_ed or has_wrong_ed:
                ed_number = extract_ed_from_name(name)
                if ed_number:
                    new_fields = fix_footnote(fields, ed_number)
                    new_fields = fix_short_footnote(new_fields, ed_number)

                    if new_fields != fields:
                        updates.append((source_id, name, new_fields, ed_number))

        print(f"{year} Census - Sources to fix: {len(updates)}")

        if args.dry_run and updates:
            for source_id, name, new_fields, ed_number in updates:
                print(f"\n  Source {source_id} (ED {ed_number}):")
                print(f"    {name}")

                # Show fixed footnote snippet
                fn_match = re.search(r'enumeration district \(ED\) [\d-]+,', new_fields)
                if fn_match:
                    print(f"    Footnote: ...{fn_match.group(0)}...")

                # Show fixed short footnote snippet
                sfn_match = re.search(r'E\.D\. [\d-]+,', new_fields)
                if sfn_match:
                    print(f"    Short fn: ...{sfn_match.group(0)}...")
        elif updates:
            for source_id, name, new_fields, ed_number in updates:
                cursor.execute(
                    "UPDATE SourceTable SET Fields = ? WHERE SourceID = ?",
                    (new_fields.encode('utf-8'), source_id)
                )
            print(f"  → Updated {len(updates)} sources")

        total_updates += len(updates)
        print()

    if not args.dry_run:
        conn.commit()

    print("=" * 70)
    print(f"Total: {total_updates} sources {'would be' if args.dry_run else ''} updated")
    if args.dry_run:
        print("DRY RUN - No changes made")

    conn.close()


if __name__ == '__main__':
    main()
