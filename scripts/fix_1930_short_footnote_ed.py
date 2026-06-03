#!/usr/bin/env python3
"""
Fix 1930 Census sources with missing ED number in short footnote.

Extracts ED number from source name and adds it to short footnote.

Short footnote format:
  Before: 1930 U.S. census, County Co., State, Locality, E.D. , sheet XX...
  After:  1930 U.S. census, County Co., State, Locality, E.D. YY, sheet XX...

Usage:
    python scripts/fix_1930_short_footnote_ed.py --dry-run    # Preview changes
    python scripts/fix_1930_short_footnote_ed.py              # Apply changes
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


def update_field_in_blob(fields_blob: bytes, field_name: str, old_value: str, new_value: str) -> bytes:
    """Update a field value in the Fields BLOB XML structure."""
    if not fields_blob:
        return fields_blob
    try:
        fields_text = fields_blob.decode('utf-8', errors='ignore')
        pattern = rf'(<Name>{field_name}</Name>\s*<Value>)(.*?)(</Value>)'

        def replacer(match):
            prefix = match.group(1)
            content = match.group(2)
            suffix = match.group(3)
            new_content = content.replace(old_value, new_value)
            return prefix + new_content + suffix

        new_text = re.sub(pattern, replacer, fields_text, flags=re.DOTALL)
        return new_text.encode('utf-8')
    except Exception as e:
        print(f"Error updating blob: {e}")
        return fields_blob


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


def extract_ed_from_source_name(name: str) -> str | None:
    """
    Extract ED number from source name.

    Patterns:
      - [citing enumeration district (ED) 232,
      - [ED 12-34,
    """
    # Try citing enumeration district pattern first
    match = re.search(r'\[citing enumeration district \(ED\)\s+(\d+)', name)
    if match:
        return match.group(1)

    # Try [ED pattern
    match = re.search(r'\[ED\s+(\d+(?:-\d+)?)', name)
    if match:
        return match.group(1)

    return None


def fix_short_footnote(short: str, ed: str) -> tuple[str, bool]:
    """
    Add ED number to short footnote.

    Pattern: Replace 'E.D. ,' with 'E.D. XX,'

    Returns (new_short, was_modified).
    """
    # Pattern: "E.D. ," or "E.D.," (empty ED value)
    pattern = r'E\.D\.\s*,'

    if re.search(pattern, short):
        new_short = re.sub(pattern, f'E.D. {ed},', short)
        return new_short, True

    return short, False


def main():
    parser = argparse.ArgumentParser(
        description='Fix 1930 Census sources with missing ED number in short footnote.'
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

    # Find 1930 sources with missing ED in short footnote
    cursor.execute('''
        SELECT s.SourceID, s.Name, s.Fields
        FROM SourceTable s
        WHERE s.Name LIKE 'Fed Census: 1930,%'
    ''')

    sources_to_fix = []

    for source_id, name, fields_blob in cursor.fetchall():
        short = extract_field_from_blob(fields_blob, 'ShortFootnote')

        # Check if short footnote has empty ED
        if not short or 'E.D.' not in short:
            continue

        # Check for empty ED pattern
        if not re.search(r'E\.D\.\s*,', short):
            continue

        # Extract ED from source name
        ed = extract_ed_from_source_name(name)

        if ed:
            new_short, modified = fix_short_footnote(short, ed)
            if modified:
                sources_to_fix.append({
                    'source_id': source_id,
                    'name': name,
                    'ed': ed,
                    'old_short': short,
                    'new_short': new_short,
                    'fields_blob': fields_blob,
                })

    print(f"Found {len(sources_to_fix)} sources with missing ED in short footnote")
    print()

    if not sources_to_fix:
        print("No changes needed")
        return 0

    print("=== CHANGES TO APPLY ===")
    for source in sources_to_fix:
        print(f"Source {source['source_id']} (ED {source['ed']}):")
        print(f"  Before: {source['old_short'][:80]}...")
        print(f"  After:  {source['new_short'][:80]}...")
        print()

    if args.dry_run:
        print("DRY RUN - No changes applied")
        return 0

    # Apply changes
    print("Applying changes...")

    for source in sources_to_fix:
        new_blob = update_field_in_blob(
            source['fields_blob'],
            'ShortFootnote',
            source['old_short'],
            source['new_short']
        )
        cursor.execute(
            'UPDATE SourceTable SET Fields = ? WHERE SourceID = ?',
            (new_blob, source['source_id'])
        )

    conn.commit()
    print(f"Updated {len(sources_to_fix)} sources")

    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
