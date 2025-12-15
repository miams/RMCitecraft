"""Unified census data extractor for FamilySearch.

This is the single entry point for all FamilySearch census data extraction.
It replaces the duplicate extraction logic that previously existed in
familysearch_automation.py and familysearch_census_extractor.py.

Usage:
    async with CensusExtractor() as extractor:
        # Extract from a detail page
        result = await extractor.extract(url, census_year=1910)

        # Extract household members
        household = await extractor.extract_household(url, census_year=1910)
"""

from dataclasses import dataclass, field
from typing import Any

from loguru import logger
from playwright.async_api import Page

from .browser import BrowserConnection
from .extraction import DetailPageStrategy, HouseholdStrategy, PersonPageStrategy
from .year_handler import YearSpecificHandler


@dataclass
class ExtractionResult:
    """Result of census data extraction.

    Attributes:
        success: Whether extraction succeeded
        person: Person-level data (CensusPerson fields)
        page_data: Page-level data (CensusPage fields)
        extended: Extended fields (EAV storage)
        raw: Raw extracted key:value pairs
        error: Error message if extraction failed
    """

    success: bool
    person: dict[str, Any] = field(default_factory=dict)
    page_data: dict[str, Any] = field(default_factory=dict)
    extended: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class HouseholdResult:
    """Result of household extraction.

    Attributes:
        success: Whether extraction succeeded
        members: List of household member dictionaries
        head_name: Name of household head (if identified)
        error: Error message if extraction failed
    """

    success: bool
    members: list[dict[str, Any]] = field(default_factory=list)
    head_name: str | None = None
    error: str | None = None


class CensusExtractor:
    """Unified census data extractor for FamilySearch.

    This class provides a single, consistent interface for extracting
    census data from FamilySearch pages. It automatically selects the
    appropriate extraction strategy based on URL pattern.

    All extraction follows the Playwright-first policy defined in
    extraction/base.py.

    Example:
        # Using context manager
        async with CensusExtractor() as extractor:
            result = await extractor.extract(url, census_year=1910)
            if result.success:
                print(f"Extracted: {result.person}")

        # Manual connection management
        extractor = CensusExtractor()
        try:
            await extractor.connect()
            result = await extractor.extract(url, census_year=1940)
        finally:
            await extractor.disconnect()
    """

    def __init__(self, browser: BrowserConnection | None = None):
        """Initialize extractor.

        Args:
            browser: Optional BrowserConnection to use. If not provided,
                    a new connection will be created.
        """
        self._browser = browser
        self._owns_browser = browser is None

        # Extraction strategies
        self._detail_strategy = DetailPageStrategy()
        self._person_strategy = PersonPageStrategy()
        self._household_strategy = HouseholdStrategy()

    @property
    def is_connected(self) -> bool:
        """Whether browser is connected."""
        return self._browser is not None and self._browser.is_connected

    async def __aenter__(self) -> "CensusExtractor":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self) -> bool:
        """Connect to browser.

        Returns:
            True if connected successfully
        """
        if self._browser is None:
            self._browser = BrowserConnection()
            self._owns_browser = True

        if not self._browser.is_connected:
            return await self._browser.connect()

        return True

    async def disconnect(self) -> None:
        """Disconnect from browser."""
        if self._browser and self._owns_browser:
            await self._browser.disconnect()
            self._browser = None

    async def extract(
        self,
        url: str,
        census_year: int,
        *,
        navigate: bool = True,
    ) -> ExtractionResult:
        """Extract census data from FamilySearch URL.

        Automatically selects the appropriate extraction strategy based
        on the URL pattern:
        - /ark:/61903/3:1: -> Detail page strategy
        - /ark:/61903/1:1: -> Person page strategy

        Args:
            url: FamilySearch URL (ARK format)
            census_year: Census year (1790-1950, excluding 1890)
            navigate: Whether to navigate to the URL (default True)

        Returns:
            ExtractionResult with extracted data
        """
        try:
            # Validate census year
            if not YearSpecificHandler(census_year):
                return ExtractionResult(
                    success=False,
                    error=f"Invalid census year: {census_year}",
                )

            # Ensure connected
            if not await self.connect():
                return ExtractionResult(
                    success=False,
                    error="Failed to connect to browser",
                )

            # Navigate to URL
            page = await self._navigate_to_page(url, navigate)
            if not page:
                return ExtractionResult(
                    success=False,
                    error="Failed to navigate to URL",
                )

            # Select and run extraction strategy
            strategy = self._select_strategy(url)
            logger.info(
                f"Extracting {census_year} census data using {strategy.get_strategy_name()} strategy"
            )

            data = await strategy.extract(page, census_year)

            return ExtractionResult(
                success=True,
                person=data.get("person", {}),
                page_data=data.get("page_data", {}),
                extended=data.get("extended", {}),
                raw=data.get("raw", {}),
            )

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return ExtractionResult(
                success=False,
                error=str(e),
            )

    async def extract_household(
        self,
        url: str,
        census_year: int,
        *,
        navigate: bool = True,
    ) -> HouseholdResult:
        """Extract household members from FamilySearch URL.

        Args:
            url: FamilySearch URL (ARK format)
            census_year: Census year for context
            navigate: Whether to navigate to the URL (default True)

        Returns:
            HouseholdResult with member data
        """
        try:
            # Ensure connected
            if not await self.connect():
                return HouseholdResult(
                    success=False,
                    error="Failed to connect to browser",
                )

            # Navigate to URL
            page = await self._navigate_to_page(url, navigate)
            if not page:
                return HouseholdResult(
                    success=False,
                    error="Failed to navigate to URL",
                )

            # Run household extraction
            data = await self._household_strategy.extract(page, census_year)

            return HouseholdResult(
                success=True,
                members=data.get("members", []),
                head_name=data.get("head_name"),
            )

        except Exception as e:
            logger.error(f"Household extraction failed: {e}")
            return HouseholdResult(
                success=False,
                error=str(e),
            )

    async def check_login(self) -> bool:
        """Check if logged into FamilySearch.

        Returns:
            True if logged in
        """
        if not await self.connect():
            return False

        return await self._browser.check_login_status()

    async def _navigate_to_page(self, url: str, navigate: bool) -> Page | None:
        """Navigate to URL and return page.

        Args:
            url: URL to navigate to
            navigate: Whether to actually navigate

        Returns:
            Page object or None
        """
        if navigate:
            return await self._browser.navigate_to(
                url,
                wait_for_selector="h1",
            )
        else:
            return await self._browser.get_familysearch_page()

    def _select_strategy(self, url: str):
        """Select extraction strategy based on URL pattern.

        Args:
            url: FamilySearch URL

        Returns:
            Appropriate extraction strategy
        """
        # Detail/image view: /ark:/61903/3:1:
        if "/ark:/61903/3:1:" in url:
            return self._detail_strategy

        # Person record: /ark:/61903/1:1:
        if "/ark:/61903/1:1:" in url:
            return self._person_strategy

        # Default to detail strategy
        logger.warning(f"Unknown URL pattern, using detail strategy: {url}")
        return self._detail_strategy

    @staticmethod
    def transform_for_batch_processing(result: ExtractionResult) -> dict[str, Any]:
        """Transform ExtractionResult to format expected by batch_processing.py.

        This provides backward compatibility with the existing batch processing
        workflow during migration.

        Args:
            result: ExtractionResult from extract()

        Returns:
            Dictionary in legacy batch processing format
        """
        if not result.success:
            return {}

        # Combine person, page_data, and some extended fields
        data = {}

        # Person name
        full_name = result.person.get("full_name", "")
        if not full_name:
            given = result.person.get("given_name", "")
            surname = result.person.get("surname", "")
            full_name = f"{given} {surname}".strip()
        data["personName"] = full_name

        # Event date (census year)
        data["eventDate"] = str(result.page_data.get("census_year", ""))

        # Event place (construct from components)
        place_parts = []
        for field_name in ["township_city", "county", "state"]:
            value = result.page_data.get(field_name)
            if value:
                place_parts.append(value)
        data["eventPlace"] = ", ".join(place_parts)

        # Census-specific fields
        data["enumerationDistrict"] = result.page_data.get("enumeration_district", "")
        data["sheet"] = result.page_data.get("sheet_number", "")
        data["page"] = result.page_data.get("page_number", "")
        data["stamp"] = result.page_data.get("stamp_number", "")
        data["line"] = result.person.get("line_number", "")
        data["dwelling_number"] = result.person.get("dwelling_number", "")
        data["family_number"] = result.person.get("family_number", "")
        data["town_ward"] = result.page_data.get("township_city", "")

        return data
