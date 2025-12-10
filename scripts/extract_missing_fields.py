#!/usr/bin/env python3
"""
Script to extract missing fields from FamilySearch for migrated records.

Records created by migrate_validated_matches.py have limited data (only what
was captured in match_attempt). This script uses the FamilySearch ARK to fetch
full census data and update the census_person records.

Prerequisites:
- Chrome must be running with remote debugging on port 9222
- User must be logged into FamilySearch

Run with: uv run python scripts/extract_missing_fields.py --dry-run
         uv run python scripts/extract_missing_fields.py --limit 10
"""

import asyncio
import contextlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger
from playwright.async_api import Page, async_playwright

# Field mappings from FamilySearch labels to normalized names
# (subset of mappings from familysearch_census_extractor.py)
FIELD_MAPPINGS: dict[str, str] = {
    "name": "name",
    "given name": "given_name",
    "surname": "surname",
    "name suffix": "name_suffix",
    "race": "race",
    "sex": "sex",
    "age": "age",
    "relationship to head of household": "relationship_to_head",
    "relationship to head": "relationship_to_head",
    "marital status": "marital_status",
    "birthplace": "birthplace",
    "birth place": "birthplace",
    "father's birth place": "birthplace_father",
    "father's birthplace": "birthplace_father",
    "mother's birth place": "birthplace_mother",
    "mother's birthplace": "birthplace_mother",
    "occupation": "occupation",
    "industry": "industry",
    "worker class": "worker_class",
    "class of worker": "worker_class",
    "line number": "line_number",
    "source line number": "line_number",
}


@dataclass
class ExtractionResult:
    """Result of extracting data for a person."""

    person_id: int
    ark: str
    full_name: str
    success: bool
    error: str | None
    fields_updated: list[str]
    extracted_name: str | None = None
    name_match: bool = False


def get_census_db_path() -> Path:
    """Get the census.db path."""
    return Path.home() / ".rmcitecraft" / "census.db"


def get_records_needing_extraction(limit: int = 100) -> list[dict]:
    """Get census_person records that need more data extracted.

    Returns records that:
    - Have a FamilySearch ARK
    - Are missing sex (the most reliable extraction indicator - FamilySearch always has it)

    We use sex as the primary indicator because:
    - FamilySearch always has sex data for census records
    - Some records legitimately have no occupation (children, housewives)
    - Some records may not have line_number in FamilySearch
    """
    db_path = get_census_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    cursor = conn.execute(
        """
        SELECT
            person_id,
            page_id,
            full_name,
            familysearch_ark,
            line_number,
            sex,
            occupation,
            marital_status,
            birthplace,
            birthplace_father,
            birthplace_mother,
            race
        FROM census_person
        WHERE familysearch_ark IS NOT NULL
          AND familysearch_ark != ''
          AND (sex IS NULL OR sex = '')
        ORDER BY person_id DESC
        LIMIT ?
    """,
        (limit,),
    )

    records = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return records


def normalize_name(name: str) -> str:
    """Normalize a name for comparison."""
    if not name:
        return ""
    # Lowercase, collapse whitespace, remove punctuation
    normalized = " ".join(name.lower().split())
    for char in ".,'-":
        normalized = normalized.replace(char, "")
    return normalized


def names_match(name1: str, name2: str) -> bool:
    """Check if two names are similar enough to be the same person."""
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)

    if not n1 or not n2:
        return False

    # Exact match after normalization
    if n1 == n2:
        return True

    # Check if one contains the other (handles middle name variations)
    if n1 in n2 or n2 in n1:
        return True

    # Split into parts and check overlap
    parts1 = set(n1.split())
    parts2 = set(n2.split())

    if len(parts1) == 0 or len(parts2) == 0:
        return False

    # At least 2 name parts must match, or all parts of the shorter name
    common = parts1 & parts2
    min_parts = min(len(parts1), len(parts2))
    required_matches = min(2, min_parts)

    return len(common) >= required_matches


async def extract_from_person_page(page: Page) -> dict[str, Any]:
    """Extract data from a FamilySearch person ARK page.

    The person ARK page has a table with key fields including Line Number
    which is NOT available on the detail view.
    """
    data: dict[str, Any] = {}

    try:
        # Extract from table rows (th/td pairs)
        table_rows = page.locator("table tr")
        row_count = await table_rows.count()
        logger.debug(f"Found {row_count} table rows")

        for i in range(row_count):
            row = table_rows.nth(i)
            th = row.locator("th").first
            td = row.locator("td").first

            if await th.count() > 0 and await td.count() > 0:
                try:
                    label = (await th.inner_text()).strip()
                    # Try to get value from strong tag first, then plain td
                    strong = td.locator("strong")
                    if await strong.count() > 0:
                        value = (await strong.first.inner_text()).strip()
                    else:
                        value = (await td.inner_text()).strip()

                    if label and len(label) < 50 and value:
                        key = label.lower().replace(" ", "_")
                        normalized_key = FIELD_MAPPINGS.get(label.lower(), key)
                        if normalized_key not in data and value:
                            data[normalized_key] = value
                            logger.debug(
                                f"Extracted: {label} = {value[:50] if len(value) > 50 else value}"
                            )
                except Exception as e:
                    logger.debug(f"Error extracting row {i}: {e}")
    except Exception as e:
        logger.warning(f"Table extraction failed: {e}")

    return data


async def navigate_to_detail_view(page: Page) -> bool:
    """Navigate from person ARK page to detail view."""
    try:
        # Look for "View Original Document" button
        button = page.locator('a:has-text("View Original Document")').first
        if await button.count() > 0:
            await button.click()
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(1500)  # Give dynamic content time to load
            return True

        # Try alternate button text
        button2 = page.locator('a:has-text("View Record")').first
        if await button2.count() > 0:
            await button2.click()
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(1500)
            return True

    except Exception as e:
        logger.debug(f"Could not navigate to detail view: {e}")

    return False


async def extract_from_detail_view(page: Page) -> dict[str, Any]:
    """Extract additional data from detail view (data-dense elements)."""
    data: dict[str, Any] = {}

    try:
        # Wait for detail panel to load
        await page.wait_for_timeout(1000)

        # Extract from data-dense elements
        dense_elements = page.locator("div[data-dense]")
        dense_count = await dense_elements.count()
        logger.debug(f"Found {dense_count} data-dense elements")

        for i in range(dense_count):
            try:
                elem = dense_elements.nth(i)
                text = (await elem.inner_text()).strip()
                # Parse "Label: Value" pattern
                if ":" in text and len(text) < 200:
                    parts = text.split(":", 1)
                    if len(parts) == 2:
                        label = parts[0].strip()
                        value = parts[1].strip()
                        if (
                            label
                            and value
                            and len(label) < 50
                            and not label.lower().startswith(
                                ("http", "click", "save", "names", "manage")
                            )
                        ):
                            key = label.lower().replace(" ", "_")
                            normalized_key = FIELD_MAPPINGS.get(label.lower(), key)
                            if normalized_key not in data:
                                data[normalized_key] = value
                                logger.debug(
                                    f"Detail view: {label} = {value[:50] if len(value) > 50 else value}"
                                )
            except Exception as e:
                logger.debug(f"Error extracting dense element {i}: {e}")
    except Exception as e:
        logger.debug(f"Detail view extraction failed: {e}")

    return data


async def extract_person_data(page: Page, ark: str) -> dict[str, Any]:
    """Full extraction flow for a person.

    1. Navigate to person ARK page
    2. Extract table data (has line number)
    3. Navigate to detail view
    4. Extract additional fields from detail view
    """
    # Normalize ARK URL
    if not ark.startswith("http"):
        ark = f"https://www.familysearch.org/ark:/61903/{ark}"

    logger.info(f"Navigating to: {ark}")

    try:
        await page.goto(ark, wait_until="domcontentloaded", timeout=20000)
    except Exception as e:
        logger.error(f"Failed to navigate to {ark}: {e}")
        return {}

    # Wait for content
    with contextlib.suppress(Exception):
        await page.locator("h1").first.wait_for(state="visible", timeout=10000)

    # Check if we're on a person page (1:1:xxxx format)
    current_url = page.url
    on_person_page = "view=index" not in current_url and "/1:1:" in current_url

    all_data: dict[str, Any] = {}

    if on_person_page:
        # Step 1: Extract from person page (has line number!)
        logger.info("On person ARK page, extracting table data...")
        person_data = await extract_from_person_page(page)
        all_data.update(person_data)

        # Step 2: Navigate to detail view for more fields
        logger.info("Navigating to detail view...")
        if await navigate_to_detail_view(page):
            logger.info("On detail view, extracting additional fields...")
            detail_data = await extract_from_detail_view(page)
            # Merge, but don't overwrite person page data
            for k, v in detail_data.items():
                if k not in all_data:
                    all_data[k] = v
        else:
            logger.warning("Could not navigate to detail view")
    else:
        # Already on detail view or unknown page type
        logger.info("Not on person ARK page, trying direct extraction...")
        detail_data = await extract_from_detail_view(page)
        all_data.update(detail_data)

    return all_data


async def extract_and_update_record(
    page: Page, record: dict, dry_run: bool = False
) -> ExtractionResult:
    """Extract data from FamilySearch and update census_person record.

    Args:
        page: Playwright page object
        record: Dict with person_id, full_name, familysearch_ark, etc.
        dry_run: If True, don't actually update the database

    Returns:
        ExtractionResult with details
    """
    person_id = record["person_id"]
    ark = record["familysearch_ark"]
    full_name = record["full_name"]

    result = ExtractionResult(
        person_id=person_id,
        ark=ark,
        full_name=full_name,
        success=False,
        error=None,
        fields_updated=[],
    )

    try:
        # Extract data from FamilySearch
        extracted_data = await extract_person_data(page, ark)

        if not extracted_data:
            result.error = "Could not extract any data from page"
            return result

        # Get extracted name for verification
        extracted_name = extracted_data.get("name", "")
        result.extracted_name = extracted_name

        # CRITICAL: Verify name matches before updating
        if extracted_name:
            result.name_match = names_match(full_name, extracted_name)
            if not result.name_match:
                result.error = f"Name mismatch: DB='{full_name}' vs FS='{extracted_name}'"
                logger.warning(f"Skipping person {person_id}: {result.error}")
                return result
            logger.info(f"Name verified: '{full_name}' matches '{extracted_name}'")
        else:
            logger.warning(f"Could not verify name for person {person_id} (no name extracted)")
            # Continue anyway if we have other useful data

        # Map extracted fields to database columns
        field_mappings = {
            "line_number": ("line_number", lambda v: int(v) if v and v.isdigit() else None),
            "sex": ("sex", lambda v: v),
            "occupation": ("occupation", lambda v: v),
            "marital_status": ("marital_status", lambda v: v),
            "birthplace": ("birthplace", lambda v: v),
            "birthplace_father": ("birthplace_father", lambda v: v),
            "birthplace_mother": ("birthplace_mother", lambda v: v),
            "race": ("race", lambda v: v),
        }

        updates = []
        params = []

        for extract_key, (db_column, converter) in field_mappings.items():
            # Only update if current value is NULL or empty
            current_value = record.get(db_column)
            if current_value is not None and current_value != "":
                continue  # Already has data

            raw_value = extracted_data.get(extract_key)
            if raw_value:
                converted = converter(raw_value)
                if converted:
                    updates.append(f"{db_column} = ?")
                    params.append(converted)
                    result.fields_updated.append(db_column)

        if not updates:
            result.error = (
                "No new data to update (all fields already populated or no data extracted)"
            )
            result.success = True  # Not an error, just nothing to do
            return result

        if dry_run:
            logger.info(
                f"DRY RUN: Would update person {person_id} ({full_name}): {result.fields_updated}"
            )
            result.success = True
            return result

        # Perform update
        db_path = get_census_db_path()
        conn = sqlite3.connect(db_path)
        try:
            params.append(person_id)
            sql = f"UPDATE census_person SET {', '.join(updates)} WHERE person_id = ?"
            conn.execute(sql, params)
            conn.commit()
            result.success = True
            logger.info(f"Updated person {person_id} ({full_name}): {result.fields_updated}")
        except Exception as e:
            conn.rollback()
            result.error = f"Database error: {e}"
            logger.error(f"Failed to update person {person_id}: {e}")
        finally:
            conn.close()

    except Exception as e:
        result.error = str(e)
        logger.error(f"Error extracting {ark}: {e}")

    return result


async def run_extraction(
    limit: int = 10, dry_run: bool = False, delay_seconds: float = 2.0
) -> dict:
    """Run extraction for records needing more data.

    Args:
        limit: Maximum records to process
        dry_run: If True, just report what would be done
        delay_seconds: Delay between extractions to avoid rate limiting

    Returns:
        Stats dict
    """
    stats = {
        "total_needing_extraction": 0,
        "processed": 0,
        "success": 0,
        "updated": 0,
        "name_mismatches": 0,
        "errors": 0,
        "error_messages": [],
    }

    records = get_records_needing_extraction(limit=limit)
    stats["total_needing_extraction"] = len(records)

    logger.info(f"Found {len(records)} records needing extraction")

    if not records:
        return stats

    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made to the database")

    # Connect to existing Chrome instance
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            logger.info("Connected to Chrome via CDP")
        except Exception as e:
            logger.error(f"Could not connect to Chrome: {e}")
            logger.error(
                "Make sure Chrome is running with: "
                "/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome "
                "--remote-debugging-port=9222"
            )
            stats["errors"] = len(records)
            stats["error_messages"].append(f"Chrome connection failed: {e}")
            return stats

        # Get or create a page
        contexts = browser.contexts
        if contexts:
            pages = contexts[0].pages
            if pages:
                page = pages[0]
                logger.info(f"Using existing page: {page.url[:50]}...")
            else:
                page = await contexts[0].new_page()
                logger.info("Created new page in existing context")
        else:
            logger.error("No browser contexts found")
            stats["errors"] = len(records)
            stats["error_messages"].append("No browser contexts available")
            return stats

        for i, rec in enumerate(records):
            logger.info(
                f"[{i + 1}/{len(records)}] Processing: {rec['full_name']} (person_id={rec['person_id']})"
            )
            result = await extract_and_update_record(page, rec, dry_run=dry_run)
            stats["processed"] += 1

            if result.success:
                stats["success"] += 1
                if result.fields_updated:
                    stats["updated"] += 1
            else:
                if result.error and "mismatch" in result.error.lower():
                    stats["name_mismatches"] += 1
                else:
                    stats["errors"] += 1
                if result.error:
                    stats["error_messages"].append(f"{rec['full_name']}: {result.error}")

            # Delay between extractions
            if i < len(records) - 1:
                await asyncio.sleep(delay_seconds)

    return stats


def main():
    """Run the extraction."""
    import argparse

    parser = argparse.ArgumentParser(description="Extract missing fields from FamilySearch")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--limit", type=int, default=10, help="Maximum records to process (default: 10)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay between extractions in seconds (default: 2.0)",
    )
    args = parser.parse_args()

    logger.info("Starting missing field extraction...")
    logger.info(f"Options: limit={args.limit}, dry_run={args.dry_run}, delay={args.delay}s")

    stats = asyncio.run(
        run_extraction(limit=args.limit, dry_run=args.dry_run, delay_seconds=args.delay)
    )

    print("\n" + "=" * 50)
    print("EXTRACTION SUMMARY")
    print("=" * 50)
    print(f"Records needing extraction: {stats['total_needing_extraction']}")
    print(f"Processed: {stats['processed']}")
    print(f"Successful: {stats['success']}")
    print(f"Actually updated: {stats['updated']}")
    print(f"Name mismatches (skipped): {stats['name_mismatches']}")
    print(f"Errors: {stats['errors']}")

    if stats.get("error_messages"):
        print("\nError details:")
        for err in stats["error_messages"][:10]:  # Show first 10
            print(f"  - {err}")
        if len(stats["error_messages"]) > 10:
            print(f"  ... and {len(stats['error_messages']) - 10} more")

    print("=" * 50)


if __name__ == "__main__":
    main()
