#!/usr/bin/env python3
"""
Fix 1910 Census empty line references in footnotes.

Problem: FamilySearch does not extract line numbers for 1910 Census, but some
footnotes contain ", line " with no actual line number, leaving an awkward
trailing comma and empty reference.

Pattern to fix:
  FROM: "sheet 4A, line , Richard James Iams"
  TO:   "sheet 4A, Richard James Iams"

Usage:
    python scripts/fix_1910_line_reference.py --dry-run    # Preview changes
    python scripts/fix_1910_line_reference.py              # Apply changes
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


def fix_empty_line_reference(text: str) -> tuple[str | None, str]:
    """
    Remove empty line references from footnote text.

    Patterns fixed:
    - ", line ," -> ","
    - ", line " (at end before person name) -> ", "

    Returns:
        Tuple of (fixed_text or None if no change, description of change)
    """
    original = text

    # Pattern: ", line ," -> ","
    # Handles: "sheet 4A, line , Richard" -> "sheet 4A, Richard"
    text = re.sub(r',\s*line\s*,', ',', text)

    # Pattern: ", line " followed by a capital letter (person's name)
    # Handles: "sheet 4A, line Richard" -> "sheet 4A, Richard"
    text = re.sub(r',\s*line\s+([A-Z])', r', \1', text)

    if text != original:
        return text, 'Removed empty "line" reference'

    return None, ""


def main():
    parser = argparse.ArgumentParser(
        description='Fix empty line references in 1910 Census footnotes.'
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

    print("=" * 70)
    print("FIX 1910 CENSUS EMPTY LINE REFERENCES")
    print("=" * 70)
    print()
    print('Issue: Some 1910 footnotes contain ", line " with no line number')
    print('FamilySearch does not extract line numbers for the 1910 Census.')
    print()

    conn = connect_rmtree(str(args.db), read_only=args.dry_run)
    cursor = conn.cursor()

    # Get all 1910 census sources
    cursor.execute('''
        SELECT s.SourceID, s.Name, s.Fields
        FROM SourceTable s
        WHERE s.Name LIKE 'Fed Census: 1910,%'
        ORDER BY s.SourceID
    ''')

    sources = cursor.fetchall()
    print(f"Found {len(sources)} 1910 census sources")
    print()

    changes = []
    already_correct = 0

    for source_id, name, fields_blob in sources:
        footnote = extract_field_from_blob(fields_blob, "Footnote")
        short_footnote = extract_field_from_blob(fields_blob, "ShortFootnote")

        fixed_fn, desc_fn = fix_empty_line_reference(footnote)
        fixed_short, desc_short = fix_empty_line_reference(short_footnote)

        if fixed_fn or fixed_short:
            new_fields = fields_blob
            if fixed_fn:
                new_fields = update_field_in_blob(new_fields, "Footnote", fixed_fn)
            if fixed_short:
                new_fields = update_field_in_blob(new_fields, "ShortFootnote", fixed_short)

            changes.append({
                'source_id': source_id,
                'name': name,
                'old_footnote': footnote,
                'new_footnote': fixed_fn or footnote,
                'old_short': short_footnote,
                'new_short': fixed_short or short_footnote,
                'new_fields': new_fields,
                'fixed_fn': bool(fixed_fn),
                'fixed_short': bool(fixed_short),
            })
        else:
            already_correct += 1

    print(f"Sources needing fix: {len(changes)}")
    print(f"Sources already correct: {already_correct}")
    print()

    if changes:
        fn_fixes = sum(1 for c in changes if c['fixed_fn'])
        short_fixes = sum(1 for c in changes if c['fixed_short'])
        print(f"Footnote fixes: {fn_fixes}")
        print(f"Short footnote fixes: {short_fixes}")
        print()

        if args.verbose:
            print("All changes:")
            print("-" * 70)
            for change in changes:
                print(f"Source {change['source_id']}: {change['name'][:60]}...")
                if change['fixed_fn']:
                    # Show the relevant portion
                    old_match = re.search(r'sheet [^,]+,\s*line\s*[^,;]*', change['old_footnote'])
                    new_match = re.search(r'sheet [^,]+,\s*[A-Z]', change['new_footnote'])
                    if old_match:
                        print(f"  Footnote OLD: ...{old_match.group()}...")
                    if new_match:
                        print(f"  Footnote NEW: ...{new_match.group()}...")
                print()
        else:
            print("Sample changes (first 5):")
            print("-" * 70)
            for change in changes[:5]:
                print(f"Source {change['source_id']}: {change['name'][:60]}...")
                if change['fixed_fn']:
                    old_match = re.search(r'sheet [^,]+,\s*line\s*[^,;]*', change['old_footnote'])
                    if old_match:
                        print(f"  OLD: ...{old_match.group()}...")
                        # Show what it becomes
                        new_portion = change['new_footnote'][old_match.start():old_match.start()+30]
                        print(f"  NEW: ...{new_portion}...")
                print()
            if len(changes) > 5:
                print(f"... and {len(changes) - 5} more")
                print()

        if not args.dry_run:
            print(f"Applying {len(changes)} fixes...")
            for change in changes:
                cursor.execute(
                    'UPDATE SourceTable SET Fields = ? WHERE SourceID = ?',
                    (change['new_fields'], change['source_id'])
                )
            conn.commit()
            print(f"Applied {len(changes)} fixes.")
        else:
            print("DRY RUN - No changes applied")
            print("Run without --dry-run to apply changes.")

    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
