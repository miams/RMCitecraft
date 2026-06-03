#!/usr/bin/env python3
"""
Fix miscellaneous 1930 Census source issues.

Fixes:
1. ED pattern typos ("[iting" -> "[citing", "numeration" -> "enumeration")
2. Double spaces in footnote and bibliography
3. State name typos ("Pennyslvania" -> "Pennsylvania")
4. Short footnote formatting issues (stray brackets, missing periods)
5. Duplicate "ED ED" patterns

Usage:
    python scripts/fix_1930_misc_issues.py --dry-run    # Preview changes
    python scripts/fix_1930_misc_issues.py              # Apply changes
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Fix:
    """A single fix to apply."""
    source_id: int
    field: str  # 'name', 'footnote', 'short_footnote', 'bibliography'
    issue: str
    old_value: str
    new_value: str


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


def find_fixes(conn: sqlite3.Connection) -> list[Fix]:
    """Find all fixable issues."""
    cursor = conn.cursor()
    fixes = []

    cursor.execute('''
        SELECT s.SourceID, s.Name, s.Fields
        FROM SourceTable s
        WHERE s.Name LIKE 'Fed Census: 1930,%'
    ''')

    for source_id, name, fields_blob in cursor.fetchall():
        footnote = extract_field_from_blob(fields_blob, 'Footnote')
        short = extract_field_from_blob(fields_blob, 'ShortFootnote')
        bibliography = extract_field_from_blob(fields_blob, 'Bibliography')

        # Fix 1: ED pattern typos in source name
        if '[iting enumeration' in name:
            fixes.append(Fix(
                source_id=source_id,
                field='name',
                issue='typo: [iting -> [citing',
                old_value=name,
                new_value=name.replace('[iting enumeration', '[citing enumeration')
            ))

        if 'citing numeration district' in name:
            new_name = name.replace('citing numeration district', 'citing enumeration district')
            # Also fix duplicate "ED ED" pattern
            new_name = re.sub(r'\(ED\)\s+ED\s+(\d+)', r'(ED) \1', new_name)
            fixes.append(Fix(
                source_id=source_id,
                field='name',
                issue='typo: numeration -> enumeration, ED ED -> ED',
                old_value=name,
                new_value=new_name
            ))

        # Fix 2: State name typos
        if 'Pennyslvania' in name:
            fixes.append(Fix(
                source_id=source_id,
                field='name',
                issue='typo: Pennyslvania -> Pennsylvania',
                old_value=name,
                new_value=name.replace('Pennyslvania', 'Pennsylvania')
            ))

        # Fix 3: Double spaces in footnote
        if footnote and '  ' in footnote:
            fixes.append(Fix(
                source_id=source_id,
                field='footnote',
                issue='double space',
                old_value=footnote,
                new_value=re.sub(r'  +', ' ', footnote)
            ))

        # Fix 4: Double spaces in bibliography
        if bibliography and '  ' in bibliography:
            fixes.append(Fix(
                source_id=source_id,
                field='bibliography',
                issue='double space',
                old_value=bibliography,
                new_value=re.sub(r'  +', ' ', bibliography)
            ))

        # Fix 5: Short footnote issues
        if short:
            new_short = short
            modified = False

            # Remove stray brackets like "] Name" at end
            if re.search(r'\]\s*[A-Z][a-z]+,?\s*[A-Z]', short):
                # Pattern: "] Iams, Denis" should be "Iams, Denis"
                new_short = re.sub(r'\]\s*([A-Z])', r'\1', new_short)
                modified = True

            # Add missing period at end
            stripped = new_short.rstrip()
            if stripped and not stripped.endswith('.'):
                new_short = stripped + '.'
                modified = True

            if modified and new_short != short:
                fixes.append(Fix(
                    source_id=source_id,
                    field='short_footnote',
                    issue='formatting (stray bracket, missing period)',
                    old_value=short,
                    new_value=new_short
                ))

    return fixes


def apply_fixes(conn: sqlite3.Connection, fixes: list[Fix]) -> int:
    """Apply fixes to database."""
    cursor = conn.cursor()
    applied = 0

    # Group fixes by source_id
    fixes_by_source: dict[int, list[Fix]] = {}
    for fix in fixes:
        if fix.source_id not in fixes_by_source:
            fixes_by_source[fix.source_id] = []
        fixes_by_source[fix.source_id].append(fix)

    for source_id, source_fixes in fixes_by_source.items():
        # Get current values
        cursor.execute('SELECT Name, Fields FROM SourceTable WHERE SourceID = ?', (source_id,))
        row = cursor.fetchone()
        if not row:
            continue

        name, fields_blob = row
        new_name = name
        new_blob = fields_blob

        for fix in source_fixes:
            if fix.field == 'name':
                new_name = fix.new_value
            elif fix.field == 'footnote':
                new_blob = update_field_in_blob(new_blob, 'Footnote', fix.old_value, fix.new_value)
            elif fix.field == 'short_footnote':
                new_blob = update_field_in_blob(new_blob, 'ShortFootnote', fix.old_value, fix.new_value)
            elif fix.field == 'bibliography':
                new_blob = update_field_in_blob(new_blob, 'Bibliography', fix.old_value, fix.new_value)

        # Update database
        cursor.execute(
            'UPDATE SourceTable SET Name = ?, Fields = ? WHERE SourceID = ?',
            (new_name, new_blob, source_id)
        )
        applied += 1

    return applied


def main():
    parser = argparse.ArgumentParser(
        description='Fix miscellaneous 1930 Census source issues.'
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
    fixes = find_fixes(conn)

    print(f"Found {len(fixes)} fixable issues")
    print()

    if not fixes:
        print("No changes needed")
        return 0

    # Group by issue type for display
    by_issue: dict[str, list[Fix]] = {}
    for fix in fixes:
        key = f"{fix.field}: {fix.issue}"
        if key not in by_issue:
            by_issue[key] = []
        by_issue[key].append(fix)

    print("=== FIXES BY TYPE ===")
    for issue_type, issue_fixes in by_issue.items():
        print(f"\n{issue_type} ({len(issue_fixes)} fixes):")
        for fix in issue_fixes[:3]:
            print(f"  Source {fix.source_id}:")
            if fix.field == 'name':
                print(f"    Before: {fix.old_value[:70]}...")
                print(f"    After:  {fix.new_value[:70]}...")
            else:
                print(f"    Before: {fix.old_value[:60]}...")
                print(f"    After:  {fix.new_value[:60]}...")
        if len(issue_fixes) > 3:
            print(f"  ... and {len(issue_fixes) - 3} more")

    print()

    if args.dry_run:
        print("DRY RUN - No changes applied")
        return 0

    # Apply changes
    print("Applying changes...")
    applied = apply_fixes(conn, fixes)
    conn.commit()
    print(f"Updated {applied} sources")

    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
