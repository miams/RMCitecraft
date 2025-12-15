"""Person page extraction strategy for FamilySearch census records.

This strategy extracts data from FamilySearch person ARK pages.
These pages show summary information about a person record and
provide links to the detail/image view.

URL Pattern: /ark:/61903/1:1:... (1:1 indicates person record)
"""

import re
from typing import Any

from loguru import logger
from playwright.async_api import Page

from ..field_mapping import map_familysearch_field
from .base import PlaywrightExtractionStrategy


class PersonPageStrategy(PlaywrightExtractionStrategy):
    """Extracts census data from FamilySearch person ARK pages.

    Person pages display summary information about a census record,
    including the person's name and key facts. These pages typically
    have less detail than the image/detail view pages.

    This strategy extracts:
    1. Person name from h1
    2. Event information (date, place)
    3. Key person attributes
    4. Links to related pages (detail view, household)
    """

    def get_strategy_name(self) -> str:
        return "person_page"

    async def extract(self, page: Page, census_year: int) -> dict[str, Any]:
        """Extract census data from person ARK page.

        Args:
            page: Playwright Page on FamilySearch person view
            census_year: Census year for context

        Returns:
            Dictionary with extracted person and event data
        """
        data: dict[str, Any] = {
            "census_year": census_year,
        }

        # Extract person name from h1
        data["full_name"] = await self._extract_person_name(page)

        # Extract event date (census year from title/breadcrumb)
        data["event_date"] = await self._extract_event_date(page)

        # Extract event place
        data["event_place"] = await self._extract_event_place(page)

        # Extract person attributes from labeled values
        attributes = await self._extract_person_attributes(page)
        data.update(attributes)

        # Extract links to related pages
        data["detail_page_url"] = await self._extract_detail_page_link(page)
        data["household_url"] = await self._extract_household_link(page)

        # Extract person ARK from URL
        data["person_ark"] = self._extract_ark_from_url(page.url)

        logger.debug(
            f"[{self.get_strategy_name()}] Extracted: "
            f"name='{data.get('full_name')}', "
            f"place='{data.get('event_place')}', "
            f"has_detail_link={bool(data.get('detail_page_url'))}"
        )

        return data

    async def _extract_person_name(self, page: Page) -> str:
        """Extract person name from h1 element.

        Args:
            page: Playwright Page object

        Returns:
            Person name or empty string
        """
        try:
            h1 = page.locator("h1").first
            if await h1.count() > 0:
                return (await h1.inner_text()).strip()
        except Exception as e:
            logger.debug(f"[{self.get_strategy_name()}] h1 extraction failed: {e}")

        return ""

    async def _extract_event_date(self, page: Page) -> str:
        """Extract event date (census year) from page.

        Looks for census year in:
        1. Page title (e.g., "United States, Census, 1910")
        2. Breadcrumb text
        3. Event date field

        Args:
            page: Playwright Page object

        Returns:
            Census year or empty string
        """
        try:
            # Check page title first
            title = await page.title()
            year_match = re.search(r"Census,?\s*(\d{4})", title)
            if year_match:
                return year_match.group(1)

            # Check for explicit date field
            date_value = await self._extract_labeled_value(page, "date")
            if date_value:
                return date_value

            # Check event date field
            event_date = await self._extract_labeled_value(page, "event date")
            if event_date:
                return event_date

        except Exception as e:
            logger.debug(f"[{self.get_strategy_name()}] date extraction failed: {e}")

        return ""

    async def _extract_event_place(self, page: Page) -> str:
        """Extract event place from page.

        Args:
            page: Playwright Page object

        Returns:
            Event place or empty string
        """
        try:
            # Try common place field labels
            for label in ["event place", "place", "residence"]:
                value = await self._extract_labeled_value(page, label)
                if value:
                    return value

        except Exception as e:
            logger.debug(f"[{self.get_strategy_name()}] place extraction failed: {e}")

        return ""

    async def _extract_person_attributes(self, page: Page) -> dict[str, Any]:
        """Extract person attributes from labeled values.

        Args:
            page: Playwright Page object

        Returns:
            Dictionary of mapped field:value pairs
        """
        attributes: dict[str, Any] = {}

        try:
            raw_data = await self._extract_all_labeled_values(page)

            for raw_key, value in raw_data.items():
                if not value or not str(value).strip():
                    continue

                internal_field = map_familysearch_field(raw_key)
                if internal_field:
                    attributes[internal_field] = value

        except Exception as e:
            logger.debug(
                f"[{self.get_strategy_name()}] attribute extraction failed: {e}"
            )

        return attributes

    async def _extract_detail_page_link(self, page: Page) -> str | None:
        """Extract link to detail/image view page.

        Looks for links with:
        - "View Record" text
        - "/ark:/61903/3:1:" pattern (image/detail view)

        Args:
            page: Playwright Page object

        Returns:
            Detail page URL or None
        """
        try:
            # Look for "View Record" or similar links
            view_link = page.locator('a:has-text("View Record"), a:has-text("View Image")')
            if await view_link.count() > 0:
                href = await view_link.first.get_attribute("href")
                if href:
                    # Make absolute URL if relative
                    if href.startswith("/"):
                        href = f"https://www.familysearch.org{href}"
                    return href

            # Look for links with 3:1 pattern (detail/image view ARK)
            detail_links = page.locator('a[href*="/ark:/61903/3:1:"]')
            if await detail_links.count() > 0:
                href = await detail_links.first.get_attribute("href")
                if href:
                    if href.startswith("/"):
                        href = f"https://www.familysearch.org{href}"
                    return href

        except Exception as e:
            logger.debug(f"[{self.get_strategy_name()}] detail link extraction failed: {e}")

        return None

    async def _extract_household_link(self, page: Page) -> str | None:
        """Extract link to household/family view.

        Args:
            page: Playwright Page object

        Returns:
            Household page URL or None
        """
        try:
            # Look for household-related links
            household_link = page.locator(
                'a:has-text("Household"), '
                'a:has-text("Family Members"), '
                'a:has-text("View Household")'
            )
            if await household_link.count() > 0:
                href = await household_link.first.get_attribute("href")
                if href:
                    if href.startswith("/"):
                        href = f"https://www.familysearch.org{href}"
                    return href

        except Exception as e:
            logger.debug(f"[{self.get_strategy_name()}] household link extraction failed: {e}")

        return None

    def _extract_ark_from_url(self, url: str) -> str:
        """Extract ARK identifier from FamilySearch URL.

        Args:
            url: FamilySearch URL

        Returns:
            ARK identifier or empty string
        """
        # Pattern: /ark:/61903/1:1:XXXX-XXX
        ark_match = re.search(r"/ark:/61903/([^?&\s]+)", url)
        if ark_match:
            return f"ark:/61903/{ark_match.group(1)}"
        return ""
