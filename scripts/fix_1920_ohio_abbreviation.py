#!/usr/bin/env python3
"""
Fix Census Ohio state abbreviation in short footnotes.

Problem: Ohio is incorrectly abbreviated as "Oh." in short footnotes.
Per Evidence Explained, Ohio has NO abbreviation and should remain "Ohio".

Pattern to fix:
  FROM: "1920 U.S. census, Knox Co., Oh., ..."
  TO:   "1920 U.S. census, Knox Co., Ohio, ..."

Usage:
    python scripts/fix_1920_ohio_abbreviation.py 1920 --dry-run    # Preview changes
    python scripts/fix_1920_ohio_abbreviation.py 1920              # Apply changes
    python scripts/fix_1920_ohio_abbreviation.py 1930 1940         # Fix multiple years
"""

import argparse
import re
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rmcitecraft.database.connection import connect_rmtree


def extract_field_from_blob(fields_blob: bytes | str | None, field_name: str) -> str:
    """Extract a field value from Fields BLOB."""
    if not fields_blob:
        return ""
    try:
        if isinstance(fields_blob, bytes):
            text = fields_blob.decode("utf-8", errors="ignore")
        else:
            text = fields_blob
        pattern = rf'<Name>{field_name}</Name>\s*<Value>(.*?)</Value>'
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1) if match else ""
    except Exception:
        return ""


def update_field_in_blob(fields_blob: bytes | str | None, field_name: str, new_value: str) -> str:
    """Update a field value in Fields BLOB, returning the modified XML string."""
    if not fields_blob:
        return ""
    try:
        if isinstance(fields_blob, bytes):
            text = fields_blob.decode("utf-8", errors="ignore")
        else:
            text = fields_blob

        pattern = rf'(<Name>{field_name}</Name>\s*<Value>)(.*?)(</Value>)'
        replacement = rf'\g<1>{new_value}\g<3>'
        return re.sub(pattern, replacement, text, flags=re.DOTALL)
    except Exception:
        return ""


def fix_ohio_abbreviation(short_footnote: str) -> tuple[str | None, str]:
    """
    Fix Ohio abbreviation in short footnote.

    Returns:
        Tuple of (fixed_text or None if no change needed, description of change)
    """
    # Pattern: "Co., Oh.," or "Co., Oh." at end
    # We need to be careful to only match "Oh." as the state abbreviation
    # Format: "{County} Co., Oh., {rest}" or "{County} Co., Oh."

    pattern = r'(Co\.,\s*)Oh\.(\s*,|\s*$)'

    if not re.search(pattern, short_footnote):
        return None, ""

    fixed = re.sub(pattern, r'\1Ohio\2', short_footnote)

    if fixed != short_footnote:
        return fixed, 'Changed "Oh." to "Ohio"'

    return None, ""


def fix_year(cursor, year: int, dry_run: bool, verbose: bool) -> int:
    """Fix Ohio abbreviation for a single census year. Returns number of fixes."""
    print("=" * 70)
    print(f"FIX {year} CENSUS OHIO STATE ABBREVIATION")
    print("=" * 70)
    print()
    print('Issue: Ohio abbreviated as "Oh." instead of "Ohio"')
    print('Per Evidence Explained, Ohio has NO abbreviation.')
    print()

    # Get all Ohio census sources for this year
    cursor.execute(f'''
        SELECT s.SourceID, s.Name, s.Fields
        FROM SourceTable s
        WHERE s.Name LIKE 'Fed Census: {year}, Ohio,%'
        ORDER BY s.SourceID
    ''')

    sources = cursor.fetchall()
    print(f"Found {len(sources)} {year} Ohio census sources")
    print()

    changes = []
    already_correct = 0

    for source_id, name, fields_blob in sources:
        short_footnote = extract_field_from_blob(fields_blob, "ShortFootnote")

        if not short_footnote:
            continue

        fixed_short, description = fix_ohio_abbreviation(short_footnote)

        if fixed_short:
            new_fields = update_field_in_blob(fields_blob, "ShortFootnote", fixed_short)
            changes.append({
                'source_id': source_id,
                'name': name,
                'old_short': short_footnote,
                'new_short': fixed_short,
                'new_fields': new_fields,
                'description': description,
            })
        else:
            already_correct += 1

    print(f"Sources needing fix: {len(changes)}")
    print(f"Sources already correct: {already_correct}")
    print()

    if changes:
        if verbose:
            print("All changes:")
            print("-" * 70)
            for change in changes:
                print(f"Source {change['source_id']}: {change['name'][:60]}...")
                print(f"  OLD: ...{change['old_short'][20:70]}...")
                print(f"  NEW: ...{change['new_short'][20:70]}...")
                print()
        else:
            print("Sample changes (first 5):")
            print("-" * 70)
            for change in changes[:5]:
                print(f"Source {change['source_id']}: {change['name'][:60]}...")
                print(f"  OLD: ...{change['old_short'][20:70]}...")
                print(f"  NEW: ...{change['new_short'][20:70]}...")
                print()
            if len(changes) > 5:
                print(f"... and {len(changes) - 5} more")
                print()

        if not dry_run:
            print(f"Applying {len(changes)} fixes...")
            for change in changes:
                cursor.execute(
                    'UPDATE SourceTable SET Fields = ? WHERE SourceID = ?',
                    (change['new_fields'], change['source_id'])
                )
            print(f"Applied {len(changes)} fixes for {year}.")
        else:
            print("DRY RUN - No changes applied")

    return len(changes)


def main():
    parser = argparse.ArgumentParser(
        description='Fix Ohio state abbreviation in Census short footnotes.'
    )
    parser.add_argument(
        'years',
        type=int,
        nargs='+',
        help='Census year(s) to fix (e.g., 1920 1930 1940)'
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
        '--verbose', '-v',
        action='store_true',
        help='Show all changes (not just summary)'
    )
    args = parser.parse_args()

    conn = connect_rmtree(str(args.db), read_only=args.dry_run)
    cursor = conn.cursor()

    total_fixes = 0
    for year in args.years:
        fixes = fix_year(cursor, year, args.dry_run, args.verbose)
        total_fixes += fixes
        print()

    if not args.dry_run and total_fixes > 0:
        conn.commit()
        print(f"Total: {total_fixes} fixes committed across {len(args.years)} year(s).")
    elif args.dry_run:
        print("DRY RUN - Run without --dry-run to apply changes.")

    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
