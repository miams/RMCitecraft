#!/usr/bin/env python3
"""
Apply 1880 Census Line Numbers

Updates source names, footnotes, short footnotes, and bibliographies with
line numbers fetched from FamilySearch.

Usage:
    python scripts/apply_1880_line_numbers.py --dry-run    # Preview changes
    python scripts/apply_1880_line_numbers.py              # Apply changes
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rmcitecraft.database.connection import connect_rmtree


# Line numbers from FamilySearch (extracted via Playwright automation)
# Round 2: Additional 76 sources
LINE_NUMBERS = {
    1321: 32, 1382: 5, 1430: 33, 1449: 25, 1457: 39, 1460: 34, 1503: 90,
    1535: 1, 1578: 29, 1604: 37, 1651: 1, 1654: 26, 1672: 5, 1685: 4,
    1687: 83, 1693: 20, 1713: 17, 1720: 66, 1727: 55, 1733: 87, 1753: 71,
    1759: 81, 1780: 4, 1781: 74, 1817: 100, 1822: 33, 1869: 55, 1879: 75,
    1891: 26, 1904: 61, 1913: 20, 1930: 1, 1976: 8, 1982: 100, 2020: 78,
    2037: 80, 2043: 72, 2055: 84, 2079: 53, 2093: 5, 2117: 95, 2120: 15,
    2248: 42, 2251: 64, 2256: 40, 2266: 24, 2279: 7, 2332: 46, 2731: 62,
    2940: 9, 2976: 86, 3000: 5, 3015: 31, 3018: 52, 3032: 21, 3033: 49,
    3034: 38, 3042: 4, 3047: 48, 3135: 20, 3154: 14, 3202: 13, 3218: 75,
    3220: 44, 3221: 39, 3232: 7, 3263: 58, 3265: 48, 3284: 55, 3287: 35,
    3339: 73, 3410: 98, 3411: 87, 3419: 87, 3439: 63, 3538: 12,
}


def update_source_name(name: str, line_number: int) -> str:
    """Update source name to include line number."""
    # Pattern: [ED X, sheet YZ] -> [ED X, sheet YZ, line N]
    if ', line ' in name:
        return name  # Already has line number

    # Match [ED X, sheet YZ] and add line number
    pattern = r'\[ED (\d+), sheet (\d+[A-D])\]'
    match = re.search(pattern, name)
    if match:
        ed = match.group(1)
        sheet = match.group(2)
        return re.sub(pattern, f'[ED {ed}, sheet {sheet}, line {line_number}]', name)

    return name


def update_footnote(fields: str, line_number: int) -> str:
    """Update footnote to include line number."""
    fn_match = re.search(r'<Name>Footnote</Name>\s*<Value>(.*?)</Value>', fields, re.DOTALL)
    if not fn_match:
        return fields

    footnote = fn_match.group(1)

    # Check if already has line number
    if 'line ' in footnote.lower():
        return fields

    # Pattern: sheet XY, family Z -> sheet XY, line N, family Z
    # Or: sheet XY, dwelling Z -> sheet XY, line N, dwelling Z
    new_footnote = re.sub(
        r'(sheet \d+[A-D]),\s*(dwelling|family)',
        rf'\1, line {line_number}, \2',
        footnote
    )

    if new_footnote == footnote:
        # Alternative: sheet XY, Person Name -> sheet XY, line N, Person Name
        new_footnote = re.sub(
            r'(sheet \d+[A-D]),\s*([A-Z][a-z]+)',
            rf'\1, line {line_number}, \2',
            footnote
        )

    if new_footnote != footnote:
        fields = re.sub(
            r'(<Name>Footnote</Name>\s*<Value>)(.*?)(</Value>)',
            lambda m: m.group(1) + new_footnote + m.group(3),
            fields,
            flags=re.DOTALL
        )

    return fields


def update_short_footnote(fields: str, line_number: int) -> str:
    """Update short footnote to include line number."""
    sfn_match = re.search(r'<Name>ShortFootnote</Name>\s*<Value>(.*?)</Value>', fields, re.DOTALL)
    if not sfn_match:
        return fields

    short_fn = sfn_match.group(1)

    # Check if already has line number
    if 'line ' in short_fn.lower() or 'ln ' in short_fn.lower():
        return fields

    # Pattern: sheet XY, Person Name -> sheet XY, ln. N, Person Name
    new_short = re.sub(
        r'(sheet \d+[A-D]),\s*([A-Z])',
        rf'\1, ln. {line_number}, \2',
        short_fn
    )

    if new_short != short_fn:
        fields = re.sub(
            r'(<Name>ShortFootnote</Name>\s*<Value>)(.*?)(</Value>)',
            lambda m: m.group(1) + new_short + m.group(3),
            fields,
            flags=re.DOTALL
        )

    return fields


def update_bibliography(fields: str, line_number: int) -> str:
    """Update bibliography to include line number."""
    bib_match = re.search(r'<Name>Bibliography</Name>\s*<Value>(.*?)</Value>', fields, re.DOTALL)
    if not bib_match:
        return fields

    bib = bib_match.group(1)

    # Check if already has line number
    if 'line ' in bib.lower():
        return fields

    # Pattern: sheet XY, -> sheet XY, line N,
    new_bib = re.sub(
        r'(sheet \d+[A-D]),',
        rf'\1, line {line_number},',
        bib
    )

    if new_bib != bib:
        fields = re.sub(
            r'(<Name>Bibliography</Name>\s*<Value>)(.*?)(</Value>)',
            lambda m: m.group(1) + new_bib + m.group(3),
            fields,
            flags=re.DOTALL
        )

    return fields


def main():
    parser = argparse.ArgumentParser(description='Apply 1880 census line numbers')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes')
    parser.add_argument('--db', type=Path, default=Path('data/Iiams.rmtree'))
    args = parser.parse_args()

    print("=" * 70)
    print("APPLY 1880 CENSUS LINE NUMBERS")
    print("=" * 70)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY CHANGES'}")
    print(f"Sources to update: {len(LINE_NUMBERS)}")
    print()

    conn = connect_rmtree(str(args.db), read_only=args.dry_run)
    cursor = conn.cursor()

    updates = []

    for source_id, line_number in LINE_NUMBERS.items():
        cursor.execute('''
            SELECT SourceID, Name, CAST(Fields AS TEXT)
            FROM SourceTable
            WHERE SourceID = ?
        ''', (source_id,))

        row = cursor.fetchone()
        if not row:
            print(f"Source {source_id} not found!")
            continue

        _, name, fields = row

        new_name = update_source_name(name, line_number)
        new_fields = fields
        new_fields = update_footnote(new_fields, line_number)
        new_fields = update_short_footnote(new_fields, line_number)
        new_fields = update_bibliography(new_fields, line_number)

        if new_name != name or new_fields != fields:
            updates.append((source_id, new_name, new_fields, name, line_number))

    print(f"Sources to update: {len(updates)}")
    print()

    if args.dry_run:
        print("Sample updates (first 5):")
        for source_id, new_name, _, old_name, line_number in updates[:5]:
            print(f"\n  Source {source_id} (line {line_number}):")
            print(f"    Old: {old_name[:70]}...")
            print(f"    New: {new_name[:70]}...")
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

    conn.close()


if __name__ == '__main__':
    main()
