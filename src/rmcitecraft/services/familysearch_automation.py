r"""
FamilySearch Automation Service using Playwright

Connects to user's existing Chrome browser to:
- Extract census citation data from FamilySearch pages
- Automate census image downloads
- Handle FamilySearch dialogs and navigation

Requires Chrome to be launched with remote debugging:
    /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
        --remote-debugging-port=9222 \
        --user-data-dir="$HOME/Library/Application Support/Google/Chrome-RMCitecraft"

Note: Must use separate profile directory (not default Chrome profile) for debugging.
"""

import asyncio
import re
from pathlib import Path
from typing import Any

from loguru import logger
from playwright.async_api import Browser, Page, async_playwright

# Chrome DevTools Protocol endpoint
CHROME_CDP_URL = "http://localhost:9222"


class FamilySearchAutomation:
    """Automates FamilySearch interactions using Playwright connected to user's Chrome."""

    def __init__(self):
        """Initialize automation service."""
        self.browser: Browser | None = None
        self.playwright = None

    async def connect_to_chrome(self) -> bool:
        """
        Connect to existing Chrome browser via CDP.

        Returns:
            True if connected successfully, False otherwise
        """
        try:
            logger.info("Connecting to Chrome browser via CDP...")
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.connect_over_cdp(CHROME_CDP_URL)
            logger.info(f"Connected to Chrome - {len(self.browser.contexts)} context(s)")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Chrome: {e}")
            logger.warning(
                "Make sure Chrome is running with: "
                "--remote-debugging-port=9222 --user-data-dir=..."
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

    async def get_or_create_page(self) -> Page | None:
        """
        Get an existing FamilySearch page or create a new one.

        Returns:
            Page instance or None if connection failed
        """
        if not self.browser:
            if not await self.connect_to_chrome():
                return None

        # Get default context (user's Chrome session)
        contexts = self.browser.contexts
        if not contexts:
            logger.error("No browser contexts available")
            return None

        context = contexts[0]

        # Look for existing FamilySearch tab
        pages = context.pages
        for page in pages:
            if "familysearch.org" in page.url:
                logger.info(f"Found existing FamilySearch tab: {page.url}")
                return page

        # If no FamilySearch tab found, use any existing page
        # Note: context.new_page() can hang when connected via CDP (known Playwright limitation)
        # For production use, user should have FamilySearch already open
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
                except asyncio.TimeoutError:
                    logger.warning(f"Navigation timed out after 10 seconds")
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
            # Use year-specific extraction logic based on census era
            table_data = await page.evaluate(self._get_extraction_javascript(census_year))

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

            citation_data["line"] = table_data.get("line", "")
            citation_data["familyNumber"] = table_data.get("family", "")
            citation_data["dwellingNumber"] = table_data.get("dwelling", "")

            # DEBUG: Log what was set in citation_data before transform
            logger.debug(f"citation_data before transform: sheet='{citation_data.get('sheet', 'KEY_MISSING')}', line='{citation_data.get('line', 'KEY_MISSING')}', page='{citation_data.get('page', 'KEY_MISSING')}'")

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
            image_link = await page.query_selector('a[href*="/ark:/61903/3:1:"]')
            if image_link:
                href = await image_link.get_attribute("href")
                # Convert relative URL to absolute
                if href and href.startswith("/"):
                    href = f"https://www.familysearch.org{href}"
                citation_data["imageViewerUrl"] = href or ""
            else:
                citation_data["imageViewerUrl"] = ""

            # Extract page title
            citation_data["pageTitle"] = await page.title()

            logger.info(f"Extracted citation data: {citation_data['personName']}")

            # Transform to expected format (snake_case keys, parsed location)
            return self._transform_citation_data(citation_data)


        except Exception as e:
            logger.error(f"Failed to extract citation data: {e}", exc_info=True)
            return None

    def _get_extraction_javascript(self, census_year: int | None) -> str:
        """
        Generate year-specific JavaScript for extracting census data from FamilySearch pages.

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

                            // Event place (always extract)
                            // Prioritize "Event Place (Original)" for 1920 census (contains ED)
                            if (label === 'event place (original)') {{
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
                            // Sheet number (1880-1940)
                            else if ({str(extract_sheet).lower()} && (label === 'sheet number' || (label.includes('sheet') && !label.includes('letter')))) {{
                                result.sheetNumber = value;
                            }}
                            // Sheet letter (1880-1940)
                            else if ({str(extract_sheet).lower()} && label === 'sheet letter') {{
                                result.sheetLetter = value;
                            }}
                            // Page number (1790-1870, 1950)
                            else if ({str(extract_page).lower()} && (label === 'page number' || label === 'page' || label === 'page no.')) {{
                                result.pageNumber = value;
                            }}
                            // Line number (1850-1950, excluding 1790-1840)
                            else if ({str(extract_line).lower()} && label.includes('line')) {{
                                result.line = value;
                            }}
                            // Family number (optional, all years)
                            else if (label.includes('family')) {{
                                result.family = value;
                            }}
                            // Dwelling number (optional, all years)
                            else if (label.includes('dwelling')) {{
                                result.dwelling = value;
                            }}
                        }}
                    }}
                }}
                return result;
            }}
        """

    def _transform_citation_data(self, raw_data: dict) -> dict:
        """
        Transform FamilySearch extraction format to expected citation format.

        Converts:
        - camelCase keys → snake_case keys
        - eventPlace string → separate state/county
        - Extracts enumeration_district from familySearchEntry

        Args:
            raw_data: Raw extraction from FamilySearch page

        Returns:
            Transformed dict with keys: person_name, state, county,
            familysearch_url, enumeration_district, etc.
        """
        # DEBUG: Log what raw_data contains for census fields
        logger.debug(f"_transform_citation_data received: sheet='{raw_data.get('sheet', 'KEY_MISSING')}', line='{raw_data.get('line', 'KEY_MISSING')}', page='{raw_data.get('page', 'KEY_MISSING')}'")

        transformed = {}

        # Map camelCase to snake_case
        transformed['person_name'] = raw_data.get('personName', '')
        transformed['familysearch_url'] = raw_data.get('arkUrl', '')

        # Parse eventPlace: "St. Louis, Missouri, United States" → state + county
        # For 1920 census: "Township, ED XX, County, State, United States"
        event_place = raw_data.get('eventPlace', '')
        state, county = self._parse_event_place(event_place)
        transformed['state'] = state
        transformed['county'] = county

        # Use table-extracted census details first (more reliable)
        # For 1920 census, ED is often embedded in eventPlace instead of separate table row
        transformed['enumeration_district'] = raw_data.get('enumerationDistrict', '')

        # 1920 Census Special Case: Extract ED and township from Event Place (Original)
        # Format: "Township, ED XX, County, State, United States"
        # Example: "Jerusalem, ED 48, Davie, North Carolina, United States"
        if not transformed['enumeration_district'] and event_place:
            ed_match = re.search(r'\bED\s+(\d+)', event_place, re.IGNORECASE)
            if ed_match:
                transformed['enumeration_district'] = ed_match.group(1)
                logger.debug(f"Extracted ED {ed_match.group(1)} from Event Place (Original): {event_place}")

                # Also extract township/ward (first part before ED)
                # Split and find the part before "ED XX"
                parts = [p.strip() for p in event_place.split(',')]
                if parts and not re.match(r'^ED\s+\d+', parts[0], re.IGNORECASE):
                    # First part is the township/ward
                    transformed['town_ward'] = parts[0]
                    logger.debug(f"Extracted township/ward '{parts[0]}' from Event Place (Original)")

        transformed['sheet'] = raw_data.get('sheet', '')
        transformed['page'] = raw_data.get('page', '')  # For 1790-1870, 1950
        transformed['line'] = raw_data.get('line', '')
        transformed['family_number'] = raw_data.get('familyNumber', '')
        transformed['dwelling_number'] = raw_data.get('dwellingNumber', '')

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
                # Note: CDP connections can be slow/unreliable with navigation
                # Use domcontentloaded (DOM ready) instead of load (all resources) for speed
                try:
                    await page.goto(image_viewer_url, wait_until="domcontentloaded", timeout=15000)
                except Exception as e:
                    logger.warning(f"Navigation to image viewer timed out or failed: {e}")
                    # Check if we're at least on FamilySearch
                    if "familysearch.org" not in page.url:
                        raise

            # Give page a moment to render (don't wait for all resources)
            await asyncio.sleep(0.5)

            # Wait for download button to appear (up to 15 seconds)
            logger.info("Waiting for download button...")
            try:
                download_button = await page.wait_for_selector(
                    'button[data-testid="download-image-button"]', timeout=15000
                )
            except Exception:
                logger.error("Download button not found after 15 seconds")
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
