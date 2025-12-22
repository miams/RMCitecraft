#!/usr/bin/env python3
"""
Fix 1880 Census Sheet to Page Notation

The 1880 census uses stamped page numbers, not sheet numbers with letter suffixes.
This script converts:
  - Source name: [ED X, sheet 92A, line N] → [ED X, page 92, line N]
  - Footnote: sheet 92A → page 92 (stamped)
  - Short footnote: sheet 92A → p. 92 (stamped)

Usage:
    python scripts/fix_1880_sheet_to_page.py --dry-run    # Preview changes
    python scripts/fix_1880_sheet_to_page.py              # Apply changes
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rmcitecraft.database.connection import connect_rmtree


def fix_source_name(name: str) -> str:
    """
    Convert source name from sheet notation to page notation.

    [ED 146, sheet 92A, line 9] → [ED 146, page 92, line 9]
    """
    # Pattern: sheet followed by number and optional letter (A/B/C/D)
    pattern = r'\[ED (\d+), sheet (\d+)[A-Da-d], line (\d+)\]'
    match = re.search(pattern, name)
    if match:
        ed = match.group(1)
        page_num = match.group(2)
        line_num = match.group(3)
        return re.sub(pattern, f'[ED {ed}, page {page_num}, line {line_num}]', name)
    return name


def fix_footnote(fields: str) -> str:
    """
    Convert footnote from sheet notation to page (stamped) notation.

    sheet 92A, line → page 92 (stamped), line
    """
    fn_match = re.search(r'(<Name>Footnote</Name>\s*<Value>)(.*?)(</Value>)', fields, re.DOTALL)
    if not fn_match:
        return fields

    footnote = fn_match.group(2)

    # Pattern: sheet followed by number and letter, then comma
    # sheet 92A, line → page 92 (stamped), line
    pattern = r'sheet (\d+)[A-Da-d],\s*line'
    new_footnote = re.sub(pattern, r'page \1 (stamped), line', footnote)

    if new_footnote != footnote:
        # Replace in full fields string, preserving everything before and after
        return fields[:fn_match.start(2)] + new_footnote + fields[fn_match.end(2):]

    return fields


def fix_short_footnote(fields: str) -> str:
    """
    Convert short footnote from sheet notation to p. (stamped) notation.

    sheet 92A, line → p. 92 (stamped), line
    """
    # Pattern: sheet followed by number and letter, then comma and line
    # sheet 92A, line → p. 92 (stamped), line
    pattern = r'(<Name>ShortFootnote</Name>\s*<Value>)(.*?)(</Value>)'
    sfn_match = re.search(pattern, fields, re.DOTALL)
    if not sfn_match:
        return fields

    short_fn = sfn_match.group(2)

    # Replace sheet XA, line with p. X (stamped), line
    sheet_pattern = r'sheet (\d+)[A-Da-d],\s*line'
    new_short_fn = re.sub(sheet_pattern, r'p. \1 (stamped), line', short_fn)

    if new_short_fn != short_fn:
        return fields[:sfn_match.start(2)] + new_short_fn + fields[sfn_match.end(2):]

    return fields


def main():
    parser = argparse.ArgumentParser(description='Fix 1880 census sheet to page notation')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--db', type=Path, default=Path('data/Iiams.rmtree'))
    args = parser.parse_args()

    print("=" * 70)
    print("FIX 1880 CENSUS: SHEET → PAGE (STAMPED) NOTATION")
    print("=" * 70)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY CHANGES'}")
    print()
    print("Changes to be made:")
    print("  Source name: [ED X, sheet 92A, line N] → [ED X, page 92, line N]")
    print("  Footnote:    sheet 92A, line → page 92 (stamped), line")
    print("  Short fn:    sheet 92A, line → p. 92 (stamped), line")
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
    name_fixes = 0
    footnote_fixes = 0
    short_fn_fixes = 0

    for row in cursor.fetchall():
        source_id, name, fields = row
        if not fields:
            continue

        original_name = name
        original_fields = fields

        # Apply fixes
        new_name = fix_source_name(name)

        # Apply footnote fix first
        fields_after_fn = fix_footnote(fields)

        # Apply short footnote fix
        new_fields = fix_short_footnote(fields_after_fn)

        # Count changes
        if new_name != original_name:
            name_fixes += 1

        # Check footnote change by comparing before/after fix_footnote
        fn_orig = re.search(r'<Name>Footnote</Name>\s*<Value>(.*?)</Value>', original_fields, re.DOTALL)
        fn_after = re.search(r'<Name>Footnote</Name>\s*<Value>(.*?)</Value>', fields_after_fn, re.DOTALL)
        if fn_orig and fn_after and fn_orig.group(1) != fn_after.group(1):
            footnote_fixes += 1

        # Check short footnote change by comparing before/after fix_short_footnote
        sfn_before = re.search(r'<Name>ShortFootnote</Name>\s*<Value>(.*?)</Value>', fields_after_fn, re.DOTALL)
        sfn_after = re.search(r'<Name>ShortFootnote</Name>\s*<Value>(.*?)</Value>', new_fields, re.DOTALL)
        if sfn_before and sfn_after and sfn_before.group(1) != sfn_after.group(1):
            short_fn_fixes += 1

        if new_name != original_name or new_fields != original_fields:
            updates.append((source_id, new_name, new_fields, original_name, new_name != original_name))

    print(f"Source names to fix: {name_fixes}")
    print(f"Footnotes to fix: {footnote_fixes}")
    print(f"Short footnotes to fix: {short_fn_fixes}")
    print(f"Total sources to update: {len(updates)}")
    print()

    if args.dry_run:
        print("Sample updates (first 5):")
        for source_id, new_name, new_fields, old_name, name_changed in updates[:5]:
            print(f"\n  Source {source_id}:")
            if name_changed:
                print(f"    Name before: {old_name}")
                print(f"    Name after:  {new_name}")

            # Show footnote snippet
            fn_match = re.search(r'<Name>Footnote</Name>\s*<Value>(.*?)</Value>', new_fields, re.DOTALL)
            if fn_match:
                fn = fn_match.group(1)
                # Find the page reference
                page_match = re.search(r'page \d+ \(stamped\), line \d+', fn)
                if page_match:
                    print(f"    Footnote ref: ...{page_match.group(0)}...")

            # Show short footnote snippet
            sfn_match = re.search(r'<Name>ShortFootnote</Name>\s*<Value>(.*?)</Value>', new_fields, re.DOTALL)
            if sfn_match:
                sfn = sfn_match.group(1)
                page_match = re.search(r'p\. \d+ \(stamped\), line \d+', sfn)
                if page_match:
                    print(f"    Short fn ref: ...{page_match.group(0)}...")

        print("\nDRY RUN - No changes made")
    else:
        print("Applying changes...")
        for source_id, new_name, new_fields, _, _ in updates:
            cursor.execute(
                "UPDATE SourceTable SET Name = ?, Fields = ? WHERE SourceID = ?",
                (new_name, new_fields.encode('utf-8'), source_id)
            )
        conn.commit()
        print(f"Updated {len(updates)} sources")
        print(f"  - {name_fixes} source names fixed")
        print(f"  - {footnote_fixes} footnotes fixed")
        print(f"  - {short_fn_fixes} short footnotes fixed")

    conn.close()


if __name__ == '__main__':
    main()
