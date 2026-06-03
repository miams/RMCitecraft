#!/usr/bin/env python3
"""
Fix 1930 Census sources missing line numbers in source name.

Extracts line number from footnote and adds it to source name.

Source name format:
  Before: Fed Census: 1930, State, County [citing enumeration district (ED) XX, sheet YY, family ZZ] Person
  After:  Fed Census: 1930, State, County [citing enumeration district (ED) XX, sheet YY, line LL, family ZZ] Person

Usage:
    python scripts/fix_1930_missing_line.py --dry-run    # Preview changes
    python scripts/fix_1930_missing_line.py              # Apply changes
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


def find_sources_missing_line(conn: sqlite3.Connection) -> list[dict]:
    """Find 1930 Census sources missing line number in source name."""
    cursor = conn.cursor()

    cursor.execute('''
        SELECT s.SourceID, s.Name, s.Fields
        FROM SourceTable s
        WHERE s.Name LIKE 'Fed Census: 1930,%'
        AND s.Name NOT LIKE '%line%'
    ''')

    sources = []
    for source_id, name, fields_blob in cursor.fetchall():
        footnote = extract_field_from_blob(fields_blob, 'Footnote')
        short = extract_field_from_blob(fields_blob, 'ShortFootnote')

        # Extract line number from footnote or short footnote
        fn_line_match = re.search(r'line (\d+)', footnote)
        short_line_match = re.search(r'line (\d+)', short)

        line_num = None
        if fn_line_match:
            line_num = fn_line_match.group(1)
        elif short_line_match:
            line_num = short_line_match.group(1)

        sources.append({
            'source_id': source_id,
            'name': name,
            'line_num': line_num,
            'footnote': footnote[:100] if footnote else '',
        })

    return sources


def fix_source_name(name: str, line_num: str) -> str | None:
    """
    Add line number to source name.

    Pattern: Insert 'line LL, ' before 'family' in the bracketed section.

    Returns None if pattern not found or already has line.
    """
    if 'line' in name.lower():
        return None

    # Pattern: find ", family" and insert "line XX, " before it
    # Handle case where sheet value might be empty: "sheet , family"
    pattern = r'(sheet [^,]*, )(family \d+)'
    replacement = rf'\1line {line_num}, \2'

    new_name, count = re.subn(pattern, replacement, name)

    if count == 0:
        # Try alternate pattern without family number
        # Some might have "] Person" directly after sheet
        pattern2 = r'(sheet [^,\]]*)(] [A-Z])'
        replacement2 = rf'\1, line {line_num}\2'
        new_name, count = re.subn(pattern2, replacement2, name)

    return new_name if count > 0 else None


def main():
    parser = argparse.ArgumentParser(
        description='Fix 1930 Census sources missing line numbers in source name.'
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
    sources = find_sources_missing_line(conn)

    print(f"Found {len(sources)} sources missing line number in name")
    print()

    fixable = []
    unfixable = []

    for source in sources:
        if source['line_num']:
            new_name = fix_source_name(source['name'], source['line_num'])
            if new_name:
                fixable.append({
                    **source,
                    'new_name': new_name
                })
            else:
                unfixable.append({**source, 'reason': 'Pattern not matched'})
        else:
            unfixable.append({**source, 'reason': 'No line number in footnote'})

    print(f"Fixable: {len(fixable)}")
    print(f"Unfixable: {len(unfixable)}")
    print()

    if unfixable:
        print("=== UNFIXABLE SOURCES ===")
        for source in unfixable:
            print(f"  Source {source['source_id']}: {source['reason']}")
            print(f"    {source['name'][:70]}...")
        print()

    if fixable:
        print("=== CHANGES TO APPLY ===")
        for source in fixable[:10]:  # Show first 10
            print(f"Source {source['source_id']}:")
            print(f"  Before: {source['name']}")
            print(f"  After:  {source['new_name']}")
            print()

        if len(fixable) > 10:
            print(f"  ... and {len(fixable) - 10} more")
            print()

    if args.dry_run:
        print("DRY RUN - No changes applied")
        return 0

    if not fixable:
        print("No changes to apply")
        return 0

    # Apply changes
    print("Applying changes...")
    cursor = conn.cursor()

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
