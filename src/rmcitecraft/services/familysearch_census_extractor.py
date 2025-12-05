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

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urlparse

from loguru import logger
from playwright.async_api import Page

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

# Forward declare RMPersonData to avoid circular imports
# The actual class is in census_rmtree_matcher
RMPersonData = Any  # Will be properly typed when passed


def normalize_ark_url(url: str) -> str:
    """Normalize a FamilySearch ARK URL by removing query parameters.

    This ensures URLs like:
    - https://www.familysearch.org/ark:/61903/1:1:6XGL-ZFGQ
    - https://www.familysearch.org/ark:/61903/1:1:6XGL-ZFGQ?lang=en
    - /ark:/61903/1:1:6XGL-ZFGQ (relative URLs)

    Are treated as the same resource.
    """
    if not url:
        return url

    # Handle relative URLs by adding FamilySearch base
    if url.startswith("/ark:"):
        url = f"https://www.familysearch.org{url}"

    parsed = urlparse(url)

    # If still no scheme, add FamilySearch base
    if not parsed.scheme or not parsed.netloc:
        # Extract the ARK path from whatever we have
        ark_match = url if "/ark:/" in url else None
        if ark_match:
            ark_start = url.find("/ark:/")
            ark_path = url[ark_start:].split("?")[0]  # Remove query params
            return f"https://www.familysearch.org{ark_path}"
        return url  # Can't normalize, return as-is

    # Reconstruct URL without query string
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def transform_to_page_index_url(detail_url: str) -> str:
    """Transform a detail page URL to show the full page index.

    Removes the 'personArk' and 'action' query parameters to show all people
    on the census page instead of focusing on one person.

    Example:
        FROM: .../3:1:3QHN-LQH7-YS51?view=index&personArk=%2Fark%3A...&action=view&cc=4464515
        TO:   .../3:1:3QHN-LQH7-YS51?view=index&cc=4464515&lang=en&groupId=

    Args:
        detail_url: The detail page URL with personArk parameter

    Returns:
        URL without personArk/action parameters, showing full page index
    """
    if not detail_url:
        return detail_url

    parsed = urlparse(detail_url)
    query_params = parse_qs(parsed.query)

    # Remove personArk and action parameters
    params_to_remove = ["personArk", "action"]
    filtered_params = {
        k: v[0] if len(v) == 1 else v
        for k, v in query_params.items()
        if k not in params_to_remove
    }

    # Reconstruct the URL with filtered parameters
    new_query = urlencode(filtered_params, doseq=True)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"


def normalize_name(name: str) -> str:
    """Normalize a name for comparison.

    - Converts to lowercase
    - Removes punctuation and extra spaces
    - Handles common variations (Jr, Sr, II, III, etc.)
    """
    if not name:
        return ""
    # Lowercase and remove extra whitespace
    normalized = " ".join(name.lower().split())
    # Remove common punctuation
    normalized = re.sub(r"[.,;:'\"-]", "", normalized)
    # Remove common suffixes for comparison
    suffixes = [" jr", " sr", " ii", " iii", " iv", " v"]
    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()
    return normalized


# Common nicknames and their formal equivalents
# Maps nickname -> list of possible formal names
NICKNAME_MAP: dict[str, list[str]] = {
    # Male names
    "mel": ["melbourne", "melvin", "melville"],
    "chas": ["charles"],
    "charlie": ["charles"],
    "chuck": ["charles"],
    "larry": ["lawrence", "laurence"],
    "les": ["leslie", "lester"],
    "will": ["william", "willard"],
    "bill": ["william"],
    "billy": ["william"],
    "bob": ["robert"],
    "bobby": ["robert"],
    "rob": ["robert"],
    "dick": ["richard"],
    "rick": ["richard", "frederick"],
    "jim": ["james"],
    "jimmy": ["james"],
    "jack": ["john", "jackson"],
    "joe": ["joseph"],
    "joey": ["joseph"],
    "mike": ["michael"],
    "al": ["albert", "alfred", "alan", "allen"],
    "ed": ["edward", "edgar", "edwin"],
    "eddie": ["edward"],
    "ted": ["theodore", "edward"],
    "teddy": ["theodore"],
    "tom": ["thomas"],
    "tommy": ["thomas"],
    "tony": ["anthony"],
    "dan": ["daniel"],
    "danny": ["daniel"],
    "dave": ["david"],
    "ben": ["benjamin"],
    "benny": ["benjamin"],
    "sam": ["samuel"],
    "sammy": ["samuel"],
    "ray": ["raymond"],
    "fred": ["frederick", "alfred"],
    "frankie": ["francis", "franklin"],
    "frank": ["francis", "franklin"],
    "hank": ["henry"],
    "harry": ["harold", "henry", "harrison"],
    "hal": ["harold", "henry"],
    "herb": ["herbert"],
    "gus": ["gustave", "augustus"],
    "leo": ["leonard", "leopold"],
    "lew": ["lewis", "louis"],
    "lou": ["louis", "lewis"],
    "nate": ["nathan", "nathaniel"],
    "nat": ["nathan", "nathaniel"],
    "nick": ["nicholas"],
    "pat": ["patrick", "patricia"],
    "pete": ["peter"],
    "phil": ["philip", "phillip"],
    "ron": ["ronald"],
    "ronnie": ["ronald"],
    "roy": ["leroy"],
    "russ": ["russell"],
    "steve": ["steven", "stephen"],
    "walt": ["walter"],
    "wes": ["wesley"],
    # Female names
    "liz": ["elizabeth"],
    "lizzie": ["elizabeth"],
    "beth": ["elizabeth", "bethany"],
    "betty": ["elizabeth"],
    "bess": ["elizabeth"],
    "kate": ["katherine", "catherine"],
    "katie": ["katherine", "catherine"],
    "kathy": ["katherine", "catherine", "kathleen"],
    "meg": ["margaret"],
    "maggie": ["margaret"],
    "madge": ["margaret"],
    "peg": ["margaret"],
    "peggy": ["margaret"],
    "sue": ["susan", "suzanne"],
    "susie": ["susan", "suzanne"],
    "sally": ["sarah"],
    "sadie": ["sarah"],
    "jenny": ["jennifer", "jane"],
    "jen": ["jennifer"],
    "dot": ["dorothy"],
    "dottie": ["dorothy"],
    "dolly": ["dorothy"],
    "fanny": ["frances"],
    "frannie": ["frances"],
    "ginny": ["virginia"],
    "ginger": ["virginia"],
    "helen": ["helena", "ellen"],
    "nell": ["helen", "eleanor", "ellen"],
    "nellie": ["helen", "eleanor", "ellen"],
    "jo": ["josephine", "joanna", "joan"],
    "josie": ["josephine"],
    "polly": ["mary"],
    "molly": ["mary"],
    "mae": ["mary"],
    "mamie": ["mary"],
    "minnie": ["wilhelmina", "minerva"],
    "nan": ["nancy", "ann"],
    "patsy": ["patricia", "martha"],
    "patty": ["patricia"],
    "tina": ["christina", "christine"],
    "chris": ["christina", "christine", "christopher"],
}

# Build reverse map: formal name -> list of nicknames
FORMAL_TO_NICKNAMES: dict[str, list[str]] = {}
for nick, formals in NICKNAME_MAP.items():
    for formal in formals:
        if formal not in FORMAL_TO_NICKNAMES:
            FORMAL_TO_NICKNAMES[formal] = []
        FORMAL_TO_NICKNAMES[formal].append(nick)


def get_name_variations(name: str) -> set[str]:
    """Get all variations of a name (nicknames and formal versions)."""
    name_lower = name.lower()
    variations = {name_lower}

    # Add nicknames if this is a formal name
    if name_lower in FORMAL_TO_NICKNAMES:
        variations.update(FORMAL_TO_NICKNAMES[name_lower])

    # Add formal names if this is a nickname
    if name_lower in NICKNAME_MAP:
        variations.update(NICKNAME_MAP[name_lower])

    return variations


def names_match_score(name1: str, name2: str) -> tuple[float, str]:
    """Calculate a match score between two names.

    Returns:
        Tuple of (score 0.0-1.0, match_reason)
        Higher scores indicate better matches.
    """
    if not name1 or not name2:
        return 0.0, "empty"

    n1 = normalize_name(name1)
    n2 = normalize_name(name2)

    # Exact match
    if n1 == n2:
        return 1.0, "exact"

    tokens1 = n1.split()
    tokens2 = n2.split()

    if not tokens1 or not tokens2:
        return 0.0, "no_tokens"

    # Extract surname (last token) and given names
    surname1 = tokens1[-1]
    surname2 = tokens2[-1]
    given1 = tokens1[:-1] if len(tokens1) > 1 else []
    given2 = tokens2[:-1] if len(tokens2) > 1 else []

    # Surname must match (or be very similar)
    if surname1 != surname2:
        # Allow minor spelling variations in surname
        if len(surname1) > 3 and len(surname2) > 3:
            if surname1[:3] == surname2[:3] or surname1[-3:] == surname2[-3:]:
                pass  # Close enough
            else:
                return 0.0, "surname_mismatch"
        else:
            return 0.0, "surname_mismatch"

    # Surname only match
    if not given1 or not given2:
        return 0.5, "surname_only"

    # Get first given name
    first1 = given1[0]
    first2 = given2[0]

    # Get variations for both first names
    vars1 = get_name_variations(first1)
    vars2 = get_name_variations(first2)

    # Check for exact first name match
    if first1 == first2:
        # Count matching middle names/initials
        middle_matches = 0
        for g1 in given1[1:]:
            for g2 in given2[1:]:
                if g1 == g2 or (len(g1) == 1 and g2.startswith(g1)) or (len(g2) == 1 and g1.startswith(g2)):
                    middle_matches += 1
                    break
        return 0.95 + (0.05 * min(middle_matches, 1)), "first_name_exact"

    # Check for initial match (first letter)
    if len(first1) == 1 and first2.startswith(first1):
        return 0.85, "initial_match"
    if len(first2) == 1 and first1.startswith(first2):
        return 0.85, "initial_match"

    # Check for nickname/formal name match
    if vars1 & vars2:  # Sets have common elements
        return 0.80, "nickname_match"

    # Check for prefix match (Mel matches Melbourne)
    if first1.startswith(first2) or first2.startswith(first1):
        min_len = min(len(first1), len(first2))
        if min_len >= 3:  # At least 3 chars must match
            return 0.75, "prefix_match"

    # No good first name match
    return 0.3, "surname_match_only"


@dataclass
class MatchCandidate:
    """A potential match between a census person and an RM person."""
    rm_person: Any  # RMPersonData
    score: float
    match_reason: str
    factors: dict[str, Any]  # Additional matching factors


def find_match_candidates(
    census_name: str,
    census_age: int | None,
    census_sex: str | None,
    census_relationship: str | None,
    rm_persons: list[Any],
) -> list[MatchCandidate]:
    """Find all potential RM matches for a census person, ranked by score.

    Uses multiple factors:
    - Name similarity (primary)
    - Age match (if available)
    - Sex match
    - Relationship to head

    Returns:
        List of MatchCandidate sorted by score (highest first)
    """
    candidates = []

    for rm_person in rm_persons:
        rm_name = getattr(rm_person, 'full_name', '')
        rm_sex = getattr(rm_person, 'sex', None)

        # Calculate name score
        name_score, match_reason = names_match_score(census_name, rm_name)

        # Skip if no surname match at all
        if name_score < 0.3:
            continue

        factors = {"name_score": name_score, "name_reason": match_reason}
        total_score = name_score

        # Factor in sex match (if both known)
        if census_sex and rm_sex:
            census_sex_norm = census_sex[0].upper() if census_sex else None
            rm_sex_norm = rm_sex[0].upper() if rm_sex else None
            if census_sex_norm == rm_sex_norm:
                total_score += 0.05  # Small boost for sex match
                factors["sex_match"] = True
            else:
                total_score -= 0.1  # Penalty for sex mismatch
                factors["sex_match"] = False

        # Cap at 1.0
        total_score = min(1.0, total_score)

        candidates.append(MatchCandidate(
            rm_person=rm_person,
            score=total_score,
            match_reason=match_reason,
            factors=factors,
        ))

    # Sort by score (highest first)
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates


def names_match_fuzzy(name1: str, name2: str, threshold: float = 0.75) -> bool:
    """Check if two names match using fuzzy comparison.

    Uses the names_match_score function which supports:
    - Exact match
    - Initial matching (L matches Larry)
    - Nickname matching (Mel matches Melbourne, Chas matches Charles)
    - Prefix matching (Mel is prefix of Melbourne)

    Args:
        name1: First name to compare
        name2: Second name to compare
        threshold: Minimum similarity score (0.0-1.0) for a match

    Returns:
        True if names are considered a match
    """
    score, _ = names_match_score(name1, name2)
    return score >= threshold


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
# Based on actual FamilySearch HTML structure and 1950.yaml schema
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

    # Birthplace (col 13) and parent birthplaces (col 25a/25b - sample only)
    "birthplace": "birthplace",
    "birth place": "birthplace",
    "place": "birthplace",  # FamilySearch sometimes uses "Place" for birthplace
    "father's birth place": "birthplace_father",  # Core field in CensusPerson
    "father's birthplace": "birthplace_father",
    "mother's birth place": "birthplace_mother",  # Core field in CensusPerson
    "mother's birthplace": "birthplace_mother",

    # Naturalization (col 14)
    "naturalized": "naturalized",
    "citizen status flag": "naturalized",

    # Employment status for persons 14+ (cols 15-20)
    "employed": "employment_status",  # Col 15: what doing last week
    "worked last week": "any_work_last_week",  # Col 16: any work at all?
    "seeking work": "looking_for_work",  # Col 17: looking for work?
    "has job": "has_job_not_at_work",  # Col 18: has job but not at work?
    "hours worked": "hours_worked",  # Col 19: hours worked
    "occupation": "occupation",  # Col 20a
    "industry": "industry",  # Col 20b
    "occupation industry": "industry",
    "worker class": "worker_class",  # Col 20c - matches CensusPerson.worker_class
    "class of worker": "worker_class",

    # Event/enumeration information
    "date": "enumeration_date",  # Census enumeration date (e.g., "April 20, 1950")
    "event date": "event_date",
    "event place": "event_place",
    "event place (original)": "event_place_original",

    # Location (page-level) - exact FamilySearch labels
    "state": "state",
    "county": "county",
    "city": "township_city",
    "enumeration district": "enumeration_district",
    "supervisor district field": "supervisor_district",
    "page number": "page_number",
    "source page number": "page_number",
    "line number": "line_number",
    "source line number": "line_number",
    "sheet number": "sheet_number",
    "stamp number": "stamp_number",
    "house number": "house_number",
    "apartment number": "apartment_number",
    "street name": "street_name",

    # Digital folder info
    "digital folder number": "digital_folder_number",
    "image number": "image_number",

    # Household/dwelling info (cols 2-5)
    # NOTE: FamilySearch labels this as "household_id" but it's actually the dwelling number (Col 3)
    "household_id": "dwelling_number",  # Col 3: Serial number of dwelling unit
    "dwelling number": "dwelling_number",
    "lived on farm": "is_dwelling_on_farm",  # Col 4: current dwelling on farm
    "3 plus acres": "farm_3_plus_acres",  # Col 5: 3+ acres
    "agricultural questionnaire": "agricultural_questionnaire",  # Col 6

    # Enumerator info
    "enumerator name": "enumerator_name",

    # Sample line: Residence April 1, 1949 (cols 21-24)
    "same house": "residence_1949_same_house",  # Col 21
    "same house 1949": "residence_1949_same_house",
    "lived on farm last year": "residence_1949_on_farm",  # Col 22
    "on farm 1949": "residence_1949_on_farm",
    "same county": "residence_1949_same_county",  # Col 23
    "same county 1949": "residence_1949_same_county",
    "different location 1949": "residence_1949_different_location",  # Col 24

    # Sample line: Education (cols 26-28)
    "attended school": "school_attendance",  # Col 28
    "highest grade": "highest_grade_attended",  # Col 26
    "grade completed": "highest_grade_attended",
    "completed grade": "completed_grade",  # Col 27

    # Sample line: Employment/income history (cols 29-33)
    "weeks out of work": "weeks_looking_for_work",  # Col 29
    "weeks worked": "weeks_worked_1949",  # Col 30
    "income": "income_wages_1949",  # Col 31
    "income from other sources": "income_other_1949",  # Col 33
    "self employment income": "income_self_employment_1949",  # Col 32

    # Veteran status
    "veteran": "veteran_status",
    "world war i vet": "veteran_ww1",
    "world war ii vet": "veteran_ww2",

    # Other demographics
    "children born count": "children_born",
    "married more than once": "married_more_than_once",
    "years since marital status change": "years_marital_change",
}

# Fields that go to census_person_field (EAV) instead of core fields
# Aligned with 1950.yaml schema column definitions
EXTENDED_FIELDS = {
    # Location/event details
    "event_date",
    "event_place",
    "event_place_original",
    "digital_folder_number",
    "image_number",
    # Note: FamilySearch "household_id" maps to dwelling_number (Col 3)
    "house_number",
    "apartment_number",
    "street_name",
    "dwelling_number",
    "enumerator_name",

    # Dwelling info (cols 4-6)
    "is_dwelling_on_farm",  # Col 4: house on farm?
    "farm_3_plus_acres",  # Col 5: 3+ acres?
    "agricultural_questionnaire",  # Col 6

    # Naturalization (col 14)
    "naturalized",

    # Employment status for persons 14+ (cols 15-20)
    "employment_status",  # Col 15: what doing last week
    "any_work_last_week",  # Col 16: any work at all?
    "looking_for_work",  # Col 17: looking for work?
    "has_job_not_at_work",  # Col 18: has job but not at work?
    "hours_worked",  # Col 19

    # Sample line: Residence April 1, 1949 (cols 21-24)
    "residence_1949_same_house",  # Col 21
    "residence_1949_on_farm",  # Col 22
    "residence_1949_same_county",  # Col 23
    "residence_1949_different_location",  # Col 24

    # Sample line: Education (cols 26-28)
    "highest_grade_attended",  # Col 26
    "completed_grade",  # Col 27
    "school_attendance",  # Col 28

    # Sample line: Employment/income history (cols 29-33)
    "weeks_looking_for_work",  # Col 29
    "weeks_worked_1949",  # Col 30
    "income_wages_1949",  # Col 31
    "income_self_employment_1949",  # Col 32
    "income_other_1949",  # Col 33

    # Veteran status
    "veteran_status",
    "veteran_ww1",
    "veteran_ww2",

    # Other demographics
    "children_born",
    "married_more_than_once",
    "years_marital_change",
}

# Sample line fields (columns 21-33 from 1950 census)
# FamilySearch indexes these with a +2 line offset, so we need to correct this
SAMPLE_LINE_FIELDS = {
    # Residence April 1, 1949 (cols 21-24)
    "residence_1949_same_house",
    "residence_1949_on_farm",
    "residence_1949_same_county",
    "residence_1949_different_location",
    # Education (cols 26-28)
    "highest_grade_attended",
    "completed_grade",
    "school_attendance",
    # Employment/income history (cols 29-33)
    "weeks_looking_for_work",
    "weeks_worked_1949",
    "income_wages_1949",
    "income_self_employment_1949",
    "income_other_1949",
    # Veteran status
    "veteran_status",
    "veteran_ww1",
    "veteran_ww2",
}

# 1950 census sample line offset correction
# FamilySearch indexes sample line data at line+2, so data at line 3 belongs to line 1
# Sample lines are: 1, 6, 11, 16, 21, 26 (every 5th starting at 1)
# Offset lines are: 3, 8, 13, 18, 23, 28
SAMPLE_LINE_OFFSET_MAP = {
    3: 1,
    8: 6,
    13: 11,
    18: 16,
    23: 21,
    28: 26,
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
        rm_persons_filter: list[Any] | None = None,
        is_primary_target: bool = True,
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
            rm_persons_filter: Optional list of RMPersonData. If provided, only extract
                household members who fuzzy-match one of these RootsMagic persons.
                This avoids extracting people not in the RootsMagic database.
            is_primary_target: If True, marks this person as the primary target in census.db.
                Set to False when extracting household members.

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

            # IMPORTANT: Extract family members NOW while we're on the person detail page
            # The family table (Spouses/Children, Parents/Siblings) is only visible here
            # _extract_page_data() will navigate away to the census image view
            family_members_from_table: list[dict] = []
            if extract_household:
                logger.info("Extracting family from person detail page table (before navigating to census image)")
                family_members_from_table = await self._extract_family_from_detail_page(page)
                if family_members_from_table:
                    logger.info(f"Found {len(family_members_from_table)} family members in table")
                else:
                    logger.info("No family members found in table")

            # Extract data from the page (locator waits handle any remaining load)
            # Pass ark_url to ensure we click the correct person in the detail view
            # NOTE: This navigates away from the person page to the census image view
            raw_data = await self._extract_page_data(page, target_ark=ark_url)
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
            person_data.is_target_person = is_primary_target
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
                # If rmtree_person_id not provided but we have rm_persons_filter,
                # try to match the extracted person's name to find the correct RM person
                matched_rm_person_id = rmtree_person_id
                match_method = "url_match"
                match_confidence = 1.0

                if not matched_rm_person_id and rm_persons_filter:
                    # Match primary person's name to RM persons filter
                    _, matched_rm = self._matches_any_rm_person(
                        person_data.full_name, rm_persons_filter
                    )
                    if matched_rm:
                        matched_rm_person_id = getattr(matched_rm, 'person_id', None)
                        match_method = "name_match"
                        match_confidence = 0.9
                        logger.info(
                            f"Primary person matched to RM: {person_data.full_name} -> "
                            f"{matched_rm.full_name} (RIN {matched_rm_person_id})"
                        )

                link = RMTreeLink(
                    census_person_id=person_id,
                    rmtree_person_id=matched_rm_person_id,
                    rmtree_citation_id=rmtree_citation_id,
                    rmtree_database=rmtree_database,
                    match_confidence=match_confidence,
                    match_method=match_method,
                )
                self.repository.insert_rmtree_link(link)

            # Extract household members if requested
            if extract_household:
                # PRIMARY: Use family members already extracted from the person detail page table
                # (extracted earlier before navigating to census image view)
                household_members = family_members_from_table

                # FALLBACK: If no family found in table, try the index approach
                if not household_members:
                    logger.info("No family in table, falling back to index extraction")
                    if rm_persons_filter:
                        # require_names=True forces DOM extraction for RM person matching
                        household_members = await self._extract_household_index(page, require_names=True)
                    else:
                        household_members = await self._extract_household_index(page)

                # Final fallback to raw_data
                if not household_members:
                    logger.warning("All extraction methods failed, using raw_data")
                    household_members = raw_data.get("_household_members", [])

                logger.info(f"Found {len(household_members)} household members on page")

                # Log filtering mode
                if rm_persons_filter:
                    rm_names = [getattr(p, 'full_name', 'Unknown') for p in rm_persons_filter]
                    logger.info(f"Filtering to {len(rm_persons_filter)} RootsMagic persons: {rm_names}")
                else:
                    logger.info("No RM filter - extracting all household members")

                # Get target person info for matching
                target_ark_normalized = normalize_ark_url(ark_url)
                target_name = person_data.full_name or ""

                # Track extraction stats
                extracted_count = 0
                skipped_count = 0

                for member in household_members:
                    member_ark = member.get("ark")
                    member_ark_normalized = normalize_ark_url(member_ark) if member_ark else None
                    member_name = member.get("name", "Unknown")

                    # Determine if this is the target person using ARK or fuzzy name matching
                    is_target = False
                    if member_ark_normalized and member_ark_normalized == target_ark_normalized:
                        is_target = True
                        logger.debug(f"Identified target person by ARK: {member_name}")
                    elif names_match_fuzzy(member_name, target_name):
                        is_target = True
                        logger.debug(f"Identified target person by name match: {member_name} ~ {target_name}")

                    # If this is the target person, we already extracted them above
                    if is_target:
                        result.related_persons.append({
                            "name": member_name,
                            "ark": member_ark_normalized,
                            "person_id": person_id,
                            "is_target_person": True,
                            "already_extracted": True,
                        })
                        extracted_count += 1
                        continue

                    # If RM filter is active, only extract members who match a RootsMagic person
                    if rm_persons_filter:
                        matches_rm, matched_rm = self._matches_any_rm_person(member_name, rm_persons_filter)
                        if not matches_rm:
                            logger.debug(f"Skipping '{member_name}' - no RootsMagic match")
                            skipped_count += 1
                            result.related_persons.append({
                                "name": member_name,
                                "ark": member_ark_normalized,
                                "skipped": True,
                                "reason": "No RootsMagic match",
                            })
                            continue
                        else:
                            rm_name = getattr(matched_rm, 'full_name', 'Unknown')
                            rm_id = getattr(matched_rm, 'person_id', 0)
                            logger.info(f"Extracting '{member_name}' - matches RM person '{rm_name}' (RIN {rm_id})")

                    # If no ARK, create a basic record with available data from the index
                    if not member_ark_normalized:
                        logger.info(f"Saving household member without ARK: {member_name}")

                        # Create a basic CensusPerson with just the name
                        # Parse name into parts
                        name_parts = member_name.split() if member_name else []
                        surname = name_parts[-1] if name_parts else ""
                        given_name = " ".join(name_parts[:-1]) if len(name_parts) > 1 else ""

                        member_person = CensusPerson(
                            page_id=page_id,  # Same page as target person
                            full_name=member_name,
                            given_name=given_name,
                            surname=surname,
                            # Household members share the same Census event as the primary
                            is_target_person=True,
                            # Include any extra data from the index if available
                            relationship_to_head=member.get("relationship", ""),
                            sex=member.get("sex", ""),
                            age=int(member.get("age")) if member.get("age", "").isdigit() else None,
                            birthplace=member.get("birthplace", ""),
                        )

                        # Check if this member matches an RM person (for rmtree_link)
                        matched_rm_person_id = None
                        if rm_persons_filter:
                            _, matched_rm = self._matches_any_rm_person(member_name, rm_persons_filter)
                            if matched_rm:
                                matched_rm_person_id = getattr(matched_rm, 'person_id', None)

                        # Insert the household member
                        try:
                            member_person_id = self.repository.insert_person(member_person)
                            logger.debug(f"Inserted household member {member_name} with person_id={member_person_id}")

                            # Create rmtree_link if we found a matching RM person
                            if matched_rm_person_id and rmtree_citation_id:
                                link = RMTreeLink(
                                    census_person_id=member_person_id,
                                    rmtree_person_id=matched_rm_person_id,
                                    rmtree_citation_id=rmtree_citation_id,
                                    rmtree_database=rmtree_database,
                                    match_method="name_match",
                                    match_confidence=0.8,  # Lower confidence for name-only match
                                )
                                self.repository.insert_rmtree_link(link)
                                logger.info(f"Created rmtree_link for {member_name} -> RM person {matched_rm_person_id}")

                            result.related_persons.append({
                                "name": member_name,
                                "ark": None,
                                "person_id": member_person_id,
                                "rmtree_person_id": matched_rm_person_id,
                                "extracted": True,
                                "note": "Limited data from index (no ARK)",
                            })
                            extracted_count += 1
                        except Exception as e:
                            logger.warning(f"Failed to insert household member {member_name}: {e}")
                            result.related_persons.append({
                                "name": member_name,
                                "ark": None,
                                "error": str(e),
                            })
                        continue

                    # Check if already extracted (use normalized URL for lookup)
                    existing = self.repository.get_person_by_ark(member_ark_normalized)
                    if existing:
                        logger.info(f"Household member already extracted: {member_name}")
                        result.related_persons.append({
                            "name": member_name,
                            "ark": member_ark_normalized,
                            "person_id": existing.person_id,
                            "already_extracted": True,
                        })
                        extracted_count += 1
                    else:
                        # Extract full data for this household member
                        logger.info(f"Extracting household member: {member_name} ({member_ark_normalized})")

                        # Get matched RM person ID if available (for creating rmtree_link)
                        matched_rm_person_id = None
                        if rm_persons_filter:
                            _, matched_rm = self._matches_any_rm_person(member_name, rm_persons_filter)
                            if matched_rm:
                                matched_rm_person_id = getattr(matched_rm, 'person_id', None)

                        member_result = await self.extract_from_ark(
                            member_ark_normalized,  # Use normalized URL
                            census_year,
                            rmtree_citation_id=rmtree_citation_id,  # Same source
                            rmtree_person_id=matched_rm_person_id,  # Matched RM person
                            extract_household=False,  # Don't recurse
                            is_primary_target=True,  # Household members share the same Census event
                        )
                        if member_result.success:
                            result.related_persons.append({
                                "name": member.get("name"),
                                "ark": member_ark_normalized,
                                "person_id": member_result.person_id,
                                "rmtree_person_id": matched_rm_person_id,
                                "extracted": True,
                            })
                            extracted_count += 1
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

                # Log extraction summary
                if rm_persons_filter:
                    logger.info(
                        f"Household extraction complete: {extracted_count} extracted, "
                        f"{skipped_count} skipped (not in RootsMagic)"
                    )

            # Fix sample line offset for 1950 census
            # FamilySearch indexes sample line data at line+2, so we need to move
            # fields from offset lines (3,8,13,18,23,28) to sample lines (1,6,11,16,21,26)
            if census_year == 1950 and extract_household:
                self._fix_sample_line_offset(page_id)

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

        Uses element-based waiting rather than networkidle for faster response:
        - wait_until="domcontentloaded" for initial load
        - Then waits for specific content elements to appear
        """
        try:
            # Use domcontentloaded for faster initial load
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)

            # Wait for FamilySearch content to appear (element-based waiting)
            # Person pages have h1 with the person's name
            try:
                await page.locator("h1").first.wait_for(state="visible", timeout=10000)
            except Exception:
                # Fallback: wait for any main content
                await page.locator('[class*="personSummary"], [class*="recordDetails"]').first.wait_for(
                    state="visible", timeout=5000
                )

            # Verify we arrived at the expected URL (handles redirects)
            if "familysearch.org" not in page.url:
                raise ValueError(f"Unexpected redirect to: {page.url}")

            logger.debug(f"Successfully navigated to: {page.url}")

        except Exception as e:
            logger.warning(f"Navigation issue: {e}, checking current state...")
            # Fallback: just wait for domcontentloaded
            if "familysearch.org" not in page.url:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)

    def _is_valid_extraction_value(self, key: str, value: str) -> bool:
        """
        Validate that an extracted value is not garbage.

        Returns False for values that are:
        - Single character (EXCEPT for certain fields like race, sex codes)
        - Clearly UI text (Census, United States, etc.)
        - Too long to be a valid field value
        """
        if not value:
            return False

        # Single character values - allow for specific fields where single chars are valid
        # Race: W (White), B (Black), etc.
        # Sex: M, F
        # Age: single digit ages (e.g., 3 for a 3-year-old)
        # Line numbers, page numbers, and codes can be single digit/char
        single_char_allowed_fields = {
            "race", "sex", "age", "line_number", "source_line_number", "sheet_letter",
            "marital_status", "citizenship", "veteran", "worker_class",
            "source_page_number", "code_c2", "code_c1", "sheet_number",
            "enumeration_district", "dwelling_number", "family_number"
        }
        if len(value) == 1:
            if key.lower() not in single_char_allowed_fields:
                logger.debug(f"Rejecting single-char value for {key}: '{value}'")
                return False

        # Values that are too long are likely page content, not field values
        if len(value) > 150:
            logger.debug(f"Rejecting too-long value for {key}: '{value[:50]}...'")
            return False

        # Garbage key names that are UI elements or contextual headers, not census data
        # These are captured from data-testid attributes and should be filtered out
        garbage_keys = {
            "manage_indexes_button",
            "save_image_to_source_box",
            "save-image-to-source-box",
            "manage-indexes-button",
            "names_button",
            "names-button",
            "view_original",
            "view-original",
            "attach_to_tree",
            "attach-to-tree",
            # FamilySearch contextual fields that are not actual census data
            "year",  # The "Year: 1949" residence context indicator
            "month",  # Similar context indicator
            "checked_by_date",  # Administrative field
            "checked by date",
        }
        if key.lower() in garbage_keys:
            logger.debug(f"Rejecting garbage key: '{key}'")
            return False

        # Common garbage patterns that indicate we grabbed page content
        garbage_patterns = [
            "census, ",  # Page title like "1950 Census, San Diego"
            "united states",
            "familysearch",
            "view original",
            "save record",
            "save to source",
            "manage indexes",
            "attach to",
            "source information",
            "citing this",
            "back to",
            "click here",
            "loading",
            "please wait",
        ]

        value_lower = value.lower()
        for pattern in garbage_patterns:
            if pattern in value_lower:
                logger.debug(f"Rejecting garbage pattern '{pattern}' in {key}: '{value[:50]}'")
                return False

        return True

    def _matches_any_rm_person(
        self,
        member_name: str,
        rm_persons: list[Any],
    ) -> tuple[bool, Any | None]:
        """Check if a household member name matches any RootsMagic person.

        Uses fuzzy name matching to determine if the FamilySearch household member
        corresponds to someone in the RootsMagic database.

        Args:
            member_name: Name from FamilySearch (e.g., "John W Smith")
            rm_persons: List of RMPersonData objects from RootsMagic

        Returns:
            Tuple of (matches: bool, matched_rm_person or None)
        """
        if not rm_persons or not member_name:
            return False, None

        for rm_person in rm_persons:
            rm_full_name = getattr(rm_person, 'full_name', '')
            rm_given = getattr(rm_person, 'given_name', '')
            rm_surname = getattr(rm_person, 'surname', '')

            # Try full name match first
            if names_match_fuzzy(member_name, rm_full_name):
                logger.debug(f"RM match found: '{member_name}' ~ '{rm_full_name}'")
                return True, rm_person

            # Try given + surname if full name didn't match
            # This handles cases where RootsMagic has "John William" but census has "John W"
            if rm_given and rm_surname:
                combined = f"{rm_given} {rm_surname}"
                if names_match_fuzzy(member_name, combined):
                    logger.debug(f"RM match found (combined): '{member_name}' ~ '{combined}'")
                    return True, rm_person

        return False, None

    async def _extract_page_data(self, page: Page, target_ark: str | None = None) -> dict[str, Any]:
        """
        Extract all census data from the FamilySearch page using Playwright's native features.

        FamilySearch has two page types:
        1. Person ARK page (1:1:xxxx) - Summary with "View Original Document" button
        2. Detail page (3:1:xxxx?view=index) - Full census data with image viewer

        CRITICAL: The person ARK page has LINE NUMBER in table data, but the detail view
        does NOT include Line Number in data-dense elements. We MUST extract table data
        from the person page FIRST, then navigate to detail view for additional fields.

        Args:
            page: Playwright page object
            target_ark: ARK URL of the target person. Used to click the correct person
                        in the detail view when multiple people are listed.
        """
        data: dict[str, Any] = {}
        data["_current_url"] = page.url

        # Step 1: Extract from person ARK page FIRST (has Line Number, Name, etc.)
        # This data is NOT available on the detail view!
        on_person_page = "view=index" not in page.url and "/1:1:" in page.url
        if on_person_page:
            logger.info("On person ARK page, extracting table data FIRST (has Line Number)...")
            await self._extract_person_page_table(page, data)
            logger.debug(f"Person page extraction got: line_number={data.get('line_number')}, name={data.get('name')}")

        # Step 2: Navigate to detail view if we're on a person ARK page
        if on_person_page:
            logger.info("Now navigating to detail view for additional fields...")
            navigated = await self._navigate_to_detail_view(page)
            if navigated:
                logger.info("Successfully navigated to detail view")
            else:
                logger.warning("Could not navigate to detail view, using person page data only")

        # Step 1.5: Check if detail panel is already open
        # Key insight: If URL contains personArk=, the page will auto-open that person's panel
        # We should NEVER click in this case - clicking risks selecting the wrong person
        # We already have good data from the person page table extraction
        has_person_ark = "personArk=" in page.url

        dense_check = page.locator("div[data-dense]")

        if has_person_ark:
            # URL has personArk - wait for panel to load, but NEVER click
            # The panel will load eventually, and we already have person page data
            logger.info("URL contains personArk - waiting for panel to auto-load (no clicking)")
            for i in range(6):  # Wait up to 3 seconds
                await page.wait_for_timeout(500)
                dense_count = await dense_check.count()

                # Check for content indicators (more reliable than just element count)
                # Panel loads between 500-1000ms, content appears with dense elements
                has_content = await page.evaluate("""
                    () => {
                        const text = document.body.textContent || '';
                        // Look for typical census data fields that indicate panel loaded
                        return text.includes('Occupation') ||
                               text.includes('Birthplace') ||
                               text.includes('Essential Information');
                    }
                """)

                if dense_count > 5 and has_content:
                    logger.info(f"Detail panel loaded with {dense_count} fields (content verified)")
                    break
                elif dense_count > 20:
                    # Enough elements even without content check
                    logger.info(f"Detail panel loaded with {dense_count} data fields")
                    break
                else:
                    logger.debug(f"Waiting... {(i+1)*500}ms: {dense_count} fields, content={has_content}")
            else:
                dense_count = await dense_check.count()
                logger.info(f"Panel has {dense_count} fields after waiting - proceeding")
        else:
            # No personArk in URL - need to click to open panel
            dense_count = await dense_check.count()
            if dense_count > 5:
                logger.info(f"Detail panel already open with {dense_count} data fields")
            else:
                logger.info("Detail panel not open, clicking person row...")
                await self._click_selected_person(page, target_ark)

        # Step 2: Wait for content to load
        await page.wait_for_load_state("domcontentloaded")

        # Give the page a moment to render dynamic content
        # Try multiple FamilySearch-specific selectors
        content_selectors = [
            '[data-testid="record-details"]',
            '[data-testid="indexing-panel"]',
            '[class*="recordData"]',
            '[class*="indexData"]',
            '[class*="detailPanel"]',
            '[class*="recordDetail"]',
            '[class*="PersonDetails"]',
            'section[class*="details"]',
            'div[class*="sidebar"]',
            'table',
        ]

        found_content = False
        for selector in content_selectors:
            try:
                elem = page.locator(selector).first
                if await elem.count() > 0:
                    await elem.wait_for(state="visible", timeout=5000)
                    logger.debug(f"Found content element with selector: {selector}")
                    found_content = True
                    break
            except Exception:
                continue

        if not found_content:
            logger.debug("No specific detail elements found, dumping page structure for debugging...")
            # Log the page body structure for debugging
            try:
                body = page.locator("body")
                body_html = await body.inner_html()
                # Log just the first 2000 chars to understand structure
                logger.debug(f"Page body preview: {body_html[:2000]}...")
            except Exception as e:
                logger.debug(f"Could not dump page body: {e}")

        # Step 3: Extract data using Playwright's native locators
        logger.info("Extracting census data using Playwright locators...")

        # === PRIMARY: EXTRACT FROM div[data-dense] ELEMENTS ===
        # After clicking a person in the index, the detail panel shows
        # census data in div[data-dense] elements with "Label: Value" format
        try:
            dense_elements = page.locator("div[data-dense]")
            dense_count = await dense_elements.count()
            logger.debug(f"Found {dense_count} data-dense elements")

            for i in range(dense_count):
                try:
                    elem = dense_elements.nth(i)
                    text = (await elem.inner_text()).strip()
                    # Parse "Label: Value" pattern
                    if ":" in text and len(text) < 200:
                        parts = text.split(":", 1)
                        if len(parts) == 2:
                            label = parts[0].strip()
                            value = parts[1].strip()
                            # Skip garbage labels (buttons, headings, etc.)
                            if (label and value and
                                len(label) < 50 and
                                not label.lower().startswith(("http", "click", "save", "names", "manage"))):
                                key = label.lower().replace(" ", "_")
                                # Validate value before storing
                                if key not in data and self._is_valid_extraction_value(key, value):
                                    data[key] = value
                                    data[f"_label_{key}"] = label
                                    logger.debug(f"Extracted from data-dense: {label} = {value[:50] if len(value) > 50 else value}")
                except Exception as e:
                    logger.debug(f"Error extracting data-dense element {i}: {e}")
        except Exception as e:
            logger.debug(f"data-dense extraction failed: {e}")

        # === EXTRACT FROM PERSON ARK PAGE (th/td table format) ===
        # Look for table rows with label in th and value in td
        try:
            table_rows = page.locator("table tr")
            row_count = await table_rows.count()
            logger.debug(f"Found {row_count} table rows")

            for i in range(row_count):
                row = table_rows.nth(i)
                th = row.locator("th").first
                td = row.locator("td").first

                if await th.count() > 0 and await td.count() > 0:
                    try:
                        label = (await th.inner_text()).strip()
                        # Try to get value from strong tag first, then plain td
                        strong = td.locator("strong")
                        if await strong.count() > 0:
                            value = (await strong.first.inner_text()).strip()
                        else:
                            value = (await td.inner_text()).strip()

                        if label and len(label) < 50:
                            key = label.lower().replace(" ", "_")
                            # Validate value before storing
                            if key not in data and self._is_valid_extraction_value(key, value):
                                data[key] = value
                                data[f"_label_{key}"] = label
                                logger.debug(f"Extracted from table: {label} = {value[:50]}...")
                    except Exception as e:
                        logger.debug(f"Error extracting table row {i}: {e}")
        except Exception as e:
            logger.debug(f"Table extraction failed: {e}")

        # === EXTRACT FROM DETAIL PAGE (right panel with selected person) ===
        # The detail page shows person info in a right-side panel
        # Look for elements that contain "Label: Value" patterns

        # Try to find the selected/highlighted person's panel
        panel_selectors = [
            '[class*="detailPanel"]',
            '[class*="selectedPerson"]',
            '[class*="recordDetails"]',
            '[class*="indexDetails"]',
            '[role="complementary"]',
        ]

        for selector in panel_selectors:
            panel = page.locator(selector).first
            if await panel.count() > 0:
                logger.debug(f"Found panel with selector: {selector}")
                try:
                    panel_text = await panel.inner_text()
                    # Parse the panel text for label:value pairs
                    lines = panel_text.split("\n")
                    for line in lines:
                        line = line.strip()
                        if ":" in line and len(line) < 150:
                            parts = line.split(":", 1)
                            if len(parts) == 2:
                                label = parts[0].strip()
                                value = parts[1].strip()
                                # Skip if label looks like a URL, timestamp, or garbage
                                if (label and
                                    len(label) < 50 and
                                    not label.startswith("http") and
                                    not any(x in label.lower() for x in ["button", "click", "save", "names", "information"])):
                                    key = label.lower().replace(" ", "_")
                                    # Validate value before storing
                                    if key not in data and self._is_valid_extraction_value(key, value):
                                        data[key] = value
                                        data[f"_label_{key}"] = label
                                        logger.debug(f"Extracted from panel: {label} = {value[:50]}...")
                except Exception as e:
                    logger.debug(f"Panel extraction error for {selector}: {e}")
                break

        # === EXTRACT FROM DT/DD PAIRS (definition lists) ===
        # FamilySearch often uses definition lists for field:value pairs
        try:
            dt_elements = page.locator("dt")
            dt_count = await dt_elements.count()
            logger.debug(f"Found {dt_count} dt elements")

            for i in range(dt_count):
                try:
                    dt = dt_elements.nth(i)
                    label_text = (await dt.inner_text()).strip()
                    # Find the following dd element
                    dd = dt.locator("xpath=following-sibling::dd[1]")
                    if await dd.count() > 0:
                        value_text = (await dd.inner_text()).strip()
                        if label_text and len(label_text) < 50:
                            key = label_text.lower().replace(" ", "_")
                            # Validate value before storing
                            if key not in data and self._is_valid_extraction_value(key, value_text):
                                data[key] = value_text
                                data[f"_label_{key}"] = label_text
                                logger.debug(f"Extracted from dt/dd: {label_text} = {value_text}")
                except Exception as e:
                    logger.debug(f"Error extracting dt/dd {i}: {e}")
        except Exception as e:
            logger.debug(f"dt/dd extraction failed: {e}")

        # === EXTRACT FROM DATA-TESTID ATTRIBUTES ===
        # FamilySearch React UI often uses data-testid for testing
        try:
            testid_elements = page.locator("[data-testid]")
            testid_count = await testid_elements.count()
            logger.debug(f"Found {testid_count} data-testid elements")

            for i in range(min(testid_count, 100)):  # Limit to avoid too many
                try:
                    elem = testid_elements.nth(i)
                    testid = await elem.get_attribute("data-testid")
                    if testid and any(
                        x in testid.lower()
                        for x in ["name", "age", "sex", "race", "birth", "relation", "occupation"]
                    ):
                        text = (await elem.inner_text()).strip()
                        if text and len(text) < 100:
                            key = testid.lower().replace("-", "_")
                            if key not in data and self._is_valid_extraction_value(key, text):
                                data[key] = text
                                logger.debug(f"Extracted from data-testid: {testid} = {text}")
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"data-testid extraction failed: {e}")

        # === EXTRACT FROM VISIBLE TEXT PATTERNS ===
        # Parse page text for "Label: Value" patterns in any div/span
        try:
            text_containers = page.locator("div, span, p, li")
            container_count = await text_containers.count()
            logger.debug(f"Found {container_count} text container elements")

            # Common census field labels to look for
            field_patterns = {
                "Name:": "name",
                "Age:": "age",
                "Sex:": "sex",
                "Race:": "race",
                "Birthplace:": "birthplace",
                "Occupation:": "occupation",
                "Relationship to Head:": "relationship_to_head",
                "Relationship to head of household:": "relationship_to_head",
                "Marital Status:": "marital_status",
                "State:": "state",
                "County:": "county",
                "Enumeration District:": "enumeration_district",
                "Line Number:": "line_number",
                "Page Number:": "page_number",
                "Sheet Number:": "sheet_number",
            }

            for i in range(min(container_count, 200)):
                try:
                    elem = text_containers.nth(i)
                    text = (await elem.inner_text()).strip()
                    if len(text) > 5 and len(text) < 150:
                        for label, key in field_patterns.items():
                            if label in text and key not in data:
                                # Extract value after the label
                                parts = text.split(label, 1)
                                if len(parts) == 2:
                                    value = parts[1].strip().split("\n")[0].strip()
                                    if self._is_valid_extraction_value(key, value):
                                        data[key] = value
                                        data[f"_label_{key}"] = label.rstrip(":")
                                        logger.debug(f"Extracted from text pattern: {label} {value}")
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Text pattern extraction failed: {e}")

        # === EXTRACT FROM SPAN LABEL/VALUE PAIRS ===
        # Some FamilySearch pages use span.label + span.value pattern
        try:
            label_spans = page.locator("span.label, span[class*='label']")
            span_count = await label_spans.count()
            logger.debug(f"Found {span_count} label spans")

            for i in range(span_count):
                try:
                    span = label_spans.nth(i)
                    label_text = (await span.inner_text()).strip().rstrip(":")
                    # Find next sibling value span
                    parent = span.locator("xpath=..")
                    if await parent.count() > 0:
                        parent_text = await parent.inner_text()
                        if ":" in parent_text:
                            parts = parent_text.split(":", 1)
                            if len(parts) == 2:
                                value_text = parts[1].strip().split("\n")[0]
                                if label_text and len(label_text) < 50:
                                    key = label_text.lower().replace(" ", "_")
                                    # Validate value before storing
                                    if key not in data and self._is_valid_extraction_value(key, value_text):
                                        data[key] = value_text
                                        data[f"_label_{key}"] = label_text
                                        logger.debug(f"Extracted from label span: {label_text} = {value_text}")
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Label span extraction failed: {e}")

        # === EXTRACT PERSON NAME FROM HIGHLIGHTED ROW ===
        # On the detail page, the target person is often highlighted
        try:
            # Look for highlighted/selected row in the person list
            highlighted_selectors = [
                '[class*="selected"]',
                '[class*="highlight"]',
                '[aria-selected="true"]',
                'tr[class*="active"]',
            ]

            for selector in highlighted_selectors:
                highlighted = page.locator(selector).first
                if await highlighted.count() > 0:
                    text = await highlighted.inner_text()
                    # First line is usually the name
                    name_candidate = text.split("\n")[0].strip()
                    # Validate using our helper
                    if "name" not in data and self._is_valid_extraction_value("name", name_candidate):
                        data["name"] = name_candidate
                        logger.debug(f"Extracted name from highlighted: {name_candidate}")
                        break
        except Exception as e:
            logger.debug(f"Highlighted row extraction failed: {e}")

        # === EXTRACT FROM ARIA LABELS ===
        # Some elements have aria-label with the full field info
        try:
            aria_elements = page.locator("[aria-label]")
            count = await aria_elements.count()
            for i in range(min(count, 50)):  # Limit to avoid too many
                elem = aria_elements.nth(i)
                try:
                    aria_label = await elem.get_attribute("aria-label")
                    if aria_label and ":" in aria_label:
                        parts = aria_label.split(":", 1)
                        label = parts[0].strip()
                        value = parts[1].strip()
                        if label and len(label) < 50:
                            key = label.lower().replace(" ", "_")
                            # Validate value before storing
                            if key not in data and self._is_valid_extraction_value(key, value):
                                data[key] = value
                                data[f"_label_{key}"] = label
                                logger.debug(f"Extracted from aria-label: {label} = {value}")
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Aria-label extraction failed: {e}")

        # === EXTRACT HOUSEHOLD MEMBERS ===
        household_members = []
        try:
            # Look for links to other person records
            person_links = page.locator('a[href*="/ark:/61903/1:1:"]')
            link_count = await person_links.count()
            logger.debug(f"Found {link_count} person ARK links")

            seen_names = set()
            for i in range(link_count):
                link = person_links.nth(i)
                try:
                    name = (await link.inner_text()).strip()
                    href = await link.get_attribute("href")
                    # Skip if not a valid person name
                    if (
                        name
                        and len(name) > 2
                        and name not in seen_names
                        and name[0].isupper()
                        and not any(x in name.lower() for x in ["view", "click", "census", "document"])
                    ):
                        seen_names.add(name)
                        household_members.append({
                            "name": name,
                            "ark": href,
                        })
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Household member extraction failed: {e}")

        data["_household_members"] = household_members

        # Log extraction summary with VALUES for debugging
        extracted_keys = [k for k in data if not k.startswith("_")]
        logger.info(f"Extracted {len(extracted_keys)} fields: {extracted_keys}")

        # DEBUG: Log actual values to diagnose extraction issues
        for key in extracted_keys:
            value = data[key]
            # Truncate long values for readability
            value_str = str(value)[:100] if len(str(value)) > 100 else str(value)
            logger.debug(f"  {key}: '{value_str}'")

        return data

    async def _click_selected_person(self, page: Page, target_ark: str | None = None) -> bool:
        """Click on the target person in the index to open their detail panel.

        On the FamilySearch detail view page (view=index), the page shows:
        - Left: Census image
        - Right: Index panel (may be collapsed)

        The "NAMES" button must be clicked first to expand the index list.
        Then clicking a name opens the person's detail panel with all data.

        Args:
            page: Playwright page object
            target_ark: ARK URL of the person to click. If provided, will find and click
                        the specific person. If None, clicks the first person.

        Returns:
            True if a person was clicked, False otherwise.
        """
        try:
            # Wait a moment for the page to load
            await page.wait_for_timeout(500)

            # Step 0: Close any InfoSheet panel that may be blocking clicks
            # The InfoSheet panel intercepts pointer events, causing 30s timeouts
            await self._close_infosheet_panel(page)

            # Step 1: Click the NAMES button to expand the index panel
            names_button_selectors = [
                '[data-testid="names-button"]',
                'button:has-text("NAMES")',
                '[class*="names"] button',
                'button[aria-label*="names" i]',
            ]

            names_clicked = False
            for btn_selector in names_button_selectors:
                try:
                    btn = page.locator(btn_selector).first
                    if await btn.count() > 0:
                        logger.info(f"Clicking NAMES button to expand index: {btn_selector}")
                        await btn.click(timeout=3000)
                        names_clicked = True
                        # Wait for person links to appear after clicking NAMES
                        try:
                            await page.locator('a[href*="/ark:/61903/1:1:"]').first.wait_for(
                                state="visible", timeout=3000
                            )
                            logger.info("Person links appeared after clicking NAMES")
                        except Exception:
                            # Fallback to fixed wait if links don't appear
                            logger.debug("Person links not immediately visible, waiting...")
                            await page.wait_for_timeout(1000)
                        break
                except Exception as e:
                    logger.debug(f"NAMES button selector {btn_selector} failed: {e}")
                    continue

            if not names_clicked:
                logger.debug("Could not find or click NAMES button (may already be expanded)")

            # Step 2: If target_ark provided, find and click that specific person
            if target_ark:
                # Extract the ARK ID (e.g., "6JJZ-JB42" from full URL)
                target_ark_id = target_ark.split("/")[-1].split("?")[0]
                logger.info(f"Looking for target person with ARK: {target_ark_id}")

                # Try to find a link or row containing the target ARK
                target_selectors = [
                    f'a[href*="{target_ark_id}"]',
                    f'div[role="button"]:has(a[href*="{target_ark_id}"])',
                ]

                target_found_and_clicked = False
                for selector in target_selectors:
                    try:
                        target_element = page.locator(selector).first
                        if await target_element.count() > 0:
                            name = await target_element.inner_text(timeout=2000)
                            name_clean = name.split('\n')[0].strip() if name else "Unknown"
                            logger.info(f"Found target person: {name_clean} (ARK: {target_ark_id})")

                            try:
                                await target_element.click(timeout=5000, force=True)
                                target_found_and_clicked = True
                            except Exception as click_err:
                                logger.debug(f"Force click failed, trying JS click: {click_err}")
                                try:
                                    await target_element.evaluate("el => el.click()")
                                    target_found_and_clicked = True
                                except Exception as js_err:
                                    logger.warning(f"JS click also failed: {js_err}")
                                    continue

                            # Wait for detail panel to load
                            await page.wait_for_timeout(1500)
                            dense_count = await page.locator("div[data-dense]").count()
                            if dense_count > 5:
                                logger.info(f"Detail panel loaded for target person ({dense_count} fields)")
                                return True
                            else:
                                # Even if dense_count is low, we clicked the target - trust it
                                logger.info(f"Clicked target person, detail panel has {dense_count} fields (waiting more...)")
                                await page.wait_for_timeout(1500)  # Extra wait
                                dense_count = await page.locator("div[data-dense]").count()
                                logger.info(f"After extra wait: {dense_count} fields")
                                return True  # Trust the click - don't fall back to wrong person
                    except Exception as e:
                        logger.debug(f"Target selector {selector} failed: {e}")
                        continue

                if target_found_and_clicked:
                    # We clicked the target, don't fall back even if panel didn't load as expected
                    return True

                logger.warning(f"Could not find target person {target_ark_id}, falling back to first person")

            # Step 3: Fallback - click first person in the expanded index
            person_selectors = [
                # Primary selector: clickable person rows with role="button"
                'div[role="button"][interactable]',
                # Fallback: rows with itemselected attribute (current selection)
                'div[role="button"][itemselected]',
                # Fallback: any div with data-testid that looks like a name
                'div[data-testid]:not([data-testid*="button"]):not([data-testid*="icon"])[role="button"]',
                # General person ARK links in the index area
                'a[href*="/ark:/61903/1:1:"]',
            ]

            for selector in person_selectors:
                try:
                    elements = page.locator(selector)
                    count = await elements.count()
                    logger.debug(f"Found {count} elements with selector: {selector}")
                    if count > 0:
                        # Click the first element (the first/selected person)
                        element = elements.first
                        name = await element.inner_text(timeout=2000)
                        # Clean up the name (may have multiple lines)
                        name_clean = name.split('\n')[0].strip() if name else "Unknown"
                        logger.info(f"Clicking on person row: {name_clean}")

                        # Use force=True to bypass overlay checks and short timeout
                        # The InfoSheet panel may still intercept, but force bypasses it
                        try:
                            await element.click(timeout=5000, force=True)
                        except Exception as click_err:
                            logger.debug(f"Force click failed, trying JS click: {click_err}")
                            # Fallback to JavaScript click which bypasses all checks
                            await element.evaluate("el => el.click()")

                        # Wait for the detail panel to load
                        # The detail panel contains div[data-dense] elements with "Label: Value" data
                        panel_indicators = [
                            'div[data-dense]',  # Primary: data fields appear in data-dense divs
                            '[data-testid="fullName"]',  # Person's full name link
                            '[data-testid="edit-essential-information-icon"]',  # Edit icon
                            '[class*="PersonDetails"]',
                            'h2:has-text("Essential Information")',
                        ]

                        for indicator in panel_indicators:
                            try:
                                await page.locator(indicator).first.wait_for(
                                    state="visible", timeout=3000
                                )
                                logger.info(f"Detail panel loaded (found: {indicator})")
                                return True
                            except Exception:
                                continue

                        # Even if no specific panel found, the click might have worked
                        logger.debug("Clicked person but no specific panel indicator found")
                        await page.wait_for_timeout(1000)
                        return True
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue

            logger.warning("Could not find person to click in index")
            return False

        except Exception as e:
            logger.warning(f"Error clicking selected person: {e}")
            return False

    async def _close_infosheet_panel(self, page: Page) -> None:
        """Close any open InfoSheet panel that may block clicks.

        The InfoSheet Panels portal intercepts pointer events and causes
        30-second timeouts when trying to click on person rows.
        """
        try:
            # Check if InfoSheet panel is open
            infosheet = page.locator('[data-portal="InfoSheet Panels"]')
            if await infosheet.count() == 0:
                return

            # Try multiple methods to close the panel
            close_selectors = [
                # Close button within the panel
                '[data-portal="InfoSheet Panels"] button[aria-label*="close" i]',
                '[data-portal="InfoSheet Panels"] button[aria-label*="dismiss" i]',
                '[data-portal="InfoSheet Panels"] [data-testid*="close"]',
                # X button
                '[data-portal="InfoSheet Panels"] button:has(svg)',
            ]

            for selector in close_selectors:
                try:
                    close_btn = page.locator(selector).first
                    if await close_btn.count() > 0:
                        logger.debug(f"Closing InfoSheet panel with: {selector}")
                        await close_btn.click(timeout=2000, force=True)
                        await page.wait_for_timeout(300)
                        return
                except Exception:
                    continue

            # If no close button found, try clicking outside the panel
            # or pressing Escape to dismiss it
            try:
                logger.debug("Pressing Escape to close InfoSheet panel")
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(300)
            except Exception:
                pass

            # As a last resort, try to hide the panel via JavaScript
            try:
                await page.evaluate("""
                    const panel = document.querySelector('[data-portal="InfoSheet Panels"]');
                    if (panel) {
                        panel.style.display = 'none';
                        panel.style.pointerEvents = 'none';
                    }
                """)
                logger.debug("Hid InfoSheet panel via JavaScript")
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"Error closing InfoSheet panel: {e}")

    async def _extract_person_page_table(self, page: Page, data: dict[str, Any]) -> None:
        """Extract data from person ARK page table (th/td pairs).

        CRITICAL: This extracts Line Number and Name which are NOT available
        on the detail view. Must be called BEFORE navigating to detail view.

        The person ARK page has a table with fields like:
        - Name: R Lynn Ijams
        - Line Number: 12
        - Age: 49
        - Relationship to Head of Household: Head
        - etc.
        """
        try:
            table_rows = page.locator("table tr")
            row_count = await table_rows.count()
            logger.debug(f"Person page: Found {row_count} table rows")

            for i in range(row_count):
                row = table_rows.nth(i)
                th = row.locator("th").first
                td = row.locator("td").first

                if await th.count() > 0 and await td.count() > 0:
                    try:
                        label = (await th.inner_text()).strip()
                        # Try to get value from strong tag first, then plain td
                        strong = td.locator("strong")
                        if await strong.count() > 0:
                            value = (await strong.first.inner_text()).strip()
                        else:
                            value = (await td.inner_text()).strip()

                        if label and len(label) < 50 and value:
                            key = label.lower().replace(" ", "_")
                            # Validate value before storing
                            if key not in data and self._is_valid_extraction_value(key, value):
                                data[key] = value
                                data[f"_label_{key}"] = label
                                logger.debug(f"Person page table: {label} = {value[:50] if len(value) > 50 else value}")
                    except Exception as e:
                        logger.debug(f"Error extracting person page row {i}: {e}")
        except Exception as e:
            logger.warning(f"Person page table extraction failed: {e}")

    async def _extract_family_member_arks_from_table(
        self, page: Page
    ) -> list[dict[str, str]]:
        """Extract family member ARKs from person page table.

        The FamilySearch person page displays "Household Members" section
        with relationship labels and linked ARKs. This method extracts:
        - Family member names
        - Their person ARKs (1:1:XXXX format)
        - Their relationship to the current person

        This is the PRIMARY method for identifying household members to extract
        because it provides NAMES (unlike the SLS API which only returns ARKs).

        Returns:
            List of dicts with keys: name, ark, relationship
            e.g., [{'name': 'Mary E James', 'ark': '1:1:XXXX', 'relationship': 'Wife'}]
        """
        family_members: list[dict[str, str]] = []
        seen_arks: set[str] = set()

        try:
            # Look for table rows with links to person ARKs
            # Family members appear as rows like:
            #   <tr><th>Father</th><td><a href="/ark:/61903/1:1:XXXX">William C James</a></td></tr>
            table_rows = page.locator("table tr")
            row_count = await table_rows.count()
            logger.debug(f"Scanning {row_count} table rows for family member ARKs")

            # Relationship labels that indicate family members (on person page)
            relationship_labels = {
                "father", "mother", "wife", "husband", "spouse",
                "son", "daughter", "child", "children",
                "brother", "sister", "sibling",
                "head", "head of household",
                "household members", "other in household",
                "grandfather", "grandmother", "grandson", "granddaughter",
                "father-in-law", "mother-in-law", "son-in-law", "daughter-in-law",
                "uncle", "aunt", "nephew", "niece", "cousin",
                "boarder", "lodger", "servant", "employee",
            }

            for i in range(row_count):
                row = table_rows.nth(i)
                th = row.locator("th").first
                td = row.locator("td").first

                if await th.count() == 0 or await td.count() == 0:
                    continue

                try:
                    label = (await th.inner_text()).strip().lower()

                    # Check if this row has a relationship label
                    is_relationship_row = any(
                        rel in label for rel in relationship_labels
                    )

                    if not is_relationship_row:
                        continue

                    # Look for links within the td cell
                    links = td.locator('a[href*="/ark:/61903/1:1:"]')
                    link_count = await links.count()

                    for j in range(link_count):
                        link = links.nth(j)
                        href = await link.get_attribute("href")
                        name = (await link.inner_text()).strip()

                        if not href or not name:
                            continue

                        # Extract the ARK identifier (1:1:XXXX)
                        ark_match = re.search(r"(1:1:[A-Z0-9-]+)", href)
                        if not ark_match:
                            continue

                        ark = ark_match.group(1)

                        # Skip duplicates
                        if ark in seen_arks:
                            continue
                        seen_arks.add(ark)

                        # Determine relationship from label
                        relationship = label.replace(":", "").strip().title()

                        family_members.append({
                            "name": name,
                            "ark": ark,
                            "relationship": relationship,
                        })
                        logger.debug(
                            f"Found family member: {name} ({relationship}) - {ark}"
                        )

                except Exception as e:
                    logger.debug(f"Error processing table row {i}: {e}")

            # Also look for "Household Members" section links outside tables
            # Some FamilySearch pages have a dedicated household section
            household_section = page.locator(
                'section:has-text("Household"), div:has-text("Household Members")'
            )
            if await household_section.count() > 0:
                section_links = household_section.locator('a[href*="/ark:/61903/1:1:"]')
                section_link_count = await section_links.count()

                for i in range(section_link_count):
                    link = section_links.nth(i)
                    href = await link.get_attribute("href")
                    name = (await link.inner_text()).strip()

                    if not href or not name:
                        continue

                    # Skip navigation/UI links
                    if any(x in name.lower() for x in ["view", "click", "census", "document"]):
                        continue

                    ark_match = re.search(r"(1:1:[A-Z0-9-]+)", href)
                    if not ark_match:
                        continue

                    ark = ark_match.group(1)
                    if ark in seen_arks:
                        continue
                    seen_arks.add(ark)

                    family_members.append({
                        "name": name,
                        "ark": ark,
                        "relationship": "Household Member",
                    })
                    logger.debug(f"Found household member: {name} - {ark}")

            logger.info(
                f"Extracted {len(family_members)} family member ARKs from person page table"
            )
            return family_members

        except Exception as e:
            logger.warning(f"Family member ARK extraction failed: {e}")
            return family_members

    async def _navigate_to_detail_view(self, page: Page) -> bool:
        """Navigate to the detail view page by clicking 'View Original Document' button.

        FamilySearch displays census data on two pages:
        1. Person ARK page (1:1:xxxx) - Summary view with limited data
        2. Detail page (3:1:xxxx?view=index) - Full data with all census fields

        This method clicks the 'View Original Document' button to navigate to the detail page.
        Uses element-based waiting instead of networkidle for faster response.

        Returns:
            True if navigation was successful, False otherwise.
        """
        try:
            # CSS selectors for the "View Original Document" button
            button_selectors = [
                '[data-testid="viewOriginalDocument-Button"]',
                '[data-testid="view-original-document"]',
                'a[href*="view=index"]',
                'button[class*="viewOriginal"]',
            ]

            for selector in button_selectors:
                locator = page.locator(selector)
                if await locator.count() > 0:
                    logger.debug(f"Found button with selector: {selector}")
                    await locator.first.click(timeout=5000)

                    # Wait for detail page content to appear (element-based waiting)
                    # The detail page has labelCss elements with census data
                    try:
                        await page.locator('[class*="labelCss"]').first.wait_for(
                            state="visible", timeout=15000
                        )
                    except Exception:
                        # Fallback: wait for URL change
                        await page.wait_for_url("**/view=index**", timeout=10000)

                    # Verify we're on the detail page (URL contains view=index or 3:1:)
                    if "view=index" in page.url or "3:1:" in page.url:
                        logger.info(f"Successfully navigated to detail view: {page.url}")
                        return True
                    else:
                        logger.debug(f"URL after click: {page.url}")

            logger.warning("Could not find 'View Original Document' button")
            return False

        except Exception as e:
            logger.warning(f"Failed to navigate to detail view: {e}")
            return False

    async def _expand_source_info(self, page: Page) -> None:
        """Click buttons to expand source/original document info if needed.

        Uses Playwright's Locator API for robust button detection with auto-waiting.
        This is a legacy method - primary navigation now uses _navigate_to_detail_view.
        """
        try:
            # Look for expand buttons on the detail page
            expand_buttons = [
                page.locator('[data-testid="expand-source"]'),
                page.locator('.expand-source-btn'),
            ]

            for locator in expand_buttons:
                try:
                    if await locator.count() > 0:
                        await locator.click(timeout=3000)
                        await page.wait_for_load_state("networkidle", timeout=5000)
                        logger.debug("Clicked expand button")
                        break
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"No expand button found or click failed: {e}")

    async def _navigate_to_household_index(self, page: Page) -> bool:
        """Navigate to the full page index by transforming the current URL.

        The detail page URL contains a 'personArk' parameter that focuses on one person.
        Removing this parameter shows ALL people on the census page.

        Example transformation:
            FROM: .../3:1:xxxx?view=index&personArk=%2Fark%3A...&action=view&cc=4464515
            TO:   .../3:1:xxxx?view=index&cc=4464515&lang=en&groupId=

        Uses element-based waiting instead of networkidle for faster response.

        Returns:
            True if navigation was successful, False otherwise.
        """
        try:
            current_url = page.url

            # Check if we're on a detail page with personArk parameter
            if "personArk" not in current_url:
                logger.debug("Already on page index (no personArk in URL)")
                return True

            # Transform URL to remove personArk and action parameters
            index_url = transform_to_page_index_url(current_url)
            logger.info(f"Navigating to page index: {index_url}")

            # Navigate to the transformed URL with domcontentloaded (faster than networkidle)
            await page.goto(index_url, wait_until="domcontentloaded", timeout=15000)

            # Wait for person list elements to appear (element-based waiting)
            # On the index page, people are shown with data-testid or as links
            try:
                # Wait for any person link or data-testid element
                await page.locator('a[href*="/ark:/61903/1:1:"]').first.wait_for(
                    state="visible", timeout=10000
                )
            except Exception:
                # Fallback: wait for any clickable element with role="button"
                try:
                    await page.locator('[data-testid][role="button"]').first.wait_for(
                        state="visible", timeout=5000
                    )
                except Exception:
                    logger.debug("No person elements found, page may still be loading")

            # Verify navigation succeeded
            if "personArk" not in page.url:
                logger.info("Successfully navigated to full page index")
                return True
            else:
                logger.warning("URL still contains personArk after navigation")
                return False

        except Exception as e:
            logger.warning(f"Failed to navigate to household index: {e}")
            return False

    async def _extract_person_arks_via_api(
        self, page: Page, image_ark: str
    ) -> list[str]:
        """
        Extract all person ARKs for a census image by intercepting the SLS API response.

        FamilySearch's internal SLS API returns ALL person ARKs when loading a census
        image page. This is more reliable than trying to click through the UI.

        Args:
            page: Playwright page instance
            image_ark: The census image ARK (format: 3:1:XXXX)

        Returns:
            List of person ARK IDs (format: 1:1:XXXX)
        """
        person_arks: list[str] = []
        captured_data: dict[str, Any] = {}

        async def capture_sls_response(response):
            """Capture the SLS API response."""
            try:
                url = response.url
                if "/sls/image/" in url and response.status == 200:
                    data = await response.json()
                    captured_data["sls"] = data
                    logger.debug(f"Captured SLS API response from {url}")
            except Exception as e:
                logger.debug(f"Failed to capture SLS response: {e}")

        # Register response handler
        page.on("response", capture_sls_response)

        try:
            # Navigate to census page index (this triggers the SLS API call)
            index_url = f"https://www.familysearch.org/ark:/61903/{image_ark}?view=index&lang=en&groupId="
            logger.info(f"Loading census page index to capture SLS API: {index_url}")

            await page.goto(index_url, wait_until="domcontentloaded", timeout=20000)

            # Wait for SLS API response to be captured
            for _ in range(30):  # Wait up to 15 seconds
                if "sls" in captured_data:
                    break
                await page.wait_for_timeout(500)

            # Extract person ARKs from the captured data
            if "sls" in captured_data:
                sls_data = captured_data["sls"]
                if "elements" in sls_data:
                    for elem in sls_data["elements"]:
                        if "subElements" in elem:
                            for sub in elem["subElements"]:
                                ark_id = sub.get("id", "")
                                if ark_id.startswith("1:1:"):
                                    person_arks.append(ark_id)

                logger.info(
                    f"Extracted {len(person_arks)} person ARKs from SLS API"
                )
            else:
                logger.warning("SLS API response was not captured")

        except Exception as e:
            logger.warning(f"Failed to extract ARKs via API: {e}")
        finally:
            # Remove the response handler
            page.remove_listener("response", capture_sls_response)

        return person_arks

    async def _extract_household_index(
        self, page: Page, require_names: bool = False
    ) -> list[dict[str, Any]]:
        """
        Extract household members from the page index.

        This method uses multiple strategies:
        1. API interception (when names not required)
        2. Click-based extraction (clicks each person row to get ARK)
        3. Static DOM extraction (fallback)

        Args:
            page: Playwright page instance
            require_names: If True, skip API extraction and use DOM-based extraction
                          to ensure names are available for matching

        Uses Playwright's Locator API for robust element detection.
        """
        try:
            # Extract the image ARK from the current URL
            # URL format: https://www.familysearch.org/ark:/61903/3:1:XXXX?...
            current_url = page.url
            image_ark_match = re.search(r"/ark:/61903/(3:1:[A-Z0-9-]+)", current_url)

            # Only use API extraction if we don't need names
            # API returns ARKs but not names, so can't be used for RM person matching
            if image_ark_match and not require_names:
                image_ark = image_ark_match.group(1)
                logger.info(f"Extracted image ARK: {image_ark}")

                # PRIMARY STRATEGY: Use API interception to get all person ARKs
                person_arks = await self._extract_person_arks_via_api(page, image_ark)

                if person_arks:
                    logger.info(
                        f"API extraction successful: {len(person_arks)} person ARKs"
                    )
                    # Convert ARK IDs to full URLs and return
                    household = []
                    for ark_id in person_arks:
                        full_ark = f"https://www.familysearch.org/ark:/61903/{ark_id}"
                        household.append({
                            "name": "",  # Name will be extracted when visiting the person page
                            "ark": full_ark,
                        })
                    return household

            # Navigate to index view for DOM-based extraction
            if require_names:
                logger.info("Using DOM-based extraction to get names for RM matching")
            else:
                logger.info("Falling back to DOM-based extraction")
            await self._navigate_to_household_index(page)

            # Wait for household members to be visible
            try:
                await page.locator('[data-testid][role="button"]').first.wait_for(
                    state="visible", timeout=10000
                )
            except Exception:
                logger.debug("No clickable person elements found")

            # CLICK-BASED EXTRACTION: Click each person row to extract ARKs
            # FamilySearch only shows ARK links for the currently selected person
            household = await self._extract_household_by_clicking(page)

            if household:
                logger.info(f"Click-based extraction: {len(household)} household members with ARKs")
                return household

            # FALLBACK: Static DOM extraction (may miss ARKs)
            logger.info("Falling back to static DOM extraction")
            household = await page.evaluate("""
                () => {
                    const members = [];
                    const seen = new Set();

                    // Try anchor elements with ARK links (most reliable)
                    const arkLinks = document.querySelectorAll('a[href*="/ark:/61903/1:1:"]');
                    for (const link of arkLinks) {
                        const ark = link.href;
                        const name = link.textContent.trim();
                        if (name && name.length > 2 && !seen.has(ark)) {
                            seen.add(ark);
                            members.push({ name, ark });
                        }
                    }

                    // Also collect names from data-testid elements (even without ARKs)
                    const personElements = document.querySelectorAll('[data-testid][role="button"]');
                    for (const elem of personElements) {
                        const name = elem.getAttribute('data-testid');
                        if (!name || name.includes('-button') || name.includes('Button') ||
                            name.includes('-link') || name.length < 3) continue;
                        if (/^[A-Z][a-z]/.test(name) && !seen.has(name)) {
                            seen.add(name);
                            const link = elem.querySelector('a[href*="/ark:/"]');
                            const ark = link ? link.href : null;
                            members.push({ name, ark });
                        }
                    }

                    return members;
                }
            """)

            logger.info(f"Extracted {len(household)} household members from index")
            return household

        except Exception as e:
            logger.warning(f"Failed to extract household index: {e}")
            return []

    async def _extract_family_from_detail_page(self, page: Page) -> list[dict[str, Any]]:
        """
        Extract family members from the person detail page's family table.

        This extracts family members from the "Spouses and Children" or "Parents and Siblings"
        sections on the person detail page. These sections contain direct links to each
        family member's ARK, along with their relationship.

        This approach is cleaner than navigating the full page index because:
        1. It only returns actual family members, not all people on the census page
        2. The ARK links are directly available as href attributes (no clicking needed)
        3. Relationship information (Wife, Daughter, Son, etc.) is included

        Returns:
            List of dicts with 'name', 'ark', and 'relationship' keys
        """
        family_members: list[dict[str, Any]] = []

        try:
            # Make sure we're on a person detail page (1:1: ARK)
            current_url = page.url
            if "/ark:/61903/1:1:" not in current_url:
                logger.warning("Not on a person detail page, cannot extract family")
                return []

            # Click "OPEN ALL" if available to expand family sections
            try:
                open_all_btn = page.locator('button:has-text("OPEN ALL")')
                if await open_all_btn.count() > 0 and await open_all_btn.first.is_visible():
                    await open_all_btn.first.click()
                    await page.wait_for_timeout(1500)
                    logger.debug("Clicked OPEN ALL to expand family sections")
            except Exception as e:
                logger.debug(f"No OPEN ALL button or error clicking: {e}")

            # Get the page title (main person's name) to exclude from results
            page_title = await page.evaluate("document.querySelector('h1')?.textContent?.trim() || ''")

            # Extract family members using JavaScript evaluation
            family_data = await page.evaluate("""
                () => {
                    const familyMembers = [];
                    const seen = new Set();

                    // Find all person ARK links (format: /ark:/61903/1:1:XXXX)
                    const allPersonLinks = document.querySelectorAll('a[href*="/ark:/61903/1:1:"]');

                    allPersonLinks.forEach(link => {
                        const href = link.getAttribute('href');
                        const name = link.textContent?.trim();

                        // Skip empty names or if already seen
                        if (!name || name.length < 2 || seen.has(href)) return;
                        seen.add(href);

                        // Try to find relationship from container
                        const container = link.closest('div, tr, li');
                        let relationship = '';
                        if (container) {
                            const containerText = container.textContent || '';
                            const relMatch = containerText.match(/(Father|Mother|Spouse|Wife|Husband|Son|Daughter|Child|Sibling|Brother|Sister)/i);
                            if (relMatch) {
                                relationship = relMatch[1];
                            }
                        }

                        familyMembers.push({
                            name: name,
                            href: href,
                            relationship: relationship
                        });
                    });

                    return familyMembers;
                }
            """)

            # Process extracted data and filter out the main person
            for member in family_data:
                name = member.get("name", "")
                href = member.get("href", "")
                relationship = member.get("relationship", "")

                # Skip if this is the main person (same name as page title)
                if name == page_title:
                    continue

                # Build full ARK URL
                if href and not href.startswith("http"):
                    ark_url = f"https://www.familysearch.org{href}"
                else:
                    ark_url = href

                family_members.append({
                    "name": name,
                    "ark": ark_url,
                    "relationship": relationship,
                })

            logger.info(f"Extracted {len(family_members)} family members from detail page")
            for fm in family_members:
                logger.debug(f"  - {fm['name']} ({fm.get('relationship', 'unknown')}) -> {fm['ark']}")

            return family_members

        except Exception as e:
            logger.warning(f"Failed to extract family from detail page: {e}")
            return []

    async def _extract_household_by_clicking(self, page: Page) -> list[dict[str, Any]]:
        """
        Extract household members by clicking each person row to reveal their ARK.

        FamilySearch only shows the ARK link for the currently selected person.
        This method re-navigates to the clean index URL between each extraction
        because clicking a person row changes the page state and removes other rows.

        Returns:
            List of dicts with 'name' and 'ark' keys
        """
        household: list[dict[str, Any]] = []
        seen_names: set[str] = set()

        try:
            # Get the clean index URL (without personArk parameter)
            current_url = page.url
            parsed = urlparse(current_url)
            # Remove personArk and action parameters to get clean index URL
            query_params = parse_qs(parsed.query)
            query_params.pop("personArk", None)
            query_params.pop("action", None)
            clean_query = urlencode(query_params, doseq=True)
            clean_index_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{clean_query}"
            logger.debug(f"Clean index URL: {clean_index_url}")

            # First pass: navigate to index and count rows
            await page.goto(clean_index_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            # Click NAMES button to expand index
            names_button = page.locator('[data-testid="names-button"]')
            if await names_button.is_visible():
                await names_button.click()
                await page.wait_for_timeout(1000)

            # Count total person rows
            row_count = await page.locator('div[role="button"][interactable]').count()
            logger.info(f"Found {row_count} person rows to extract")

            if row_count == 0:
                return household

            # Extract each row by re-navigating between extractions
            # This is necessary because clicking a person changes the page state
            for i in range(row_count):
                try:
                    # Re-navigate to clean index (page state changes after each click)
                    if i > 0:
                        await page.goto(
                            clean_index_url, wait_until="domcontentloaded", timeout=30000
                        )
                        await page.wait_for_timeout(1500)

                        # Re-click NAMES button
                        names_button = page.locator('[data-testid="names-button"]')
                        if await names_button.is_visible():
                            await names_button.click()
                            await page.wait_for_timeout(800)

                    # Get the row at index i
                    row = page.locator('div[role="button"][interactable]').nth(i)

                    # Get name from data-testid
                    test_id = await row.get_attribute("data-testid", timeout=2000)
                    if not test_id or not test_id.strip():
                        continue

                    # Clean the name - remove relationship prefixes
                    name = test_id.strip()
                    for prefix in [
                        "Census | Primary",
                        "Census|Primary",
                        "Census | ",
                        "Census|",
                    ]:
                        if name.startswith(prefix):
                            name = name[len(prefix) :].strip()
                            break

                    if not name or len(name) < 2:
                        continue

                    # Skip duplicates
                    if name.lower() in seen_names:
                        continue

                    # Click the row
                    await row.click(timeout=5000)
                    await page.wait_for_timeout(500)

                    # Extract ARK from URL parameter
                    ark_url = None
                    result_url = page.url
                    result_parsed = urlparse(result_url)
                    result_params = parse_qs(result_parsed.query)
                    if "personArk" in result_params:
                        ark_path = unquote(result_params["personArk"][0])
                        ark_url = f"https://www.familysearch.org{ark_path}"

                    household.append({"name": name, "ark": ark_url})
                    seen_names.add(name.lower())

                    if ark_url:
                        logger.debug(f"Extracted [{i}]: {name} -> {ark_url}")
                    else:
                        logger.debug(f"Extracted [{i}]: {name} (no ARK)")

                except Exception as e:
                    logger.debug(f"Error extracting row {i}: {e}")
                    continue

            logger.info(
                f"Click-based extraction complete: {len(household)} persons, "
                f"{sum(1 for h in household if h.get('ark'))} with ARKs"
            )

        except Exception as e:
            logger.warning(f"Click-based extraction failed: {e}")

        return household

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

            # Normalize label - convert underscores back to spaces for lookup
            # since extraction stores keys with underscores but map uses spaces
            label = fs_label.lower().strip().replace("_", " ")

            # Look up mapping
            mapped_field = FAMILYSEARCH_FIELD_MAP.get(label)
            if not mapped_field:
                # Try partial match for fields with parenthetical variations
                # Example: "birth year (estimated)" should match "birth year"
                # Only match if fs_key appears as a complete phrase at start of label
                # to avoid false matches like "year" matching "birth year"
                for fs_key, mapped in FAMILYSEARCH_FIELD_MAP.items():
                    # Check if label starts with fs_key (handles parenthetical additions)
                    # e.g., "birth year (estimated)" starts with "birth year"
                    if label.startswith(fs_key):
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

        # Note: stamp_number is only used for a small percentage of 1950 census forms
        # that didn't use page numbers. FamilySearch provides it separately if available,
        # so we don't automatically copy page_number to stamp_number.

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

    def _fix_sample_line_offset(self, page_id: int) -> int:
        """Fix sample line data offset for 1950 census.

        FamilySearch indexes 1950 census sample line data (columns 21-33) with a +2
        line offset. Sample lines are 1, 6, 11, 16, 21, 26 but the data is stored at
        lines 3, 8, 13, 18, 23, 28.

        This method moves sample line fields from offset lines to the correct
        sample line persons.

        Args:
            page_id: The census page ID to fix

        Returns:
            Number of fields moved
        """
        fields_moved = 0

        try:
            # Get all persons on this page with their line numbers
            persons = self.repository.get_persons_on_page(page_id)
            if not persons:
                return 0

            # Build lookup by line number
            persons_by_line = {p.line_number: p for p in persons if p.line_number}

            for offset_line, sample_line in SAMPLE_LINE_OFFSET_MAP.items():
                # Skip if either person doesn't exist
                if offset_line not in persons_by_line or sample_line not in persons_by_line:
                    continue

                offset_person = persons_by_line[offset_line]
                sample_person = persons_by_line[sample_line]

                # Get sample line fields from the offset person
                offset_fields = self.repository.get_person_field_objects(offset_person.person_id)
                sample_fields_to_move = [
                    f for f in offset_fields
                    if f.field_name in SAMPLE_LINE_FIELDS
                ]

                if not sample_fields_to_move:
                    continue

                logger.debug(
                    f"Moving {len(sample_fields_to_move)} sample line fields from "
                    f"line {offset_line} ({offset_person.full_name}) to "
                    f"line {sample_line} ({sample_person.full_name})"
                )

                # Move each field to the correct sample line person
                for field_obj in sample_fields_to_move:
                    self.repository.move_person_field(
                        field_obj.field_id,
                        sample_person.person_id
                    )
                    fields_moved += 1

            if fields_moved > 0:
                logger.info(
                    f"Fixed sample line offset: moved {fields_moved} fields on page {page_id}"
                )

        except Exception as e:
            logger.warning(f"Error fixing sample line offset for page {page_id}: {e}")

        return fields_moved


# =============================================================================
# Convenience Functions
# =============================================================================


async def extract_census_from_citation(
    ark_url: str,
    census_year: int,
    rmtree_citation_id: int | None = None,
    rmtree_person_id: int | None = None,
    rmtree_database: str = "",
    filter_to_rmtree: bool = True,
) -> ExtractionResult:
    """
    Convenience function to extract census data from a FamilySearch ARK URL.

    When a rmtree_citation_id is provided and filter_to_rmtree is True, only
    household members who match a RootsMagic person on the citation will be
    extracted. This avoids extracting people not in the RootsMagic database.

    Args:
        ark_url: FamilySearch ARK URL
        census_year: Census year (1790-1950)
        rmtree_citation_id: Optional CitationID from RootsMagic
        rmtree_person_id: Optional PersonID/RIN from RootsMagic
        rmtree_database: Path to RootsMagic database
        filter_to_rmtree: If True and citation_id provided, only extract
            household members who match RootsMagic persons. Default True.

    Returns:
        ExtractionResult with extracted data
    """
    extractor = FamilySearchCensusExtractor()

    # If citation ID provided and filtering enabled, get RM persons
    rm_persons_filter = None
    if rmtree_citation_id and filter_to_rmtree:
        try:
            from rmcitecraft.services.census_rmtree_matcher import create_matcher

            matcher = create_matcher()
            rm_persons, event_id, _ = matcher.get_rm_persons_for_citation(rmtree_citation_id)
            if rm_persons:
                rm_persons_filter = rm_persons
                logger.info(
                    f"Will filter to {len(rm_persons)} RootsMagic persons "
                    f"from citation {rmtree_citation_id}"
                )
        except Exception as e:
            logger.warning(f"Could not get RM persons for filtering: {e}")

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
            rm_persons_filter=rm_persons_filter,
        )
        extractor.complete_batch()
        return result

    finally:
        await extractor.disconnect()


def display_extraction_result(result: ExtractionResult) -> None:
    """Print extraction result in a formatted way."""
    if result.success:
        print(f"\n{'='*60}")
        print("Extraction Successful")
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
