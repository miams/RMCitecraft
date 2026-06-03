#!/usr/bin/env python3
"""
Fix Sheet Hyphenation for 1900-1940 Census

Updates sheet numbers from "6B" to "6-B" format in:
- Source names
- Footnotes
- Short footnotes

Usage:
    python scripts/fix_sheet_hyphenation.py --dry-run    # Preview changes
    python scripts/fix_sheet_hyphenation.py              # Apply changes
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rmcitecraft.database.connection import connect_rmtree


YEARS = [1900, 1910, 1920, 1930, 1940]


def add_sheet_hyphen(text: str) -> str:
    """Add hyphen to sheet numbers: 6B → 6-B, 12A → 12-A."""
    # Pattern: sheet followed by number and letter (without existing hyphen)
    # sheet 6B → sheet 6-B
    # sheet 12A → sheet 12-A
    return re.sub(r'sheet (\d+)([AB])\b', r'sheet \1-\2', text)


def fix_source_name(name: str) -> str:
    """Fix sheet format in source name."""
    # Pattern in source name: [ED X, sheet 6B, ...] → [ED X, sheet 6-B, ...]
    return re.sub(r'sheet (\d+)([AB])\b', r'sheet \1-\2', name)


def fix_footnote(fields: str) -> str:
    """Fix sheet format in footnote."""
    fn_match = re.search(r'(<Name>Footnote</Name>\s*<Value>)(.*?)(</Value>)', fields, re.DOTALL)
    if not fn_match:
        return fields

    footnote = fn_match.group(2)
    new_footnote = add_sheet_hyphen(footnote)

    if new_footnote != footnote:
        return fields[:fn_match.start(2)] + new_footnote + fields[fn_match.end(2):]

    return fields


def fix_short_footnote(fields: str) -> str:
    """Fix sheet format in short footnote."""
    sfn_match = re.search(r'(<Name>ShortFootnote</Name>\s*<Value>)(.*?)(</Value>)', fields, re.DOTALL)
    if not sfn_match:
        return fields

    short_fn = sfn_match.group(2)
    new_short_fn = add_sheet_hyphen(short_fn)

    if new_short_fn != short_fn:
        return fields[:sfn_match.start(2)] + new_short_fn + fields[sfn_match.end(2):]

    return fields


def main():
    parser = argparse.ArgumentParser(description='Fix sheet hyphenation for 1900-1940 census')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--db', type=Path, default=Path('data/Iiams.rmtree'))
    parser.add_argument('--year', type=int, choices=YEARS, help='Fix specific year only')
    args = parser.parse_args()

    print("=" * 70)
    print("FIX SHEET HYPHENATION: 6B → 6-B")
    print("=" * 70)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY CHANGES'}")
    print(f"Years: {args.year if args.year else YEARS}")
    print()

    conn = connect_rmtree(str(args.db), read_only=args.dry_run)
    cursor = conn.cursor()

    years_to_fix = [args.year] if args.year else YEARS
    total_updates = 0

    for year in years_to_fix:
        cursor.execute('''
            SELECT SourceID, Name, CAST(Fields AS TEXT)
            FROM SourceTable
            WHERE Name LIKE ?
            ORDER BY SourceID
        ''', (f'Fed Census: {year},%',))

        updates = []
        name_fixes = 0
        footnote_fixes = 0
        short_fn_fixes = 0

        for row in cursor.fetchall():
            source_id, name, fields = row
            if not fields:
                continue

            original_name = name
            original_fields = fields

            # Fix source name
            new_name = fix_source_name(name)
            if new_name != original_name:
                name_fixes += 1

            # Fix footnote
            new_fields = fix_footnote(fields)
            if new_fields != fields:
                footnote_fixes += 1

            # Fix short footnote
            fields_after_fn = new_fields
            new_fields = fix_short_footnote(new_fields)
            if new_fields != fields_after_fn:
                short_fn_fixes += 1

            if new_name != original_name or new_fields != original_fields:
                updates.append((source_id, new_name, new_fields))

        print(f"{year} Census:")
        print(f"  Source names to fix: {name_fixes}")
        print(f"  Footnotes to fix: {footnote_fixes}")
        print(f"  Short footnotes to fix: {short_fn_fixes}")
        print(f"  Total sources to update: {len(updates)}")

        if not args.dry_run and updates:
            for source_id, new_name, new_fields in updates:
                cursor.execute(
                    "UPDATE SourceTable SET Name = ?, Fields = ? WHERE SourceID = ?",
                    (new_name, new_fields.encode('utf-8'), source_id)
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
