"""Detail page extraction strategy for FamilySearch census records.

This strategy extracts data from FamilySearch census detail/image view pages.
These pages show the indexed census data in a structured format with
label:value pairs.

URL Pattern: /ark:/61903/3:1:... (3:1 indicates image/detail view)

For pre-1850 censuses (1790-1840), the detail page provides more reliable
place data than the person page. The field labels are consistent even
though the order may vary.
"""

import re
from typing import Any

from loguru import logger
from playwright.async_api import Page

from ..field_mapping import (
    is_extended_field,
    is_page_field,
    map_familysearch_field,
)
from ..year_handler import YearSpecificHandler
from .base import PlaywrightExtractionStrategy


class DetailPageStrategy(PlaywrightExtractionStrategy):
    """Extracts census data from FamilySearch detail/image view pages.

    These pages display indexed census record data in label:value format,
    typically in a panel alongside the census image.

    Extraction uses Playwright locators to find:
    1. data-dense elements with labelCss class (primary)
    2. Table rows with th/td structure (fallback)
    3. Definition lists (dt/dd) (fallback)
    """

    def get_strategy_name(self) -> str:
        return "detail_page"

    async def extract(self, page: Page, census_year: int) -> dict[str, Any]:
        """Extract census data from detail page.

        Args:
            page: Playwright Page on FamilySearch detail view
            census_year: Census year for year-specific processing

        Returns:
            Dictionary with:
            - person: Person field values
            - page_data: Page/location field values
            - extended: Extended field values (EAV storage)
            - raw: All raw extracted key:value pairs
        """
        year_handler = YearSpecificHandler(census_year)

        # Extract all raw data using Playwright locators
        raw_data = await self._extract_all_raw_data(page)

        logger.debug(
            f"[{self.get_strategy_name()}] "
            f"Extracted {len(raw_data)} raw fields for {census_year}"
        )

        # Map and categorize fields
        person: dict[str, Any] = {}
        page_data: dict[str, Any] = {"census_year": census_year}
        extended: dict[str, Any] = {}

        for raw_key, value in raw_data.items():
            # Skip empty values
            if not value or not str(value).strip():
                continue

            # Map FamilySearch label to internal field name
            internal_field = map_familysearch_field(raw_key)

            if not internal_field:
                # Store unmapped fields in extended
                extended[raw_key] = value
                continue

            # Categorize into person, page, or extended
            if is_page_field(internal_field):
                page_data[internal_field] = value
            elif is_extended_field(internal_field):
                extended[internal_field] = value
            else:
                person[internal_field] = value

        # Apply year-specific processing
        self._apply_year_specific_processing(
            year_handler, person, page_data, extended
        )

        return {
            "person": person,
            "page_data": page_data,
            "extended": extended,
            "raw": raw_data,
        }

    async def _extract_all_raw_data(self, page: Page) -> dict[str, str]:
        """Extract all label:value pairs from page using Playwright.

        Args:
            page: Playwright Page object

        Returns:
            Dictionary of {lowercase_underscore_label: value}
        """
        data: dict[str, str] = {}

        # First, ensure the NAMES panel is visible (click NAMES tab if present)
        await self._ensure_names_panel_visible(page)

        # Primary: Regex-based extraction from body text
        # This is the most reliable method for FamilySearch detail pages
        # The field labels are consistent even though order varies
        regex_data = await self._extract_using_text_patterns(page)
        data.update(regex_data)

        # Fallback: data-dense elements (labelCss class)
        dense_data = await self._extract_all_labeled_values(page)
        for key, value in dense_data.items():
            if key not in data:
                data[key] = value

        # Fallback: table rows
        table_data = await self._extract_table_data(page)
        for key, value in table_data.items():
            if key not in data:
                data[key] = value

        # Fallback: dt/dd pairs
        dl_data = await self._extract_definition_list(page)
        for key, value in dl_data.items():
            if key not in data:
                data[key] = value

        return data

    async def _ensure_names_panel_visible(self, page: Page) -> None:
        """Click NAMES tab to reveal the index panel if not already visible.

        FamilySearch detail pages may show the image viewer without the
        index panel visible. Clicking the NAMES tab reveals the indexed data.

        Args:
            page: Playwright Page object
        """
        try:
            names_tab = page.locator('text=NAMES').first
            if await names_tab.count() > 0:
                await names_tab.click()
                await page.wait_for_timeout(1500)
                logger.debug(f"[{self.get_strategy_name()}] Clicked NAMES tab")
        except Exception as e:
            logger.debug(f"[{self.get_strategy_name()}] NAMES tab click failed: {e}")

    async def _extract_using_text_patterns(self, page: Page) -> dict[str, str]:
        """Extract fields using regex patterns on body text.

        This is the most reliable extraction method for FamilySearch detail pages.
        The field labels are consistent (e.g., "Township:", "County:", "State:")
        even though the display order may vary.

        Args:
            page: Playwright Page object

        Returns:
            Dictionary of {lowercase_underscore_label: value}
        """
        data: dict[str, str] = {}

        try:
            body_text = await page.locator('body').inner_text()

            # Define field patterns - these are CONSISTENT and RELIABLE
            field_patterns = {
                'given_name': r'Given Name:\s*(.+)',
                'surname': r'Surname:\s*(.+)',
                'township': r'Township:\s*(.+)',
                'state': r'State:\s*(.+)',
                'county': r'County:\s*(.+)',
                'country': r'Country:\s*(.+)',
                'year': r'Year:\s*(\d{4})',
                'source_page_number': r'Source Page Number:\s*(\d+)',
                'page_number': r'Page Number:\s*(\d+)',
                'enumeration_district': r'Enumeration District:\s*(.+)',
                'sheet_number': r'Sheet Number:\s*(.+)',
                'sheet_letter': r'Sheet Letter:\s*(.+)',
                'dwelling_number': r'Dwelling Number:\s*(\d+)',
                'family_number': r'Family Number:\s*(\d+)',
                'line_number': r'Line Number:\s*(\d+)',
                'age': r'Age:\s*(\d+)',
                'birthplace': r'Birthplace:\s*(.+)',
                'occupation': r'Occupation:\s*(.+)',
                'race': r'Race:\s*(.+)',
                'gender': r'Gender:\s*(.+)',
                'marital_status': r'Marital Status:\s*(.+)',
            }

            for key, pattern in field_patterns.items():
                match = re.search(pattern, body_text, re.IGNORECASE)
                if match:
                    # Clean value - take first line only, trim whitespace
                    value = match.group(1).strip().split('\n')[0].strip()
                    if value:
                        data[key] = value

            logger.debug(
                f"[{self.get_strategy_name()}] "
                f"Regex extraction found {len(data)} fields"
            )

        except Exception as e:
            logger.debug(f"[{self.get_strategy_name()}] Regex extraction failed: {e}")

        return data

    async def _extract_definition_list(self, page: Page) -> dict[str, str]:
        """Extract data from dt/dd definition lists.

        Args:
            page: Playwright Page object

        Returns:
            Dictionary of {lowercase_underscore_label: value}
        """
        data: dict[str, str] = {}

        try:
            dt_elements = await page.locator("dt").all()

            for dt in dt_elements:
                try:
                    label = (await dt.inner_text()).strip()
                    # Get following dd element
                    dd = dt.locator("xpath=following-sibling::dd[1]")
                    if await dd.count() > 0:
                        value = (await dd.inner_text()).strip()
                        if label and value and len(label) < 50:
                            key = label.lower().replace(" ", "_")
                            data[key] = value
                except Exception:
                    continue

            return data

        except Exception as e:
            logger.debug(f"[{self.get_strategy_name()}] dt/dd extraction failed: {e}")
            return data

    def _apply_year_specific_processing(
        self,
        handler: YearSpecificHandler,
        person: dict[str, Any],
        page_data: dict[str, Any],
        extended: dict[str, Any],
    ) -> None:
        """Apply year-specific field processing.

        Handles census-year-specific quirks like:
        - 1910: household_id is family_number, not dwelling_number
        - 1910: Combine sheet_number + sheet_letter
        - 1910: Parse "ED 340" format

        Args:
            handler: YearSpecificHandler for the census year
            person: Person data dict (modified in place)
            page_data: Page data dict (modified in place)
            extended: Extended data dict (modified in place)
        """
        census_year = handler.year

        # Process household_id based on year
        # For 1910, it's family_number; for others, it's dwelling_number
        if "dwelling_number" in person:
            dwelling, family = handler.parse_household_id(person["dwelling_number"])
            if family:
                person["family_number"] = family
                del person["dwelling_number"]
            elif dwelling:
                person["dwelling_number"] = dwelling

        # Process house_number for 1850: FamilySearch's "House Number" is the dwelling number
        if "house_number" in extended and census_year == 1850:
            dwelling = handler.parse_house_number(extended["house_number"])
            if dwelling and "dwelling_number" not in person:
                person["dwelling_number"] = dwelling
                logger.debug(f"[{self.get_strategy_name()}] 1850: house_number -> dwelling_number: {dwelling}")

        # Process enumeration district
        if "enumeration_district" in page_data:
            parsed_ed = handler.parse_enumeration_district(
                page_data["enumeration_district"]
            )
            if parsed_ed:
                page_data["enumeration_district"] = parsed_ed

        # Process sheet number with letter
        sheet_letter = page_data.pop("sheet_letter", None) or extended.pop("sheet_letter", None)
        if "sheet_number" in page_data:
            combined = handler.parse_sheet(
                page_data["sheet_number"],
                sheet_letter
            )
            if combined:
                page_data["sheet_number"] = combined

        logger.debug(
            f"[{self.get_strategy_name()}] "
            f"Applied {census_year} processing: "
            f"ED={page_data.get('enumeration_district')}, "
            f"sheet={page_data.get('sheet_number')}, "
            f"family={person.get('family_number')}"
        )
