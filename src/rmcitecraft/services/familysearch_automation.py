r"""
FamilySearch Automation Service using Playwright

DEPRECATION NOTICE:
    This module is being replaced by rmcitecraft.services.familysearch.
    For new code, use:
        from rmcitecraft.services.familysearch import CensusExtractor

    The extract_citation_data() method now delegates to the new unified
    CensusExtractor for consistent extraction across all census years.

Launches Chrome with persistent context to:
- Extract census citation data from FamilySearch pages
- Automate census image downloads
- Handle FamilySearch dialogs and navigation

Uses persistent Chrome profile for login persistence:
    - Profile directory: ~/chrome-debug-profile
    - Login once to FamilySearch, stays logged in across sessions
    - Separate from your main Chrome browser

Note: Playwright launches and manages Chrome directly (not CDP connection).
"""

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger
from playwright.async_api import BrowserContext, Page, async_playwright

# Chrome profile directory (persistent login)
CHROME_PROFILE_DIR = os.path.expanduser("~/chrome-debug-profile")


class FamilySearchAutomation:
    """Automates FamilySearch interactions using Playwright-launched Chrome."""

    def __init__(self):
        """Initialize automation service."""
        self.browser: BrowserContext | None = None
        self.playwright = None

    async def connect_to_chrome(self) -> bool:
        """
        Connect to Chrome browser for FamilySearch automation.

        Strategy:
        1. First try to connect to existing Chrome (CDP on port 9222)
        2. If that fails, launch new Chrome with persistent context

        Uses persistent user profile to maintain FamilySearch login across sessions.

        Returns:
            True if connected successfully, False otherwise
        """
        self.playwright = await async_playwright().start()

        # Try connecting to existing Chrome first (via CDP)
        try:
            logger.info("Attempting to connect to existing Chrome via CDP...")
            browser = await self.playwright.chromium.connect_over_cdp("http://localhost:9222")

            # CDP returns a Browser, but we need BrowserContext
            contexts = browser.contexts
            if contexts:
                self.browser = contexts[0]  # Use first context
                logger.info(
                    f"Connected to existing Chrome via CDP - {len(self.browser.pages)} page(s)"
                )
                return True
            else:
                logger.warning("CDP connection has no contexts")
                await browser.close()
        except Exception as e:
            logger.info(f"CDP connection failed (Chrome may not be running): {e}")

        # Fallback: Launch new Chrome with persistent context
        try:
            logger.info("Launching new Chrome with persistent context...")
            self.browser = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=CHROME_PROFILE_DIR,
                headless=False,  # Keep visible so user can log in if needed
                channel="chrome",  # Use system Chrome
                args=[
                    "--remote-debugging-port=9222",
                    "--disable-blink-features=AutomationControlled",
                ],
            )

            logger.info(f"Launched Chrome with persistent context - {len(self.browser.pages)} page(s)")
            return True
        except Exception as e:
            logger.error(f"Failed to launch Chrome: {e}")
            logger.warning(
                "Make sure Chrome is not already running with the same profile directory"
            )
            return False

    async def disconnect(self):
        """Disconnect from Chrome browser."""
        if self.browser:
            try:
                await self.browser.close()
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")
            self.browser = None

        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception as e:
                logger.warning(f"Error stopping playwright: {e}")
            self.playwright = None

        logger.info("Disconnected from Chrome")

    async def check_login_status(self) -> bool:
        """
        Check if user is logged into FamilySearch.

        Returns:
            True if logged in, False if not logged in or cannot determine

        Strategy:
            1. Look for FamilySearch page in Chrome tabs
            2. Check for login indicators (sign in button vs user menu)
            3. Return False if on signin page or no user elements found
        """
        try:
            page = await self.get_or_create_page()
            if not page:
                logger.warning("Cannot check login status - no browser page available")
                return False

            # If not on FamilySearch domain, navigate to homepage
            if "familysearch.org" not in page.url:
                logger.info("Navigating to FamilySearch homepage to check login status...")
                try:
                    await asyncio.wait_for(
                        page.goto("https://www.familysearch.org", wait_until="domcontentloaded"),
                        timeout=10.0
                    )
                except Exception as e:
                    logger.warning(f"Failed to navigate to FamilySearch: {e}")
                    return False

            # Wait for page to render
            await asyncio.sleep(1)

            # Check if on signin page (indicates not logged in)
            if "/auth/signin" in page.url or "/login" in page.url:
                logger.info("Currently on FamilySearch sign-in page - not logged in")
                return False

            # Check for login indicators in the DOM
            # FamilySearch shows "Sign In" button when not logged in
            # Shows user menu/account icon when logged in
            login_status = await page.evaluate("""
                () => {
                    // Check for sign-in button (not logged in)
                    const signInLink = document.querySelector('a[href*="signin"]');
                    if (signInLink && signInLink.textContent.toLowerCase().includes('sign in')) {
                        return { loggedIn: false, indicator: 'sign-in-link-found' };
                    }

                    // Check for sign-in button by text content
                    const buttons = document.querySelectorAll('button');
                    for (const button of buttons) {
                        if (button.textContent.toLowerCase().includes('sign in')) {
                            return { loggedIn: false, indicator: 'sign-in-button-found' };
                        }
                    }

                    // Check for user menu/account elements (logged in)
                    // FamilySearch uses various selectors for user menu
                    const userMenu = document.querySelector('[data-testid="user-menu"], [aria-label*="account"], [aria-label*="user"]');
                    if (userMenu) {
                        return { loggedIn: true, indicator: 'user-menu-found' };
                    }

                    // Check for "My Account" or username display
                    const bodyText = document.body.innerText;
                    if (bodyText.includes('My Account') || bodyText.includes('Sign Out')) {
                        return { loggedIn: true, indicator: 'account-text-found' };
                    }

                    // Check for FamilySearch portal page (usually means logged in)
                    const url = window.location.href;
                    if (url.includes('/en/home/portal') || url.includes('/en/discovery')) {
                        return { loggedIn: true, indicator: 'portal-url' };
                    }

                    // Check for common header elements on logged-in pages
                    const header = document.querySelector('header, [role="banner"]');
                    if (header) {
                        const headerText = header.innerText || '';
                        if (headerText.includes('Family Tree') || headerText.includes('Search') || headerText.includes('Memories')) {
                            return { loggedIn: true, indicator: 'logged-in-navigation' };
                        }
                    }

                    // Cannot determine
                    return { loggedIn: false, indicator: 'no-indicators-found' };
                }
            """)

            is_logged_in = login_status.get("loggedIn", False)
            indicator = login_status.get("indicator", "unknown")

            if is_logged_in:
                logger.info(f"FamilySearch login verified ({indicator})")
            else:
                logger.warning(f"FamilySearch login required ({indicator})")

            return is_logged_in

        except Exception as e:
            logger.error(f"Error checking FamilySearch login status: {e}")
            return False

    async def get_or_create_page(self) -> Page | None:
        """
        Get an existing FamilySearch page or create a new one.

        Returns:
            Page instance or None if connection failed
        """
        if not self.browser and not await self.connect_to_chrome():
            return None

        # self.browser is now a BrowserContext directly (from launch_persistent_context)
        context = self.browser

        # Look for existing FamilySearch tab
        pages = context.pages
        for page in pages:
            if "familysearch.org" in page.url:
                logger.info(f"Found existing FamilySearch tab: {page.url}")
                return page

        # If no FamilySearch tab found, create a new page (safe with launched browser)
        # With launch_persistent_context, we can safely call new_page()
        if pages:
            logger.info(f"No FamilySearch tab found, using existing page: {pages[0].url}")
            logger.warning(
                "For best results, open FamilySearch in a Chrome tab before running automation"
            )
            return pages[0]

        # No pages available at all
        logger.error("No browser pages available - cannot proceed")
        return None

    async def extract_citation_data(self, url: str, census_year: int | None = None) -> dict[str, Any] | None:
        """
        Navigate to FamilySearch census record page and extract citation data.

        Args:
            url: FamilySearch record URL (ARK format)
            census_year: Census year (1790-1950) for year-specific extraction logic

        Returns:
            Dictionary with citation data or None if extraction failed
        """
        try:
            page = await self.get_or_create_page()
            if not page:
                return None

            # Check if we're already on the target page (skip navigation if so)
            # Compare URLs without query parameters
            current_url_base = page.url.split("?")[0]
            target_url_base = url.split("?")[0]

            if current_url_base == target_url_base:
                logger.info(f"Already on target page: {page.url}")
            else:
                logger.info(f"Navigating to FamilySearch record: {url}")
                # Note: CDP connections can be slow/unreliable with navigation
                # Use asyncio.wait_for to enforce timeout (page.goto timeout doesn't work with CDP)
                try:
                    await asyncio.wait_for(
                        page.goto(url, wait_until="domcontentloaded"),
                        timeout=10.0
                    )
                except TimeoutError:
                    logger.warning("Navigation timed out after 10 seconds")
                    # Check if we're at least on FamilySearch
                    if "familysearch.org" not in page.url:
                        raise
                except Exception as e:
                    logger.warning(f"Navigation failed: {e}")
                    if "familysearch.org" not in page.url:
                        raise

            # Wait for census record content to render (FamilySearch is a React SPA)
            # Wait for h1 (person name) to appear - indicates page has rendered
            logger.info("Waiting for page content to render...")
            try:
                await page.wait_for_selector('h1', timeout=15000)
                logger.info("Page content rendered")
            except Exception as e:
                logger.warning(f"Timeout waiting for h1: {e}")
                # Continue anyway, maybe we can still extract some data

            # Extract citation data from page using Playwright selectors
            # Note: Using selectors instead of page.evaluate() - more reliable with CDP
            logger.info("Extracting citation data using selectors...")

            citation_data = {}

            # Extract person name from H1
            person_name_elem = await page.query_selector('h1')
            citation_data["personName"] = (
                await person_name_elem.text_content() if person_name_elem else ""
            ).strip()

            # Extract event date - census records display year in title/breadcrumb, not as separate field
            # Look for "United States, Census, YYYY" pattern in page title
            page_title = await page.title()
            import re
            year_match = re.search(r'Census,?\s*(\d{4})', page_title)
            citation_data["eventDate"] = year_match.group(1) if year_match else ""

            # Extract event place and census details from table structure
            # Use Playwright native features for more reliable extraction with CDP
            table_data = await self._extract_table_data_playwright(page, census_year)

            # Log found labels for debugging
            found_labels = table_data.get("foundLabels", [])
            if found_labels:
                logger.debug(f"Found {len(found_labels)} table labels on FamilySearch page (first 10): {', '.join(found_labels[:10])}")
                # Log census-specific fields if present
                census_fields = [label for label in found_labels if any(key in label for key in ['line', 'sheet', 'enumeration', 'district', 'page', 'family', 'dwelling'])]
                if census_fields:
                    logger.debug(f"Census-related fields found: {', '.join(census_fields)}")
            else:
                logger.warning("No table labels found on FamilySearch page")

            # DEBUG: Log what raw values were extracted
            logger.debug(f"Raw extraction: ED='{table_data.get('enumerationDistrict', '')}', sheetNum='{table_data.get('sheetNumber', '')}', sheetLetter='{table_data.get('sheetLetter', '')}', line='{table_data.get('line', '')}', page='{table_data.get('pageNumber', '')}')")

            citation_data["eventPlace"] = table_data.get("eventPlace", "")
            citation_data["enumerationDistrict"] = table_data.get("enumerationDistrict", "")

            # Handle sheet or page (depending on census year)
            sheet_number = table_data.get("sheetNumber", "")
            sheet_letter = table_data.get("sheetLetter", "")
            page_number = table_data.get("pageNumber", "")

            # Sheet (1880-1940): Combine sheet number and letter (e.g., "19" + "B" = "19B")
            if sheet_number and sheet_letter:
                citation_data["sheet"] = f"{sheet_number}{sheet_letter}"
            elif sheet_number:
                citation_data["sheet"] = sheet_number
            else:
                citation_data["sheet"] = ""

            # Page (1790-1870, 1950)
            citation_data["page"] = page_number

            # Special case for 1950: FamilySearch calls it "Page Number" but citations use "sheet" terminology
            # Copy page number to sheet for consistent formatting with Evidence Explained standards
            if census_year == 1950 and page_number and not citation_data.get("sheet"):
                citation_data["sheet"] = page_number
                logger.debug(f"1950 census: Copied page number '{page_number}' to sheet field")

            citation_data["line"] = table_data.get("line", "")
            citation_data["familyNumber"] = table_data.get("family", "")
            citation_data["dwellingNumber"] = table_data.get("dwelling", "")

            # 1910 Census-specific fields: Pass through to transform for year-specific handling
            # These need to be passed through for YearSpecificHandler to process
            citation_data["householdId"] = table_data.get("householdId", "")  # Maps to family_number
            citation_data["district"] = table_data.get("district", "")  # "ED 340" format
            citation_data["sourceSheetNumber"] = table_data.get("sourceSheetNumber", "")
            citation_data["sourceSheetLetter"] = table_data.get("sourceSheetLetter", "")
            citation_data["township"] = table_data.get("township", "")

            # DEBUG: Log what was set in citation_data before transform
            logger.debug(f"citation_data before transform: sheet='{citation_data.get('sheet', 'KEY_MISSING')}', line='{citation_data.get('line', 'KEY_MISSING')}', page='{citation_data.get('page', 'KEY_MISSING')}'")

            # DEBUG: Log 1880-specific fields for troubleshooting
            if census_year == 1880:
                all_labels = table_data.get('foundLabels', [])
                logger.info(f"1880 Census extraction - line='{table_data.get('line', '')}', ED='{table_data.get('enumerationDistrict', '')}'")
                logger.info(f"1880 Census extraction - ALL {len(all_labels)} labels found: {all_labels}")

            # DEBUG: Log 1910-specific fields for troubleshooting
            if census_year == 1910:
                logger.info(f"1910 Census extraction - district='{table_data.get('district', '')}', householdId='{table_data.get('householdId', '')}', ED='{table_data.get('enumerationDistrict', '')}', line='{table_data.get('line', '')}'")
                all_labels = table_data.get('foundLabels', [])
                logger.info(f"1910 Census extraction - ALL {len(all_labels)} labels found: {all_labels}")

            # Extract FamilySearch citation text
            citation_elems = await page.query_selector_all(
                '[data-testid="citation-text"], .citation'
            )
            familysearch_entry = ""
            for elem in citation_elems:
                text = (await elem.text_content()).strip()
                if text and len(text) > 50:
                    familysearch_entry = text
                    break
            citation_data["familySearchEntry"] = familysearch_entry

            # Extract current URL
            citation_data["arkUrl"] = page.url

            # Extract image viewer URL (convert relative URL to absolute)
            # Try multiple selectors for image links - FamilySearch uses different patterns
            image_selectors = [
                'a[href*="/ark:/61903/3:1:"]',  # Standard ARK pattern for images
                'a[href*="/ark:/61903/3:"]',    # More general ARK pattern
                'a[href*="image-viewer"]',      # Image viewer link
                '[data-testid="view-image-link"]',  # Data-testid attribute
                'a:has-text("View Image")',    # Link text pattern
            ]

            image_link = None
            for selector in image_selectors:
                try:
                    image_link = await page.query_selector(selector)
                    if image_link:
                        break
                except Exception:
                    continue

            if image_link:
                href = await image_link.get_attribute("href")
                # Convert relative URL to absolute
                if href and href.startswith("/"):
                    href = f"https://www.familysearch.org{href}"
                citation_data["imageViewerUrl"] = href or ""
                logger.debug(f"Found image viewer URL: {href}")
            else:
                citation_data["imageViewerUrl"] = ""
                logger.warning(f"Could not find image viewer URL on page: {url}")

            # Extract page title
            citation_data["pageTitle"] = await page.title()

            logger.info(f"Extracted citation data: {citation_data['personName']}")

            # Transform to expected format (snake_case keys, parsed location)
            transformed = self._transform_citation_data(citation_data, census_year)

            # 1930 Census Special Case: ED and Family Number are on the detail page, not main page
            # Navigate to detail page if we're missing these fields
            if census_year == 1930:
                ed = transformed.get('enumeration_district', '')
                family = transformed.get('family_number', '')

                if not ed or not family:
                    image_viewer_url = citation_data.get("imageViewerUrl", "")
                    if image_viewer_url:
                        logger.info("1930 census: ED or Family Number missing, extracting from detail page...")
                        detail_data = await self._extract_1930_detail_page_data(page, image_viewer_url)

                        if detail_data:
                            if not ed and detail_data.get('enumeration_district'):
                                transformed['enumeration_district'] = detail_data['enumeration_district']
                                logger.info(f"1930 census: Extracted ED '{detail_data['enumeration_district']}' from detail page")
                            if not family and detail_data.get('family_number'):
                                transformed['family_number'] = detail_data['family_number']
                                logger.info(f"1930 census: Extracted Family Number '{detail_data['family_number']}' from detail page")

            # 1880 Census Special Case: External Line Number is on the detail page, not main page
            # Navigate to detail page if line number is missing
            if census_year == 1880:
                line = transformed.get('line', '')

                if not line:
                    image_viewer_url = citation_data.get("imageViewerUrl", "")
                    if image_viewer_url:
                        logger.info("1880 census: Line number missing, extracting from detail page...")
                        detail_data = await self._extract_1880_detail_page_data(page, image_viewer_url)

                        if detail_data and detail_data.get('line_number'):
                            transformed['line'] = detail_data['line_number']
                            logger.info(f"1880 census: Extracted line number '{detail_data['line_number']}' from detail page")

            return transformed


        except Exception as e:
            logger.error(f"Failed to extract citation data: {e}", exc_info=True)
            return None

    def _get_extraction_javascript(self, census_year: int | None) -> str:
        """
        Generate year-specific JavaScript for extracting census data from FamilySearch pages.

        DEPRECATED: This method is no longer used. Use _extract_table_data_playwright()
        instead, which uses Playwright's native locators for more reliable extraction.

        This JavaScript approach was replaced because:
        1. Playwright locators are more maintainable and testable
        2. CDP connections work better with native Playwright methods
        3. The unified extraction architecture uses Playwright-first policy

        Census Eras:
        - 1790-1840: Page only (household head names, no individual records)
        - 1850-1870: Page + line (NO enumeration district)
        - 1880-1940: ED + sheet + line (NO page)
        - 1950: Page + line + ED (different structure)

        Args:
            census_year: Census year to determine extraction strategy

        Returns:
            JavaScript code string for page.evaluate()
        """
        # Determine which fields to extract based on census year
        if census_year is None:
            # No year provided - extract all possible fields (generic fallback)
            extract_ed = True
            extract_sheet = True
            extract_page = True
            extract_line = True
        elif 1790 <= census_year <= 1840:
            # Era 1: Household only - page numbers only
            extract_ed = False
            extract_sheet = False
            extract_page = True
            extract_line = False  # No individual line numbers
        elif 1850 <= census_year <= 1870:
            # Era 2: Individual, NO ED - page + line
            extract_ed = False
            extract_sheet = False
            extract_page = True
            extract_line = True
        elif 1880 <= census_year <= 1940:
            # Era 3: With ED - ED + sheet + line (NO page)
            extract_ed = True
            extract_sheet = True
            extract_page = False
            extract_line = True
        elif census_year == 1950:
            # Era 4: Modern - page + line + ED
            extract_ed = True
            extract_sheet = False
            extract_page = True
            extract_line = True
        else:
            # Unknown year - extract all fields
            extract_ed = True
            extract_sheet = True
            extract_page = True
            extract_line = True

        # 1940 census: Use only "Event Place" (not "Event Place (Original)")
        is_1940 = census_year == 1940

        # Build JavaScript extraction code
        return f"""
            () => {{
                const result = {{
                    eventPlace: '',
                    enumerationDistrict: '',
                    sheetNumber: '',
                    sheetLetter: '',
                    pageNumber: '',
                    line: '',
                    family: '',
                    dwelling: '',
                    // 1910 Census-specific fields
                    district: '',
                    sourceSheetNumber: '',
                    sourceSheetLetter: '',
                    householdId: '',
                    township: '',
                    foundLabels: []  // Debug: track what labels we find
                }};

                const tables = document.querySelectorAll('table');
                for (const table of tables) {{
                    const rows = table.querySelectorAll('tr');
                    for (const row of rows) {{
                        const cells = row.querySelectorAll('td, th');
                        if (cells.length >= 2) {{
                            const label = cells[0].textContent.trim().toLowerCase();
                            const value = cells[1].textContent.trim();

                            // Track all labels found (for debugging)
                            if (label && value) {{
                                result.foundLabels.push(label);
                            }}

                            // Event place extraction
                            // 1940 census: Use ONLY "Event Place" (not "Event Place (Original)")
                            // Other years: Prioritize "Event Place (Original)" for 1920 census (contains ED)
                            if ({str(not is_1940).lower()} && label === 'event place (original)') {{
                                result.eventPlace = value;
                                result.eventPlaceOriginal = value;  // Store original separately
                            }}
                            else if (label === 'event place' && !result.eventPlace) {{
                                result.eventPlace = value;
                            }}
                            // Enumeration District (1880-1950)
                            else if ({str(extract_ed).lower()} && (label.includes('enumeration') || label === 'ed' || label === 'e.d.')) {{
                                result.enumerationDistrict = value;
                            }}
                            // 1910 Census: "District" field with "ED 340" format
                            else if ({str(extract_ed).lower()} && label === 'district') {{
                                result.district = value;
                            }}
                            // Sheet number (1880-1940)
                            else if ({str(extract_sheet).lower()} && (label === 'sheet number' || (label.includes('sheet') && !label.includes('letter') && !label.includes('source')))) {{
                                result.sheetNumber = value;
                            }}
                            // 1910 Census: "Source Sheet Number"
                            else if ({str(extract_sheet).lower()} && label === 'source sheet number') {{
                                result.sourceSheetNumber = value;
                            }}
                            // Sheet letter (1880-1940)
                            else if ({str(extract_sheet).lower()} && label === 'sheet letter') {{
                                result.sheetLetter = value;
                            }}
                            // 1910 Census: "Source Sheet Letter"
                            else if ({str(extract_sheet).lower()} && label === 'source sheet letter') {{
                                result.sourceSheetLetter = value;
                            }}
                            // Page number (1790-1870, 1950)
                            else if ({str(extract_page).lower()} && (label === 'page number' || label === 'page' || label === 'page no.')) {{
                                result.pageNumber = value;
                            }}
                            // Line number (1850-1950, excluding 1790-1840)
                            else if ({str(extract_line).lower()} && (label === 'line number' || label === 'line' || label === 'line no.')) {{
                                result.line = value;
                            }}
                            // Family number (optional, all years)
                            else if (label.includes('family')) {{
                                result.family = value;
                            }}
                            // 1910 Census: "HOUSEHOLD_ID" field for family number
                            else if (label === 'household_id' || label === 'household id') {{
                                result.householdId = value;
                            }}
                            // Dwelling number (optional, all years)
                            else if (label.includes('dwelling')) {{
                                result.dwelling = value;
                            }}
                            // 1910 Census: "Township" field
                            else if (label === 'township') {{
                                result.township = value;
                            }}
                        }}
                    }}
                }}
                return result;
            }}
        """

    async def _extract_1930_detail_page_data(
        self, page: Page, image_viewer_url: str
    ) -> dict[str, str] | None:
        """
        Extract ED and Family Number from 1930 census detail/image viewer page.

        The 1930 census doesn't show ED and Family Number on the main person page.
        Instead, they appear on the detail page in the right sidebar:
        - District: ED X
        - HOUSEHOLD_ID: X

        Args:
            page: Playwright Page object
            image_viewer_url: URL to the detail/image viewer page

        Returns:
            Dict with enumeration_district and family_number, or None on error
        """
        result = {
            'enumeration_district': '',
            'family_number': '',
        }

        try:
            logger.debug(f"Navigating to 1930 detail page: {image_viewer_url}")

            # Navigate to the detail page
            try:
                await asyncio.wait_for(
                    page.goto(image_viewer_url, wait_until="domcontentloaded"),
                    timeout=15.0
                )
            except TimeoutError:
                logger.warning("1930 detail page navigation timed out after 15 seconds")
                # Continue anyway if we're on FamilySearch
                if "familysearch.org" not in page.url:
                    return None

            # Wait for sidebar to render - the District field appears in the sidebar
            try:
                await page.wait_for_selector('text=District:', timeout=10000)
                logger.debug("1930 detail page: Found 'District:' text, sidebar loaded")
            except Exception as e:
                logger.warning(f"1930 detail page: Timeout waiting for 'District:' text: {e}")
                # Try a shorter sleep and continue anyway
                await asyncio.sleep(2)

            # Get all text content from the page body
            body_text = await page.text_content('body')

            if not body_text:
                logger.warning("1930 detail page has no body text")
                return None

            # Extract District: ED X pattern
            # Format: "District: ED 4" or "District: ED 4-5"
            district_match = re.search(r'District[:\s]*(ED[-\s]*\d+[-\d]*)', body_text, re.IGNORECASE)
            if district_match:
                ed_value = district_match.group(1).strip()
                # Clean up: "ED 4" -> "4", "ED4" -> "4"
                ed_clean = re.sub(r'^ED[-\s]*', '', ed_value, flags=re.IGNORECASE)
                result['enumeration_district'] = ed_clean
                logger.debug(f"1930 detail page: Found ED '{ed_clean}' from '{district_match.group(0)}'")

            # Extract HOUSEHOLD_ID: X pattern
            # Format: "HOUSEHOLD_ID: 258"
            household_match = re.search(r'HOUSEHOLD_ID[:\s]*(\d+)', body_text, re.IGNORECASE)
            if household_match:
                result['family_number'] = household_match.group(1)
                logger.debug(f"1930 detail page: Found Family Number '{household_match.group(1)}'")

            return result

        except Exception as e:
            logger.warning(f"Error extracting 1930 detail page data: {e}")
            return None

    async def _extract_1880_detail_page_data(
        self, page: Page, image_viewer_url: str
    ) -> dict[str, str] | None:
        """
        Extract External Line Number from 1880 census detail/image viewer page.

        The 1880 census shows "External Line Number" on the detail page in the
        right sidebar, not on the main person page.

        Args:
            page: Playwright Page object
            image_viewer_url: URL to the detail/image viewer page

        Returns:
            Dict with line_number, or None on error
        """
        result = {
            'line_number': '',
        }

        try:
            logger.debug(f"Navigating to 1880 detail page: {image_viewer_url}")

            # Navigate to the detail page
            try:
                await asyncio.wait_for(
                    page.goto(image_viewer_url, wait_until="domcontentloaded"),
                    timeout=15.0
                )
            except TimeoutError:
                logger.warning("1880 detail page navigation timed out after 15 seconds")
                # Continue anyway if we're on FamilySearch
                if "familysearch.org" not in page.url:
                    return None

            # Wait for sidebar to render
            try:
                await page.wait_for_selector('text=External Line Number', timeout=10000)
                logger.debug("1880 detail page: Found 'External Line Number' text, sidebar loaded")
            except Exception as e:
                logger.warning(f"1880 detail page: Timeout waiting for 'External Line Number' text: {e}")
                # Try a shorter sleep and continue anyway
                await asyncio.sleep(2)

            # Get all text content from the page body
            body_text = await page.text_content('body')

            if not body_text:
                logger.warning("1880 detail page has no body text")
                return None

            # Extract External Line Number: XXXXX pattern
            # Format: "External Line Number: 00033" -> extract "00033"
            line_match = re.search(r'External\s+Line\s+Number[:\s]*(\d+)', body_text, re.IGNORECASE)
            if line_match:
                line_value = line_match.group(1)
                # Strip leading zeros: "00033" -> "33"
                stripped_line = line_value.lstrip('0')
                if stripped_line:
                    result['line_number'] = stripped_line
                else:
                    result['line_number'] = '0'  # Preserve single "0" for line 0
                logger.debug(f"1880 detail page: Found line number '{result['line_number']}' from '{line_match.group(0)}'")

            return result

        except Exception as e:
            logger.warning(f"Error extracting 1880 detail page data: {e}")
            return None

    def _get_extraction_flags(self, census_year: int | None) -> tuple[bool, bool, bool, bool]:
        """
        Determine which fields to extract based on census year.

        DEPRECATED: Use YearSpecificHandler.get_extraction_flags() instead.
        This method is kept for backward compatibility.

        Args:
            census_year: Census year to determine extraction strategy

        Returns:
            Tuple of (extract_ed, extract_sheet, extract_page, extract_line)
        """
        if census_year is None:
            # No year provided - extract all possible fields
            return (True, True, True, True)
        elif 1790 <= census_year <= 1840:
            # Era 1: Household only - page numbers only
            return (False, False, True, False)
        elif 1850 <= census_year <= 1870:
            # Era 2: Individual, NO ED - page + line
            return (False, False, True, True)
        elif 1880 <= census_year <= 1940:
            # Era 3: With ED - ED + sheet + line (NO page)
            return (True, True, False, True)
        elif census_year == 1950:
            # Era 4: Modern - page + line + ED
            return (True, False, True, True)
        else:
            # Unknown year - extract all fields
            return (True, True, True, True)

    async def _extract_table_data_playwright(
        self, page: Page, census_year: int | None
    ) -> dict[str, Any]:
        """
        Extract census data from tables using Playwright's native features.

        This replaces _get_extraction_javascript() for more reliable extraction
        when connected via CDP.

        Args:
            page: Playwright Page object
            census_year: Census year to determine extraction strategy

        Returns:
            Dict with eventPlace, enumerationDistrict, sheetNumber, sheetLetter,
            pageNumber, line, family, dwelling, foundLabels
        """
        result: dict[str, Any] = {
            "eventPlace": "",
            "enumerationDistrict": "",
            "sheetNumber": "",
            "sheetLetter": "",
            "pageNumber": "",
            "line": "",
            "family": "",
            "dwelling": "",
            # 1910 Census-specific fields
            "district": "",
            "sourceSheetNumber": "",
            "sourceSheetLetter": "",
            "householdId": "",
            "township": "",
            "foundLabels": [],
        }

        # Get year-specific extraction flags
        extract_ed, extract_sheet, extract_page, extract_line = self._get_extraction_flags(
            census_year
        )
        is_1940 = census_year == 1940

        try:
            tables = page.locator("table")
            table_count = await tables.count()
            logger.debug(f"Found {table_count} tables on page")

            for t in range(table_count):
                table = tables.nth(t)
                rows = table.locator("tr")
                row_count = await rows.count()

                for r in range(row_count):
                    row = rows.nth(r)
                    cells = row.locator("td, th")
                    cell_count = await cells.count()

                    if cell_count >= 2:
                        try:
                            label = (await cells.nth(0).inner_text()).strip().lower()
                            value = (await cells.nth(1).inner_text()).strip()

                            if label and value:
                                result["foundLabels"].append(label)

                                # Event place extraction
                                # 1940 census: Use ONLY "Event Place" (not "Event Place (Original)")
                                if (
                                    (not is_1940 and label == "event place (original)")
                                    or (label == "event place" and not result["eventPlace"])
                                ):
                                    result["eventPlace"] = value

                                # Enumeration District (1880-1950)
                                elif extract_ed and (
                                    "enumeration" in label or label in ["ed", "e.d."]
                                ):
                                    result["enumerationDistrict"] = value

                                # 1910 Census: "District" field with "ED 340" format
                                elif extract_ed and label == "district":
                                    result["district"] = value

                                # Sheet number (1880-1940)
                                elif (
                                    extract_sheet
                                    and "sheet" in label
                                    and "letter" not in label
                                    and "source" not in label
                                ):
                                    result["sheetNumber"] = value

                                # 1910 Census: "Source Sheet Number"
                                elif extract_sheet and label == "source sheet number":
                                    result["sourceSheetNumber"] = value

                                # Sheet letter (1880-1940)
                                elif extract_sheet and label == "sheet letter":
                                    result["sheetLetter"] = value

                                # 1910 Census: "Source Sheet Letter"
                                elif extract_sheet and label == "source sheet letter":
                                    result["sourceSheetLetter"] = value

                                # Page number (1790-1870, 1950)
                                elif extract_page and label in [
                                    "page number",
                                    "page",
                                    "page no.",
                                ]:
                                    result["pageNumber"] = value

                                # Line number (1850-1950)
                                # FamilySearch may use "Visitation Number" for some census years
                                # 1880 Census uses "External Line Number" on detail page
                                elif extract_line and (
                                    label in ["line number", "line", "line no.", "external line number"]
                                    or "visitation" in label
                                ):
                                    result["line"] = value

                                # Family number (optional, all years)
                                elif "family" in label:
                                    result["family"] = value

                                # 1910 Census: "HOUSEHOLD_ID" or "Household Identifier" for family number
                                # FamilySearch uses "household identifier" for 1910 Census
                                elif label in ["household_id", "household id", "home id", "household identifier"]:
                                    result["householdId"] = value
                                elif label == "household" and not result["householdId"]:
                                    result["householdId"] = value

                                # Dwelling number (optional, all years)
                                elif "dwelling" in label:
                                    result["dwelling"] = value

                                # 1910 Census: "Township" field
                                elif label == "township":
                                    result["township"] = value

                        except Exception as e:
                            logger.debug(f"Error extracting cell data: {e}")
                            continue

        except Exception as e:
            logger.warning(f"Error during Playwright table extraction: {e}")

        logger.debug(
            f"Playwright extraction found {len(result['foundLabels'])} labels: "
            f"{result['foundLabels'][:10]}"
        )
        return result

    def _transform_citation_data(self, raw_data: dict, census_year: int | None = None) -> dict:
        """
        Transform FamilySearch extraction format to expected citation format.

        Converts:
        - camelCase keys → snake_case keys
        - eventPlace string → separate state/county
        - Extracts enumeration_district from familySearchEntry

        Uses YearSpecificHandler for year-specific parsing to ensure
        consistency with the unified CensusExtractor.

        Args:
            raw_data: Raw extraction from FamilySearch page
            census_year: Census year for year-specific parsing (e.g., 1940)

        Returns:
            Transformed dict with keys: person_name, state, county,
            familysearch_url, enumeration_district, etc.
        """
        # DEBUG: Log what raw_data contains for census fields
        logger.debug(f"_transform_citation_data received: sheet='{raw_data.get('sheet', 'KEY_MISSING')}', line='{raw_data.get('line', 'KEY_MISSING')}', page='{raw_data.get('page', 'KEY_MISSING')}'")

        # Get year-specific handler if valid census year
        year_handler = None
        if census_year:
            try:
                from rmcitecraft.services.familysearch import YearSpecificHandler
                year_handler = YearSpecificHandler(census_year)
            except (ImportError, ValueError) as e:
                logger.debug(f"Could not create YearSpecificHandler: {e}")

        # DEBUG: Log raw_data keys for 1910 Census
        if census_year == 1910:
            logger.info(f"1910 transform: raw_data keys = {list(raw_data.keys())}")
            logger.info(f"1910 transform: district='{raw_data.get('district', 'KEY_NOT_FOUND')}', householdId='{raw_data.get('householdId', 'KEY_NOT_FOUND')}'")

        transformed = {}

        # Map camelCase to snake_case
        transformed['person_name'] = raw_data.get('personName', '')

        # Clean FamilySearch URL: Remove query parameters (e.g., ?lang=en)
        raw_url = raw_data.get('arkUrl', '')
        transformed['familysearch_url'] = raw_url.split('?')[0] if raw_url else ''

        # Generate access date in Evidence Explained format: "24 July 2015"
        now = datetime.now()
        transformed['access_date'] = now.strftime("%d %B %Y")

        # Parse eventPlace: "St. Louis, Missouri, United States" → state + county
        # For 1920 census: "Township, ED XX, County, State, United States"
        # For 1910 census: "Township, ED, County, State, United States" (ED is bare number)
        event_place = raw_data.get('eventPlace', '')
        if census_year == 1910:
            logger.info(f"1910 transform: eventPlace='{event_place}'")
        state, county = self._parse_event_place(event_place)
        transformed['state'] = state
        transformed['county'] = county

        # Use table-extracted census details first (more reliable)
        # For 1920 census, ED is often embedded in eventPlace instead of separate table row
        raw_ed = raw_data.get('enumerationDistrict', '')

        # Use YearSpecificHandler for ED parsing if available
        if year_handler:
            # Try district field first (1910 uses "District: ED 340" format)
            if not raw_ed:
                raw_ed = raw_data.get('district', '')
                if census_year == 1910:
                    logger.info(f"1910 transform: got district='{raw_ed}' from raw_data")

            parsed_ed = year_handler.parse_enumeration_district(raw_ed)
            if census_year == 1910:
                logger.info(f"1910 transform: parse_enumeration_district('{raw_ed}') -> '{parsed_ed}'")
            if parsed_ed:
                transformed['enumeration_district'] = parsed_ed
            else:
                transformed['enumeration_district'] = raw_ed or ''
        else:
            # Fallback: Legacy parsing without handler
            # 1910 Census: FamilySearch uses "district" field with "ED 340" format
            if not raw_ed and census_year == 1910:
                raw_district = raw_data.get('district', '')
                if raw_district:
                    ed_match = re.search(r'ED\s*(\d+)', raw_district, re.IGNORECASE)
                    if ed_match:
                        transformed['enumeration_district'] = ed_match.group(1)
                    else:
                        transformed['enumeration_district'] = raw_district
            # 1940 Census: Extract hyphenated ED pattern
            elif census_year == 1940 and raw_ed:
                ed_match = re.search(r'(\d+-\d+)', raw_ed)
                if ed_match:
                    transformed['enumeration_district'] = ed_match.group(1)
                else:
                    transformed['enumeration_district'] = raw_ed
            else:
                transformed['enumeration_district'] = raw_ed

        # Extract locality/township from Event Place
        # Format: "Locality, County, State, Country" or "Township, ED XX, County, State, Country" (1920)
        # Examples:
        #   - "Cumberland, Allegany, Maryland, United States" -> locality = "Cumberland"
        #   - "Jerusalem, ED 48, Davie, North Carolina, United States" -> locality = "Jerusalem"
        if event_place and not transformed.get('town_ward'):
            parts = [p.strip() for p in event_place.split(',')]
            if parts:
                # First part is typically the locality (city, township, ward, etc.)
                # Skip if it's just the county name repeated (some records don't have locality)
                first_part = parts[0]
                # Skip if first part is "ED XX" pattern (malformed data) or same as county
                if (
                    first_part
                    and not re.match(r'^ED\s+\d+', first_part, re.IGNORECASE)
                    and len(parts) >= 2
                    and first_part.lower() != transformed['county'].lower()
                ):
                    transformed['town_ward'] = first_part
                    logger.debug(f"Extracted locality '{first_part}' from Event Place: {event_place}")

        # Census-year specific ED extraction from Event Place (Original) if not already set
        if not transformed['enumeration_district'] and event_place:
            parts = [p.strip() for p in event_place.split(',')]

            # 1910 Census: ED is the second component as a bare number
            # Format: "Township, ED, County, State, United States"
            # Example: "Lander, 64, Fremont, Wyoming, United States" - ED is "64"
            if census_year == 1910 and len(parts) >= 4:
                second_part = parts[1]
                # Check if second part is a bare number (the ED)
                if re.match(r'^\d+$', second_part):
                    transformed['enumeration_district'] = second_part
                    logger.info(f"1910: Extracted ED '{second_part}' from Event Place (Original): {event_place}")

            # 1920 Census: ED is prefixed with "ED" in format "ED XX"
            # Format: "Township, ED XX, County, State, United States"
            if not transformed['enumeration_district']:
                ed_match = re.search(r'\bED\s+(\d+)', event_place, re.IGNORECASE)
                if ed_match:
                    transformed['enumeration_district'] = ed_match.group(1)
                    logger.debug(f"Extracted ED {ed_match.group(1)} from Event Place (Original): {event_place}")

        transformed['sheet'] = raw_data.get('sheet', '')
        transformed['page'] = raw_data.get('page', '')  # For 1790-1870, 1950
        transformed['line'] = raw_data.get('line', '')
        transformed['family_number'] = raw_data.get('familyNumber', '')
        transformed['dwelling_number'] = raw_data.get('dwellingNumber', '')

        # Year-specific field handling using YearSpecificHandler
        if year_handler:
            # Sheet: Handle source_sheet_number + source_sheet_letter combination
            if not transformed['sheet']:
                sheet_num = raw_data.get('source_sheet_number', '') or raw_data.get('sourceSheetNumber', '')
                sheet_letter = raw_data.get('source_sheet_letter', '') or raw_data.get('sourceSheetLetter', '')
                if sheet_num:
                    parsed_sheet = year_handler.parse_sheet(sheet_num, sheet_letter)
                    if parsed_sheet:
                        transformed['sheet'] = parsed_sheet

            # Household ID: Year-specific mapping (dwelling vs family number)
            if not transformed['family_number'] and not transformed['dwelling_number']:
                household_id = raw_data.get('household_id', '') or raw_data.get('householdId', '')
                if census_year == 1910:
                    logger.info(f"1910 transform: got householdId='{household_id}' from raw_data")
                if household_id:
                    dwelling, family = year_handler.parse_household_id(household_id)
                    if census_year == 1910:
                        logger.info(f"1910 transform: parse_household_id('{household_id}') -> dwelling='{dwelling}', family='{family}'")
                    if family:
                        transformed['family_number'] = family
                    if dwelling:
                        transformed['dwelling_number'] = dwelling

            # Township handling
            if not transformed.get('town_ward'):
                township = raw_data.get('township', '')
                if township:
                    transformed['town_ward'] = township

            # 1880 Census: Line number from "External Line Number" has leading zeros to strip
            # Example: "00033" -> "33"
            if census_year == 1880 and transformed['line']:
                stripped_line = transformed['line'].lstrip('0')
                if stripped_line:  # Preserve "0" if line was literally "0" or "00"
                    transformed['line'] = stripped_line
                else:
                    transformed['line'] = '0'  # Keep single "0" for line 0
                logger.debug(f"1880: Stripped leading zeros from line: '{raw_data.get('line', '')}' -> '{transformed['line']}'")

        elif census_year == 1880:
            # 1880 Census: Line number from "External Line Number" has leading zeros to strip
            # Example: "00033" -> "33"
            if transformed['line']:
                stripped_line = transformed['line'].lstrip('0')
                if stripped_line:  # Preserve "0" if line was literally "0" or "00"
                    transformed['line'] = stripped_line
                else:
                    transformed['line'] = '0'  # Keep single "0" for line 0
                logger.debug(f"1880: Stripped leading zeros from line: '{raw_data.get('line', '')}' -> '{transformed['line']}'")

        elif census_year == 1900:
            # Fallback: Legacy 1900-specific handling without handler
            # Household Identifier maps to family_number
            if not transformed['family_number']:
                household_id = raw_data.get('household_id', '') or raw_data.get('householdId', '')
                if household_id:
                    transformed['family_number'] = household_id

        elif census_year == 1910:
            # Fallback: Legacy 1910-specific handling without handler
            if not transformed['sheet']:
                sheet_num = raw_data.get('source_sheet_number', '') or raw_data.get('sourceSheetNumber', '')
                sheet_letter = raw_data.get('source_sheet_letter', '') or raw_data.get('sourceSheetLetter', '')
                if sheet_num:
                    if sheet_letter and not str(sheet_num).endswith(sheet_letter):
                        transformed['sheet'] = f"{sheet_num}{sheet_letter}"
                    else:
                        transformed['sheet'] = str(sheet_num)

            # Household Identifier maps to family_number
            if not transformed['family_number']:
                household_id = raw_data.get('household_id', '') or raw_data.get('householdId', '')
                if household_id:
                    transformed['family_number'] = household_id

            if not transformed.get('town_ward'):
                township = raw_data.get('township', '')
                if township:
                    transformed['town_ward'] = township

        # Initialize town_ward if not already set from Event Place parsing
        if 'town_ward' not in transformed:
            transformed['town_ward'] = ''

        # If ED not found in table, try extracting from citation text as fallback
        if not transformed['enumeration_district']:
            familysearch_entry = raw_data.get('familySearchEntry', '')
            census_details = self._extract_census_details(familysearch_entry)
            # Only update fields that are still empty (don't overwrite table-extracted values)
            for key, value in census_details.items():
                if not transformed.get(key):  # Only if current value is empty
                    transformed[key] = value

        # Copy other useful fields
        transformed['event_date'] = raw_data.get('eventDate', '')
        transformed['event_place'] = event_place
        transformed['image_viewer_url'] = raw_data.get('imageViewerUrl', '')

        logger.debug(f"Transformed citation data: state={state}, county={county}, ED={transformed.get('enumeration_district', 'N/A')}")

        # DEBUG: Log 1910-specific transformed values
        if census_year == 1910:
            logger.info(f"1910 Census TRANSFORMED - ED='{transformed.get('enumeration_district', '')}', family_number='{transformed.get('family_number', '')}', line='{transformed.get('line', '')}', sheet='{transformed.get('sheet', '')}'")
            logger.info(f"1910 Census FINAL extracted_data being returned: {transformed}")

        return transformed

    def _parse_event_place(self, event_place: str) -> tuple[str, str]:
        """
        Parse FamilySearch event place into state and county.

        Event place format: "County, State, Country" or "City, County, State, Country"
        For 1920 census: "Township, ED XX, County, State, Country"

        Args:
            event_place: Full event place string from FamilySearch

        Returns:
            Tuple of (state, county)
        """
        if not event_place:
            return '', ''

        # Split by comma and strip whitespace
        parts = [p.strip() for p in event_place.split(',')]

        # Remove "United States" if present
        parts = [p for p in parts if p.lower() not in ('united states', 'usa', 'us')]

        # Filter out ED parts (e.g., "ED 48") - these are not geographic locations
        # Save ED for later extraction
        parts = [p for p in parts if not re.match(r'^ED\s+\d+', p, re.IGNORECASE)]

        if len(parts) >= 2:
            # Last part should be state, second-to-last should be county
            state = parts[-1]
            county = parts[-2]

            # Remove common county suffixes for cleaner matching
            county = re.sub(r'\s+(County|Parish|Borough|Census Area)$', '', county, flags=re.IGNORECASE)

            return state, county
        elif len(parts) == 1:
            # Only one part - could be just state or just county, unclear
            return '', parts[0]

        return '', ''

    def _extract_census_details(self, familysearch_entry: str) -> dict:
        """
        Extract census-specific details from FamilySearch citation text.

        Looks for:
        - Enumeration District (ED)
        - Sheet number
        - Line number
        - Family number
        - Township/Ward

        Args:
            familysearch_entry: Full citation text from FamilySearch

        Returns:
            Dict with census detail fields
        """
        details = {
            'enumeration_district': '',
            'sheet': '',
            'line': '',
            'family_number': '',
            'dwelling_number': '',
            'town_ward': '',
        }

        if not familysearch_entry:
            return details

        # Extract ED (various formats)
        # "ED 95-123", "enumeration district (ED) 95", "E.D. 95", "ED95"
        ed_patterns = [
            r'(?:enumeration district|ED|E\.D\.)\s*[\(\s]*(\d+[\-\d]*)',
            r'ED\s*(\d+[\-\d]*)',
            r'E\.D\.\s*(\d+[\-\d]*)',
        ]
        for pattern in ed_patterns:
            match = re.search(pattern, familysearch_entry, re.IGNORECASE)
            if match:
                details['enumeration_district'] = match.group(1)
                break

        # Extract sheet number
        # "sheet 3B", "Sheet 5A", "pg 123"
        sheet_match = re.search(r'(?:sheet|page|pg|p\.)\s*(\d+[AB]?)', familysearch_entry, re.IGNORECASE)
        if sheet_match:
            details['sheet'] = sheet_match.group(1)

        # Extract line number
        line_match = re.search(r'line\s*(\d+)', familysearch_entry, re.IGNORECASE)
        if line_match:
            details['line'] = line_match.group(1)

        # Extract family number
        family_match = re.search(r'family\s*(?:number|#)?\s*(\d+)', familysearch_entry, re.IGNORECASE)
        if family_match:
            details['family_number'] = family_match.group(1)

        # Extract dwelling number
        dwelling_match = re.search(r'dwelling\s*(?:number|#)?\s*(\d+)', familysearch_entry, re.IGNORECASE)
        if dwelling_match:
            details['dwelling_number'] = dwelling_match.group(1)

        # Extract township/ward (more complex, often at start of location string)
        # Look for patterns like "Canton Township", "Ward 5", etc. in the entry
        # This is harder to extract reliably from full citation text
        # Leave empty for now - can be extracted from eventPlace if needed

        return details

    async def download_census_image(
        self, image_viewer_url: str, download_path: Path
    ) -> bool:
        """
        Navigate to image viewer and download census image as JPG.

        Args:
            image_viewer_url: FamilySearch image viewer URL
            download_path: Path where JPG should be saved

        Returns:
            True if download succeeded, False otherwise
        """
        try:
            page = await self.get_or_create_page()
            if not page:
                return False

            # Check if we're already on the target page (skip navigation if so)
            # Compare URLs without query parameters
            current_url_base = page.url.split("?")[0]
            target_url_base = image_viewer_url.split("?")[0]

            if current_url_base == target_url_base:
                logger.info(f"Already on image viewer page: {page.url}")
            else:
                logger.info(f"Navigating to image viewer: {image_viewer_url}")
                # WORKAROUND: page.goto() hangs with launch_persistent_context()
                # Use JavaScript location.href instead
                try:
                    logger.info("Using JavaScript navigation (location.href)...")
                    await page.evaluate(f"window.location.href = '{image_viewer_url}'")
                    logger.info("JavaScript navigation executed, waiting for page to load...")
                    # Wait for page to load (longer since we're not using goto's wait_until)
                    await asyncio.sleep(3.0)
                except Exception as e:
                    logger.error(f"JavaScript navigation to image viewer failed: {e}")
                    # Check if we at least partially navigated
                    try:
                        current_url = page.url
                        logger.info(f"Current URL after failed navigation: {current_url}")
                        if "familysearch.org" not in current_url:
                            raise ValueError(f"Navigation failed and not on FamilySearch: {current_url}")
                    except Exception as recovery_error:
                        logger.error(f"Failed to recover from navigation error: {recovery_error}")
                        raise

            # Additional wait for page to render
            logger.info("Waiting for page to fully render...")
            await asyncio.sleep(1.5)

            # Wait for download button to appear
            # Use manual retry loop instead of wait_for_selector (which hangs with CDP)
            logger.info("Waiting for download button...")
            download_button = None
            selector = 'button[data-testid="download-image-button"]'

            # Manual retry with timeout (15 seconds total, check every 0.5 seconds)
            for attempt in range(30):
                try:
                    download_button = await page.query_selector(selector)
                    if download_button:
                        logger.info(f"Found download button (attempt {attempt + 1})")
                        break
                except Exception as e:
                    logger.debug(f"Query selector error: {e}")

                await asyncio.sleep(0.5)

            if not download_button:
                # Log page content for debugging
                logger.error("Download button not found after 15 seconds")
                try:
                    page_title = await page.title()
                    page_url = page.url
                    logger.error(f"Current page: {page_title} ({page_url})")
                    # Get all buttons on the page for debugging
                    buttons = await page.query_selector_all("button")
                    logger.error(f"Found {len(buttons)} buttons on page")
                except Exception as e:
                    logger.error(f"Failed to get page info: {e}")
                return False

            # Click download button to open dialog
            logger.info("Clicking download button...")
            await download_button.click()

            # Wait for dialog to appear
            await asyncio.sleep(0.8)

            # Use keyboard to select JPG Only and download
            # Sequence: tab → down → down → tab → tab → enter
            logger.info("Using keyboard automation: tab down down tab tab enter")

            await page.keyboard.press("Tab")
            await asyncio.sleep(0.1)

            await page.keyboard.press("ArrowDown")
            await asyncio.sleep(0.1)

            await page.keyboard.press("ArrowDown")
            await asyncio.sleep(0.1)

            await page.keyboard.press("Tab")
            await asyncio.sleep(0.1)

            await page.keyboard.press("Tab")
            await asyncio.sleep(0.1)

            # Start waiting for download before pressing Enter
            async with page.expect_download() as download_info:
                await page.keyboard.press("Enter")

            # Wait for download to complete
            download = await download_info.value
            logger.info(f"Download started: {download.suggested_filename}")

            # Save to specified path
            await download.save_as(str(download_path))
            logger.info(f"Downloaded census image to: {download_path}")

            return True

        except Exception as e:
            logger.error(f"Failed to download census image: {e}", exc_info=True)
            return False

    async def extract_and_download(
        self, record_url: str, download_path: Path
    ) -> dict[str, Any] | None:
        """
        Complete workflow: extract citation data and download image.

        Args:
            record_url: FamilySearch census record URL
            download_path: Path where JPG should be saved

        Returns:
            Citation data dictionary or None if failed
        """
        try:
            # Extract citation data
            citation_data = await self.extract_citation_data(record_url)
            if not citation_data:
                logger.error("Failed to extract citation data")
                return None

            # Download image if image viewer URL is available
            if citation_data.get("imageViewerUrl"):
                success = await self.download_census_image(
                    citation_data["imageViewerUrl"], download_path
                )
                citation_data["image_downloaded"] = success
            else:
                logger.warning("No image viewer URL found")
                citation_data["image_downloaded"] = False

            return citation_data

        except Exception as e:
            logger.error(f"Extract and download workflow failed: {e}", exc_info=True)
            return None


# Singleton instance
_automation_service: FamilySearchAutomation | None = None


def get_automation_service() -> FamilySearchAutomation:
    """Get singleton automation service instance."""
    global _automation_service
    if _automation_service is None:
        _automation_service = FamilySearchAutomation()
    return _automation_service
