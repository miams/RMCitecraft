#!/usr/bin/env python3
"""
Test draft registration scraper with real URLs from spreadsheet.

Prerequisites:
    - Chrome must be running with remote debugging on port 9222
    - Logged into FamilySearch in that Chrome instance
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import openpyxl
from loguru import logger

from rmcitecraft.services.familysearch_draft_scraper import FamilySearchDraftScraper
from rmcitecraft.services.ancestrylibrary_draft_scraper import AncestryLibraryDraftScraper
from rmcitecraft.database.draft_registration_db import get_draft_repository


async def main():
    """Test scraper with sample URLs."""
    # Read spreadsheet to get sample URLs
    xlsx_path = Path(__file__).parent.parent / "ww2_draft_updated.xlsx"
    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    sheet = wb.active

    # Find column indexes
    headers = [cell.value for cell in sheet[1]]
    citation_col = headers.index("familysearch_citation") + 1  # 1-indexed
    rin_col = headers.index("rin") + 1

    # Find sample URLs from all three sources
    fs_1_1_urls = []
    fs_3_1_urls = []
    ancestry_urls = []

    for row in sheet.iter_rows(min_row=2, max_row=500):  # Check first 500 rows
        citation = row[citation_col - 1].value
        rin = row[rin_col - 1].value

        if citation and isinstance(citation, str):
            if "/ark:/61903/1:1:" in citation and len(fs_1_1_urls) < 1:
                # Extract URL from citation text
                import re
                url_match = re.search(r'https://www\.familysearch\.org/ark:/61903/1:1:[A-Z0-9-]+', citation)
                if url_match:
                    fs_1_1_urls.append((rin, url_match.group(0)))
            elif "https://www.familysearch.org/ark:/61903/3:1:" in citation and len(fs_3_1_urls) < 1:
                fs_3_1_urls.append((rin, citation.strip()))
            elif "ancestrylibrary.com" in citation.lower() and len(ancestry_urls) < 1:
                import re
                url_match = re.search(r'https://www\.ancestrylibrary\.com/[^\s\)]+', citation)
                if url_match:
                    ancestry_urls.append((rin, url_match.group(0)))

        if len(fs_1_1_urls) >= 1 and len(fs_3_1_urls) >= 1 and len(ancestry_urls) >= 1:
            break

    wb.close()

    logger.info(f"Found {len(fs_1_1_urls)} FS 1:1, {len(fs_3_1_urls)} FS 3:1, {len(ancestry_urls)} Ancestry URLs")

    # Initialize scraper and repository
    scraper = FamilySearchDraftScraper(download_dir=Path("/tmp/draft_test"))
    repo = get_draft_repository()

    connected = await scraper.connect()
    if not connected:
        logger.error("Failed to connect to Chrome CDP")
        logger.error("\nMake sure Chrome is running:")
        logger.error("  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\")
        logger.error("      --remote-debugging-port=9222 \\")
        logger.error("      --no-first-run \\")
        logger.error("      --user-data-dir=~/.chrome-debug-profile")
        return

    # Create test batch
    batch_id = repo.create_batch(
        source="familysearch",
        url_type="fs_1_1_person",
        notes="Test scraping session"
    )
    logger.info(f"Created batch {batch_id}")

    try:
        # Test 1:1 person ARK
        if fs_1_1_urls:
            logger.info("\n" + "="*60)
            logger.info("Testing FamilySearch 1:1 Person ARK")
            logger.info("="*60)
            rin, url = fs_1_1_urls[0]
            logger.info(f"RIN: {rin}")
            logger.info(f"URL: {url}")

            registration, image_path = await scraper.scrape_and_download(url)

            if registration:
                logger.info("\n✅ Metadata extracted:")
                logger.info(f"  Full Name: {registration.full_name}")
                logger.info(f"  Birth Date: {registration.birth_date}")
                logger.info(f"  Birth Place: {registration.birth_place}")
                logger.info(f"  Residence: {registration.registration_place}")
                logger.info(f"  Employer: {registration.employer_name}")
                logger.info(f"  Race: {registration.race}")
                logger.info(f"  Height: {registration.height}, Weight: {registration.weight}")
                logger.info(f"  Complexion: {registration.complexion}")
                logger.info(f"  Eyes: {registration.eye_color}, Hair: {registration.hair_color}")
                logger.info(f"  Registration Date: {registration.registration_date}")
                logger.info(f"  Collection: {registration.collection_name}")

                # Save to database
                registration.batch_id = batch_id
                if image_path:
                    registration.image_downloaded = 1
                    registration.image_file_path = str(image_path)

                reg_id = repo.insert_registration(registration)
                logger.info(f"\n✅ Saved to database with ID: {reg_id}")

                # Create RMTree link
                from rmcitecraft.database.draft_registration_db import RMTreeLink
                link = RMTreeLink(
                    registration_id=reg_id,
                    rmtree_person_id=rin,
                    match_method="rin_match",
                )
                link_id = repo.insert_rmtree_link(link)
                logger.info(f"✅ Linked to RIN {rin} (link_id={link_id})")

            else:
                logger.error("❌ Failed to extract metadata")

            if image_path:
                logger.info(f"\n✅ Image downloaded: {image_path}")
                logger.info(f"   File size: {image_path.stat().st_size / 1024:.1f} KB")
            else:
                logger.error("❌ Failed to download image")

        # Test 3:1 image ARK
        if fs_3_1_urls:
            logger.info("\n" + "="*60)
            logger.info("Testing FamilySearch 3:1 Image ARK")
            logger.info("="*60)
            rin, url = fs_3_1_urls[0]
            logger.info(f"RIN: {rin}")
            logger.info(f"URL: {url}")

            registration, image_path = await scraper.scrape_and_download(url)

            if registration:
                logger.info("\n✅ Minimal metadata extracted:")
                logger.info(f"  Full Name: {registration.full_name}")
                logger.info(f"  State: {registration.residence_state}")
                logger.info(f"  Collection: {registration.collection_name}")

                registration.batch_id = batch_id
                if image_path:
                    registration.image_downloaded = 1
                    registration.image_file_path = str(image_path)

                reg_id = repo.insert_registration(registration)
                logger.info(f"\n✅ Saved to database with ID: {reg_id}")

            if image_path:
                logger.info(f"\n✅ Image downloaded: {image_path}")
                logger.info(f"   File size: {image_path.stat().st_size / 1024:.1f} KB")
            else:
                logger.error("❌ Failed to download image")

        # Test Ancestry Library
        if ancestry_urls:
            logger.info("\n" + "="*60)
            logger.info("Testing AncestryLibrary Record")
            logger.info("="*60)
            rin, url = ancestry_urls[0]
            logger.info(f"RIN: {rin}")
            logger.info(f"URL: {url}")

            ancestry_scraper = AncestryLibraryDraftScraper()  # Gets config from settings
            connected = await ancestry_scraper.connect()

            if not connected:
                logger.error("❌ Failed to connect to Chrome for Ancestry scraper")
            else:
                try:
                    registration, image_path = await ancestry_scraper.scrape_and_download(url)

                    if registration:
                        logger.info("\n✅ Metadata extracted:")
                        logger.info(f"  Full Name: {registration.full_name}")
                        logger.info(f"  Birth Date: {registration.birth_date}")
                        logger.info(f"  Birth Place: {registration.birth_place}")
                        logger.info(f"  Residence: {registration.residence_city}, {registration.residence_state}")
                        logger.info(f"  Employer: {registration.employer_name}")
                        logger.info(f"  Race: {registration.race}")
                        logger.info(f"  Height: {registration.height}, Weight: {registration.weight}")
                        logger.info(f"  NARA: {registration.nara_location}")
                        logger.info(f"  Record Group: {registration.record_group}")
                        logger.info(f"  Box: {registration.box_number}")
                        logger.info(f"  Collection: {registration.collection_name}")

                        registration.batch_id = batch_id
                        if image_path:
                            registration.image_downloaded = 1
                            registration.image_file_path = str(image_path)

                        reg_id = repo.insert_registration(registration)
                        logger.info(f"\n✅ Saved to database with ID: {reg_id}")

                    if image_path:
                        logger.info(f"\n✅ Image downloaded: {image_path}")
                        logger.info(f"   File size: {image_path.stat().st_size / 1024:.1f} KB")
                    else:
                        logger.error("❌ Failed to download image")

                finally:
                    await ancestry_scraper.disconnect()

        # Complete batch
        repo.complete_batch(batch_id, len(fs_1_1_urls) + len(fs_3_1_urls) + len(ancestry_urls))

        # Show statistics
        logger.info("\n" + "="*60)
        logger.info("Database Statistics")
        logger.info("="*60)
        stats = repo.get_statistics()
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")

    finally:
        await scraper.disconnect()
        logger.info("\n✅ Test complete!")


if __name__ == "__main__":
    asyncio.run(main())
