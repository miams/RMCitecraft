#!/usr/bin/env python3
"""Fix 1880 Census citation formatting issues in RootsMagic database.

This script corrects formatting issues in 1880 Census citations:
1. Postal code state abbreviations (e.g., "MO") → full names or traditional abbrev
2. All-caps state names (e.g., "CALIFORNIA") → proper case
3. All-caps localities (e.g., "KNOXVILLE") → proper case

Usage:
    # Dry run (show changes without applying)
    python scripts/fix_1880_census_formatting.py --dry-run

    # Apply fixes
    python scripts/fix_1880_census_formatting.py --apply
"""

import argparse
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from loguru import logger

from rmcitecraft.database.connection import connect_rmtree

# State name mappings
# Postal codes → Full names (for Footnote and Bibliography)
POSTAL_TO_FULL = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}

# Postal codes → Traditional abbreviations (for Short Footnote per Evidence Explained)
POSTAL_TO_TRADITIONAL = {
    "AL": "Ala.", "AK": "Alaska", "AZ": "Ariz.", "AR": "Ark.",
    "CA": "Calif.", "CO": "Colo.", "CT": "Conn.", "DE": "Del.",
    "FL": "Fla.", "GA": "Ga.", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Ill.", "IN": "Ind.", "IA": "Iowa", "KS": "Kans.",
    "KY": "Ky.", "LA": "La.", "ME": "Maine", "MD": "Md.",
    "MA": "Mass.", "MI": "Mich.", "MN": "Minn.", "MS": "Miss.",
    "MO": "Mo.", "MT": "Mont.", "NE": "Nebr.", "NV": "Nev.",
    "NH": "N.H.", "NJ": "N.J.", "NM": "N.Mex.", "NY": "N.Y.",
    "NC": "N.C.", "ND": "N.Dak.", "OH": "Ohio", "OK": "Okla.",
    "OR": "Oreg.", "PA": "Pa.", "RI": "R.I.", "SC": "S.C.",
    "SD": "S.Dak.", "TN": "Tenn.", "TX": "Tex.", "UT": "Utah",
    "VT": "Vt.", "VA": "Va.", "WA": "Wash.", "WV": "W.Va.",
    "WI": "Wis.", "WY": "Wyo.", "DC": "D.C.",
}

# Full state names → Traditional abbreviations (for Short Footnote)
FULL_TO_TRADITIONAL = {
    "Alabama": "Ala.", "Alaska": "Alaska", "Arizona": "Ariz.", "Arkansas": "Ark.",
    "California": "Calif.", "Colorado": "Colo.", "Connecticut": "Conn.", "Delaware": "Del.",
    "Florida": "Fla.", "Georgia": "Ga.", "Hawaii": "Hawaii", "Idaho": "Idaho",
    "Illinois": "Ill.", "Indiana": "Ind.", "Iowa": "Iowa", "Kansas": "Kans.",
    "Kentucky": "Ky.", "Louisiana": "La.", "Maine": "Maine", "Maryland": "Md.",
    "Massachusetts": "Mass.", "Michigan": "Mich.", "Minnesota": "Minn.", "Mississippi": "Miss.",
    "Missouri": "Mo.", "Montana": "Mont.", "Nebraska": "Nebr.", "Nevada": "Nev.",
    "New Hampshire": "N.H.", "New Jersey": "N.J.", "New Mexico": "N.Mex.", "New York": "N.Y.",
    "North Carolina": "N.C.", "North Dakota": "N.Dak.", "Ohio": "Ohio", "Oklahoma": "Okla.",
    "Oregon": "Oreg.", "Pennsylvania": "Pa.", "Rhode Island": "R.I.", "South Carolina": "S.C.",
    "South Dakota": "S.Dak.", "Tennessee": "Tenn.", "Texas": "Tex.", "Utah": "Utah",
    "Vermont": "Vt.", "Virginia": "Va.", "Washington": "Wash.", "West Virginia": "W.Va.",
    "Wisconsin": "Wis.", "Wyoming": "Wyo.", "District of Columbia": "D.C.",
}

# Build reverse lookup for all-caps state names
ALL_CAPS_TO_PROPER = {name.upper(): name for name in POSTAL_TO_FULL.values()}


@dataclass
class CitationFix:
    """Represents a fix to be applied to a citation."""
    source_id: int
    source_name: str
    field_name: str
    original: str
    fixed: str
    changes: list[str]


def fix_postal_codes_full(text: str) -> tuple[str, list[str]]:
    """Replace postal code abbreviations with full state names.

    Used for Footnote and Bibliography fields.
    """
    changes = []
    result = text

    # Pattern: "County, XX," where XX is a postal code
    for postal, full in POSTAL_TO_FULL.items():
        # Match postal code after "County, " and before comma or other punctuation
        pattern = rf'(County,\s*){postal}([,\s])'
        if re.search(pattern, result):
            result = re.sub(pattern, rf'\1{full}\2', result)
            changes.append(f"'{postal}' → '{full}'")

    # Also fix in Bibliography format: "U.S. XX. County"
    for postal, full in POSTAL_TO_FULL.items():
        pattern = rf'(U\.S\.\s*){postal}(\.\s)'
        if re.search(pattern, result):
            result = re.sub(pattern, rf'\1{full}\2', result)
            changes.append(f"'U.S. {postal}.' → 'U.S. {full}.'")

    return result, changes


def fix_postal_codes_traditional(text: str) -> tuple[str, list[str]]:
    """Replace postal code abbreviations with traditional abbreviations.

    Used for Short Footnote field.
    """
    changes = []
    result = text

    # Pattern: "Co., XX," where XX is a postal code
    for postal, trad in POSTAL_TO_TRADITIONAL.items():
        pattern = rf'(Co\.,\s*){postal}([,\s])'
        if re.search(pattern, result):
            result = re.sub(pattern, rf'\1{trad}\2', result)
            changes.append(f"'{postal}' → '{trad}'")

    return result, changes


def fix_all_caps_states(text: str) -> tuple[str, list[str]]:
    """Replace ALL CAPS state names with proper case."""
    changes = []
    result = text

    for caps, proper in ALL_CAPS_TO_PROPER.items():
        # Only match as whole words (word boundaries)
        pattern = rf'\b{caps}\b'
        if re.search(pattern, result):
            result = re.sub(pattern, proper, result)
            changes.append(f"'{caps}' → '{proper}'")

    return result, changes


def fix_all_caps_words(text: str) -> tuple[str, list[str]]:
    """Replace ALL CAPS words (localities) with title case.

    Excludes known abbreviations like ED, NARA, FHL, and content inside URLs.
    """
    changes = []

    # Split text into URL and non-URL parts
    # URLs contain familysearch.org or ark:/
    url_pattern = r'(https?://[^\s<>]+|ark:/[^\s<>]+)'

    parts = re.split(url_pattern, text)
    result_parts = []

    # Known abbreviations to preserve
    preserve = {'ED', 'NARA', 'FHL', 'USA'}

    for i, part in enumerate(parts):
        # Skip URL parts (odd indices after split with capturing group)
        if 'familysearch.org' in part or 'ark:/' in part:
            result_parts.append(part)
            continue

        # Process non-URL parts
        processed = part

        # Find all-caps words (3+ letters) in this part
        caps_words = re.findall(r'\b([A-Z]{3,})\b', processed)

        for word in set(caps_words):
            if word in preserve:
                continue
            if word in ALL_CAPS_TO_PROPER:
                continue  # Already handled by fix_all_caps_states

            # Convert to title case
            title_word = word.title()
            processed = re.sub(rf'\b{word}\b', title_word, processed)
            changes.append(f"'{word}' → '{title_word}'")

        result_parts.append(processed)

    return ''.join(result_parts), changes


def fix_footnote(text: str) -> tuple[str, list[str]]:
    """Fix a Footnote field."""
    all_changes = []
    result = text

    # Fix postal codes → full names
    result, changes = fix_postal_codes_full(result)
    all_changes.extend(changes)

    # Fix all-caps state names
    result, changes = fix_all_caps_states(result)
    all_changes.extend(changes)

    # Fix all-caps localities
    result, changes = fix_all_caps_words(result)
    all_changes.extend(changes)

    return result, all_changes


def fix_short_footnote(text: str) -> tuple[str, list[str]]:
    """Fix a Short Footnote field."""
    all_changes = []
    result = text

    # Fix postal codes → traditional abbreviations
    result, changes = fix_postal_codes_traditional(result)
    all_changes.extend(changes)

    # Fix all-caps state names → traditional abbreviations
    for caps, proper in ALL_CAPS_TO_PROPER.items():
        if caps in result:
            trad = FULL_TO_TRADITIONAL.get(proper, proper)
            result = re.sub(rf'\b{caps}\b', trad, result)
            all_changes.append(f"'{caps}' → '{trad}'")

    # Fix all-caps localities
    result, changes = fix_all_caps_words(result)
    all_changes.extend(changes)

    return result, all_changes


def fix_bibliography(text: str) -> tuple[str, list[str]]:
    """Fix a Bibliography field."""
    all_changes = []
    result = text

    # Fix postal codes → full names
    result, changes = fix_postal_codes_full(result)
    all_changes.extend(changes)

    # Fix all-caps state names
    result, changes = fix_all_caps_states(result)
    all_changes.extend(changes)

    # Fix all-caps localities
    result, changes = fix_all_caps_words(result)
    all_changes.extend(changes)

    return result, all_changes


def parse_fields_xml(fields_blob: bytes | str) -> dict[str, str]:
    """Parse the Fields XML blob into a dictionary."""
    if isinstance(fields_blob, bytes):
        fields_xml = fields_blob.decode('utf-8')
    else:
        fields_xml = fields_blob

    result = {}

    # Extract each field
    for field_name in ['Footnote', 'ShortFootnote', 'Bibliography']:
        pattern = rf'<Name>{field_name}</Name>\s*<Value>(.*?)</Value>'
        match = re.search(pattern, fields_xml, re.DOTALL)
        if match:
            result[field_name] = match.group(1)

    return result


def rebuild_fields_xml(original_xml: str, updates: dict[str, str]) -> str:
    """Rebuild the Fields XML with updated values."""
    result = original_xml

    for field_name, new_value in updates.items():
        # Find and replace the value for this field
        pattern = rf'(<Name>{field_name}</Name>\s*<Value>)(.*?)(</Value>)'

        # Use a function for replacement to avoid regex escaping issues
        # Capture new_value in default argument to avoid closure issues
        def replacer(match, value=new_value):
            return match.group(1) + value + match.group(3)

        result = re.sub(pattern, replacer, result, flags=re.DOTALL)

    return result


def analyze_and_fix_source(source_id: int, source_name: str, fields_blob: bytes | str) -> list[CitationFix]:
    """Analyze a source and return list of fixes needed."""
    fixes = []

    fields = parse_fields_xml(fields_blob)

    # Fix Footnote
    if 'Footnote' in fields:
        original = fields['Footnote']
        fixed, changes = fix_footnote(original)
        if changes:
            fixes.append(CitationFix(
                source_id=source_id,
                source_name=source_name,
                field_name='Footnote',
                original=original,
                fixed=fixed,
                changes=changes
            ))

    # Fix Short Footnote
    if 'ShortFootnote' in fields:
        original = fields['ShortFootnote']
        fixed, changes = fix_short_footnote(original)
        if changes:
            fixes.append(CitationFix(
                source_id=source_id,
                source_name=source_name,
                field_name='ShortFootnote',
                original=original,
                fixed=fixed,
                changes=changes
            ))

    # Fix Bibliography
    if 'Bibliography' in fields:
        original = fields['Bibliography']
        fixed, changes = fix_bibliography(original)
        if changes:
            fixes.append(CitationFix(
                source_id=source_id,
                source_name=source_name,
                field_name='Bibliography',
                original=original,
                fixed=fixed,
                changes=changes
            ))

    return fixes


def main():
    parser = argparse.ArgumentParser(description='Fix 1880 Census citation formatting')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without applying')
    parser.add_argument('--apply', action='store_true', help='Apply fixes to database')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed changes')
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("Please specify --dry-run or --apply")
        print("Use --dry-run to preview changes, --apply to make changes")
        return

    # Connect to database
    db_path = 'data/Iiams.rmtree'
    read_only = args.dry_run
    conn = connect_rmtree(db_path, read_only=read_only)
    cursor = conn.cursor()

    print(f"{'DRY RUN - ' if args.dry_run else ''}Analyzing 1880 Census sources...")
    print()

    # Get all 1880 Census sources with Fields
    cursor.execute('''
        SELECT SourceID, Name, Fields
        FROM SourceTable
        WHERE Name LIKE "Fed Census: 1880,%"
        AND Fields IS NOT NULL
        AND length(Fields) > 50
        ORDER BY Name
    ''')

    sources = cursor.fetchall()
    print(f"Found {len(sources)} sources with formatted citations")
    print()

    all_fixes = []
    sources_with_fixes = set()

    for source_id, source_name, fields_blob in sources:
        fixes = analyze_and_fix_source(source_id, source_name, fields_blob)
        if fixes:
            all_fixes.extend(fixes)
            sources_with_fixes.add(source_id)

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Sources needing fixes: {len(sources_with_fixes)}")
    print(f"Total field fixes: {len(all_fixes)}")
    print()

    # Count by field type
    footnote_fixes = [f for f in all_fixes if f.field_name == 'Footnote']
    short_fixes = [f for f in all_fixes if f.field_name == 'ShortFootnote']
    bib_fixes = [f for f in all_fixes if f.field_name == 'Bibliography']

    print(f"  Footnote fixes: {len(footnote_fixes)}")
    print(f"  Short Footnote fixes: {len(short_fixes)}")
    print(f"  Bibliography fixes: {len(bib_fixes)}")
    print()

    # Show sample fixes
    if args.verbose or args.dry_run:
        print("=" * 60)
        print("SAMPLE FIXES (first 10 sources)")
        print("=" * 60)

        shown_sources = set()
        for fix in all_fixes:
            if fix.source_id in shown_sources:
                continue
            if len(shown_sources) >= 10:
                break
            shown_sources.add(fix.source_id)

            print(f"\nSource {fix.source_id}: {fix.source_name[:60]}...")

            # Show all fixes for this source
            source_fixes = [f for f in all_fixes if f.source_id == fix.source_id]
            for sf in source_fixes:
                print(f"  {sf.field_name}:")
                print(f"    Changes: {', '.join(sf.changes)}")
                if args.verbose:
                    print(f"    Before: {sf.original[:100]}...")
                    print(f"    After:  {sf.fixed[:100]}...")

    # Apply fixes if requested
    if args.apply:
        print()
        print("=" * 60)
        print("APPLYING FIXES")
        print("=" * 60)

        updated_count = 0

        # Group fixes by source_id
        fixes_by_source = {}
        for fix in all_fixes:
            if fix.source_id not in fixes_by_source:
                fixes_by_source[fix.source_id] = []
            fixes_by_source[fix.source_id].append(fix)

        for source_id, source_fixes in fixes_by_source.items():
            # Get current Fields blob
            cursor.execute('SELECT Fields FROM SourceTable WHERE SourceID = ?', (source_id,))
            row = cursor.fetchone()
            if not row:
                continue

            fields_blob = row[0]
            fields_xml = fields_blob.decode('utf-8') if isinstance(fields_blob, bytes) else fields_blob

            # Build updates
            updates = {}
            for fix in source_fixes:
                updates[fix.field_name] = fix.fixed

            # Rebuild XML
            new_xml = rebuild_fields_xml(fields_xml, updates)

            # Update database
            cursor.execute(
                'UPDATE SourceTable SET Fields = ? WHERE SourceID = ?',
                (new_xml.encode('utf-8'), source_id)
            )
            updated_count += 1

        conn.commit()
        print(f"Updated {updated_count} sources")

    conn.close()
    print()
    print("Done!")


if __name__ == '__main__':
    main()
