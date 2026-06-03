#!/usr/bin/env python3
"""
Fix Independent City formatting in Census sources.

For independent cities (Baltimore, St. Louis, Virginia cities), this script:
1. Adds "(Independent City)" notation to footnote, short footnote, and bibliography
2. Fixes "X County" references to "X (Independent City)" where appropriate

This script only fixes records that clearly appear to be independent city records
based on locality patterns (e.g., "Ward" for Baltimore City). Ambiguous records
are flagged for manual review.

Usage:
    python scripts/fix_independent_city_formatting.py 1930 --dry-run    # Preview
    python scripts/fix_independent_city_formatting.py 1930              # Apply
    python scripts/fix_independent_city_formatting.py 1920 1930 1940    # Multiple years
    python scripts/fix_independent_city_formatting.py 1930 --city Baltimore  # Specific city
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rmcitecraft.database.connection import connect_rmtree
from rmcitecraft.config.independent_cities import (
    INDEPENDENT_CITIES,
    get_independent_city,
    is_independent_city,
)


@dataclass
class CitationFix:
    """Represents a fix to be applied."""
    source_id: int
    source_name: str
    field: str
    old_value: str
    new_value: str
    fix_type: str
    confidence: str  # "high", "medium", "low"


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
    """Update a field value in Fields BLOB."""
    if not fields_blob:
        return ""
    try:
        if isinstance(fields_blob, bytes):
            text = fields_blob.decode("utf-8", errors="ignore")
        else:
            text = fields_blob
        pattern = rf'(<Name>{field_name}</Name>\s*<Value>)(.*?)(</Value>)'
        return re.sub(pattern, rf'\g<1>{new_value}\g<3>', text, flags=re.DOTALL)
    except Exception:
        return ""


def fix_footnote_city_notation(
    footnote: str,
    city_name: str,
    state_name: str,
) -> tuple[str | None, str]:
    """
    Fix independent city notation in footnote.

    Transforms:
        "Baltimore County, Maryland" -> "Baltimore (Independent City), Maryland"

    Returns:
        (fixed_text or None, description)
    """
    # Pattern 1: "City County, State" -> "City (Independent City), State"
    pattern1 = rf'\b{re.escape(city_name)} County,\s*{re.escape(state_name)}\b'
    replacement1 = f'{city_name} (Independent City), {state_name}'

    if re.search(pattern1, footnote):
        fixed = re.sub(pattern1, replacement1, footnote)
        return fixed, f'Changed "{city_name} County" to "{city_name} (Independent City)"'

    # Pattern 2: Already has city name but no "(Independent City)"
    # e.g., "Baltimore, Maryland" -> "Baltimore (Independent City), Maryland"
    pattern2 = rf'\b{re.escape(city_name)},\s*{re.escape(state_name)}\b'
    if re.search(pattern2, footnote) and "(Independent City)" not in footnote:
        # Only if it doesn't already say "County"
        if f"{city_name} County" not in footnote:
            fixed = re.sub(pattern2, f'{city_name} (Independent City), {state_name}', footnote)
            return fixed, f'Added "(Independent City)" after "{city_name}"'

    return None, ""


def fix_short_footnote_city_notation(
    short_fn: str,
    city_name: str,
    state_abbrev: str,
) -> tuple[str | None, str]:
    """
    Fix independent city notation in short footnote.

    Transforms:
        "Baltimore Co., Md." -> "Baltimore (Independent City), Md."
    """
    # Pattern: "City Co., State" -> "City (Independent City), State"
    pattern = rf'\b{re.escape(city_name)} Co\.,\s*{re.escape(state_abbrev)}\b'
    replacement = f'{city_name} (Independent City), {state_abbrev}'

    if re.search(pattern, short_fn):
        fixed = re.sub(pattern, replacement, short_fn)
        return fixed, f'Changed "{city_name} Co." to "{city_name} (Independent City)"'

    return None, ""


def fix_bibliography_city_notation(
    bibliography: str,
    city_name: str,
    state_name: str,
) -> tuple[str | None, str]:
    """
    Fix independent city notation in bibliography.

    Transforms:
        "U.S. Maryland. Baltimore County." -> "U.S. Maryland. Baltimore (Independent City)."
    """
    # Pattern: "State. City County." -> "State. City (Independent City)."
    pattern = rf'(U\.S\.\s+{re.escape(state_name)}\.\s+){re.escape(city_name)} County\.'
    replacement = rf'\g<1>{city_name} (Independent City).'

    if re.search(pattern, bibliography):
        fixed = re.sub(pattern, replacement, bibliography)
        return fixed, f'Changed "{city_name} County" to "{city_name} (Independent City)"'

    return None, ""


def analyze_source(
    source_id: int,
    name: str,
    footnote: str,
    short_fn: str,
    bibliography: str,
    year: int,
) -> list[CitationFix]:
    """Analyze a source and generate fixes if needed."""
    fixes = []

    # Extract state and county from source name
    match = re.search(rf'Fed Census: {year}, ([^,]+), ([^\[]+)', name)
    if not match:
        return fixes

    state_name = match.group(1).strip()
    county_name = match.group(2).strip()

    # Check if this is an independent city
    if not is_independent_city(county_name, state_name):
        return fixes

    ic_info = get_independent_city(county_name, state_name)
    if not ic_info:
        return fixes

    # Already has "(Independent City)" - no fix needed
    if "(Independent City)" in footnote:
        return fixes

    # Determine confidence based on locality patterns
    has_city_pattern = ic_info.locality_pattern and ic_info.locality_pattern in footnote
    has_county_pattern = ic_info.county_locality_pattern and ic_info.county_locality_pattern in footnote

    if has_county_pattern and not has_city_pattern:
        # This is likely the COUNTY, not the city - don't fix
        return fixes

    if has_city_pattern:
        confidence = "high"
    elif f"{county_name} County" in footnote:
        # Says "County" but no clear pattern - ambiguous
        confidence = "low"
    else:
        confidence = "medium"

    # Only auto-fix high confidence cases
    if confidence != "high":
        return fixes

    # Get state abbreviation
    STATE_ABBREVIATIONS = {
        "Maryland": "Md.", "Missouri": "Mo.", "Virginia": "Va.",
        "Nevada": "Nev.",
    }
    state_abbrev = STATE_ABBREVIATIONS.get(state_name, state_name)

    # Generate fixes for each field
    fixed_fn, desc_fn = fix_footnote_city_notation(footnote, county_name, state_name)
    if fixed_fn:
        fixes.append(CitationFix(
            source_id=source_id,
            source_name=name,
            field="Footnote",
            old_value=footnote,
            new_value=fixed_fn,
            fix_type="add_independent_city_notation",
            confidence=confidence,
        ))

    fixed_short, desc_short = fix_short_footnote_city_notation(short_fn, county_name, state_abbrev)
    if fixed_short:
        fixes.append(CitationFix(
            source_id=source_id,
            source_name=name,
            field="ShortFootnote",
            old_value=short_fn,
            new_value=fixed_short,
            fix_type="add_independent_city_notation",
            confidence=confidence,
        ))

    fixed_bib, desc_bib = fix_bibliography_city_notation(bibliography, county_name, state_name)
    if fixed_bib:
        fixes.append(CitationFix(
            source_id=source_id,
            source_name=name,
            field="Bibliography",
            old_value=bibliography,
            new_value=fixed_bib,
            fix_type="add_independent_city_notation",
            confidence=confidence,
        ))

    return fixes


def fix_year(
    cursor,
    year: int,
    dry_run: bool,
    city_filter: str | None = None,
    verbose: bool = False,
) -> tuple[int, int]:
    """
    Fix independent city formatting for a census year.

    Returns: (fixes_applied, sources_skipped)
    """
    print("=" * 70)
    print(f"FIX INDEPENDENT CITY FORMATTING: {year} Census")
    print("=" * 70)
    print()

    # Build query
    if city_filter:
        query = f"""
            SELECT s.SourceID, s.Name, s.Fields
            FROM SourceTable s
            WHERE s.Name LIKE 'Fed Census: {year},%{city_filter}%'
            ORDER BY s.SourceID
        """
    else:
        # Get sources for all known independent cities
        city_patterns = []
        for (city, state), ic in INDEPENDENT_CITIES.items():
            city_patterns.append(f"s.Name LIKE 'Fed Census: {year}, {state}, {city} %'")

        if not city_patterns:
            print("No independent cities configured.")
            return 0, 0

        query = f"""
            SELECT s.SourceID, s.Name, s.Fields
            FROM SourceTable s
            WHERE {' OR '.join(city_patterns)}
            ORDER BY s.SourceID
        """

    cursor.execute(query)
    sources = cursor.fetchall()

    print(f"Found {len(sources)} potential independent city sources")
    print()

    all_fixes = []
    skipped_ambiguous = []
    already_correct = 0

    for source_id, name, fields_blob in sources:
        footnote = extract_field_from_blob(fields_blob, "Footnote")
        short_fn = extract_field_from_blob(fields_blob, "ShortFootnote")
        bibliography = extract_field_from_blob(fields_blob, "Bibliography")

        # Skip if already has "(Independent City)"
        if "(Independent City)" in footnote:
            already_correct += 1
            continue

        fixes = analyze_source(source_id, name, footnote, short_fn, bibliography, year)

        if fixes:
            all_fixes.extend(fixes)
        else:
            # Check if this was skipped due to ambiguity
            match = re.search(rf'Fed Census: {year}, ([^,]+), ([^\[]+)', name)
            if match:
                state_name = match.group(1).strip()
                county_name = match.group(2).strip()
                if is_independent_city(county_name, state_name):
                    skipped_ambiguous.append((source_id, name, footnote[:80]))

    # Group fixes by source
    fixes_by_source: dict[int, list[CitationFix]] = {}
    for fix in all_fixes:
        if fix.source_id not in fixes_by_source:
            fixes_by_source[fix.source_id] = []
        fixes_by_source[fix.source_id].append(fix)

    print(f"Sources already correct: {already_correct}")
    print(f"Sources to fix (high confidence): {len(fixes_by_source)}")
    print(f"Sources skipped (ambiguous/low confidence): {len(skipped_ambiguous)}")
    print()

    # Show fixes
    if fixes_by_source:
        print("Fixes to apply:")
        print("-" * 70)

        shown = 0
        for source_id, fixes in fixes_by_source.items():
            if shown < 5 or verbose:
                print(f"Source {source_id}: {fixes[0].source_name[:60]}...")
                for fix in fixes:
                    print(f"  {fix.field}: Add '(Independent City)' notation")
                print()
            shown += 1

        if shown < len(fixes_by_source) and not verbose:
            print(f"  ... and {len(fixes_by_source) - 5} more sources")
            print()

    # Show skipped
    if skipped_ambiguous and verbose:
        print("Skipped (requires manual review):")
        print("-" * 70)
        for sid, name, fn_preview in skipped_ambiguous[:10]:
            print(f"  {sid}: {name[:60]}...")
            print(f"       Footnote: {fn_preview}...")
        if len(skipped_ambiguous) > 10:
            print(f"  ... and {len(skipped_ambiguous) - 10} more")
        print()

    # Apply fixes
    if fixes_by_source and not dry_run:
        print(f"Applying fixes to {len(fixes_by_source)} sources...")

        for source_id, fixes in fixes_by_source.items():
            # Get current Fields BLOB
            cursor.execute('SELECT Fields FROM SourceTable WHERE SourceID = ?', (source_id,))
            row = cursor.fetchone()
            if not row:
                continue

            fields_blob = row[0]

            # Apply each fix
            for fix in fixes:
                fields_blob = update_field_in_blob(fields_blob, fix.field, fix.new_value)

            # Update database
            cursor.execute(
                'UPDATE SourceTable SET Fields = ? WHERE SourceID = ?',
                (fields_blob, source_id)
            )

        print(f"Applied {len(all_fixes)} fixes to {len(fixes_by_source)} sources.")
    elif dry_run:
        print("DRY RUN - No changes applied")

    return len(fixes_by_source), len(skipped_ambiguous)


def main():
    parser = argparse.ArgumentParser(
        description='Fix Independent City formatting in Census sources.'
    )
    parser.add_argument(
        'years',
        type=int,
        nargs='+',
        help='Census year(s) to fix (e.g., 1920 1930 1940)'
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
        '--city',
        type=str,
        help='Filter to specific city (e.g., Baltimore, "St. Louis")'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show all changes and skipped sources'
    )
    args = parser.parse_args()

    conn = connect_rmtree(str(args.db), read_only=args.dry_run)
    cursor = conn.cursor()

    total_fixed = 0
    total_skipped = 0

    for year in args.years:
        fixed, skipped = fix_year(cursor, year, args.dry_run, args.city, args.verbose)
        total_fixed += fixed
        total_skipped += skipped
        print()

    if not args.dry_run and total_fixed > 0:
        conn.commit()
        print(f"Total: {total_fixed} sources fixed across {len(args.years)} year(s).")
        print(f"       {total_skipped} sources require manual review.")
    elif args.dry_run:
        print(f"DRY RUN Summary: {total_fixed} sources would be fixed, {total_skipped} need manual review.")
        print("Run without --dry-run to apply changes.")

    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
