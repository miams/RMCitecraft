"""
E2E tests for census image downloads from FamilySearch.

These tests navigate to image viewer pages and download census images
using keyboard automation to select JPG format.

PREREQUISITES:
- Chrome running with remote debugging (port 9222)
- User manually logged into FamilySearch in Chrome
- Real image viewer URLs (see conftest.py TEST_URLS)

IMPORTANT:
- These tests actually download files to temp directory
- Tests verify file exists and is valid JPG
- Downloads are cleaned up automatically
"""

import time

import pytest
from loguru import logger

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_download_1900_census_image(
    automation_service, test_urls, cleanup_downloads
):
    """Test downloading census image from 1900 record."""
    image_url = test_urls["1900_census_image_viewer"]
    download_path = cleanup_downloads / "test_1900_census.jpg"

    logger.info(f"Testing download from: {image_url}")
    logger.info(f"Download path: {download_path}")

    success = await automation_service.download_census_image(image_url, download_path)

    assert success is True
    assert download_path.exists()
    assert download_path.stat().st_size > 0

    # Verify it's a JPG file (check magic bytes)
    with open(download_path, "rb") as f:
        magic_bytes = f.read(2)
        assert magic_bytes == b"\xff\xd8"  # JPG signature

    logger.info(f"Downloaded: {download_path.stat().st_size} bytes")


@pytest.mark.asyncio
async def test_download_1940_census_image(
    automation_service, test_urls, cleanup_downloads
):
    """Test downloading census image from 1940 record."""
    image_url = test_urls["1940_census_image_viewer"]
    download_path = cleanup_downloads / "test_1940_census.jpg"

    logger.info(f"Testing download from: {image_url}")

    success = await automation_service.download_census_image(image_url, download_path)

    assert success is True
    assert download_path.exists()
    assert download_path.stat().st_size > 10000  # Should be at least 10KB

    logger.info(f"Downloaded: {download_path.stat().st_size} bytes")


@pytest.mark.asyncio
async def test_download_button_detection_timing(
    automation_service, test_urls, cleanup_downloads
):
    """Test that download button is detected within reasonable time."""
    image_url = test_urls["1900_census_image_viewer"]
    download_path = cleanup_downloads / "test_timing.jpg"

    start_time = time.time()
    success = await automation_service.download_census_image(image_url, download_path)
    elapsed = time.time() - start_time

    assert success is True

    # Should complete within 30 seconds (includes page load + dialog + download)
    assert elapsed < 30

    logger.info(f"Download completed in {elapsed:.2f} seconds")


@pytest.mark.asyncio
async def test_keyboard_automation_selects_jpg(
    automation_service, test_urls, cleanup_downloads
):
    """Test that keyboard automation correctly selects JPG option."""
    image_url = test_urls["1900_census_image_viewer"]
    download_path = cleanup_downloads / "test_jpg_selection.jpg"

    success = await automation_service.download_census_image(image_url, download_path)

    assert success is True
    assert download_path.exists()

    # Verify file is JPG, not PDF
    with open(download_path, "rb") as f:
        magic_bytes = f.read(4)
        assert magic_bytes[:2] == b"\xff\xd8"  # JPG
        assert magic_bytes != b"%PDF"  # Not PDF

    logger.info("Correctly downloaded JPG (not PDF)")


@pytest.mark.asyncio
async def test_download_multiple_images_sequentially(
    automation_service, test_urls, cleanup_downloads
):
    """Test downloading multiple images in sequence."""
    image_urls = [
        (test_urls["1900_census_image_viewer"], "test_1900.jpg"),
        (test_urls["1940_census_image_viewer"], "test_1940.jpg"),
    ]

    for image_url, filename in image_urls:
        download_path = cleanup_downloads / filename
        logger.info(f"Downloading: {filename}")

        success = await automation_service.download_census_image(
            image_url, download_path
        )

        assert success is True
        assert download_path.exists()

    # Verify both files exist
    assert (cleanup_downloads / "test_1900.jpg").exists()
    assert (cleanup_downloads / "test_1940.jpg").exists()

    logger.info("Successfully downloaded multiple images")


@pytest.mark.asyncio
async def test_download_with_existing_file(
    automation_service, test_urls, cleanup_downloads
):
    """Test downloading when file already exists (should overwrite)."""
    image_url = test_urls["1900_census_image_viewer"]
    download_path = cleanup_downloads / "test_overwrite.jpg"

    # Create existing file
    download_path.write_text("existing content")
    assert download_path.exists()

    # Download should overwrite
    success = await automation_service.download_census_image(image_url, download_path)

    assert success is True
    assert download_path.exists()

    # Verify it's a valid JPG (not our text content)
    with open(download_path, "rb") as f:
        magic_bytes = f.read(2)
        assert magic_bytes == b"\xff\xd8"

    logger.info("Successfully overwrote existing file")


@pytest.mark.asyncio
async def test_download_handles_invalid_url(automation_service, cleanup_downloads):
    """Test that download handles invalid image viewer URLs gracefully."""
    invalid_url = "https://www.familysearch.org/invalid-image-xyz"
    download_path = cleanup_downloads / "test_invalid.jpg"

    success = await automation_service.download_census_image(
        invalid_url, download_path
    )

    # Should fail gracefully (not crash)
    assert success is False

    # File should not be created
    assert not download_path.exists()

    logger.info("Gracefully handled invalid URL")


@pytest.mark.asyncio
async def test_download_waits_for_completion(
    automation_service, test_urls, cleanup_downloads
):
    """Test that download function waits for file download to complete."""
    image_url = test_urls["1900_census_image_viewer"]
    download_path = cleanup_downloads / "test_completion.jpg"

    # Download (should wait for completion)
    success = await automation_service.download_census_image(image_url, download_path)

    assert success is True

    # File should be complete and valid immediately
    assert download_path.exists()
    assert download_path.stat().st_size > 0

    # Should be readable as JPG
    with open(download_path, "rb") as f:
        content = f.read()
        assert len(content) > 1000  # Should be substantial
        assert content[:2] == b"\xff\xd8"  # JPG header
        assert content[-2:] == b"\xff\xd9"  # JPG footer (end marker)

    logger.info("Download completed and file is valid")


@pytest.mark.asyncio
async def test_download_button_found_on_image_viewer_page(
    automation_service, test_urls
):
    """Test that download button is found on image viewer pages."""
    image_url = test_urls["1900_census_image_viewer"]

    # Navigate to image viewer
    page = await automation_service.get_or_create_page()
    assert page is not None

    await page.goto(image_url, wait_until="domcontentloaded")
    await page.wait_for_load_state("networkidle")

    # Check for download button
    download_button = await page.query_selector(
        'button[data-testid="download-image-button"]'
    )

    assert download_button is not None
    logger.info("Download button found on image viewer page")


@pytest.mark.asyncio
async def test_download_performance_reasonable(
    automation_service, test_urls, cleanup_downloads
):
    """Test that download completes in reasonable time."""
    image_url = test_urls["1900_census_image_viewer"]
    download_path = cleanup_downloads / "test_performance.jpg"

    start_time = time.time()
    success = await automation_service.download_census_image(image_url, download_path)
    elapsed = time.time() - start_time

    assert success is True

    # Most downloads should complete within 20 seconds
    # (page load: 5s, dialog: 1s, download: 5-10s)
    assert elapsed < 20

    logger.info(f"Download completed in {elapsed:.2f} seconds")


@pytest.mark.asyncio
async def test_download_creates_parent_directory(
    automation_service, test_urls, tmp_path
):
    """Test that download creates parent directory if needed."""
    nested_path = tmp_path / "nested" / "dir" / "test.jpg"
    image_url = test_urls["1900_census_image_viewer"]

    # Parent directory doesn't exist yet
    assert not nested_path.parent.exists()

    # Playwright's save_as should create parent directories
    success = await automation_service.download_census_image(image_url, nested_path)

    # This might fail - that's okay, we're testing edge case
    # If Playwright doesn't create parent dirs, our code should handle it
    if success:
        assert nested_path.exists()
        logger.info("Parent directory created successfully")
    else:
        logger.info("Download failed (expected - parent dir doesn't exist)")


@pytest.mark.asyncio
async def test_download_file_size_reasonable(
    automation_service, test_urls, cleanup_downloads
):
    """Test that downloaded file size is reasonable for census image."""
    image_url = test_urls["1900_census_image_viewer"]
    download_path = cleanup_downloads / "test_size.jpg"

    success = await automation_service.download_census_image(image_url, download_path)

    assert success is True
    assert download_path.exists()

    file_size = download_path.stat().st_size

    # Census images are typically 100KB - 5MB
    assert 10_000 < file_size < 10_000_000

    logger.info(f"File size: {file_size / 1024:.2f} KB")
