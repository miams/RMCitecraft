r"""
Find a Grave Automation Service using Playwright

Connects to user's existing Chrome browser via Chrome DevTools Protocol (CDP) to:
- Extract memorial data from Find a Grave pages
- Download photos with metadata
- Format Evidence Explained citations

BROWSER CONNECTION:
Requires Chrome to be launched with remote debugging:
    /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
        --remote-debugging-port=9222 \
        --user-data-dir="$HOME/Library/Application Support/Google/Chrome-RMCitecraft"

PHOTO EXTRACTION ARCHITECTURE:
Find a Grave uses a complex data structure with:
- HTML elements for photo metadata (type, contributor, date)
- JSON data structures for photo captions
- Navigation elements that must be filtered out

Photo extraction happens in TWO PHASES:
1. _extract_photo_metadata() - Extract from HTML (type, contributor, date, URL)
2. _extract_captions_from_json() - Extract captions from JSON (window.__INITIAL_STATE__ or script tags)

WHY TWO PHASES:
- Metadata is in rendered HTML and easy to extract with DOM queries
- Captions are in JSON data and NOT reliably in HTML
- Rendered HTML contains navigation text ("Now Showing", "View original") that looks like captions
- Using JSON avoids false positives from navigation elements

PHOTO TYPES (Find a Grave Classification):
- "Person": Photo of the individual
- "Grave": Headstone/gravesite photo
- "Family": Photo with family members
- "Other": Documents, records, etc.
- Empty/undefined: Type not specified by contributor

FILE ORGANIZATION BY TYPE:
- Person → ~/Genealogy/RootsMagic/Files/Pictures - People
- Grave → ~/Genealogy/RootsMagic/Files/Pictures - Cemetaries
- Family → ~/Genealogy/RootsMagic/Files/Pictures - People
- Other → ~/Genealogy/RootsMagic/Files/Pictures - Other
"""

import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger
from playwright.async_api import Browser, Page, async_playwright

# Chrome DevTools Protocol endpoint
CHROME_CDP_URL = "http://localhost:9222"


class FindAGraveAutomation:
    """Automates Find a Grave interactions using Playwright connected to user's Chrome."""

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
        Get an existing Find a Grave page or create a new one.

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

        # Look for existing Find a Grave tab
        pages = context.pages
        for page in pages:
            if "findagrave.com" in page.url:
                logger.info(f"Found existing Find a Grave tab: {page.url}")
                return page

        # If no Find a Grave tab found, use any existing page
        if pages:
            logger.info(f"No Find a Grave tab found, using existing page: {pages[0].url}")
            logger.warning(
                "For best results, open Find a Grave in a Chrome tab before running automation"
            )
            return pages[0]

        # No pages available at all
        logger.error("No browser pages available - cannot proceed")
        return None

    async def extract_memorial_data(self, url: str) -> dict[str, Any] | None:
        """
        Navigate to Find a Grave memorial page and extract data.

        Args:
            url: Find a Grave memorial URL

        Returns:
            Dictionary with memorial data or None if extraction failed
        """
        try:
            page = await self.get_or_create_page()
            if not page:
                return None

            # Check if we're already on the target page
            current_url_base = page.url.split("?")[0].split("#")[0]
            target_url_base = url.split("?")[0].split("#")[0]

            if current_url_base == target_url_base:
                logger.info(f"Already on target page: {page.url}")
            else:
                logger.info(f"Navigating to Find a Grave memorial: {url}")
                try:
                    await asyncio.wait_for(
                        page.goto(url, wait_until="domcontentloaded"),
                        timeout=10.0
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Navigation timed out after 10 seconds")
                    if "findagrave.com" not in page.url:
                        raise

            # Wait for memorial content to render
            logger.info("Waiting for page content to render...")
            try:
                await page.wait_for_selector('h1', timeout=15000)
                logger.info("Page content rendered")
            except Exception as e:
                logger.warning(f"Timeout waiting for h1: {e}")

            # Extract memorial data using JavaScript
            logger.info("Extracting memorial data...")
            memorial_data = await page.evaluate("""
                () => {
                    const data = {};

                    // Extract person name from h1
                    const h1 = document.querySelector('h1');
                    data.personName = h1 ? h1.textContent.trim() : '';

                    // Extract memorial ID from URL or page
                    const memorialIdMatch = window.location.href.match(/memorial\\/(\\d+)/);
                    data.memorialId = memorialIdMatch ? memorialIdMatch[1] : '';

                    // Extract dates from h1 or meta data
                    const h1Text = data.personName;
                    const dateMatch = h1Text.match(/\\((\\d{4}).*?(\\d{4})\\)/);
                    if (dateMatch) {
                        data.birthYear = dateMatch[1];
                        data.deathYear = dateMatch[2];
                    }

                    // Extract cemetery information from table
                    const rows = document.querySelectorAll('tr, dl');
                    for (const row of rows) {
                        const label = row.querySelector('dt, th');
                        const value = row.querySelector('dd, td');

                        if (label && value) {
                            const labelText = label.textContent.trim().toLowerCase();
                            const valueText = value.textContent.trim();

                            if (labelText.includes('burial') || labelText.includes('cemetery')) {
                                // Extract cemetery name
                                const cemeteryLink = value.querySelector('a[href*="/cemetery/"]');
                                if (cemeteryLink) {
                                    data.cemeteryName = cemeteryLink.textContent.trim();
                                }

                                // Extract location (city, county, state, country)
                                const cityElem = value.querySelector('#cemeteryCityName, [itemprop="addressLocality"]');
                                const countyElem = value.querySelector('#cemeteryCountyName');
                                const stateElem = value.querySelector('#cemeteryStateName, [itemprop="addressRegion"]');
                                const countryElem = value.querySelector('#cemeteryCountryName');

                                data.cemeteryCity = cityElem ? cityElem.textContent.trim() : '';
                                data.cemeteryCounty = countyElem ? countyElem.textContent.trim() : '';
                                data.cemeteryState = stateElem ? stateElem.textContent.trim() : '';
                                data.cemeteryCountry = countryElem ? countryElem.textContent.trim() : '';
                            }
                        }
                    }

                    // Extract citation text if available
                    const citationDiv = document.querySelector('#citationInfo');
                    data.citationText = citationDiv ? citationDiv.textContent.trim() : '';

                    // Extract creator information (originally created by)
                    const createdByInput = document.querySelector('#originallyCreatedBy');
                    data.createdBy = createdByInput ? createdByInput.value : '';

                    // Extract maintainer information (maintained by)
                    const maintainedInput = document.querySelector('#maintainedBy');
                    data.maintainedBy = maintainedInput ? maintainedInput.value : '';

                    // Extract memorial text (biography, inscription, veteran info, etc.)
                    // Find a Grave stores this in #partBio or #fullBio elements
                    let memorialText = '';

                    // Primary: Extract from #partBio (visible biography/memorial text)
                    const partBio = document.querySelector('#partBio');
                    if (partBio) {
                        memorialText = partBio.textContent.trim();
                    }

                    // Fallback: Try #fullBio (print version, same content)
                    if (!memorialText) {
                        const fullBio = document.querySelector('#fullBio');
                        if (fullBio) {
                            memorialText = fullBio.textContent.trim();
                        }
                    }

                    // Alternative fallback: .bio-min class
                    if (!memorialText) {
                        const bioMin = document.querySelector('.bio-min');
                        if (bioMin) {
                            memorialText = bioMin.textContent.trim();
                        }
                    }

                    data.memorialText = memorialText;

                    // Extract photo information
                    data.photos = [];
                    const photoElements = document.querySelectorAll('[data-photo-id]');
                    for (const photoElem of photoElements) {
                        const photoId = photoElem.getAttribute('data-photo-id');
                        if (photoId) {
                            data.photos.push({
                                photoId: photoId,
                                url: `https://www.findagrave.com/memorial/${data.memorialId}/photo#view-photo=${photoId}`
                            });
                        }
                    }

                    return data;
                }
            """)

            # Deduplicate photos by photoId
            if memorial_data.get('photos'):
                seen_ids = set()
                unique_photos = []
                for photo in memorial_data['photos']:
                    photo_id = photo.get('photoId')
                    if photo_id and photo_id not in seen_ids:
                        seen_ids.add(photo_id)
                        unique_photos.append(photo)
                memorial_data['photos'] = unique_photos

            # Extract detailed photo metadata if photos exist
            if memorial_data.get('photos'):
                logger.info(f"Found {len(memorial_data['photos'])} photo(s), extracting metadata...")
                memorial_data['photos'] = await self._extract_photo_metadata(page, memorial_data)

                # Try to extract captions from page JSON data
                memorial_data['photos'] = await self._extract_captions_from_json(page, memorial_data['photos'])

            # Extract maiden name (if italicized in name)
            memorial_data['maidenName'] = self._extract_maiden_name(memorial_data.get('personName', ''))

            # Extract access date
            memorial_data['accessDate'] = datetime.now().strftime("%B %d, %Y")

            logger.info(f"Extracted memorial data for: {memorial_data.get('personName')}")
            logger.debug(f"Memorial data: {memorial_data}")

            return memorial_data

        except Exception as e:
            logger.error(f"Failed to extract memorial data: {e}", exc_info=True)
            return None

    async def _extract_photo_metadata(self, page: Page, memorial_data: dict) -> list[dict]:
        """
        Extract detailed metadata for each photo from rendered HTML.

        This is phase 1 of photo extraction. It extracts metadata from the rendered
        HTML elements (photo type, contributor, added date, image URL). Photo captions
        are extracted separately in phase 2 (_extract_captions_from_json) because
        Find a Grave stores them in JSON data structures, not rendered HTML.

        Find a Grave Photo Structure:
        - Photos are rendered in viewer-item containers with data-photo-id attribute
        - Metadata (type, contributor, date) is in HTML elements
        - Captions are stored in JSON (window.__INITIAL_STATE__ or script tags)
        - Navigation text ("Now Showing", "View original") must be filtered out

        Photo Types (from Find a Grave):
        - "Person": Photo of the individual
        - "Grave": Headstone/gravesite photo
        - "Family": Photo with family members
        - "Other": Documents, records, etc.
        - Empty/undefined: Type not specified by contributor

        Args:
            page: Playwright page
            memorial_data: Memorial data with basic photo info

        Returns:
            List of photo dictionaries with metadata (excluding captions)
        """
        photos = []

        try:
            # Extract photo metadata from rendered HTML
            # Note: This extracts everything EXCEPT captions (see _extract_captions_from_json)
            photo_metadata = await page.evaluate("""
                () => {
                    const photos = [];

                    // Find all photo viewer items (Find a Grave's photo carousel containers)
                    const photoViewers = document.querySelectorAll('[class*="viewer-item"]');

                    for (const viewer of photoViewers) {
                        const photoId = viewer.getAttribute('data-photo-id');
                        if (!photoId) continue;

                        // ===== Extract Contributor Info =====
                        // Format: "Bill LaBach (46539089)" - full name + user ID
                        // Find a Grave displays this in .added-by element with profile link
                        const addedByElem = viewer.querySelector('.added-by, [class*="added-by"]');
                        let addedBy = '';
                        let addedDate = '';
                        if (addedByElem) {
                            const text = addedByElem.textContent;
                            // Preferred: Extract from profile link to get user ID
                            const userLink = addedByElem.querySelector('a[href*="/user/profile/"]');
                            if (userLink) {
                                const userIdMatch = userLink.href.match(/\\/user\\/profile\\/(\\d+)/);
                                const userId = userIdMatch ? userIdMatch[1] : '';
                                const userName = userLink.textContent.trim();
                                addedBy = userId ? `${userName} (${userId})` : userName;
                            } else {
                                // Fallback: Parse text format "Added by: Name on Date"
                                const userMatch = text.match(/by[:\\s]+(.+?)\\s+on/);
                                addedBy = userMatch ? userMatch[1].trim() : '';
                            }
                            // Extract date added
                            const dateMatch = text.match(/on\\s+(.+?)$/);
                            addedDate = dateMatch ? dateMatch[1].trim() : '';
                        }

                        // ===== Extract Photo Type =====
                        // Values: "Person", "Grave", "Family", "Other", or empty
                        // Displayed as "Photo type: <value>" in a paragraph element
                        let photoType = '';
                        const paragraphs = viewer.querySelectorAll('p');
                        for (const p of paragraphs) {
                            const text = p.textContent;
                            if (text.includes('Photo type:')) {
                                const typeMatch = text.match(/Photo type:[\\s]*(.+?)$/i);
                                photoType = typeMatch ? typeMatch[1].trim() : '';
                                break;
                            }
                        }

                        // ===== Extract Image URL =====
                        // Find a Grave uses data-src for lazy loading, falls back to src
                        const imgElem = viewer.querySelector('img[data-src], img[src]');
                        let imageUrl = '';
                        if (imgElem) {
                            imageUrl = imgElem.getAttribute('data-src') || imgElem.getAttribute('src') || '';
                        }

                        // ===== Extract Photo Caption/Description =====
                        // NOTE: This is a fallback attempt. Captions are actually stored in
                        // JSON data (see _extract_captions_from_json method) and not reliably
                        // in rendered HTML. This code handles edge cases where caption might
                        // appear in HTML elements, but the JSON extraction is the primary method.
                        let photoDescription = '';

                        // Check for caption in data attribute (rare but possible)
                        if (viewer.dataset && viewer.dataset.caption) {
                            photoDescription = viewer.dataset.caption;
                        }

                        // Try to find caption in dedicated elements
                        if (!photoDescription) {
                            const captionElement = viewer.querySelector(
                                '.photo-caption, .caption, .description, ' +
                                '[data-caption], [class*="caption"], ' +
                                'p.caption, div.caption'
                            );

                            if (captionElement) {
                                const text = captionElement.textContent.trim();
                                // Filter out navigation/metadata text that isn't actual captions
                                // These are UI elements that might be mistaken for descriptions:
                                // - "Added by: ..." - contributor info
                                // - "Photo type: ..." - photo categorization
                                // - "Now Showing X of Y" - carousel navigation
                                // - "View original" - link to full-size image
                                // - "Photo Updated" / "actualizada" - status messages
                                if (text &&
                                    !text.includes('Added by') &&
                                    !text.includes('Photo type:') &&
                                    !text.includes('Now Showing') &&
                                    !text.includes('View original') &&
                                    !text.includes('Photo Updated') &&
                                    !text.includes('actualizada')) {
                                    photoDescription = text;
                                }
                            }
                        }

                        photos.push({
                            photoId: photoId,
                            addedBy: addedBy,
                            addedDate: addedDate,
                            photoType: photoType,
                            imageUrl: imageUrl,
                            description: photoDescription
                        });
                    }

                    return photos;
                }
            """)

            # Merge with basic photo info
            for photo in memorial_data.get('photos', []):
                photo_id = photo['photoId']
                # Find matching metadata
                metadata = next((p for p in photo_metadata if p['photoId'] == photo_id), {})
                photo.update(metadata)
                photos.append(photo)

        except Exception as e:
            logger.warning(f"Could not extract detailed photo metadata: {e}")
            # Return basic photo info if detailed extraction fails
            photos = memorial_data.get('photos', [])

        return photos

    async def _extract_captions_from_json(self, page: Page, photos: list[dict]) -> list[dict]:
        """
        Extract photo captions from Find a Grave's JSON data structures (Phase 2).

        WHY THIS METHOD EXISTS:
        Find a Grave stores photo captions in JavaScript/JSON data, NOT in rendered
        HTML elements. The rendered HTML contains navigation text ("Now Showing 2 of 3",
        "View original", "Photo Updated") which are easily confused with actual captions.

        FIND A GRAVE DATA STRUCTURE:
        Find a Grave embeds photo data in one of these locations:
        1. window.__INITIAL_STATE__.memorial.photos - Global state object
        2. <script type="application/json"> - JSON-LD or data islands
        3. <script type="application/ld+json"> - Structured data

        CAPTION FIELD VALUES:
        - caption: "Elizabeth (Lizzie) Davis Ijames" - User-provided photo description
        - caption: null - Photo has no caption (intentionally blank)
        - caption: <missing> - Field doesn't exist (treat as blank)

        EXTRACTION STRATEGY:
        1. Search window.__INITIAL_STATE__ for memorial.photos array
        2. Parse JSON from script tags looking for photos array
        3. Build dictionary mapping photo.id → photo.caption
        4. Overlay captions onto photos list from Phase 1 (_extract_photo_metadata)

        Args:
            page: Playwright page (already navigated to memorial)
            photos: List of photo dictionaries from _extract_photo_metadata

        Returns:
            Updated list of photo dictionaries with 'description' field populated
        """
        try:
            # Execute JavaScript in browser context to extract caption data
            captions_data = await page.evaluate("""
                () => {
                    // Build map of photoId → caption text
                    const captions = {};

                    // ===== Strategy 1: Check window.__INITIAL_STATE__ =====
                    // This is Find a Grave's global state object for React/Next.js
                    if (window.__INITIAL_STATE__?.memorial?.photos) {
                        window.__INITIAL_STATE__.memorial.photos.forEach(photo => {
                            // photo.id is the unique photo identifier
                            // photo.caption is the user-provided description (or null)
                            if (photo.id && photo.caption) {
                                captions[photo.id] = photo.caption;
                            }
                        });
                    }

                    // ===== Strategy 2: Parse JSON from script tags =====
                    // Find a Grave may embed photo data in JSON-LD or data islands
                    const scripts = document.querySelectorAll('script[type="application/json"], script[type="application/ld+json"]');
                    for (const script of scripts) {
                        try {
                            const data = JSON.parse(script.textContent);
                            // Look for photos array at any depth in the JSON structure
                            if (data.photos && Array.isArray(data.photos)) {
                                data.photos.forEach(photo => {
                                    if (photo.id && photo.caption) {
                                        captions[photo.id] = photo.caption;
                                    }
                                });
                            }
                            // Also check nested memorial.photos path
                            if (data.memorial?.photos && Array.isArray(data.memorial.photos)) {
                                data.memorial.photos.forEach(photo => {
                                    if (photo.id && photo.caption) {
                                        captions[photo.id] = photo.caption;
                                    }
                                });
                            }
                        } catch (e) {
                            // Not valid JSON or doesn't have photos - skip this script tag
                        }
                    }

                    return captions;
                }
            """)

            # Overlay captions from JSON data onto photos from Phase 1
            for photo in photos:
                photo_id = photo.get('photoId')
                if photo_id and photo_id in captions_data:
                    # Replace any HTML-extracted description with authoritative JSON caption
                    photo['description'] = captions_data[photo_id]
                    logger.debug(f"Found caption for photo {photo_id}: {captions_data[photo_id]}")

            return photos

        except Exception as e:
            logger.warning(f"Could not extract captions from JSON data: {e}")
            # Return photos unchanged - Phase 1 metadata is still valid
            return photos

    def _extract_maiden_name(self, person_name: str) -> str:
        """
        Extract maiden name from person name (italicized portion).

        In Find a Grave HTML, maiden names appear in <i> tags.

        Args:
            person_name: Full person name

        Returns:
            Maiden name or empty string
        """
        # This will be handled by HTML parsing, returning empty for now
        # The actual maiden name detection happens in browser via italics
        return ''

    async def download_photo(self, photo_url: str, memorial_id: str, download_path: Path) -> bool:
        """
        Download a photo from Find a Grave using browser context.

        Args:
            photo_url: Full-resolution photo URL
            memorial_id: Memorial ID
            download_path: Path to save the image

        Returns:
            True if download succeeded, False otherwise
        """
        try:
            page = await self.get_or_create_page()
            if not page:
                return False

            logger.info(f"Downloading photo to: {download_path}")
            logger.info(f"Photo URL: {photo_url}")

            # Use browser context to fetch image (maintains authentication/cookies)
            context = page.context

            # Fetch the image using the browser's network context
            response = await context.request.get(photo_url)

            if response.status != 200:
                logger.error(f"Failed to fetch image: HTTP {response.status}")
                return False

            # Get image data
            image_data = await response.body()

            # Write to file
            download_path.parent.mkdir(parents=True, exist_ok=True)
            with open(download_path, 'wb') as f:
                f.write(image_data)

            logger.info(f"Successfully downloaded photo: {download_path} ({len(image_data)} bytes)")
            return True

        except Exception as e:
            logger.error(f"Failed to download photo: {e}", exc_info=True)
            return False


# Singleton instance
_automation_service: FindAGraveAutomation | None = None


def get_findagrave_automation() -> FindAGraveAutomation:
    """Get singleton Find a Grave automation service instance."""
    global _automation_service
    if _automation_service is None:
        _automation_service = FindAGraveAutomation()
    return _automation_service
