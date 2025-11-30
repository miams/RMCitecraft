#!/usr/bin/env python
"""
End-to-end test for FamilySearch census extraction.

This test extracts census data from a known FamilySearch ARK URL
and verifies the data is stored correctly in census.db.

Usage:
    # Run with pytest
    uv run pytest tests/e2e/test_familysearch_census_extraction.py -v -s

    # Or run directly (requires Chrome with FamilySearch login)
    uv run python tests/e2e/test_familysearch_census_extraction.py
"""

import asyncio
import sys
from pathlib import Path

import pytest
from loguru import logger

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rmcitecraft.database.census_extraction_db import (
    CENSUS_DB_PATH,
    CensusExtractionRepository,
    get_census_repository,
)
from rmcitecraft.services.familysearch_census_extractor import (
    ExtractionResult,
    FamilySearchCensusExtractor,
    display_extraction_result,
    extract_census_from_citation,
)


# Test data - 1950 Census record for Larry W Ijams
TEST_ARK_URL = "https://www.familysearch.org/ark:/61903/1:1:6XKG-DP65"
TEST_CENSUS_YEAR = 1950
TEST_CITATION_ID = 10370
TEST_PERSON_ID = 2776  # RIN in RootsMagic

# Expected values from FamilySearch
EXPECTED_VALUES = {
    "given_name": "Larry",
    "surname": "Ijams",
    "sex": "M",
    "race": "W",
    "age": 34,
    "marital_status": "Mar",
    "birthplace": "Ariz",
    "occupation": "Asst Manager",
    "relationship_to_head": "Head",
}


class TestFamilySearchExtraction:
    """Test suite for FamilySearch census extraction."""

    @pytest.fixture
    def repository(self, tmp_path):
        """Create a test repository with temporary database."""
        db_path = tmp_path / "test_census.db"
        return CensusExtractionRepository(db_path)

    @pytest.mark.asyncio
    async def test_extraction_connects_to_chrome(self):
        """Test that we can connect to Chrome."""
        extractor = FamilySearchCensusExtractor()
        try:
            connected = await extractor.connect()
            # This may fail if Chrome isn't running - that's expected in CI
            if connected:
                logger.info("Successfully connected to Chrome")
            else:
                pytest.skip("Chrome not available - run setup_chrome_login.py first")
        finally:
            await extractor.disconnect()

    @pytest.mark.asyncio
    async def test_full_extraction(self, repository):
        """Test full extraction workflow."""
        extractor = FamilySearchCensusExtractor(repository=repository)

        try:
            connected = await extractor.connect()
            if not connected:
                pytest.skip("Chrome not available")

            # Check login status
            logged_in = await extractor.automation.check_login_status()
            if not logged_in:
                pytest.skip("Not logged into FamilySearch - run setup_chrome_login.py")

            # Perform extraction
            extractor.start_batch("Test extraction")
            result = await extractor.extract_from_ark(
                TEST_ARK_URL,
                TEST_CENSUS_YEAR,
                rmtree_citation_id=TEST_CITATION_ID,
                rmtree_person_id=TEST_PERSON_ID,
            )
            extractor.complete_batch()

            # Verify result
            assert result.success, f"Extraction failed: {result.error_message}"
            assert result.person_id is not None
            assert result.page_id is not None

            # Verify data in database
            person = repository.get_person_by_ark(TEST_ARK_URL)
            assert person is not None
            assert person.familysearch_ark == TEST_ARK_URL

            # Check expected values
            for field, expected in EXPECTED_VALUES.items():
                actual = getattr(person, field, None)
                if actual is not None:
                    logger.info(f"  {field}: expected={expected}, actual={actual}")

            # Verify RootsMagic link
            links = repository.get_links_for_citation(TEST_CITATION_ID)
            assert len(links) > 0
            assert links[0].rmtree_citation_id == TEST_CITATION_ID

            logger.info("Full extraction test passed!")
            display_extraction_result(result)

        finally:
            await extractor.disconnect()

    def test_repository_operations(self, repository):
        """Test basic repository CRUD operations."""
        from rmcitecraft.database.census_extraction_db import (
            CensusPage,
            CensusPerson,
            FieldQuality,
        )

        # Create batch
        batch_id = repository.create_batch("Test batch")
        assert batch_id > 0

        # Create page
        page = CensusPage(
            batch_id=batch_id,
            census_year=1950,
            state="Arizona",
            county="Maricopa",
            township_city="Phoenix",
            enumeration_district="7-283",
            page_number="32",
            stamp_number="32",
        )
        page_id = repository.insert_page(page)
        assert page_id > 0

        # Create person
        person = CensusPerson(
            page_id=page_id,
            line_number=28,
            full_name="Larry W Ijams",
            given_name="Larry",
            surname="Ijams",
            sex="M",
            race="W",
            age=34,
            marital_status="Mar",
            birthplace="Ariz",
            occupation="Asst Manager",
            familysearch_ark=TEST_ARK_URL,
            is_target_person=True,
        )
        person_id = repository.insert_person(person)
        assert person_id > 0

        # Add extended fields
        extended = {
            "income": "402",
            "weeks_worked": "50",
            "same_house_1949": "Yes",
            "veteran": "No",
        }
        repository.insert_person_fields_bulk(person_id, extended)

        # Verify extended fields
        fields = repository.get_person_fields(person_id)
        assert fields["income"] == "402"
        assert fields["weeks_worked"] == "50"

        # Add quality assessment
        quality = FieldQuality(
            person_id=person_id,
            field_name="occupation",
            confidence_score=0.85,
            source_legibility="clear",
            transcription_note="Abbreviated as 'Asst'",
        )
        quality_id = repository.insert_field_quality(quality)
        assert quality_id > 0

        # Verify quality
        qualities = repository.get_field_quality(person_id)
        assert len(qualities) == 1
        assert qualities[0].field_name == "occupation"
        assert qualities[0].confidence_score == 0.85

        # Test search
        results = repository.search_persons(surname="Ijams")
        assert len(results) == 1
        assert results[0].given_name == "Larry"

        # Get stats
        stats = repository.get_extraction_stats()
        assert stats["total_persons"] == 1
        assert stats["total_pages"] == 1

        logger.info("Repository operations test passed!")


async def run_manual_extraction():
    """Run a manual extraction for testing outside pytest."""
    logger.info("=" * 60)
    logger.info("FamilySearch Census Extraction Test")
    logger.info("=" * 60)
    logger.info(f"ARK URL: {TEST_ARK_URL}")
    logger.info(f"Census Year: {TEST_CENSUS_YEAR}")
    logger.info(f"Database: {CENSUS_DB_PATH}")
    logger.info("=" * 60)

    result = await extract_census_from_citation(
        TEST_ARK_URL,
        TEST_CENSUS_YEAR,
        rmtree_citation_id=TEST_CITATION_ID,
        rmtree_person_id=TEST_PERSON_ID,
        rmtree_database="data/Iiams.rmtree",
    )

    display_extraction_result(result)

    if result.success:
        # Show what's in the database
        repo = get_census_repository()
        stats = repo.get_extraction_stats()
        logger.info(f"\nDatabase Stats: {stats}")

        # Show the person record
        person = repo.get_person_by_ark(TEST_ARK_URL)
        if person:
            logger.info(f"\nPerson Record:")
            logger.info(f"  Name: {person.full_name}")
            logger.info(f"  Age: {person.age}")
            logger.info(f"  Birthplace: {person.birthplace}")
            logger.info(f"  Occupation: {person.occupation}")

            # Show extended fields
            fields = repo.get_person_fields(person.person_id)
            if fields:
                logger.info(f"\nExtended Fields ({len(fields)}):")
                for name, value in sorted(fields.items()):
                    logger.info(f"  {name}: {value}")

    return result


if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level="INFO")

    # Run extraction
    result = asyncio.run(run_manual_extraction())
    sys.exit(0 if result.success else 1)
