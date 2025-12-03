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

import json
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

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO schema_version (version) VALUES (2);
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

    def get_person_by_page_and_line(self, page_id: int, line_number: int) -> CensusPerson | None:
        """Get a census person by page ID and line number.

        Used to detect duplicates when the same person is indexed under
        multiple FamilySearch ARKs.

        Args:
            page_id: Census page ID
            line_number: Line number on the page

        Returns:
            CensusPerson if found, None otherwise
        """
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT person_id, page_id, line_number, dwelling_number, family_number,
                       household_id, full_name, given_name, surname, name_suffix,
                       relationship_to_head, sex, race, age, age_months,
                       marital_status, birthplace, birthplace_father, birthplace_mother,
                       occupation, industry, worker_class,
                       familysearch_ark, familysearch_person_id, is_target_person
                FROM census_person
                WHERE page_id = ? AND line_number = ?
                LIMIT 1
                """,
                (page_id, line_number),
            ).fetchone()

            if row:
                return CensusPerson(
                    person_id=row[0],
                    page_id=row[1],
                    line_number=row[2],
                    dwelling_number=row[3],
                    family_number=row[4],
                    household_id=row[5],
                    full_name=row[6],
                    given_name=row[7],
                    surname=row[8],
                    name_suffix=row[9],
                    relationship_to_head=row[10],
                    sex=row[11],
                    race=row[12],
                    age=row[13],
                    age_months=row[14],
                    marital_status=row[15],
                    birthplace=row[16],
                    birthplace_father=row[17],
                    birthplace_mother=row[18],
                    occupation=row[19],
                    industry=row[20],
                    worker_class=row[21],
                    familysearch_ark=row[22],
                    familysearch_person_id=row[23],
                    is_target_person=bool(row[24]),
                )
            return None

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

            return stats


# =============================================================================
# Convenience Functions
# =============================================================================


def get_census_repository() -> CensusExtractionRepository:
    """Get the census extraction repository singleton."""
    return CensusExtractionRepository()
