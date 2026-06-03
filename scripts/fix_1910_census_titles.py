#!/usr/bin/env python3
"""
Fix 1910 Census source titles to match FamilySearch standard format.

Problem: 1910 Census sources have inconsistent title formats that don't match
the standard FamilySearch format used for other census years.

Fixes applied:
  Footnote:
    FROM: "United States Census, 1910,"
    TO:   "United States, Census, 1910,"

  Bibliography:
    FROM: "1910 United States Federal Census."
      OR: "United States Census, 1910"
      OR: "United States Census, 1910,"
    TO:   "United States, Census, 1910."

Also fixes year typos (1920 -> 1910 in 1910 sources).

Usage:
    python scripts/fix_1910_census_titles.py --dry-run    # Preview changes
    python scripts/fix_1910_census_titles.py              # Apply changes
"""

import argparse
import re
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rmcitecraft.database.connection import connect_rmtree

# Target titles (FamilySearch standard format)
TARGET_FOOTNOTE_TITLE = "United States, Census, 1910,"
TARGET_BIBLIOGRAPHY_TITLE = "United States, Census, 1910."


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


def fix_footnote_title(footnote: str) -> tuple[str | None, str]:
    """
    Fix footnote title to standard format.

    Returns:
        Tuple of (fixed_text or None if no change, description of change)
    """
    original = footnote

    # Pattern 1: "United States Census, 1910," -> "United States, Census, 1910,"
    footnote = re.sub(
        r'&quot;United States Census, 1910,&quot;',
        f'&quot;{TARGET_FOOTNOTE_TITLE}&quot;',
        footnote
    )
    footnote = re.sub(
        r'"United States Census, 1910,"',
        f'"{TARGET_FOOTNOTE_TITLE}"',
        footnote
    )

    # Pattern 2: Fix year typo "1920" -> "1910" (in 1910 sources)
    footnote = re.sub(
        r'&quot;United States Census, 1920,&quot;',
        f'&quot;{TARGET_FOOTNOTE_TITLE}&quot;',
        footnote
    )
    footnote = re.sub(
        r'"United States Census, 1920,"',
        f'"{TARGET_FOOTNOTE_TITLE}"',
        footnote
    )

    if footnote != original:
        return footnote, 'Fixed footnote title to standard format'

    return None, ""


def fix_bibliography_title(bibliography: str) -> tuple[str | None, str]:
    """
    Fix bibliography title to standard format.

    Returns:
        Tuple of (fixed_text or None if no change, description of change)
    """
    original = bibliography

    # Pattern 1: "1910 United States Federal Census." -> "United States, Census, 1910."
    bibliography = re.sub(
        r'&quot;1910 United States Federal Census\.&quot;',
        f'&quot;{TARGET_BIBLIOGRAPHY_TITLE}&quot;',
        bibliography
    )
    bibliography = re.sub(
        r'"1910 United States Federal Census\."',
        f'"{TARGET_BIBLIOGRAPHY_TITLE}"',
        bibliography
    )

    # Pattern 2: "United States Census, 1910" (no trailing punctuation) -> add period
    bibliography = re.sub(
        r'&quot;United States Census, 1910&quot;',
        f'&quot;{TARGET_BIBLIOGRAPHY_TITLE}&quot;',
        bibliography
    )
    bibliography = re.sub(
        r'"United States Census, 1910"',
        f'"{TARGET_BIBLIOGRAPHY_TITLE}"',
        bibliography
    )

    # Pattern 3: "United States Census, 1910," (trailing comma) -> fix to period
    bibliography = re.sub(
        r'&quot;United States Census, 1910,&quot;',
        f'&quot;{TARGET_BIBLIOGRAPHY_TITLE}&quot;',
        bibliography
    )
    bibliography = re.sub(
        r'"United States Census, 1910,"',
        f'"{TARGET_BIBLIOGRAPHY_TITLE}"',
        bibliography
    )

    # Pattern 4: Fix year typo "1920" -> "1910"
    bibliography = re.sub(
        r'&quot;United States Census, 1920&quot;',
        f'&quot;{TARGET_BIBLIOGRAPHY_TITLE}&quot;',
        bibliography
    )
    bibliography = re.sub(
        r'"United States Census, 1920"',
        f'"{TARGET_BIBLIOGRAPHY_TITLE}"',
        bibliography
    )

    if bibliography != original:
        return bibliography, 'Fixed bibliography title to standard format'

    return None, ""


def main():
    parser = argparse.ArgumentParser(
        description='Fix 1910 Census source titles to standard FamilySearch format.'
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
    print("FIX 1910 CENSUS SOURCE TITLES")
    print("=" * 70)
    print()
    print(f'Target footnote title:     "{TARGET_FOOTNOTE_TITLE}"')
    print(f'Target bibliography title: "{TARGET_BIBLIOGRAPHY_TITLE}"')
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
        bibliography = extract_field_from_blob(fields_blob, "Bibliography")

        fixed_fn, desc_fn = fix_footnote_title(footnote)
        fixed_bib, desc_bib = fix_bibliography_title(bibliography)

        if fixed_fn or fixed_bib:
            new_fields = fields_blob
            if fixed_fn:
                new_fields = update_field_in_blob(new_fields, "Footnote", fixed_fn)
            if fixed_bib:
                new_fields = update_field_in_blob(new_fields, "Bibliography", fixed_bib)

            changes.append({
                'source_id': source_id,
                'name': name,
                'new_fields': new_fields,
                'fixed_fn': bool(fixed_fn),
                'fixed_bib': bool(fixed_bib),
            })
        else:
            already_correct += 1

    print(f"Sources needing fix: {len(changes)}")
    print(f"Sources already correct: {already_correct}")
    print()

    if changes:
        fn_fixes = sum(1 for c in changes if c['fixed_fn'])
        bib_fixes = sum(1 for c in changes if c['fixed_bib'])
        print(f"Footnote title fixes: {fn_fixes}")
        print(f"Bibliography title fixes: {bib_fixes}")
        print()

        if args.verbose:
            print("Sources to fix:")
            print("-" * 70)
            for change in changes[:20]:
                fixes = []
                if change['fixed_fn']:
                    fixes.append("footnote")
                if change['fixed_bib']:
                    fixes.append("bibliography")
                print(f"  {change['source_id']}: {change['name'][:55]}... ({', '.join(fixes)})")
            if len(changes) > 20:
                print(f"  ... and {len(changes) - 20} more")
            print()

        if not args.dry_run:
            print(f"Applying {len(changes)} fixes...")
            for change in changes:
                cursor.execute(
                    'UPDATE SourceTable SET Fields = ? WHERE SourceID = ?',
                    (change['new_fields'], change['source_id'])
                )
            conn.commit()
            print(f"Applied fixes to {len(changes)} sources.")
        else:
            print("DRY RUN - No changes applied")
            print("Run without --dry-run to apply changes.")

    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
