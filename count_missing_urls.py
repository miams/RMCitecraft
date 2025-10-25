#!/usr/bin/env python3
"""
Count missing FamilySearch URLs by census year (red error icons).
Uses the same logic as the Citation Manager UI.
"""

import sqlite3
import re
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rmcitecraft.parsers.familysearch_parser import FamilySearchParser
from rmcitecraft.repositories.citation_repository import CitationRepository
from rmcitecraft.repositories.database import DatabaseConnection

def extract_census_year_from_source_name(source_name):
    """Extract census year from SourceName field."""
    match = re.search(r"Fed(?:eral)?\s+Census:\s*(\d{4})", source_name, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None

def main():
    db_path = "data/Iiams.rmtree"

    # Initialize database connection and repository
    db_conn = DatabaseConnection(db_path)
    repo = CitationRepository(db_conn)
    parser = FamilySearchParser()

    # Get all census years
    years = repo.get_all_census_years()

    print("\nCounting missing FamilySearch URLs (red error icons) by census year...\n")
    print("=" * 70)
    print(f"{'Census Year':<15} {'Total':<10} {'Missing URLs':<15} {'Success Rate':<15}")
    print("=" * 70)

    total_citations = 0
    total_missing = 0

    for census_year in years:

        # Get all citations for this year
        citations = repo.get_citations_by_year(census_year)

        year_total = len(citations)
        year_missing = 0

        for citation in citations:
            citation_id = citation["CitationID"]
            source_name = citation["SourceName"]

            # Extract parse_text using same priority as UI
            # Priority: Citation.Footnote > Source.Footnote > Free Form > SourceName
            parse_text = citation["Footnote"]

            # Try Source.Footnote from SourceFields BLOB
            if not parse_text:
                parse_text = repo.extract_field_from_blob(citation["SourceFields"], "Footnote")

            # Try Free Form citation from CitationFields BLOB
            if not parse_text and citation["TemplateID"] == 0:
                parse_text = repo.extract_freeform_text(citation["CitationFields"])

            # Fall back to SourceName
            if not parse_text:
                parse_text = source_name

            # Pass SourceName as second parameter for simplified format state/county extraction
            context_text = citation["ActualText"] if citation["ActualText"] else source_name

            # Parse citation
            try:
                parsed = parser.parse(parse_text, context_text, citation_id=citation_id)
                has_url = bool(parsed.get("familysearch_url"))

                if not has_url:
                    year_missing += 1
            except Exception as e:
                # Parse error = missing URL
                year_missing += 1

        total_citations += year_total
        total_missing += year_missing

        success_rate = ((year_total - year_missing) / year_total * 100) if year_total > 0 else 0
        print(f"{census_year:<15} {year_total:<10} {year_missing:<15} {success_rate:>6.1f}%")

    print("=" * 70)
    overall_success = ((total_citations - total_missing) / total_citations * 100) if total_citations > 0 else 0
    print(f"{'TOTAL':<15} {total_citations:<10} {total_missing:<15} {overall_success:>6.1f}%")
    print("=" * 70)

    print(f"\n📊 Summary:")
    print(f"   Total citations: {total_citations}")
    print(f"   Missing URLs (red ❌): {total_missing}")
    print(f"   Successfully extracted (green ✓/blue ◯): {total_citations - total_missing}")
    print(f"   Overall success rate: {overall_success:.1f}%")

if __name__ == "__main__":
    main()
