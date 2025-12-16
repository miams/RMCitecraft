"""Integration test for household member extraction.

This test verifies that:
1. Household members are correctly extracted from FamilySearch
2. RM persons filter correctly matches household members
3. rmtree_links are created for matched members
"""

import asyncio
import sqlite3
from pathlib import Path

import pytest
from loguru import logger

# Test configuration
CENSUS_DB_PATH = Path.home() / ".rmcitecraft" / "census.db"
RMTREE_PATH = Path("/Users/miams/Code/RMCitecraft/data/Iiams.rmtree")
ICU_EXTENSION = Path("/Users/miams/Code/RMCitecraft/sqlite-extension/icu.dylib")


def get_test_sources(limit: int = 3) -> list[tuple[int, str]]:
    """Get test source IDs from RootsMagic that have multiple persons sharing a census event."""
    from rmcitecraft.services.census_rmtree_matcher import CensusRMTreeMatcher

    matcher = CensusRMTreeMatcher(RMTREE_PATH, ICU_EXTENSION)

    # Get sources with 2+ persons (family households)
    sources_with_family = []

    # Query for 1950 census sources with multiple persons
    with sqlite3.connect(RMTREE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT DISTINCT s.SourceID, s.Name
            FROM SourceTable s
            WHERE s.Name LIKE '%1950%census%'
            ORDER BY s.SourceID
            LIMIT 50
        """).fetchall()

        for row in rows:
            source_id = row["SourceID"]
            persons, _, _ = matcher.get_rm_persons_for_source(source_id)
            if len(persons) >= 2:
                sources_with_family.append((source_id, row["Name"], len(persons)))
                if len(sources_with_family) >= limit:
                    break

    logger.info(f"Found {len(sources_with_family)} sources with 2+ persons")
    for sid, name, count in sources_with_family:
        logger.info(f"  Source {sid}: {count} persons - {name[:60]}...")

    return [(s[0], s[1]) for s in sources_with_family]


def clear_test_data(source_ids: list[int]) -> None:
    """Clear census.db data for test sources."""
    if not CENSUS_DB_PATH.exists():
        return

    with sqlite3.connect(CENSUS_DB_PATH) as conn:
        for source_id in source_ids:
            # Get batch_id for this source
            batch_rows = conn.execute(
                "SELECT batch_id FROM extraction_batch WHERE rmtree_citation_id = ?",
                (source_id,)
            ).fetchall()

            for (batch_id,) in batch_rows:
                # Get page_ids for this batch
                page_ids = [r[0] for r in conn.execute(
                    "SELECT page_id FROM census_page WHERE batch_id = ?",
                    (batch_id,)
                ).fetchall()]

                for page_id in page_ids:
                    # Get person_ids for this page
                    person_ids = [r[0] for r in conn.execute(
                        "SELECT person_id FROM census_person WHERE page_id = ?",
                        (page_id,)
                    ).fetchall()]

                    for person_id in person_ids:
                        conn.execute(
                            "DELETE FROM census_person_field WHERE person_id = ?",
                            (person_id,)
                        )
                        conn.execute(
                            "DELETE FROM rmtree_link WHERE census_person_id = ?",
                            (person_id,)
                        )

                    conn.execute(
                        "DELETE FROM census_person WHERE page_id = ?",
                        (page_id,)
                    )

                conn.execute(
                    "DELETE FROM census_page WHERE batch_id = ?",
                    (batch_id,)
                )

            conn.execute(
                "DELETE FROM extraction_batch WHERE rmtree_citation_id = ?",
                (source_id,)
            )

        conn.commit()
    logger.info(f"Cleared census.db data for sources: {source_ids}")


def verify_extraction_results(source_id: int, expected_persons: int) -> dict:
    """Verify extraction results for a source."""
    results = {
        "source_id": source_id,
        "expected_persons": expected_persons,
        "extracted_persons": 0,
        "rmtree_links": 0,
        "target_persons": 0,
        "success": False,
    }

    if not CENSUS_DB_PATH.exists():
        return results

    with sqlite3.connect(CENSUS_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        # Get batch for this source
        batch = conn.execute(
            "SELECT batch_id FROM extraction_batch WHERE rmtree_citation_id = ?",
            (source_id,)
        ).fetchone()

        if not batch:
            return results

        batch_id = batch["batch_id"]

        # Get pages and persons
        pages = conn.execute(
            "SELECT page_id FROM census_page WHERE batch_id = ?",
            (batch_id,)
        ).fetchall()

        for page in pages:
            page_id = page["page_id"]
            persons = conn.execute(
                "SELECT person_id, full_name, is_target_person FROM census_person WHERE page_id = ?",
                (page_id,)
            ).fetchall()

            results["extracted_persons"] += len(persons)
            results["target_persons"] += sum(1 for p in persons if p["is_target_person"])

            # Count rmtree_links
            for person in persons:
                link = conn.execute(
                    "SELECT 1 FROM rmtree_link WHERE census_person_id = ?",
                    (person["person_id"],)
                ).fetchone()
                if link:
                    results["rmtree_links"] += 1

    # Success if we extracted at least as many as expected and have links
    results["success"] = (
        results["extracted_persons"] >= expected_persons
        and results["rmtree_links"] >= expected_persons
    )

    return results


@pytest.mark.asyncio
async def test_household_extraction_with_rm_filter():
    """Test that household members are extracted when RM filter is active."""
    from rmcitecraft.services.census_transcription_batch import CensusTranscriptionBatchService
    from rmcitecraft.services.census_rmtree_matcher import CensusRMTreeMatcher

    # Get test sources
    test_sources = get_test_sources(limit=2)
    if not test_sources:
        pytest.skip("No test sources with multiple persons found")

    source_ids = [s[0] for s in test_sources]

    # Clear old data
    clear_test_data(source_ids)

    # Get expected person counts
    matcher = CensusRMTreeMatcher(RMTREE_PATH, ICU_EXTENSION)
    expected_counts = {}
    for source_id, _ in test_sources:
        persons, _, _ = matcher.get_rm_persons_for_source(source_id)
        expected_counts[source_id] = len(persons)
        logger.info(f"Source {source_id}: expecting {len(persons)} persons")

    # Run extraction
    batch_service = CensusTranscriptionBatchService()

    # Build queue for test sources
    from rmcitecraft.services.census_transcription_batch import QueueItem
    queue_items = []
    for source_id, name in test_sources:
        queue_items.append(QueueItem(
            rmtree_citation_id=source_id,
            source_name=name,
            person_name="Test",
            surname="Test",
            state="",
            county="",
            census_year=1950,
        ))

    # Create session and process
    session_id = batch_service.create_session_from_queue(queue_items, census_year=1950)

    def on_progress(completed, total, name):
        logger.info(f"Progress: {completed}/{total} - {name}")

    result = await batch_service.process_batch(session_id, on_progress=on_progress)

    logger.info(f"Batch result: {result.completed} completed, {result.errors} errors")

    # Verify results
    all_success = True
    for source_id in source_ids:
        expected = expected_counts[source_id]
        verification = verify_extraction_results(source_id, expected)
        logger.info(
            f"Source {source_id}: extracted={verification['extracted_persons']}, "
            f"links={verification['rmtree_links']}, expected={expected}, "
            f"success={verification['success']}"
        )
        if not verification["success"]:
            all_success = False

    assert all_success, "Not all sources were extracted successfully with household members"


if __name__ == "__main__":
    # Run manually for debugging
    asyncio.run(test_household_extraction_with_rm_filter())
