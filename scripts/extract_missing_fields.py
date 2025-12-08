#!/usr/bin/env python3
"""
Script to extract missing fields from FamilySearch for migrated records.

Records created by migrate_validated_matches.py have limited data (only what
was captured in match_attempt). This script uses the FamilySearch ARK to fetch
full census data and update the census_person records.

Prerequisites:
- Chrome must be running with remote debugging on port 9222
- User must be logged into FamilySearch

Run with: uv run python scripts/extract_missing_fields.py
"""

import asyncio
import sqlite3
from datetime import datetime
from pathlib import Path

from loguru import logger


def get_census_db_path() -> Path:
    """Get the census.db path."""
    return Path.home() / ".rmcitecraft" / "census.db"


def get_records_needing_extraction(limit: int = 100) -> list[dict]:
    """Get census_person records that need more data extracted.

    Returns records that:
    - Were created by migration (have limited data)
    - Have a FamilySearch ARK
    - Are missing key fields like line_number, age, sex, occupation, etc.
    """
    db_path = get_census_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Records from migration typically have:
    # - full_name, given_name, surname (from match_attempt)
    # - familysearch_ark (from match_attempt)
    # - relationship_to_head, age, birthplace (partial, from match_attempt)
    # Missing: occupation, marital_status, line_number (often NULL), sex, etc.

    cursor = conn.execute("""
        SELECT
            person_id,
            page_id,
            full_name,
            familysearch_ark,
            line_number,
            sex,
            occupation,
            marital_status,
            extracted_at
        FROM census_person
        WHERE familysearch_ark IS NOT NULL
          AND familysearch_ark != ''
          AND (
              line_number IS NULL
              OR sex IS NULL OR sex = ''
              OR occupation IS NULL OR occupation = ''
          )
        ORDER BY person_id DESC
        LIMIT ?
    """, (limit,))

    records = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return records


async def extract_and_update_record(person_id: int, ark: str) -> dict:
    """Extract data from FamilySearch and update census_person record.

    Args:
        person_id: The census_person_id to update
        ark: The FamilySearch ARK URL

    Returns:
        Dict with extraction result
    """
    from rmcitecraft.services.familysearch_census_extractor import (
        FamilySearchCensusExtractor,
    )

    result = {
        "person_id": person_id,
        "ark": ark,
        "success": False,
        "error": None,
        "fields_updated": [],
    }

    try:
        extractor = FamilySearchCensusExtractor()
        await extractor.connect()

        # Navigate to the person page and extract data
        page = await extractor.automation.get_or_create_page()
        if not page:
            result["error"] = "Could not get browser page"
            return result

        # Navigate to the ARK
        normalized_ark = ark if ark.startswith("http") else f"https://www.familysearch.org/ark:/61903/{ark}"
        await page.goto(normalized_ark, wait_until="domcontentloaded", timeout=15000)

        # Wait for content to load
        try:
            await page.locator("h1").first.wait_for(state="visible", timeout=10000)
        except Exception:
            pass

        # Extract data from the person page
        extracted_data = await extractor._extract_from_details_page(page, None)

        if not extracted_data:
            result["error"] = "Could not extract data from page"
            return result

        # Build update query
        db_path = get_census_db_path()
        conn = sqlite3.connect(db_path)

        updates = []
        params = []

        # Map extracted fields to database columns
        field_mappings = {
            "line_number": "line_number",
            "sex": "sex",
            "occupation": "occupation",
            "marital_status": "marital_status",
            "birthplace": "birthplace",
            "birthplace_father": "birthplace_father",
            "birthplace_mother": "birthplace_mother",
            "race": "race",
        }

        for extract_key, db_column in field_mappings.items():
            value = extracted_data.get(extract_key)
            if value:
                updates.append(f"{db_column} = ?")
                params.append(value)
                result["fields_updated"].append(db_column)

        if updates:
            params.append(person_id)
            sql = f"UPDATE census_person SET {', '.join(updates)} WHERE person_id = ?"
            conn.execute(sql, params)
            conn.commit()
            result["success"] = True
            logger.info(f"Updated person {person_id}: {result['fields_updated']}")
        else:
            result["error"] = "No new data to update"

        conn.close()

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Error extracting {ark}: {e}")

    return result


async def run_extraction(limit: int = 10, dry_run: bool = False) -> dict:
    """Run extraction for records needing more data.

    Args:
        limit: Maximum records to process
        dry_run: If True, just report what would be done

    Returns:
        Stats dict
    """
    stats = {
        "total_needing_extraction": 0,
        "processed": 0,
        "success": 0,
        "errors": 0,
        "error_messages": [],
    }

    records = get_records_needing_extraction(limit=limit)
    stats["total_needing_extraction"] = len(records)

    logger.info(f"Found {len(records)} records needing extraction")

    if dry_run:
        logger.info("DRY RUN - No changes will be made")
        for rec in records:
            logger.info(f"  Would extract: {rec['full_name']} (person_id={rec['person_id']}, "
                       f"ark={rec['familysearch_ark'][:50]}...)")
        return stats

    for rec in records:
        logger.info(f"Extracting: {rec['full_name']} (person_id={rec['person_id']})")
        result = await extract_and_update_record(rec["person_id"], rec["familysearch_ark"])
        stats["processed"] += 1

        if result["success"]:
            stats["success"] += 1
        else:
            stats["errors"] += 1
            if result["error"]:
                stats["error_messages"].append(f"{rec['full_name']}: {result['error']}")

        # Small delay to avoid rate limiting
        await asyncio.sleep(1)

    return stats


def main():
    """Run the extraction."""
    import argparse

    parser = argparse.ArgumentParser(description="Extract missing fields from FamilySearch")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without making changes")
    parser.add_argument("--limit", type=int, default=10,
                        help="Maximum records to process (default: 10)")
    args = parser.parse_args()

    logger.info("Starting missing field extraction...")
    stats = asyncio.run(run_extraction(limit=args.limit, dry_run=args.dry_run))

    print("\n=== Extraction Summary ===")
    print(f"Records needing extraction: {stats['total_needing_extraction']}")
    print(f"Processed: {stats['processed']}")
    print(f"Success: {stats['success']}")
    print(f"Errors: {stats['errors']}")
    if stats.get("error_messages"):
        print("Error details:")
        for err in stats["error_messages"]:
            print(f"  - {err}")


if __name__ == "__main__":
    main()
