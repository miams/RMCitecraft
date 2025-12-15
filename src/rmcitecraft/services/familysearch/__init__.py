"""FamilySearch automation and census data extraction.

This package provides a unified interface for extracting census data
from FamilySearch pages using Playwright browser automation.

Primary Classes:
    CensusExtractor: Main entry point for census data extraction
    BrowserConnection: Chrome browser connection management

Example Usage:
    from rmcitecraft.services.familysearch import CensusExtractor

    async with CensusExtractor() as extractor:
        result = await extractor.extract(url, census_year=1910)
        if result.success:
            print(f"Person: {result.person}")
            print(f"Page: {result.page_data}")

================================================================================
                         EXTRACTION POLICY: PLAYWRIGHT-FIRST
================================================================================

All data extraction in this package MUST use Playwright locators.

See extraction/base.py for full policy details and requirements for
any JavaScript escape hatches.

================================================================================
"""

from .browser import BrowserConnection
from .census_extractor import CensusExtractor, ExtractionResult, HouseholdResult
from .field_mapping import (
    EXTENDED_FIELDS,
    FAMILYSEARCH_FIELD_MAP,
    PAGE_FIELDS,
    is_extended_field,
    is_page_field,
    map_familysearch_field,
)
from .year_handler import ExtractionFlags, YearSpecificHandler

__all__ = [
    # Main classes
    "CensusExtractor",
    "BrowserConnection",
    # Result types
    "ExtractionResult",
    "HouseholdResult",
    # Year handling
    "YearSpecificHandler",
    "ExtractionFlags",
    # Field mapping
    "FAMILYSEARCH_FIELD_MAP",
    "EXTENDED_FIELDS",
    "PAGE_FIELDS",
    "map_familysearch_field",
    "is_extended_field",
    "is_page_field",
]
