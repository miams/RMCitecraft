"""Test script for database connection and citation repository."""

from loguru import logger

from src.rmcitecraft.repositories import CitationRepository, DatabaseConnection

logger.add("logs/test_db.log", rotation="1 MB")


def main() -> None:
    """Test database connection and citation queries."""
    print("=" * 80)
    print("Testing RootsMagic Database Connection")
    print("=" * 80)

    # Test database connection
    print("\n1. Testing database connection...")
    db = DatabaseConnection()

    if db.test_connection():
        print("   ✓ Database connection successful")
    else:
        print("   ✗ Database connection failed")
        return

    # Test citation repository
    print("\n2. Testing citation repository...")
    citation_repo = CitationRepository(db)

    # Get all census years
    print("\n3. Getting all census years in database...")
    years = citation_repo.get_all_census_years()
    print(f"   Found {len(years)} census years: {years}")

    # Get citations for 1900
    if 1900 in years:
        print("\n4. Getting citations for 1900...")
        citations_1900 = citation_repo.get_citations_by_year(1900)
        print(f"   Found {len(citations_1900)} citations for 1900")

        if citations_1900:
            print("\n5. Sample citation:")
            citation = citations_1900[0]
            print(f"   Citation ID: {citation['CitationID']}")
            print(f"   Source Name: {citation['SourceName']}")
            print(f"   Actual Text: {citation['ActualText'][:100]}...")

            # Get full citation details
            full_citation = citation_repo.get_citation_by_id(citation["CitationID"])
            if full_citation:
                print("\n6. Full citation details:")
                print(f"   Has Footnote: {bool(full_citation['Footnote'])}")
                print(f"   Has ShortFootnote: {bool(full_citation['ShortFootnote'])}")
                print(f"   Has Bibliography: {bool(full_citation['Bibliography'])}")
                print(
                    f"   Has Media: {citation_repo.citation_has_media(citation['CitationID'])}"
                )

    print("\n" + "=" * 80)
    print("✓ All database tests completed successfully")
    print("=" * 80)

    db.close()


if __name__ == "__main__":
    main()
