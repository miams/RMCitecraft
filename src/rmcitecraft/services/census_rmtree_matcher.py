"""Census to RootsMagic matching service.

This service matches extracted census persons from census.db to RootsMagic
persons who share a census citation. It uses a weighted scoring algorithm
based on multiple factors including name, age, sex, relationship, and position.

Matching Philosophy
===================
The matching operates within a **constrained universe**: only persons who share
the same census citation are candidates for matching. This dramatically reduces
false positives compared to searching the entire database.

The algorithm uses a multi-factor weighted scoring approach:
1. **Name matching** (25%): Fuzzy matching supporting phonetic variants, nicknames,
   spelling variations, initials, and middle-name-as-first-name patterns.
2. **Relationship matching** (25%): Compares census relationship to head with
   RootsMagic witness roles (Wife, Son, Daughter, etc.).
3. **Age matching** (20%): Compares census age against expected age calculated
   from RootsMagic birth year.
4. **Sex matching** (20%): Exact M/F comparison. Higher weight than typical
   because sex is reliably recorded and disambiguates same-name siblings.
5. **Position matching** (10%): Uses census line numbers to compare household
   enumeration order with expected RootsMagic family structure.

Optimal Assignment
==================
Uses the Hungarian algorithm (scipy.optimize.linear_sum_assignment) for globally
optimal 1:1 matching rather than greedy assignment. This prevents suboptimal
matches where greedy selection of high-scoring pairs blocks better overall solutions.

Non-RIN Witnesses
=================
RootsMagic can store census household members as "name-only" witnesses (PersonID=0
in WitnessTable with Given/Surname populated). These are people recorded in the
census who don't have their own RootsMagic person record. The matcher identifies
these and marks census persons as "accounted for but no RIN" when they match
a non-RIN witness.

Family Structure Validation
===========================
Post-match validation checks that matched relationships form a coherent family
structure, flagging inconsistencies like missing spouses or mismatched child counts.

Author: RMCitecraft
Last Updated: 2025-12-09
"""

import contextlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger
from scipy.optimize import linear_sum_assignment

from rmcitecraft.database.census_extraction_db import (
    CensusExtractionRepository,
    RMTreeLink,
    get_census_repository,
)
from rmcitecraft.database.connection import connect_rmtree
from rmcitecraft.services.familysearch_census_extractor import names_match_fuzzy, names_match_score

# =============================================================================
# WEIGHT CONFIGURATION
# =============================================================================
# These weights determine how much each factor contributes to the match score.
# They should sum to 1.0 (100%).
#
# Rationale for weights:
# - Name (25%): Important but can have transcription errors, nicknames, etc.
# - Relationship (25%): Highly reliable when both sources record it correctly.
# - Age (20%): Usually accurate within 1-2 years but can have errors.
# - Sex (20%): Almost always recorded correctly; helps disambiguate siblings.
# - Position (10%): Useful signal but enumeration order can vary.

MATCH_WEIGHTS = {
    "name": 0.25,  # Fuzzy name matching with phonetics/nicknames
    "relationship": 0.25,  # Head, Wife, Son, Daughter - highly reliable
    "age": 0.20,  # Birth year → expected age ±2 years tolerance
    "sex": 0.20,  # M/F exact match - increased weight for disambiguation
    "position": 0.10,  # Census line number / enumeration order
}

# Verify weights sum to 1.0
assert abs(sum(MATCH_WEIGHTS.values()) - 1.0) < 0.001, "Match weights must sum to 1.0"

# =============================================================================
# ROOTSMAGIC ROLE MAPPINGS
# =============================================================================
# RootsMagic stores witness relationships using RoleIDs in the RoleTable.
# These mappings convert Role IDs to normalized relationship strings.

ROLE_TO_RELATIONSHIP = {
    63: "son",
    64: "daughter-in-law",
    65: "daughter",
    66: "wife",
    67: "husband",
    68: "servant",
    69: "mother-in-law",
    70: "mother",
    71: "father",
    72: "grandson",
    73: "granddaughter",
    74: "son-in-law",
    75: "father-in-law",
    76: "nephew",
    77: "brother",
    78: "sister",
    79: "niece",
    80: "boarder",
    81: "lodger",
    82: "roomer",
}

# =============================================================================
# RELATIONSHIP NORMALIZATION
# =============================================================================
# Census records use various spellings and terms for relationships.
# This dictionary normalizes them to standard forms for matching.
#
# Key design decisions:
# - All values are lowercase for case-insensitive comparison
# - Compound terms (step-son, son-in-law) use hyphens
# - Common typos are included (neice → niece)
# - Employment relationships (servant, hired hand) are grouped

RELATIONSHIP_ALIASES = {
    # Head of household variations
    "head": "head",
    "head of household": "head",
    "head of family": "head",
    # Spouse variations
    "wife": "wife",
    "spouse": "wife",  # Generic spouse → wife (adjust based on sex if needed)
    "husband": "husband",
    "partner": "partner",
    # Children variations
    "son": "son",
    "daughter": "daughter",
    "child": "child",
    "adopted son": "son",
    "adopted daughter": "daughter",
    "foster son": "son",
    "foster daughter": "daughter",
    # Step-children (handle various spellings)
    "step-son": "step-son",
    "stepson": "step-son",
    "step son": "step-son",
    "step-daughter": "step-daughter",
    "stepdaughter": "step-daughter",
    "step daughter": "step-daughter",
    "stepchild": "step-child",
    "step-child": "step-child",
    "step child": "step-child",
    # Parents
    "mother": "mother",
    "father": "father",
    "parent": "parent",
    # In-laws
    "mother-in-law": "mother-in-law",
    "father-in-law": "father-in-law",
    "son-in-law": "son-in-law",
    "daughter-in-law": "daughter-in-law",
    "brother-in-law": "brother-in-law",
    "sister-in-law": "sister-in-law",
    # Grandchildren/grandparents
    "grandson": "grandson",
    "granddaughter": "granddaughter",
    "grandchild": "grandchild",
    "grandmother": "grandmother",
    "grandfather": "grandfather",
    "grandparent": "grandparent",
    # Siblings
    "brother": "brother",
    "sister": "sister",
    "sibling": "sibling",
    "half-brother": "half-brother",
    "half brother": "half-brother",
    "half-sister": "half-sister",
    "half sister": "half-sister",
    # Extended family
    "nephew": "nephew",
    "niece": "niece",
    "neice": "niece",  # Common typo
    "uncle": "uncle",
    "aunt": "aunt",
    "cousin": "cousin",
    # Non-family household members
    "boarder": "boarder",
    "lodger": "lodger",
    "roomer": "roomer",
    "tenant": "lodger",
    # Employment relationships
    "servant": "servant",
    "domestic": "servant",
    "hired hand": "servant",
    "hired man": "servant",
    "hired girl": "servant",
    "employee": "servant",
    "laborer": "laborer",
    "farm laborer": "laborer",
    "farm hand": "laborer",
    "housekeeper": "housekeeper",
    "cook": "servant",
    # Other
    "ward": "ward",
    "inmate": "inmate",
    "patient": "patient",
    "visitor": "visitor",
    "guest": "visitor",
    "other": "other",
    "unknown": "unknown",
}

# =============================================================================
# RELATIONSHIP COMPATIBILITY GROUPS
# =============================================================================
# Some relationships are "compatible" even if not exact matches.
# For example, "son" matches "child" with a partial score.

RELATIONSHIP_COMPATIBLE_GROUPS = {
    # Children group - son/daughter can match generic "child"
    "children": {"son", "daughter", "child", "step-son", "step-daughter", "step-child"},
    # Grandchildren group
    "grandchildren": {"grandson", "granddaughter", "grandchild"},
    # Siblings group
    "siblings": {"brother", "sister", "sibling", "half-brother", "half-sister"},
    # Non-family residents - these are often interchangeable in census records
    "residents": {"boarder", "lodger", "roomer", "tenant"},
    # Service workers
    "workers": {"servant", "domestic", "laborer", "housekeeper", "hired hand"},
}


def relationships_compatible(rel1: str, rel2: str) -> tuple[bool, float]:
    """Check if two relationships are compatible for matching.

    Relationships can be:
    - Exact match (score 1.0)
    - Compatible within a group (score 0.8)
    - Incompatible (score 0.0)

    Args:
        rel1: First relationship (normalized lowercase)
        rel2: Second relationship (normalized lowercase)

    Returns:
        Tuple of (is_compatible, score)
    """
    # Exact match
    if rel1 == rel2:
        return True, 1.0

    # Check compatibility groups
    for _group_name, members in RELATIONSHIP_COMPATIBLE_GROUPS.items():
        if rel1 in members and rel2 in members:
            return True, 0.8

    return False, 0.0


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class RMPersonData:
    """RootsMagic person data for matching.

    Represents a person from RootsMagic who is associated with a census event,
    either as the event owner (head of household) or as a witness.

    Attributes:
        person_id: RootsMagic PersonID (RIN). 0 for non-RIN witnesses.
        given_name: First/given name(s)
        surname: Family name/surname
        full_name: Combined given + surname
        sex: "M" for male, "F" for female, "?" for unknown
        birth_year: Year of birth (for age calculation), or None
        relationship: Relationship to head of household (normalized)
        event_id: Census EventID this person is associated with
        alternate_names: List of alternate names from NameTable
        is_non_rin: True if this is a "name-only" witness without a PersonID
    """

    person_id: int  # RIN, or 0 for non-RIN witnesses
    given_name: str
    surname: str
    full_name: str
    sex: str  # "M", "F", or "?"
    birth_year: int | None
    relationship: str  # Normalized relationship to head
    event_id: int
    alternate_names: list[str] = field(default_factory=list)
    is_non_rin: bool = False  # True for witnesses without PersonIDs


@dataclass
class CensusPersonData:
    """Census person data for matching.

    Represents a person extracted from a FamilySearch census record.

    Attributes:
        person_id: census.db person_id (internal ID, not RIN)
        full_name: Full name as recorded on census
        given_name: First/given name(s)
        surname: Family name/surname
        sex: "M" or "F" (normalized from various forms)
        age: Age in years as recorded on census
        relationship: Relationship to head (normalized)
        familysearch_ark: FamilySearch ARK identifier
        line_number: Census line number (1-based enumeration order)
    """

    person_id: int  # census.db internal ID
    full_name: str
    given_name: str
    surname: str
    sex: str  # "M" or "F"
    age: int | None
    relationship: str  # Normalized
    familysearch_ark: str
    line_number: int | None = None  # Census enumeration line number


@dataclass
class MatchCandidate:
    """A potential match between an RM person and a census person.

    Contains the match score and detailed breakdown of how the score
    was calculated across all factors.

    Attributes:
        rm_person: The RootsMagic person
        census_person: The census person
        score: Overall weighted match score (0.0 to 1.0)
        score_breakdown: Individual scores per factor (name, age, etc.)
        match_notes: Human-readable notes about the match
    """

    rm_person: RMPersonData
    census_person: CensusPersonData
    score: float
    score_breakdown: dict[str, float] = field(default_factory=dict)
    match_notes: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        status = " [NO RIN]" if self.rm_person.is_non_rin else ""
        return (
            f"{self.rm_person.full_name} (RIN {self.rm_person.person_id}){status} → "
            f"{self.census_person.full_name} (score: {self.score:.2f})"
        )


@dataclass
class FamilyValidationResult:
    """Result of family structure validation.

    Contains warnings about potential inconsistencies between the
    matched family structure and expected relationships.
    """

    is_valid: bool
    warnings: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.is_valid:
            return "Family structure validation: OK"
        return f"Family structure validation: {len(self.warnings)} warning(s)"


@dataclass
class MatchResult:
    """Result of matching a census citation to RootsMagic persons.

    Contains all matches, unmatched persons on both sides, and
    validation results.

    Attributes:
        citation_id: RootsMagic CitationID
        event_id: RootsMagic EventID for the census
        census_year: Year of the census
        matches: List of matched pairs with scores
        unmatched_rm: RM persons that couldn't be matched
        unmatched_census: Census persons that couldn't be matched
        accounted_no_rin: Census persons matched to non-RIN witnesses
        success_rate: Percentage of RM persons successfully matched
        family_validation: Results of family structure validation
        threshold_used: The threshold that was used for matching
    """

    citation_id: int
    event_id: int
    census_year: int
    matches: list[MatchCandidate]
    unmatched_rm: list[RMPersonData]
    unmatched_census: list[CensusPersonData]
    accounted_no_rin: list[MatchCandidate] = field(default_factory=list)
    success_rate: float = 0.0
    family_validation: FamilyValidationResult | None = None
    threshold_used: float = 0.5

    @property
    def is_complete(self) -> bool:
        """True if all RM persons with RINs were matched."""
        return len([p for p in self.unmatched_rm if not p.is_non_rin]) == 0


@dataclass
class MatchStatistics:
    """Statistics for tracking matching success rates over time.

    Used for dynamic threshold adjustment based on historical performance.
    """

    census_year: int
    total_attempts: int = 0
    successful_matches: int = 0
    failed_matches: int = 0
    avg_confidence: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_attempts == 0:
            return 0.0
        return self.successful_matches / self.total_attempts


# =============================================================================
# MAIN MATCHER CLASS
# =============================================================================


class CensusRMTreeMatcher:
    """Matches census extractions to RootsMagic persons.

    This matcher works within a constrained universe: given a RootsMagic
    census citation, it finds all RM persons who share that citation and
    matches them to census persons extracted from the same FamilySearch page.

    Key features:
    - Multi-factor weighted scoring (name, relationship, age, sex, position)
    - Hungarian algorithm for globally optimal 1:1 matching
    - Non-RIN witness detection ("accounted for but no RIN")
    - Alternate name support from RootsMagic NameTable
    - Family structure validation
    - Auto-calculated contextual thresholds

    Usage:
        matcher = create_matcher()
        result = matcher.match_citation_to_census(citation_id, ark_url)

        for match in result.matches:
            print(f"{match.rm_person.full_name} → {match.census_person.full_name}")

        for person in result.accounted_no_rin:
            print(f"{person.census_person.full_name}: accounted for but no RIN")
    """

    def __init__(
        self,
        rmtree_path: Path,
        icu_extension_path: Path,
        census_repo: CensusExtractionRepository | None = None,
    ):
        """Initialize the matcher.

        Args:
            rmtree_path: Path to RootsMagic database file
            icu_extension_path: Path to ICU extension for RMNOCASE collation
            census_repo: Optional census repository (uses default if not provided)
        """
        self.rmtree_path = rmtree_path
        self.icu_extension_path = icu_extension_path
        self.census_repo = census_repo or get_census_repository()
        self._statistics: dict[int, MatchStatistics] = {}  # By census year

    # =========================================================================
    # ROOTSMAGIC DATA RETRIEVAL
    # =========================================================================

    def get_rm_persons_for_citation(
        self, citation_id: int
    ) -> tuple[list[RMPersonData], list[RMPersonData], int, int]:
        """Get all RootsMagic persons who share a citation.

        This method retrieves:
        1. The event owner (typically head of household)
        2. All witnesses with PersonIDs (family members with RINs)
        3. All witnesses without PersonIDs (non-RIN, name-only entries)

        Non-RIN witnesses are people recorded in the census who appear in
        RootsMagic's WitnessTable but don't have their own PersonTable entry.
        They have names and roles but no RIN to link to.

        Args:
            citation_id: RootsMagic CitationID

        Returns:
            Tuple of:
            - List of RMPersonData with RINs
            - List of RMPersonData without RINs (non-RIN witnesses)
            - EventID
            - Census year
        """
        conn = connect_rmtree(self.rmtree_path, self.icu_extension_path)
        try:
            cursor = conn.cursor()

            # Step 1: Find the census event linked to this citation
            cursor.execute(
                """
                SELECT cl.OwnerID, e.Date
                FROM CitationLinkTable cl
                JOIN EventTable e ON cl.OwnerID = e.EventID
                WHERE cl.CitationID = ?
                  AND cl.OwnerType = 2  -- Event
                  AND e.EventType = 18  -- Census
                LIMIT 1
            """,
                (citation_id,),
            )

            event_row = cursor.fetchone()
            if not event_row:
                logger.warning(f"No census event found for citation {citation_id}")
                return [], [], 0, 0

            event_id = event_row[0]
            date_str = event_row[1] or ""

            # Parse census year from RootsMagic date format (D.+YYYYMMDD...)
            census_year = 0
            if len(date_str) >= 7:
                with contextlib.suppress(ValueError):
                    census_year = int(date_str[3:7])

            persons_with_rin: list[RMPersonData] = []
            persons_no_rin: list[RMPersonData] = []

            # Step 2: Get the event owner (head of household)
            cursor.execute(
                """
                SELECT
                    p.PersonID,
                    n.Given,
                    n.Surname,
                    CASE p.Sex WHEN 0 THEN 'M' WHEN 1 THEN 'F' ELSE '?' END as sex,
                    (SELECT substr(Date, 4, 4)
                     FROM EventTable
                     WHERE OwnerID = p.PersonID AND EventType = 1
                     LIMIT 1) as birth_year
                FROM EventTable e
                JOIN PersonTable p ON e.OwnerID = p.PersonID
                JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
                WHERE e.EventID = ?
            """,
                (event_id,),
            )

            head_row = cursor.fetchone()
            if head_row:
                birth_year = None
                if head_row[4]:
                    with contextlib.suppress(ValueError):
                        birth_year = int(head_row[4])

                # Get alternate names for head
                alt_names = self._get_alternate_names(cursor, head_row[0])

                persons_with_rin.append(
                    RMPersonData(
                        person_id=head_row[0],
                        given_name=head_row[1] or "",
                        surname=head_row[2] or "",
                        full_name=f"{head_row[1] or ''} {head_row[2] or ''}".strip(),
                        sex=head_row[3],
                        birth_year=birth_year,
                        relationship="head",
                        event_id=event_id,
                        alternate_names=alt_names,
                        is_non_rin=False,
                    )
                )

            # Step 3: Get all witnesses WITH PersonIDs (family members with RINs)
            cursor.execute(
                """
                SELECT
                    w.PersonID,
                    n.Given,
                    n.Surname,
                    CASE p.Sex WHEN 0 THEN 'M' WHEN 1 THEN 'F' ELSE '?' END as sex,
                    (SELECT substr(Date, 4, 4)
                     FROM EventTable
                     WHERE OwnerID = w.PersonID AND EventType = 1
                     LIMIT 1) as birth_year,
                    r.RoleName
                FROM WitnessTable w
                JOIN PersonTable p ON w.PersonID = p.PersonID
                JOIN NameTable n ON w.PersonID = n.OwnerID AND n.IsPrimary = 1
                LEFT JOIN RoleTable r ON w.Role = r.RoleID
                WHERE w.EventID = ?
                ORDER BY w.WitnessOrder
            """,
                (event_id,),
            )

            for row in cursor.fetchall():
                birth_year = None
                if row[4]:
                    with contextlib.suppress(ValueError):
                        birth_year = int(row[4])

                # Get alternate names
                alt_names = self._get_alternate_names(cursor, row[0])

                persons_with_rin.append(
                    RMPersonData(
                        person_id=row[0],
                        given_name=row[1] or "",
                        surname=row[2] or "",
                        full_name=f"{row[1] or ''} {row[2] or ''}".strip(),
                        sex=row[3],
                        birth_year=birth_year,
                        relationship=(row[5] or "unknown").lower(),
                        event_id=event_id,
                        alternate_names=alt_names,
                        is_non_rin=False,
                    )
                )

            # Step 4: Get all witnesses WITHOUT PersonIDs (non-RIN, name-only)
            # These are household members recorded in the census who don't have
            # their own RootsMagic person record (e.g., servants, boarders,
            # relatives not being tracked in the genealogy)
            cursor.execute(
                """
                SELECT
                    w.Given,
                    w.Surname,
                    r.RoleName
                FROM WitnessTable w
                LEFT JOIN RoleTable r ON w.Role = r.RoleID
                WHERE w.EventID = ?
                  AND w.PersonID = 0
                  AND (w.Given <> '' OR w.Surname <> '')
                ORDER BY w.WitnessOrder
            """,
                (event_id,),
            )

            for row in cursor.fetchall():
                given = row[0] or ""
                surname = row[1] or ""
                role = (row[2] or "unknown").lower()

                # Handle case where data might be in wrong columns
                # (observed in some databases: Given="0", Surname="ActualName")
                if given == "0" or given == "":
                    given = ""

                full_name = f"{given} {surname}".strip()

                persons_no_rin.append(
                    RMPersonData(
                        person_id=0,  # No RIN
                        given_name=given,
                        surname=surname,
                        full_name=full_name,
                        sex="?",  # Unknown for non-RIN witnesses
                        birth_year=None,
                        relationship=role,
                        event_id=event_id,
                        alternate_names=[],
                        is_non_rin=True,
                    )
                )

            logger.info(
                f"Found {len(persons_with_rin)} RM persons with RINs and "
                f"{len(persons_no_rin)} non-RIN witnesses for citation {citation_id}"
            )
            return persons_with_rin, persons_no_rin, event_id, census_year

        finally:
            conn.close()

    def _get_alternate_names(self, cursor: Any, person_id: int) -> list[str]:
        """Get alternate names for a person from NameTable.

        RootsMagic stores alternate names (AKA, married names, spelling variants)
        in NameTable with IsPrimary=0. Including these improves matching when
        the census record uses a different name variant.

        Args:
            cursor: Database cursor
            person_id: RootsMagic PersonID

        Returns:
            List of alternate full names
        """
        cursor.execute(
            """
            SELECT Given, Surname, NameType
            FROM NameTable
            WHERE OwnerID = ? AND IsPrimary = 0
        """,
            (person_id,),
        )

        alt_names = []
        for row in cursor.fetchall():
            given = row[0] or ""
            surname = row[1] or ""
            full = f"{given} {surname}".strip()
            if full:
                alt_names.append(full)

        return alt_names

    def get_rm_persons_for_source(
        self, source_id: int
    ) -> tuple[list[RMPersonData], list[RMPersonData], int, int]:
        """Get all RootsMagic persons who share a source (via any of its citations).

        This method is useful when you have a SourceID rather than a CitationID.
        Multiple citations can reference the same source.

        Args:
            source_id: RootsMagic SourceID

        Returns:
            Tuple of (persons_with_rin, persons_no_rin, EventID, census_year)
        """
        conn = connect_rmtree(self.rmtree_path, self.icu_extension_path)
        try:
            cursor = conn.cursor()

            # Find all census events linked via citations from this source
            cursor.execute(
                """
                SELECT DISTINCT cl.OwnerID as EventID, e.Date
                FROM CitationTable c
                JOIN CitationLinkTable cl ON c.CitationID = cl.CitationID
                JOIN EventTable e ON cl.OwnerID = e.EventID
                WHERE c.SourceID = ?
                  AND cl.OwnerType = 2  -- Event
                  AND e.EventType = 18  -- Census
            """,
                (source_id,),
            )

            event_rows = cursor.fetchall()
            if not event_rows:
                logger.warning(f"No census events found for source {source_id}")
                return [], [], 0, 0

            # Use the first event for census year
            event_id = event_rows[0][0]
            date_str = event_rows[0][1] or ""

            census_year = 0
            if len(date_str) >= 7:
                with contextlib.suppress(ValueError):
                    census_year = int(date_str[3:7])

            # Collect all unique persons from all census events
            all_event_ids = [row[0] for row in event_rows]
            persons_dict: dict[int, RMPersonData] = {}
            non_rin_persons: list[RMPersonData] = []

            for evt_id in all_event_ids:
                # Get event owner
                cursor.execute(
                    """
                    SELECT
                        p.PersonID,
                        n.Given,
                        n.Surname,
                        CASE p.Sex WHEN 0 THEN 'M' WHEN 1 THEN 'F' ELSE '?' END as sex,
                        (SELECT substr(Date, 4, 4)
                         FROM EventTable
                         WHERE OwnerID = p.PersonID AND EventType = 1
                         LIMIT 1) as birth_year
                    FROM EventTable e
                    JOIN PersonTable p ON e.OwnerID = p.PersonID
                    JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
                    WHERE e.EventID = ?
                """,
                    (evt_id,),
                )

                head_row = cursor.fetchone()
                if head_row and head_row[0] not in persons_dict:
                    birth_year = None
                    if head_row[4]:
                        with contextlib.suppress(ValueError):
                            birth_year = int(head_row[4])

                    alt_names = self._get_alternate_names(cursor, head_row[0])

                    persons_dict[head_row[0]] = RMPersonData(
                        person_id=head_row[0],
                        given_name=head_row[1] or "",
                        surname=head_row[2] or "",
                        full_name=f"{head_row[1] or ''} {head_row[2] or ''}".strip(),
                        sex=head_row[3],
                        birth_year=birth_year,
                        relationship="head",
                        event_id=evt_id,
                        alternate_names=alt_names,
                        is_non_rin=False,
                    )

                # Get witnesses with RINs
                cursor.execute(
                    """
                    SELECT
                        w.PersonID,
                        n.Given,
                        n.Surname,
                        CASE p.Sex WHEN 0 THEN 'M' WHEN 1 THEN 'F' ELSE '?' END as sex,
                        (SELECT substr(Date, 4, 4)
                         FROM EventTable
                         WHERE OwnerID = w.PersonID AND EventType = 1
                         LIMIT 1) as birth_year,
                        r.RoleName
                    FROM WitnessTable w
                    JOIN PersonTable p ON w.PersonID = p.PersonID
                    JOIN NameTable n ON w.PersonID = n.OwnerID AND n.IsPrimary = 1
                    LEFT JOIN RoleTable r ON w.Role = r.RoleID
                    WHERE w.EventID = ?
                    ORDER BY w.WitnessOrder
                """,
                    (evt_id,),
                )

                for row in cursor.fetchall():
                    if row[0] in persons_dict:
                        continue

                    birth_year = None
                    if row[4]:
                        with contextlib.suppress(ValueError):
                            birth_year = int(row[4])

                    alt_names = self._get_alternate_names(cursor, row[0])

                    persons_dict[row[0]] = RMPersonData(
                        person_id=row[0],
                        given_name=row[1] or "",
                        surname=row[2] or "",
                        full_name=f"{row[1] or ''} {row[2] or ''}".strip(),
                        sex=row[3],
                        birth_year=birth_year,
                        relationship=(row[5] or "unknown").lower(),
                        event_id=evt_id,
                        alternate_names=alt_names,
                        is_non_rin=False,
                    )

                # Get non-RIN witnesses
                cursor.execute(
                    """
                    SELECT w.Given, w.Surname, r.RoleName
                    FROM WitnessTable w
                    LEFT JOIN RoleTable r ON w.Role = r.RoleID
                    WHERE w.EventID = ?
                      AND w.PersonID = 0
                      AND (w.Given <> '' OR w.Surname <> '')
                """,
                    (evt_id,),
                )

                for row in cursor.fetchall():
                    given = row[0] or ""
                    surname = row[1] or ""
                    role = (row[2] or "unknown").lower()

                    if given == "0" or given == "":
                        given = ""

                    non_rin_persons.append(
                        RMPersonData(
                            person_id=0,
                            given_name=given,
                            surname=surname,
                            full_name=f"{given} {surname}".strip(),
                            sex="?",
                            birth_year=None,
                            relationship=role,
                            event_id=evt_id,
                            alternate_names=[],
                            is_non_rin=True,
                        )
                    )

            persons = list(persons_dict.values())
            logger.info(
                f"Found {len(persons)} RM persons with RINs and "
                f"{len(non_rin_persons)} non-RIN for source {source_id}"
            )
            return persons, non_rin_persons, event_id, census_year

        finally:
            conn.close()

    # =========================================================================
    # CENSUS DATA RETRIEVAL
    # =========================================================================

    def get_census_persons_for_page(self, page_id: int) -> list[CensusPersonData]:
        """Get all census persons from a specific page.

        Args:
            page_id: census.db page_id

        Returns:
            List of CensusPersonData sorted by line number
        """
        persons = self.census_repo.get_persons_on_page(page_id)

        result = []
        for p in persons:
            # Normalize relationship using our alias dictionary
            rel = (p.relationship_to_head or "").lower().strip()
            rel = RELATIONSHIP_ALIASES.get(rel, rel)

            result.append(
                CensusPersonData(
                    person_id=p.person_id,
                    full_name=p.full_name or "",
                    given_name=p.given_name or "",
                    surname=p.surname or "",
                    sex=(p.sex or "").upper()[:1],  # Normalize to M/F
                    age=p.age,
                    relationship=rel,
                    familysearch_ark=p.familysearch_ark or "",
                    line_number=p.line_number,
                )
            )

        # Sort by line number for position-based matching
        result.sort(key=lambda x: x.line_number or 999)
        return result

    def get_census_persons_by_ark(self, ark_url: str) -> tuple[list[CensusPersonData], int | None]:
        """Get census persons that match a FamilySearch ARK URL.

        Args:
            ark_url: FamilySearch ARK URL (person or page level)

        Returns:
            Tuple of (list of CensusPersonData, page_id or None)
        """
        target = self.census_repo.get_person_by_ark(ark_url)
        if not target:
            # Try partial ARK match
            ark_id = ark_url.split("/")[-1].split("?")[0]
            with self.census_repo._connect() as conn:
                row = conn.execute(
                    "SELECT page_id FROM census_person WHERE familysearch_ark LIKE ?",
                    (f"%{ark_id}%",),
                ).fetchone()
                if row:
                    return self.get_census_persons_for_page(row["page_id"]), row["page_id"]
            return [], None

        return self.get_census_persons_for_page(target.page_id), target.page_id

    # =========================================================================
    # SCORING FUNCTIONS
    # =========================================================================

    def calculate_match_score(
        self,
        rm_person: RMPersonData,
        census_person: CensusPersonData,
        census_year: int,
        head_surname: str = "",
        position_map: dict[int, int] | None = None,
    ) -> tuple[float, dict[str, float], list[str]]:
        """Calculate match score between RM and census person.

        Uses five weighted factors:
        1. Name (25%): Fuzzy matching with phonetics, nicknames, alternate names
        2. Relationship (25%): Exact or compatible relationship matching
        3. Age (20%): Expected age from birth year vs census age
        4. Sex (20%): M/F exact match
        5. Position (10%): Census line number vs expected household position

        Args:
            rm_person: RootsMagic person data
            census_person: Census person data
            census_year: Census year (for age calculation)
            head_surname: Surname of head of household (for spouse matching)
            position_map: Optional mapping of rm_person_id to expected position

        Returns:
            Tuple of (total_score, breakdown_dict, match_notes)
        """
        breakdown = {}
        notes = []

        # =====================================================================
        # Factor 1: NAME MATCH (25%)
        # =====================================================================
        # Uses fuzzy matching that handles:
        # - Phonetic surname variants (Ijams/Iams/Ijames)
        # - Nicknames (William/Bill, Margaret/Peggy)
        # - Spelling variants (Katherine/Catherine)
        # - Initials (W matches William)
        # - Middle name as first name (Guy Harvey matches Harvey)

        name_score = 0.0
        best_name_match = ""

        # Try primary name first
        score, reason = names_match_score(rm_person.full_name, census_person.full_name)
        if score > name_score:
            name_score = score
            best_name_match = f"primary name ({reason})"

        # Try alternate names from RootsMagic
        for alt_name in rm_person.alternate_names:
            alt_score, alt_reason = names_match_score(alt_name, census_person.full_name)
            if alt_score > name_score:
                name_score = alt_score
                best_name_match = f"alternate name '{alt_name}' ({alt_reason})"

        # Special case: Wife surname matching
        # Census records married women under husband's surname, but RootsMagic
        # often stores maiden name. Check if census surname matches head's surname.
        if (
            rm_person.relationship == "wife"
            and head_surname
            and names_match_fuzzy(census_person.surname, head_surname)
        ):
            given_score, given_reason = names_match_score(
                rm_person.given_name, census_person.given_name
            )
            if given_score >= 0.7:
                # Given name matches + husband's surname = strong match
                combined_score = 0.95
                if combined_score > name_score:
                    name_score = combined_score
                    best_name_match = f"wife using husband's surname ({given_reason})"
                    notes.append(
                        f"Wife surname: RM '{rm_person.surname}' → "
                        f"Census '{census_person.surname}' (husband's surname)"
                    )

        if best_name_match:
            notes.append(f"Name match: {best_name_match}")

        breakdown["name"] = name_score * MATCH_WEIGHTS["name"]

        # =====================================================================
        # Factor 2: RELATIONSHIP MATCH (25%)
        # =====================================================================
        # Compares normalized relationships. Supports:
        # - Exact match (1.0)
        # - Compatible group match, e.g., son/daughter/child (0.8)

        rm_rel = RELATIONSHIP_ALIASES.get(rm_person.relationship, rm_person.relationship)
        census_rel = census_person.relationship

        _, rel_score = relationships_compatible(rm_rel, census_rel)

        if rel_score == 1.0:
            notes.append(f"Relationship: exact match ({rm_rel})")
        elif rel_score > 0:
            notes.append(f"Relationship: compatible ({rm_rel} ~ {census_rel})")

        breakdown["relationship"] = rel_score * MATCH_WEIGHTS["relationship"]

        # =====================================================================
        # Factor 3: AGE MATCH (20%)
        # =====================================================================
        # Compares census age against expected age (census_year - birth_year).
        # Scoring: 0 diff=1.0, 1 diff=0.9, 2 diff=0.7, 3-5 diff=0.4

        age_score = 0.0
        if rm_person.birth_year and census_person.age is not None:
            expected_age = census_year - rm_person.birth_year
            age_diff = abs(expected_age - census_person.age)

            if age_diff == 0:
                age_score = 1.0
            elif age_diff == 1:
                age_score = 0.9
            elif age_diff == 2:
                age_score = 0.7
            elif age_diff <= 5:
                age_score = 0.4

            if age_diff <= 2:
                notes.append(
                    f"Age: expected {expected_age}, census {census_person.age} (±{age_diff})"
                )
            elif age_diff <= 5:
                notes.append(
                    f"Age: expected {expected_age}, census {census_person.age} (diff={age_diff})"
                )

        breakdown["age"] = age_score * MATCH_WEIGHTS["age"]

        # =====================================================================
        # Factor 4: SEX MATCH (20%)
        # =====================================================================
        # Simple M/F comparison. Higher weight because sex is reliably recorded
        # and helps disambiguate same-name siblings.

        sex_score = 0.0
        if rm_person.sex and census_person.sex:
            rm_sex = rm_person.sex.upper()[:1]
            census_sex = census_person.sex.upper()[:1]

            if rm_sex == census_sex:
                sex_score = 1.0
            elif rm_sex == "?" or census_sex == "?":
                sex_score = 0.5  # Unknown sex - partial credit
        else:
            sex_score = 0.5  # Missing data - partial credit

        breakdown["sex"] = sex_score * MATCH_WEIGHTS["sex"]

        # =====================================================================
        # Factor 5: POSITION MATCH (10%)
        # =====================================================================
        # Compares census line number against expected household position.
        # Expected order: Head (1), Spouse (2), Children by age, Others.

        position_score = 0.0
        if position_map and rm_person.person_id in position_map and census_person.line_number:
            expected_pos = position_map[rm_person.person_id]
            actual_pos = census_person.line_number
            pos_diff = abs(expected_pos - actual_pos)

            if pos_diff == 0:
                position_score = 1.0
            elif pos_diff == 1:
                position_score = 0.8
            elif pos_diff == 2:
                position_score = 0.6
            elif pos_diff <= 4:
                position_score = 0.3

            if pos_diff <= 2:
                notes.append(f"Position: expected {expected_pos}, actual {actual_pos}")
        else:
            # No position data - give neutral score
            position_score = 0.5

        breakdown["position"] = position_score * MATCH_WEIGHTS["position"]

        # =====================================================================
        # TOTAL SCORE
        # =====================================================================
        total_score = sum(breakdown.values())
        return total_score, breakdown, notes

    def build_position_map(
        self,
        rm_persons: list[RMPersonData],
        census_year: int,
    ) -> dict[int, int]:
        """Build expected position map for RM persons.

        Creates a mapping from person_id to expected census line position
        based on standard household enumeration order:
        1. Head of household
        2. Spouse
        3. Children (oldest to youngest by birth year)
        4. Other relatives
        5. Non-relatives (servants, boarders, etc.)

        Args:
            rm_persons: List of RM persons in the household
            census_year: Census year (for age ordering)

        Returns:
            Dict mapping person_id to expected position (1-based)
        """
        position_map = {}
        position = 1

        # Group by relationship type
        head = None
        spouse = None
        children = []
        relatives = []
        others = []

        for p in rm_persons:
            if p.is_non_rin:
                continue  # Skip non-RIN for position mapping

            rel = p.relationship.lower()

            if rel == "head":
                head = p
            elif rel in ("wife", "husband", "spouse"):
                spouse = p
            elif rel in ("son", "daughter", "child", "step-son", "step-daughter"):
                children.append(p)
            elif rel in (
                "mother",
                "father",
                "mother-in-law",
                "father-in-law",
                "brother",
                "sister",
                "grandson",
                "granddaughter",
                "nephew",
                "niece",
                "aunt",
                "uncle",
                "cousin",
            ):
                relatives.append(p)
            else:
                others.append(p)

        # Position 1: Head
        if head:
            position_map[head.person_id] = position
            position += 1

        # Position 2: Spouse
        if spouse:
            position_map[spouse.person_id] = position
            position += 1

        # Children sorted by birth year (oldest first)
        children.sort(key=lambda p: p.birth_year or 9999)
        for child in children:
            position_map[child.person_id] = position
            position += 1

        # Relatives
        for rel in relatives:
            position_map[rel.person_id] = position
            position += 1

        # Others (servants, boarders, etc.)
        for other in others:
            position_map[other.person_id] = position
            position += 1

        return position_map

    # =========================================================================
    # OPTIMAL MATCHING
    # =========================================================================

    def find_optimal_matches(
        self,
        rm_persons: list[RMPersonData],
        census_persons: list[CensusPersonData],
        census_year: int,
        threshold: float = 0.5,
    ) -> tuple[list[MatchCandidate], list[RMPersonData], list[CensusPersonData]]:
        """Find globally optimal 1:1 matching using Hungarian algorithm.

        The Hungarian algorithm (also known as Kuhn-Munkres) finds the optimal
        assignment that maximizes total match score across all pairs. This is
        better than greedy selection which can produce suboptimal results.

        Example where Hungarian beats greedy:
        - Person A → Census X (0.82), A → Census Y (0.78)
        - Person B → Census Y (0.85)

        Greedy picks A→X (0.82) first, then B→Y (0.85). Total: 1.67
        Hungarian picks A→Y (0.78) and B→... because B→Y was B's only good match.

        Args:
            rm_persons: List of RootsMagic persons (including non-RIN)
            census_persons: List of census persons
            census_year: Census year
            threshold: Minimum score to consider a match

        Returns:
            Tuple of (matches, unmatched_rm, unmatched_census)
        """
        # Separate RIN and non-RIN persons
        rm_with_rin = [p for p in rm_persons if not p.is_non_rin]
        rm_no_rin = [p for p in rm_persons if p.is_non_rin]

        if not rm_with_rin or not census_persons:
            return [], rm_persons, census_persons

        # Extract head's surname for wife matching
        head_surname = ""
        for p in rm_with_rin:
            if p.relationship.lower() == "head":
                head_surname = p.surname
                break

        # Build position map for positional scoring
        position_map = self.build_position_map(rm_with_rin, census_year)

        # Build score matrix for Hungarian algorithm
        # Rows = RM persons, Columns = Census persons
        n_rm = len(rm_with_rin)
        n_census = len(census_persons)

        # Store all candidates for later retrieval
        all_candidates: dict[tuple[int, int], MatchCandidate] = {}

        # Build cost matrix (Hungarian minimizes, so use 1 - score)
        score_matrix = np.zeros((n_rm, n_census))

        for i, rm_person in enumerate(rm_with_rin):
            for j, census_person in enumerate(census_persons):
                score, breakdown, notes = self.calculate_match_score(
                    rm_person, census_person, census_year, head_surname, position_map
                )

                score_matrix[i, j] = score

                # Store candidate for later use
                all_candidates[(i, j)] = MatchCandidate(
                    rm_person=rm_person,
                    census_person=census_person,
                    score=score,
                    score_breakdown=breakdown,
                    match_notes=notes,
                )

        # Apply Hungarian algorithm
        # Convert to cost matrix (maximize score → minimize 1-score)
        cost_matrix = 1 - score_matrix

        try:
            row_ind, col_ind = linear_sum_assignment(cost_matrix)
        except ValueError:
            # Fallback to greedy if Hungarian fails
            logger.warning("Hungarian algorithm failed, falling back to greedy")
            return self._find_matches_greedy(rm_with_rin, census_persons, census_year, threshold)

        # Extract matches above threshold
        matches: list[MatchCandidate] = []
        matched_rm_ids: set[int] = set()
        matched_census_ids: set[int] = set()

        for i, j in zip(row_ind, col_ind, strict=True):
            candidate = all_candidates[(i, j)]

            if candidate.score >= threshold:
                matches.append(candidate)
                matched_rm_ids.add(candidate.rm_person.person_id)
                matched_census_ids.add(candidate.census_person.person_id)

                logger.debug(
                    f"Match: {candidate.rm_person.full_name} → "
                    f"{candidate.census_person.full_name} ({candidate.score:.2f})"
                )

        # Find unmatched
        unmatched_rm = [p for p in rm_with_rin if p.person_id not in matched_rm_ids]
        unmatched_rm.extend(rm_no_rin)  # Add non-RIN to unmatched
        unmatched_census = [p for p in census_persons if p.person_id not in matched_census_ids]

        return matches, unmatched_rm, unmatched_census

    def _find_matches_greedy(
        self,
        rm_persons: list[RMPersonData],
        census_persons: list[CensusPersonData],
        census_year: int,
        threshold: float,
    ) -> tuple[list[MatchCandidate], list[RMPersonData], list[CensusPersonData]]:
        """Fallback greedy matching if Hungarian fails.

        Sorts all candidates by score and greedily assigns highest-scoring pairs.
        """
        head_surname = ""
        for p in rm_persons:
            if p.relationship.lower() == "head":
                head_surname = p.surname
                break

        position_map = self.build_position_map(rm_persons, census_year)

        candidates: list[MatchCandidate] = []

        for rm_person in rm_persons:
            if rm_person.is_non_rin:
                continue
            for census_person in census_persons:
                score, breakdown, notes = self.calculate_match_score(
                    rm_person, census_person, census_year, head_surname, position_map
                )
                if score >= threshold:
                    candidates.append(
                        MatchCandidate(
                            rm_person=rm_person,
                            census_person=census_person,
                            score=score,
                            score_breakdown=breakdown,
                            match_notes=notes,
                        )
                    )

        candidates.sort(key=lambda c: c.score, reverse=True)

        matches: list[MatchCandidate] = []
        matched_rm_ids: set[int] = set()
        matched_census_ids: set[int] = set()

        for candidate in candidates:
            rm_id = candidate.rm_person.person_id
            census_id = candidate.census_person.person_id

            if rm_id not in matched_rm_ids and census_id not in matched_census_ids:
                matches.append(candidate)
                matched_rm_ids.add(rm_id)
                matched_census_ids.add(census_id)

        unmatched_rm = [p for p in rm_persons if p.person_id not in matched_rm_ids]
        unmatched_census = [p for p in census_persons if p.person_id not in matched_census_ids]

        return matches, unmatched_rm, unmatched_census

    def match_non_rin_witnesses(
        self,
        non_rin_persons: list[RMPersonData],
        unmatched_census: list[CensusPersonData],
        census_year: int,
        threshold: float = 0.4,
    ) -> tuple[list[MatchCandidate], list[CensusPersonData]]:
        """Match unmatched census persons to non-RIN witnesses.

        Non-RIN witnesses are household members in WitnessTable without PersonIDs.
        When a census person matches a non-RIN witness, we mark them as
        "accounted for but no RIN" - they exist in both sources but can't be
        linked to a RootsMagic person record.

        Uses a lower threshold (0.4) because non-RIN witnesses have limited data
        (no sex, no birth year) making exact matching harder.

        Args:
            non_rin_persons: List of non-RIN witnesses from RootsMagic
            unmatched_census: Census persons not matched to RIN persons
            census_year: Census year
            threshold: Minimum score (default 0.4, lower than normal)

        Returns:
            Tuple of (accounted_matches, still_unmatched_census)
        """
        if not non_rin_persons or not unmatched_census:
            return [], unmatched_census

        accounted: list[MatchCandidate] = []
        matched_census_ids: set[int] = set()

        # Build candidates
        candidates: list[MatchCandidate] = []

        for nr_person in non_rin_persons:
            for census_person in unmatched_census:
                # Simplified scoring for non-RIN (no birth year, no sex)
                name_score, reason = names_match_score(nr_person.full_name, census_person.full_name)

                # Relationship match
                _, rel_score = relationships_compatible(
                    nr_person.relationship, census_person.relationship
                )

                # Weighted score (simplified: 60% name, 40% relationship)
                total_score = name_score * 0.6 + rel_score * 0.4

                if total_score >= threshold:
                    candidates.append(
                        MatchCandidate(
                            rm_person=nr_person,
                            census_person=census_person,
                            score=total_score,
                            score_breakdown={"name": name_score, "relationship": rel_score},
                            match_notes=[f"Non-RIN match: {reason}"],
                        )
                    )

        # Greedy assignment for non-RIN (simpler, usually fewer candidates)
        candidates.sort(key=lambda c: c.score, reverse=True)
        matched_nr_full_names: set[str] = set()

        for candidate in candidates:
            nr_name = candidate.rm_person.full_name
            census_id = candidate.census_person.person_id

            if nr_name not in matched_nr_full_names and census_id not in matched_census_ids:
                accounted.append(candidate)
                matched_nr_full_names.add(nr_name)
                matched_census_ids.add(census_id)

                logger.info(
                    f"Census person '{candidate.census_person.full_name}' accounted for "
                    f"by non-RIN witness '{nr_name}' (no RIN to link)"
                )

        still_unmatched = [p for p in unmatched_census if p.person_id not in matched_census_ids]
        return accounted, still_unmatched

    # =========================================================================
    # FAMILY STRUCTURE VALIDATION
    # =========================================================================

    def validate_family_structure(self, matches: list[MatchCandidate]) -> FamilyValidationResult:
        """Validate that matched relationships form a coherent family structure.

        Checks for inconsistencies between the matched family structure and
        expected relationships. This helps identify potential matching errors.

        Validations performed:
        1. If RM has a wife, census should have wife/spouse
        2. Child count should roughly match
        3. Sex/relationship consistency (sons should be male, etc.)

        Args:
            matches: List of matched candidates

        Returns:
            FamilyValidationResult with warnings
        """
        warnings = []

        if not matches:
            return FamilyValidationResult(is_valid=True, warnings=[])

        # Collect relationships from both sides
        rm_rels = {m.rm_person.relationship.lower() for m in matches}
        census_rels = {m.census_person.relationship.lower() for m in matches}

        # Check 1: Spouse consistency
        rm_has_spouse = "wife" in rm_rels or "husband" in rm_rels
        census_has_spouse = (
            "wife" in census_rels or "spouse" in census_rels or "husband" in census_rels
        )

        if rm_has_spouse and not census_has_spouse:
            warnings.append(
                "RM has spouse but no spouse found in census matches - "
                "possible missing or mismatched spouse"
            )

        # Check 2: Child count
        rm_children = sum(
            1 for m in matches if m.rm_person.relationship.lower() in ("son", "daughter", "child")
        )
        census_children = sum(
            1
            for m in matches
            if m.census_person.relationship.lower() in ("son", "daughter", "child")
        )

        if abs(rm_children - census_children) > 1:
            warnings.append(
                f"Child count mismatch: RM has {rm_children}, Census has {census_children}"
            )

        # Check 3: Sex/relationship consistency
        for m in matches:
            rm_rel = m.rm_person.relationship.lower()
            rm_sex = m.rm_person.sex.upper()
            census_sex = m.census_person.sex.upper()

            # Sons should be male
            if rm_rel == "son" and rm_sex == "M" and census_sex == "F":
                warnings.append(
                    f"Sex mismatch: '{m.rm_person.full_name}' is RM son (M) but census shows F"
                )

            # Daughters should be female
            if rm_rel == "daughter" and rm_sex == "F" and census_sex == "M":
                warnings.append(
                    f"Sex mismatch: '{m.rm_person.full_name}' is RM daughter (F) but census shows M"
                )

        is_valid = len(warnings) == 0
        return FamilyValidationResult(is_valid=is_valid, warnings=warnings)

    # =========================================================================
    # CONTEXTUAL THRESHOLD
    # =========================================================================

    def calculate_contextual_threshold(
        self,
        rm_count: int,
        census_count: int,
        census_year: int,
    ) -> float:
        """Calculate auto-adjusted threshold based on context.

        The threshold is adjusted based on:
        1. Household size: Larger households need stricter matching
        2. Census year: Earlier censuses have less data (lower threshold)
        3. Historical success rate: If we have good data, be stricter

        Args:
            rm_count: Number of RM persons to match
            census_count: Number of census persons
            census_year: Year of the census

        Returns:
            Adjusted threshold (0.3 to 0.7)
        """
        base = 0.5

        # Adjustment 1: Household size
        # Larger households have more potential for confusion
        max_count = max(rm_count, census_count)
        if max_count > 10:
            base += 0.10  # Large household: stricter
        elif max_count > 6:
            base += 0.05  # Medium household: slightly stricter

        # Adjustment 2: Census year
        # Earlier censuses have less detailed information
        if census_year < 1850:
            base -= 0.15  # Pre-1850: much less data
        elif census_year < 1880:
            base -= 0.05  # 1850-1870: less data (no ED)
        elif census_year >= 1940:
            base += 0.05  # 1940+: very detailed records

        # Adjustment 3: Historical success rate (if available)
        if census_year in self._statistics:
            stats = self._statistics[census_year]
            if stats.total_attempts >= 10:
                if stats.success_rate > 0.9:
                    base += 0.05  # High success: can be stricter
                elif stats.success_rate < 0.6:
                    base -= 0.05  # Low success: be more lenient

        # Clamp to reasonable range
        return max(0.3, min(0.7, base))

    # =========================================================================
    # MAIN MATCHING METHODS
    # =========================================================================

    def match_citation_to_census(
        self,
        citation_id: int,
        ark_url: str | None = None,
        threshold: float | None = None,
        create_links: bool = False,
    ) -> MatchResult | None:
        """Match a RootsMagic citation to extracted census data.

        This is the main entry point for matching. It:
        1. Retrieves all RM persons (with and without RINs) for the citation
        2. Retrieves all census persons for the matching page
        3. Runs optimal matching using Hungarian algorithm
        4. Matches remaining census persons to non-RIN witnesses
        5. Validates family structure
        6. Optionally creates rmtree_link records

        Args:
            citation_id: RootsMagic CitationID
            ark_url: FamilySearch ARK URL (required to find census data)
            threshold: Minimum match score (auto-calculated if None)
            create_links: If True, create rmtree_link records for matches

        Returns:
            MatchResult or None if no census data found
        """
        # Get RM persons (with and without RINs)
        rm_with_rin, rm_no_rin, event_id, census_year = self.get_rm_persons_for_citation(
            citation_id
        )

        if not rm_with_rin:
            logger.warning(f"No RM persons found for citation {citation_id}")
            return None

        logger.info(
            f"Matching {len(rm_with_rin)} RM persons (+{len(rm_no_rin)} non-RIN) "
            f"for {census_year} census"
        )

        # Get census persons
        if not ark_url:
            logger.warning("No ARK URL provided, cannot find census data")
            return None

        census_persons, page_id = self.get_census_persons_by_ark(ark_url)

        if not census_persons:
            logger.warning(f"No census persons found for ARK {ark_url}")
            return None

        logger.info(f"Found {len(census_persons)} census persons to match against")

        # Auto-calculate threshold if not provided
        if threshold is None:
            threshold = self.calculate_contextual_threshold(
                len(rm_with_rin), len(census_persons), census_year
            )
            logger.info(f"Using auto-calculated threshold: {threshold:.2f}")

        # Combine for matching (non-RIN handled separately after)
        all_rm = rm_with_rin + rm_no_rin

        # Find optimal matches for persons with RINs
        matches, unmatched_rm, unmatched_census = self.find_optimal_matches(
            all_rm, census_persons, census_year, threshold
        )

        # Separate unmatched into RIN and non-RIN
        unmatched_rm_with_rin = [p for p in unmatched_rm if not p.is_non_rin]
        unmatched_rm_no_rin = [p for p in unmatched_rm if p.is_non_rin]

        # Match remaining census persons to non-RIN witnesses
        accounted_no_rin, final_unmatched_census = self.match_non_rin_witnesses(
            unmatched_rm_no_rin, unmatched_census, census_year
        )

        # Validate family structure
        family_validation = self.validate_family_structure(matches)

        # Log results
        logger.info(f"=== Matching Results for Citation {citation_id} ===")
        for match in matches:
            logger.info(f"  ✓ {match}")

        for person in accounted_no_rin:
            logger.info(
                f"  ○ {person.census_person.full_name}: accounted for but no RIN "
                f"(matches '{person.rm_person.full_name}')"
            )

        for rm_person in unmatched_rm_with_rin:
            logger.warning(f"  ✗ Unmatched RM: {rm_person.full_name} (RIN {rm_person.person_id})")

        for census_person in final_unmatched_census:
            logger.warning(f"  ✗ Unmatched Census: {census_person.full_name}")

        if not family_validation.is_valid:
            for warning in family_validation.warnings:
                logger.warning(f"  ⚠ {warning}")

        # Create links if requested
        if create_links and matches:
            for match in matches:
                if not match.rm_person.is_non_rin:
                    link = RMTreeLink(
                        census_person_id=match.census_person.person_id,
                        rmtree_person_id=match.rm_person.person_id,
                        rmtree_citation_id=citation_id,
                        rmtree_event_id=event_id,
                        rmtree_database=str(self.rmtree_path),
                        match_confidence=match.score,
                        match_method="hungarian_optimal",
                    )
                    self.census_repo.insert_rmtree_link(link)
                    logger.info(
                        f"Created link: RIN {match.rm_person.person_id} → "
                        f"Census {match.census_person.person_id}"
                    )

        # Calculate success rate (only for RIN persons)
        rm_rin_count = len(rm_with_rin)
        success_rate = len(matches) / rm_rin_count if rm_rin_count else 0.0

        # Update statistics
        self._update_statistics(census_year, matches, rm_with_rin)

        return MatchResult(
            citation_id=citation_id,
            event_id=event_id,
            census_year=census_year,
            matches=matches,
            unmatched_rm=unmatched_rm_with_rin,
            unmatched_census=final_unmatched_census,
            accounted_no_rin=accounted_no_rin,
            success_rate=success_rate,
            family_validation=family_validation,
            threshold_used=threshold,
        )

    def match_census_persons_by_ark(
        self,
        ark_url: str,
        census_year: int,
        threshold: float | None = None,
    ) -> MatchResult | None:
        """Match census persons to RootsMagic by finding citations containing the ARK.

        This method searches RootsMagic for citations that contain the FamilySearch
        ARK URL, then performs matching.

        Args:
            ark_url: FamilySearch ARK URL
            census_year: Census year
            threshold: Minimum match score (auto-calculated if None)

        Returns:
            MatchResult or None if no matching citation found
        """
        ark_id = ark_url.split("/")[-1].split("?")[0] if ark_url else ""
        if not ark_id:
            logger.warning("Invalid ARK URL")
            return None

        logger.info(f"Searching for citations containing ARK: {ark_id}")

        conn = connect_rmtree(self.rmtree_path, self.icu_extension_path)
        try:
            cursor = conn.cursor()

            # Try CitationTable.Footnote first
            cursor.execute(
                """
                SELECT DISTINCT c.CitationID
                FROM CitationTable c
                WHERE c.Footnote LIKE ?
                LIMIT 1
            """,
                (f"%{ark_id}%",),
            )

            row = cursor.fetchone()
            if not row:
                # Try SourceTable.Fields (free-form citations)
                cursor.execute(
                    """
                    SELECT DISTINCT c.CitationID
                    FROM CitationTable c
                    JOIN SourceTable s ON c.SourceID = s.SourceID
                    WHERE s.TemplateID = 0 AND CAST(s.Fields AS TEXT) LIKE ?
                    LIMIT 1
                """,
                    (f"%{ark_id}%",),
                )
                row = cursor.fetchone()

            if not row:
                logger.info(f"No citation found containing ARK {ark_id}")
                return None

            citation_id = row[0]
            logger.info(f"Found citation {citation_id} containing ARK {ark_id}")
        finally:
            conn.close()

        return self.match_citation_to_census(
            citation_id=citation_id,
            ark_url=ark_url,
            threshold=threshold,
            create_links=False,
        )

    def create_links_for_matches(self, match_result: MatchResult) -> int:
        """Create rmtree_link records for all matches in a MatchResult.

        Args:
            match_result: MatchResult containing matches to link

        Returns:
            Number of links created
        """
        created = 0
        for match in match_result.matches:
            if match.rm_person.is_non_rin:
                continue  # Can't create links for non-RIN witnesses

            try:
                link = RMTreeLink(
                    census_person_id=match.census_person.person_id,
                    rmtree_person_id=match.rm_person.person_id,
                    rmtree_citation_id=match_result.citation_id,
                    rmtree_event_id=match_result.event_id,
                    rmtree_database=str(self.rmtree_path),
                    match_confidence=match.score,
                    match_method="hungarian_optimal",
                )
                self.census_repo.insert_rmtree_link(link)
                created += 1
                logger.info(
                    f"Created link: {match.rm_person.full_name} (RIN {match.rm_person.person_id}) → "
                    f"{match.census_person.full_name} (Census ID {match.census_person.person_id})"
                )
            except Exception as e:
                logger.warning(f"Failed to create link for {match.rm_person.full_name}: {e}")

        return created

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def _update_statistics(
        self,
        census_year: int,
        matches: list[MatchCandidate],
        rm_persons: list[RMPersonData],
    ) -> None:
        """Update match statistics for a census year."""
        if census_year not in self._statistics:
            self._statistics[census_year] = MatchStatistics(census_year=census_year)

        stats = self._statistics[census_year]
        rm_with_rin = [p for p in rm_persons if not p.is_non_rin]

        stats.total_attempts += len(rm_with_rin)
        stats.successful_matches += len(matches)
        stats.failed_matches += len(rm_with_rin) - len(matches)

        if matches:
            total_confidence = sum(m.score for m in matches)
            n = stats.successful_matches
            stats.avg_confidence = (
                stats.avg_confidence * (n - len(matches)) + total_confidence
            ) / n

    def get_statistics(self, census_year: int | None = None) -> dict[int, MatchStatistics]:
        """Get match statistics.

        Args:
            census_year: Optional specific year, or None for all years

        Returns:
            Dictionary of census_year -> MatchStatistics
        """
        if census_year is not None:
            if census_year in self._statistics:
                return {census_year: self._statistics[census_year]}
            return {}
        return self._statistics.copy()


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


def create_matcher(
    rmtree_path: str | Path | None = None,
    icu_extension_path: str | Path | None = None,
) -> CensusRMTreeMatcher:
    """Create a matcher with default paths.

    Args:
        rmtree_path: Path to RootsMagic database (uses config if not provided)
        icu_extension_path: Path to ICU extension (uses config if not provided)

    Returns:
        Configured CensusRMTreeMatcher
    """
    from rmcitecraft.config.settings import Config

    settings = Config()

    if rmtree_path is None:
        rmtree_path = settings.rm_database_path
    if icu_extension_path is None:
        icu_extension_path = settings.sqlite_icu_extension

    return CensusRMTreeMatcher(
        rmtree_path=Path(rmtree_path),
        icu_extension_path=Path(icu_extension_path),
    )
