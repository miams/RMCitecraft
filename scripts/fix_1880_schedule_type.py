#!/usr/bin/env python3
"""
Fix 1880 Census Schedule Type

Adds "population schedule" to footnotes and "pop. sch." to short footnotes
where missing.

Usage:
    python scripts/fix_1880_schedule_type.py --dry-run    # Preview changes
    python scripts/fix_1880_schedule_type.py              # Apply changes
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rmcitecraft.database.connection import connect_rmtree


def main():
    parser = argparse.ArgumentParser(description='Fix 1880 census schedule type')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes')
    parser.add_argument('--db', type=Path, default=Path('data/Iiams.rmtree'))
    args = parser.parse_args()

    print("=" * 70)
    print("FIX 1880 CENSUS SCHEDULE TYPE")
    print("=" * 70)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY CHANGES'}")
    print()

    conn = connect_rmtree(str(args.db), read_only=args.dry_run)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT SourceID, Name, CAST(Fields AS TEXT)
        FROM SourceTable
        WHERE Name LIKE 'Fed Census: 1880%'
    ''')

    updates = []
    fn_fixed = 0
    sfn_fixed = 0

    for source_id, name, fields in cursor.fetchall():
        new_fields = fields
        changed = False

        # Fix footnote - add "population schedule" if missing
        fn_match = re.search(r'<Name>Footnote</Name>\s*<Value>(.*?)</Value>', new_fields, re.DOTALL)
        if fn_match:
            footnote = fn_match.group(1)
            if 'population schedule' not in footnote.lower():
                # Insert after "State," before locality or ED
                new_footnote = re.sub(
                    r'(County,\s*[A-Za-z\s]+,\s*)(enumeration district|[A-Z][a-z]+)',
                    r'\1population schedule, \2',
                    footnote,
                    count=1
                )
                if new_footnote != footnote:
                    new_fields = re.sub(
                        r'(<Name>Footnote</Name>\s*<Value>)(.*?)(</Value>)',
                        lambda m: m.group(1) + new_footnote + m.group(3),
                        new_fields,
                        flags=re.DOTALL
                    )
                    changed = True
                    fn_fixed += 1

        # Fix short footnote - add "pop. sch." if missing
        sfn_match = re.search(r'<Name>ShortFootnote</Name>\s*<Value>(.*?)</Value>', new_fields, re.DOTALL)
        if sfn_match:
            short_fn = sfn_match.group(1)
            if 'pop. sch.' not in short_fn.lower():
                # Insert after state abbreviation, before locality or E.D.
                new_short = re.sub(
                    r'(Co\.,\s*[A-Za-z\.]+,\s*)(E\.D\.|[A-Z][a-z]+)',
                    r'\1pop. sch., \2',
                    short_fn,
                    count=1
                )
                if new_short != short_fn:
                    new_fields = re.sub(
                        r'(<Name>ShortFootnote</Name>\s*<Value>)(.*?)(</Value>)',
                        lambda m: m.group(1) + new_short + m.group(3),
                        new_fields,
                        flags=re.DOTALL
                    )
                    changed = True
                    sfn_fixed += 1

        if changed:
            updates.append((source_id, name, new_fields))

    print(f"Footnotes to fix: {fn_fixed}")
    print(f"Short footnotes to fix: {sfn_fixed}")
    print(f"Total sources to update: {len(updates)}")
    print()

    if updates and not args.dry_run:
        print("Applying changes...")
        for source_id, name, new_fields in updates:
            cursor.execute(
                "UPDATE SourceTable SET Fields = ? WHERE SourceID = ?",
                (new_fields.encode('utf-8'), source_id)
            )
        conn.commit()
        print(f"Updated {len(updates)} sources")
    elif args.dry_run:
        print("DRY RUN - No changes made")
        if updates:
            print("\nSample (first 3):")
            for source_id, name, _ in updates[:3]:
                print(f"  Source {source_id}: {name[:60]}...")

    conn.close()


if __name__ == '__main__':
    main()
