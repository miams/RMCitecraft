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

            # Click "Read More" button if it exists and is visible to expand full biography text
            logger.info("Checking for 'Read More' button...")
            try:
                read_more_button = await page.query_selector('a.read-more, button.read-more, a:has-text("Read More"), button:has-text("Read More")')
                if read_more_button and await read_more_button.is_visible():
                    logger.info("Found visible 'Read More' button, clicking to expand full text...")
                    # Use shorter timeout (5 seconds) for click
                    await read_more_button.click(timeout=5000)
                    # Wait a moment for content to expand
                    await page.wait_for_timeout(500)
                    logger.info("Full biography text expanded")
                else:
                    logger.info("No visible 'Read More' button (full text already visible)")
            except Exception as e:
                logger.warning(f"Error handling 'Read More' button: {e}")

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
                    console.log(`Found ${rows.length} rows/dl elements to check for burial info`);

                    for (const row of rows) {
                        const label = row.querySelector('dt, th');
                        const value = row.querySelector('dd, td');

                        if (label && value) {
                            const labelText = label.textContent.trim().toLowerCase();
                            const valueText = value.textContent.trim();

                            if (labelText.includes('burial') || labelText.includes('cemetery')) {
                                console.log(`Found burial/cemetery row with label: ${labelText}`);

                                // Extract cemetery name from link within the value cell
                                const cemeteryLink = value.querySelector('a[href*="/cemetery/"]');
                                if (cemeteryLink) {
                                    data.cemeteryName = cemeteryLink.textContent.trim();
                                    console.log(`Cemetery name: ${data.cemeteryName}`);
                                } else {
                                    console.log('No cemetery link found in value cell');
                                }

                                // Extract location (city, county, state, country)
                                // IDs are document-wide, so use document.querySelector
                                const cityElem = document.querySelector('#cemeteryCityName, [itemprop="addressLocality"]');
                                const countyElem = document.querySelector('#cemeteryCountyName');
                                const stateElem = document.querySelector('#cemeteryStateName, [itemprop="addressRegion"]');
                                const countryElem = document.querySelector('#cemeteryCountryName');

                                data.cemeteryCity = cityElem ? cityElem.textContent.trim() : '';
                                data.cemeteryCounty = countyElem ? countyElem.textContent.trim() : '';
                                data.cemeteryState = stateElem ? stateElem.textContent.trim() : '';
                                data.cemeteryCountry = countryElem ? countryElem.textContent.trim() : '';

                                console.log(`Cemetery location: ${data.cemeteryCity}, ${data.cemeteryCounty}, ${data.cemeteryState}, ${data.cemeteryCountry}`);
                            }
                        }
                    }

                    console.log(`Cemetery extraction complete. Name: ${data.cemeteryName || 'NOT FOUND'}`);


                    // Extract citation text if available
                    const citationDiv = document.querySelector('#citationInfo');
                    data.citationText = citationDiv ? citationDiv.textContent.trim() : '';

                    // Extract creator information
                    // Try simple "Created by:" first, then fall back to "Originally Created by:"
                    const createdBySimple = document.querySelector('#createdBy');
                    const createdByOriginal = document.querySelector('#originallyCreatedBy');

                    if (createdBySimple && createdBySimple.value) {
                        data.createdBy = createdBySimple.value;
                    } else if (createdByOriginal && createdByOriginal.value) {
                        data.createdBy = createdByOriginal.value;
                    } else {
                        data.createdBy = '';
                    }

                    // Extract maintainer information (maintained by)
                    const maintainedInput = document.querySelector('#maintainedBy');
                    data.maintainedBy = maintainedInput ? maintainedInput.value : '';

                    // Extract memorial text (biography, inscription, veteran info, etc.)
                    // Find a Grave stores this in #partBio or #fullBio elements

                    // Helper function to extract text while preserving paragraph breaks
                    const extractTextWithLineBreaks = (element) => {
                        if (!element) return '';

                        // Get innerHTML and convert block elements to text with newlines
                        let html = element.innerHTML;

                        // Replace closing tags of block elements with blank line separator
                        // Using newline + space + newline to ensure RootsMagic shows blank line
                        html = html.replace(/<\\/(p|div|h1|h2|h3|h4|h5|h6)>/gi, '\\n \\n');

                        // Replace <br> tags with single newline
                        html = html.replace(/<br\\s*\/?>/gi, '\\n');

                        // Replace list items with newline
                        html = html.replace(/<\/li>/gi, '\\n');

                        // Remove all remaining HTML tags
                        html = html.replace(/<[^>]+>/g, '');

                        // Decode HTML entities
                        const textarea = document.createElement('textarea');
                        textarea.innerHTML = html;
                        let text = textarea.value;

                        // Normalize whitespace: collapse multiple spaces/tabs to single space
                        text = text.replace(/[ \\t]+/g, ' ');

                        // Remove leading/trailing spaces from each line, BUT preserve lines with just a space (blank line markers)
                        const lines = text.split('\\n');
                        text = lines.map(line => {
                            // Keep single-space lines as-is (our blank line markers)
                            if (line === ' ') return line;
                            // Trim all other lines
                            return line.trim();
                        }).join('\\n');

                        // Remove excessive consecutive newlines (3+ becomes 2)
                        text = text.replace(/\\n{3,}/g, '\\n\\n');

                        return text.trim();
                    };

                    let memorialText = '';

                    // Primary: Try #fullBio first (contains complete text without truncation)
                    const fullBio = document.querySelector('#fullBio');
                    if (fullBio) {
                        memorialText = extractTextWithLineBreaks(fullBio);
                    }

                    // Fallback 1: Extract from #partBio (visible biography, may be truncated)
                    if (!memorialText) {
                        const partBio = document.querySelector('#partBio');
                        if (partBio) {
                            memorialText = extractTextWithLineBreaks(partBio);
                        }
                    }

                    // Fallback 2: .bio-min class
                    if (!memorialText) {
                        const bioMin = document.querySelector('.bio-min');
                        if (bioMin) {
                            memorialText = extractTextWithLineBreaks(bioMin);
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

            # Extract source comment data (biographical summary, photos, family)
            memorial_data['sourceComment'] = await self._extract_source_comment(page, memorial_data)

            logger.info(f"Extracted memorial data for: {memorial_data.get('personName')}")
            logger.info(
                f"Cemetery extraction result:\n"
                f"  Name: {memorial_data.get('cemeteryName', 'NOT FOUND')}\n"
                f"  City: {memorial_data.get('cemeteryCity', 'NOT FOUND')}\n"
                f"  County: {memorial_data.get('cemeteryCounty', 'NOT FOUND')}\n"
                f"  State: {memorial_data.get('cemeteryState', 'NOT FOUND')}\n"
                f"  Country: {memorial_data.get('cemeteryCountry', 'NOT FOUND')}"
            )
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

    async def _extract_source_comment(self, page: Page, memorial_data: dict) -> str:
        """
        Extract data for Source Comment field.

        Formats three sections:
        1. Biographical Summary (Birth, Death, Burial)
        2. Photo Summary (list of photos with types)
        3. Family Members (Parents, Spouse, Siblings, Children)

        Args:
            page: Playwright page
            memorial_data: Memorial data with basic info

        Returns:
            Formatted source comment text
        """
        try:
            # Extract biographical and family data from page
            comment_data = await page.evaluate("""
                () => {
                    const data = {
                        birth: { date: '', location: '' },
                        death: { date: '', location: '' },
                        burial: { cemetery: '', location: '' },
                        family: {
                            parents: [],
                            spouse: [],
                            siblings: [],
                            children: []
                        }
                    };

                    // === Extract Birth/Death/Burial Info ===
                    // Find all dl/dt/dd elements which contain vital info
                    const vitals = document.querySelectorAll('dl');
                    for (const dl of vitals) {
                        const items = dl.querySelectorAll('dt, dd');
                        let currentLabel = '';

                        for (const item of items) {
                            const text = item.textContent.trim();

                            if (item.tagName === 'DT') {
                                currentLabel = text.toLowerCase();
                            } else if (item.tagName === 'DD') {
                                if (currentLabel.includes('birth')) {
                                    // Extract birth date and location
                                    const parts = text.split('\\n').map(p => p.trim()).filter(p => p);
                                    if (parts.length >= 1) data.birth.date = parts[0];
                                    if (parts.length >= 2) data.birth.location = parts.slice(1).join(', ');
                                } else if (currentLabel.includes('death')) {
                                    // Extract death date and location
                                    const parts = text.split('\\n').map(p => p.trim()).filter(p => p);
                                    if (parts.length >= 1) {
                                        // Remove "(aged XX)" from date
                                        data.death.date = parts[0].replace(/\\s*\\(aged \\d+\\)\\s*/i, '').trim();
                                    }
                                    if (parts.length >= 2) data.death.location = parts.slice(1).join(', ');
                                } else if (currentLabel.includes('burial')) {
                                    // Extract burial cemetery and location
                                    const cemeteryLink = item.querySelector('a[href*="/cemetery/"]');
                                    if (cemeteryLink) {
                                        data.burial.cemetery = cemeteryLink.textContent.trim();
                                    }

                                    // Get location from specific spans, avoiding duplicates and GPS data
                                    const locationParts = [];
                                    const citySpan = item.querySelector('#cemeteryCityName, [itemprop="addressLocality"]');
                                    const countySpan = item.querySelector('#cemeteryCountyName');
                                    const stateSpan = item.querySelector('#cemeteryStateName, [itemprop="addressRegion"]');
                                    const countrySpan = item.querySelector('#cemeteryCountryName');

                                    if (citySpan && citySpan.textContent.trim()) locationParts.push(citySpan.textContent.trim());
                                    if (countySpan && countySpan.textContent.trim()) locationParts.push(countySpan.textContent.trim());
                                    if (stateSpan && stateSpan.textContent.trim()) locationParts.push(stateSpan.textContent.trim());
                                    if (countrySpan && countrySpan.textContent.trim()) locationParts.push(countrySpan.textContent.trim());

                                    data.burial.location = locationParts.join(', ');
                                }
                            }
                        }
                    }

                    // === Extract Family Members ===
                    // Find all family member lists
                    const familyLists = document.querySelectorAll('.member-family');

                    for (const list of familyLists) {
                        // Determine relationship type from previous heading
                        let relationshipType = '';
                        let sibling = list.previousElementSibling;
                        while (sibling) {
                            const text = sibling.textContent.trim().toLowerCase();
                            if (text.includes('parent')) {
                                relationshipType = 'parents';
                                break;
                            } else if (text.includes('spouse')) {
                                relationshipType = 'spouse';
                                break;
                            } else if (text.includes('sibling')) {
                                relationshipType = 'siblings';
                                break;
                            } else if (text.includes('child')) {
                                relationshipType = 'children';
                                break;
                            }
                            sibling = sibling.previousElementSibling;
                        }

                        if (!relationshipType) continue;

                        // Extract members from this list
                        const items = list.querySelectorAll('li');
                        for (const item of items) {
                            // Only process top-level li items (not nested ones)
                            if (item.parentElement !== list) continue;

                            // Get the name link
                            const nameLink = item.querySelector('a[href*="/memorial/"]');
                            if (!nameLink) continue;

                            const name = nameLink.textContent.trim().replace(/\\s+/g, ' ');

                            // Extract dates from the FIRST text occurrence only
                            // Strategy: Get only the immediate text nodes near the link
                            let datesText = '';

                            // Look for text nodes and small elements directly after the link
                            let currentNode = nameLink.nextSibling;
                            let textParts = [];
                            let foundDate = false;

                            while (currentNode && !foundDate) {
                                if (currentNode.nodeType === Node.TEXT_NODE) {
                                    const text = currentNode.textContent.trim();
                                    if (text) textParts.push(text);
                                } else if (currentNode.nodeType === Node.ELEMENT_NODE) {
                                    // Only examine small inline elements, skip UL/OL
                                    if (currentNode.tagName !== 'UL' && currentNode.tagName !== 'OL') {
                                        const text = currentNode.textContent.trim();
                                        if (text) {
                                            textParts.push(text);
                                            // If we found a date pattern, we're done
                                            if (/\\d{4}/.test(text)) {
                                                foundDate = true;
                                            }
                                        }
                                    } else {
                                        // Hit a nested list, stop
                                        break;
                                    }
                                }
                                currentNode = currentNode.nextSibling;
                            }

                            datesText = textParts.join(' ');

                            // Extract date range (birth-death)
                            let dates = '';
                            const dateMatch = datesText.match(/(\\d{4})\\s*[–-]\\s*(\\d{4}|)/);
                            if (dateMatch) {
                                const startYear = dateMatch[1];
                                const endYear = dateMatch[2] ? dateMatch[2].trim() : '';
                                dates = endYear ? `${startYear}–${endYear}` : startYear;
                            }

                            // Extract marriage date if present (for spouses)
                            const marriageMatch = datesText.match(/\\(m\\.\\s*(\\d{4})\\)/);
                            if (marriageMatch && !dates.includes('(m.')) {
                                dates += ` (m. ${marriageMatch[1]})`;
                            }

                            if (name) {
                                data.family[relationshipType].push({
                                    name: name,
                                    dates: dates
                                });
                            }
                        }
                    }

                    return data;
                }
            """)

            # Format the source comment with three sections
            sections = []

            # === Section 1: Biographical Details ===
            bio_lines = ["<b>Biographical Details</b>"]
            has_bio_data = False

            if comment_data.get('birth', {}).get('date'):
                birth = comment_data['birth']
                bio_lines.append("Birth  " + birth['date'])
                if birth.get('location'):
                    bio_lines.append("       " + birth['location'])
                has_bio_data = True

            if comment_data.get('death', {}).get('date'):
                death = comment_data['death']
                if has_bio_data:
                    bio_lines.append("")
                bio_lines.append("Death  " + death['date'])
                if death.get('location'):
                    bio_lines.append("       " + death['location'])
                has_bio_data = True

            if comment_data.get('burial', {}).get('cemetery'):
                burial = comment_data['burial']
                if has_bio_data:
                    bio_lines.append("")
                bio_lines.append("Burial")
                bio_lines.append("       " + burial['cemetery'])
                if burial.get('location'):
                    bio_lines.append("       " + burial['location'])
                has_bio_data = True

            if not has_bio_data:
                bio_lines.append("none")

            sections.append("\n".join(bio_lines))

            # === Section 2: Photo Summary ===
            photo_lines = ["<b>Photo Summary</b>"]
            photos = memorial_data.get('photos', [])
            if photos:
                for i, photo in enumerate(photos, 1):
                    photo_type = photo.get('photoType', 'Photo')
                    if not photo_type:
                        photo_type = 'Photo'
                    photo_lines.append(f"{i}. {photo_type} Photo")
            else:
                photo_lines.append("none")

            sections.append("\n".join(photo_lines))

            # === Section 3: Identified Family ===
            family_lines = ["<b>Identified Family</b>"]
            family = comment_data.get('family', {})
            has_family_data = False

            if family.get('parents'):
                family_lines.append("Parents")
                for member in family['parents']:
                    name_dates = f"  {member['name']}"
                    if member.get('dates'):
                        name_dates += f" {member['dates']}"
                    family_lines.append(name_dates)
                family_lines.append("")
                has_family_data = True

            if family.get('spouse'):
                family_lines.append("Spouse")
                for member in family['spouse']:
                    name_dates = f"  {member['name']}"
                    if member.get('dates'):
                        name_dates += f" {member['dates']}"
                    family_lines.append(name_dates)
                family_lines.append("")
                has_family_data = True

            if family.get('siblings'):
                family_lines.append("Siblings")
                for member in family['siblings']:
                    name_dates = f"  {member['name']}"
                    if member.get('dates'):
                        name_dates += f" {member['dates']}"
                    family_lines.append(name_dates)
                family_lines.append("")
                has_family_data = True

            if family.get('children'):
                family_lines.append("Children")
                for member in family['children']:
                    name_dates = f"  {member['name']}"
                    if member.get('dates'):
                        name_dates += f" {member['dates']}"
                    family_lines.append(name_dates)
                has_family_data = True

            # Remove trailing empty line if present
            while family_lines and family_lines[-1] == "":
                family_lines.pop()

            if not has_family_data:
                family_lines.append("none")

            sections.append("\n".join(family_lines))

            # Combine all sections with double newlines
            return "\n\n".join(sections)

        except Exception as e:
            logger.warning(f"Could not extract source comment data: {e}")
            return ""

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
