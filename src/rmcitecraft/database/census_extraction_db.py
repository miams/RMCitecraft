"""
Census Extraction Database Schema and Repository.

Stores census data extracted from FamilySearch in a flexible schema
that supports all census years (1790-1950) with different field sets.

Database: ~/.rmcitecraft/census.db

Architecture:
- Core tables for common fields (name, age, sex, birthplace)
- EAV table for year-specific fields (occupation, income, etc.)
- Linking tables to connect to RootsMagic database
- Extraction metadata for provenance tracking
- Optional per-field quality assessment
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

# Database location
CENSUS_DB_PATH = Path.home() / ".rmcitecraft" / "census.db"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ExtractionBatch:
    """A batch of extractions (one session)."""

    batch_id: int | None = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    source: str = "familysearch"  # familysearch, ancestry, ai_transcription
    extractor_version: str = "1.0.0"
    notes: str = ""


@dataclass
class CensusPage:
    """Census page-level metadata."""

    page_id: int | None = None
    batch_id: int | None = None
    census_year: int = 0
    state: str = ""
    county: str = ""
    township_city: str = ""
    enumeration_district: str = ""
    supervisor_district: str = ""
    sheet_number: str = ""  # 1880-1940
    sheet_letter: str = ""  # A or B
    page_number: str = ""  # 1790-1870, 1950
    stamp_number: str = ""  # 1950 citation terminology
    enumeration_date: str = ""
    enumerator_name: str = ""
    familysearch_film: str = ""
    familysearch_image_url: str = ""
    extracted_at: datetime = field(default_factory=datetime.now)


@dataclass
class CensusPerson:
    """Individual person record from census."""

    person_id: int | None = None
    page_id: int | None = None
    line_number: int | None = None
    dwelling_number: int | None = None
    family_number: int | None = None
    household_id: str = ""  # FamilySearch HOUSEHOLD_ID

    # Core fields (present in most census years)
    full_name: str = ""
    given_name: str = ""
    surname: str = ""
    name_suffix: str = ""
    relationship_to_head: str = ""
    sex: str = ""
    race: str = ""
    age: int | None = None
    age_months: int | None = None  # For infants
    marital_status: str = ""
    birthplace: str = ""
    birthplace_father: str = ""
    birthplace_mother: str = ""

    # Employment (1850+)
    occupation: str = ""
    industry: str = ""
    worker_class: str = ""  # P=Private, G=Government, O=Own business

    # FamilySearch identifiers
    familysearch_ark: str = ""  # ARK URL for this person's record
    familysearch_person_id: str = ""  # Internal FS person ID

    # Extraction metadata
    extracted_at: datetime = field(default_factory=datetime.now)
    is_target_person: bool = False  # Was this person specifically searched for?


@dataclass
class CensusPersonField:
    """Year-specific field value (EAV pattern)."""

    field_id: int | None = None
    person_id: int | None = None
    field_name: str = ""
    field_value: str = ""
    field_type: str = "string"  # string, integer, boolean
    familysearch_label: str = ""  # Original label from FamilySearch


@dataclass
class CensusRelationship:
    """Relationship between two census persons."""

    relationship_id: int | None = None
    person_id: int | None = None  # The person
    related_person_id: int | None = None  # The related person (if in database)
    related_person_name: str = ""  # Name if related person not in database
    relationship_type: str = ""  # spouse, child, parent, sibling, etc.


@dataclass
class RMTreeLink:
    """Link between census extraction and RootsMagic database."""

    link_id: int | None = None
    census_person_id: int | None = None
    rmtree_person_id: int | None = None  # PersonID/RIN in RootsMagic
    rmtree_citation_id: int | None = None  # CitationID in RootsMagic
    rmtree_event_id: int | None = None  # EventID in RootsMagic
    rmtree_database: str = ""  # Path to .rmtree file
    match_confidence: float = 0.0  # 0.0-1.0
    match_method: str = ""  # url_match, name_match, manual
    linked_at: datetime = field(default_factory=datetime.now)


@dataclass
class FieldQuality:
    """Per-field quality assessment (optional)."""

    quality_id: int | None = None
    person_field_id: int | None = None  # Links to CensusPersonField or core field
    person_id: int | None = None
    field_name: str = ""
    confidence_score: float = 0.0  # 0.0-1.0
    source_legibility: str = ""  # clear, faded, damaged, illegible
    transcription_note: str = ""  # e.g., "uncertain reading", "abbreviated"
    ai_confidence: float | None = None  # If AI-transcribed
    human_verified: bool = False
    verified_by: str = ""
    verified_at: datetime | None = None


@dataclass
class FieldHistory:
    """Version control entry for field edits."""

    history_id: int | None = None
    person_id: int | None = None
    field_name: str = ""
    field_value: str = ""
    field_source: str = ""  # 'familysearch', 'manual_edit', 'ai_transcription'
    is_original: bool = False  # True if this is the original imported value
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = ""  # User who made the edit (blank for system imports)


@dataclass
class MatchAttempt:
    """Record of a match attempt (successful or failed) between FS and RM persons.

    Stores ALL match attempts to enable iterative improvement of matching algorithms.
    Even failed matches are recorded with diagnostic information.
    """

    attempt_id: int | None = None
    batch_id: int | None = None
    page_id: int | None = None
    source_id: int | None = None  # RootsMagic SourceID being processed

    # FamilySearch data (always captured)
    fs_full_name: str = ""
    fs_given_name: str = ""
    fs_surname: str = ""
    fs_ark: str = ""
    fs_line_number: int | None = None
    fs_relationship: str = ""  # "Head", "Wife", "Son", etc.
    fs_age: str = ""
    fs_birthplace: str = ""
    fs_household_head_name: str = ""  # Critical for married name matching

    # Match result
    match_status: str = ""  # 'matched', 'skipped', 'review_needed'
    matched_rm_person_id: int | None = None
    matched_census_person_id: int | None = None  # If saved to census_person

    # Diagnostic data (WHY it failed or succeeded)
    skip_reason: str = ""  # 'surname_mismatch', 'no_first_match', 'below_threshold', etc.
    best_candidate_rm_id: int | None = None  # Best match even if rejected
    best_candidate_name: str = ""
    best_candidate_score: float = 0.0
    best_match_method: str = ""  # 'exact', 'initial', 'nickname', 'married_name', etc.
    candidates_json: str = ""  # All candidates: [{"rm_id":123,"score":0.72,"reason":"prefix"}]

    attempted_at: datetime = field(default_factory=datetime.now)


@dataclass
class ExtractionGap:
    """Record of missing or incomplete extraction data requiring analysis.

    Used to track:
    1. Expected RM persons not found in extraction (missing persons)
    2. Extracted persons with missing field data (incomplete data)
    3. Patterns in failures that may indicate systemic bugs
    """

    gap_id: int | None = None
    batch_id: int | None = None
    source_id: int | None = None  # RootsMagic SourceID

    # Gap type and classification
    gap_type: str = ""  # 'missing_person', 'missing_field', 'match_failure'
    gap_category: str = ""  # 'married_name', 'ocr_error', 'middle_name', 'fs_data_missing', etc.
    severity: str = "medium"  # 'high', 'medium', 'low'

    # Expected data (what we expected to find)
    expected_rm_person_id: int | None = None
    expected_rm_name: str = ""
    expected_field_name: str = ""  # For missing_field gaps
    expected_field_value: str = ""

    # Actual data (what we found, if anything)
    actual_fs_name: str = ""
    actual_fs_ark: str = ""
    actual_census_person_id: int | None = None
    actual_field_value: str = ""

    # Analysis
    root_cause: str = ""  # Identified root cause after analysis
    root_cause_pattern: str = ""  # Pattern ID for grouping similar gaps
    fs_data_verified: bool = False  # True if manually verified FS data exists/doesn't exist
    fs_data_exists: bool | None = None  # True=exists in FS, False=doesn't exist, None=unknown

    # Resolution
    resolution_status: str = "open"  # 'open', 'in_progress', 'resolved', 'wont_fix'
    resolution_notes: str = ""
    resolved_at: datetime | None = None

    # Timestamps
    detected_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class GapPattern:
    """Aggregated pattern of extraction gaps for prioritized fixing.

    Groups similar gaps to identify high-impact bugs that affect many records.
    """

    pattern_id: int | None = None
    pattern_name: str = ""  # e.g., "married_name_surname_mismatch"
    pattern_description: str = ""

    # Pattern matching criteria (JSON)
    match_criteria_json: str = ""  # {"gap_type": "match_failure", "skip_reason": "surname_mismatch", ...}

    # Impact metrics
    affected_count: int = 0  # Number of gaps matching this pattern
    affected_sources: int = 0  # Number of unique sources affected
    affected_batches: int = 0  # Number of unique batches affected

    # Suggested fix
    suggested_fix: str = ""  # Description of code change needed
    fix_complexity: str = "medium"  # 'trivial', 'easy', 'medium', 'hard', 'complex'

    # Status
    status: str = "identified"  # 'identified', 'analyzing', 'fix_planned', 'fix_implemented', 'verified'

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


# =============================================================================
# Database Schema
# =============================================================================

SCHEMA_SQL = """
-- Extraction batch (one session/run)
CREATE TABLE IF NOT EXISTS extraction_batch (
    batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT,
    source TEXT NOT NULL DEFAULT 'familysearch',
    extractor_version TEXT NOT NULL DEFAULT '1.0.0',
    notes TEXT DEFAULT ''
);

-- Census page metadata
CREATE TABLE IF NOT EXISTS census_page (
    page_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER REFERENCES extraction_batch(batch_id),
    census_year INTEGER NOT NULL,
    state TEXT NOT NULL DEFAULT '',
    county TEXT NOT NULL DEFAULT '',
    township_city TEXT DEFAULT '',
    enumeration_district TEXT DEFAULT '',
    supervisor_district TEXT DEFAULT '',
    sheet_number TEXT DEFAULT '',
    sheet_letter TEXT DEFAULT '',
    page_number TEXT DEFAULT '',
    stamp_number TEXT DEFAULT '',
    enumeration_date TEXT DEFAULT '',
    enumerator_name TEXT DEFAULT '',
    familysearch_film TEXT DEFAULT '',
    familysearch_image_url TEXT DEFAULT '',
    extracted_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_census_page_year ON census_page(census_year);
CREATE INDEX IF NOT EXISTS idx_census_page_location ON census_page(state, county);
CREATE INDEX IF NOT EXISTS idx_census_page_ed ON census_page(enumeration_district);

-- Census person records (core fields)
CREATE TABLE IF NOT EXISTS census_person (
    person_id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id INTEGER NOT NULL REFERENCES census_page(page_id),
    line_number INTEGER,
    dwelling_number INTEGER,
    family_number INTEGER,
    household_id TEXT DEFAULT '',

    -- Core fields present in most census years
    full_name TEXT NOT NULL DEFAULT '',
    given_name TEXT DEFAULT '',
    surname TEXT DEFAULT '',
    name_suffix TEXT DEFAULT '',
    relationship_to_head TEXT DEFAULT '',
    sex TEXT DEFAULT '',
    race TEXT DEFAULT '',
    age INTEGER,
    age_months INTEGER,
    marital_status TEXT DEFAULT '',
    birthplace TEXT DEFAULT '',
    birthplace_father TEXT DEFAULT '',
    birthplace_mother TEXT DEFAULT '',

    -- Employment (1850+)
    occupation TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    worker_class TEXT DEFAULT '',

    -- FamilySearch identifiers
    familysearch_ark TEXT DEFAULT '',
    familysearch_person_id TEXT DEFAULT '',

    -- Metadata
    extracted_at TEXT NOT NULL DEFAULT (datetime('now')),
    is_target_person INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_census_person_page ON census_person(page_id);
CREATE INDEX IF NOT EXISTS idx_census_person_name ON census_person(surname, given_name);
CREATE INDEX IF NOT EXISTS idx_census_person_ark ON census_person(familysearch_ark);
CREATE INDEX IF NOT EXISTS idx_census_person_line ON census_person(page_id, line_number);

-- Year-specific fields (EAV pattern)
CREATE TABLE IF NOT EXISTS census_person_field (
    field_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES census_person(person_id),
    field_name TEXT NOT NULL,
    field_value TEXT DEFAULT '',
    field_type TEXT DEFAULT 'string',
    familysearch_label TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_person_field_person ON census_person_field(person_id);
CREATE INDEX IF NOT EXISTS idx_person_field_name ON census_person_field(field_name);

-- Relationships between census persons
CREATE TABLE IF NOT EXISTS census_relationship (
    relationship_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES census_person(person_id),
    related_person_id INTEGER REFERENCES census_person(person_id),
    related_person_name TEXT DEFAULT '',
    relationship_type TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_relationship_person ON census_relationship(person_id);

-- Links to RootsMagic database
CREATE TABLE IF NOT EXISTS rmtree_link (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    census_person_id INTEGER NOT NULL REFERENCES census_person(person_id),
    rmtree_person_id INTEGER,
    rmtree_citation_id INTEGER,
    rmtree_event_id INTEGER,
    rmtree_database TEXT DEFAULT '',
    match_confidence REAL DEFAULT 0.0,
    match_method TEXT DEFAULT '',
    linked_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_rmtree_link_census ON rmtree_link(census_person_id);
CREATE INDEX IF NOT EXISTS idx_rmtree_link_rmtree ON rmtree_link(rmtree_person_id);
CREATE INDEX IF NOT EXISTS idx_rmtree_link_citation ON rmtree_link(rmtree_citation_id);

-- Per-field quality assessment (optional)
CREATE TABLE IF NOT EXISTS field_quality (
    quality_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_field_id INTEGER REFERENCES census_person_field(field_id),
    person_id INTEGER REFERENCES census_person(person_id),
    field_name TEXT NOT NULL,
    confidence_score REAL DEFAULT 0.0,
    source_legibility TEXT DEFAULT '',
    transcription_note TEXT DEFAULT '',
    ai_confidence REAL,
    human_verified INTEGER DEFAULT 0,
    verified_by TEXT DEFAULT '',
    verified_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_field_quality_person ON field_quality(person_id);
CREATE INDEX IF NOT EXISTS idx_field_quality_field ON field_quality(person_field_id);

-- Field edit history for version control
CREATE TABLE IF NOT EXISTS field_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES census_person(person_id),
    field_name TEXT NOT NULL,
    field_value TEXT DEFAULT '',
    field_source TEXT NOT NULL DEFAULT 'manual_edit',
    is_original INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_by TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_field_history_person ON field_history(person_id);
CREATE INDEX IF NOT EXISTS idx_field_history_field ON field_history(person_id, field_name);

-- Match attempt tracking (stores ALL match attempts for analysis)
CREATE TABLE IF NOT EXISTS match_attempt (
    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER REFERENCES extraction_batch(batch_id),
    page_id INTEGER REFERENCES census_page(page_id),
    source_id INTEGER,  -- RootsMagic SourceID being processed

    -- FamilySearch data (always captured)
    fs_full_name TEXT NOT NULL,
    fs_given_name TEXT DEFAULT '',
    fs_surname TEXT DEFAULT '',
    fs_ark TEXT DEFAULT '',
    fs_line_number INTEGER,
    fs_relationship TEXT DEFAULT '',
    fs_age TEXT DEFAULT '',
    fs_birthplace TEXT DEFAULT '',
    fs_household_head_name TEXT DEFAULT '',

    -- Match result
    match_status TEXT NOT NULL,  -- 'matched', 'skipped', 'review_needed'
    matched_rm_person_id INTEGER,
    matched_census_person_id INTEGER REFERENCES census_person(person_id),

    -- Diagnostic data
    skip_reason TEXT DEFAULT '',
    best_candidate_rm_id INTEGER,
    best_candidate_name TEXT DEFAULT '',
    best_candidate_score REAL DEFAULT 0.0,
    best_match_method TEXT DEFAULT '',
    candidates_json TEXT DEFAULT '[]',

    attempted_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_match_attempt_status ON match_attempt(match_status);
CREATE INDEX IF NOT EXISTS idx_match_attempt_source ON match_attempt(source_id);
CREATE INDEX IF NOT EXISTS idx_match_attempt_fs_ark ON match_attempt(fs_ark);
CREATE INDEX IF NOT EXISTS idx_match_attempt_batch ON match_attempt(batch_id);
CREATE INDEX IF NOT EXISTS idx_match_attempt_skip_reason ON match_attempt(skip_reason);

-- Extraction gaps (missing/incomplete data for analysis)
CREATE TABLE IF NOT EXISTS extraction_gap (
    gap_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER REFERENCES extraction_batch(batch_id),
    source_id INTEGER,

    -- Gap classification
    gap_type TEXT NOT NULL,  -- 'missing_person', 'missing_field', 'match_failure'
    gap_category TEXT DEFAULT '',  -- 'married_name', 'ocr_error', 'middle_name', 'fs_data_missing'
    severity TEXT DEFAULT 'medium',  -- 'high', 'medium', 'low'

    -- Expected data
    expected_rm_person_id INTEGER,
    expected_rm_name TEXT DEFAULT '',
    expected_field_name TEXT DEFAULT '',
    expected_field_value TEXT DEFAULT '',

    -- Actual data found
    actual_fs_name TEXT DEFAULT '',
    actual_fs_ark TEXT DEFAULT '',
    actual_census_person_id INTEGER REFERENCES census_person(person_id),
    actual_field_value TEXT DEFAULT '',

    -- Analysis
    root_cause TEXT DEFAULT '',
    root_cause_pattern TEXT DEFAULT '',
    fs_data_verified INTEGER DEFAULT 0,
    fs_data_exists INTEGER,  -- NULL=unknown, 0=doesn't exist, 1=exists

    -- Resolution
    resolution_status TEXT DEFAULT 'open',  -- 'open', 'in_progress', 'resolved', 'wont_fix'
    resolution_notes TEXT DEFAULT '',
    resolved_at TEXT,

    -- Timestamps
    detected_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_extraction_gap_type ON extraction_gap(gap_type);
CREATE INDEX IF NOT EXISTS idx_extraction_gap_category ON extraction_gap(gap_category);
CREATE INDEX IF NOT EXISTS idx_extraction_gap_source ON extraction_gap(source_id);
CREATE INDEX IF NOT EXISTS idx_extraction_gap_status ON extraction_gap(resolution_status);
CREATE INDEX IF NOT EXISTS idx_extraction_gap_pattern ON extraction_gap(root_cause_pattern);
CREATE INDEX IF NOT EXISTS idx_extraction_gap_severity ON extraction_gap(severity);

-- Gap patterns (aggregated patterns for prioritized fixing)
CREATE TABLE IF NOT EXISTS gap_pattern (
    pattern_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_name TEXT NOT NULL UNIQUE,
    pattern_description TEXT DEFAULT '',

    -- Pattern matching criteria
    match_criteria_json TEXT DEFAULT '{}',

    -- Impact metrics
    affected_count INTEGER DEFAULT 0,
    affected_sources INTEGER DEFAULT 0,
    affected_batches INTEGER DEFAULT 0,

    -- Suggested fix
    suggested_fix TEXT DEFAULT '',
    fix_complexity TEXT DEFAULT 'medium',  -- 'trivial', 'easy', 'medium', 'hard', 'complex'

    -- Status
    status TEXT DEFAULT 'identified',  -- 'identified', 'analyzing', 'fix_planned', 'fix_implemented', 'verified'

    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_gap_pattern_status ON gap_pattern(status);
CREATE INDEX IF NOT EXISTS idx_gap_pattern_complexity ON gap_pattern(fix_complexity);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO schema_version (version) VALUES (3);
"""


# =============================================================================
# Repository Class
# =============================================================================


class CensusExtractionRepository:
    """Repository for census extraction data operations."""

    def __init__(self, db_path: Path | None = None):
        """Initialize repository with database path."""
        self.db_path = db_path or CENSUS_DB_PATH
        self._ensure_db_exists()

    def _ensure_db_exists(self) -> None:
        """Create database and tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA_SQL)
            logger.info(f"Census extraction database initialized: {self.db_path}")

    def _connect(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # -------------------------------------------------------------------------
    # Batch Operations
    # -------------------------------------------------------------------------

    def create_batch(self, source: str = "familysearch", notes: str = "") -> int:
        """Create a new extraction batch."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO extraction_batch (source, notes)
                VALUES (?, ?)
                """,
                (source, notes),
            )
            batch_id = cursor.lastrowid
            logger.info(f"Created extraction batch {batch_id}")
            return batch_id

    def complete_batch(self, batch_id: int) -> None:
        """Mark batch as completed."""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE extraction_batch
                SET completed_at = datetime('now')
                WHERE batch_id = ?
                """,
                (batch_id,),
            )

    # -------------------------------------------------------------------------
    # Page Operations
    # -------------------------------------------------------------------------

    def insert_page(self, page: CensusPage) -> int:
        """Insert a census page record."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO census_page (
                    batch_id, census_year, state, county, township_city,
                    enumeration_district, supervisor_district,
                    sheet_number, sheet_letter, page_number, stamp_number,
                    enumeration_date, enumerator_name,
                    familysearch_film, familysearch_image_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    page.batch_id,
                    page.census_year,
                    page.state,
                    page.county,
                    page.township_city,
                    page.enumeration_district,
                    page.supervisor_district,
                    page.sheet_number,
                    page.sheet_letter,
                    page.page_number,
                    page.stamp_number,
                    page.enumeration_date,
                    page.enumerator_name,
                    page.familysearch_film,
                    page.familysearch_image_url,
                ),
            )
            return cursor.lastrowid

    def get_page_by_location(
        self, census_year: int, state: str, county: str, ed: str, sheet_or_page: str
    ) -> CensusPage | None:
        """Find existing page by location identifiers."""
        with self._connect() as conn:
            # Try sheet first, then page
            row = conn.execute(
                """
                SELECT * FROM census_page
                WHERE census_year = ? AND state = ? AND county = ?
                AND enumeration_district = ?
                AND (sheet_number = ? OR page_number = ? OR stamp_number = ?)
                ORDER BY page_id DESC LIMIT 1
                """,
                (census_year, state, county, ed, sheet_or_page, sheet_or_page, sheet_or_page),
            ).fetchone()

            if row:
                return self._row_to_page(row)
            return None

    def get_page(self, page_id: int) -> CensusPage | None:
        """Get a census page by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM census_page WHERE page_id = ?", (page_id,)
            ).fetchone()
            if row:
                return self._row_to_page(row)
            return None

    def _row_to_page(self, row: sqlite3.Row) -> CensusPage:
        """Convert database row to CensusPage dataclass."""
        return CensusPage(
            page_id=row["page_id"],
            batch_id=row["batch_id"],
            census_year=row["census_year"],
            state=row["state"],
            county=row["county"],
            township_city=row["township_city"],
            enumeration_district=row["enumeration_district"],
            supervisor_district=row["supervisor_district"],
            sheet_number=row["sheet_number"],
            sheet_letter=row["sheet_letter"],
            page_number=row["page_number"],
            stamp_number=row["stamp_number"],
            enumeration_date=row["enumeration_date"],
            enumerator_name=row["enumerator_name"],
            familysearch_film=row["familysearch_film"],
            familysearch_image_url=row["familysearch_image_url"],
        )

    # -------------------------------------------------------------------------
    # Person Operations
    # -------------------------------------------------------------------------

    def insert_person(self, person: CensusPerson) -> int:
        """Insert a census person record."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO census_person (
                    page_id, line_number, dwelling_number, family_number, household_id,
                    full_name, given_name, surname, name_suffix,
                    relationship_to_head, sex, race, age, age_months,
                    marital_status, birthplace, birthplace_father, birthplace_mother,
                    occupation, industry, worker_class,
                    familysearch_ark, familysearch_person_id, is_target_person
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    person.page_id,
                    person.line_number,
                    person.dwelling_number,
                    person.family_number,
                    person.household_id,
                    person.full_name,
                    person.given_name,
                    person.surname,
                    person.name_suffix,
                    person.relationship_to_head,
                    person.sex,
                    person.race,
                    person.age,
                    person.age_months,
                    person.marital_status,
                    person.birthplace,
                    person.birthplace_father,
                    person.birthplace_mother,
                    person.occupation,
                    person.industry,
                    person.worker_class,
                    person.familysearch_ark,
                    person.familysearch_person_id,
                    1 if person.is_target_person else 0,
                ),
            )
            return cursor.lastrowid

    def get_person_by_ark(self, ark: str) -> CensusPerson | None:
        """Find person by FamilySearch ARK URL."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM census_person WHERE familysearch_ark = ?", (ark,)
            ).fetchone()
            if row:
                return self._row_to_person(row)
            return None

    def get_persons_on_page(self, page_id: int) -> list[CensusPerson]:
        """Get all persons on a census page."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM census_person WHERE page_id = ? ORDER BY line_number",
                (page_id,),
            ).fetchall()
            return [self._row_to_person(row) for row in rows]

    def update_person_line_number(self, person_id: int, line_number: int) -> None:
        """Update the line number for an existing person record."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE census_person SET line_number = ? WHERE person_id = ?",
                (line_number, person_id),
            )

    def _row_to_person(self, row: sqlite3.Row) -> CensusPerson:
        """Convert database row to CensusPerson dataclass."""
        return CensusPerson(
            person_id=row["person_id"],
            page_id=row["page_id"],
            line_number=row["line_number"],
            dwelling_number=row["dwelling_number"],
            family_number=row["family_number"],
            household_id=row["household_id"],
            full_name=row["full_name"],
            given_name=row["given_name"],
            surname=row["surname"],
            name_suffix=row["name_suffix"],
            relationship_to_head=row["relationship_to_head"],
            sex=row["sex"],
            race=row["race"],
            age=row["age"],
            age_months=row["age_months"],
            marital_status=row["marital_status"],
            birthplace=row["birthplace"],
            birthplace_father=row["birthplace_father"],
            birthplace_mother=row["birthplace_mother"],
            occupation=row["occupation"],
            industry=row["industry"],
            worker_class=row["worker_class"],
            familysearch_ark=row["familysearch_ark"],
            familysearch_person_id=row["familysearch_person_id"],
            is_target_person=bool(row["is_target_person"]),
        )

    # -------------------------------------------------------------------------
    # Extended Fields (EAV)
    # -------------------------------------------------------------------------

    def insert_person_field(
        self,
        person_id: int,
        field_name: str,
        field_value: str,
        field_type: str = "string",
        familysearch_label: str = "",
    ) -> int:
        """Insert a year-specific field for a person."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO census_person_field
                (person_id, field_name, field_value, field_type, familysearch_label)
                VALUES (?, ?, ?, ?, ?)
                """,
                (person_id, field_name, field_value, field_type, familysearch_label),
            )
            return cursor.lastrowid

    def insert_person_fields_bulk(
        self, person_id: int, fields: dict[str, Any], familysearch_labels: dict[str, str] | None = None
    ) -> None:
        """Bulk insert multiple fields for a person."""
        familysearch_labels = familysearch_labels or {}
        with self._connect() as conn:
            for field_name, field_value in fields.items():
                if field_value is None or field_value == "":
                    continue

                # Determine field type
                if isinstance(field_value, bool):
                    field_type = "boolean"
                    field_value = "1" if field_value else "0"
                elif isinstance(field_value, int):
                    field_type = "integer"
                    field_value = str(field_value)
                else:
                    field_type = "string"
                    field_value = str(field_value)

                conn.execute(
                    """
                    INSERT INTO census_person_field
                    (person_id, field_name, field_value, field_type, familysearch_label)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        person_id,
                        field_name,
                        field_value,
                        field_type,
                        familysearch_labels.get(field_name, ""),
                    ),
                )

    def get_person_fields(self, person_id: int) -> dict[str, Any]:
        """Get all extended fields for a person as a dict."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT field_name, field_value, field_type FROM census_person_field WHERE person_id = ?",
                (person_id,),
            ).fetchall()

            fields = {}
            for row in rows:
                value = row["field_value"]
                if row["field_type"] == "integer":
                    value = int(value) if value else None
                elif row["field_type"] == "boolean":
                    value = value == "1"
                fields[row["field_name"]] = value
            return fields

    def get_person_field_objects(self, person_id: int) -> list[CensusPersonField]:
        """Get all extended fields for a person as CensusPersonField objects."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT field_id, person_id, field_name, field_value, field_type, familysearch_label
                   FROM census_person_field WHERE person_id = ?""",
                (person_id,),
            ).fetchall()

            return [
                CensusPersonField(
                    field_id=row["field_id"],
                    person_id=row["person_id"],
                    field_name=row["field_name"],
                    field_value=row["field_value"],
                    field_type=row["field_type"],
                    familysearch_label=row["familysearch_label"],
                )
                for row in rows
            ]

    def move_person_field(self, field_id: int, new_person_id: int) -> None:
        """Move a field to a different person (update person_id).

        Used for fixing sample line offset where FamilySearch associates
        sample line data with line+2 instead of the actual sample line person.
        """
        with self._connect() as conn:
            conn.execute(
                "UPDATE census_person_field SET person_id = ? WHERE field_id = ?",
                (new_person_id, field_id),
            )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------

    def insert_relationship(
        self,
        person_id: int,
        relationship_type: str,
        related_person_id: int | None = None,
        related_person_name: str = "",
    ) -> int:
        """Insert a relationship record."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO census_relationship
                (person_id, related_person_id, related_person_name, relationship_type)
                VALUES (?, ?, ?, ?)
                """,
                (person_id, related_person_id, related_person_name, relationship_type),
            )
            return cursor.lastrowid

    def get_relationships(self, person_id: int) -> list[CensusRelationship]:
        """Get all relationships for a person."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM census_relationship WHERE person_id = ?", (person_id,)
            ).fetchall()
            return [
                CensusRelationship(
                    relationship_id=row["relationship_id"],
                    person_id=row["person_id"],
                    related_person_id=row["related_person_id"],
                    related_person_name=row["related_person_name"],
                    relationship_type=row["relationship_type"],
                )
                for row in rows
            ]

    # -------------------------------------------------------------------------
    # RootsMagic Links
    # -------------------------------------------------------------------------

    def insert_rmtree_link(self, link: RMTreeLink) -> int:
        """Insert a link to RootsMagic database."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO rmtree_link
                (census_person_id, rmtree_person_id, rmtree_citation_id,
                 rmtree_event_id, rmtree_database, match_confidence, match_method)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    link.census_person_id,
                    link.rmtree_person_id,
                    link.rmtree_citation_id,
                    link.rmtree_event_id,
                    link.rmtree_database,
                    link.match_confidence,
                    link.match_method,
                ),
            )
            return cursor.lastrowid

    def get_links_for_citation(self, citation_id: int) -> list[RMTreeLink]:
        """Get all census extractions linked to a RootsMagic citation."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM rmtree_link WHERE rmtree_citation_id = ?", (citation_id,)
            ).fetchall()
            return [
                RMTreeLink(
                    link_id=row["link_id"],
                    census_person_id=row["census_person_id"],
                    rmtree_person_id=row["rmtree_person_id"],
                    rmtree_citation_id=row["rmtree_citation_id"],
                    rmtree_event_id=row["rmtree_event_id"],
                    rmtree_database=row["rmtree_database"],
                    match_confidence=row["match_confidence"],
                    match_method=row["match_method"],
                )
                for row in rows
            ]

    # -------------------------------------------------------------------------
    # Quality Assessment
    # -------------------------------------------------------------------------

    def insert_field_quality(self, quality: FieldQuality) -> int:
        """Insert a field quality assessment."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO field_quality
                (person_field_id, person_id, field_name, confidence_score,
                 source_legibility, transcription_note, ai_confidence,
                 human_verified, verified_by, verified_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    quality.person_field_id,
                    quality.person_id,
                    quality.field_name,
                    quality.confidence_score,
                    quality.source_legibility,
                    quality.transcription_note,
                    quality.ai_confidence,
                    1 if quality.human_verified else 0,
                    quality.verified_by,
                    quality.verified_at.isoformat() if quality.verified_at else None,
                ),
            )
            return cursor.lastrowid

    def get_field_quality(self, person_id: int) -> list[FieldQuality]:
        """Get all quality assessments for a person's fields."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM field_quality WHERE person_id = ?", (person_id,)
            ).fetchall()
            return [
                FieldQuality(
                    quality_id=row["quality_id"],
                    person_field_id=row["person_field_id"],
                    person_id=row["person_id"],
                    field_name=row["field_name"],
                    confidence_score=row["confidence_score"],
                    source_legibility=row["source_legibility"],
                    transcription_note=row["transcription_note"],
                    ai_confidence=row["ai_confidence"],
                    human_verified=bool(row["human_verified"]),
                    verified_by=row["verified_by"],
                    verified_at=datetime.fromisoformat(row["verified_at"])
                    if row["verified_at"]
                    else None,
                )
                for row in rows
            ]

    # -------------------------------------------------------------------------
    # Field History (Version Control)
    # -------------------------------------------------------------------------

    def insert_field_history(
        self,
        person_id: int,
        field_name: str,
        field_value: str,
        field_source: str = "manual_edit",
        is_original: bool = False,
        created_by: str = "",
    ) -> int:
        """Insert a field history entry for version control.

        Args:
            person_id: The census person ID
            field_name: Name of the field being tracked
            field_value: The value at this version
            field_source: Source of the value ('familysearch', 'manual_edit', 'ai_transcription')
            is_original: True if this is the original imported value
            created_by: User who made the edit (blank for system imports)

        Returns:
            The history_id of the inserted record
        """
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO field_history
                (person_id, field_name, field_value, field_source, is_original, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (person_id, field_name, field_value, field_source, 1 if is_original else 0, created_by),
            )
            return cursor.lastrowid

    def get_field_history(self, person_id: int, field_name: str | None = None) -> list[FieldHistory]:
        """Get field history for a person, optionally filtered by field name.

        Args:
            person_id: The census person ID
            field_name: Optional field name to filter by

        Returns:
            List of FieldHistory records ordered by created_at descending (newest first)
        """
        with self._connect() as conn:
            if field_name:
                rows = conn.execute(
                    """SELECT * FROM field_history
                       WHERE person_id = ? AND field_name = ?
                       ORDER BY created_at DESC""",
                    (person_id, field_name),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM field_history
                       WHERE person_id = ?
                       ORDER BY field_name, created_at DESC""",
                    (person_id,),
                ).fetchall()

            return [
                FieldHistory(
                    history_id=row["history_id"],
                    person_id=row["person_id"],
                    field_name=row["field_name"],
                    field_value=row["field_value"],
                    field_source=row["field_source"],
                    is_original=bool(row["is_original"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    created_by=row["created_by"],
                )
                for row in rows
            ]

    def get_original_field_value(self, person_id: int, field_name: str) -> str | None:
        """Get the original imported value for a field.

        Args:
            person_id: The census person ID
            field_name: Name of the field

        Returns:
            The original value, or None if no history exists
        """
        with self._connect() as conn:
            row = conn.execute(
                """SELECT field_value FROM field_history
                   WHERE person_id = ? AND field_name = ? AND is_original = 1
                   LIMIT 1""",
                (person_id, field_name),
            ).fetchone()
            return row["field_value"] if row else None

    def record_field_change(
        self,
        person_id: int,
        field_name: str,
        old_value: str,
        new_value: str,
        source: str = "manual_edit",
        created_by: str = "",
    ) -> None:
        """Record a field value change, creating original entry if needed.

        This is the main method to use when editing fields. It will:
        1. Check if there's an existing history for this field
        2. If not, create an 'original' entry with the old value
        3. Create a new entry with the new value

        Args:
            person_id: The census person ID
            field_name: Name of the field being changed
            old_value: Previous value before the edit
            new_value: New value after the edit
            source: Source of the change ('manual_edit', 'ai_transcription')
            created_by: User who made the edit
        """
        with self._connect() as conn:
            # Check if we have any history for this field
            existing = conn.execute(
                "SELECT COUNT(*) FROM field_history WHERE person_id = ? AND field_name = ?",
                (person_id, field_name),
            ).fetchone()[0]

            if existing == 0 and old_value:
                # No history exists - create the original entry first
                conn.execute(
                    """INSERT INTO field_history
                       (person_id, field_name, field_value, field_source, is_original, created_by)
                       VALUES (?, ?, ?, 'familysearch', 1, '')""",
                    (person_id, field_name, old_value),
                )

            # Now insert the new value
            conn.execute(
                """INSERT INTO field_history
                   (person_id, field_name, field_value, field_source, is_original, created_by)
                   VALUES (?, ?, ?, ?, 0, ?)""",
                (person_id, field_name, new_value, source, created_by),
            )

    # -------------------------------------------------------------------------
    # Query Utilities
    # -------------------------------------------------------------------------

    def search_persons(
        self,
        surname: str | None = None,
        given_name: str | None = None,
        census_year: int | None = None,
        state: str | None = None,
        county: str | None = None,
    ) -> list[CensusPerson]:
        """Search for persons with optional filters."""
        conditions = []
        params = []

        if surname:
            conditions.append("cp.surname LIKE ?")
            params.append(f"%{surname}%")
        if given_name:
            conditions.append("cp.given_name LIKE ?")
            params.append(f"%{given_name}%")
        if census_year:
            conditions.append("pg.census_year = ?")
            params.append(census_year)
        if state:
            conditions.append("pg.state = ?")
            params.append(state)
        if county:
            conditions.append("pg.county LIKE ?")
            params.append(f"%{county}%")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT cp.* FROM census_person cp
                JOIN census_page pg ON cp.page_id = pg.page_id
                WHERE {where_clause}
                ORDER BY pg.census_year, cp.surname, cp.given_name
                LIMIT 100
                """,
                params,
            ).fetchall()
            return [self._row_to_person(row) for row in rows]

    def get_extraction_stats(self) -> dict[str, Any]:
        """Get statistics about extracted data."""
        with self._connect() as conn:
            stats = {}

            # Total counts
            stats["total_batches"] = conn.execute(
                "SELECT COUNT(*) FROM extraction_batch"
            ).fetchone()[0]
            stats["total_pages"] = conn.execute(
                "SELECT COUNT(*) FROM census_page"
            ).fetchone()[0]
            stats["total_persons"] = conn.execute(
                "SELECT COUNT(*) FROM census_person"
            ).fetchone()[0]

            # By census year
            year_counts = conn.execute(
                """
                SELECT pg.census_year, COUNT(DISTINCT pg.page_id) as pages,
                       COUNT(cp.person_id) as persons
                FROM census_page pg
                LEFT JOIN census_person cp ON pg.page_id = cp.page_id
                GROUP BY pg.census_year
                ORDER BY pg.census_year
                """
            ).fetchall()
            stats["by_year"] = {row["census_year"]: {"pages": row["pages"], "persons": row["persons"]} for row in year_counts}

            # Links to RootsMagic
            stats["rmtree_links"] = conn.execute(
                "SELECT COUNT(*) FROM rmtree_link"
            ).fetchone()[0]

            # Sample line persons (1950 census with sample data)
            sample_line_field_names = [
                "residence_1949_same_house", "residence_1949_on_farm",
                "residence_1949_same_county", "residence_1949_different_location",
                "highest_grade_attended", "completed_grade", "school_attendance",
                "weeks_looking_for_work", "weeks_worked_1949",
                "income_wages_1949", "income_self_employment_1949", "income_other_1949",
                "veteran_status", "veteran_ww1", "veteran_ww2",
            ]
            placeholders = ",".join("?" * len(sample_line_field_names))
            stats["sample_line_persons"] = conn.execute(
                f"""
                SELECT COUNT(DISTINCT cp.person_id)
                FROM census_person cp
                JOIN census_page pg ON cp.page_id = pg.page_id
                JOIN census_person_field cpf ON cp.person_id = cpf.person_id
                WHERE pg.census_year = 1950
                  AND cpf.field_name IN ({placeholders})
                  AND cpf.field_value IS NOT NULL
                  AND cpf.field_value != ''
                """,
                sample_line_field_names,
            ).fetchone()[0]

            return stats

    # -------------------------------------------------------------------------
    # Match Attempt Operations
    # -------------------------------------------------------------------------

    def insert_match_attempt(self, attempt: MatchAttempt) -> int:
        """Insert a match attempt record (successful or failed)."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO match_attempt (
                    batch_id, page_id, source_id,
                    fs_full_name, fs_given_name, fs_surname, fs_ark,
                    fs_line_number, fs_relationship, fs_age, fs_birthplace,
                    fs_household_head_name,
                    match_status, matched_rm_person_id, matched_census_person_id,
                    skip_reason, best_candidate_rm_id, best_candidate_name,
                    best_candidate_score, best_match_method, candidates_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt.batch_id,
                    attempt.page_id,
                    attempt.source_id,
                    attempt.fs_full_name,
                    attempt.fs_given_name,
                    attempt.fs_surname,
                    attempt.fs_ark,
                    attempt.fs_line_number,
                    attempt.fs_relationship,
                    attempt.fs_age,
                    attempt.fs_birthplace,
                    attempt.fs_household_head_name,
                    attempt.match_status,
                    attempt.matched_rm_person_id,
                    attempt.matched_census_person_id,
                    attempt.skip_reason,
                    attempt.best_candidate_rm_id,
                    attempt.best_candidate_name,
                    attempt.best_candidate_score,
                    attempt.best_match_method,
                    attempt.candidates_json,
                ),
            )
            return cursor.lastrowid

    def get_match_attempts_by_status(
        self, status: str, batch_id: int | None = None, limit: int = 100
    ) -> list[MatchAttempt]:
        """Get match attempts filtered by status."""
        with self._connect() as conn:
            if batch_id:
                rows = conn.execute(
                    """SELECT * FROM match_attempt
                       WHERE match_status = ? AND batch_id = ?
                       ORDER BY attempted_at DESC LIMIT ?""",
                    (status, batch_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM match_attempt
                       WHERE match_status = ?
                       ORDER BY attempted_at DESC LIMIT ?""",
                    (status, limit),
                ).fetchall()
            return [self._row_to_match_attempt(row) for row in rows]

    def get_match_attempts_by_skip_reason(
        self, skip_reason: str, limit: int = 100
    ) -> list[MatchAttempt]:
        """Get failed match attempts by skip reason."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM match_attempt
                   WHERE skip_reason = ?
                   ORDER BY attempted_at DESC LIMIT ?""",
                (skip_reason, limit),
            ).fetchall()
            return [self._row_to_match_attempt(row) for row in rows]

    def get_match_attempt_stats(self, batch_id: int | None = None) -> dict[str, Any]:
        """Get statistics about match attempts."""
        with self._connect() as conn:
            batch_filter = "WHERE batch_id = ?" if batch_id else ""
            params = (batch_id,) if batch_id else ()

            stats = {}

            # Status counts
            status_rows = conn.execute(
                f"""SELECT match_status, COUNT(*) as count
                    FROM match_attempt {batch_filter}
                    GROUP BY match_status""",
                params,
            ).fetchall()
            stats["by_status"] = {row["match_status"]: row["count"] for row in status_rows}

            # Skip reason counts
            reason_rows = conn.execute(
                f"""SELECT skip_reason, COUNT(*) as count
                    FROM match_attempt
                    WHERE match_status = 'skipped' {' AND batch_id = ?' if batch_id else ''}
                    GROUP BY skip_reason
                    ORDER BY count DESC""",
                params if batch_id else (),
            ).fetchall()
            stats["by_skip_reason"] = {row["skip_reason"]: row["count"] for row in reason_rows}

            # Match rate
            total = sum(stats["by_status"].values())
            matched = stats["by_status"].get("matched", 0)
            stats["total_attempts"] = total
            stats["match_rate"] = matched / total if total > 0 else 0.0

            return stats

    def _row_to_match_attempt(self, row: sqlite3.Row) -> MatchAttempt:
        """Convert database row to MatchAttempt dataclass."""
        return MatchAttempt(
            attempt_id=row["attempt_id"],
            batch_id=row["batch_id"],
            page_id=row["page_id"],
            source_id=row["source_id"],
            fs_full_name=row["fs_full_name"],
            fs_given_name=row["fs_given_name"],
            fs_surname=row["fs_surname"],
            fs_ark=row["fs_ark"],
            fs_line_number=row["fs_line_number"],
            fs_relationship=row["fs_relationship"],
            fs_age=row["fs_age"],
            fs_birthplace=row["fs_birthplace"],
            fs_household_head_name=row["fs_household_head_name"],
            match_status=row["match_status"],
            matched_rm_person_id=row["matched_rm_person_id"],
            matched_census_person_id=row["matched_census_person_id"],
            skip_reason=row["skip_reason"],
            best_candidate_rm_id=row["best_candidate_rm_id"],
            best_candidate_name=row["best_candidate_name"],
            best_candidate_score=row["best_candidate_score"],
            best_match_method=row["best_match_method"],
            candidates_json=row["candidates_json"],
        )

    # -------------------------------------------------------------------------
    # Extraction Gap Operations
    # -------------------------------------------------------------------------

    def insert_extraction_gap(self, gap: ExtractionGap) -> int:
        """Insert an extraction gap record."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO extraction_gap (
                    batch_id, source_id, gap_type, gap_category, severity,
                    expected_rm_person_id, expected_rm_name,
                    expected_field_name, expected_field_value,
                    actual_fs_name, actual_fs_ark, actual_census_person_id, actual_field_value,
                    root_cause, root_cause_pattern, fs_data_verified, fs_data_exists,
                    resolution_status, resolution_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    gap.batch_id,
                    gap.source_id,
                    gap.gap_type,
                    gap.gap_category,
                    gap.severity,
                    gap.expected_rm_person_id,
                    gap.expected_rm_name,
                    gap.expected_field_name,
                    gap.expected_field_value,
                    gap.actual_fs_name,
                    gap.actual_fs_ark,
                    gap.actual_census_person_id,
                    gap.actual_field_value,
                    gap.root_cause,
                    gap.root_cause_pattern,
                    1 if gap.fs_data_verified else 0,
                    1 if gap.fs_data_exists else (0 if gap.fs_data_exists is False else None),
                    gap.resolution_status,
                    gap.resolution_notes,
                ),
            )
            return cursor.lastrowid

    def get_extraction_gaps(
        self,
        gap_type: str | None = None,
        resolution_status: str | None = None,
        batch_id: int | None = None,
        limit: int = 100,
    ) -> list[ExtractionGap]:
        """Get extraction gaps with optional filters."""
        conditions = []
        params = []

        if gap_type:
            conditions.append("gap_type = ?")
            params.append(gap_type)
        if resolution_status:
            conditions.append("resolution_status = ?")
            params.append(resolution_status)
        if batch_id:
            conditions.append("batch_id = ?")
            params.append(batch_id)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT * FROM extraction_gap
                    WHERE {where_clause}
                    ORDER BY severity DESC, detected_at DESC
                    LIMIT ?""",
                params,
            ).fetchall()
            return [self._row_to_extraction_gap(row) for row in rows]

    def update_extraction_gap(
        self,
        gap_id: int,
        root_cause: str | None = None,
        root_cause_pattern: str | None = None,
        fs_data_verified: bool | None = None,
        fs_data_exists: bool | None = None,
        resolution_status: str | None = None,
        resolution_notes: str | None = None,
    ) -> None:
        """Update extraction gap analysis fields."""
        updates = []
        params = []

        if root_cause is not None:
            updates.append("root_cause = ?")
            params.append(root_cause)
        if root_cause_pattern is not None:
            updates.append("root_cause_pattern = ?")
            params.append(root_cause_pattern)
        if fs_data_verified is not None:
            updates.append("fs_data_verified = ?")
            params.append(1 if fs_data_verified else 0)
        if fs_data_exists is not None:
            updates.append("fs_data_exists = ?")
            params.append(1 if fs_data_exists else 0)
        if resolution_status is not None:
            updates.append("resolution_status = ?")
            params.append(resolution_status)
            if resolution_status == "resolved":
                updates.append("resolved_at = datetime('now')")
        if resolution_notes is not None:
            updates.append("resolution_notes = ?")
            params.append(resolution_notes)

        if not updates:
            return

        updates.append("updated_at = datetime('now')")
        params.append(gap_id)

        with self._connect() as conn:
            conn.execute(
                f"UPDATE extraction_gap SET {', '.join(updates)} WHERE gap_id = ?",
                params,
            )

    def get_gap_summary_by_category(self, batch_id: int | None = None) -> list[dict[str, Any]]:
        """Get gap counts grouped by category for prioritization."""
        with self._connect() as conn:
            batch_filter = "WHERE batch_id = ?" if batch_id else ""
            params = (batch_id,) if batch_id else ()

            rows = conn.execute(
                f"""SELECT
                        gap_category,
                        gap_type,
                        COUNT(*) as count,
                        COUNT(DISTINCT source_id) as affected_sources,
                        SUM(CASE WHEN severity = 'high' THEN 1 ELSE 0 END) as high_severity,
                        SUM(CASE WHEN resolution_status = 'open' THEN 1 ELSE 0 END) as open_count
                    FROM extraction_gap
                    {batch_filter}
                    GROUP BY gap_category, gap_type
                    ORDER BY count DESC""",
                params,
            ).fetchall()

            return [
                {
                    "gap_category": row["gap_category"],
                    "gap_type": row["gap_type"],
                    "count": row["count"],
                    "affected_sources": row["affected_sources"],
                    "high_severity": row["high_severity"],
                    "open_count": row["open_count"],
                    "priority_score": row["count"] * (2 if row["high_severity"] > 0 else 1),
                }
                for row in rows
            ]

    def _row_to_extraction_gap(self, row: sqlite3.Row) -> ExtractionGap:
        """Convert database row to ExtractionGap dataclass."""
        return ExtractionGap(
            gap_id=row["gap_id"],
            batch_id=row["batch_id"],
            source_id=row["source_id"],
            gap_type=row["gap_type"],
            gap_category=row["gap_category"],
            severity=row["severity"],
            expected_rm_person_id=row["expected_rm_person_id"],
            expected_rm_name=row["expected_rm_name"],
            expected_field_name=row["expected_field_name"],
            expected_field_value=row["expected_field_value"],
            actual_fs_name=row["actual_fs_name"],
            actual_fs_ark=row["actual_fs_ark"],
            actual_census_person_id=row["actual_census_person_id"],
            actual_field_value=row["actual_field_value"],
            root_cause=row["root_cause"],
            root_cause_pattern=row["root_cause_pattern"],
            fs_data_verified=bool(row["fs_data_verified"]),
            fs_data_exists=None if row["fs_data_exists"] is None else bool(row["fs_data_exists"]),
            resolution_status=row["resolution_status"],
            resolution_notes=row["resolution_notes"],
            resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
        )

    # -------------------------------------------------------------------------
    # Gap Pattern Operations
    # -------------------------------------------------------------------------

    def upsert_gap_pattern(self, pattern: GapPattern) -> int:
        """Insert or update a gap pattern."""
        with self._connect() as conn:
            # Try to find existing pattern
            existing = conn.execute(
                "SELECT pattern_id FROM gap_pattern WHERE pattern_name = ?",
                (pattern.pattern_name,),
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE gap_pattern SET
                        pattern_description = ?,
                        match_criteria_json = ?,
                        affected_count = ?,
                        affected_sources = ?,
                        affected_batches = ?,
                        suggested_fix = ?,
                        fix_complexity = ?,
                        status = ?,
                        updated_at = datetime('now')
                    WHERE pattern_id = ?""",
                    (
                        pattern.pattern_description,
                        pattern.match_criteria_json,
                        pattern.affected_count,
                        pattern.affected_sources,
                        pattern.affected_batches,
                        pattern.suggested_fix,
                        pattern.fix_complexity,
                        pattern.status,
                        existing["pattern_id"],
                    ),
                )
                return existing["pattern_id"]
            else:
                cursor = conn.execute(
                    """INSERT INTO gap_pattern (
                        pattern_name, pattern_description, match_criteria_json,
                        affected_count, affected_sources, affected_batches,
                        suggested_fix, fix_complexity, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        pattern.pattern_name,
                        pattern.pattern_description,
                        pattern.match_criteria_json,
                        pattern.affected_count,
                        pattern.affected_sources,
                        pattern.affected_batches,
                        pattern.suggested_fix,
                        pattern.fix_complexity,
                        pattern.status,
                    ),
                )
                return cursor.lastrowid

    def get_gap_patterns_prioritized(self, status: str | None = None) -> list[GapPattern]:
        """Get gap patterns ordered by impact (affected_count * severity factor)."""
        with self._connect() as conn:
            status_filter = "WHERE status = ?" if status else ""
            params = (status,) if status else ()

            rows = conn.execute(
                f"""SELECT * FROM gap_pattern
                    {status_filter}
                    ORDER BY affected_count DESC, affected_sources DESC""",
                params,
            ).fetchall()

            return [
                GapPattern(
                    pattern_id=row["pattern_id"],
                    pattern_name=row["pattern_name"],
                    pattern_description=row["pattern_description"],
                    match_criteria_json=row["match_criteria_json"],
                    affected_count=row["affected_count"],
                    affected_sources=row["affected_sources"],
                    affected_batches=row["affected_batches"],
                    suggested_fix=row["suggested_fix"],
                    fix_complexity=row["fix_complexity"],
                    status=row["status"],
                )
                for row in rows
            ]


    # -------------------------------------------------------------------------
    # Validation Queue Operations
    # -------------------------------------------------------------------------

    def get_validation_queue(
        self,
        include_skipped: bool = True,
        include_low_confidence: bool = True,
        confidence_threshold: float = 0.80,
        limit: int = 500,
    ) -> list[MatchAttempt]:
        """Get match attempts needing manual validation.

        Returns skipped matches and low-confidence matches (below threshold)
        ordered by priority (skipped first, then by score ascending).

        Args:
            include_skipped: Include records with match_status='skipped'
            include_low_confidence: Include matched records below confidence threshold
            confidence_threshold: Score below which matched records need review (default 0.80)
            limit: Maximum records to return

        Returns:
            List of MatchAttempt records needing validation
        """
        conditions = []
        if include_skipped:
            conditions.append("match_status = 'skipped'")
        if include_low_confidence:
            conditions.append(
                f"(match_status = 'matched' AND best_candidate_score < {confidence_threshold})"
            )

        if not conditions:
            return []

        where_clause = " OR ".join(conditions)

        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT * FROM match_attempt
                    WHERE ({where_clause})
                    ORDER BY
                        CASE WHEN match_status = 'skipped' THEN 0 ELSE 1 END,
                        best_candidate_score ASC
                    LIMIT ?""",
                (limit,),
            ).fetchall()
            return [self._row_to_match_attempt(row) for row in rows]

    def get_validation_stats(self, confidence_threshold: float = 0.80) -> dict[str, Any]:
        """Get statistics for validation queue.

        Returns counts of:
        - skipped: Records that couldn't be matched
        - low_confidence: Matched records below threshold
        - validated: Records that have been manually validated
        - total_queue: Total records needing validation
        """
        with self._connect() as conn:
            # Skipped count
            skipped = conn.execute(
                "SELECT COUNT(*) as count FROM match_attempt WHERE match_status = 'skipped'"
            ).fetchone()["count"]

            # Low confidence count (matched but below threshold)
            low_conf = conn.execute(
                """SELECT COUNT(*) as count FROM match_attempt
                   WHERE match_status = 'matched' AND best_candidate_score < ?""",
                (confidence_threshold,),
            ).fetchone()["count"]

            # Validated count (manually confirmed)
            validated = conn.execute(
                "SELECT COUNT(*) as count FROM match_attempt WHERE match_status = 'validated'"
            ).fetchone()["count"]

            # Rejected count
            rejected = conn.execute(
                "SELECT COUNT(*) as count FROM match_attempt WHERE match_status = 'rejected'"
            ).fetchone()["count"]

            return {
                "skipped": skipped,
                "low_confidence": low_conf,
                "validated": validated,
                "rejected": rejected,
                "total_queue": skipped + low_conf,
            }

    def update_match_attempt_validation(
        self,
        attempt_id: int,
        new_status: str,
        confirmed_rm_person_id: int | None = None,
        validation_note: str = "",
    ) -> None:
        """Update a match attempt after manual validation.

        Args:
            attempt_id: The match attempt to update
            new_status: 'validated', 'rejected', or 'review_needed'
            confirmed_rm_person_id: The RIN if confirming a match
            validation_note: Optional note about the decision
        """
        with self._connect() as conn:
            if confirmed_rm_person_id:
                conn.execute(
                    """UPDATE match_attempt SET
                        match_status = ?,
                        matched_rm_person_id = ?,
                        skip_reason = ?
                    WHERE attempt_id = ?""",
                    (new_status, confirmed_rm_person_id, validation_note, attempt_id),
                )
            else:
                conn.execute(
                    """UPDATE match_attempt SET
                        match_status = ?,
                        skip_reason = ?
                    WHERE attempt_id = ?""",
                    (new_status, validation_note, attempt_id),
                )

    def update_match_attempt_census_person(
        self,
        attempt_id: int,
        census_person_id: int,
    ) -> None:
        """Update match attempt with the census_person_id after person creation.

        Args:
            attempt_id: The match attempt to update
            census_person_id: The newly created census_person_id
        """
        with self._connect() as conn:
            conn.execute(
                """UPDATE match_attempt SET
                    matched_census_person_id = ?
                WHERE attempt_id = ?""",
                (census_person_id, attempt_id),
            )

    def get_match_attempt_by_id(self, attempt_id: int) -> MatchAttempt | None:
        """Get a single match attempt by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM match_attempt WHERE attempt_id = ?", (attempt_id,)
            ).fetchone()
            if row:
                return self._row_to_match_attempt(row)
            return None

    def get_household_by_head_name(
        self, page_id: int, household_head_name: str
    ) -> list[CensusPerson]:
        """Get all census persons in a household by head name.

        Args:
            page_id: The census page ID
            household_head_name: Name of the household head from FamilySearch

        Returns:
            List of CensusPerson records in the same household
        """
        with self._connect() as conn:
            # First try to find household_id by head name
            head_row = conn.execute(
                """SELECT household_id FROM census_person
                   WHERE page_id = ?
                   AND (relationship_to_head = 'Head' OR relationship_to_head = 'Self')
                   AND full_name LIKE ?
                   LIMIT 1""",
                (page_id, f"%{household_head_name.split()[-1]}%"),  # Match by surname
            ).fetchone()

            if head_row and head_row["household_id"]:
                # Get all persons with same household_id
                rows = conn.execute(
                    """SELECT * FROM census_person
                       WHERE page_id = ? AND household_id = ?
                       ORDER BY line_number""",
                    (page_id, head_row["household_id"]),
                ).fetchall()
            else:
                # Fall back to getting persons near the head's line number
                rows = conn.execute(
                    """SELECT * FROM census_person
                       WHERE page_id = ?
                       ORDER BY line_number""",
                    (page_id,),
                ).fetchall()

            return [self._row_to_person(row) for row in rows]

    def get_validated_needing_extraction(self) -> list[MatchAttempt]:
        """Get validated match attempts that need data extraction.

        Returns match attempts that have been validated but don't have
        census_person records created yet (matched_census_person_id is NULL).
        """
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM match_attempt
                   WHERE match_status = 'validated'
                   AND matched_census_person_id IS NULL
                   ORDER BY attempted_at"""
            ).fetchall()
            return [self._row_to_match_attempt(row) for row in rows]

    def get_validated_count(self) -> int:
        """Get count of validated matches needing extraction."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT COUNT(*) as count FROM match_attempt
                   WHERE match_status = 'validated'
                   AND matched_census_person_id IS NULL"""
            ).fetchone()
            return row["count"] if row else 0

    def get_rmtree_citation_id_for_page(self, page_id: int) -> int | None:
        """Get the RootsMagic citation ID for a census page.

        Finds the citation_id from existing rmtree_links on the same page.

        Args:
            page_id: The census page ID

        Returns:
            The rmtree_citation_id if found, None otherwise
        """
        with self._connect() as conn:
            row = conn.execute(
                """SELECT DISTINCT rl.rmtree_citation_id
                   FROM rmtree_link rl
                   JOIN census_person cp ON rl.census_person_id = cp.person_id
                   WHERE cp.page_id = ?
                   AND rl.rmtree_citation_id IS NOT NULL
                   LIMIT 1""",
                (page_id,),
            ).fetchone()
            return row["rmtree_citation_id"] if row else None

    def create_rmtree_link_for_validation(
        self,
        census_person_id: int,
        rmtree_person_id: int,
        page_id: int,
        match_method: str = "manual_validation",
        match_confidence: float = 1.0,
    ) -> int | None:
        """Create an rmtree_link for a validated match.

        Args:
            census_person_id: The census_person to link
            rmtree_person_id: The RootsMagic person ID (RIN)
            page_id: The census page ID (to find citation_id)
            match_method: How the match was made (default: manual_validation)
            match_confidence: Confidence score (default: 1.0 for manual)

        Returns:
            The new link_id, or None if citation_id not found
        """
        # Get the citation_id from the page
        rmtree_citation_id = self.get_rmtree_citation_id_for_page(page_id)
        if not rmtree_citation_id:
            return None

        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO rmtree_link (
                    census_person_id, rmtree_person_id, rmtree_citation_id,
                    match_confidence, match_method
                ) VALUES (?, ?, ?, ?, ?)""",
                (
                    census_person_id,
                    rmtree_person_id,
                    rmtree_citation_id,
                    match_confidence,
                    match_method,
                ),
            )
            return cursor.lastrowid


# =============================================================================
# Convenience Functions
# =============================================================================


def get_census_repository() -> CensusExtractionRepository:
    """Get the census extraction repository singleton."""
    return CensusExtractionRepository()
