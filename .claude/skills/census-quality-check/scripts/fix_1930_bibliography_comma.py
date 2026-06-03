#!/usr/bin/env python3
"""
Fix 1930 Census sources with trailing comma in bibliography title.

Changes: "United States Census, 1930," -> "United States Census, 1930."

Usage:
    python scripts/fix_1930_bibliography_comma.py --dry-run    # Preview changes
    python scripts/fix_1930_bibliography_comma.py              # Apply changes
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
        # Replace the old value with new value within the field
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


def main():
    parser = argparse.ArgumentParser(
        description='Fix 1930 Census bibliography trailing comma.'
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

    # Find sources with trailing comma in bibliography
    cursor.execute('''
        SELECT s.SourceID, s.Name, s.Fields
        FROM SourceTable s
        WHERE s.Name LIKE 'Fed Census: 1930,%'
    ''')

    sources_to_fix = []
    for source_id, name, fields_blob in cursor.fetchall():
        bib = extract_field_from_blob(fields_blob, 'Bibliography')
        # Check for the trailing comma pattern (both quote styles)
        if '&quot;United States Census, 1930,&quot;' in bib:
            sources_to_fix.append({
                'source_id': source_id,
                'name': name,
                'fields_blob': fields_blob,
                'old_pattern': '&quot;United States Census, 1930,&quot;',
                'new_pattern': '&quot;United States Census, 1930.&quot;',
                'bibliography': bib
            })

    print(f"Found {len(sources_to_fix)} sources with trailing comma in bibliography")
    print()

    if not sources_to_fix:
        print("No changes needed")
        return 0

    print("=== CHANGES TO APPLY ===")
    for source in sources_to_fix:
        print(f"Source {source['source_id']}: {source['name']}")
        print(f"  Before: ...{source['old_pattern']}...")
        print(f"  After:  ...{source['new_pattern']}...")
        print()

    if args.dry_run:
        print("DRY RUN - No changes applied")
        return 0

    # Apply changes
    print("Applying changes...")
    for source in sources_to_fix:
        new_blob = update_field_in_blob(
            source['fields_blob'],
            'Bibliography',
            source['old_pattern'],
            source['new_pattern']
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
