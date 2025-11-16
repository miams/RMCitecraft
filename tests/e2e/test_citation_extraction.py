"""
E2E tests for citation data extraction from FamilySearch pages.

These tests navigate to real FamilySearch census records and extract
structured citation data.

PREREQUISITES:
- Chrome running with remote debugging (port 9222)
- User manually logged into FamilySearch in Chrome
- Real census record URLs (see conftest.py TEST_URLS)
"""

import pytest
from loguru import logger

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_extract_citation_from_1900_census(automation_service, test_urls):
    """Test extracting citation data from 1900 census record."""
    url = test_urls["1900_census_record"]

    logger.info(f"Testing extraction from: {url}")

    citation_data = await automation_service.extract_citation_data(url)

    # Verify extraction succeeded
    assert citation_data is not None

    # Verify required fields are present
    assert "personName" in citation_data
    assert "eventDate" in citation_data
    assert "eventPlace" in citation_data
    assert "arkUrl" in citation_data
    assert "pageTitle" in citation_data

    # Verify data makes sense
    assert len(citation_data["personName"]) > 0
    assert "1900" in citation_data["eventDate"] or "1900" in citation_data["pageTitle"]
    assert len(citation_data["arkUrl"]) > 0

    logger.info(f"Extracted: {citation_data['personName']} - {citation_data['eventDate']}")
    logger.info(f"Location: {citation_data['eventPlace']}")


@pytest.mark.asyncio
async def test_extract_citation_from_1940_census(automation_service, test_urls):
    """Test extracting citation data from 1940 census record."""
    url = test_urls["1940_census_record"]

    logger.info(f"Testing extraction from: {url}")

    citation_data = await automation_service.extract_citation_data(url)

    # Verify extraction succeeded
    assert citation_data is not None

    # Verify census year
    assert "1940" in citation_data["eventDate"] or "1940" in citation_data["pageTitle"]

    logger.info(f"Extracted: {citation_data['personName']} - {citation_data['eventDate']}")


@pytest.mark.asyncio
async def test_extract_finds_image_viewer_url(automation_service, test_urls):
    """Test that extraction includes image viewer URL."""
    url = test_urls["1900_census_record"]

    citation_data = await automation_service.extract_citation_data(url)

    assert citation_data is not None
    assert "imageViewerUrl" in citation_data

    # Image viewer URL should be present and valid
    if citation_data["imageViewerUrl"]:
        assert "familysearch.org" in citation_data["imageViewerUrl"]
        assert "/ark:/61903/3:1:" in citation_data["imageViewerUrl"]
        logger.info(f"Image viewer URL: {citation_data['imageViewerUrl']}")
    else:
        logger.warning("No image viewer URL found (record may not have image)")


@pytest.mark.asyncio
async def test_extract_handles_page_loading(automation_service, test_urls):
    """Test that extraction waits for page to fully load."""
    url = test_urls["1900_census_record"]

    # Navigate to page
    citation_data = await automation_service.extract_citation_data(url)

    assert citation_data is not None

    # Page should be fully loaded
    page = await automation_service.get_or_create_page()
    assert page.url.startswith("https://www.familysearch.org")

    # Page title should be populated
    assert len(citation_data["pageTitle"]) > 0
    assert "Census" in citation_data["pageTitle"] or "census" in citation_data["pageTitle"].lower()

    logger.info(f"Page loaded: {citation_data['pageTitle']}")


@pytest.mark.asyncio
async def test_extract_multiple_records_sequentially(automation_service, test_urls):
    """Test extracting data from multiple records in sequence."""
    urls = [
        test_urls["1900_census_record"],
        test_urls["1940_census_record"],
    ]

    results = []

    for url in urls:
        logger.info(f"Extracting from: {url}")
        citation_data = await automation_service.extract_citation_data(url)
        assert citation_data is not None
        results.append(citation_data)

    assert len(results) == 2

    # Verify both extractions succeeded
    for result in results:
        assert len(result["personName"]) > 0
        assert len(result["eventDate"]) > 0

    logger.info(f"Successfully extracted {len(results)} citations")


@pytest.mark.asyncio
async def test_extract_handles_invalid_url(automation_service):
    """Test that extraction handles invalid URLs gracefully."""
    invalid_url = "https://www.familysearch.org/invalid-record-xyz"

    citation_data = await automation_service.extract_citation_data(invalid_url)

    # Should return data even if page doesn't exist (may be empty)
    # or return None if navigation fails
    if citation_data:
        logger.info("Extraction returned data for invalid URL (404 page?)")
    else:
        logger.info("Extraction returned None for invalid URL")


@pytest.mark.asyncio
async def test_extract_familysearch_entry_text(automation_service, test_urls):
    """Test extracting FamilySearch citation entry text."""
    url = test_urls["1900_census_record"]

    citation_data = await automation_service.extract_citation_data(url)

    assert citation_data is not None
    assert "familySearchEntry" in citation_data

    # FamilySearch entry should be substantial text
    if citation_data["familySearchEntry"]:
        assert len(citation_data["familySearchEntry"]) > 50
        logger.info(f"FamilySearch entry length: {len(citation_data['familySearchEntry'])} chars")
    else:
        logger.warning("No FamilySearch citation entry found on page")


@pytest.mark.asyncio
async def test_extract_preserves_page_state(automation_service, test_urls):
    """Test that extraction doesn't close or navigate away from page."""
    url = test_urls["1900_census_record"]

    # Extract data
    citation_data = await automation_service.extract_citation_data(url)
    assert citation_data is not None

    # Page should still be open at the same URL
    page = await automation_service.get_or_create_page()
    assert page is not None
    assert url.split("?")[0] in page.url  # Ignore query params

    logger.info("Page state preserved after extraction")


@pytest.mark.asyncio
async def test_extract_performance(automation_service, test_urls):
    """Test that extraction completes in reasonable time."""
    import time

    url = test_urls["1900_census_record"]

    start_time = time.time()
    citation_data = await automation_service.extract_citation_data(url)
    elapsed = time.time() - start_time

    assert citation_data is not None
    assert elapsed < 30  # Should complete within 30 seconds

    logger.info(f"Extraction completed in {elapsed:.2f} seconds")


@pytest.mark.asyncio
async def test_extract_event_date_formats(automation_service, test_urls):
    """Test that extraction handles various event date formats."""
    url = test_urls["1900_census_record"]

    citation_data = await automation_service.extract_citation_data(url)

    assert citation_data is not None

    # Event date should contain census year
    event_date = citation_data.get("eventDate", "")
    page_title = citation_data.get("pageTitle", "")

    # Census year should appear somewhere
    assert (
        "1900" in event_date
        or "1900" in page_title
        or "1900" in citation_data.get("familySearchEntry", "")
    )

    logger.info(f"Event date format: {event_date}")
