#!/usr/bin/env python3
"""
Fix Census bibliography and footnote titles to use official FamilySearch format.

Changes for 1930, 1940, 1950:
  Bibliography: "United States, Census, YYYY."  (comma after States, trailing period)
  Footnote:     "United States, Census, YYYY,"  (comma after States, trailing comma)

Handles various source formats including Ancestry titles.

Usage:
    python scripts/fix_census_titles.py --dry-run    # Preview changes
    python scripts/fix_census_titles.py              # Apply changes
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path
from dataclasses import dataclass


@dataclass
class TitleFix:
    """Represents a title replacement."""
    old_pattern: str
    new_value: str


# Define all title replacements for each year
# Includes both &quot; (XML entity) and regular " quote formats
TITLE_FIXES = {
    1930: {
        'bibliography': [
            # &quot; format
            TitleFix('&quot;United States Census, 1930&quot;', '&quot;United States, Census, 1930.&quot;'),
            TitleFix('&quot;United States Census, 1930.&quot;', '&quot;United States, Census, 1930.&quot;'),
            TitleFix('&quot;1930 United States Federal Census.&quot;', '&quot;United States, Census, 1930.&quot;'),
            TitleFix('&quot;1930 United States Federal Census&quot;', '&quot;United States, Census, 1930.&quot;'),
            # Regular quote format
            TitleFix('"United States Census, 1930"', '"United States, Census, 1930."'),
            TitleFix('"United States Census, 1930."', '"United States, Census, 1930."'),
            TitleFix('"1930 United States Federal Census."', '"United States, Census, 1930."'),
            TitleFix('"1930 United States Federal Census"', '"United States, Census, 1930."'),
        ],
        'footnote': [
            # &quot; format
            TitleFix('&quot;United States Census, 1930,&quot;', '&quot;United States, Census, 1930,&quot;'),
            TitleFix('&quot;United States Census, 1930.&quot;', '&quot;United States, Census, 1930,&quot;'),
            TitleFix('&quot;United States Census, 1930&quot;', '&quot;United States, Census, 1930,&quot;'),
            TitleFix('&quot;1930 United States Federal Census,&quot;', '&quot;United States, Census, 1930,&quot;'),
            TitleFix('&quot;1930 United States Federal Census.&quot;', '&quot;United States, Census, 1930,&quot;'),
            # Regular quote format
            TitleFix('"United States Census, 1930,"', '"United States, Census, 1930,"'),
            TitleFix('"United States Census, 1930."', '"United States, Census, 1930,"'),
            TitleFix('"United States Census, 1930"', '"United States, Census, 1930,"'),
            TitleFix('"1930 United States Federal Census,"', '"United States, Census, 1930,"'),
            TitleFix('"1930 United States Federal Census."', '"United States, Census, 1930,"'),
        ],
    },
    1940: {
        'bibliography': [
            # &quot; format
            TitleFix('&quot;United States Census, 1940&quot;', '&quot;United States, Census, 1940.&quot;'),
            TitleFix('&quot;United States Census, 1940.&quot;', '&quot;United States, Census, 1940.&quot;'),
            TitleFix('&quot;1940 United States Federal Census.&quot;', '&quot;United States, Census, 1940.&quot;'),
            TitleFix('&quot;1940 United States Federal Census&quot;', '&quot;United States, Census, 1940.&quot;'),
            # Regular quote format
            TitleFix('"United States Census, 1940"', '"United States, Census, 1940."'),
            TitleFix('"United States Census, 1940."', '"United States, Census, 1940."'),
            TitleFix('"1940 United States Federal Census."', '"United States, Census, 1940."'),
            TitleFix('"1940 United States Federal Census"', '"United States, Census, 1940."'),
        ],
        'footnote': [
            # &quot; format
            TitleFix('&quot;United States Census, 1940,&quot;', '&quot;United States, Census, 1940,&quot;'),
            TitleFix('&quot;United States Census, 1940.&quot;', '&quot;United States, Census, 1940,&quot;'),
            TitleFix('&quot;United States Census, 1940&quot;', '&quot;United States, Census, 1940,&quot;'),
            TitleFix('&quot;1940 United States Federal Census,&quot;', '&quot;United States, Census, 1940,&quot;'),
            TitleFix('&quot;1940 United States Federal Census.&quot;', '&quot;United States, Census, 1940,&quot;'),
            # Regular quote format
            TitleFix('"United States Census, 1940,"', '"United States, Census, 1940,"'),
            TitleFix('"United States Census, 1940."', '"United States, Census, 1940,"'),
            TitleFix('"United States Census, 1940"', '"United States, Census, 1940,"'),
            TitleFix('"1940 United States Federal Census,"', '"United States, Census, 1940,"'),
            TitleFix('"1940 United States Federal Census."', '"United States, Census, 1940,"'),
        ],
    },
    1950: {
        'bibliography': [
            # &quot; format
            TitleFix('&quot;United States Census, 1950&quot;', '&quot;United States, Census, 1950.&quot;'),
            TitleFix('&quot;United States Census, 1950.&quot;', '&quot;United States, Census, 1950.&quot;'),
            TitleFix('&quot;1950 United States Federal Census.&quot;', '&quot;United States, Census, 1950.&quot;'),
            TitleFix('&quot;1950 United States Federal Census&quot;', '&quot;United States, Census, 1950.&quot;'),
            # Regular quote format
            TitleFix('"United States Census, 1950"', '"United States, Census, 1950."'),
            TitleFix('"United States Census, 1950."', '"United States, Census, 1950."'),
            TitleFix('"1950 United States Federal Census."', '"United States, Census, 1950."'),
            TitleFix('"1950 United States Federal Census"', '"United States, Census, 1950."'),
        ],
        'footnote': [
            # &quot; format
            TitleFix('&quot;United States Census, 1950,&quot;', '&quot;United States, Census, 1950,&quot;'),
            TitleFix('&quot;United States Census, 1950.&quot;', '&quot;United States, Census, 1950,&quot;'),
            TitleFix('&quot;United States Census, 1950&quot;', '&quot;United States, Census, 1950,&quot;'),
            TitleFix('&quot;1950 United States Federal Census,&quot;', '&quot;United States, Census, 1950,&quot;'),
            TitleFix('&quot;1950 United States Federal Census.&quot;', '&quot;United States, Census, 1950,&quot;'),
            # Regular quote format
            TitleFix('"United States Census, 1950,"', '"United States, Census, 1950,"'),
            TitleFix('"United States Census, 1950."', '"United States, Census, 1950,"'),
            TitleFix('"United States Census, 1950"', '"United States, Census, 1950,"'),
            TitleFix('"1950 United States Federal Census,"', '"United States, Census, 1950,"'),
            TitleFix('"1950 United States Federal Census."', '"United States, Census, 1950,"'),
        ],
    },
}


def extract_field_from_blob(fields_blob: bytes, field_name: str) -> str:
    """Extract a field value from the Fields BLOB XML structure."""
    if not fields_blob:
        return ""
    try:
        fields_text = fields_blob.decode('utf-8', errors='ignore')
        pattern = rf'<Name>{field_name}</Name>\s*<Value>(.*?)</Value>'
        match = re.search(pattern, fields_text, re.DOTALL)
        return match.group(1) if match else ""
    except Exception:
        return ""


def update_field_in_blob(fields_blob: bytes, field_name: str, fixes: list[TitleFix]) -> tuple[bytes, bool]:
    """
    Apply title fixes to a field in the Fields BLOB.

    Returns (new_blob, was_modified).
    """
    if not fields_blob:
        return fields_blob, False

    try:
        fields_text = fields_blob.decode('utf-8', errors='ignore')
        original_text = fields_text

        # Find the field and apply fixes
        pattern = rf'(<Name>{field_name}</Name>\s*<Value>)(.*?)(</Value>)'

        def replacer(match):
            prefix = match.group(1)
            content = match.group(2)
            suffix = match.group(3)

            # Apply each fix in order
            for fix in fixes:
                if fix.old_pattern in content:
                    content = content.replace(fix.old_pattern, fix.new_value)
                    break  # Only apply first matching fix

            return prefix + content + suffix

        fields_text = re.sub(pattern, replacer, fields_text, flags=re.DOTALL)

        was_modified = fields_text != original_text
        return fields_text.encode('utf-8'), was_modified

    except Exception as e:
        print(f"Error updating blob: {e}")
        return fields_blob, False


def connect_database(db_path: Path) -> sqlite3.Connection:
    """Connect to RootsMagic database."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    return sqlite3.connect(db_path)


def main():
    parser = argparse.ArgumentParser(
        description='Fix Census bibliography and footnote titles to FamilySearch format.'
    )
    parser.add_argument(
        '--db',
        type=Path,
        default=Path('data/Iiams.rmtree'),
        help='Path to RootsMagic database'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without applying them'
    )
    parser.add_argument(
        '--year',
        type=int,
        choices=[1930, 1940, 1950],
        help='Fix only specific year (default: all)'
    )
    args = parser.parse_args()

    conn = connect_database(args.db)
    cursor = conn.cursor()

    years = [args.year] if args.year else [1930, 1940, 1950]

    total_bib_fixed = 0
    total_fn_fixed = 0

    for year in years:
        print(f"\n{'='*60}")
        print(f"Processing {year} Census")
        print(f"{'='*60}")

        fixes = TITLE_FIXES[year]

        # Get all sources for this year
        cursor.execute('''
            SELECT s.SourceID, s.Name, s.Fields
            FROM SourceTable s
            WHERE s.Name LIKE ?
        ''', (f'Fed Census: {year},%',))

        sources = cursor.fetchall()
        print(f"Found {len(sources)} sources")

        bib_fixed = 0
        fn_fixed = 0
        changes = []

        for source_id, name, fields_blob in sources:
            if not fields_blob:
                continue

            # Check and fix bibliography
            old_bib = extract_field_from_blob(fields_blob, 'Bibliography')
            new_blob, bib_modified = update_field_in_blob(fields_blob, 'Bibliography', fixes['bibliography'])

            # Check and fix footnote
            old_fn = extract_field_from_blob(fields_blob, 'Footnote')
            new_blob, fn_modified = update_field_in_blob(new_blob, 'Footnote', fixes['footnote'])

            if bib_modified or fn_modified:
                new_bib = extract_field_from_blob(new_blob, 'Bibliography')
                new_fn = extract_field_from_blob(new_blob, 'Footnote')

                changes.append({
                    'source_id': source_id,
                    'name': name,
                    'bib_modified': bib_modified,
                    'fn_modified': fn_modified,
                    'old_bib': old_bib[:80] if old_bib else '',
                    'new_bib': new_bib[:80] if new_bib else '',
                    'old_fn': old_fn[:80] if old_fn else '',
                    'new_fn': new_fn[:80] if new_fn else '',
                    'new_blob': new_blob,
                })

                if bib_modified:
                    bib_fixed += 1
                if fn_modified:
                    fn_fixed += 1

        print(f"Bibliography fixes needed: {bib_fixed}")
        print(f"Footnote fixes needed: {fn_fixed}")

        if changes and not args.dry_run:
            print(f"\nApplying {len(changes)} changes...")
            for change in changes:
                cursor.execute(
                    'UPDATE SourceTable SET Fields = ? WHERE SourceID = ?',
                    (change['new_blob'], change['source_id'])
                )

        # Show sample changes
        if changes:
            print(f"\nSample changes (first 5):")
            for change in changes[:5]:
                print(f"  Source {change['source_id']}:")
                if change['bib_modified']:
                    print(f"    Bib: ...{change['old_bib'][20:60]}...")
                    print(f"      -> ...{change['new_bib'][20:60]}...")
                if change['fn_modified']:
                    print(f"    Fn:  ...{change['old_fn'][20:60]}...")
                    print(f"      -> ...{change['new_fn'][20:60]}...")

        total_bib_fixed += bib_fixed
        total_fn_fixed += fn_fixed

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total bibliography fixes: {total_bib_fixed}")
    print(f"Total footnote fixes: {total_fn_fixed}")

    if args.dry_run:
        print("\nDRY RUN - No changes applied")
    else:
        conn.commit()
        print(f"\nChanges applied successfully")

    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
