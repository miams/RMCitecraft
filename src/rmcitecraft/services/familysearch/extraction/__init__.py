"""FamilySearch extraction strategies.

This package contains extraction strategy implementations for different
FamilySearch page types, all following the Playwright-first policy.
"""

from .base import PlaywrightExtractionStrategy
from .detail_page import DetailPageStrategy
from .household import HouseholdStrategy
from .person_page import PersonPageStrategy

__all__ = [
    "PlaywrightExtractionStrategy",
    "DetailPageStrategy",
    "HouseholdStrategy",
    "PersonPageStrategy",
]
