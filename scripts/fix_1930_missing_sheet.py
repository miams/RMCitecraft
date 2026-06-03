#!/usr/bin/env python3
"""
Fix 1930 Census sources with missing sheet numbers in source name.

Extracts sheet number from footnote and adds it to source name.

Source name format:
  Before: Fed Census: 1930, State, County [citing enumeration district (ED) XX, sheet , line LL, family ZZ] Person
  After:  Fed Census: 1930, State, County [citing enumeration district (ED) XX, sheet YY, line LL, family ZZ] Person

Usage:
    python scripts/fix_1930_missing_sheet.py --dry-run    # Preview changes
    python scripts/fix_1930_missing_sheet.py              # Apply changes
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path


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


def connect_database(db_path: Path) -> sqlite3.Connection:
    """Connect to RootsMagic database with ICU extension."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)

    # Try to load ICU extension for RMNOCASE collation
    script_dir = Path(__file__).parent.parent
    possible_paths = [
        script_dir / 'sqlite-extension/icu.dylib',
        Path('sqlite-extension/icu.dylib'),
        Path.cwd() / 'sqlite-extension/icu.dylib',
    ]

    for icu_path in possible_paths:
        if icu_path.exists():
            try:
                conn.enable_load_extension(True)
                conn.load_extension(str(icu_path))
                conn.execute(
                    "SELECT icu_load_collation("
                    "'en_US@colStrength=primary;caseLevel=off;normalization=on',"
                    "'RMNOCASE')"
                )
                conn.enable_load_extension(False)
                break
            except Exception:
                pass

    return conn


def extract_sheet_from_footnote(footnote: str) -> str | None:
    """
    Extract sheet number from footnote.

    Looks for patterns like:
      - "sheet 16A, line"
      - "sheet 3A, line"
      - "sheet 2B,"
    """
    # Pattern: sheet followed by number and optional letter, then comma
    match = re.search(r'sheet\s+(\d+[AB]?),', footnote, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def extract_sheet_from_short_footnote(short: str) -> str | None:
    """Extract sheet number from short footnote."""
    match = re.search(r'sheet\s+(\d+[AB]?),', short, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def fix_source_name(name: str, sheet: str) -> str | None:
    """
    Add sheet number to source name.

    Pattern: Replace 'sheet , ' with 'sheet XX, '

    Returns None if pattern not found.
    """
    # Pattern: "sheet , " or "sheet, " (empty sheet value)
    pattern = r'sheet\s*,\s*((?:line|family))'
    replacement = rf'sheet {sheet}, \1'

    new_name, count = re.subn(pattern, replacement, name, flags=re.IGNORECASE)

    return new_name if count > 0 else None


def main():
    parser = argparse.ArgumentParser(
        description='Fix 1930 Census sources with missing sheet numbers.'
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
    args = parser.parse_args()

    conn = connect_database(args.db)
    cursor = conn.cursor()

    # Find 1930 sources with missing sheet number
    cursor.execute('''
        SELECT s.SourceID, s.Name, s.Fields
        FROM SourceTable s
        WHERE s.Name LIKE 'Fed Census: 1930,%'
        AND s.Name LIKE '%sheet ,%'
    ''')

    sources = []
    for source_id, name, fields_blob in cursor.fetchall():
        footnote = extract_field_from_blob(fields_blob, 'Footnote')
        short = extract_field_from_blob(fields_blob, 'ShortFootnote')

        # Try to extract sheet from footnote first, then short footnote
        sheet = extract_sheet_from_footnote(footnote)
        if not sheet:
            sheet = extract_sheet_from_short_footnote(short)

        sources.append({
            'source_id': source_id,
            'name': name,
            'sheet': sheet,
            'footnote': footnote[:150] if footnote else '',
        })

    print(f"Found {len(sources)} sources with missing sheet number")
    print()

    fixable = []
    unfixable = []

    for source in sources:
        if source['sheet']:
            new_name = fix_source_name(source['name'], source['sheet'])
            if new_name:
                fixable.append({
                    **source,
                    'new_name': new_name
                })
            else:
                unfixable.append({**source, 'reason': 'Pattern not matched'})
        else:
            unfixable.append({**source, 'reason': 'No sheet number in footnote'})

    print(f"Fixable: {len(fixable)}")
    print(f"Unfixable: {len(unfixable)}")
    print()

    if unfixable:
        print("=== UNFIXABLE SOURCES ===")
        for source in unfixable:
            print(f"  Source {source['source_id']}: {source['reason']}")
            print(f"    Name: {source['name'][:70]}...")
            if source['footnote']:
                print(f"    Footnote: {source['footnote'][:70]}...")
        print()

    if fixable:
        print("=== CHANGES TO APPLY ===")
        for source in fixable[:15]:  # Show first 15
            print(f"Source {source['source_id']} (sheet {source['sheet']}):")
            print(f"  Before: {source['name']}")
            print(f"  After:  {source['new_name']}")
            print()

        if len(fixable) > 15:
            print(f"  ... and {len(fixable) - 15} more")
            print()

    if args.dry_run:
        print("DRY RUN - No changes applied")
        return 0

    if not fixable:
        print("No changes to apply")
        return 0

    # Apply changes
    print("Applying changes...")

    for source in fixable:
        cursor.execute(
            'UPDATE SourceTable SET Name = ? WHERE SourceID = ?',
            (source['new_name'], source['source_id'])
        )

    conn.commit()
    print(f"Updated {len(fixable)} sources")

    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
