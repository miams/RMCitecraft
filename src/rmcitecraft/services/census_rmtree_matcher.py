"""Census to RootsMagic matching service.

This service matches extracted census persons from census.db to RootsMagic
persons who share a census citation. It uses a weighted scoring algorithm
based on name, age, sex, and relationship to head.

The matching is constrained to a small universe: only persons who share
the same census citation are candidates for matching.
"""

from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from rmcitecraft.database.census_extraction_db import (
    CensusExtractionRepository,
    RMTreeLink,
    get_census_repository,
)
from rmcitecraft.database.connection import connect_rmtree
from rmcitecraft.services.familysearch_census_extractor import names_match_fuzzy

# Weight configuration for matching algorithm
# These can be adjusted based on observed success rates
MATCH_WEIGHTS = {
    "relationship": 0.25,  # Head, Wife, Son, Daughter - highly reliable
    "name": 0.35,          # Fuzzy name matching
    "age": 0.25,           # Birth year → expected age ±2 years
    "sex": 0.15,           # M/F exact match
}

# RootsMagic Role ID to relationship name mapping (for Census, EventType=18)
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

# Normalize census relationship strings to match RootsMagic roles
RELATIONSHIP_ALIASES = {
    "head": "head",
    "head of household": "head",
    "wife": "wife",
    "spouse": "wife",
    "husband": "husband",
    "son": "son",
    "daughter": "daughter",
    "child": "child",
    "mother": "mother",
    "father": "father",
    "mother-in-law": "mother-in-law",
    "father-in-law": "father-in-law",
    "son-in-law": "son-in-law",
    "daughter-in-law": "daughter-in-law",
    "grandson": "grandson",
    "granddaughter": "granddaughter",
    "grandchild": "grandchild",
    "brother": "brother",
    "sister": "sister",
    "sibling": "sibling",
    "nephew": "nephew",
    "niece": "niece",
    "boarder": "boarder",
    "lodger": "lodger",
    "roomer": "roomer",
    "servant": "servant",
    "hired hand": "servant",
    "employee": "servant",
}


@dataclass
class RMPersonData:
    """RootsMagic person data for matching."""

    person_id: int  # RIN
    given_name: str
    surname: str
    full_name: str
    sex: str  # "M" or "F"
    birth_year: int | None
    relationship: str  # "head", "wife", "son", etc.
    event_id: int  # Census EventID


@dataclass
class CensusPersonData:
    """Census person data for matching (simplified from CensusPerson)."""

    person_id: int  # census.db person_id
    full_name: str
    given_name: str
    surname: str
    sex: str  # "M" or "F"
    age: int | None
    relationship: str  # normalized relationship to head
    familysearch_ark: str


@dataclass
class MatchCandidate:
    """A potential match between RM and census persons."""

    rm_person: RMPersonData
    census_person: CensusPersonData
    score: float
    score_breakdown: dict[str, float] = field(default_factory=dict)

    def __str__(self) -> str:
        return (
            f"{self.rm_person.full_name} (RIN {self.rm_person.person_id}) → "
            f"{self.census_person.full_name} (score: {self.score:.2f})"
        )


@dataclass
class MatchResult:
    """Result of matching a census citation to RootsMagic persons."""

    citation_id: int
    event_id: int
    census_year: int
    matches: list[MatchCandidate]
    unmatched_rm: list[RMPersonData]
    unmatched_census: list[CensusPersonData]
    success_rate: float  # Percentage of RM persons matched

    @property
    def is_complete(self) -> bool:
        """True if all RM persons were matched."""
        return len(self.unmatched_rm) == 0


@dataclass
class MatchStatistics:
    """Statistics for matching success rates."""

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


class CensusRMTreeMatcher:
    """Matches census extractions to RootsMagic persons.

    This matcher works within a constrained universe: given a RootsMagic
    census citation, it finds all RM persons who share that citation and
    matches them to census persons extracted from the same FamilySearch page.
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
            icu_extension_path: Path to ICU extension for RMNOCASE
            census_repo: Optional census repository (uses default if not provided)
        """
        self.rmtree_path = rmtree_path
        self.icu_extension_path = icu_extension_path
        self.census_repo = census_repo or get_census_repository()
        self._statistics: dict[int, MatchStatistics] = {}  # By census year

    def get_rm_persons_for_citation(self, citation_id: int) -> tuple[list[RMPersonData], int, int]:
        """Get all RootsMagic persons who share a citation.

        Args:
            citation_id: RootsMagic CitationID

        Returns:
            Tuple of (list of RMPersonData, EventID, census_year)
        """
        conn = connect_rmtree(self.rmtree_path, self.icu_extension_path)
        try:
            cursor = conn.cursor()

            # First, find the event linked to this citation
            cursor.execute("""
                SELECT cl.OwnerID, e.Date
                FROM CitationLinkTable cl
                JOIN EventTable e ON cl.OwnerID = e.EventID
                WHERE cl.CitationID = ?
                  AND cl.OwnerType = 2  -- Event
                  AND e.EventType = 18  -- Census
                LIMIT 1
            """, (citation_id,))

            event_row = cursor.fetchone()
            if not event_row:
                logger.warning(f"No census event found for citation {citation_id}")
                return [], 0, 0

            event_id = event_row[0]
            date_str = event_row[1] or ""

            # Parse census year from date (format: D.+YYYYMMDD...)
            census_year = 0
            if len(date_str) >= 7:
                try:
                    census_year = int(date_str[3:7])
                except ValueError:
                    pass

            persons = []

            # Get the event owner (head of household)
            cursor.execute("""
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
            """, (event_id,))

            head_row = cursor.fetchone()
            if head_row:
                birth_year = None
                if head_row[4]:
                    try:
                        birth_year = int(head_row[4])
                    except ValueError:
                        pass

                persons.append(RMPersonData(
                    person_id=head_row[0],
                    given_name=head_row[1] or "",
                    surname=head_row[2] or "",
                    full_name=f"{head_row[1] or ''} {head_row[2] or ''}".strip(),
                    sex=head_row[3],
                    birth_year=birth_year,
                    relationship="head",
                    event_id=event_id,
                ))

            # Get all witnesses (other family members)
            cursor.execute("""
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
            """, (event_id,))

            for row in cursor.fetchall():
                birth_year = None
                if row[4]:
                    try:
                        birth_year = int(row[4])
                    except ValueError:
                        pass

                persons.append(RMPersonData(
                    person_id=row[0],
                    given_name=row[1] or "",
                    surname=row[2] or "",
                    full_name=f"{row[1] or ''} {row[2] or ''}".strip(),
                    sex=row[3],
                    birth_year=birth_year,
                    relationship=(row[5] or "unknown").lower(),
                    event_id=event_id,
                ))

            logger.info(f"Found {len(persons)} RM persons for citation {citation_id} (EventID {event_id})")
            return persons, event_id, census_year

        finally:
            conn.close()

    def get_rm_persons_for_source(self, source_id: int) -> tuple[list[RMPersonData], int, int]:
        """Get all RootsMagic persons who share a source (via any of its citations).

        This is the correct method to use when you have a SourceID (from SourceTable)
        rather than a CitationID. Multiple citations can reference the same source.

        Args:
            source_id: RootsMagic SourceID

        Returns:
            Tuple of (list of RMPersonData, EventID of first census event, census_year)
        """
        conn = connect_rmtree(self.rmtree_path, self.icu_extension_path)
        try:
            cursor = conn.cursor()

            # Find all census events linked via citations from this source
            cursor.execute("""
                SELECT DISTINCT cl.OwnerID as EventID, e.Date
                FROM CitationTable c
                JOIN CitationLinkTable cl ON c.CitationID = cl.CitationID
                JOIN EventTable e ON cl.OwnerID = e.EventID
                WHERE c.SourceID = ?
                  AND cl.OwnerType = 2  -- Event
                  AND e.EventType = 18  -- Census
            """, (source_id,))

            event_rows = cursor.fetchall()
            if not event_rows:
                logger.warning(f"No census events found for source {source_id}")
                return [], 0, 0

            # Use the first event for census year
            event_id = event_rows[0][0]
            date_str = event_rows[0][1] or ""

            # Parse census year from date (format: D.+YYYYMMDD...)
            census_year = 0
            if len(date_str) >= 7:
                try:
                    census_year = int(date_str[3:7])
                except ValueError:
                    pass

            # Collect all unique persons from all census events
            all_event_ids = [row[0] for row in event_rows]
            persons_dict: dict[int, RMPersonData] = {}  # Dedupe by PersonID

            for evt_id in all_event_ids:
                # Get the event owner (head of household or person with owned census event)
                cursor.execute("""
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
                """, (evt_id,))

                head_row = cursor.fetchone()
                if head_row and head_row[0] not in persons_dict:
                    birth_year = None
                    if head_row[4]:
                        try:
                            birth_year = int(head_row[4])
                        except ValueError:
                            pass

                    persons_dict[head_row[0]] = RMPersonData(
                        person_id=head_row[0],
                        given_name=head_row[1] or "",
                        surname=head_row[2] or "",
                        full_name=f"{head_row[1] or ''} {head_row[2] or ''}".strip(),
                        sex=head_row[3],
                        birth_year=birth_year,
                        relationship="head",
                        event_id=evt_id,
                    )

                # Get all witnesses (other family members)
                cursor.execute("""
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
                """, (evt_id,))

                for row in cursor.fetchall():
                    if row[0] in persons_dict:
                        continue  # Already added

                    birth_year = None
                    if row[4]:
                        try:
                            birth_year = int(row[4])
                        except ValueError:
                            pass

                    persons_dict[row[0]] = RMPersonData(
                        person_id=row[0],
                        given_name=row[1] or "",
                        surname=row[2] or "",
                        full_name=f"{row[1] or ''} {row[2] or ''}".strip(),
                        sex=row[3],
                        birth_year=birth_year,
                        relationship=(row[5] or "unknown").lower(),
                        event_id=evt_id,
                    )

            persons = list(persons_dict.values())
            logger.info(f"Found {len(persons)} RM persons for source {source_id} across {len(all_event_ids)} events")
            return persons, event_id, census_year

        finally:
            conn.close()

    def get_census_persons_for_page(self, page_id: int) -> list[CensusPersonData]:
        """Get all census persons from a specific page.

        Args:
            page_id: census.db page_id

        Returns:
            List of CensusPersonData
        """
        persons = self.census_repo.get_persons_on_page(page_id)

        result = []
        for p in persons:
            # Normalize relationship
            rel = (p.relationship_to_head or "").lower().strip()
            rel = RELATIONSHIP_ALIASES.get(rel, rel)

            result.append(CensusPersonData(
                person_id=p.person_id,
                full_name=p.full_name or "",
                given_name=p.given_name or "",
                surname=p.surname or "",
                sex=(p.sex or "").upper()[:1],  # Normalize to M/F
                age=p.age,
                relationship=rel,
                familysearch_ark=p.familysearch_ark or "",
            ))

        return result

    def get_census_persons_by_ark(self, ark_url: str) -> tuple[list[CensusPersonData], int | None]:
        """Get census persons that match a FamilySearch ARK URL.

        Args:
            ark_url: FamilySearch ARK URL (person or page level)

        Returns:
            Tuple of (list of CensusPersonData, page_id or None)
        """
        # Find the target person by ARK
        target = self.census_repo.get_person_by_ark(ark_url)
        if not target:
            # Try to find by partial ARK match
            ark_id = ark_url.split("/")[-1].split("?")[0]
            with self.census_repo._connect() as conn:
                row = conn.execute(
                    "SELECT page_id FROM census_person WHERE familysearch_ark LIKE ?",
                    (f"%{ark_id}%",)
                ).fetchone()
                if row:
                    return self.get_census_persons_for_page(row["page_id"]), row["page_id"]
            return [], None

        # Get all persons on the same page
        return self.get_census_persons_for_page(target.page_id), target.page_id

    def calculate_match_score(
        self,
        rm_person: RMPersonData,
        census_person: CensusPersonData,
        census_year: int,
        head_surname: str = "",
    ) -> tuple[float, dict[str, float]]:
        """Calculate match score between RM and census person.

        Args:
            rm_person: RootsMagic person data
            census_person: Census person data
            census_year: Census year (for age calculation)
            head_surname: Surname of head of household (for spouse surname matching)

        Returns:
            Tuple of (total_score, breakdown_dict)
        """
        breakdown = {}

        # 1. Relationship match (25%)
        rel_score = 0.0
        rm_rel = rm_person.relationship.lower()
        census_rel = census_person.relationship.lower()

        if rm_rel == census_rel:
            rel_score = 1.0
        elif rm_rel in ("son", "daughter") and census_rel == "child" or rm_rel in ("grandson", "granddaughter") and census_rel == "grandchild" or rm_rel in ("brother", "sister") and census_rel == "sibling":
            rel_score = 0.8

        breakdown["relationship"] = rel_score * MATCH_WEIGHTS["relationship"]

        # 2. Name match (35%)
        # For wives: also accept husband's surname since census records married name
        # RootsMagic typically stores maiden name, census shows married name
        name_score = 0.0
        if names_match_fuzzy(rm_person.full_name, census_person.full_name):
            name_score = 1.0
        elif names_match_fuzzy(rm_person.surname, census_person.surname):
            # Surname matches, check given name
            if names_match_fuzzy(rm_person.given_name, census_person.given_name):
                name_score = 0.9
            else:
                name_score = 0.5  # Surname only
        elif rm_rel == "wife" and head_surname:
            # Wife with different surname - check if census uses husband's surname
            # Example: RM has "Charlotte Teeple", Census has "Charlotte Ijames"
            if names_match_fuzzy(census_person.surname, head_surname):
                # Census surname matches head's surname (married name)
                if names_match_fuzzy(rm_person.given_name, census_person.given_name):
                    name_score = 0.95  # Strong match: same given name, husband's surname
                    logger.debug(
                        f"Wife surname match: {rm_person.full_name} → "
                        f"{census_person.full_name} (using husband's surname '{head_surname}')"
                    )
                else:
                    name_score = 0.6  # Husband's surname only

        breakdown["name"] = name_score * MATCH_WEIGHTS["name"]

        # 3. Age match (25%)
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
            # else: 0.0

        breakdown["age"] = age_score * MATCH_WEIGHTS["age"]

        # 4. Sex match (15%)
        sex_score = 0.0
        if rm_person.sex and census_person.sex:
            if rm_person.sex == census_person.sex:
                sex_score = 1.0

        breakdown["sex"] = sex_score * MATCH_WEIGHTS["sex"]

        total_score = sum(breakdown.values())
        return total_score, breakdown

    def find_optimal_matches(
        self,
        rm_persons: list[RMPersonData],
        census_persons: list[CensusPersonData],
        census_year: int,
        threshold: float = 0.5,
    ) -> tuple[list[MatchCandidate], list[RMPersonData], list[CensusPersonData]]:
        """Find optimal 1:1 matching between RM and census persons.

        Uses a greedy algorithm to assign matches, prioritizing highest scores.

        Args:
            rm_persons: List of RootsMagic persons
            census_persons: List of census persons
            census_year: Census year
            threshold: Minimum score to consider a match

        Returns:
            Tuple of (matches, unmatched_rm, unmatched_census)
        """
        # Extract head's surname for spouse matching
        # Wife's census surname often matches husband's surname (married name)
        # while RootsMagic stores maiden name
        head_surname = ""
        for p in rm_persons:
            if p.relationship.lower() == "head":
                head_surname = p.surname
                break

        # Calculate all pairwise scores
        candidates: list[MatchCandidate] = []

        for rm_person in rm_persons:
            for census_person in census_persons:
                score, breakdown = self.calculate_match_score(
                    rm_person, census_person, census_year, head_surname
                )
                if score >= threshold:
                    candidates.append(MatchCandidate(
                        rm_person=rm_person,
                        census_person=census_person,
                        score=score,
                        score_breakdown=breakdown,
                    ))

        # Sort by score descending
        candidates.sort(key=lambda c: c.score, reverse=True)

        # Greedy assignment
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

        # Find unmatched
        unmatched_rm = [p for p in rm_persons if p.person_id not in matched_rm_ids]
        unmatched_census = [p for p in census_persons if p.person_id not in matched_census_ids]

        return matches, unmatched_rm, unmatched_census

    def match_citation_to_census(
        self,
        citation_id: int,
        ark_url: str | None = None,
        threshold: float = 0.5,
        create_links: bool = False,
    ) -> MatchResult | None:
        """Match a RootsMagic citation to extracted census data.

        Args:
            citation_id: RootsMagic CitationID
            ark_url: Optional FamilySearch ARK URL (if not provided, looks up from citation)
            threshold: Minimum score for a match
            create_links: If True, create rmtree_link records for matches

        Returns:
            MatchResult or None if no census data found
        """
        # Get RM persons for this citation
        rm_persons, event_id, census_year = self.get_rm_persons_for_citation(citation_id)

        if not rm_persons:
            logger.warning(f"No RM persons found for citation {citation_id}")
            return None

        logger.info(f"Matching {len(rm_persons)} RM persons for {census_year} census")

        # Get census persons
        if ark_url:
            census_persons, page_id = self.get_census_persons_by_ark(ark_url)
        else:
            # Try to find ARK from citation (would need to parse citation text)
            logger.warning("No ARK URL provided, cannot find census data")
            return None

        if not census_persons:
            logger.warning(f"No census persons found for ARK {ark_url}")
            return None

        logger.info(f"Found {len(census_persons)} census persons to match against")

        # Find optimal matches
        matches, unmatched_rm, unmatched_census = self.find_optimal_matches(
            rm_persons, census_persons, census_year, threshold
        )

        # Log results
        for match in matches:
            logger.info(
                f"  ✓ {match.rm_person.full_name} (RIN {match.rm_person.person_id}) → "
                f"{match.census_person.full_name} (score: {match.score:.2f})"
            )

        for rm_person in unmatched_rm:
            logger.warning(f"  ✗ Unmatched RM: {rm_person.full_name} (RIN {rm_person.person_id})")

        for census_person in unmatched_census:
            logger.warning(f"  ✗ Unmatched Census: {census_person.full_name}")

        # Create links if requested
        if create_links and matches:
            for match in matches:
                link = RMTreeLink(
                    census_person_id=match.census_person.person_id,
                    rmtree_person_id=match.rm_person.person_id,
                    rmtree_citation_id=citation_id,
                    rmtree_event_id=event_id,
                    rmtree_database=str(self.rmtree_path),
                    match_confidence=match.score,
                    match_method="name_match",
                )
                self.census_repo.insert_rmtree_link(link)
                logger.info(f"Created link: RIN {match.rm_person.person_id} → Census {match.census_person.person_id}")

        # Calculate success rate
        success_rate = len(matches) / len(rm_persons) if rm_persons else 0.0

        # Update statistics
        self._update_statistics(census_year, matches, rm_persons)

        return MatchResult(
            citation_id=citation_id,
            event_id=event_id,
            census_year=census_year,
            matches=matches,
            unmatched_rm=unmatched_rm,
            unmatched_census=unmatched_census,
            success_rate=success_rate,
        )

    def match_census_persons_by_ark(
        self,
        ark_url: str,
        census_year: int,
        threshold: float = 0.5,
    ) -> MatchResult | None:
        """Match census persons to RootsMagic by finding citations containing the ARK.

        This method searches the RootsMagic database for citations that contain
        the FamilySearch ARK URL in their footnote, then matches the persons.

        Args:
            ark_url: FamilySearch ARK URL
            census_year: Census year
            threshold: Minimum match score

        Returns:
            MatchResult or None if no matching citation found
        """
        # Normalize the ARK to just the ID portion for searching
        ark_id = ark_url.split("/")[-1].split("?")[0] if ark_url else ""
        if not ark_id:
            logger.warning("Invalid ARK URL")
            return None

        logger.info(f"Searching for citations containing ARK: {ark_id}")

        # Connect to RootsMagic database
        conn = connect_rmtree(self.rmtree_path, self.icu_extension_path)
        try:
            cursor = conn.cursor()

            # Try CitationTable.Footnote first
            cursor.execute("""
                SELECT DISTINCT c.CitationID
                FROM CitationTable c
                WHERE c.Footnote LIKE ?
                LIMIT 1
            """, (f"%{ark_id}%",))

            row = cursor.fetchone()
            if not row:
                # Try SourceTable.Fields (free-form citations)
                cursor.execute("""
                    SELECT DISTINCT c.CitationID
                    FROM CitationTable c
                    JOIN SourceTable s ON c.SourceID = s.SourceID
                    WHERE s.TemplateID = 0 AND CAST(s.Fields AS TEXT) LIKE ?
                    LIMIT 1
                """, (f"%{ark_id}%",))
                row = cursor.fetchone()

            if not row:
                logger.info(f"No citation found containing ARK {ark_id}")
                return None

            citation_id = row[0]
            logger.info(f"Found citation {citation_id} containing ARK {ark_id}")
        finally:
            conn.close()

        # Use existing method to do the matching
        return self.match_citation_to_census(
            citation_id=citation_id,
            ark_url=ark_url,
            threshold=threshold,
            create_links=False,  # Let caller decide
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
            try:
                link = RMTreeLink(
                    census_person_id=match.census_person.person_id,
                    rmtree_person_id=match.rm_person.person_id,
                    rmtree_citation_id=match_result.citation_id,
                    rmtree_event_id=match_result.event_id,
                    rmtree_database=str(self.rmtree_path),
                    match_confidence=match.score,
                    match_method="fuzzy_match",
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
        stats.total_attempts += len(rm_persons)
        stats.successful_matches += len(matches)
        stats.failed_matches += len(rm_persons) - len(matches)

        if matches:
            total_confidence = sum(m.score for m in matches)
            n = stats.successful_matches
            # Running average
            stats.avg_confidence = (
                (stats.avg_confidence * (n - len(matches)) + total_confidence) / n
            )

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

    def get_dynamic_threshold(self, census_year: int, default: float = 0.5) -> float:
        """Get dynamic threshold based on historical success rate.

        If we have high success rates, we can be more strict.
        If success rates are low, we might need to relax the threshold.

        Args:
            census_year: Census year
            default: Default threshold if no statistics

        Returns:
            Recommended threshold (0.0-1.0)
        """
        if census_year not in self._statistics:
            return default

        stats = self._statistics[census_year]
        if stats.total_attempts < 10:
            return default  # Not enough data

        # If success rate is high (>90%), we can be stricter
        if stats.success_rate > 0.9:
            return min(0.7, default + 0.1)

        # If success rate is low (<70%), relax threshold
        if stats.success_rate < 0.7:
            return max(0.3, default - 0.1)

        return default


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
