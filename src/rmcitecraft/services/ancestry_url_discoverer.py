"""
Ancestry URL Discovery Service.

Searches AncestryLibrary for draft registration records by name and birth year,
then returns the clean Ancestry URL for matching records.

Uses Playwright CDP connection to existing Chrome instance for authentication.
"""

import re
from typing import Optional

from loguru import logger
from playwright.async_api import async_playwright, Browser, Page


class AncestryUrlDiscoverer:
    """Discover Ancestry URLs by searching with name and birth year."""

    def __init__(self):
        """Initialize Ancestry URL discoverer."""
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

        logger.info("AncestryUrlDiscoverer initialized")

    async def connect(self) -> bool:
        """
        Connect to existing Chrome instance via CDP.

        Returns:
            True if connected successfully, False otherwise
        """
        try:
            logger.info("🔌 AncestryUrlDiscoverer: Connecting to Chrome CDP on port 9222...")
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

            context = contexts[0]
            pages = context.pages
            logger.debug(f"Found {len(pages)} page(s) in context")
            self.page = pages[0] if pages else await context.new_page()

            logger.info("✅ AncestryUrlDiscoverer: Connected to Chrome via CDP")
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
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception as e:
                logger.warning(f"Error stopping playwright: {e}")

        self.browser = None
        self.page = None
        self.playwright = None

    async def search_and_get_url(
        self,
        first_middle_name: str,
        last_name: str,
        birth_year: int,
        preferred_collections: Optional[list[str]] = None
    ) -> Optional[str]:
        """
        Search AncestryLibrary for a draft registration and return the clean URL.

        Args:
            first_middle_name: First and middle name(s)
            last_name: Last name/surname
            birth_year: Birth year
            preferred_collections: List of preferred collection names to match against

        Returns:
            Clean Ancestry URL (without query parameters) or None if not found
        """
        if not self.page:
            logger.error("Not connected to browser")
            return None

        if not preferred_collections:
            preferred_collections = [
                "U.S., World War II Draft Cards Young Men, 1940-1947",
                "U.S., World War II Draft Registration Cards, 1942"
            ]

        try:
            logger.info(f"Searching for: {first_middle_name} {last_name}, born {birth_year}")

            # Navigate to draft search page
            await self.page.goto(
                "https://www.ancestrylibrary.com/search/categories/mil_draft",
                wait_until="networkidle",
                timeout=30000
            )
            await self.page.wait_for_timeout(2000)

            # Fill search form
            logger.info("Filling search form...")
            await self.page.locator('input[aria-label*="First"]').first.fill(first_middle_name)
            await self.page.locator('input[aria-label*="Last"]').first.fill(last_name)
            await self.page.locator('input[aria-label*="Birth"]').first.fill(str(birth_year))

            # Submit search
            logger.info("Submitting search...")
            await self.page.locator('input[type="submit"]').first.click()
            await self.page.wait_for_load_state("networkidle", timeout=30000)
            await self.page.wait_for_timeout(3000)

            # Extract search results
            logger.info("Extracting results...")
            results = await self.page.evaluate("""
                () => {
                    const results = [];
                    const recordLinks = document.querySelectorAll('a[href*="/records/"]');

                    for (const link of recordLinks) {
                        const href = link.getAttribute('href');
                        const text = link.innerText.trim();

                        // Only include links that look like collection links
                        if (text.length > 20 && text.includes('Draft')) {
                            const recordIdMatch = href.match(/\\/records\\/(\\d+)/);
                            results.push({
                                href: href,
                                collection: text,
                                recordId: recordIdMatch ? recordIdMatch[1] : null
                            });
                        }
                    }

                    return results;
                }
            """)

            if not results:
                logger.warning("No draft registration results found")
                return None

            logger.info(f"Found {len(results)} potential records")

            # Find best matching collection
            matched_result = None
            for result in results:
                for preferred in preferred_collections:
                    if preferred in result["collection"]:
                        logger.info(f"✅ Found matching collection: {result['collection']}")
                        matched_result = result
                        break
                if matched_result:
                    break

            if not matched_result:
                logger.warning("No preferred collection found, using first result")
                matched_result = results[0]

            # Click the result and navigate to record page
            record_id = matched_result["recordId"]
            logger.info(f"Clicking record {record_id}...")
            await self.page.locator(f'a[href*="/records/{record_id}"]').first.click()
            await self.page.wait_for_load_state("networkidle", timeout=30000)
            await self.page.wait_for_timeout(1000)

            # Extract clean URL
            full_url = self.page.url
            clean_url = full_url.split('?')[0]

            logger.info(f"✅ Found Ancestry URL: {clean_url}")
            return clean_url

        except Exception as e:
            logger.error(f"Error searching Ancestry: {e}", exc_info=True)
            return None
