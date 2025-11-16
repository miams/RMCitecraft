"""
E2E tests for complete citation + image workflow.

These tests simulate the full user workflow:
1. Connect to Chrome
2. Navigate to FamilySearch census record
3. Extract citation data
4. Download census image
5. Verify all data is correct

PREREQUISITES:
- Chrome running with remote debugging (port 9222)
- User manually logged into FamilySearch in Chrome
- Real census record URLs (see conftest.py TEST_URLS)
"""

import time

import pytest
from loguru import logger

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_complete_workflow_1900_census(
    automation_service, test_urls, cleanup_downloads
):
    """Test complete workflow: extract + download for 1900 census."""
    record_url = test_urls["1900_census_record"]
    download_path = cleanup_downloads / "workflow_1900.jpg"

    logger.info("=== Starting Complete Workflow Test ===")
    logger.info(f"Record URL: {record_url}")

    # Execute complete workflow
    start_time = time.time()
    citation_data = await automation_service.extract_and_download(
        record_url, download_path
    )
    elapsed = time.time() - start_time

    # Verify citation data extracted
    assert citation_data is not None
    assert citation_data["personName"]
    assert citation_data["eventDate"]
    assert citation_data["eventPlace"]
    assert citation_data["imageViewerUrl"]

    # Verify image downloaded
    assert citation_data["image_downloaded"] is True
    assert download_path.exists()
    assert download_path.stat().st_size > 10000

    logger.info(f"✓ Extracted: {citation_data['personName']}")
    logger.info(f"✓ Date: {citation_data['eventDate']}")
    logger.info(f"✓ Place: {citation_data['eventPlace']}")
    logger.info(f"✓ Image: {download_path.stat().st_size} bytes")
    logger.info(f"✓ Completed in {elapsed:.2f} seconds")


@pytest.mark.asyncio
async def test_complete_workflow_1940_census(
    automation_service, test_urls, cleanup_downloads
):
    """Test complete workflow: extract + download for 1940 census."""
    record_url = test_urls["1940_census_record"]
    download_path = cleanup_downloads / "workflow_1940.jpg"

    logger.info("=== Starting Complete Workflow Test (1940) ===")

    citation_data = await automation_service.extract_and_download(
        record_url, download_path
    )

    # Verify complete workflow
    assert citation_data is not None
    assert "1940" in citation_data["eventDate"] or "1940" in citation_data["pageTitle"]
    assert citation_data["image_downloaded"] is True
    assert download_path.exists()

    logger.info(f"✓ Workflow completed: {citation_data['personName']}")


@pytest.mark.asyncio
async def test_workflow_handles_missing_image(automation_service):
    """Test workflow when record has no image."""
    # Use a URL that might not have image (or invalid URL)
    record_url = "https://www.familysearch.org/ark:/61903/1:1:TEST"
    download_path = None  # Won't be used

    citation_data = await automation_service.extract_and_download(
        record_url, download_path
    )

    # Should handle gracefully
    if citation_data:
        assert citation_data["image_downloaded"] is False
        logger.info("Workflow handled missing image gracefully")
    else:
        logger.info("Workflow returned None for invalid record")


@pytest.mark.asyncio
async def test_workflow_performance_benchmark(
    automation_service, test_urls, cleanup_downloads
):
    """Benchmark complete workflow performance."""
    record_url = test_urls["1900_census_record"]
    download_path = cleanup_downloads / "benchmark.jpg"

    # Run workflow
    start_time = time.time()
    citation_data = await automation_service.extract_and_download(
        record_url, download_path
    )
    elapsed = time.time() - start_time

    assert citation_data is not None
    assert citation_data["image_downloaded"] is True

    # Complete workflow should finish within 45 seconds
    # (page load: 5s, extraction: 5s, navigation: 5s, download: 20s)
    assert elapsed < 45

    logger.info(f"BENCHMARK: Complete workflow took {elapsed:.2f} seconds")
    logger.info(
        f"  - Extraction + Download: {elapsed:.2f}s for {citation_data['personName']}"
    )


@pytest.mark.asyncio
async def test_workflow_multiple_records_batch(
    automation_service, test_urls, cleanup_downloads
):
    """Test processing multiple records in batch."""
    records = [
        (test_urls["1900_census_record"], "batch_1900.jpg"),
        (test_urls["1940_census_record"], "batch_1940.jpg"),
    ]

    results = []

    logger.info("=== Processing Batch of Records ===")

    for record_url, filename in records:
        download_path = cleanup_downloads / filename
        logger.info(f"Processing: {record_url}")

        citation_data = await automation_service.extract_and_download(
            record_url, download_path
        )

        assert citation_data is not None
        assert citation_data["image_downloaded"] is True
        assert download_path.exists()

        results.append(citation_data)

    assert len(results) == 2

    logger.info(f"✓ Successfully processed {len(results)} records")


@pytest.mark.asyncio
async def test_workflow_extracts_all_required_fields(
    automation_service, test_urls, cleanup_downloads
):
    """Test that workflow extracts all fields needed for RootsMagic."""
    record_url = test_urls["1900_census_record"]
    download_path = cleanup_downloads / "fields_test.jpg"

    citation_data = await automation_service.extract_and_download(
        record_url, download_path
    )

    assert citation_data is not None

    # Required fields for citation generation
    required_fields = [
        "personName",
        "eventDate",
        "eventPlace",
        "arkUrl",
        "pageTitle",
    ]

    for field in required_fields:
        assert field in citation_data
        assert citation_data[field] is not None
        logger.info(f"✓ {field}: {citation_data[field][:50]}...")

    # Optional but expected fields
    if citation_data.get("familySearchEntry"):
        logger.info(
            f"✓ familySearchEntry: {len(citation_data['familySearchEntry'])} chars"
        )

    if citation_data.get("imageViewerUrl"):
        logger.info(f"✓ imageViewerUrl: {citation_data['imageViewerUrl']}")


@pytest.mark.asyncio
async def test_workflow_image_quality_verification(
    automation_service, test_urls, cleanup_downloads
):
    """Test that downloaded image is valid and complete."""
    record_url = test_urls["1900_census_record"]
    download_path = cleanup_downloads / "quality_test.jpg"

    citation_data = await automation_service.extract_and_download(
        record_url, download_path
    )

    assert citation_data is not None
    assert citation_data["image_downloaded"] is True
    assert download_path.exists()

    # Verify JPG structure
    with open(download_path, "rb") as f:
        content = f.read()

    # Check JPG markers
    assert content[:2] == b"\xff\xd8"  # SOI (Start of Image)
    assert content[-2:] == b"\xff\xd9"  # EOI (End of Image)

    # Check reasonable file size
    assert len(content) > 10_000
    assert len(content) < 10_000_000

    logger.info(f"✓ Image quality verified: {len(content)} bytes")


@pytest.mark.asyncio
async def test_workflow_error_recovery(automation_service, test_urls):
    """Test workflow error handling and recovery."""
    # Test with invalid download path (no permission)
    import tempfile
    from pathlib import Path

    record_url = test_urls["1900_census_record"]

    # Create read-only directory (will fail to write)
    with tempfile.TemporaryDirectory() as tmpdir:
        readonly_dir = Path(tmpdir) / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)  # Read-only

        download_path = readonly_dir / "test.jpg"

        # Should handle error gracefully
        citation_data = await automation_service.extract_and_download(
            record_url, download_path
        )

        # Citation should still be extracted even if download fails
        if citation_data:
            assert citation_data["personName"]
            assert citation_data["image_downloaded"] in [False, None]
            logger.info("✓ Workflow recovered from download error")


@pytest.mark.asyncio
async def test_workflow_maintains_browser_state(
    automation_service, test_urls, cleanup_downloads
):
    """Test that workflow doesn't break browser state."""
    record_url = test_urls["1900_census_record"]
    download_path = cleanup_downloads / "state_test.jpg"

    # Run workflow
    citation_data = await automation_service.extract_and_download(
        record_url, download_path
    )

    assert citation_data is not None

    # Browser should still be connected
    assert automation_service.browser is not None
    assert len(automation_service.browser.contexts) > 0

    # Should be able to run another workflow
    download_path2 = cleanup_downloads / "state_test2.jpg"
    citation_data2 = await automation_service.extract_and_download(
        record_url, download_path2
    )

    assert citation_data2 is not None

    logger.info("✓ Browser state maintained across workflows")


@pytest.mark.asyncio
async def test_workflow_end_to_end_real_use_case(
    automation_service, test_urls, cleanup_downloads
):
    """
    Simulate real user workflow:
    1. User clicks citation in RMCitecraft UI
    2. System extracts citation data
    3. System downloads image
    4. User sees success notification
    """
    logger.info("=== Simulating Real User Workflow ===")

    # Step 1: User is on FamilySearch page (already logged in)
    logger.info("1. User viewing FamilySearch census record")
    record_url = test_urls["1900_census_record"]

    # Step 2: User clicks "Apply to Database" in RMCitecraft
    logger.info("2. User clicks 'Apply to Database'")

    # Step 3: RMCitecraft extracts data and downloads image
    logger.info("3. RMCitecraft processing...")
    download_path = cleanup_downloads / "real_workflow.jpg"

    start_time = time.time()
    citation_data = await automation_service.extract_and_download(
        record_url, download_path
    )
    elapsed = time.time() - start_time

    # Step 4: Verify success
    assert citation_data is not None
    assert citation_data["image_downloaded"] is True
    assert download_path.exists()

    logger.info("4. Success! Citation and image ready for database")
    logger.info(f"   Person: {citation_data['personName']}")
    logger.info(f"   Date: {citation_data['eventDate']}")
    logger.info(f"   Place: {citation_data['eventPlace']}")
    logger.info(f"   Image: {download_path.name} ({download_path.stat().st_size} bytes)")
    logger.info(f"   Time: {elapsed:.2f} seconds")

    # Step 5: RMCitecraft would now save to RootsMagic database
    logger.info("5. Ready to save to RootsMagic database")

    logger.info("=== Real Workflow Test Complete ===")
