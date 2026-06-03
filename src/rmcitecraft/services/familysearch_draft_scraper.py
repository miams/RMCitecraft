"""
FamilySearch Draft Registration Scraper.

Downloads images from FamilySearch draft registration pages (preferred image source).
Handles both 1:1 person-level ARK pages and 3:1 image-level ARK pages.

NOTE: This scraper is used ONLY for image downloads, not metadata extraction.
Metadata should be scraped from Ancestry for superior data quality.

Uses Playwright CDP connection to existing Chrome instance for authentication.
"""

import asyncio
import re
import shutil
from pathlib import Path
from typing import Any, Optional, Tuple

from loguru import logger
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
    Browser,
    Page,
)

from rmcitecraft.database.draft_registration_db import DraftRegistration
from rmcitecraft.services.draft_citation_builder import DraftCitationBuilder
from rmcitecraft.services.draft_image_processor import DraftImageProcessor
from rmcitecraft.services.draft_file_naming import get_filename_from_rin, get_unique_filename
from rmcitecraft.config.settings import get_config


class FamilySearchDraftScraper:
    """Scrape draft registration metadata and download images from FamilySearch."""

    # Download and navigation parameters
    NAVIGATION_TIMEOUT_MS = 45_000  # FamilySearch page load timeout (45 seconds)
    MIN_IMAGE_SIZE_BYTES = 10_240  # Minimum valid image file size (10KB)

    def __init__(self, download_dir: Optional[Path] = None, rmtree_path: Optional[str] = None):
        """
        Initialize scraper.

        Args:
            download_dir: Directory for downloaded images (default: from config)
            rmtree_path: Path to RootsMagic database for file naming (default: from config)
        """
        config = get_config()
        self.download_dir = download_dir or Path(config.draft_download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.rmtree_path = rmtree_path or config.rm_database_path
        self.storage_dir = Path(config.draft_image_storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.playwright = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.image_processor = DraftImageProcessor()

    async def connect(self) -> bool:
        """Connect to existing Chrome CDP instance on port 9222."""
        try:
            logger.info("🔌 FamilySearchDraftScraper: Connecting to Chrome CDP on port 9222...")
            logger.debug("Starting playwright...")
            self.playwright = await async_playwright().start()
            logger.debug("Playwright started, attempting CDP connection...")

            # Add timeout to prevent indefinite hanging
            try:
                self.browser = await asyncio.wait_for(
                    self.playwright.chromium.connect_over_cdp("http://localhost:9222"),
                    timeout=10.0  # 10 second timeout
                )
                logger.debug("CDP connection established")
            except asyncio.TimeoutError:
                logger.error("⏱️ Timeout connecting to Chrome CDP after 10 seconds")
                logger.error("Make sure Chrome is running with: --remote-debugging-port=9222")
                await self.playwright.stop()
                return False

            logger.info("✅ FamilySearchDraftScraper: Connected to Chrome CDP")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Chrome CDP: {e}", exc_info=True)
            if self.playwright:
                try:
                    await self.playwright.stop()
                except:
                    pass
            return False

    async def disconnect(self) -> None:
        """Disconnect from browser."""
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
            self.browser = None
            self.page = None

    async def scrape_and_download(
        self, url: str, rin: Optional[int] = None, metadata_only: bool = False
    ) -> Tuple[Optional[DraftRegistration], Optional[Path]]:
        """
        Scrape metadata and download image from FamilySearch URL.

        Args:
            url: FamilySearch ARK URL (1:1 person or 3:1 image)
            rin: Optional RootsMagic person ID for file naming
            metadata_only: If True, only scrape metadata without downloading images

        Returns:
            Tuple of (DraftRegistration, final_image_path) or (None, None) if failed
        """
        # Determine URL type
        if "/ark:/61903/1:1:" in url:
            return await self._scrape_1_1_person_ark(url, rin, metadata_only=metadata_only)
        elif "/ark:/61903/3:1:" in url:
            return await self._scrape_3_1_image_ark(url, rin, metadata_only=metadata_only)
        else:
            logger.error(f"Unknown FamilySearch URL format: {url}")
            return None, None

    async def _scrape_1_1_person_ark(
        self, url: str, rin: Optional[int] = None, metadata_only: bool = False
    ) -> Tuple[Optional[DraftRegistration], Optional[Path]]:
        """
        Scrape 1:1 person-level ARK page.

        Process:
        1. Navigate to person page
        2. Scrape metadata from page
        3. Click "View Original Document" (skipped if metadata_only=True)
        4. Download image via keyboard automation (skipped if metadata_only=True)
        5. Analyze and process image (skipped if metadata_only=True)
        6. Rename and move to final storage location (skipped if metadata_only=True)
        """
        try:
            # Get or create page
            if not self.browser:
                logger.error("Browser not connected")
                return None, None

            context = self.browser.contexts[0]
            self.page = await context.new_page()

            # Navigate to person page
            logger.info(f"Navigating to person page: {url}")
            await self.page.goto(url, wait_until="domcontentloaded", timeout=self.NAVIGATION_TIMEOUT_MS)
            # Note: Don't wait for networkidle - FamilySearch has continuous background requests

            if not await self._wait_for_person_page_ready():
                logger.error("Timed out waiting for FamilySearch person page to render metadata")
                await self._capture_debug_screenshot("fs_person_page_timeout.png")
                return None, None

            # Scrape metadata
            metadata = await self._extract_person_page_metadata()
            if not metadata:
                logger.error("Failed to extract metadata from person page")
                return None, None

            # Create DraftRegistration object
            ark_match = re.search(r"ark:/61903/1:1:([A-Z0-9-]+)", url)
            ark_id = ark_match.group(1) if ark_match else None

            registration = DraftRegistration(
                familysearch_url=url,
                source_type="familysearch",
                full_name=metadata.get("name", ""),
                given_name=metadata.get("given_name"),
                surname=metadata.get("surname"),
                birth_date=metadata.get("birth_date"),
                birth_place=metadata.get("birthplace"),
                employer_name=metadata.get("employer"),
                race=metadata.get("race"),
                height=DraftCitationBuilder.normalize_height(metadata.get("height")),
                weight=metadata.get("weight"),
                complexion=metadata.get("complexion"),
                eye_color=metadata.get("eye_color"),
                hair_color=metadata.get("hair_color"),
                registration_date=metadata.get("event_date"),
                registration_place=metadata.get("event_place"),
                collection_name=metadata.get("collection_name"),
            )

            # Skip image download if metadata_only mode
            if metadata_only:
                logger.info(f"Metadata-only mode: skipping image download for {registration.full_name}")
                return registration, None

            # Navigate to image viewer and download
            raw_image_path = await self._navigate_to_viewer_and_download(registration.full_name, url_type="1:1")

            if not raw_image_path:
                logger.error("Failed to download image")
                return registration, None

            # Process and finalize image
            final_image_path = await self._process_and_finalize_image(raw_image_path, rin)

            return registration, final_image_path

        except Exception as e:
            logger.error(f"Error scraping 1:1 person ARK: {e}", exc_info=True)
            return None, None
        finally:
            if self.page:
                await self.page.close()
                self.page = None

    async def _scrape_3_1_image_ark(
        self, url: str, rin: Optional[int] = None, metadata_only: bool = False
    ) -> Tuple[Optional[DraftRegistration], Optional[Path]]:
        """
        Scrape 3:1 image-level ARK page.

        Per user direction: Just download image, skip detailed metadata scraping.
        Extract minimal info from page title and film info.
        Process and finalize downloaded images (skipped if metadata_only=True).
        """
        try:
            if not self.browser:
                logger.error("Browser not connected")
                return None, None

            context = self.browser.contexts[0]
            self.page = await context.new_page()

            # Navigate to image viewer
            logger.info(f"Navigating to image viewer: {url}")
            await self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(1)

            # Extract minimal metadata from page title
            title = await self.page.title()
            logger.info(f"Page title: {title}")

            # Parse state from title (e.g., "Ohio, WWII draft registration cards")
            state_match = re.search(r"^([A-Za-z\s]+),", title)
            state = state_match.group(1).strip() if state_match else None

            # Extract ARK ID
            ark_match = re.search(r"ark:/61903/3:1:([A-Z0-9-]+)", url)
            ark_id = ark_match.group(1) if ark_match else None

            # Create minimal registration record
            registration = DraftRegistration(
                familysearch_url=url,
                source_type="familysearch",
                full_name="[Not extracted from image]",  # Placeholder
                residence_state=state,
                collection_name=title,
            )

            # Skip image download if metadata_only mode
            if metadata_only:
                logger.info("Metadata-only mode: skipping image download for 3:1 image ARK")
                return registration, None

            # Download image (already on image viewer)
            # FS 3:1 URLs have TWO images (front + back) that need to be downloaded and combined
            raw_image_path = await self._download_image_from_viewer("[3:1 image]", url_type="3:1")

            if not raw_image_path:
                logger.error("Failed to download image")
                return registration, None

            # Process and finalize image
            final_image_path = await self._process_and_finalize_image(raw_image_path, rin)

            return registration, final_image_path

        except Exception as e:
            logger.error(f"Error scraping 3:1 image ARK: {e}", exc_info=True)
            return None, None
        finally:
            if self.page:
                await self.page.close()
                self.page = None

    async def _extract_person_page_metadata(self) -> dict[str, Any]:
        """Extract metadata from 1:1 person page using text pattern matching.

        NOTE: This method is currently NOT USED for metadata extraction as Ancestry
        provides superior data quality. This is kept for reference only.

        Uses Playwright page.evaluate() to run JavaScript in the browser context,
        extracting visible text and pattern matching against field labels like
        "Name", "Birth Date", "Event Place", etc. This approach is more reliable
        than DOM traversal since FamilySearch doesn't use semantic HTML (dt/dd).

        Returns:
            Dictionary of extracted metadata fields (name, birth_date, event_place, etc.)
        """
        if not self.page:
            return {}

        try:
            # Use JavaScript in-browser text pattern matching on page content
            # This is more reliable than DOM selectors since FamilySearch layout varies
            metadata = await self.page.evaluate("""
                () => {
                    const data = {};
                    const allText = document.body.innerText;

                    // Define regex patterns for each field
                    const patterns = {
                        name: /Name\\s+([^\\n]+)/,
                        birth_date: /Birth Date\\s+([^\\n]+)/,
                        birthplace: /Birthplace\\s+([^\\n]+)/,
                        employer: /Employer\\s+([^\\n]+)/,
                        complexion: /Complexion\\s+([^\\n]+)/,
                        race: /Race\\s+([^\\n]+)/,
                        height: /Height\\s+([^\\n]+)/,
                        weight: /Weight\\s+([^\\n]+)/,
                        eye_color: /Eye Color\\s+([^\\n]+)/,
                        hair_color: /Hair Color\\s+([^\\n]+)/,
                        event_type: /Event Type\\s+([^\\n]+)/,
                        event_date: /Event Date\\s+([^\\n]+)/,
                        event_place: /Event Place\\s+([^\\n]+)/,
                        digital_folder_number: /Digital Folder Number\\s+([^\\n]+)/,
                        image_number: /Image Number\\s+([^\\n]+)/,
                        affiliate_publication_number: /Affiliate Publication Number\\s+([^\\n]+)/,
                        collection_name: /Affiliate Publication Title\\s+([^\\n]+)/,
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

            if not metadata or not metadata.get("name"):
                logger.warning("No metadata extracted - name field not found")
                await self._capture_debug_screenshot("fs_person_page_no_metadata.png")
                return {}

            logger.info(f"✅ Extracted metadata for: {metadata.get('name')}")
            return metadata

        except Exception as e:
            logger.error(f"Error evaluating page for metadata: {e}")
            return {}

    async def _navigate_to_viewer_and_download(self, person_name: str, url_type: str = "1:1") -> Optional[Path]:
        """
        Navigate from person page to image viewer and download.

        Args:
            person_name: Name for filename
            url_type: "1:1" or "3:1" to determine download flow

        Returns:
            Path to downloaded image or None
        """
        if not self.page:
            return None

        try:
            # Find and click "View Original Document" button
            view_btn = self.page.locator('[data-testid="viewOriginalDocument-Button"]')
            is_visible = await view_btn.is_visible(timeout=5000)

            if not is_visible:
                logger.error("View Original Document button not found")
                return None

            logger.info("Clicking 'View Original Document'...")
            await view_btn.click()
            await asyncio.sleep(2)  # Wait for image viewer to load

            # Now download the image
            return await self._download_image_from_viewer(person_name, url_type=url_type)

        except Exception as e:
            logger.error(f"Error navigating to viewer: {e}")
            return None

    async def _download_image_from_viewer(self, person_name: str, url_type: str = "1:1") -> Optional[Path]:
        """
        Download image(s) from FamilySearch image viewer.

        Handles two different download flows:
        - FS 1:1 (person pages): Radio button dialog with JPG selection
        - FS 3:1 (image pages): Filename confirmation dialog (use CMD-S)

        FS 3:1 pages have TWO separate images (front + back) that must be combined.

        Args:
            person_name: Name for filename
            url_type: "1:1" for person pages, "3:1" for image pages

        Returns:
            Path to downloaded image (or combined image if multiple) or None
        """
        if not self.page:
            return None

        try:
            # Wait for download button
            download_btn = self.page.locator('[data-testid="download-image-button"]')
            is_visible = await download_btn.is_visible(timeout=15000)

            if not is_visible:
                logger.error("Download button not found")
                return None

            # Check current image number (e.g., "Image 621 of 2,248")
            image_info = await self.page.evaluate("""
                () => {
                    const text = document.body.innerText;
                    const match = text.match(/Image\\s+(\\d+)\\s+of\\s+(\\d+)/);
                    return match ? { current: parseInt(match[1]), total: parseInt(match[2]) } : null;
                }
            """)

            if image_info:
                logger.info(f"Current image: {image_info['current']} of {image_info['total']}")

            # Download first image
            logger.info("Downloading first image...")
            first_image = await self._download_single_image(download_btn, person_name, "img1", url_type)

            if not first_image:
                return None

            # For FS 3:1 URLs, ALWAYS download second image (front + back)
            # For FS 1:1 URLs, check if Next Image button exists
            if url_type == "3:1":
                logger.info("FS 3:1 URL - downloading second image (back of card)...")

                # Navigate to next image
                next_btn = self.page.locator('button[aria-label*="Next"], button[title*="Next"]').first
                await next_btn.click()
                await asyncio.sleep(1)

                # Download second image
                second_image = await self._download_single_image(download_btn, person_name, "img2", url_type)

                if second_image:
                    # Combine both images horizontally using ImageMagick
                    logger.info("Combining front and back images...")
                    combined_path = await self._combine_images([first_image, second_image], person_name)

                    if combined_path:
                        # Clean up individual images
                        first_image.unlink()
                        second_image.unlink()
                        return combined_path
                    else:
                        logger.warning("Failed to combine images, returning first image only")
                        return first_image
                else:
                    logger.warning("Failed to download second image, returning first image only")
                    return first_image
            else:
                # FS 1:1 URLs may have combined image already
                next_btn = self.page.locator('button:has-text("Next Image"), button[aria-label*="Next"]')
                has_next = await next_btn.count() > 0

                if has_next:
                    logger.info("Found 'Next Image' button - downloading second image...")
                    await next_btn.click()
                    await asyncio.sleep(1)

                    # Download second image
                    second_image = await self._download_single_image(download_btn, person_name, "img2", url_type)

                    if second_image:
                        # Combine both images
                        logger.info("Combining front and back images...")
                        combined_path = await self._combine_images([first_image, second_image], person_name)

                        if combined_path:
                            first_image.unlink()
                            second_image.unlink()
                            return combined_path
                        else:
                            return first_image
                    else:
                        return first_image
                else:
                    logger.info("No 'Next Image' button - card has single combined image")
                    return first_image

        except Exception as e:
            logger.error(f"Error downloading image: {e}", exc_info=True)
            return None

    async def _wait_for_download_completion(self, file_path: Path, timeout_seconds: int = 60, min_size_bytes: int = 1024) -> bool:
        """
        Wait for a download to complete by polling file size.

        Playwright's save_as() creates an empty file immediately and streams content
        in the background. This method polls until the file has actual content.

        Args:
            file_path: Path to downloaded file
            timeout_seconds: Max seconds to wait for file content
            min_size_bytes: Minimum expected file size (default 1KB)

        Returns:
            True if file has content, False if timeout or stays empty
        """
        start_time = asyncio.get_event_loop().time()
        poll_interval = 0.5  # Check every 500ms
        last_size = 0
        stable_count = 0

        logger.debug(f"Waiting for download to complete: {file_path.name}")

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time

            if elapsed > timeout_seconds:
                logger.error(f"Download timeout after {timeout_seconds}s: {file_path.name} ({last_size} bytes)")
                return False

            # Check file size
            if file_path.exists():
                current_size = file_path.stat().st_size

                # File is growing or stable with content
                if current_size > 0:
                    if current_size == last_size:
                        stable_count += 1
                        # File size hasn't changed for 1.5 seconds (3 polls) - likely complete
                        if stable_count >= 3 and current_size >= min_size_bytes:
                            logger.debug(f"Download complete: {file_path.name} ({current_size:,} bytes)")
                            return True
                    else:
                        # Size changed, reset stability counter
                        stable_count = 0
                        logger.debug(f"Download in progress: {current_size:,} bytes ({elapsed:.1f}s elapsed)")

                    last_size = current_size
                else:
                    # Still 0 bytes
                    logger.debug(f"File still empty after {elapsed:.1f}s")

            await asyncio.sleep(poll_interval)

    async def _download_single_image(self, download_btn, person_name: str, suffix: str, url_type: str = "1:1") -> Optional[Path]:
        """
        Download a single image from the viewer.

        Two different flows:
        - FS 1:1: Opens dialog with radio buttons, select JPG, click Download
        - FS 3:1: Opens filename dialog, use CMD-S to save

        Args:
            download_btn: Playwright locator for download button
            person_name: Name for filename
            suffix: Suffix for filename (e.g., "img1", "img2")
            url_type: "1:1" for person pages, "3:1" for image pages

        Returns:
            Path to downloaded image or None
        """
        try:
            if url_type == "3:1":
                # FS 3:1: Click download button, then use CMD-S to confirm save
                logger.info("Clicking download button (FS 3:1 flow)...")

                # Start waiting for download before clicking button
                async with self.page.expect_download(timeout=30000) as download_info:
                    await download_btn.click()
                    await asyncio.sleep(1)

                    # Press CMD-S to confirm save in filename dialog
                    logger.info("Pressing CMD-S to save...")
                    await self.page.keyboard.press("Meta+s")  # CMD-S on macOS

                # Get download and save
                download = await download_info.value
                suggested_filename = download.suggested_filename

                # Create safe filename
                safe_name = person_name.replace(" ", "_").replace("/", "_")
                filename = f"fs_draft_{safe_name}_{suffix}_{suggested_filename}"
                save_path = self.download_dir / filename

                # Start download (creates empty file, streams in background)
                await download.save_as(str(save_path))

                # Wait for actual content to arrive
                if await self._wait_for_download_completion(save_path, timeout_seconds=60, min_size_bytes=self.MIN_IMAGE_SIZE_BYTES):
                    logger.info(f"✅ Downloaded: {save_path.name} ({save_path.stat().st_size:,} bytes)")
                    return save_path
                else:
                    logger.error(f"❌ Download failed or incomplete: {save_path.name}")
                    # Clean up empty/incomplete file
                    if save_path.exists():
                        save_path.unlink()
                    return None

            else:
                # FS 1:1: Click download button, select JPG radio, click Download
                logger.info("Clicking download button (FS 1:1 flow)...")
                await download_btn.click()

                # Wait for dialog to appear and radio buttons to be ready
                jpg_radio = self.page.locator('input[type="radio"][value="JPG Only"]')
                await jpg_radio.wait_for(state="visible", timeout=10000)

                # Select "JPG Only" radio button (third option, value="JPG Only")
                logger.info("Selecting JPG Only option...")
                await jpg_radio.click()

                # Find and click Download button in dialog
                dialog_download_btn = self.page.locator('button:has-text("Download")').last

                # Start waiting for download before clicking
                logger.info("Clicking Download button...")
                async with self.page.expect_download(timeout=30000) as download_info:
                    await dialog_download_btn.click()

                # Get download and save
                download = await download_info.value
                suggested_filename = download.suggested_filename

                # Create safe filename
                safe_name = person_name.replace(" ", "_").replace("/", "_")
                filename = f"fs_draft_{safe_name}_{suffix}_{suggested_filename}"
                save_path = self.download_dir / filename

                # Start download (creates empty file, streams in background)
                await download.save_as(str(save_path))

                # Close dialog if still open
                try:
                    cancel_btn = self.page.locator('button:has-text("Cancel")')
                    if await cancel_btn.is_visible(timeout=500):
                        await cancel_btn.click()
                except:
                    pass  # Dialog already closed

                # Wait for actual content to arrive
                if await self._wait_for_download_completion(save_path, timeout_seconds=60, min_size_bytes=self.MIN_IMAGE_SIZE_BYTES):
                    logger.info(f"✅ Downloaded: {save_path.name} ({save_path.stat().st_size:,} bytes)")
                    return save_path
                else:
                    logger.error(f"❌ Download failed or incomplete: {save_path.name}")
                    # Clean up empty/incomplete file
                    if save_path.exists():
                        save_path.unlink()
                    return None

        except Exception as e:
            logger.error(f"Error downloading single image ({url_type} flow): {e}")
            await self._capture_debug_screenshot("fs_download_error.png")
            return None

    async def _wait_for_person_page_ready(self) -> bool:
        """Ensure the FamilySearch person page rendered key metadata."""
        if not self.page:
            return False

        try:
            await self.page.wait_for_selector(
                '[data-testid="viewOriginalDocument-Button"]',
                timeout=25000,
            )
            await self.page.wait_for_function(
                "() => document.body.innerText.includes('Birth Date') || "
                "document.body.innerText.includes('Event Date')",
                timeout=25000,
            )
            return True
        except PlaywrightTimeoutError:
            return False

    async def _capture_debug_screenshot(self, filename: str) -> None:
        """Persist a full-page screenshot for debugging asynchronous rendering issues."""
        if not self.page:
            return

        screenshot_dir = self.download_dir / "debug"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        path = screenshot_dir / filename
        try:
            await self.page.wait_for_load_state("load", timeout=5000)
        except PlaywrightTimeoutError:
            pass
        await asyncio.sleep(0.5)
        try:
            await self.page.screenshot(path=str(path), full_page=True)
            logger.info(f"Saved debug screenshot to {path}")
        except Exception as exc:
            logger.error(f"Failed to capture debug screenshot {filename}: {exc}")

    async def _process_and_finalize_image(
        self, first_image_path: Path, rin: Optional[int] = None
    ) -> Optional[Path]:
        """
        Process downloaded image(s) and save to final location with proper naming.

        Steps:
        1. Analyze first image to determine if second image needed
        2. Download second image if required
        3. Process images (deskew, rotate, combine)
        4. Generate filename from RIN
        5. Move to final storage location
        6. Clean up originals (if configured)

        Args:
            first_image_path: Path to first downloaded image
            rin: Optional RIN for file naming

        Returns:
            Path to final processed image in storage directory, or None if failed
        """
        try:
            # Step 1: Analyze first image
            logger.info("Analyzing downloaded image...")
            analysis = await self.image_processor.analyze_image(first_image_path)

            second_image_path = None

            # Step 2: Download second image if needed
            if analysis.needs_second_image:
                logger.info("Second image required, attempting download...")
                # Try to navigate to next image and download
                # NOTE: This assumes we're still on the image viewer page
                # If page has been closed, this will fail gracefully
                try:
                    if self.page:
                        next_btn = self.page.locator('button[aria-label*="Next"], button[title*="Next"]').first
                        await next_btn.click()
                        await asyncio.sleep(1)

                        # Download second image
                        download_btn = self.page.locator('[data-testid="download-image-button"]')
                        second_image_path = await self._download_single_image(
                            download_btn,
                            "back_card",
                            "img2",
                            "1:1"
                        )

                        if not second_image_path:
                            logger.warning("Failed to download second image, using first image only")
                except Exception as e:
                    logger.warning(f"Failed to download second image: {e}")

            # Step 3: Process image(s)
            logger.info("Processing image(s)...")
            temp_output = self.download_dir / "processed_temp.jpg"

            if second_image_path:
                # Process both cards and combine
                front_processed = await self.image_processor.process_front_card(first_image_path)
                back_processed = await self.image_processor.process_back_card(second_image_path)
                processed_image = await self.image_processor.combine_cards(
                    front_processed, back_processed, temp_output
                )

                # Clean up intermediate processed files
                if front_processed != first_image_path:
                    front_processed.unlink(missing_ok=True)
                if back_processed != second_image_path:
                    back_processed.unlink(missing_ok=True)

            elif analysis.estimated_type == "A":
                # Already combined, minimal processing
                processed_image = await self.image_processor.process_combined_card(
                    first_image_path, temp_output
                )
            elif analysis.estimated_type == "E":
                # Vertically stacked (front on top, back on bottom)
                processed_image = await self.image_processor.process_stacked_card(
                    first_image_path, temp_output
                )
            else:
                # Single card, no second image available
                logger.warning("Single card detected but second image not available")
                processed_image = await self.image_processor.process_front_card(
                    first_image_path, temp_output
                )

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
            shutil.move(str(processed_image), str(final_path))
            logger.info(f"✅ Final image saved: {final_path}")

            # Step 6: Clean up originals
            await self.image_processor.cleanup_originals(first_image_path, second_image_path)

            return final_path

        except Exception as e:
            logger.error(f"Error processing and finalizing image: {e}", exc_info=True)

            # On error: keep original, mark for manual review
            logger.warning("Keeping original downloaded image due to processing error")
            if first_image_path.exists():
                # Move original to storage with error prefix
                error_filename = f"ERROR_{first_image_path.name}"
                error_path = self.storage_dir / error_filename
                shutil.copy(str(first_image_path), str(error_path))
                logger.info(f"Original saved as: {error_path}")
                return error_path

            return None

    async def _combine_images(self, image_paths: list[Path], person_name: str) -> Optional[Path]:
        """
        Combine multiple images horizontally with proper vertical centering.

        Delegates to DraftImageProcessor.combine_raw_images() for the actual processing.

        Args:
            image_paths: List of paths to images to combine
            person_name: Name for output filename

        Returns:
            Path to combined image or None
        """
        try:
            # Create output filename
            safe_name = person_name.replace(" ", "_").replace("/", "_")
            output_path = self.download_dir / f"fs_draft_{safe_name}_combined.jpg"

            # Delegate to image processor for combining
            await self.image_processor.combine_raw_images(
                image_paths[0],
                image_paths[1],
                output_path,
                temp_dir=self.download_dir
            )

            return output_path

        except Exception as e:
            logger.error(f"Error combining images: {e}", exc_info=True)
            return None
