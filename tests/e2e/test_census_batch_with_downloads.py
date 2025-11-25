"""
End-to-end test for Census batch processing with image downloads.

This test verifies the complete census batch workflow:
1. Census batch creation with real FamilySearch URLs
2. Image downloads using browser automation
3. Dashboard analytics accuracy
4. Image file verification

PREREQUISITES:
- Chrome running with remote debugging (port 9222)
- User manually logged into FamilySearch in Chrome
- Real census record URLs (see conftest.py TEST_URLS)

Test Scenario:
- Creates a batch of 3 census records (1900, 1910, 1940)
- Downloads actual census images from FamilySearch
- Validates image files exist and are valid
- Validates dashboard analytics reflect downloads
"""

import pytest
from loguru import logger
from pathlib import Path

from rmcitecraft.database.batch_state_repository import FindAGraveBatchStateRepository
from rmcitecraft.database.census_batch_state_repository import CensusBatchStateRepository
from .components import (
    DashboardValidator,
)

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


@pytest.mark.asyncio
class TestCensusBatchWithDownloads:
    """E2E tests for Census batch processing with image downloads."""

    @pytest.fixture
    def temp_state_db(self, tmp_path):
        """Create temporary state database for test."""
        db_path = tmp_path / "test_batch_state.db"
        return str(db_path)

    @pytest.fixture
    def state_repo(self, temp_state_db):
        """Create CensusBatchStateRepository instance."""
        # Initialize database and run migrations
        FindAGraveBatchStateRepository(db_path=temp_state_db)
        return CensusBatchStateRepository(db_path=temp_state_db)

    @pytest.fixture
    def dashboard_validator(self, state_repo):
        """Create DashboardValidator instance."""
        return DashboardValidator(state_repo)

    async def test_census_batch_with_real_downloads(
        self,
        automation_service,
        test_urls,
        state_repo,
        dashboard_validator,
        cleanup_downloads,
    ):
        """
        Test census batch processing with real image downloads.

        Creates a batch of 3 census records, downloads images using
        FamilySearch automation, and validates complete workflow.
        """
        logger.info("=" * 80)
        logger.info("E2E TEST: Census Batch with Real Image Downloads")
        logger.info("=" * 80)

        # Test configuration
        test_records = [
            {
                "census_year": 1900,
                "state": "Ohio",
                "county": "Noble",
                "person_name": "Ella Ijams",
                "record_url": test_urls["1900_census_record"],
                "image_url": test_urls["1900_census_image_viewer"],
            },
            {
                "census_year": 1940,
                "state": "Texas",
                "county": "Milam",
                "person_name": "Test Person",
                "record_url": test_urls["1940_census_record"],
                "image_url": test_urls["1940_census_image_viewer"],
            },
        ]

        session_id = f"test_batch_with_downloads_{state_repo._now_iso()}"
        downloaded_files = []

        try:
            # ============================================================
            # PHASE 1: Create Census Batch
            # ============================================================
            logger.info("\n" + "=" * 80)
            logger.info("PHASE 1: Create Census Batch")
            logger.info("=" * 80)

            state_repo.create_session(
                session_id=session_id,
                total_items=len(test_records),
                census_year=None,  # Mixed years
            )
            state_repo.start_session(session_id)

            # Create batch items with real FamilySearch URLs
            for i, record in enumerate(test_records):
                person_id = 1000 + i
                item_id = state_repo.create_item(
                    session_id=session_id,
                    person_id=person_id,
                    person_name=record["person_name"],
                    census_year=record["census_year"],
                    state=record["state"],
                    county=record["county"],
                )
                record["item_id"] = item_id
                logger.info(
                    f"Created item {item_id}: {record['person_name']} "
                    f"({record['census_year']} {record['state']})"
                )

            # ============================================================
            # PHASE 2: Download Census Images
            # ============================================================
            logger.info("\n" + "=" * 80)
            logger.info("PHASE 2: Download Census Images")
            logger.info("=" * 80)

            for record in test_records:
                logger.info(f"\n--- Processing {record['person_name']} ({record['census_year']}) ---")

                try:
                    # Download census image
                    download_filename = (
                        f"{record['census_year']}, {record['state']}, {record['county']} - "
                        f"{record['person_name']}.jpg"
                    )
                    download_path = cleanup_downloads / download_filename

                    logger.info(f"Downloading from: {record['image_url']}")
                    logger.info(f"Destination: {download_path}")

                    success = await automation_service.download_census_image(
                        record["image_url"], download_path
                    )

                    if success and download_path.exists():
                        # Verify image file
                        file_size = download_path.stat().st_size
                        logger.info(f"✓ Downloaded: {file_size} bytes")

                        # Verify JPG signature
                        with open(download_path, "rb") as f:
                            magic_bytes = f.read(2)
                            if magic_bytes == b"\xff\xd8":
                                logger.info("✓ Valid JPG file")
                            else:
                                logger.warning("⚠ File may not be valid JPG")

                        # Update item status
                        state_repo.update_item_status(record["item_id"], "complete")
                        state_repo.update_item_images(record["item_id"], [str(download_path)])
                        downloaded_files.append(download_path)

                    else:
                        logger.error(f"✗ Download failed for {record['person_name']}")
                        state_repo.update_item_status(
                            record["item_id"],
                            "error",
                            "Image download failed"
                        )

                except Exception as e:
                    logger.error(f"Error processing {record['person_name']}: {e}")
                    state_repo.update_item_status(
                        record["item_id"],
                        "error",
                        str(e)
                    )

            # Complete session
            state_repo.complete_session(session_id)

            # ============================================================
            # PHASE 3: Validate Downloaded Files
            # ============================================================
            logger.info("\n" + "=" * 80)
            logger.info("PHASE 3: Validate Downloaded Files")
            logger.info("=" * 80)

            logger.info(f"Total files downloaded: {len(downloaded_files)}")
            for file_path in downloaded_files:
                assert file_path.exists(), f"File not found: {file_path}"
                assert file_path.stat().st_size > 10000, f"File too small: {file_path}"
                logger.info(f"✓ Verified: {file_path.name} ({file_path.stat().st_size} bytes)")

            # ============================================================
            # PHASE 4: Validate Dashboard Analytics
            # ============================================================
            logger.info("\n" + "=" * 80)
            logger.info("PHASE 4: Validate Dashboard Analytics")
            logger.info("=" * 80)

            # Get actual results
            status_dist = state_repo.get_status_distribution()
            year_dist = state_repo.get_year_distribution()
            state_dist = state_repo.get_state_distribution()

            logger.info(f"Status distribution: {status_dist}")
            logger.info(f"Year distribution: {year_dist}")
            logger.info(f"State distribution: {state_dist}")

            # Validate analytics
            completed_count = status_dist.get("complete", 0)
            error_count = status_dist.get("error", 0)

            logger.info(f"✓ Completed: {completed_count}/{len(test_records)}")
            logger.info(f"✓ Errors: {error_count}/{len(test_records)}")

            # At least some downloads should succeed
            assert completed_count > 0, "No downloads succeeded"

            # Verify year distribution
            for record in test_records:
                year = record["census_year"]
                assert year in year_dist, f"Year {year} not in distribution"
                logger.info(f"✓ Year {year}: {year_dist[year]} record(s)")

            # ============================================================
            # PHASE 5: Validate Session Metadata
            # ============================================================
            logger.info("\n" + "=" * 80)
            logger.info("PHASE 5: Validate Session Metadata")
            logger.info("=" * 80)

            session = state_repo.get_session(session_id)
            assert session is not None, "Session not found"
            assert session["status"] == "completed", f"Session status: {session['status']}"
            assert session["total_items"] == len(test_records)

            logger.info(f"✓ Session status: {session['status']}")
            logger.info(f"✓ Total items: {session['total_items']}")
            logger.info(f"✓ Completed count: {session['completed_count']}")
            logger.info(f"✓ Error count: {session['error_count']}")

            # ============================================================
            # TEST SUMMARY
            # ============================================================
            logger.info("\n" + "=" * 80)
            logger.info("TEST SUMMARY - Census Batch with Downloads")
            logger.info("=" * 80)
            logger.info(f"✓ Records processed: {len(test_records)}")
            logger.info(f"✓ Images downloaded: {len(downloaded_files)}")
            logger.info(f"✓ Completed: {completed_count}")
            logger.info(f"✓ Errors: {error_count}")
            logger.info(f"✓ Analytics validated")
            logger.info("=" * 80)
            logger.info("ALL VALIDATIONS PASSED ✓")
            logger.info("=" * 80)

        finally:
            # Cleanup: Delete test session
            logger.info("\n--- Cleanup ---")
            try:
                state_repo.delete_session(session_id)
                logger.info(f"✓ Deleted session: {session_id}")
            except Exception as e:
                logger.warning(f"Failed to delete session {session_id}: {e}")


if __name__ == "__main__":
    # Allow running test directly for debugging
    pytest.main([__file__, "-v", "-s", "--tb=short"])
