"""Browser connection management for FamilySearch automation.

Provides a unified interface for connecting to Chrome and managing pages
for FamilySearch extraction. Supports both CDP connection to existing
Chrome and launching new Chrome with persistent context.

Connection Strategy:
1. First try CDP connection to existing Chrome (port 9222)
2. If that fails, launch new Chrome with persistent profile

The persistent profile maintains FamilySearch login across sessions.
"""

import asyncio
import os

from loguru import logger
from playwright.async_api import BrowserContext, Page, async_playwright

# Chrome profile directory for persistent login
CHROME_PROFILE_DIR = os.path.expanduser("~/chrome-debug-profile")

# CDP port for connecting to existing Chrome
CDP_PORT = 9222


class BrowserConnection:
    """Manages Chrome browser connection for FamilySearch automation.

    This class handles:
    - CDP connection to existing Chrome instance
    - Launching new Chrome with persistent context
    - Finding/creating FamilySearch pages
    - Checking login status

    Example:
        async with BrowserConnection() as browser:
            page = await browser.get_familysearch_page()
            if page:
                # Do extraction
                pass

    Or manually:
        browser = BrowserConnection()
        try:
            if await browser.connect():
                page = await browser.get_familysearch_page()
        finally:
            await browser.disconnect()
    """

    def __init__(self, cdp_port: int = CDP_PORT, profile_dir: str = CHROME_PROFILE_DIR):
        """Initialize browser connection.

        Args:
            cdp_port: Port for CDP connection to existing Chrome
            profile_dir: Directory for persistent Chrome profile
        """
        self._cdp_port = cdp_port
        self._profile_dir = profile_dir
        self._context: BrowserContext | None = None
        self._playwright = None
        self._is_cdp_connection = False

    @property
    def is_connected(self) -> bool:
        """Whether browser is currently connected."""
        return self._context is not None

    @property
    def is_cdp(self) -> bool:
        """Whether connected via CDP (vs launched browser)."""
        return self._is_cdp_connection

    async def __aenter__(self) -> "BrowserConnection":
        """Async context manager entry - connect to browser."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - disconnect from browser."""
        await self.disconnect()

    async def connect(self) -> bool:
        """Connect to Chrome browser.

        Strategy:
        1. First try CDP connection to existing Chrome (port 9222)
        2. If that fails, launch new Chrome with persistent context

        Returns:
            True if connected successfully, False otherwise
        """
        self._playwright = await async_playwright().start()

        # Try CDP connection first
        if await self._try_cdp_connection():
            return True

        # Fallback to launching new Chrome
        return await self._try_launch_chrome()

    async def _try_cdp_connection(self) -> bool:
        """Try connecting to existing Chrome via CDP.

        Returns:
            True if connected, False otherwise
        """
        try:
            logger.info(f"Attempting CDP connection on port {self._cdp_port}...")
            browser = await self._playwright.chromium.connect_over_cdp(
                f"http://localhost:{self._cdp_port}"
            )

            contexts = browser.contexts
            if contexts:
                self._context = contexts[0]
                self._is_cdp_connection = True
                logger.info(
                    f"Connected via CDP - {len(self._context.pages)} page(s)"
                )
                return True
            else:
                logger.warning("CDP connection has no contexts")
                await browser.close()
                return False

        except Exception as e:
            logger.info(f"CDP connection failed (Chrome may not be running): {e}")
            return False

    async def _try_launch_chrome(self) -> bool:
        """Launch new Chrome with persistent context.

        Returns:
            True if launched, False otherwise
        """
        try:
            logger.info("Launching Chrome with persistent context...")
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=self._profile_dir,
                headless=False,
                channel="chrome",
                args=[
                    f"--remote-debugging-port={self._cdp_port}",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            self._is_cdp_connection = False
            logger.info(
                f"Launched Chrome - {len(self._context.pages)} page(s)"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to launch Chrome: {e}")
            logger.warning(
                "Ensure Chrome is not running with the same profile directory"
            )
            return False

    async def disconnect(self) -> None:
        """Disconnect from Chrome browser."""
        if self._context:
            try:
                await self._context.close()
            except Exception as e:
                logger.warning(f"Error closing browser context: {e}")
            self._context = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning(f"Error stopping Playwright: {e}")
            self._playwright = None

        self._is_cdp_connection = False
        logger.info("Disconnected from Chrome")

    async def get_familysearch_page(self) -> Page | None:
        """Get an existing FamilySearch page or return first available page.

        Looks for a page already on familysearch.org. If none found,
        returns the first available page.

        Returns:
            Page instance or None if no pages available
        """
        if not self._context and not await self.connect():
            return None

        pages = self._context.pages

        # Look for existing FamilySearch tab
        for page in pages:
            if "familysearch.org" in page.url:
                logger.info(f"Found FamilySearch tab: {page.url}")
                return page

        # Return first available page
        if pages:
            logger.info(f"No FamilySearch tab, using: {pages[0].url}")
            return pages[0]

        logger.error("No browser pages available")
        return None

    async def get_or_create_page(self) -> Page | None:
        """Get existing page or create new one.

        For CDP connections, only returns existing pages.
        For launched browsers, can create new pages.

        Returns:
            Page instance or None if unavailable
        """
        if not self._context and not await self.connect():
            return None

        # Try to get existing FamilySearch page
        page = await self.get_familysearch_page()
        if page:
            return page

        # For launched browser (not CDP), we can create new pages
        if not self._is_cdp_connection:
            try:
                page = await self._context.new_page()
                logger.info("Created new browser page")
                return page
            except Exception as e:
                logger.error(f"Failed to create new page: {e}")

        return None

    async def check_login_status(self) -> bool:
        """Check if user is logged into FamilySearch.

        Navigates to FamilySearch homepage if not already there and
        checks for login indicators.

        Returns:
            True if logged in, False otherwise
        """
        try:
            page = await self.get_or_create_page()
            if not page:
                logger.warning("Cannot check login - no page available")
                return False

            # Navigate to FamilySearch if not already there
            if "familysearch.org" not in page.url:
                logger.info("Navigating to FamilySearch to check login...")
                try:
                    await asyncio.wait_for(
                        page.goto(
                            "https://www.familysearch.org",
                            wait_until="domcontentloaded"
                        ),
                        timeout=10.0
                    )
                except Exception as e:
                    logger.warning(f"Failed to navigate: {e}")
                    return False

            await asyncio.sleep(1)  # Wait for page render

            # Check if on signin page
            if "/auth/signin" in page.url or "/login" in page.url:
                logger.info("On sign-in page - not logged in")
                return False

            # Check for login indicators using Playwright locators
            # Look for sign-in button (indicates NOT logged in)
            sign_in_link = page.locator('a[href*="signin"]')
            if await sign_in_link.count() > 0:
                text = await sign_in_link.first.inner_text()
                if "sign in" in text.lower():
                    logger.info("Sign-in link found - not logged in")
                    return False

            # Look for user menu (indicates logged in)
            user_menu = page.locator(
                '[data-testid="user-menu"], '
                '[aria-label*="account"], '
                '[aria-label*="user"]'
            )
            if await user_menu.count() > 0:
                logger.info("User menu found - logged in")
                return True

            # Check page text for account indicators
            body_text = await page.inner_text("body")
            if "My Account" in body_text or "Sign Out" in body_text:
                logger.info("Account text found - logged in")
                return True

            # Check URL for logged-in portal
            if "/en/home/portal" in page.url or "/en/discovery" in page.url:
                logger.info("On portal page - logged in")
                return True

            logger.warning("Cannot determine login status")
            return False

        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            return False

    async def navigate_to(
        self,
        url: str,
        *,
        timeout: float = 10.0,
        wait_for_selector: str | None = None,
    ) -> Page | None:
        """Navigate to a URL and optionally wait for selector.

        Args:
            url: URL to navigate to
            timeout: Navigation timeout in seconds
            wait_for_selector: Optional selector to wait for after navigation

        Returns:
            Page if navigation successful, None otherwise
        """
        page = await self.get_or_create_page()
        if not page:
            return None

        # Skip navigation if already on target URL
        current_base = page.url.split("?")[0]
        target_base = url.split("?")[0]

        if current_base == target_base:
            logger.info(f"Already on target page: {page.url}")
        else:
            logger.info(f"Navigating to: {url}")
            try:
                await asyncio.wait_for(
                    page.goto(url, wait_until="domcontentloaded"),
                    timeout=timeout
                )
            except TimeoutError:
                logger.warning(f"Navigation timed out after {timeout}s")
                if "familysearch.org" not in page.url:
                    return None
            except Exception as e:
                logger.warning(f"Navigation failed: {e}")
                if "familysearch.org" not in page.url:
                    return None

        # Wait for selector if specified
        if wait_for_selector:
            try:
                await page.wait_for_selector(wait_for_selector, timeout=15000)
            except Exception as e:
                logger.warning(f"Timeout waiting for {wait_for_selector}: {e}")

        return page
