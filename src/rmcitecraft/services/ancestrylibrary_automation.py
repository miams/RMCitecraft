r"""
AncestryLibrary.com automation service for downloading draft registration images.

Uses Playwright to automate image downloads from AncestryLibrary.com when
connected to library WiFi. Requires Chrome running with remote debugging on port 9222.

Prerequisites:
    Chrome must be started with remote debugging:
    /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
        --remote-debugging-port=9222 \
        --no-first-run \
        --user-data-dir=~/.chrome-debug-profile

Usage:
    service = AncestryLibraryAutomation()
    await service.connect()
    images = await service.download_draft_images(record_url)
    combined_path = await service.combine_images(images[0], images[1])
"""

import subprocess
from pathlib import Path
from typing import List, Optional, Tuple
from loguru import logger

from playwright.async_api import async_playwright, Browser, BrowserContext, Page


class AncestryLibraryAutomation:
    """Automates AncestryLibrary.com image downloads using Playwright."""

    def __init__(self, download_dir: Optional[Path] = None):
        """
        Initialize AncestryLibrary automation service.

        Args:
            download_dir: Directory for downloaded images (default: /tmp/ancestry_downloads)
        """
        self.download_dir = download_dir or Path("/tmp/ancestry_downloads")
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        logger.info(f"AncestryLibraryAutomation initialized (download_dir={self.download_dir})")

    async def connect(self) -> bool:
        """
        Connect to existing Chrome instance via CDP.

        Returns:
            True if connected successfully, False otherwise
        """
        try:
            logger.info("🔌 AncestryLibraryAutomation: Connecting to Chrome CDP on port 9222...")
            logger.debug("Starting playwright...")
            self.playwright = await async_playwright().start()
            logger.debug("Playwright started, attempting CDP connection...")

            # Add timeout to prevent indefinite hanging
            import asyncio
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

            contexts = self.browser.contexts
            logger.debug(f"Found {len(contexts)} browser context(s)")
            if not contexts:
                logger.error("No browser contexts found")
                return False

            self.context = contexts[0]
            pages = self.context.pages
            logger.debug(f"Found {len(pages)} page(s) in context")
            self.page = pages[0] if pages else await self.context.new_page()

            logger.info("✅ AncestryLibraryAutomation: Connected to Chrome via CDP")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to connect to Chrome CDP: {e}", exc_info=True)
            if self.playwright:
                try:
                    await self.playwright.stop()
                except:
                    pass
            return False

    async def disconnect(self):
        """Disconnect from Chrome."""
        if self.browser:
            try:
                # Don't close browser since we connected to existing instance
                pass
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")

        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception as e:
                logger.warning(f"Error stopping playwright: {e}")

        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None

    async def download_draft_images(
        self, record_url: str
    ) -> Tuple[Optional[Path], Optional[Path]]:
        """
        Download both images (front and back) of a draft registration card.

        Args:
            record_url: AncestryLibrary.com record URL

        Returns:
            Tuple of (image1_path, image2_path) or (None, None) if failed
        """
        if not self.page:
            logger.error("Not connected to browser")
            return None, None

        try:
            logger.info(f"Navigating to: {record_url}")
            await self.page.goto(record_url, wait_until="networkidle", timeout=30000)

            # Check for access restrictions on the record page
            page_content = await self.page.content()
            if await self._check_access_restriction(page_content):
                return None, None

            # Check if image thumbnail is available
            logger.info("Checking for image thumbnail...")
            image_link = self.page.locator("a.photoContainer.photo.photoCenter.clickable").first
            image_count = await image_link.count()

            if image_count == 0:
                logger.error("❌ No image thumbnail found - images may not be available")
                logger.error("This typically means:")
                logger.error("  1. Not connected to library WiFi")
                logger.error("  2. AncestryLibrary session expired")
                logger.error("  3. Images not available for this record")
                return None, None

            # Click the image thumbnail to open image viewer
            logger.info("Clicking image thumbnail...")
            await image_link.wait_for(state="visible", timeout=10000)
            await image_link.click()

            logger.info("Waiting for image viewer to load...")
            await self.page.wait_for_timeout(1500)

            # Check if iframe loaded (indicates image viewer is accessible)
            iframe_count = await self.page.locator("iframe.iivIframe").count()

            if iframe_count == 0:
                logger.error("❌ Image viewer did not load - checking for access restrictions...")

                # Check for common error messages
                error_selectors = [
                    "text=/not available/i",
                    "text=/library access/i",
                    "text=/restricted/i",
                    "text=/subscription required/i",
                    ".error",
                    ".alert"
                ]

                for selector in error_selectors:
                    elements = await self.page.locator(selector).all()
                    if elements:
                        for elem in elements[:2]:  # Check first 2 matches
                            text = await elem.text_content()
                            if text and text.strip():
                                logger.error(f"  Error message: {text.strip()}")

                logger.error("\nPossible reasons:")
                logger.error("  1. Not connected to library WiFi")
                logger.error("  2. AncestryLibrary session expired - try logging in again")
                logger.error("  3. Images restricted for this record")
                return None, None

            # Get the iframe
            iframe_element = await self.page.wait_for_selector(
                "iframe.iivIframe", timeout=10000
            )
            iframe = await iframe_element.content_frame()

            if not iframe:
                logger.error("❌ Could not access image viewer iframe")
                return None, None

            logger.info("✅ Image viewer loaded")

            # Download first image
            image1_path = await self._download_image(iframe, 1)
            if not image1_path:
                return None, None

            # Click next button to advance to second image
            logger.info("\n➡️  Clicking Next button to advance to second image...")
            next_button = iframe.locator('button[aria-label="Next image"]')
            await next_button.wait_for(state="visible", timeout=5000)
            await next_button.click()
            logger.info("✅ Advanced to second image")

            # Wait for second image to load
            await self.page.wait_for_timeout(1000)

            # Download second image
            image2_path = await self._download_image(iframe, 2)
            if not image2_path:
                return image1_path, None

            logger.info("\n✅ Both images downloaded successfully!")
            logger.info(f"  - Image 1: {image1_path.name}")
            logger.info(f"  - Image 2: {image2_path.name}")

            return image1_path, image2_path

        except Exception as e:
            logger.error(f"Failed to download images: {e}")
            return None, None

    async def _download_image(self, iframe, image_number: int) -> Optional[Path]:
        """
        Download a single image from the current viewer state.

        Args:
            iframe: Playwright frame object for the image viewer
            image_number: Image number (1 or 2) for filename

        Returns:
            Path to downloaded image or None if failed
        """
        try:
            logger.info(f"\n📥 Downloading image {image_number}...")

            # Click the "Tool menu" button
            logger.info("🖱️  Opening Tool menu...")
            tool_menu_button = iframe.locator('button.settingsMenu[title="Tool menu"]')
            await tool_menu_button.wait_for(state="visible", timeout=5000)
            await tool_menu_button.click()

            # Wait for menu to appear
            await self.page.wait_for_timeout(500)

            # Look for the Download option in the menu
            logger.info("🔍 Looking for Download option...")

            download_selectors = [
                "text=/^Download$/i",
                'button:has-text("Download")',
                'a:has-text("Download")',
                '[data-action="download"]',
                ".download",
            ]

            download_option = None
            for selector in download_selectors:
                element = iframe.locator(selector).first
                count = await element.count()
                if count > 0 and await element.is_visible():
                    download_option = element
                    logger.info(f"✅ Found Download option with selector: {selector}")
                    break

            if not download_option:
                # Try looking in the parent page (menu might pop out of iframe)
                logger.info("🔍 Checking for menu outside iframe...")
                for selector in download_selectors:
                    element = self.page.locator(selector).first
                    count = await element.count()
                    if count > 0 and await element.is_visible():
                        download_option = element
                        logger.info(f"✅ Found Download option in parent page: {selector}")
                        break

            if not download_option:
                raise Exception("Could not find Download option in Tool menu")

            # Set up download listener before clicking
            async with self.page.expect_download(timeout=30000) as download_info:
                logger.info("🖱️  Clicking Download option...")
                await download_option.click()

            # Wait for the download
            logger.info("⏳ Waiting for download...")
            download = await download_info.value

            # Save the download
            filename = download.suggested_filename or f"image_{image_number}.jpg"
            download_path = self.download_dir / f"{image_number}_{filename}"
            await download.save_as(download_path)
            logger.info(f"✅ Image {image_number} downloaded to: {download_path}")

            # Close the menu if still open
            await self.page.keyboard.press("Escape")

            return download_path

        except Exception as e:
            logger.error(f"Failed to download image {image_number}: {e}")
            return None

    async def combine_images(
        self, image1_path: Path, image2_path: Path, output_filename: str = "combined_images.jpg"
    ) -> Optional[Path]:
        """
        Combine two draft registration images horizontally with left image centered.

        Process:
        1. Trim black borders from both images (25% fuzz)
        2. Center left image vertically
        3. Append right image horizontally
        4. Trim outer black borders from combined result

        Args:
            image1_path: Path to first image (horizontal/front)
            image2_path: Path to second image (vertical/back)
            output_filename: Output filename (default: "combined_images.jpg")

        Returns:
            Path to combined image or None if failed
        """
        try:
            logger.info("\n🖼️  Combining images...")

            # Create temporary trimmed images
            trimmed1_path = self.download_dir / "1_trimmed.jpg"
            trimmed2_path = self.download_dir / "2_trimmed.jpg"

            # Trim black borders from both images (25% fuzz for aggressive trimming)
            logger.info("  Trimming black borders...")
            subprocess.run(
                [
                    "convert",
                    str(image1_path),
                    "-fuzz",
                    "25%",
                    "-trim",
                    "+repage",
                    str(trimmed1_path),
                ],
                check=True,
                capture_output=True,
            )

            subprocess.run(
                [
                    "convert",
                    str(image2_path),
                    "-fuzz",
                    "25%",
                    "-trim",
                    "+repage",
                    str(trimmed2_path),
                ],
                check=True,
                capture_output=True,
            )

            # Get dimensions of trimmed images
            identify1 = subprocess.run(
                ["identify", "-format", "%wx%h", str(trimmed1_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            identify2 = subprocess.run(
                ["identify", "-format", "%wx%h", str(trimmed2_path)],
                check=True,
                capture_output=True,
                text=True,
            )

            width1, height1 = map(int, identify1.stdout.strip().split("x"))
            width2, height2 = map(int, identify2.stdout.strip().split("x"))

            logger.info(f"  Trimmed Image 1: {width1}×{height1}")
            logger.info(f"  Trimmed Image 2: {width2}×{height2}")

            # Determine max height for vertical centering
            max_height = max(height1, height2)

            # Combine: extend image 1 to max height (centered), append image 2, then trim outer edges
            combined_path = self.download_dir / output_filename
            subprocess.run(
                [
                    "convert",
                    str(trimmed1_path),
                    "-gravity",
                    "center",
                    "-background",
                    "black",
                    "-extent",
                    f"{width1}x{max_height}",
                    str(trimmed2_path),
                    "+append",
                    "-fuzz",
                    "25%",
                    "-trim",
                    "+repage",
                    str(combined_path),
                ],
                check=True,
                capture_output=True,
            )

            # Get final dimensions
            identify_combined = subprocess.run(
                ["identify", "-format", "%wx%h", str(combined_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            combined_size = identify_combined.stdout.strip()

            logger.info(f"✅ Combined image saved to: {combined_path}")
            logger.info(f"  Combined size: {combined_size}")

            # Clean up temporary files
            trimmed1_path.unlink(missing_ok=True)
            trimmed2_path.unlink(missing_ok=True)

            return combined_path

        except subprocess.CalledProcessError as e:
            logger.error(f"ImageMagick command failed: {e}")
            logger.error(f"  stderr: {e.stderr.decode() if e.stderr else 'N/A'}")
            return None
        except Exception as e:
            logger.error(f"Failed to combine images: {e}")
            return None

    async def download_and_combine(
        self, record_url: str, output_filename: str = "combined_images.jpg"
    ) -> Optional[Path]:
        """
        Complete workflow: download both images and combine them.

        Args:
            record_url: AncestryLibrary.com record URL
            output_filename: Output filename for combined image

        Returns:
            Path to combined image or None if failed
        """
        # Download both images
        image1_path, image2_path = await self.download_draft_images(record_url)

        if not image1_path or not image2_path:
            logger.error("Failed to download one or both images")
            return None

        # Combine images
        combined_path = await self.combine_images(image1_path, image2_path, output_filename)

        return combined_path

    async def _check_access_restriction(self, page_content: str) -> bool:
        """
        Check if the page shows access restriction messages.

        Args:
            page_content: HTML content of the page

        Returns:
            True if access is restricted, False otherwise
        """
        # Common restriction phrases
        restriction_indicators = [
            "not available",
            "library access required",
            "available at participating libraries",
            "subscription required",
            "access denied",
            "restricted content",
            "must be at library",
        ]

        content_lower = page_content.lower()

        for indicator in restriction_indicators:
            if indicator in content_lower:
                logger.error(f"❌ Access restriction detected: '{indicator}'")
                logger.error("\nThis record requires library WiFi access.")
                logger.error("Please:")
                logger.error("  1. Connect to library WiFi network")
                logger.error("  2. Log into AncestryLibrary.com in your Chrome browser")
                logger.error("  3. Try again")
                return True

        return False


# Context manager support
class AncestryLibrarySession:
    """Context manager for AncestryLibrary automation sessions."""

    def __init__(self, download_dir: Optional[Path] = None):
        """
        Initialize session.

        Args:
            download_dir: Directory for downloaded images
        """
        self.service = AncestryLibraryAutomation(download_dir)

    async def __aenter__(self):
        """Connect to browser."""
        await self.service.connect()
        return self.service

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Disconnect from browser."""
        await self.service.disconnect()
