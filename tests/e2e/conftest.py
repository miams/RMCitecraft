"""
Pytest fixtures for E2E tests.

These tests require:
1. Chrome running with remote debugging on port 9222
2. User manually logged into FamilySearch in Chrome
3. Real FamilySearch URLs (stored in test_data.py)
"""

import asyncio
from pathlib import Path

import pytest
from loguru import logger

from rmcitecraft.services.familysearch_automation import FamilySearchAutomation


# Note: No custom event_loop fixture needed - pytest-asyncio handles it automatically
# Custom event loops can cause issues with Playwright's async operations


@pytest.fixture(scope="function")
async def automation_service():
    """
    Provide FamilySearch automation service connected to Chrome.

    Requires Chrome to be running with remote debugging:
        /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\
            --remote-debugging-port=9222 \\
            --user-data-dir="$HOME/Library/Application Support/Google/Chrome-RMCitecraft"
    """
    automation = FamilySearchAutomation()

    # Try to connect to Chrome
    logger.info("E2E Test: Attempting to connect to Chrome...")
    connected = await automation.connect_to_chrome()

    if not connected:
        pytest.skip(
            "Chrome not running with remote debugging. "
            "Launch Chrome with: --remote-debugging-port=9222"
        )

    logger.info("E2E Test: Successfully connected to Chrome")

    yield automation

    # Cleanup
    logger.info("E2E Test: Disconnecting from Chrome")
    await automation.disconnect()


@pytest.fixture
def temp_download_dir(tmp_path):
    """Provide temporary directory for download tests."""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    return download_dir


@pytest.fixture
def cleanup_downloads(temp_download_dir):
    """Clean up downloaded files after test."""
    yield temp_download_dir

    # Remove all files in download directory
    for file in temp_download_dir.glob("*"):
        try:
            file.unlink()
        except Exception as e:
            logger.warning(f"Failed to delete {file}: {e}")


# Test URLs - Update these with real FamilySearch URLs
# These should be census records you have access to
TEST_URLS = {
    "1900_census_record": "https://www.familysearch.org/ark:/61903/1:1:MM6X-FGZ",
    "1900_census_image_viewer": "https://www.familysearch.org/ark:/61903/3:1:S3HT-DC17-RCM",
    "1940_census_record": "https://familysearch.org/ark:/61903/1:1:KQ7P-538",
    "1940_census_image_viewer": "https://www.familysearch.org/ark:/61903/3:1:3QS7-L9MT-RHHD",
}


@pytest.fixture
def test_urls():
    """Provide test URLs for FamilySearch records."""
    return TEST_URLS


@pytest.fixture(autouse=True)
def skip_if_chrome_not_available(request):
    """Skip tests if Chrome is not available."""
    # Only apply to tests marked with @pytest.mark.e2e
    if "e2e" in request.keywords:
        from rmcitecraft.utils.chrome_launcher import is_chrome_running_with_debugging

        if not is_chrome_running_with_debugging():
            pytest.skip(
                "Chrome not running with remote debugging. "
                "Run: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome "
                "--remote-debugging-port=9222 "
                '--user-data-dir="$HOME/Library/Application Support/Google/Chrome-RMCitecraft"'
            )
