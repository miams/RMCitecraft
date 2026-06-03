#!/usr/bin/env python3
"""
Fix 1920 Census source names to match 1930-1950 standardized format.

Target format: [ED X, sheet X, line X]

Handles multiple source patterns:
  1. [citing sheet X, family Y] → [ED ?, sheet X, line ?] (extract from footnote)
  2. [citing sheet X] → [ED ?, sheet X, line ?] (extract from footnote)
  3. [citing enumeration district (ED) X, sheet Y, line Z] → [ED X, sheet Y, line Z]
  4. [citing ED X, sheet Y, line Z] → [ED X, sheet Y, line Z]
  5. [ED X, sheet Y, line Z] → already correct

Also fixes:
  - State name typos (Illinoiis → Illinois, Frankllin → Franklin)
  - Removes "family" component (not used in 1930-1950 format)

Usage:
    python scripts/fix_1920_census_sources.py --dry-run    # Preview changes
    python scripts/fix_1920_census_sources.py              # Apply changes
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
class SourceFix:
    """Represents a fix to be applied to a source."""
    source_id: int
    old_name: str
    new_name: str
    fix_type: str
    details: str = ""


# State name typo corrections - ordered by specificity (longer matches first)
# Use word boundary matching to avoid partial replacements
STATE_TYPOS = {
    "Illinoiis": "Illinois",
    "Frankllin": "Franklin",
    "Frankin": "Franklin",
    "Pensylvania": "Pennsylvania",
    "Pennyslvania": "Pennsylvania",
    "Californa": "California",
    "Misouri": "Missouri",
    # Note: Don't include "Tennesse" as it's a substring of "Tennessee"
}


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


def extract_components_from_footnote(footnote: str) -> dict:
    """Extract ED, sheet, and line from footnote."""
    components = {"ed": None, "sheet": None, "line": None}

    # ED: "enumeration district (ED) X"
    if match := re.search(r'enumeration district \(ED\) (\d+(?:-\d+)?[A-Z]?)', footnote):
        components["ed"] = match.group(1)

    # Sheet: "sheet X" or "sheet XA/XB"
    if match := re.search(r'sheet (\d+[AB]?)', footnote, re.IGNORECASE):
        components["sheet"] = match.group(1)

    # Line: "line X"
    if match := re.search(r'line (\d+)', footnote, re.IGNORECASE):
        components["line"] = match.group(1)

    return components


def extract_components_from_name(name: str) -> dict:
    """Extract ED, sheet, and line from source name."""
    components = {"ed": None, "sheet": None, "line": None, "family": None}

    # Extract bracket content
    bracket_match = re.search(r'\[([^\]]+)\]', name)
    if not bracket_match:
        return components

    bracket = bracket_match.group(1)

    # ED patterns
    if match := re.search(r'ED (\d+(?:-\d+)?[A-Z]?)', bracket):
        components["ed"] = match.group(1)
    elif match := re.search(r'enumeration district \(ED\) (\d+(?:-\d+)?[A-Z]?)', bracket):
        components["ed"] = match.group(1)

    # Sheet
    if match := re.search(r'sheet (\d+[AB]?)', bracket, re.IGNORECASE):
        components["sheet"] = match.group(1)

    # Line
    if match := re.search(r'line (\d+)', bracket, re.IGNORECASE):
        components["line"] = match.group(1)

    # Family (to be removed)
    if match := re.search(r'family (\d+)', bracket, re.IGNORECASE):
        components["family"] = match.group(1)

    return components


def fix_state_typos(name: str) -> tuple[str, str | None]:
    """Fix state name typos. Returns (fixed_name, typo_found)."""
    for typo, correct in STATE_TYPOS.items():
        if typo in name:
            return name.replace(typo, correct), typo
    return name, None


def build_new_bracket(ed: str | None, sheet: str | None, line: str | None) -> str:
    """Build the standardized bracket format."""
    parts = []

    if ed:
        parts.append(f"ED {ed}")

    if sheet:
        parts.append(f"sheet {sheet}")

    if line:
        parts.append(f"line {line}")

    return f"[{', '.join(parts)}]" if parts else "[]"


def fix_source_name(
    source_id: int,
    name: str,
    footnote: str
) -> SourceFix | None:
    """
    Generate a fix for a source name.

    Returns SourceFix if changes needed, None otherwise.
    """
    original_name = name
    fix_details = []

    # Step 1: Fix state typos
    name, typo = fix_state_typos(name)
    if typo:
        fix_details.append(f"Fixed typo: {typo}")

    # Step 2: Extract components from source name
    name_components = extract_components_from_name(name)

    # Step 3: If missing ED or line, try to get from footnote
    if not name_components["ed"] or not name_components["line"]:
        fn_components = extract_components_from_footnote(footnote)

        if not name_components["ed"] and fn_components["ed"]:
            name_components["ed"] = fn_components["ed"]
            fix_details.append(f"Added ED {fn_components['ed']} from footnote")

        if not name_components["line"] and fn_components["line"]:
            name_components["line"] = fn_components["line"]
            fix_details.append(f"Added line {fn_components['line']} from footnote")

        # Sheet might also need to be extracted
        if not name_components["sheet"] and fn_components["sheet"]:
            name_components["sheet"] = fn_components["sheet"]
            fix_details.append(f"Added sheet {fn_components['sheet']} from footnote")

    # Step 4: Build new bracket
    new_bracket = build_new_bracket(
        name_components["ed"],
        name_components["sheet"],
        name_components["line"]
    )

    # Step 5: Replace old bracket with new bracket in name
    # Extract person name after bracket
    person_match = re.search(r'\]\s*(.+)$', name)
    person_name = person_match.group(1).strip() if person_match else ""

    # Extract prefix before bracket
    prefix_match = re.search(r'^(Fed Census: 1920, [^[]+)', name)
    prefix = prefix_match.group(1).strip() if prefix_match else ""

    if prefix and new_bracket:
        new_name = f"{prefix} {new_bracket} {person_name}".strip()

        # Clean up double spaces
        new_name = re.sub(r'\s+', ' ', new_name)

        # Check if actually changed
        if new_name != original_name:
            # Determine fix type
            if typo:
                fix_type = "typo_and_format"
            elif "Added ED" in str(fix_details) or "Added line" in str(fix_details):
                fix_type = "extracted_from_footnote"
            else:
                fix_type = "bracket_standardization"

            return SourceFix(
                source_id=source_id,
                old_name=original_name,
                new_name=new_name,
                fix_type=fix_type,
                details="; ".join(fix_details) if fix_details else "Standardized bracket format"
            )

    return None


def main():
    parser = argparse.ArgumentParser(
        description='Fix 1920 Census source names to standardized format.'
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
        '--verbose',
        '-v',
        action='store_true',
        help='Show all changes (not just samples)'
    )
    args = parser.parse_args()

    conn = connect_rmtree(str(args.db), read_only=args.dry_run)
    cursor = conn.cursor()

    print("=" * 70)
    print("FIX 1920 CENSUS SOURCE NAMES")
    print("=" * 70)

    # Get all 1920 census sources with their footnotes
    cursor.execute('''
        SELECT s.SourceID, s.Name, s.Fields
        FROM SourceTable s
        WHERE s.Name LIKE 'Fed Census: 1920,%'
        ORDER BY s.SourceID
    ''')

    sources = cursor.fetchall()
    print(f"Found {len(sources)} 1920 census sources\n")

    # Categorize and fix
    fixes_by_type = {
        "typo_and_format": [],
        "extracted_from_footnote": [],
        "bracket_standardization": [],
    }
    already_correct = 0
    unfixable = []

    for source_id, name, fields_blob in sources:
        footnote = extract_field_from_blob(fields_blob, "Footnote")

        fix = fix_source_name(source_id, name, footnote)

        if fix:
            fixes_by_type[fix.fix_type].append(fix)
        else:
            # Check if already in correct format
            if re.search(r'\[ED \d+(?:-\d+)?[A-Z]?, sheet \d+[AB]?, line \d+\]', name):
                already_correct += 1
            else:
                # Cannot be fixed (missing data in both name and footnote)
                unfixable.append((source_id, name))

    # Print summary
    total_fixes = sum(len(fixes) for fixes in fixes_by_type.values())
    print(f"Already correct: {already_correct}")
    print(f"Total fixes needed: {total_fixes}")
    print(f"Unfixable (missing data): {len(unfixable)}")
    print()

    for fix_type, fixes in fixes_by_type.items():
        if fixes:
            print(f"{fix_type}: {len(fixes)}")

    print()

    # Show sample changes by type
    for fix_type, fixes in fixes_by_type.items():
        if not fixes:
            continue

        print(f"\n{'='*60}")
        print(f"{fix_type.upper()} ({len(fixes)} sources)")
        print(f"{'='*60}")

        sample_size = len(fixes) if args.verbose else min(5, len(fixes))
        for fix in fixes[:sample_size]:
            print(f"\nSource {fix.source_id}:")
            print(f"  OLD: {fix.old_name}")
            print(f"  NEW: {fix.new_name}")
            if fix.details:
                print(f"  Details: {fix.details}")

        if not args.verbose and len(fixes) > 5:
            print(f"\n  ... and {len(fixes) - 5} more")

    # Show unfixable sources
    if unfixable:
        print(f"\n{'='*60}")
        print(f"UNFIXABLE ({len(unfixable)} sources)")
        print(f"{'='*60}")
        print("These sources are missing ED/line in both name and footnote:")
        for sid, name in unfixable[:10]:
            print(f"  {sid}: {name[:70]}...")
        if len(unfixable) > 10:
            print(f"  ... and {len(unfixable) - 10} more")

    # Apply fixes
    if not args.dry_run and total_fixes > 0:
        print(f"\nApplying {total_fixes} fixes...")
        for fixes in fixes_by_type.values():
            for fix in fixes:
                cursor.execute(
                    'UPDATE SourceTable SET Name = ? WHERE SourceID = ?',
                    (fix.new_name, fix.source_id)
                )
        conn.commit()
        print("Fixes applied successfully.")
    elif args.dry_run:
        print("\nDRY RUN - No changes applied")

    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
