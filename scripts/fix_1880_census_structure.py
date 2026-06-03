#!/usr/bin/env python3
"""
Fix 1880 Census Structure

Standardizes 1880 census source structure to match Evidence Explained style.

Changes:
1. Source Name: [citing enumeration district X, sheet Y] → [ED X, sheet Y, line Z]
2. Footnote: Add ED reference, fix title to "United States, Census, 1880"
3. Short Footnote: Add E.D. reference, add line number
4. Bibliography: Fix title to "United States, Census, 1880"

For sources missing line numbers, the line field is omitted.

Usage:
    python scripts/fix_1880_census_structure.py --dry-run    # Preview changes
    python scripts/fix_1880_census_structure.py              # Apply changes
    python scripts/fix_1880_census_structure.py --limit 10   # Process only 10
    python scripts/fix_1880_census_structure.py --source-id 272  # Process one
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rmcitecraft.database.connection import connect_rmtree


@dataclass
class SourceUpdate:
    """Pending update for a source."""
    source_id: int
    old_name: str
    new_name: str
    old_fields: str
    new_fields: str
    changes: list


def extract_field(fields_text: str, field_name: str) -> str:
    """Extract a field value from Fields XML."""
    pattern = rf'<Name>{field_name}</Name>\s*<Value>(.*?)</Value>'
    match = re.search(pattern, fields_text, re.DOTALL)
    return match.group(1) if match else ""


def update_field(fields_text: str, field_name: str, new_value: str) -> str:
    """Update a field value in Fields XML using safe replacement."""
    pattern = rf'(<Name>{re.escape(field_name)}</Name>\s*<Value>)(.*?)(</Value>)'

    def replacer(m):
        return m.group(1) + new_value + m.group(3)

    return re.sub(pattern, replacer, fields_text, flags=re.DOTALL)


def extract_ed_from_name(name: str) -> str | None:
    """Extract ED number from source name."""
    # Pattern: [citing enumeration district X, or [citing enumeration district ED X,
    match = re.search(r'\[citing enumeration district\s+(?:ED\s+)?(\d+)', name)
    if match:
        return match.group(1)
    # Also check for already-formatted [ED X,
    match = re.search(r'\[ED\s+(\d+)', name)
    if match:
        return match.group(1)
    # Check for (ED) X pattern in source name
    match = re.search(r'\[citing enumeration district \(ED\)\s+(\d+)', name)
    if match:
        return match.group(1)
    return None


def extract_sheet_from_name(name: str) -> str | None:
    """Extract sheet number from source name."""
    match = re.search(r'sheet\s+(\d+[A-D]?)', name, re.IGNORECASE)
    return match.group(1) if match else None


def extract_line_from_footnote(footnote: str) -> str | None:
    """Extract line number from footnote."""
    match = re.search(r'line\s+(\d+)', footnote, re.IGNORECASE)
    return match.group(1) if match else None


def extract_line_from_name(name: str) -> str | None:
    """Extract line number from source name if present."""
    match = re.search(r'line\s+(\d+)', name, re.IGNORECASE)
    return match.group(1) if match else None


def extract_person_name(name: str) -> str | None:
    """Extract person name from source name (after the last ])."""
    match = re.search(r'\]\s*(.+)$', name)
    return match.group(1).strip() if match else None


def extract_state_county(name: str) -> tuple[str, str] | None:
    """Extract state and county from source name."""
    match = re.search(r'Fed Census:\s*1880,\s*([^,]+),\s*([^\[]+)', name)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return None


def fix_source_name(name: str, ed: str, sheet: str, line: str | None, person: str) -> str:
    """Fix source name to standard format."""
    # Extract state and county
    location = extract_state_county(name)
    if not location:
        return name

    state, county = location

    # Build new format
    if line:
        bracket_content = f"ED {ed}, sheet {sheet}, line {line}"
    else:
        bracket_content = f"ED {ed}, sheet {sheet}"

    return f"Fed Census: 1880, {state}, {county} [{bracket_content}] {person}"


def fix_footnote(footnote: str, ed: str, line: str | None) -> str:
    """Fix footnote to standard format."""
    new_footnote = footnote

    # Fix title: various forms → "United States, Census, 1880"
    title_patterns = [
        (r'"1880 United States Federal Census,"', '"United States, Census, 1880,"'),
        (r'"United States Census, 1880,"', '"United States, Census, 1880,"'),
    ]
    for old, new in title_patterns:
        new_footnote = re.sub(old, new, new_footnote)

    # Add ED if missing - insert before "sheet"
    if 'enumeration district (ED)' not in new_footnote and ed:
        # Find where to insert - before "sheet X"
        new_footnote = re.sub(
            r'(,\s*)sheet\s+(\d+[A-D]?)',
            rf'\1enumeration district (ED) {ed}, sheet \2',
            new_footnote,
            count=1
        )

    # Add line number if we have it and it's missing
    if line and 'line ' not in new_footnote.lower():
        # Insert after sheet reference, before the comma and person name
        new_footnote = re.sub(
            r'(sheet\s+\d+[A-D]?)(,\s*)([A-Z])',
            rf'\1, line {line}\2\3',
            new_footnote,
            count=1
        )

    return new_footnote


def fix_short_footnote(short_fn: str, ed: str, line: str | None) -> str:
    """Fix short footnote to standard format."""
    new_short = short_fn

    # Add E.D. if missing - insert before "sheet"
    if 'E.D.' not in new_short and ed:
        new_short = re.sub(
            r'(,\s*)sheet\s+(\d+[A-D]?)',
            rf'\1E.D. {ed}, sheet \2',
            new_short,
            count=1
        )

    # Add line number if we have it and it's missing
    if line and 'line ' not in new_short.lower():
        # Insert after sheet reference, before person name
        new_short = re.sub(
            r'(sheet\s+\d+[A-D]?)(,\s*)([A-Z])',
            rf'\1, line {line}\2\3',
            new_short,
            count=1
        )

    return new_short


def fix_bibliography(bibliography: str) -> str:
    """Fix bibliography title."""
    new_bib = bibliography

    # Fix title patterns
    title_patterns = [
        (r'"1880 United States Federal Census"', '"United States, Census, 1880."'),
        (r'"United States Census, 1880"', '"United States, Census, 1880."'),
    ]
    for old, new in title_patterns:
        new_bib = re.sub(old, new, new_bib)

    return new_bib


def process_source(source_id: int, name: str, fields_text: str) -> SourceUpdate | None:
    """Process a single source and return update if needed."""
    changes = []

    # Extract data from source name
    ed = extract_ed_from_name(name)
    sheet = extract_sheet_from_name(name)
    person = extract_person_name(name)

    if not ed or not sheet or not person:
        return None

    # Extract fields
    footnote = extract_field(fields_text, "Footnote")
    short_fn = extract_field(fields_text, "ShortFootnote")
    bibliography = extract_field(fields_text, "Bibliography")

    # Get line number from footnote or source name if available
    line = extract_line_from_footnote(footnote) or extract_line_from_name(name)

    # Fix source name
    new_name = fix_source_name(name, ed, sheet, line, person)
    if new_name != name:
        changes.append("Source name: fixed format")

    # Fix fields
    new_fields = fields_text

    # Fix footnote
    if footnote:
        new_footnote = fix_footnote(footnote, ed, line)
        if new_footnote != footnote:
            new_fields = update_field(new_fields, "Footnote", new_footnote)
            changes.append("Footnote: fixed format/title")

    # Fix short footnote
    if short_fn:
        new_short = fix_short_footnote(short_fn, ed, line)
        if new_short != short_fn:
            new_fields = update_field(new_fields, "ShortFootnote", new_short)
            changes.append("ShortFootnote: added E.D./line")

    # Fix bibliography
    if bibliography:
        new_bib = fix_bibliography(bibliography)
        if new_bib != bibliography:
            new_fields = update_field(new_fields, "Bibliography", new_bib)
            changes.append("Bibliography: fixed title")

    # Only return update if something changed
    if not changes:
        return None

    return SourceUpdate(
        source_id=source_id,
        old_name=name,
        new_name=new_name,
        old_fields=fields_text,
        new_fields=new_fields,
        changes=changes
    )


def main():
    parser = argparse.ArgumentParser(
        description='Fix 1880 census structure',
        formatter_class=argparse.RawDescriptionHelpFormatter
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
        '--limit',
        type=int,
        default=0,
        help='Limit number of sources to process (0 = all)'
    )
    parser.add_argument(
        '--source-id',
        type=int,
        default=0,
        help='Process only specific source ID'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed changes'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("FIX 1880 CENSUS STRUCTURE")
    print("=" * 70)
    print()
    print(f"Database: {args.db}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY CHANGES'}")
    if args.limit > 0:
        print(f"Limit: {args.limit} sources")
    if args.source_id > 0:
        print(f"Source ID: {args.source_id}")
    print()

    # Connect to database
    conn = connect_rmtree(str(args.db), read_only=args.dry_run)
    cursor = conn.cursor()

    # Get 1880 census sources
    if args.source_id > 0:
        cursor.execute('''
            SELECT SourceID, Name, CAST(Fields AS TEXT)
            FROM SourceTable
            WHERE SourceID = ? AND Name LIKE 'Fed Census: 1880%'
        ''', (args.source_id,))
    else:
        cursor.execute('''
            SELECT SourceID, Name, CAST(Fields AS TEXT)
            FROM SourceTable
            WHERE Name LIKE 'Fed Census: 1880%'
            ORDER BY SourceID
        ''')

    sources = cursor.fetchall()
    print(f"Found {len(sources)} 1880 census sources")
    print()

    # Process sources
    updates = []
    skipped = 0
    with_line = 0
    without_line = 0

    for source_id, name, fields_text in sources:
        if args.limit > 0 and len(updates) >= args.limit:
            break

        update = process_source(source_id, name, fields_text)
        if update:
            updates.append(update)
            # Count line number status
            if 'line' in update.new_name:
                with_line += 1
            else:
                without_line += 1
        else:
            skipped += 1

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Sources to update: {len(updates)}")
    print(f"  - With line numbers: {with_line}")
    print(f"  - Without line numbers: {without_line}")
    print(f"Skipped (no changes needed or couldn't parse): {skipped}")
    print()

    if updates:
        # Show preview
        print("=" * 70)
        print(f"PREVIEW OF CHANGES (first {min(5, len(updates))})")
        print("=" * 70)

        for update in updates[:5]:
            print(f"\nSource {update.source_id}:")
            print(f"  OLD: {update.old_name}")
            print(f"  NEW: {update.new_name}")
            print(f"  Changes: {', '.join(update.changes)}")

        if len(updates) > 5:
            print(f"\n... and {len(updates) - 5} more")

        # Apply changes
        if not args.dry_run:
            print()
            print("=" * 70)
            print("APPLYING CHANGES")
            print("=" * 70)

            for update in updates:
                # Update source name
                cursor.execute(
                    "UPDATE SourceTable SET Name = ? WHERE SourceID = ?",
                    (update.new_name, update.source_id)
                )

                # Update fields
                if update.new_fields != update.old_fields:
                    cursor.execute(
                        "UPDATE SourceTable SET Fields = ? WHERE SourceID = ?",
                        (update.new_fields.encode('utf-8'), update.source_id)
                    )

            conn.commit()
            print(f"Updated {len(updates)} sources")

            # Verify a sample
            print()
            print("Verification (first 3 updated sources):")
            for update in updates[:3]:
                cursor.execute(
                    "SELECT Name FROM SourceTable WHERE SourceID = ?",
                    (update.source_id,)
                )
                row = cursor.fetchone()
                if row:
                    print(f"  Source {update.source_id}: {row[0]}")
        else:
            print()
            print("=" * 70)
            print("DRY RUN COMPLETE - No changes made")
            print("Run without --dry-run to apply changes")
            print("=" * 70)

    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
