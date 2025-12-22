#!/usr/bin/env python3
"""
Fix 1880 Census Short Footnotes and Bibliographies

1. Change "ln." to "line" in short footnotes
2. Change ": 16 D." to ": 2025." in bibliographies

Usage:
    python scripts/fix_1880_shortfn_and_bib.py --dry-run    # Preview changes
    python scripts/fix_1880_shortfn_and_bib.py              # Apply changes
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rmcitecraft.database.connection import connect_rmtree


def main():
    parser = argparse.ArgumentParser(description='Fix 1880 census short footnotes and bibliographies')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--db', type=Path, default=Path('data/Iiams.rmtree'))
    args = parser.parse_args()

    print("=" * 70)
    print("FIX 1880 CENSUS SHORT FOOTNOTES AND BIBLIOGRAPHIES")
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
    ln_fixes = 0
    bib_fixes = 0

    for row in cursor.fetchall():
        source_id, name, fields = row
        if not fields:
            continue

        new_fields = fields
        fixed_ln = False
        fixed_bib = False

        # Fix 1: Change "ln." to "line" in short footnote
        sfn_match = re.search(r'(<Name>ShortFootnote</Name>\s*<Value>)(.*?)(</Value>)', new_fields, re.DOTALL)
        if sfn_match:
            short_fn = sfn_match.group(2)
            if 'ln.' in short_fn:
                # Replace "ln." with "line" (preserve the number after it)
                new_short_fn = re.sub(r'\bln\.\s*', 'line ', short_fn)
                new_fields = new_fields[:sfn_match.start(2)] + new_short_fn + new_fields[sfn_match.end(2):]
                fixed_ln = True
                ln_fixes += 1

        # Fix 2: Change ": 16 D." to ": 2025." in bibliography
        bib_match = re.search(r'(<Name>Bibliography</Name>\s*<Value>)(.*?)(</Value>)', new_fields, re.DOTALL)
        if bib_match:
            bib = bib_match.group(2)
            if ': 16 D.' in bib:
                new_bib = bib.replace(': 16 D.', ': 2025.')
                # Need to recalculate positions since we may have modified fields above
                new_fields = re.sub(
                    r'(<Name>Bibliography</Name>\s*<Value>)(.*?)(</Value>)',
                    lambda m: m.group(1) + m.group(2).replace(': 16 D.', ': 2025.') + m.group(3),
                    new_fields,
                    flags=re.DOTALL
                )
                fixed_bib = True
                bib_fixes += 1

        if new_fields != fields:
            updates.append((source_id, name, new_fields, fixed_ln, fixed_bib))

    print(f"Short footnotes to fix (ln. -> line): {ln_fixes}")
    print(f"Bibliographies to fix (: 16 D. -> : 2025.): {bib_fixes}")
    print(f"Total sources to update: {len(updates)}")
    print()

    if args.dry_run:
        print("Sample updates (first 5):")
        for source_id, name, new_fields, fixed_ln, fixed_bib in updates[:5]:
            fixes = []
            if fixed_ln:
                fixes.append("ln.->line")
            if fixed_bib:
                fixes.append("16 D.->2025.")
            print(f"\n  Source {source_id}: {name[:60]}...")
            print(f"    Fixes: {', '.join(fixes)}")
        print("\nDRY RUN - No changes made")
    else:
        print("Applying changes...")
        for source_id, name, new_fields, _, _ in updates:
            cursor.execute(
                "UPDATE SourceTable SET Fields = ? WHERE SourceID = ?",
                (new_fields.encode('utf-8'), source_id)
            )
        conn.commit()
        print(f"Updated {len(updates)} sources")
        print(f"  - {ln_fixes} short footnotes fixed (ln. -> line)")
        print(f"  - {bib_fixes} bibliographies fixed (: 16 D. -> : 2025.)")

    conn.close()


if __name__ == '__main__':
    main()
