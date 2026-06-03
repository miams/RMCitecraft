#!/usr/bin/env python3
"""
Analyze 1930 Census ED Compliance

Checks whether 1930 census sources have the correct ED format with state-county prefix.
The 1930 census ED format should be: ED [prefix]-[number]
where prefix is assigned by state and county.

For example:
- Pennsylvania, Greene County has prefix 30
- So an ED in Greene County should be "ED 30-5" not just "ED 5"

Reference: ./scripts/1930_ED_prefix_by_state_county.csv

Independent cities and large cities may have their own prefixes not covered by the
county table. For uncovered cases, the Steve Morse tool can be used:
https://stevemorse.org/census/unified.html?year=1930

Usage:
    python scripts/analyze_1930_ed_compliance.py              # Generate report
    python scripts/analyze_1930_ed_compliance.py --verbose    # Show all sources
    python scripts/analyze_1930_ed_compliance.py --json       # JSON output
"""

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rmcitecraft.database.connection import connect_rmtree


@dataclass
class EDAnalysis:
    """Analysis result for a single source."""
    source_id: int
    source_name: str
    state: str
    county: str
    current_ed: str
    has_prefix: bool
    expected_prefix: int | None = None
    prefix_source: str = ""  # "csv", "inferred", "unknown"
    is_compliant: bool = False
    suggested_ed: str | None = None
    notes: str = ""


@dataclass
class ComplianceReport:
    """Overall compliance report."""
    total_sources: int = 0
    compliant_sources: int = 0
    non_compliant_sources: int = 0
    unknown_prefix_sources: int = 0
    sources_by_state: dict = field(default_factory=dict)
    non_compliant_list: list = field(default_factory=list)
    unknown_prefix_list: list = field(default_factory=list)


def normalize_county_name(county: str) -> str:
    """Normalize county name for lookup."""
    # Remove common variations
    county = county.strip()

    # Handle "De Witt" vs "DeWitt" variations (normalize to no-space version)
    county = county.replace('De Witt', 'DeWitt')
    county = county.replace('De Kalb', 'DeKalb')
    county = county.replace('De Soto', 'DeSoto')
    county = county.replace('La Salle', 'LaSalle')

    # Handle "St." vs "St" variations
    county = county.replace('St.', 'St')

    return county.lower()


def load_prefix_lookup(csv_path: Path) -> dict[tuple[str, str], int]:
    """
    Load state/county to prefix mapping from CSV.

    Returns dict mapping (state, county) -> prefix
    """
    lookup = {}

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            state = row['state'].strip()
            county = row['county'].strip()
            prefix = int(row['prefix'])

            # Apply same normalization as source names
            county_norm = normalize_county_name(county)
            state_norm = state.lower()

            lookup[(state_norm, county_norm)] = prefix

            # Also store without common suffixes for flexibility
            for suffix in [' county', ' city', ' (new)', ' territory']:
                if county_norm.endswith(suffix):
                    county_base = county_norm[:-len(suffix)]
                    lookup[(state_norm, county_base)] = prefix
                    break

    return lookup


def normalize_state_name(state: str) -> str:
    """Normalize state name for lookup."""
    state = state.strip().lower()

    # Handle territory suffixes
    if ' territory' in state:
        state = state.replace(' territory', '')

    return state


def extract_ed_from_source_name(name: str) -> tuple[str, str, str] | None:
    """
    Extract state, county, and ED from source name.

    Returns (state, county, ed) or None if not found.
    """
    # Pattern: Fed Census: 1930, State, County [ED X...
    # or: Fed Census: 1930, State, County, Locality [ED X...
    match = re.search(
        r'Fed Census:\s*1930,\s*([^,]+),\s*([^,\[]+)(?:,\s*[^,\[]+)?\s*\[ED\s+([^\],]+)',
        name
    )
    if match:
        state = match.group(1).strip()
        county = match.group(2).strip()
        ed = match.group(3).strip()
        return state, county, ed

    return None


def analyze_ed_format(ed: str) -> tuple[bool, int | None, int | None]:
    """
    Analyze ED format to determine if it has a prefix.

    Returns (has_prefix, prefix_number, ed_number)
    """
    # Check for prefix-number format (e.g., "30-5", "8-18")
    match = re.match(r'^(\d+)-(\d+)$', ed)
    if match:
        return True, int(match.group(1)), int(match.group(2))

    # Check for simple number format (e.g., "29", "164")
    match = re.match(r'^(\d+)$', ed)
    if match:
        return False, None, int(match.group(1))

    # Handle other formats (e.g., with letters)
    match = re.match(r'^(\d+[A-Z]?)-(\d+[A-Z]?)$', ed)
    if match:
        prefix_str = re.sub(r'[A-Z]', '', match.group(1))
        ed_str = re.sub(r'[A-Z]', '', match.group(2))
        return True, int(prefix_str) if prefix_str else None, int(ed_str) if ed_str else None

    return False, None, None


def analyze_source(
    source_id: int,
    source_name: str,
    prefix_lookup: dict[tuple[str, str], int]
) -> EDAnalysis | None:
    """Analyze a single source for ED compliance."""

    extracted = extract_ed_from_source_name(source_name)
    if not extracted:
        return None

    state, county, ed = extracted
    has_prefix, current_prefix, ed_number = analyze_ed_format(ed)

    # Try to find expected prefix
    state_norm = normalize_state_name(state)
    county_norm = normalize_county_name(county)

    expected_prefix = None
    prefix_source = "unknown"

    # Try direct lookup
    if (state_norm, county_norm) in prefix_lookup:
        expected_prefix = prefix_lookup[(state_norm, county_norm)]
        prefix_source = "csv"
    else:
        # Try variations
        for key in prefix_lookup:
            if key[0] == state_norm:
                # Check if county matches with some flexibility
                if county_norm in key[1] or key[1] in county_norm:
                    expected_prefix = prefix_lookup[key]
                    prefix_source = "csv_fuzzy"
                    break

    # Determine compliance
    is_compliant = False
    suggested_ed = None
    notes = ""

    if has_prefix:
        if expected_prefix is not None:
            if current_prefix == expected_prefix:
                is_compliant = True
            else:
                notes = f"Prefix mismatch: has {current_prefix}, expected {expected_prefix}"
                if ed_number:
                    suggested_ed = f"{expected_prefix}-{ed_number}"
        else:
            # Has prefix but we don't know the expected - assume OK for now
            is_compliant = True
            notes = "Has prefix but county not in lookup table"
    else:
        # No prefix - not compliant
        if expected_prefix is not None and ed_number is not None:
            suggested_ed = f"{expected_prefix}-{ed_number}"
            notes = f"Missing prefix (expected {expected_prefix})"
        elif expected_prefix is None:
            notes = "Missing prefix; county not in lookup table"

    return EDAnalysis(
        source_id=source_id,
        source_name=source_name,
        state=state,
        county=county,
        current_ed=ed,
        has_prefix=has_prefix,
        expected_prefix=expected_prefix,
        prefix_source=prefix_source,
        is_compliant=is_compliant,
        suggested_ed=suggested_ed,
        notes=notes
    )


def generate_report(analyses: list[EDAnalysis]) -> ComplianceReport:
    """Generate compliance report from analyses."""
    report = ComplianceReport()
    report.total_sources = len(analyses)

    for analysis in analyses:
        # Count by state
        if analysis.state not in report.sources_by_state:
            report.sources_by_state[analysis.state] = {
                'total': 0,
                'compliant': 0,
                'non_compliant': 0,
                'unknown': 0
            }

        report.sources_by_state[analysis.state]['total'] += 1

        if analysis.is_compliant:
            report.compliant_sources += 1
            report.sources_by_state[analysis.state]['compliant'] += 1
        elif analysis.expected_prefix is None:
            report.unknown_prefix_sources += 1
            report.sources_by_state[analysis.state]['unknown'] += 1
            report.unknown_prefix_list.append(analysis)
        else:
            report.non_compliant_sources += 1
            report.sources_by_state[analysis.state]['non_compliant'] += 1
            report.non_compliant_list.append(analysis)

    return report


def print_text_report(report: ComplianceReport, verbose: bool = False):
    """Print human-readable report."""
    print("=" * 70)
    print("1930 CENSUS ED COMPLIANCE REPORT")
    print("=" * 70)
    print()
    print(f"Total sources analyzed: {report.total_sources}")
    print(f"  Compliant (has correct prefix): {report.compliant_sources} ({100*report.compliant_sources/report.total_sources:.1f}%)")
    print(f"  Non-compliant (missing/wrong prefix): {report.non_compliant_sources} ({100*report.non_compliant_sources/report.total_sources:.1f}%)")
    print(f"  Unknown prefix (county not in lookup): {report.unknown_prefix_sources} ({100*report.unknown_prefix_sources/report.total_sources:.1f}%)")
    print()

    # State summary
    print("=" * 70)
    print("BY STATE")
    print("=" * 70)
    print()
    print(f"{'State':<25} {'Total':>8} {'OK':>8} {'Missing':>8} {'Unknown':>8}")
    print("-" * 70)

    for state in sorted(report.sources_by_state.keys()):
        stats = report.sources_by_state[state]
        print(f"{state:<25} {stats['total']:>8} {stats['compliant']:>8} {stats['non_compliant']:>8} {stats['unknown']:>8}")

    print()

    # Non-compliant sources
    if report.non_compliant_list:
        print("=" * 70)
        print(f"NON-COMPLIANT SOURCES ({len(report.non_compliant_list)})")
        print("=" * 70)
        print()

        limit = len(report.non_compliant_list) if verbose else min(20, len(report.non_compliant_list))

        for analysis in report.non_compliant_list[:limit]:
            print(f"Source {analysis.source_id}:")
            print(f"  Name: {analysis.source_name[:70]}...")
            print(f"  State/County: {analysis.state}, {analysis.county}")
            print(f"  Current ED: {analysis.current_ed}")
            if analysis.suggested_ed:
                print(f"  Suggested ED: {analysis.suggested_ed}")
            print(f"  Notes: {analysis.notes}")
            print()

        if not verbose and len(report.non_compliant_list) > limit:
            print(f"... and {len(report.non_compliant_list) - limit} more")
            print()

    # Unknown prefix sources
    if report.unknown_prefix_list:
        print("=" * 70)
        print(f"SOURCES WITH UNKNOWN PREFIX ({len(report.unknown_prefix_list)})")
        print("(County not found in lookup table - may need manual verification)")
        print("=" * 70)
        print()

        limit = len(report.unknown_prefix_list) if verbose else min(10, len(report.unknown_prefix_list))

        for analysis in report.unknown_prefix_list[:limit]:
            print(f"Source {analysis.source_id}: {analysis.state}, {analysis.county} - ED {analysis.current_ed}")

        if not verbose and len(report.unknown_prefix_list) > limit:
            print(f"... and {len(report.unknown_prefix_list) - limit} more")
        print()

    print("=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    print()
    print("1. Non-compliant sources need ED prefix added to source names and citations")
    print("2. Unknown prefix sources may be:")
    print("   - Independent cities with their own ED series")
    print("   - Large cities with separate ED numbering")
    print("   - County name spelling variations not in lookup")
    print("3. Use Steve Morse tool to verify ED numbers:")
    print("   https://stevemorse.org/census/unified.html?year=1930")


def print_json_report(report: ComplianceReport, analyses: list[EDAnalysis]):
    """Print JSON report."""
    output = {
        'summary': {
            'total_sources': report.total_sources,
            'compliant_sources': report.compliant_sources,
            'non_compliant_sources': report.non_compliant_sources,
            'unknown_prefix_sources': report.unknown_prefix_sources,
            'compliance_rate': report.compliant_sources / report.total_sources if report.total_sources > 0 else 0
        },
        'by_state': report.sources_by_state,
        'non_compliant': [
            {
                'source_id': a.source_id,
                'source_name': a.source_name,
                'state': a.state,
                'county': a.county,
                'current_ed': a.current_ed,
                'expected_prefix': a.expected_prefix,
                'suggested_ed': a.suggested_ed,
                'notes': a.notes
            }
            for a in report.non_compliant_list
        ],
        'unknown_prefix': [
            {
                'source_id': a.source_id,
                'source_name': a.source_name,
                'state': a.state,
                'county': a.county,
                'current_ed': a.current_ed
            }
            for a in report.unknown_prefix_list
        ]
    }
    print(json.dumps(output, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description='Analyze 1930 census ED compliance',
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
        '--verbose', '-v',
        action='store_true',
        help='Show all sources in report'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    args = parser.parse_args()

    # Load prefix lookup
    if not args.csv.exists():
        print(f"Error: CSV file not found: {args.csv}", file=sys.stderr)
        return 1

    prefix_lookup = load_prefix_lookup(args.csv)

    # Connect to database
    conn = connect_rmtree(str(args.db), read_only=True)
    cursor = conn.cursor()

    # Get all 1930 census sources
    cursor.execute('''
        SELECT SourceID, Name
        FROM SourceTable
        WHERE Name LIKE 'Fed Census: 1930%'
        ORDER BY SourceID
    ''')

    sources = cursor.fetchall()

    # Analyze each source
    analyses = []
    for source_id, name in sources:
        analysis = analyze_source(source_id, name, prefix_lookup)
        if analysis:
            analyses.append(analysis)

    conn.close()

    # Generate and print report
    report = generate_report(analyses)

    if args.json:
        print_json_report(report, analyses)
    else:
        print_text_report(report, args.verbose)

    return 0


if __name__ == '__main__':
    sys.exit(main())
