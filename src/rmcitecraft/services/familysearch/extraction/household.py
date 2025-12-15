"""Household extraction strategy for FamilySearch census records.

This strategy extracts household member data from FamilySearch census pages.
Household data shows all persons enumerated at the same dwelling/family
in the census.
"""

import re
from typing import Any

from loguru import logger
from playwright.async_api import Page

from ..field_mapping import map_familysearch_field
from .base import PlaywrightExtractionStrategy


class HouseholdStrategy(PlaywrightExtractionStrategy):
    """Extracts household member data from FamilySearch census pages.

    This strategy finds and extracts information about all members
    of a census household, typically shown in a list or table format
    on the census detail page.

    Household members usually share:
    - Dwelling number
    - Family number
    - Location (state, county, township)
    - Enumeration district, sheet, page

    Each member has individual:
    - Name
    - Age
    - Sex
    - Relationship to head
    - Other personal details
    """

    def get_strategy_name(self) -> str:
        return "household"

    async def extract(self, page: Page, census_year: int) -> dict[str, Any]:
        """Extract household members from census page.

        Args:
            page: Playwright Page on FamilySearch census view
            census_year: Census year for context

        Returns:
            Dictionary with:
            - members: List of household member dictionaries
            - head_name: Name of household head (if identified)
            - member_count: Number of members found
        """
        members = await self._extract_household_members(page, census_year)

        # Try to identify head of household
        head_name = None
        for member in members:
            relationship = member.get("relationship_to_head", "").lower()
            if relationship in ("head", "self", "head of household"):
                head_name = member.get("full_name") or member.get("given_name", "")
                break

        logger.debug(
            f"[{self.get_strategy_name()}] "
            f"Found {len(members)} household members, head='{head_name}'"
        )

        return {
            "members": members,
            "head_name": head_name,
            "member_count": len(members),
        }

    async def _extract_household_members(
        self,
        page: Page,
        census_year: int,
    ) -> list[dict[str, Any]]:
        """Extract all household members from page.

        Looks for household data in:
        1. Explicit household/family section
        2. Related persons list
        3. Table of household members

        Args:
            page: Playwright Page object
            census_year: Census year for context

        Returns:
            List of member dictionaries
        """
        members: list[dict[str, Any]] = []

        # Try different extraction approaches
        # 1. Look for household member links/rows
        members = await self._extract_from_household_section(page)
        if members:
            return members

        # 2. Try table-based extraction
        members = await self._extract_from_table(page)
        if members:
            return members

        # 3. Try list-based extraction
        members = await self._extract_from_list(page)

        return members

    async def _extract_from_household_section(
        self,
        page: Page,
    ) -> list[dict[str, Any]]:
        """Extract members from dedicated household section.

        Args:
            page: Playwright Page object

        Returns:
            List of member dictionaries
        """
        members: list[dict[str, Any]] = []

        try:
            # Look for household section containers
            section_selectors = [
                '[class*="household"]',
                '[class*="family-members"]',
                '[data-testid="household"]',
                'section:has-text("Household")',
            ]

            for selector in section_selectors:
                section = page.locator(selector).first
                if await section.count() == 0:
                    continue

                # Look for person links within section
                person_links = section.locator('a[href*="/ark:/61903/1:1:"]')
                count = await person_links.count()

                if count > 0:
                    for i in range(count):
                        link = person_links.nth(i)
                        member = await self._extract_member_from_link(link)
                        if member:
                            members.append(member)

                    if members:
                        return members

        except Exception as e:
            logger.debug(
                f"[{self.get_strategy_name()}] "
                f"household section extraction failed: {e}"
            )

        return members

    async def _extract_member_from_link(self, link) -> dict[str, Any] | None:
        """Extract member info from a person link element.

        Args:
            link: Playwright locator for link element

        Returns:
            Member dictionary or None
        """
        try:
            # Get link text (usually person name)
            name = (await link.inner_text()).strip()
            if not name:
                return None

            # Get link href for ARK
            href = await link.get_attribute("href")
            ark = ""
            if href:
                ark_match = re.search(r"/ark:/61903/([^?&\s]+)", href)
                if ark_match:
                    ark = f"ark:/61903/{ark_match.group(1)}"

            member = {
                "full_name": name,
                "person_ark": ark,
            }

            # Try to get additional info from sibling/parent elements
            parent = link.locator("..")
            parent_text = await parent.inner_text()

            # Look for age pattern
            age_match = re.search(r"\b(\d{1,3})\s*(?:years?|yrs?|y)?\b", parent_text)
            if age_match:
                member["age"] = age_match.group(1)

            # Look for sex indicator
            if re.search(r"\b(?:male|man|boy|m)\b", parent_text, re.IGNORECASE):
                member["sex"] = "Male"
            elif re.search(r"\b(?:female|woman|girl|f)\b", parent_text, re.IGNORECASE):
                member["sex"] = "Female"

            # Look for relationship
            rel_patterns = [
                (r"\b(head)\b", "Head"),
                (r"\b(wife|spouse)\b", "Wife"),
                (r"\b(son|daughter|child)\b", "Child"),
                (r"\b(mother|father|parent)\b", "Parent"),
                (r"\b(brother|sister|sibling)\b", "Sibling"),
                (r"\b(boarder|lodger)\b", "Boarder"),
                (r"\b(servant)\b", "Servant"),
            ]
            for pattern, relationship in rel_patterns:
                if re.search(pattern, parent_text, re.IGNORECASE):
                    member["relationship_to_head"] = relationship
                    break

            return member

        except Exception:
            return None

    async def _extract_from_table(self, page: Page) -> list[dict[str, Any]]:
        """Extract members from table structure.

        Args:
            page: Playwright Page object

        Returns:
            List of member dictionaries
        """
        members: list[dict[str, Any]] = []

        try:
            # Look for tables that might contain household data
            tables = await page.locator("table").all()

            for table in tables:
                # Check if this looks like a household table
                header_text = await table.inner_text()
                if not any(
                    keyword in header_text.lower()
                    for keyword in ["name", "age", "relationship", "household"]
                ):
                    continue

                # Get table rows
                rows = await table.locator("tr").all()
                if len(rows) < 2:  # Need header + at least one data row
                    continue

                # Get header columns
                header_row = rows[0]
                headers = await header_row.locator("th, td").all()
                header_names = []
                for h in headers:
                    text = (await h.inner_text()).strip().lower()
                    header_names.append(text)

                # Process data rows
                for row in rows[1:]:
                    cells = await row.locator("td").all()
                    if len(cells) != len(header_names):
                        continue

                    member: dict[str, Any] = {}
                    for i, cell in enumerate(cells):
                        value = (await cell.inner_text()).strip()
                        if not value:
                            continue

                        header = header_names[i] if i < len(header_names) else f"col_{i}"
                        internal_field = map_familysearch_field(header)
                        if internal_field:
                            member[internal_field] = value
                        elif header in ("name", "person"):
                            member["full_name"] = value

                    if member and ("full_name" in member or "given_name" in member):
                        members.append(member)

                if members:
                    return members

        except Exception as e:
            logger.debug(
                f"[{self.get_strategy_name()}] table extraction failed: {e}"
            )

        return members

    async def _extract_from_list(self, page: Page) -> list[dict[str, Any]]:
        """Extract members from list structure.

        Args:
            page: Playwright Page object

        Returns:
            List of member dictionaries
        """
        members: list[dict[str, Any]] = []

        try:
            # Look for list items containing person links
            list_items = await page.locator(
                'li:has(a[href*="/ark:/61903/1:1:"]), '
                '[class*="person-item"], '
                '[class*="member-item"]'
            ).all()

            for item in list_items:
                # Find person link
                link = item.locator('a[href*="/ark:/61903/1:1:"]').first
                if await link.count() > 0:
                    member = await self._extract_member_from_link(link)
                    if member:
                        members.append(member)

        except Exception as e:
            logger.debug(
                f"[{self.get_strategy_name()}] list extraction failed: {e}"
            )

        return members
