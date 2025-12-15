"""Base extraction strategy with Playwright-first policy enforcement.

================================================================================
                         EXTRACTION POLICY: PLAYWRIGHT-FIRST
================================================================================

ALL data extraction from FamilySearch pages MUST use Playwright locators.

This policy exists because:
1. Playwright locators are maintainable and readable
2. They integrate with Playwright's auto-waiting and retry mechanisms
3. They are testable and debuggable
4. Duplicate JavaScript extraction caused the 1910 Census bug

--------------------------------------------------------------------------------
IF YOU NEED JavaScript (page.evaluate()):
--------------------------------------------------------------------------------

You MUST:
1. Document the reason in the method docstring
2. Use the _javascript_escape_hatch() method (not raw page.evaluate)
3. Add a JAVASCRIPT_JUSTIFICATION comment block
4. File an issue to investigate Playwright alternatives

Required comment format:
    # JAVASCRIPT_JUSTIFICATION: <why Playwright cannot do this>
    # ALTERNATIVES_TRIED: <what Playwright approaches were attempted>
    # ISSUE_LINK: <GitHub issue number for tracking>

================================================================================
"""

from abc import ABC, abstractmethod
from typing import Any

from loguru import logger
from playwright.async_api import Page


class PlaywrightExtractionStrategy(ABC):
    """Base class for FamilySearch data extraction strategies.

    EXTRACTION POLICY: All extraction MUST use Playwright locators.

    See module docstring for full policy details and escape hatch requirements.

    Subclasses must implement:
        - extract(): Main extraction method using Playwright locators
        - get_strategy_name(): Return strategy identifier for logging

    Example implementation:
        class DetailPageStrategy(PlaywrightExtractionStrategy):
            def get_strategy_name(self) -> str:
                return "detail_page"

            async def extract(self, page: Page, census_year: int) -> dict[str, Any]:
                data = {}
                # Use Playwright locators for all extraction
                name_elem = page.locator('[data-testid="name"]')
                if await name_elem.count() > 0:
                    data["name"] = await name_elem.inner_text()
                return data
    """

    @abstractmethod
    def get_strategy_name(self) -> str:
        """Return identifier for this extraction strategy.

        Used in logging and error messages.

        Returns:
            Strategy name (e.g., "detail_page", "person_page", "household")
        """
        pass

    @abstractmethod
    async def extract(self, page: Page, census_year: int) -> dict[str, Any]:
        """Extract data from page using Playwright locators.

        This method MUST use Playwright locators for all extraction.
        Do NOT use page.evaluate() with JavaScript here.

        Args:
            page: Playwright Page object connected to FamilySearch
            census_year: Census year for year-specific extraction logic

        Returns:
            Dictionary of extracted data with lowercase_underscore keys
        """
        pass

    async def _javascript_escape_hatch(
        self,
        page: Page,
        script: str,
        justification: str,
    ) -> Any:
        """Execute JavaScript when Playwright locators cannot accomplish the task.

        WARNING: This is an escape hatch. Before using this method, you MUST:
        1. Try all Playwright alternatives
        2. Document why Playwright cannot work in the justification parameter
        3. Add JAVASCRIPT_JUSTIFICATION comment block at call site
        4. File an issue to track investigation of Playwright alternatives

        Args:
            page: Playwright Page object
            script: JavaScript code to execute
            justification: REQUIRED explanation of why Playwright cannot do this

        Returns:
            Result of JavaScript execution

        Example:
            # JAVASCRIPT_JUSTIFICATION: SLS API response not in DOM, only in memory
            # ALTERNATIVES_TRIED: route() interception, network events
            # ISSUE_LINK: #456
            result = await self._javascript_escape_hatch(
                page,
                "return window.__slsData",
                "SLS API stores data in memory, not DOM"
            )
        """
        if not justification or len(justification) < 10:
            raise ValueError(
                "JavaScript escape hatch requires meaningful justification. "
                "Explain why Playwright locators cannot accomplish this task."
            )

        logger.warning(
            f"[{self.get_strategy_name()}] JavaScript escape hatch used: {justification}"
        )

        return await page.evaluate(script)

    async def _extract_labeled_value(
        self,
        page: Page,
        label_pattern: str,
        *,
        parent_selector: str | None = None,
    ) -> str | None:
        """Extract value from a label:value pattern using Playwright.

        Common FamilySearch pattern where data appears as "Label: Value".

        Args:
            page: Playwright Page object
            label_pattern: Text pattern to match label (case-insensitive)
            parent_selector: Optional selector to scope the search

        Returns:
            Extracted value or None if not found
        """
        try:
            # FamilySearch uses data-dense elements with labelCss class
            base = page if not parent_selector else page.locator(parent_selector)
            elements = await base.locator('[class*="labelCss"], [data-dense]').all()

            for elem in elements:
                text = await elem.inner_text()
                if ":" in text:
                    colon_idx = text.index(":")
                    label = text[:colon_idx].strip()
                    value = text[colon_idx + 1 :].strip()

                    if label.lower() == label_pattern.lower():
                        return value

            return None

        except Exception as e:
            logger.debug(
                f"[{self.get_strategy_name()}] "
                f"Failed to extract '{label_pattern}': {e}"
            )
            return None

    async def _extract_all_labeled_values(
        self,
        page: Page,
        *,
        parent_selector: str | None = None,
    ) -> dict[str, str]:
        """Extract all label:value pairs from page.

        Args:
            page: Playwright Page object
            parent_selector: Optional selector to scope the search

        Returns:
            Dictionary of {lowercase_underscore_label: value}
        """
        data: dict[str, str] = {}

        try:
            base = page if not parent_selector else page.locator(parent_selector)
            elements = await base.locator('[class*="labelCss"], [data-dense]').all()

            for elem in elements:
                try:
                    text = await elem.inner_text()
                    if ":" in text:
                        colon_idx = text.index(":")
                        label = text[:colon_idx].strip()
                        value = text[colon_idx + 1 :].strip()

                        if label and value and len(label) < 50:
                            key = label.lower().replace(" ", "_")
                            data[key] = value
                except Exception:
                    continue

            return data

        except Exception as e:
            logger.debug(
                f"[{self.get_strategy_name()}] "
                f"Failed to extract labeled values: {e}"
            )
            return data

    async def _extract_table_data(
        self,
        page: Page,
        *,
        table_selector: str = "table",
    ) -> dict[str, str]:
        """Extract data from HTML tables (th/td pattern).

        Args:
            page: Playwright Page object
            table_selector: CSS selector for table(s)

        Returns:
            Dictionary of {lowercase_underscore_header: value}
        """
        data: dict[str, str] = {}

        try:
            rows = await page.locator(f"{table_selector} tr").all()

            for row in rows:
                try:
                    th = row.locator("th").first
                    td = row.locator("td").first

                    if await th.count() > 0 and await td.count() > 0:
                        header = (await th.inner_text()).strip()
                        value = (await td.inner_text()).strip()

                        if header and value and len(header) < 50:
                            key = header.lower().replace(" ", "_")
                            data[key] = value
                except Exception:
                    continue

            return data

        except Exception as e:
            logger.debug(
                f"[{self.get_strategy_name()}] " f"Failed to extract table data: {e}"
            )
            return data
