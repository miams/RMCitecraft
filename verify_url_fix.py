#!/usr/bin/env python3
"""
Verify URL extraction improvement after PAL format fix.
Counts missing FamilySearch URLs by census year.
"""

import sqlite3
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rmcitecraft.parsers.familysearch_parser import FamilySearchParser

def connect_rmtree(db_path):
    """Connect to RootsMagic database with RMNOCASE collation support."""
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    conn.load_extension("./sqlite-extension/icu.dylib")
    conn.execute(
        "SELECT icu_load_collation('en_US@colStrength=primary;caseLevel=off;normalization=on','RMNOCASE')"
    )
    conn.enable_load_extension(False)
    return conn

def extract_census_year_from_source_name(source_name):
    """Extract census year from SourceName field."""
    import re
    # Pattern: "Fed Census: YYYY" or "Federal Census: YYYY"
    match = re.search(r"Fed(?:eral)?\s+Census:\s*(\d{4})", source_name, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None

def main():
    db_path = "data/Iiams.rmtree"

    # Connect to database
    conn = connect_rmtree(db_path)
    cursor = conn.cursor()

    # Query all Federal Census citations
    query = """
    SELECT
        c.CitationID,
        s.Name as SourceName,
        c.ActualText,
        s.Fields as SourceFields
    FROM CitationTable c
    JOIN SourceTable s ON c.SourceID = s.SourceID
    WHERE s.Name LIKE 'Fed Census: ____,%'
    ORDER BY c.CitationID
    """

    cursor.execute(query)
    citations = cursor.fetchall()

    # Initialize parser
    parser = FamilySearchParser()

    # Count by census year
    year_stats = {}
    total_citations = 0
    total_missing = 0

    print("Analyzing FamilySearch URL extraction after PAL format fix...\n")

    for citation_id, source_name, actual_text, source_fields in citations:
        # Extract census year
        census_year = extract_census_year_from_source_name(source_name)
        if not census_year:
            continue

        # Initialize year stats
        if census_year not in year_stats:
            year_stats[census_year] = {"total": 0, "missing": 0}

        year_stats[census_year]["total"] += 1
        total_citations += 1

        # Parse citation
        parse_text = actual_text if actual_text else ""
        context_text = source_name

        try:
            parsed = parser.parse(parse_text, context_text, citation_id)
            has_url = bool(parsed.get("familysearch_url"))

            if not has_url:
                year_stats[census_year]["missing"] += 1
                total_missing += 1
        except Exception as e:
            # Parse error = missing URL
            year_stats[census_year]["missing"] += 1
            total_missing += 1

    conn.close()

    # Print results table
    print("=" * 70)
    print(f"{'Census Year':<15} {'Total':<10} {'Missing URLs':<15} {'Success Rate':<15}")
    print("=" * 70)

    for year in sorted(year_stats.keys()):
        total = year_stats[year]["total"]
        missing = year_stats[year]["missing"]
        success_rate = ((total - missing) / total * 100) if total > 0 else 0

        print(f"{year:<15} {total:<10} {missing:<15} {success_rate:>6.1f}%")

    print("=" * 70)
    overall_success = ((total_citations - total_missing) / total_citations * 100) if total_citations > 0 else 0
    print(f"{'TOTAL':<15} {total_citations:<10} {total_missing:<15} {overall_success:>6.1f}%")
    print("=" * 70)

    print(f"\n✅ URL extraction improvement:")
    print(f"   Before PAL fix: 145 missing URLs (96.7% success)")
    print(f"   After PAL fix:  {total_missing} missing URLs ({overall_success:.1f}% success)")
    print(f"   Improvement: {145 - total_missing} URLs now extracting")

    # List remaining citations with missing URLs (if any)
    if total_missing > 0:
        print(f"\n⚠️  {total_missing} citations still have missing URLs")
        print("   These may have '[missing]' tags or truly unavailable URLs")

if __name__ == "__main__":
    main()
