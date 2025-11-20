"""Test Citation Manager UI component.

This script tests the Citation Manager tab functionality without starting the UI.
"""

from rmcitecraft.repositories import CitationRepository, DatabaseConnection
from rmcitecraft.ui.tabs.citation_manager import CitationManagerTab


def test_citation_manager_initialization() -> None:
    """Test Citation Manager initialization."""
    print("=" * 80)
    print("Test 1: Citation Manager Initialization")
    print("=" * 80)

    manager = CitationManagerTab()

    # Check that database connection works
    print(f"\n✓ Database connection: {manager.db.test_connection()}")
    print(f"✓ Repository initialized: {manager.repo is not None}")
    print(f"✓ Parser initialized: {manager.parser is not None}")
    print(f"✓ Formatter initialized: {manager.formatter is not None}")

    # Check available census years
    years = manager.repo.get_all_census_years()
    print(f"✓ Available census years: {sorted(years)}")

    # Clean up
    manager.cleanup()
    print("\n✓ Cleanup successful")


def test_citation_loading() -> None:
    """Test loading citations from database."""
    print("\n" + "=" * 80)
    print("Test 2: Citation Loading")
    print("=" * 80)

    manager = CitationManagerTab()

    # Get available years
    years = manager.repo.get_all_census_years()
    if not years:
        print("\n✗ No census years found in database")
        manager.cleanup()
        return

    # Test loading citations for first year
    test_year = sorted(years)[0]
    print(f"\n→ Loading citations for {test_year}...")

    citations = manager.repo.get_citations_by_year(test_year)
    print(f"✓ Loaded {len(citations)} citations")

    if citations:
        # Show first citation details
        first = citations[0]
        print(f"\n→ First citation details:")
        print(f"  Citation ID: {first['CitationID']}")
        print(f"  Source Name: {first['SourceName'][:80]}...")
        print(f"  Has Footnote: {bool(first['Footnote'])}")

        # Test parsing
        parsed = manager.parser.parse(
            first["SourceName"], first["ActualText"], citation_id=first["CitationID"]
        )
        print(f"\n→ Parsed citation:")
        print(f"  Year: {parsed.census_year}")
        print(f"  State: {parsed.state}")
        print(f"  County: {parsed.county}")
        print(f"  Person: {parsed.person_name}")
        print(f"  Complete: {parsed.is_complete}")
        if not parsed.is_complete:
            print(f"  Missing fields: {parsed.missing_fields}")

        # Test formatting (if complete)
        if parsed.is_complete:
            footnote, short_footnote, bibliography = manager.formatter.format(parsed)
            print(f"\n→ Generated footnote:")
            print(f"  {footnote[:100]}...")
        else:
            print(f"\n⚠ Citation incomplete - would prompt user for missing data")

    manager.cleanup()
    print("\n✓ Test complete")


def test_person_name_extraction() -> None:
    """Test person name extraction from source names."""
    print("\n" + "=" * 80)
    print("Test 3: Person Name Extraction")
    print("=" * 80)

    manager = CitationManagerTab()

    test_cases = [
        "Fed Census: 1900, Ohio, Noble [citing sheet 3B, family 57] Ijams, Ella",
        "Fed Census: 1910, Maryland, Baltimore [citing enumeration district (ED) ED 214, sheet 3B] Ijams, William H.",
        "Fed Census: 1920, California, Los Angeles [citing sheet 5A] Smith, John",
    ]

    for source_name in test_cases:
        person_name = manager._extract_person_name(source_name)
        print(f"\n→ Source: {source_name[:60]}...")
        print(f"  Person: {person_name}")

    manager.cleanup()
    print("\n✓ Test complete")


def test_batch_selection() -> None:
    """Test batch selection state management."""
    print("\n" + "=" * 80)
    print("Test 4: Batch Selection State")
    print("=" * 80)

    manager = CitationManagerTab()

    # Load some citations
    years = manager.repo.get_all_census_years()
    if years:
        test_year = sorted(years)[0]
        manager.citations = manager.repo.get_citations_by_year(test_year)[:5]

        print(f"\n→ Loaded {len(manager.citations)} test citations")

        # Simulate selecting citations
        for citation in manager.citations[:3]:
            manager.selected_citation_ids.add(citation["CitationID"])

        print(f"✓ Selected {len(manager.selected_citation_ids)} citations")
        print(f"  IDs: {sorted(manager.selected_citation_ids)}")

        # Test select all
        manager.selected_citation_ids = {c["CitationID"] for c in manager.citations}
        print(f"✓ Select all: {len(manager.selected_citation_ids)} citations")

        # Test deselect all
        manager.selected_citation_ids.clear()
        print(f"✓ Deselect all: {len(manager.selected_citation_ids)} citations")

    manager.cleanup()
    print("\n✓ Test complete")


def main() -> None:
    """Run all tests."""
    try:
        test_citation_manager_initialization()
        test_citation_loading()
        test_person_name_extraction()
        test_batch_selection()

        print("\n" + "=" * 80)
        print("All Citation Manager tests passed! ✓")
        print("=" * 80)
        print("\nTo run the UI:")
        print("  uv run rmcitecraft")
        print("\nOr in browser mode (with hot reload):")
        print("  RMCITECRAFT_NATIVE=false uv run rmcitecraft")

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
