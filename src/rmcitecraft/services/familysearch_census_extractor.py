"""
FamilySearch Census Data Extractor.

Extracts detailed census transcription data from FamilySearch using Playwright.
Stores extracted data in census.db and links to RootsMagic citations.

Usage:
    extractor = FamilySearchCensusExtractor()
    await extractor.connect()

    # Extract from ARK URL (from citation footnote)
    result = await extractor.extract_from_ark(
        "https://www.familysearch.org/ark:/61903/1:1:6XKG-DP65",
        census_year=1950,
        rmtree_citation_id=10370,
        rmtree_person_id=2776
    )

    await extractor.disconnect()
"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from loguru import logger
from playwright.async_api import Page


def normalize_ark_url(url: str) -> str:
    """Normalize a FamilySearch ARK URL by removing query parameters.

    This ensures URLs like:
    - https://www.familysearch.org/ark:/61903/1:1:6XGL-ZFGQ
    - https://www.familysearch.org/ark:/61903/1:1:6XGL-ZFGQ?lang=en

    Are treated as the same resource.
    """
    if not url:
        return url
    parsed = urlparse(url)
    # Reconstruct URL without query string
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

from rmcitecraft.database.census_extraction_db import (
    CensusExtractionRepository,
    CensusPage,
    CensusPerson,
    RMTreeLink,
    get_census_repository,
)
from rmcitecraft.services.familysearch_automation import (
    FamilySearchAutomation,
    get_automation_service,
)


@dataclass
class ExtractionResult:
    """Result of a FamilySearch census extraction."""

    success: bool = False
    person_id: int | None = None  # Database ID in census.db
    page_id: int | None = None
    error_message: str = ""
    extracted_data: dict[str, Any] = field(default_factory=dict)
    related_persons: list[dict[str, Any]] = field(default_factory=list)


# FamilySearch field name mappings to our schema
# Based on actual FamilySearch HTML structure (November 2024)
FAMILYSEARCH_FIELD_MAP = {
    # Core person fields - exact labels from FamilySearch
    "name": "full_name",  # FamilySearch shows "Name" not separate given/surname
    "given name": "given_name",
    "surname": "surname",
    "name suffix": "name_suffix",
    "race": "race",
    "sex": "sex",
    "age": "age",
    "relationship to head of household": "relationship_to_head",  # Exact FS label
    "relationship to head": "relationship_to_head",
    "marital status": "marital_status",

    # Birthplace
    "birthplace": "birthplace",
    "birth place": "birthplace",
    "father's birth place": "birthplace_father",
    "father's birthplace": "birthplace_father",
    "mother's birth place": "birthplace_mother",
    "mother's birthplace": "birthplace_mother",

    # Birth year
    "birth year (estimated)": "birth_year",  # Exact FS label
    "birth year": "birth_year",

    # Employment
    "occupation": "occupation",
    "industry": "industry",  # FS uses just "Industry"
    "occupation industry": "industry",
    "worker class": "worker_class",

    # Event information
    "event date": "event_date",
    "event place": "event_place",
    "event place (original)": "event_place_original",

    # Location (page-level) - exact FamilySearch labels
    "state": "state",
    "county": "county",
    "city": "township_city",
    "enumeration district": "enumeration_district",  # Exact FS label
    "supervisor district field": "supervisor_district",
    "page number": "page_number",  # Exact FS label
    "source page number": "page_number",
    "line number": "line_number",  # Exact FS label
    "source line number": "line_number",
    "sheet number": "sheet_number",
    "stamp number": "stamp_number",
    "house number": "house_number",
    "apartment number": "apartment_number",

    # Digital folder info
    "digital folder number": "digital_folder_number",
    "image number": "image_number",

    # Census-specific extended fields (stored in EAV table)
    "household_id": "household_id",
    "enumerator name": "enumerator_name",
    "attended school": "attended_school",
    "worked last week": "worked_last_week",
    "seeking work": "seeking_work",
    "employed": "employed",
    "hours worked": "hours_worked",
    "weeks worked": "weeks_worked",
    "weeks out of work": "weeks_out_of_work",
    "income": "income",
    "income from other sources": "income_other",
    "same house": "same_house_1949",
    "same county": "same_county_1949",
    "lived on farm": "lived_on_farm",
    "lived on farm last year": "lived_on_farm_1949",
    "3 plus acres": "farm_3_plus_acres",
    "grade completed": "grade_completed",
    "completed grade": "completed_grade",
    "veteran": "veteran",
    "world war i vet": "veteran_ww1",
    "world war ii vet": "veteran_ww2",
    "children born count": "children_born",
    "citizen status flag": "citizenship_status",
    "married more than once": "married_more_than_once",
    "years since marital status change": "years_marital_change",
}

# Fields that go to census_person_field (EAV) instead of core fields
EXTENDED_FIELDS = {
    # Location/event details
    "event_date",
    "event_place",
    "event_place_original",
    "digital_folder_number",
    "image_number",
    "birth_year",
    "household_id",
    "house_number",
    "apartment_number",
    "enumerator_name",
    # School/employment details
    "attended_school",
    "worked_last_week",
    "seeking_work",
    "employed",
    "hours_worked",
    "weeks_worked",
    "weeks_out_of_work",
    "income",
    "income_other",
    # Residence questions
    "same_house_1949",
    "same_county_1949",
    "lived_on_farm",
    "lived_on_farm_1949",
    "farm_3_plus_acres",
    # Education
    "grade_completed",
    "completed_grade",
    # Military service
    "veteran",
    "veteran_ww1",
    "veteran_ww2",
    # Other demographics
    "children_born",
    "citizenship_status",
    "married_more_than_once",
    "years_marital_change",
}


class FamilySearchCensusExtractor:
    """Extracts detailed census data from FamilySearch."""

    def __init__(
        self,
        automation: FamilySearchAutomation | None = None,
        repository: CensusExtractionRepository | None = None,
    ):
        """Initialize extractor with automation service and repository."""
        self.automation = automation or get_automation_service()
        self.repository = repository or get_census_repository()
        self._batch_id: int | None = None

    async def connect(self) -> bool:
        """Connect to Chrome browser."""
        return await self.automation.connect_to_chrome()

    async def disconnect(self) -> None:
        """Disconnect from browser."""
        await self.automation.disconnect()

    def start_batch(self, notes: str = "") -> int:
        """Start a new extraction batch."""
        self._batch_id = self.repository.create_batch(
            source="familysearch", notes=notes
        )
        return self._batch_id

    def complete_batch(self) -> None:
        """Complete the current batch."""
        if self._batch_id:
            self.repository.complete_batch(self._batch_id)
            self._batch_id = None

    async def extract_from_ark(
        self,
        ark_url: str,
        census_year: int,
        rmtree_citation_id: int | None = None,
        rmtree_person_id: int | None = None,
        rmtree_database: str = "",
        extract_household: bool = True,
    ) -> ExtractionResult:
        """
        Extract census data from a FamilySearch ARK URL.

        Args:
            ark_url: FamilySearch ARK URL (e.g., https://www.familysearch.org/ark:/61903/1:1:6XKG-DP65)
            census_year: Census year (1790-1950)
            rmtree_citation_id: Optional CitationID from RootsMagic
            rmtree_person_id: Optional PersonID/RIN from RootsMagic
            rmtree_database: Path to RootsMagic database file
            extract_household: If True, also extract other household members

        Returns:
            ExtractionResult with success status and extracted data
        """
        result = ExtractionResult()

        try:
            # Get browser page
            page = await self.automation.get_or_create_page()
            if not page:
                result.error_message = "Failed to get browser page"
                return result

            # Check if already extracted
            existing = self.repository.get_person_by_ark(ark_url)
            if existing:
                logger.info(f"Already extracted: {ark_url}")
                result.success = True
                result.person_id = existing.person_id
                result.page_id = existing.page_id
                return result

            # Navigate to the ARK URL (networkidle waiting handles React hydration)
            logger.info(f"Navigating to: {ark_url}")
            await self._navigate_to_url(page, ark_url)

            # Extract data from the page (locator waits handle any remaining load)
            raw_data = await self._extract_page_data(page)
            if not raw_data:
                result.error_message = "Failed to extract data from page"
                return result

            logger.info(f"Extracted {len(raw_data)} fields from FamilySearch")
            result.extracted_data = raw_data

            # Parse and store the data
            person_data, page_data, extended_fields = self._parse_extracted_data(
                raw_data, census_year, ark_url
            )

            # Ensure batch exists
            if not self._batch_id:
                self.start_batch("Single extraction")

            # Insert or get page
            page_data.batch_id = self._batch_id
            existing_page = self.repository.get_page_by_location(
                census_year,
                page_data.state,
                page_data.county,
                page_data.enumeration_district,
                page_data.page_number or page_data.sheet_number,
            )
            if existing_page:
                page_id = existing_page.page_id
            else:
                page_id = self.repository.insert_page(page_data)

            result.page_id = page_id

            # Insert person
            person_data.page_id = page_id
            person_data.is_target_person = True
            person_id = self.repository.insert_person(person_data)
            result.person_id = person_id

            # Insert extended fields
            if extended_fields:
                fs_labels = {k: raw_data.get(f"_label_{k}", "") for k in extended_fields}
                self.repository.insert_person_fields_bulk(
                    person_id, extended_fields, fs_labels
                )

            # Extract relationships from the data
            relationships = self._extract_relationships(raw_data)
            for rel_type, rel_name in relationships:
                self.repository.insert_relationship(
                    person_id, rel_type, related_person_name=rel_name
                )

            # Create RootsMagic link if provided
            if rmtree_citation_id or rmtree_person_id:
                link = RMTreeLink(
                    census_person_id=person_id,
                    rmtree_person_id=rmtree_person_id,
                    rmtree_citation_id=rmtree_citation_id,
                    rmtree_database=rmtree_database,
                    match_confidence=1.0,
                    match_method="url_match",
                )
                self.repository.insert_rmtree_link(link)

            # Extract household members if requested
            if extract_household:
                # First get household members from the current page's table
                household_members = raw_data.get("_household_members", [])
                if not household_members:
                    # Fallback to index extraction
                    household_members = await self._extract_household_index(page)

                logger.info(f"Found {len(household_members)} household members")

                # Normalize the target person's ARK for comparison
                target_ark_normalized = normalize_ark_url(ark_url)

                # Extract full data for each household member
                for member in household_members:
                    member_ark = member.get("ark")
                    member_ark_normalized = normalize_ark_url(member_ark) if member_ark else None

                    # Skip the target person (compare normalized URLs)
                    if not member_ark_normalized or member_ark_normalized == target_ark_normalized:
                        logger.debug(f"Skipping target person: {member.get('name')}")
                        continue

                    # Check if already extracted (use normalized URL for lookup)
                    existing = self.repository.get_person_by_ark(member_ark_normalized)
                    if existing:
                        logger.info(f"Household member already extracted: {member.get('name')}")
                        result.related_persons.append({
                            "name": member.get("name"),
                            "ark": member_ark_normalized,
                            "person_id": existing.person_id,
                            "already_extracted": True,
                        })
                    else:
                        # Extract full data for this household member
                        logger.info(f"Extracting household member: {member.get('name')} ({member_ark_normalized})")
                        member_result = await self.extract_from_ark(
                            member_ark_normalized,  # Use normalized URL
                            census_year,
                            extract_household=False,  # Don't recurse
                        )
                        if member_result.success:
                            result.related_persons.append({
                                "name": member.get("name"),
                                "ark": member_ark_normalized,
                                "person_id": member_result.person_id,
                                "extracted": True,
                            })
                        else:
                            logger.warning(
                                f"Failed to extract household member {member.get('name')}: "
                                f"{member_result.error_message}"
                            )
                            result.related_persons.append({
                                "name": member.get("name"),
                                "ark": member_ark_normalized,
                                "error": member_result.error_message,
                            })

            result.success = True
            logger.info(
                f"Successfully extracted: {person_data.full_name} "
                f"(person_id={person_id}, page_id={page_id}, "
                f"household_members={len(result.related_persons)})"
            )

        except Exception as e:
            logger.error(f"Extraction failed: {e}", exc_info=True)
            result.error_message = str(e)

        return result

    async def _navigate_to_url(self, page: Page, url: str) -> None:
        """Navigate to URL with proper Playwright waiting strategies.

        Uses Playwright's built-in waiting rather than arbitrary sleeps:
        - wait_until="networkidle" waits for React to finish loading
        - Confirms URL matches expected destination
        """
        try:
            # Use networkidle to wait for React app to fully hydrate
            # This is much better than arbitrary sleeps for SPA apps
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Verify we arrived at the expected URL (handles redirects)
            if "familysearch.org" not in page.url:
                raise ValueError(f"Unexpected redirect to: {page.url}")

            logger.debug(f"Successfully navigated to: {page.url}")

        except Exception as e:
            logger.warning(f"Navigation issue: {e}, checking current state...")
            # Fallback: just wait for domcontentloaded
            if "familysearch.org" not in page.url:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)

    async def _extract_page_data(self, page: Page) -> dict[str, Any]:
        """
        Extract all census data from the FamilySearch page.

        Uses Playwright's Locator API for robust element detection with auto-waiting.
        FamilySearch is a React SPA - elements need time to render after navigation.

        Optimized selectors based on FamilySearch HTML structure:
        - Person details: th.leftSideCss / td.rightSideCss pairs
        - Household members: table.tableCss_t1upzggo with rowCss rows
        """
        # First check if we need to click "Original Document" or expand source info
        await self._expand_source_info(page)

        # Use Playwright Locator API with auto-waiting (much better than wait_for_selector)
        # Locators automatically retry until element is found or timeout
        person_details_locator = page.locator('th[class*="leftSideCss"]').first
        household_table_locator = page.locator('table[class*="tableCss_t1upzggo"]').first

        # Wait for person details to be visible (this is the critical element)
        try:
            await person_details_locator.wait_for(state="visible", timeout=15000)
            logger.debug("Person details table is visible")
        except Exception as e:
            logger.warning(f"Person details not visible after 15s: {e}")
            # Try waiting for any table as fallback
            try:
                await page.locator("table").first.wait_for(state="visible", timeout=5000)
            except Exception:
                logger.warning("No tables found on page")

        # Check if household table exists (optional - don't fail if missing)
        try:
            # Use count() to check existence without waiting
            if await household_table_locator.count() > 0:
                await household_table_locator.wait_for(state="visible", timeout=5000)
                logger.debug("Household members table found")
        except Exception:
            logger.debug("No household table found (may not exist on this page)")

        # Extract all data from the page using JavaScript with optimized selectors
        data = await page.evaluate("""
            () => {
                const result = {};

                // Get the person's name from h1
                const h1 = document.querySelector('h1');
                if (h1) {
                    result['primary_name'] = h1.textContent.trim();
                }

                // OPTIMIZED: Find ALL th/td pairs with leftSideCss/rightSideCss classes
                // This works regardless of which table they're in
                const labelElements = document.querySelectorAll('th[class*="leftSideCss"]');
                for (const th of labelElements) {
                    // Find the parent row, then the td with rightSideCss
                    const row = th.closest('tr');
                    if (!row) continue;

                    const td = row.querySelector('td[class*="rightSideCss"]');
                    if (!td) continue;

                    const label = th.textContent.trim();
                    // Get value - often wrapped in <strong>
                    const strong = td.querySelector('strong');
                    const value = strong ? strong.textContent.trim() : td.textContent.trim();

                    if (label && value) {
                        const key = label.toLowerCase();
                        result[key] = value;
                        result['_label_' + key] = label;
                    }
                }

                // FALLBACK: Generic table extraction if specific selectors don't match
                if (Object.keys(result).length < 5) {
                    const tables = document.querySelectorAll('table');
                    for (const table of tables) {
                        const rows = table.querySelectorAll('tr');
                        for (const row of rows) {
                            const cells = row.querySelectorAll('td, th');
                            if (cells.length >= 2) {
                                const label = cells[0].textContent.trim();
                                const value = cells[1].textContent.trim();
                                if (label && value && !result[label.toLowerCase()]) {
                                    result[label.toLowerCase()] = value;
                                    result['_label_' + label.toLowerCase()] = label;
                                }
                            }
                        }
                    }
                }

                // Extract household members from the family table
                const householdMembers = [];
                const familyTable = document.querySelector('table[class*="tableCss_t1upzggo"], #additionalPersons table');
                if (familyTable) {
                    const rows = familyTable.querySelectorAll('tr[class*="rowCss"]:not([class*="expandable"])');
                    for (const row of rows) {
                        const link = row.querySelector('a[href*="/ark:/"]');
                        const cells = row.querySelectorAll('td');
                        if (link && cells.length >= 4) {
                            householdMembers.push({
                                name: link.textContent.trim(),
                                ark: link.href,
                                relationship: cells[0]?.textContent.trim() || '',
                                sex: cells[1]?.textContent.trim() || '',
                                age: cells[2]?.textContent.trim() || '',
                                birthplace: cells[3]?.textContent.trim() || ''
                            });
                        }
                    }
                }
                result['_household_members'] = householdMembers;

                // Also look for definition lists (dl/dt/dd) as fallback
                const dls = document.querySelectorAll('dl');
                for (const dl of dls) {
                    const dts = dl.querySelectorAll('dt');
                    const dds = dl.querySelectorAll('dd');
                    for (let i = 0; i < dts.length && i < dds.length; i++) {
                        const label = dts[i].textContent.trim();
                        const value = dds[i].textContent.trim();
                        if (label && value && !result[label.toLowerCase()]) {
                            result[label.toLowerCase()] = value;
                            result['_label_' + label.toLowerCase()] = label;
                        }
                    }
                }

                // Look for specific FamilySearch data containers
                const dataContainers = document.querySelectorAll('[data-testid], .source-info, .record-details');
                for (const container of dataContainers) {
                    // Look for label/value pairs
                    const labels = container.querySelectorAll('.label, .field-label, dt');
                    const values = container.querySelectorAll('.value, .field-value, dd');
                    for (let i = 0; i < labels.length && i < values.length; i++) {
                        const label = labels[i].textContent.trim();
                        const value = values[i].textContent.trim();
                        if (label && value && !result[label.toLowerCase()]) {
                            result[label.toLowerCase()] = value;
                            result['_label_' + label.toLowerCase()] = label;
                        }
                    }
                }

                // Get relationships section if present (legacy selector)
                const relationships = [];
                const relSection = document.querySelector('[data-testid="relationships"], .relationships');
                if (relSection) {
                    const items = relSection.querySelectorAll('li, .relationship-item');
                    for (const item of items) {
                        const text = item.textContent.trim();
                        const linkEl = item.querySelector('a');
                        relationships.push({
                            text: text,
                            link: linkEl ? linkEl.href : null
                        });
                    }
                }
                result['_relationships'] = relationships;

                // Get current URL
                result['_current_url'] = window.location.href;

                return result;
            }
        """)

        return data

    async def _expand_source_info(self, page: Page) -> None:
        """Click buttons to expand source/original document info if needed.

        Uses Playwright's Locator API for robust button detection with auto-waiting.
        """
        try:
            # Look for "Original Document" or "Source" expand buttons using Locator API
            # Locators auto-wait and are more reliable than query_selector
            expand_buttons = [
                page.get_by_role("button", name="Original Document"),
                page.get_by_role("button", name="Source"),
                page.get_by_role("button", name="View Original"),
                page.locator('[data-testid="expand-source"]'),
                page.locator('.expand-source-btn'),
            ]

            for locator in expand_buttons:
                try:
                    # Use count() to check if button exists (non-blocking)
                    if await locator.count() > 0:
                        # Click with force=False lets Playwright wait for actionability
                        await locator.click(timeout=3000)
                        # Wait for potential animations/content loading
                        await page.wait_for_load_state("networkidle", timeout=5000)
                        logger.debug(f"Clicked expand button: {locator}")
                        break
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"No expand button found or click failed: {e}")

    async def _extract_household_index(self, page: Page) -> list[dict[str, Any]]:
        """
        Extract household members from the page index.

        FamilySearch shows other people on the same census page
        in a sidebar or index view. Uses Playwright's Locator API.
        """
        try:
            # Try to find and click the "Browse" or index link using Locator API
            index_locators = [
                page.get_by_role("link", name="Browse"),
                page.get_by_role("link", name="Index"),
                page.locator('[data-testid="browse-records"]'),
                page.locator('.browse-link'),
            ]

            for locator in index_locators:
                try:
                    if await locator.count() > 0:
                        await locator.click(timeout=3000)
                        # Wait for index content to load
                        await page.wait_for_load_state("networkidle", timeout=5000)
                        break
                except Exception:
                    continue

            # Extract list of people from the index
            household = await page.evaluate("""
                () => {
                    const members = [];
                    // Look for list of names in index view
                    const items = document.querySelectorAll(
                        '.index-item, .browse-item, [data-testid="index-row"], .record-list li'
                    );
                    for (const item of items) {
                        const linkEl = item.querySelector('a');
                        const name = item.textContent.trim();
                        if (name) {
                            members.push({
                                name: name,
                                ark: linkEl ? linkEl.href : null
                            });
                        }
                    }
                    return members;
                }
            """)

            return household

        except Exception as e:
            logger.warning(f"Failed to extract household index: {e}")
            return []

    def _parse_extracted_data(
        self, raw_data: dict[str, Any], census_year: int, ark_url: str
    ) -> tuple[CensusPerson, CensusPage, dict[str, Any]]:
        """
        Parse raw extracted data into structured objects.

        Returns:
            Tuple of (CensusPerson, CensusPage, extended_fields dict)
        """
        # Initialize objects (normalize ARK URL for consistent storage/lookup)
        person = CensusPerson(familysearch_ark=normalize_ark_url(ark_url))
        page = CensusPage(census_year=census_year)
        extended_fields = {}

        # Map FamilySearch fields to our schema
        for fs_label, value in raw_data.items():
            if fs_label.startswith("_"):
                continue  # Skip metadata fields

            # Normalize label
            label = fs_label.lower().strip()

            # Look up mapping
            mapped_field = FAMILYSEARCH_FIELD_MAP.get(label)
            if not mapped_field:
                # Try partial match for fields with colons or parentheses
                for fs_key, mapped in FAMILYSEARCH_FIELD_MAP.items():
                    if fs_key in label or label in fs_key:
                        mapped_field = mapped
                        break

            if mapped_field:
                # Determine if this is a core field or extended field
                if mapped_field in EXTENDED_FIELDS or "code" in label:
                    extended_fields[mapped_field] = value
                elif hasattr(person, mapped_field):
                    self._set_field(person, mapped_field, value)
                elif hasattr(page, mapped_field):
                    self._set_field(page, mapped_field, value)
            else:
                # Store unmapped fields in extended
                safe_name = re.sub(r"[^a-z0-9_]", "_", label)
                extended_fields[safe_name] = value

        # Build full name from parts or parse full_name into parts
        if person.full_name and not person.given_name and not person.surname:
            # FamilySearch provides "Name" as full name - split into parts
            self._parse_name_into_parts(person)

        if not person.full_name:
            parts = [person.given_name, person.surname]
            if person.name_suffix:
                parts.append(person.name_suffix)
            person.full_name = " ".join(p for p in parts if p)

        # Use primary_name if we still don't have a name
        if not person.full_name and raw_data.get("primary_name"):
            person.full_name = raw_data["primary_name"]
            self._parse_name_into_parts(person)

        # Handle 1950 stamp/page terminology
        if census_year == 1950 and page.page_number:
            page.stamp_number = page.page_number

        # Parse event_place for state/county if not already set
        event_place = extended_fields.get("event_place", "")
        if event_place and not page.state:
            self._parse_event_place(page, event_place)

        return person, page, extended_fields

    def _parse_name_into_parts(self, person: CensusPerson) -> None:
        """Parse a full name into given_name and surname."""
        if not person.full_name:
            return

        name = person.full_name.strip()

        # Common suffixes to detect
        suffixes = ["Jr", "Jr.", "Sr", "Sr.", "II", "III", "IV", "V"]

        # Check for suffix
        for suffix in suffixes:
            if name.endswith(f" {suffix}"):
                person.name_suffix = suffix.rstrip(".")
                name = name[: -(len(suffix) + 1)].strip()
                break

        # Split remaining name into parts
        parts = name.split()
        if len(parts) >= 2:
            # Last word is surname, rest is given name
            person.surname = parts[-1]
            person.given_name = " ".join(parts[:-1])
        elif len(parts) == 1:
            person.surname = parts[0]

    def _parse_event_place(self, page: CensusPage, event_place: str) -> None:
        """Parse event place string into state/county fields."""
        # Format typically: "County, State, United States"
        parts = [p.strip() for p in event_place.split(",")]
        if len(parts) >= 3 and "United States" in parts[-1]:
            page.state = parts[-2]
            page.county = parts[-3] if len(parts) >= 3 else ""
        elif len(parts) >= 2:
            page.state = parts[-1]
            page.county = parts[-2]

    def _set_field(self, obj: Any, field_name: str, value: str) -> None:
        """Set a field value with type conversion."""
        if not hasattr(obj, field_name):
            return

        # Get the expected type from the existing value
        current = getattr(obj, field_name)

        try:
            if isinstance(current, int) or field_name in ("age", "line_number"):
                # Extract numeric value
                match = re.search(r"\d+", str(value))
                if match:
                    setattr(obj, field_name, int(match.group()))
            elif isinstance(current, bool):
                setattr(obj, field_name, value.lower() in ("yes", "y", "true", "1"))
            else:
                setattr(obj, field_name, str(value))
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to set {field_name}={value}: {e}")

    def _extract_relationships(self, raw_data: dict[str, Any]) -> list[tuple[str, str]]:
        """Extract relationships from raw data."""
        relationships = []

        # Check the _relationships list from JavaScript extraction
        rel_list = raw_data.get("_relationships", [])
        for rel in rel_list:
            text = rel.get("text", "")
            # Parse relationship type and name
            # Format: "Spouse: John Smith" or "Child: Jane Smith"
            if ":" in text:
                rel_type, name = text.split(":", 1)
                relationships.append((rel_type.strip().lower(), name.strip()))

        # Also check individual relationship fields
        rel_fields = ["spouse", "child", "father", "mother", "sibling"]
        for rel_type in rel_fields:
            value = raw_data.get(rel_type)
            if value:
                relationships.append((rel_type, value))

        return relationships


# =============================================================================
# Convenience Functions
# =============================================================================


async def extract_census_from_citation(
    ark_url: str,
    census_year: int,
    rmtree_citation_id: int | None = None,
    rmtree_person_id: int | None = None,
    rmtree_database: str = "",
) -> ExtractionResult:
    """
    Convenience function to extract census data from a FamilySearch ARK URL.

    Args:
        ark_url: FamilySearch ARK URL
        census_year: Census year (1790-1950)
        rmtree_citation_id: Optional CitationID from RootsMagic
        rmtree_person_id: Optional PersonID/RIN from RootsMagic
        rmtree_database: Path to RootsMagic database

    Returns:
        ExtractionResult with extracted data
    """
    extractor = FamilySearchCensusExtractor()
    try:
        connected = await extractor.connect()
        if not connected:
            return ExtractionResult(
                success=False, error_message="Failed to connect to Chrome"
            )

        extractor.start_batch(f"Extract from {ark_url}")
        result = await extractor.extract_from_ark(
            ark_url,
            census_year,
            rmtree_citation_id=rmtree_citation_id,
            rmtree_person_id=rmtree_person_id,
            rmtree_database=rmtree_database,
        )
        extractor.complete_batch()
        return result

    finally:
        await extractor.disconnect()


def display_extraction_result(result: ExtractionResult) -> None:
    """Print extraction result in a formatted way."""
    if result.success:
        print(f"\n{'='*60}")
        print(f"Extraction Successful")
        print(f"{'='*60}")
        print(f"Person ID: {result.person_id}")
        print(f"Page ID: {result.page_id}")
        print(f"\nExtracted Fields ({len(result.extracted_data)}):")
        for key, value in sorted(result.extracted_data.items()):
            if not key.startswith("_"):
                print(f"  {key}: {value}")
        if result.related_persons:
            print(f"\nHousehold Members ({len(result.related_persons)}):")
            for member in result.related_persons:
                print(f"  - {member.get('name', 'Unknown')}")
    else:
        print(f"\nExtraction Failed: {result.error_message}")
