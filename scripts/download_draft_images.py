#!/usr/bin/env python3
r"""
Download draft registration images for existing citations.

This script:
1. Queries the database for draft registration citations
2. Identifies citations with FamilySearch or AncestryLibrary URLs
3. Downloads images using the appropriate automation service
4. Saves combined images to the media directory

Prerequisites:
    - Chrome must be running with remote debugging on port 9222:
      /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
          --remote-debugging-port=9222 \
          --no-first-run \
          --user-data-dir=~/.chrome-debug-profile

Usage:
    python scripts/download_draft_images.py
    python scripts/download_draft_images.py --person-id 123  # Download for specific person
    python scripts/download_draft_images.py --dry-run  # Preview without downloading
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Optional, Tuple
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from loguru import logger
from rmcitecraft.config import get_config
from rmcitecraft.database.connection import connect_rmtree
from rmcitecraft.services.ancestrylibrary_automation import AncestryLibraryAutomation


def get_draft_citations(
    db_path: Path, person_id: Optional[int] = None
) -> List[Tuple[int, int, str, str, str]]:
    """
    Get draft registration citations from the database.

    Args:
        db_path: Path to RootsMagic database
        person_id: Optional PersonID to filter results

    Returns:
        List of tuples: (CitationID, PersonID, PersonName, SourceName, URL)
    """
    conn = connect_rmtree(db_path, read_only=True)
    cursor = conn.cursor()

    query = """
        SELECT
            c.CitationID,
            p.PersonID,
            n.Given || ' ' || n.Surname as PersonName,
            s.Name as SourceName,
            COALESCE(c.ActualText, c.RefNumber, s.ActualText) as URL
        FROM CitationTable c
        JOIN SourceTable s ON c.SourceID = s.SourceID
        JOIN CitationLinkTable cl ON c.CitationID = cl.CitationID AND cl.OwnerType = 0
        JOIN PersonTable p ON cl.OwnerID = p.PersonID
        JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
        WHERE (s.Name LIKE '%Draft Registration%' OR s.Name LIKE '%Selective Service%')
          AND (c.ActualText LIKE '%familysearch.org%'
               OR c.ActualText LIKE '%ancestrylibrary.com%'
               OR c.RefNumber LIKE '%familysearch.org%'
               OR c.RefNumber LIKE '%ancestrylibrary.com%'
               OR s.ActualText LIKE '%familysearch.org%'
               OR s.ActualText LIKE '%ancestrylibrary.com%')
    """

    params = []
    if person_id:
        query += " AND p.PersonID = ?"
        params.append(person_id)

    query += " ORDER BY p.PersonID, c.CitationID"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    return results


async def download_ancestrylibrary_image(
    service: AncestryLibraryAutomation,
    record_url: str,
    output_dir: Path,
    citation_id: int,
    person_name: str,
) -> Optional[Path]:
    """
    Download and combine AncestryLibrary draft registration images.

    Args:
        service: AncestryLibraryAutomation service instance
        record_url: AncestryLibrary record URL
        output_dir: Directory to save combined image
        citation_id: Citation ID for filename
        person_name: Person name for filename

    Returns:
        Path to combined image or None if failed
    """
    try:
        # Download both images
        image1_path, image2_path = await service.download_draft_images(record_url)

        if not image1_path or not image2_path:
            logger.error(f"Failed to download images for {person_name}")
            return None

        # Generate output filename
        safe_name = person_name.replace(" ", "_").replace("/", "_")
        output_filename = f"draft_reg_{citation_id}_{safe_name}.jpg"

        # Combine images
        combined_path = await service.combine_images(
            image1_path, image2_path, output_filename
        )

        if combined_path:
            # Move to output directory
            final_path = output_dir / output_filename
            combined_path.rename(final_path)
            logger.info(f"✅ Saved combined image: {final_path}")
            return final_path
        else:
            return None

    except Exception as e:
        logger.error(f"Error downloading image for {person_name}: {e}")
        return None


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Download draft registration images")
    parser.add_argument(
        "--person-id", type=int, help="Download images for specific PersonID only"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview citations without downloading",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for images (default: ~/Genealogy/RootsMagic/Files/Records - Draft)",
    )
    args = parser.parse_args()

    # Load config
    config = get_config()
    db_path = config.rm_database_path

    # Set output directory
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = (
            Path.home()
            / "Genealogy"
            / "RootsMagic"
            / "Files"
            / "Records - Draft"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")

    # Get draft citations
    logger.info("Querying database for draft registration citations...")
    citations = get_draft_citations(db_path, person_id=args.person_id)

    if not citations:
        logger.info("No draft registration citations found")
        return

    logger.info(f"Found {len(citations)} draft registration citation(s)")

    # Group by source type
    ancestrylibrary_citations = []
    familysearch_citations = []

    for citation_id, person_id, person_name, source_name, url in citations:
        if "ancestrylibrary.com" in url.lower():
            ancestrylibrary_citations.append(
                (citation_id, person_id, person_name, source_name, url)
            )
        elif "familysearch.org" in url.lower() or "ark:/" in url.lower():
            familysearch_citations.append(
                (citation_id, person_id, person_name, source_name, url)
            )

    logger.info(f"  - AncestryLibrary: {len(ancestrylibrary_citations)}")
    logger.info(f"  - FamilySearch: {len(familysearch_citations)}")

    if args.dry_run:
        logger.info("\nDry run - would download:")
        for citation_id, person_id, person_name, source_name, url in citations:
            logger.info(f"  [{citation_id}] {person_name}: {url[:80]}...")
        return

    # Download AncestryLibrary images
    if ancestrylibrary_citations:
        logger.info("\n📥 Downloading AncestryLibrary images...")

        service = AncestryLibraryAutomation(download_dir=output_dir / "temp")
        connected = await service.connect()

        if not connected:
            logger.error("❌ Failed to connect to Chrome")
            logger.error("\nMake sure Chrome is running with remote debugging:")
            logger.error("  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\")
            logger.error("      --remote-debugging-port=9222 \\")
            logger.error("      --no-first-run \\")
            logger.error("      --user-data-dir=~/.chrome-debug-profile")
            return

        successful_downloads = 0
        failed_downloads = 0
        restriction_detected = False

        try:
            for citation_id, person_id, person_name, source_name, url in ancestrylibrary_citations:
                logger.info(f"\n📄 Processing: {person_name} (CitationID={citation_id})")
                logger.info(f"   URL: {url}")

                # Extract record URL (remove query params)
                record_url = url.split("?")[0] if "?" in url else url

                result = await download_ancestrylibrary_image(
                    service, record_url, output_dir, citation_id, person_name
                )

                if result:
                    successful_downloads += 1
                else:
                    failed_downloads += 1
                    # Check if it's likely an access restriction
                    if failed_downloads == 1:
                        logger.warning("\n⚠️  First download failed - might indicate access restriction")
                        logger.warning("Continuing with remaining records...")

        finally:
            await service.disconnect()

        # Summary
        logger.info(f"\n📊 AncestryLibrary Download Summary:")
        logger.info(f"  ✅ Successful: {successful_downloads}")
        logger.info(f"  ❌ Failed: {failed_downloads}")

        if failed_downloads > 0:
            logger.warning("\n⚠️  Some downloads failed. Common reasons:")
            logger.warning("  1. Not connected to library WiFi")
            logger.warning("  2. Session expired - log into AncestryLibrary again")
            logger.warning("  3. Images not available for those specific records")

    # FamilySearch images (future implementation)
    if familysearch_citations:
        logger.info(
            f"\n⚠️  FamilySearch image download not yet implemented "
            f"({len(familysearch_citations)} citations)"
        )

    logger.info("\n✅ Download complete!")


if __name__ == "__main__":
    asyncio.run(main())
