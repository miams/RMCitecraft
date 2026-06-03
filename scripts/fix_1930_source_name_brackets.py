#!/usr/bin/env python3
"""
Standardize 1930 Census source name brackets to match 1940/1950 format.

Changes:
  FROM: [citing enumeration district (ED) 29, sheet 7A, family 174, line 1]
  TO:   [ED 29, sheet 7A, line 1]

Specifically:
  1. Replace "[citing enumeration district (ED) " with "[ED "
  2. Remove "family XXX, " component

Usage:
    python scripts/fix_1930_source_name_brackets.py --dry-run    # Preview changes
    python scripts/fix_1930_source_name_brackets.py              # Apply changes
"""

import argparse
import re
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rmcitecraft.database.connection import connect_rmtree


def transform_bracket(bracket_content: str) -> str | None:
    """
    Transform bracket content from 1930 format to 1940/1950 format.

    Args:
        bracket_content: Content inside brackets (without the brackets)

    Returns:
        Transformed content, or None if no changes needed
    """
    original = bracket_content

    # Step 1: Replace "citing enumeration district (ED) " with "ED "
    if "citing enumeration district (ED) " in bracket_content:
        bracket_content = bracket_content.replace(
            "citing enumeration district (ED) ", "ED "
        )

    # Step 2: Remove "family XXX" component (handles all variations)
    # Pattern A: "family XXX, " (family before line)
    bracket_content = re.sub(r"family \d+, ", "", bracket_content)
    # Pattern B: ", family XXX" (family at end, after line)
    bracket_content = re.sub(r", family \d+$", "", bracket_content)
    # Pattern C: "family , " (empty family value before line)
    bracket_content = re.sub(r"family , ", "", bracket_content)
    # Pattern D: ", family " or ", family]" (empty family at end)
    bracket_content = re.sub(r", family\s*$", "", bracket_content)
    # Pattern E: ",family XXX" (missing space after comma)
    bracket_content = re.sub(r",family \d+", "", bracket_content)
    # Pattern F: "family XXXED " (corrupted - family runs into duplicate ED content)
    bracket_content = re.sub(r"family \d+ED .*$", "", bracket_content)

    # Step 3: Clean up any trailing ", " left over
    bracket_content = re.sub(r",\s*$", "", bracket_content)

    # Return None if no changes were made
    if bracket_content == original:
        return None

    return bracket_content


def fix_source_name(name: str) -> tuple[str | None, str, str]:
    """
    Fix a source name's bracket format.

    Args:
        name: Full source name

    Returns:
        Tuple of (new_name or None if no change, old_bracket, new_bracket)
    """
    # Extract bracket content
    match = re.search(r'\[([^\]]+)\]', name)
    if not match:
        return None, "", ""

    old_bracket = match.group(1)
    new_bracket = transform_bracket(old_bracket)

    if new_bracket is None:
        return None, old_bracket, old_bracket

    # Replace in the full name
    new_name = name.replace(f"[{old_bracket}]", f"[{new_bracket}]")

    return new_name, old_bracket, new_bracket


def main():
    parser = argparse.ArgumentParser(
        description='Standardize 1930 Census source name brackets to 1940/1950 format.'
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

    conn = connect_rmtree(str(args.db), read_only=False)
    cursor = conn.cursor()

    print("=" * 70)
    print("STANDARDIZE 1930 CENSUS SOURCE NAME BRACKETS")
    print("=" * 70)

    # Get all 1930 census sources
    cursor.execute('''
        SELECT SourceID, Name
        FROM SourceTable
        WHERE Name LIKE 'Fed Census: 1930,%'
        ORDER BY SourceID
    ''')

    sources = cursor.fetchall()
    print(f"Found {len(sources)} 1930 census sources\n")

    changes = []
    already_correct = 0

    for source_id, name in sources:
        new_name, old_bracket, new_bracket = fix_source_name(name)

        if new_name:
            changes.append({
                'source_id': source_id,
                'old_name': name,
                'new_name': new_name,
                'old_bracket': old_bracket,
                'new_bracket': new_bracket,
            })
        else:
            already_correct += 1

    print(f"Sources needing update: {len(changes)}")
    print(f"Sources already correct: {already_correct}")

    if changes:
        print(f"\nSample changes (first 10):")
        print("-" * 70)
        for change in changes[:10]:
            print(f"Source {change['source_id']}:")
            print(f"  OLD: [{change['old_bracket']}]")
            print(f"  NEW: [{change['new_bracket']}]")

        if not args.dry_run:
            print(f"\nApplying {len(changes)} changes...")
            for change in changes:
                cursor.execute(
                    'UPDATE SourceTable SET Name = ? WHERE SourceID = ?',
                    (change['new_name'], change['source_id'])
                )
            conn.commit()
            print("Changes applied successfully.")
        else:
            print("\nDRY RUN - No changes applied")

    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
