"""
AncestryLibrary Draft Registration Scraper.

PRIMARY SOURCE for draft registration metadata extraction.
Extracts comprehensive data from Detail tab (name, birth, physical description, etc.)

Also downloads images as FALLBACK when FamilySearch URL is unavailable.

NOTE: Ancestry provides superior metadata quality compared to FamilySearch,
including fields like gender, age, and next of kin that FamilySearch lacks.

Uses Playwright CDP connection to existing Chrome instance for authentication.
"""

import re
import shutil
from pathlib import Path
from typing import Any, Optional, Tuple

from loguru import logger

from rmcitecraft.database.draft_registration_db import DraftRegistration
from rmcitecraft.services.ancestrylibrary_automation import AncestryLibraryAutomation
from rmcitecraft.services.draft_image_processor import DraftImageProcessor
from rmcitecraft.services.draft_file_naming import get_filename_from_rin, get_unique_filename
from rmcitecraft.services.draft_citation_builder import DraftCitationBuilder
from rmcitecraft.config.settings import get_config


class AncestryLibraryDraftScraper(AncestryLibraryAutomation):
    """Scrape draft registration metadata and download images from AncestryLibrary."""

    def __init__(self):
        """Initialize scraper with image processor and settings."""
        super().__init__()
        config = get_config()
        self.rmtree_path = config.rm_database_path
        self.storage_dir = Path(config.draft_image_storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.image_processor = DraftImageProcessor()
        self.citation_builder = DraftCitationBuilder()

    @staticmethod
    def _normalize_height(height: Optional[str]) -> str:
        """Normalize height to standard format. Delegates to DraftCitationBuilder.normalize_height."""
        return DraftCitationBuilder.normalize_height(height)

    async def scrape_and_download(
        self, record_url: str, rin: Optional[int] = None, metadata_only: bool = False
    ) -> Tuple[Optional[DraftRegistration], Optional[Path]]:
        """
        Scrape metadata and download images from AncestryLibrary draft registration page.

        Process:
        1. Navigate to record page
        2. Extract metadata from Detail tab (default view)
        3. Click Source tab and extract archival provenance
        4. Download both images (front + back) - skipped if metadata_only=True
        5. Combine images horizontally - skipped if metadata_only=True

        Args:
            record_url: AncestryLibrary record URL
            rin: Optional RootsMagic person ID for file naming
            metadata_only: If True, only scrape metadata without downloading images

        Returns:
            Tuple of (DraftRegistration, combined_image_path) or (None, None) if failed
        """
        if not self.page:
            logger.error("Browser not connected")
            return None, None

        try:
            # Navigate to record page
            logger.info(f"Navigating to: {record_url}")
            await self.page.goto(record_url, wait_until="networkidle", timeout=30000)

            # Check for access restrictions
            page_content = await self.page.content()
            if await self._check_access_restriction(page_content):
                return None, None

            # Extract metadata from Detail tab (default view)
            metadata = await self._extract_detail_tab_metadata()

            if not metadata or not metadata.get("name"):
                logger.warning("Failed to extract metadata from Detail tab")
                return None, None

            if not metadata:
                logger.error("No metadata extracted from either tab")
                return None, None

            # Extract ARK/record ID from URL
            # URL format: https://www.ancestrylibrary.com/search/collections/2238/records/200350484
            record_id_match = re.search(r'/records/(\d+)', record_url)
            record_id = record_id_match.group(1) if record_id_match else None

            # Parse age field (convert to int if present)
            age_value = None
            if metadata.get("age"):
                try:
                    age_value = int(metadata.get("age"))
                except (ValueError, TypeError):
                    logger.warning(f"Could not parse age: {metadata.get('age')}")

            # Create DraftRegistration object
            registration = DraftRegistration(
                ancestry_url=record_url,
                source_type="ancestrylibrary",
                full_name=metadata.get("name", ""),
                given_name=metadata.get("given_name"),
                surname=metadata.get("surname"),
                age=age_value,
                birth_date=metadata.get("birth_date"),
                birth_place=metadata.get("birth_place"),
                residence_city=metadata.get("residence_place"),  # "Residence Place" field
                employer_name=metadata.get("employer"),
                race=metadata.get("race"),
                height=self._normalize_height(metadata.get("height")),
                weight=metadata.get("weight"),
                complexion=metadata.get("complexion"),
                eye_color=metadata.get("eye_color"),
                hair_color=metadata.get("hair_color"),
                registration_date=metadata.get("registration_date"),
                registration_place=metadata.get("registration_place"),
                contact_person_name=metadata.get("next_of_kin"),
            )

            # Build citations (Phase 1: using scraped name)
            logger.info("Building Evidence Explained citations...")
            from datetime import datetime, timezone
            extracted_at = datetime.now(timezone.utc).isoformat()

            footnote, short_footnote, bibliography, warnings = await self.citation_builder.build_ancestry_citations(
                page=self.page,
                url=record_url,
                person_name=registration.full_name,
                extracted_at=extracted_at,
            )

            if footnote and short_footnote and bibliography:
                registration.rm_source_footnote = footnote
                registration.rm_source_short_footnote = short_footnote
                registration.rm_source_bibliography = bibliography
                logger.info("✅ Citations built successfully")
            else:
                logger.warning("⚠️  Citation building incomplete")

            # Store any warnings in notes field
            if warnings:
                registration.notes = "; ".join(warnings)
                logger.warning(f"Citation warnings: {registration.notes}")

            # Skip image download if metadata_only mode
            if metadata_only:
                logger.info(f"Metadata-only mode: skipping image download for {registration.full_name}")
                return registration, None

            # Download and combine images
            logger.info("\nDownloading images...")
            image1_path, image2_path = await self.download_draft_images(record_url)

            if not image1_path or not image2_path:
                logger.warning("Failed to download images")
                return registration, None

            # Process and finalize images using smart image processor
            final_image_path = await self._process_and_finalize_images(
                image1_path, image2_path, rin
            )

            if final_image_path:
                logger.info(f"✅ Processed and saved final image: {final_image_path.name}")
            else:
                logger.warning("Failed to process images")

            return registration, final_image_path

        except Exception as e:
            logger.error(f"Error scraping AncestryLibrary record: {e}", exc_info=True)
            return None, None

    async def _extract_detail_tab_metadata(self) -> dict[str, Any]:
        """
        Extract metadata from the Detail tab (default view).

        Extracts all person and event details using text pattern matching.
        """
        if not self.page:
            return {}

        try:
            # Content already loaded from goto with networkidle

            # Extract metadata using JavaScript evaluation
            metadata = await self.page.evaluate("""
                () => {
                    const data = {};
                    const allText = document.body.innerText;

                    // Define regex patterns for all wanted fields
                    const patterns = {
                        name: /Name\\t([^\\t\\n]+)/,
                        gender: /Gender[:\\s]+(Male|Female)/i,
                        race: /Race[:\\s]+([A-Za-z]+)/i,
                        age: /Age[:\\s]+(\\d+)/i,
                        birth_date: /Birth Date[:\\s]+([^\\n]+)/i,
                        birth_place: /Birth Place[:\\s]+([^\\n]+)/i,
                        residence_place: /Residence Place[:\\s]+([^\\n]+)/i,
                        registration_date: /Registration Date[:\\s]+([^\\n]+)/i,
                        registration_place: /Registration Place[:\\s]+([^\\n]+)/i,
                        employer: /Employer[:\\s]+([^\\n]+)/i,
                        height: /Height[:\\s]+([^\\n]+)/i,
                        weight: /Weight[:\\s]+([^\\n]+)/i,
                        complexion: /Complexion[:\\s]+([^\\n]+)/i,
                        hair_color: /Hair Color[:\\s]+([^\\n]+)/i,
                        eye_color: /Eye Color[:\\s]+([^\\n]+)/i,
                        next_of_kin: /Next of Kin[:\\s]+([^\\n]+)/i,
                    };

                    // Extract values using regex patterns
                    for (const [key, pattern] of Object.entries(patterns)) {
                        const match = allText.match(pattern);
                        if (match) {
                            data[key] = match[1].trim();
                        }
                    }

                    // Parse given name and surname from full name
                    if (data.name) {
                        const parts = data.name.split(' ');
                        if (parts.length >= 2) {
                            data.surname = parts[parts.length - 1];
                            data.given_name = parts.slice(0, -1).join(' ');
                        }
                    }

                    return data;
                }
            """)

            if metadata and metadata.get("name"):
                logger.info(f"✅ Extracted Detail tab metadata for: {metadata.get('name')}")
            else:
                logger.warning("No name found in Detail tab")

            return metadata

        except Exception as e:
            logger.error(f"Error extracting Detail tab metadata: {e}")
            return {}

    async def _extract_source_tab_metadata(self) -> dict[str, Any]:
        """
        Extract archival provenance metadata from the Source tab.

        Extracts:
        - NARA location (e.g., "National Archives at St. Louis")
        - Record Group (e.g., "Records of the Selective Service System, 147")
        - Box number
        - Collection name
        """
        if not self.page:
            return {}

        try:
            # Find and click the Source tab
            logger.info("Clicking Source tab...")
            source_tab = self.page.locator('button:has-text("Source"), a:has-text("Source")').first

            source_tab_count = await source_tab.count()
            if source_tab_count == 0:
                logger.warning("Source tab not found")
                return {}

            await source_tab.click()
            await self.page.wait_for_timeout(500)

            # Extract source citation text
            source_metadata = await self.page.evaluate("""
                () => {
                    const data = {};

                    // Find the source citation section
                    const sourceText = document.body.innerText;

                    // Extract NARA location
                    // Example: "National Archives at St. Louis; St. Louis, Missouri"
                    const naraMatch = sourceText.match(/National Archives at ([^;\\n]+)/i);
                    if (naraMatch) {
                        data.nara_location = 'National Archives at ' + naraMatch[1].trim();
                    }

                    // Extract Record Group
                    // Example: "Record Group: Records of the Selective Service System, 147"
                    const rgMatch = sourceText.match(/Record Group[:\\s]+([^\\n]+)/i);
                    if (rgMatch) {
                        data.record_group = rgMatch[1].trim();
                    }

                    // Extract Box number
                    // Example: "Box: 686"
                    const boxMatch = sourceText.match(/Box[:\\s]+(\\d+)/i);
                    if (boxMatch) {
                        data.box_number = boxMatch[1].trim();
                    }

                    // Extract collection name
                    // Example: "U.S., World War II Draft Cards Young Men, 1940-1947"
                    const collectionMatch = sourceText.match(/Ancestry\\.com\\.[\\s]+([^\\[\\n]+)\\[database/i);
                    if (collectionMatch) {
                        data.collection_name = collectionMatch[1].trim();
                    }

                    return data;
                }
            """)

            if source_metadata:
                logger.info(f"✅ Extracted Source tab metadata")
                if source_metadata.get("nara_location"):
                    logger.info(f"  NARA: {source_metadata['nara_location']}")
                if source_metadata.get("box_number"):
                    logger.info(f"  Box: {source_metadata['box_number']}")
            else:
                logger.warning("No metadata extracted from Source tab")

            return source_metadata

        except Exception as e:
            logger.error(f"Error extracting Source tab metadata: {e}")
            return {}

    async def _process_and_finalize_images(
        self, front_image_path: Path, back_image_path: Path, rin: Optional[int] = None
    ) -> Optional[Path]:
        """
        Process downloaded images (front and back) and save to final location.

        Ancestry images are always two separate cards that need processing.

        Steps:
        1. Process front card (deskew if needed, trim)
        2. Process back card (rotate if needed, deskew, trim)
        3. Combine horizontally
        4. Generate filename from RIN
        5. Move to final storage location
        6. Clean up originals (if configured)

        Args:
            front_image_path: Path to front card image
            back_image_path: Path to back card image
            rin: Optional RIN for file naming

        Returns:
            Path to final processed image in storage directory, or None if failed
        """
        try:
            # Step 1 & 2: Process both cards
            logger.info("Processing front and back cards...")
            front_processed = await self.image_processor.process_front_card(front_image_path)
            back_processed = await self.image_processor.process_back_card(back_image_path)

            # Step 3: Combine cards
            logger.info("Combining cards...")
            temp_output = front_image_path.parent / "combined_temp.jpg"
            combined_image = await self.image_processor.combine_cards(
                front_processed, back_processed, temp_output
            )

            # Clean up intermediate processed files
            if front_processed != front_image_path:
                front_processed.unlink(missing_ok=True)
            if back_processed != back_image_path:
                back_processed.unlink(missing_ok=True)

            # Step 4: Generate final filename
            if rin:
                filename = get_filename_from_rin(rin, self.rmtree_path)
            else:
                # Fallback: use timestamp
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"draft_card_{timestamp}.jpg"

            # Ensure unique filename
            filename = get_unique_filename(filename, self.storage_dir)

            # Step 5: Move to final storage location
            final_path = self.storage_dir / filename
            shutil.move(str(combined_image), str(final_path))
            logger.info(f"✅ Final image saved: {final_path}")

            # Step 6: Clean up originals
            await self.image_processor.cleanup_originals(front_image_path, back_image_path)

            return final_path

        except Exception as e:
            logger.error(f"Error processing and finalizing images: {e}", exc_info=True)

            # On error: keep originals, mark for manual review
            logger.warning("Keeping original downloaded images due to processing error")
            if front_image_path.exists():
                # Move original front to storage with error prefix
                error_filename = f"ERROR_{front_image_path.name}"
                error_path = self.storage_dir / error_filename
                shutil.copy(str(front_image_path), str(error_path))
                logger.info(f"Original front saved as: {error_path}")
                return error_path

            return None
