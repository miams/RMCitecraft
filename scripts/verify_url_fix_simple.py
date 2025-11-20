#!/usr/bin/env python3
"""
Simple URL extraction test - just check if URL patterns match in raw text.
"""

import sqlite3
import re
from pathlib import Path

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
    match = re.search(r"Fed(?:eral)?\s+Census:\s*(\d{4})", source_name, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None

# URL pattern that handles both ARK and PAL formats
URL_PATTERN = re.compile(
    r"https?://(?:www\.)?familysearch\.org/(?:ark|pal):/[^\s)]+",
    re.IGNORECASE,
)

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
        c.ActualText
    FROM CitationTable c
    JOIN SourceTable s ON c.SourceID = s.SourceID
    WHERE s.Name LIKE 'Fed Census: ____,%'
    ORDER BY c.CitationID
    """

    cursor.execute(query)
    citations = cursor.fetchall()

    # Count by census year
    year_stats = {}
    total_citations = 0
    total_missing = 0

    print("Analyzing FamilySearch URL extraction after PAL format fix...\n")

    for citation_id, source_name, actual_text in citations:
        # Extract census year
        census_year = extract_census_year_from_source_name(source_name)
        if not census_year:
            continue

        # Initialize year stats
        if census_year not in year_stats:
            year_stats[census_year] = {"total": 0, "missing": 0}

        year_stats[census_year]["total"] += 1
        total_citations += 1

        # Check if URL exists in ActualText
        parse_text = actual_text if actual_text else ""

        # Look for URL in the citation text
        has_url = bool(URL_PATTERN.search(parse_text))

        if not has_url:
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

    if total_missing < 145:
        improvement = 145 - total_missing
        print(f"   Improvement: {improvement} URLs now extracting ✅")
    else:
        print(f"   Issue: More missing URLs than before ⚠️")

    # List remaining citations with missing URLs (if any and reasonable number)
    if 0 < total_missing <= 50:
        print(f"\n⚠️  Remaining {total_missing} citations with missing URLs:")

        cursor = conn.cursor()
        cursor.execute(query)
        citations = cursor.fetchall()

        for citation_id, source_name, actual_text in citations:
            census_year = extract_census_year_from_source_name(source_name)
            if not census_year:
                continue

            parse_text = actual_text if actual_text else ""
            has_url = bool(URL_PATTERN.search(parse_text))

            if not has_url:
                print(f"   - Citation {citation_id} ({census_year})")

if __name__ == "__main__":
    main()
