"""Test citation generation with George B Iams 1930 census example.

This test verifies the complete workflow:
1. LLM extraction from FamilySearch citation
2. Place parsing from RootsMagic PlaceTable
3. Template-based formatting
4. Output matches Evidence Explained format
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rmcitecraft.models.census_citation import CensusExtraction, PlaceDetails
from rmcitecraft.services.citation_formatter import format_census_citation


def test_george_iams_1930_manual():
    """Test citation generation with manually constructed data.

    This tests the formatter without LLM or database dependencies.
    """
    # Manually construct extraction (simulating LLM output)
    extraction = CensusExtraction(
        year=1930,
        state="Pennsylvania",
        county="Greene",
        locality="Jefferson",
        locality_type="Township",
        enumeration_district="30-17",  # User corrected from incomplete "17"
        sheet="13-A",
        line="15",
        family_number="281",
        dwelling_number=None,
        person_name="George B Iams",
        familysearch_url="https://www.familysearch.org/ark:/61903/1:1:XH3Z-4J8",
        access_date="7 November 2020",
        nara_publication="T626",
        fhl_microfilm="2,341,778",
        missing_fields=[],
    )

    # Parse place from RootsMagic format
    place = PlaceDetails.from_place_string(
        "Jefferson Township, Greene, Pennsylvania, United States"
    )

    # Generate all three citations
    citation = format_census_citation(
        extraction=extraction,
        place=place,
        citation_id=9816,
        source_id=3099,
        event_id=24124,
        person_id=3447,
    )

    # Expected Evidence Explained formats
    expected_footnote = (
        "1930 U.S. census, Greene County, Pennsylvania, Jefferson Township, "
        "enumeration district (ED) 30-17, sheet 13-A, line 15, George B Iams; "
        'imaged, "United States Census, 1930," <i>FamilySearch</i>, '
        "(https://www.familysearch.org/ark:/61903/1:1:XH3Z-4J8 : accessed 7 November 2020)."
    )

    expected_short_footnote = (
        "1930 U.S. census, Greene Co., Pa., Jefferson Twp., "
        "E.D. 30-17, sheet 13-A, George B Iams."
    )

    expected_bibliography = (
        "U.S. Pennsylvania. Greene County. 1930 U.S Census. "
        'Imaged. "1930 United States Federal Census." <i>FamilySearch</i> '
        "https://www.familysearch.org/ark:/61903/1:1:XH3Z-4J8 : 2020."
    )

    # Verify outputs
    print("=" * 80)
    print("FOOTNOTE:")
    print("-" * 80)
    print(citation.footnote)
    print()
    assert citation.footnote == expected_footnote, "Footnote mismatch"
    print("✓ Footnote matches expected format")
    print()

    print("=" * 80)
    print("SHORT FOOTNOTE:")
    print("-" * 80)
    print(citation.short_footnote)
    print()
    assert citation.short_footnote == expected_short_footnote, "Short footnote mismatch"
    print("✓ Short footnote matches expected format")
    print()

    print("=" * 80)
    print("BIBLIOGRAPHY:")
    print("-" * 80)
    print(citation.bibliography)
    print()
    assert citation.bibliography == expected_bibliography, "Bibliography mismatch"
    print("✓ Bibliography matches expected format")
    print()

    print("=" * 80)
    print("ALL TESTS PASSED")
    print("=" * 80)


if __name__ == "__main__":
    test_george_iams_1930_manual()
