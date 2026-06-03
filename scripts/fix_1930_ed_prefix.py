#!/usr/bin/env python3
"""
Fix 1930 Census ED Prefix

Adds the state-county prefix to 1930 census enumeration districts.
The 1930 ED format should be: ED [prefix]-[number]
where prefix is assigned sequentially by county in alphabetical order within each state.

Updates:
- Source Name: [ED 29, ...] -> [ED 30-29, ...]
- Footnote: enumeration district (ED) 29, -> enumeration district (ED) 30-29,
- Short Footnote: E.D. 29, -> E.D. 30-29,

Reference: ./scripts/1930_ED_prefix_by_state_county.csv
Data source: NARA microfilm publications T1224, M1931, M1930, A3378
Verification: https://stevemorse.org/census/unified.html?year=1930

Usage:
    python scripts/fix_1930_ed_prefix.py --dry-run           # Preview changes
    python scripts/fix_1930_ed_prefix.py                     # Apply changes
    python scripts/fix_1930_ed_prefix.py --limit 10          # Process only 10 sources
    python scripts/fix_1930_ed_prefix.py --source-id 23      # Process specific source
"""

import argparse
import csv
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
    state: str
    county: str
    old_ed: str
    new_ed: str
    prefix: int


def normalize_county_name(county: str) -> str:
    """Normalize county name for lookup."""
    county = county.strip()
    county = county.replace('De Witt', 'DeWitt')
    county = county.replace('De Kalb', 'DeKalb')
    county = county.replace('De Soto', 'DeSoto')
    county = county.replace('La Salle', 'LaSalle')
    county = county.replace('St.', 'St')
    return county.lower()


def load_prefix_lookup(csv_path: Path) -> dict[tuple[str, str], int]:
    """Load state/county to prefix mapping from CSV."""
    lookup = {}

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            state = row['state'].strip().lower()
            county = normalize_county_name(row['county'])
            prefix = int(row['prefix'])

            lookup[(state, county)] = prefix

            # Also store without common suffixes
            for suffix in [' county', ' city', ' (new)', ' territory']:
                if county.endswith(suffix):
                    lookup[(state, county[:-len(suffix)])] = prefix
                    break

    return lookup


def extract_source_info(name: str) -> tuple[str, str, str] | None:
    """Extract state, county, and ED from source name."""
    match = re.search(
        r'Fed Census:\s*1930,\s*([^,]+),\s*([^,\[]+)(?:,\s*[^,\[]+)?\s*\[ED\s+([^\],]+)',
        name
    )
    if match:
        return match.group(1).strip(), match.group(2).strip(), match.group(3).strip()
    return None


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


def has_prefix(ed: str) -> bool:
    """Check if ED already has a prefix (contains hyphen)."""
    return '-' in ed


def add_prefix_to_ed(ed: str, prefix: int) -> str:
    """Add prefix to ED number."""
    return f"{prefix}-{ed}"


def fix_source_name(name: str, old_ed: str, new_ed: str) -> str:
    """Fix the ED in source name."""
    # Pattern: [ED 29, -> [ED 30-29,
    return name.replace(f'[ED {old_ed},', f'[ED {new_ed},')


def fix_footnote(footnote: str, old_ed: str, new_ed: str) -> str:
    """Fix the ED in footnote."""
    # Pattern: enumeration district (ED) 29, -> enumeration district (ED) 30-29,
    return footnote.replace(
        f'enumeration district (ED) {old_ed},',
        f'enumeration district (ED) {new_ed},'
    )


def fix_short_footnote(short_fn: str, old_ed: str, new_ed: str) -> str:
    """Fix the ED in short footnote."""
    # Pattern: E.D. 29, -> E.D. 30-29,
    return short_fn.replace(f'E.D. {old_ed},', f'E.D. {new_ed},')


def process_source(
    source_id: int,
    name: str,
    fields_text: str,
    prefix_lookup: dict[tuple[str, str], int]
) -> SourceUpdate | None:
    """Process a single source and return update if needed."""

    # Extract info from source name
    extracted = extract_source_info(name)
    if not extracted:
        return None

    state, county, ed = extracted

    # Skip if already has prefix
    if has_prefix(ed):
        return None

    # Look up expected prefix
    state_norm = state.strip().lower()
    if ' territory' in state_norm:
        state_norm = state_norm.replace(' territory', '')
    county_norm = normalize_county_name(county)

    prefix = prefix_lookup.get((state_norm, county_norm))
    if prefix is None:
        # Try fuzzy match
        for key in prefix_lookup:
            if key[0] == state_norm:
                if county_norm in key[1] or key[1] in county_norm:
                    prefix = prefix_lookup[key]
                    break

    if prefix is None:
        return None

    # Calculate new ED
    new_ed = add_prefix_to_ed(ed, prefix)

    # Fix source name
    new_name = fix_source_name(name, ed, new_ed)

    # Fix fields
    new_fields = fields_text

    # Fix footnote
    footnote = extract_field(fields_text, "Footnote")
    if footnote:
        new_footnote = fix_footnote(footnote, ed, new_ed)
        if new_footnote != footnote:
            new_fields = update_field(new_fields, "Footnote", new_footnote)

    # Fix short footnote
    short_fn = extract_field(fields_text, "ShortFootnote")
    if short_fn:
        new_short = fix_short_footnote(short_fn, ed, new_ed)
        if new_short != short_fn:
            new_fields = update_field(new_fields, "ShortFootnote", new_short)

    # Only return update if something changed
    if new_name == name and new_fields == fields_text:
        return None

    return SourceUpdate(
        source_id=source_id,
        old_name=name,
        new_name=new_name,
        old_fields=fields_text,
        new_fields=new_fields,
        state=state,
        county=county,
        old_ed=ed,
        new_ed=new_ed,
        prefix=prefix
    )


def main():
    parser = argparse.ArgumentParser(
        description='Fix 1930 census ED prefixes',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--db',
        type=Path,
        default=Path('data/Iiams.rmtree'),
        help='Path to RootsMagic database'
    )
    parser.add_argument(
        '--csv',
        type=Path,
        default=Path('scripts/1930_ED_prefix_by_state_county.csv'),
        help='Path to ED prefix lookup CSV'
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
    print("FIX 1930 CENSUS ED PREFIXES")
    print("=" * 70)
    print()
    print(f"Database: {args.db}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY CHANGES'}")
    if args.limit > 0:
        print(f"Limit: {args.limit} sources")
    if args.source_id > 0:
        print(f"Source ID: {args.source_id}")
    print()

    # Load prefix lookup
    if not args.csv.exists():
        print(f"Error: CSV file not found: {args.csv}", file=sys.stderr)
        return 1

    prefix_lookup = load_prefix_lookup(args.csv)
    print(f"Loaded {len(prefix_lookup)} county prefixes from CSV")
    print()

    # Connect to database
    conn = connect_rmtree(str(args.db), read_only=args.dry_run)
    cursor = conn.cursor()

    # Get 1930 census sources
    if args.source_id > 0:
        cursor.execute('''
            SELECT SourceID, Name, CAST(Fields AS TEXT)
            FROM SourceTable
            WHERE SourceID = ? AND Name LIKE 'Fed Census: 1930%'
        ''', (args.source_id,))
    else:
        cursor.execute('''
            SELECT SourceID, Name, CAST(Fields AS TEXT)
            FROM SourceTable
            WHERE Name LIKE 'Fed Census: 1930%'
            ORDER BY SourceID
        ''')

    sources = cursor.fetchall()
    print(f"Found {len(sources)} 1930 census sources")
    print()

    # Process sources
    updates = []
    skipped_has_prefix = 0
    skipped_no_match = 0

    for source_id, name, fields_text in sources:
        if args.limit > 0 and len(updates) >= args.limit:
            break

        # Check if already has prefix
        extracted = extract_source_info(name)
        if extracted:
            _, _, ed = extracted
            if has_prefix(ed):
                skipped_has_prefix += 1
                continue

        update = process_source(source_id, name, fields_text, prefix_lookup)
        if update:
            updates.append(update)
        else:
            if extracted:
                skipped_no_match += 1

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Sources to update: {len(updates)}")
    print(f"Already has prefix: {skipped_has_prefix}")
    print(f"Could not match county: {skipped_no_match}")
    print()

    if updates:
        # Show preview
        print("=" * 70)
        print(f"PREVIEW OF CHANGES (first {min(10, len(updates))})")
        print("=" * 70)

        for update in updates[:10]:
            print(f"\nSource {update.source_id}:")
            print(f"  State/County: {update.state}, {update.county}")
            print(f"  ED: {update.old_ed} -> {update.new_ed} (prefix {update.prefix})")
            if args.verbose:
                print(f"  Old Name: {update.old_name[:70]}...")
                print(f"  New Name: {update.new_name[:70]}...")

        if len(updates) > 10:
            print(f"\n... and {len(updates) - 10} more")

        # Group by state for summary
        print()
        print("=" * 70)
        print("UPDATES BY STATE")
        print("=" * 70)

        state_counts = {}
        for update in updates:
            state_counts[update.state] = state_counts.get(update.state, 0) + 1

        for state in sorted(state_counts.keys()):
            print(f"  {state}: {state_counts[state]}")

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
                    print(f"  Source {update.source_id}: {row[0][:60]}...")
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
