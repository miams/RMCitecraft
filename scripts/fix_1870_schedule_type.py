#!/usr/bin/env python3
"""
Fix 1870 Census Missing Population Schedule

Adds "population schedule" to footnotes and "pop. sch." to short footnotes
for 1870 census sources.

Usage:
    python scripts/fix_1870_schedule_type.py --dry-run    # Preview changes
    python scripts/fix_1870_schedule_type.py              # Apply changes
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rmcitecraft.database.connection import connect_rmtree


# US state names and their abbreviations
# Note: Some historical records use "Territory" suffix or alternate abbreviations
STATE_PATTERNS = {
    'Alabama': 'Ala.',
    'Arizona': 'Ariz.',
    'Arizona Territory': 'Ariz.',
    'Arkansas': 'Ark.',
    'California': 'Cal.',
    'Colorado': 'Colo.',
    'Colorado Territory': 'Colo.',
    'Connecticut': 'Conn.',
    'Delaware': 'Del.',
    'District of Columbia': 'D.C.',
    'Florida': 'Fla.',
    'Georgia': 'Ga.',
    'Idaho': 'Idaho',
    'Illinois': 'Ill.',
    'Indiana': 'Ind.',
    'Iowa': 'Iowa',
    'Kansas': 'Kans.',
    'Kentucky': 'Ky.',
    'Louisiana': 'La.',
    'Maine': 'Me.',
    'Maryland': 'Md.',
    'Massachusetts': 'Mass.',
    'Michigan': 'Mich.',
    'Minnesota': 'Minn.',
    'Mississippi': 'Miss.',
    'Missouri': 'Mo.',
    'Montana': 'Mont.',
    'Nebraska': 'Nebr.',
    'Nevada': 'Nev.',
    'New Hampshire': 'N.H.',
    'New Jersey': 'N.J.',
    'New Mexico': 'N.Mex.',
    'New York': 'N.Y.',
    'North Carolina': 'N.C.',
    'North Dakota': 'N.Dak.',
    'Ohio': 'Oh.',
    'Oklahoma': 'Okla.',
    'Oregon': 'Ore.',
    'Oregon Territory': 'Ore.',
    'Pennsylvania': 'Pa.',
    'Rhode Island': 'R.I.',
    'South Carolina': 'S.C.',
    'South Dakota': 'S.Dak.',
    'Tennessee': 'Tenn.',
    'Texas': 'Tex.',
    'Utah': 'Utah',
    'Vermont': 'Vt.',
    'Virginia': 'Va.',
    'Washington': 'Wash.',
    'West Virginia': 'W.Va.',
    'Wisconsin': 'Wis.',
    'Wyoming': 'Wyo.',
}

# Additional abbreviation variants found in historical records (for matching)
ALTERNATE_ABBREVS = ['Calif.', 'Oreg.']


def fix_footnote(footnote: str) -> tuple[str, bool]:
    """Add 'population schedule' after state name if missing.

    Handles two patterns:
    1. With township: 1870 U.S. census, County, State, Township, page...
       Target:        1870 U.S. census, County, State, population schedule, Township, page...
    2. No township:   1870 U.S. census, County, State, page...
       Target:        1870 U.S. census, County, State, population schedule, page...
    """
    # Skip if already has population schedule or slave schedule
    if 'population schedule' in footnote or 'slave schedule' in footnote:
        return footnote, False

    # Build regex pattern for all state names
    state_names = '|'.join(re.escape(s) for s in STATE_PATTERNS.keys())

    # Pattern 1: With township - "County, State, Township, page"
    pattern1 = rf'(1870 U\.S\. census, [^,]+, (?:{state_names})), ([^,]+, page)'
    new_footnote = re.sub(pattern1, r'\1, population schedule, \2', footnote)

    if new_footnote != footnote:
        return new_footnote, True

    # Pattern 2: No township - "County, State, page" (insert before page)
    pattern2 = rf'(1870 U\.S\. census, [^,]+, (?:{state_names})), (page)'
    new_footnote = re.sub(pattern2, r'\1, population schedule, \2', footnote)

    return new_footnote, new_footnote != footnote


def fix_short_footnote(short_fn: str) -> tuple[str, bool]:
    """Add 'pop. sch.' after state abbreviation or name if missing.

    Handles patterns with abbreviations or full state names:
    1. With township: 1870 U.S. census, Co., St., Township, page...
       Target:        1870 U.S. census, Co., St., pop. sch., Township, page...
    2. No township:   1870 U.S. census, Co., St., page...
       Target:        1870 U.S. census, Co., St., pop. sch., page...
    """
    # Skip if already has pop. sch. or slave sch.
    if 'pop. sch.' in short_fn or 'slave sch.' in short_fn:
        return short_fn, False

    # Build regex patterns for state abbreviations AND full names
    state_abbrevs = '|'.join(re.escape(s) for s in STATE_PATTERNS.values())
    alt_abbrevs = '|'.join(re.escape(s) for s in ALTERNATE_ABBREVS)
    state_names = '|'.join(re.escape(s) for s in STATE_PATTERNS.keys())
    all_states = f'{state_abbrevs}|{alt_abbrevs}|{state_names}'

    # Pattern 1: With township - "Co., St., Township, page"
    pattern1 = rf'(1870 U\.S\. census, [^,]+, (?:{all_states})), ([^,]+, (?:page|p\.))'
    new_short = re.sub(pattern1, r'\1, pop. sch., \2', short_fn)

    if new_short != short_fn:
        return new_short, True

    # Pattern 2: No township - "Co., St., page" (insert before page)
    pattern2 = rf'(1870 U\.S\. census, [^,]+, (?:{all_states})), ((?:page|p\.))'
    new_short = re.sub(pattern2, r'\1, pop. sch., \2', short_fn)

    return new_short, new_short != short_fn


def extract_field(fields_text: str, field_name: str) -> str:
    """Extract a field value from Fields XML."""
    pattern = rf'<Name>{field_name}</Name>\s*<Value>(.*?)</Value>'
    match = re.search(pattern, fields_text, re.DOTALL)
    return match.group(1) if match else ""


def update_field(fields_text: str, field_name: str, new_value: str) -> str:
    """Update a field value in Fields XML."""
    pattern = rf'(<Name>{field_name}</Name>\s*<Value>)(.*?)(</Value>)'

    def replacer(match):
        return match.group(1) + new_value + match.group(3)

    return re.sub(pattern, replacer, fields_text, flags=re.DOTALL)


def main():
    parser = argparse.ArgumentParser(description='Fix 1870 census missing population schedule')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--db', type=Path, default=Path('data/Iiams.rmtree'))
    args = parser.parse_args()

    print("=" * 70)
    print("FIX 1870 CENSUS MISSING POPULATION SCHEDULE")
    print("=" * 70)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY CHANGES'}")
    print()

    conn = connect_rmtree(str(args.db), read_only=args.dry_run)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT SourceID, Name, Fields
        FROM SourceTable
        WHERE Name LIKE 'Fed Census: 1870,%'
        ORDER BY SourceID
    ''')

    updates = []
    fn_fixes = 0
    sfn_fixes = 0

    for row in cursor.fetchall():
        source_id, name, fields_blob = row
        if not fields_blob:
            continue

        fields_text = fields_blob.decode('utf-8', errors='ignore')
        original_text = fields_text

        # Fix footnote
        footnote = extract_field(fields_text, 'Footnote')
        if footnote:
            new_footnote, fn_changed = fix_footnote(footnote)
            if fn_changed:
                fields_text = update_field(fields_text, 'Footnote', new_footnote)
                fn_fixes += 1

        # Fix short footnote
        short_fn = extract_field(fields_text, 'ShortFootnote')
        if short_fn:
            new_short, sfn_changed = fix_short_footnote(short_fn)
            if sfn_changed:
                fields_text = update_field(fields_text, 'ShortFootnote', new_short)
                sfn_fixes += 1

        if fields_text != original_text:
            updates.append((source_id, name, fields_text))

    print(f"Footnotes to fix: {fn_fixes}")
    print(f"Short footnotes to fix: {sfn_fixes}")
    print(f"Total sources to update: {len(updates)}")
    print()

    if args.dry_run and updates:
        print("Sample changes (first 5):")
        for source_id, name, new_fields in updates[:5]:
            print(f"\n  Source {source_id}: {name[:60]}")
            fn = extract_field(new_fields, 'Footnote')
            sfn = extract_field(new_fields, 'ShortFootnote')
            # Show the schedule part
            fn_match = re.search(r'(population schedule|slave schedule)', fn)
            sfn_match = re.search(r'(pop\. sch\.|slave sch\.)', sfn)
            if fn_match:
                print(f"    Footnote now has: '{fn_match.group(1)}'")
            if sfn_match:
                print(f"    Short footnote now has: '{sfn_match.group(1)}'")
    elif updates:
        for source_id, name, new_fields in updates:
            cursor.execute(
                "UPDATE SourceTable SET Fields = ? WHERE SourceID = ?",
                (new_fields.encode('utf-8'), source_id)
            )
        conn.commit()
        print(f"Updated {len(updates)} sources")

    print()
    print("=" * 70)
    if args.dry_run:
        print("DRY RUN - No changes made")
    else:
        print("Changes applied successfully")

    conn.close()


if __name__ == '__main__':
    main()
