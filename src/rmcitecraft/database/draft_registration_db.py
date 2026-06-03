"""
Draft Registration Database Repository.

This module provides access to the draft registration sidecar database (~/.rmcitecraft/ww2-draft.db)
which stores structured metadata scraped from FamilySearch and AncestryLibrary draft registration
records.

The database uses a simplified schema (compared to census.db) since draft registrations are
1-person-per-card rather than multi-person-per-page.

Schema Version: 5
Created: 2026-02-06
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger

# Default database path
DRAFT_DB_PATH = Path.home() / ".rmcitecraft" / "ww2-draft.db"

# Current schema version
SCHEMA_VERSION = 5  # Updated 2026-02-18: Added rin + workflow status fields to draft_registration


@dataclass
class ExtractionBatch:
    """Batch of draft registration extractions."""

    batch_id: Optional[int] = None
    batch_name: Optional[str] = None
    extraction_date: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class DraftRegistration:
    """Draft registration record with all scraped metadata."""

    # Primary key
    registration_id: Optional[int] = None

    # Batch and source tracking
    batch_id: Optional[int] = None
    ancestry_url: Optional[str] = None
    familysearch_url: Optional[str] = None
    source_type: Optional[str] = None  # 'familysearch', 'ancestrylibrary'

    # RootsMagic source citation fields (computed)
    rm_source_footnote: Optional[str] = None
    rm_source_short_footnote: Optional[str] = None
    rm_source_bibliography: Optional[str] = None

    # Personal information
    full_name: str = ""
    given_name: Optional[str] = None
    surname: Optional[str] = None
    birth_date: Optional[str] = None
    birth_place: Optional[str] = None
    age: Optional[int] = None

    # Residence information
    residence_street: Optional[str] = None
    residence_city: Optional[str] = None
    residence_county: Optional[str] = None
    residence_state: Optional[str] = None

    # Contact/emergency information
    contact_person_name: Optional[str] = None
    contact_person_relationship: Optional[str] = None

    # Employment
    employer_name: Optional[str] = None

    # Physical description
    race: Optional[str] = None
    height: Optional[str] = None
    weight: Optional[str] = None
    complexion: Optional[str] = None
    eye_color: Optional[str] = None
    hair_color: Optional[str] = None
    other_characteristics: Optional[str] = None

    # Registration details
    registration_date: Optional[str] = None
    registration_place: Optional[str] = None  # Place (State) of registration

    # Collection metadata
    collection_name: Optional[str] = None

    # Image tracking
    image_downloaded: int = 0
    image_file_path: Optional[str] = None

    # Processing notes and warnings
    notes: Optional[str] = None

    # Extraction timestamp
    extracted_at: str = ""

    # RootsMagic person link
    rin: Optional[int] = None  # RootsMagic PersonID (RIN)

    # RIN linking workflow status
    rin_link_status: str = "pending"  # pending | linked | skipped | needs_review
    rin_link_method: Optional[str] = None   # auto | manual
    rin_link_notes: Optional[str] = None    # reason for skip or review flag
    rin_linked_at: Optional[str] = None     # timestamp when linked

    # RootsMagic write workflow status
    rm_write_status: str = "pending"        # pending | completed | failed
    rm_write_error: Optional[str] = None    # error message if failed
    rm_written_at: Optional[str] = None     # timestamp when written


@dataclass
class RMTreeLink:
    """Link between draft registration and RootsMagic database records."""

    # Primary key
    link_id: Optional[int] = None

    # Foreign keys
    registration_id: int = 0
    rmtree_person_id: Optional[int] = None  # RIN in RootsMagic
    rmtree_source_id: Optional[int] = None  # Source ID in RootsMagic
    rmtree_media_id: Optional[int] = None   # Media/photo ID in RootsMagic

    # Timestamp when link was created (when RM records were created)
    linked_at: str = ""


class DraftRegistrationRepository:
    """Repository for draft registration database operations."""

    def __init__(self, db_path: Path = DRAFT_DB_PATH):
        """
        Initialize repository.

        Args:
            db_path: Path to database file (default: ~/.rmcitecraft/ww2-draft.db)
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        """Create database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        """Create schema if it doesn't exist."""
        with self._connect() as conn:
            cursor = conn.cursor()

            # Check if schema exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
            )
            if not cursor.fetchone():
                # New database - create all tables
                self._create_schema(conn)
                cursor.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()
                logger.info(f"Created ww2-draft.db schema version {SCHEMA_VERSION}")
            else:
                # Schema exists - apply migrations as needed
                cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
                current_version = cursor.fetchone()[0]
                if current_version < 5:
                    self._migrate_to_v5(conn)
                    current_version = 5
                if current_version < SCHEMA_VERSION:
                    logger.warning(
                        f"Database schema is outdated (v{current_version}, expected v{SCHEMA_VERSION}). "
                        f"Please backup and delete ~/.rmcitecraft/ww2-draft.db to recreate with latest schema."
                    )

    def _migrate_to_v5(self, conn: sqlite3.Connection) -> None:
        """Migrate schema from v4 to v5: add rin + workflow status fields."""
        cursor = conn.cursor()
        logger.info("Migrating ww2-draft.db schema from v4 to v5...")

        migrations = [
            "ALTER TABLE draft_registration ADD COLUMN rin INTEGER",
            "ALTER TABLE draft_registration ADD COLUMN rin_link_status TEXT DEFAULT 'pending'",
            "ALTER TABLE draft_registration ADD COLUMN rin_link_method TEXT",
            "ALTER TABLE draft_registration ADD COLUMN rin_link_notes TEXT",
            "ALTER TABLE draft_registration ADD COLUMN rin_linked_at TEXT",
            "ALTER TABLE draft_registration ADD COLUMN rm_write_status TEXT DEFAULT 'pending'",
            "ALTER TABLE draft_registration ADD COLUMN rm_write_error TEXT",
            "ALTER TABLE draft_registration ADD COLUMN rm_written_at TEXT",
            "CREATE INDEX IF NOT EXISTS idx_draft_rin ON draft_registration(rin)",
            "CREATE INDEX IF NOT EXISTS idx_draft_rin_link_status ON draft_registration(rin_link_status)",
            "CREATE INDEX IF NOT EXISTS idx_draft_rm_write_status ON draft_registration(rm_write_status)",
        ]

        for sql in migrations:
            try:
                cursor.execute(sql)
            except Exception as e:
                # Column may already exist if partial migration was applied
                logger.debug(f"Migration step skipped ({e}): {sql[:60]}")

        # Recreate view to include new fields (DROP + CREATE since SQLite can't ALTER VIEW)
        cursor.execute("DROP VIEW IF EXISTS v_draft_with_links")
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS v_draft_with_links AS
            SELECT
                dr.*,
                rl.rmtree_source_id,
                rl.rmtree_media_id,
                rl.linked_at AS rm_linked_at
            FROM draft_registration dr
            LEFT JOIN rmtree_link rl ON rl.registration_id = dr.registration_id
        """)

        cursor.execute(
            "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?)",
            (5, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        logger.info("Migration to v5 complete.")

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        """Create all database tables."""
        cursor = conn.cursor()

        # extraction_batch table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extraction_batch (
                batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_name TEXT,
                extraction_date TEXT,
                notes TEXT
            )
        """)

        # draft_registration table (main table with all fields)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS draft_registration (
                -- Primary key
                registration_id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- Batch and source tracking
                batch_id INTEGER,
                ancestry_url TEXT,
                familysearch_url TEXT,
                source_type TEXT,

                -- RootsMagic source citation fields (computed)
                rm_source_footnote TEXT,
                rm_source_short_footnote TEXT,
                rm_source_bibliography TEXT,

                -- Personal information
                full_name TEXT NOT NULL,
                given_name TEXT,
                surname TEXT,
                birth_date TEXT,
                birth_place TEXT,
                age INTEGER,

                -- Residence information
                residence_street TEXT,
                residence_city TEXT,
                residence_county TEXT,
                residence_state TEXT,

                -- Contact/emergency information
                contact_person_name TEXT,
                contact_person_relationship TEXT,

                -- Employment
                employer_name TEXT,

                -- Physical description
                race TEXT,
                height TEXT,
                weight TEXT,
                complexion TEXT,
                eye_color TEXT,
                hair_color TEXT,
                other_characteristics TEXT,

                -- Registration details
                registration_date TEXT,
                registration_place TEXT,  -- Place (State) of registration

                -- Collection metadata
                collection_name TEXT,

                -- Image tracking
                image_downloaded INTEGER DEFAULT 0,  -- Boolean: 0=false, 1=true
                image_file_path TEXT,

                -- Processing notes and warnings
                notes TEXT,

                -- Extraction timestamp
                extracted_at TEXT,

                -- RootsMagic person link
                rin INTEGER,  -- RootsMagic PersonID (RIN)

                -- RIN linking workflow status
                rin_link_status TEXT DEFAULT 'pending',  -- pending | linked | skipped | needs_review
                rin_link_method TEXT,                    -- auto | manual
                rin_link_notes TEXT,                     -- reason for skip or review flag
                rin_linked_at TEXT,                      -- timestamp when linked

                -- RootsMagic write workflow status
                rm_write_status TEXT DEFAULT 'pending',  -- pending | completed | failed
                rm_write_error TEXT,                     -- error message if failed
                rm_written_at TEXT                       -- timestamp when written
            )
        """)

        # Create indexes for draft_registration
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_draft_state ON draft_registration(residence_state)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_draft_city ON draft_registration(residence_city)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_draft_surname ON draft_registration(surname)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_draft_full_name ON draft_registration(full_name)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_draft_batch ON draft_registration(batch_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_draft_rin ON draft_registration(rin)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_draft_rin_link_status ON draft_registration(rin_link_status)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_draft_rm_write_status ON draft_registration(rm_write_status)"
        )

        # rmtree_link table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rmtree_link (
                -- Primary key
                link_id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- Foreign keys
                registration_id INTEGER NOT NULL,
                rmtree_person_id INTEGER,  -- RIN in RootsMagic
                rmtree_source_id INTEGER,  -- Source ID in RootsMagic
                rmtree_media_id INTEGER,   -- Media/photo ID in RootsMagic

                -- Timestamp when link was created (when RM records were created)
                linked_at TEXT,

                -- Foreign key constraint
                FOREIGN KEY (registration_id) REFERENCES draft_registration(registration_id)
                    ON DELETE CASCADE
            )
        """)

        # Create indexes for rmtree_link
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_link_registration ON rmtree_link(registration_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_link_person ON rmtree_link(rmtree_person_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_link_source ON rmtree_link(rmtree_source_id)"
        )

        # Create view for easy querying
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS v_draft_with_links AS
            SELECT
                dr.*,
                rl.rmtree_source_id,
                rl.rmtree_media_id,
                rl.linked_at AS rm_linked_at
            FROM draft_registration dr
            LEFT JOIN rmtree_link rl ON rl.registration_id = dr.registration_id
        """)

        # schema_version table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
        """)

    # ==================== Batch Operations ====================

    def create_batch(
        self, batch_name: Optional[str] = None, notes: Optional[str] = None
    ) -> int:
        """
        Create a new extraction batch.

        Args:
            batch_name: Optional name for the batch
            notes: Optional notes about this batch

        Returns:
            Batch ID
        """
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO extraction_batch (batch_name, extraction_date, notes)
                VALUES (?, ?, ?)
                """,
                (batch_name, datetime.now(timezone.utc).isoformat(), notes),
            )
            conn.commit()
            return cursor.lastrowid

    def get_batch(self, batch_id: int) -> Optional[ExtractionBatch]:
        """Get batch by ID."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM extraction_batch WHERE batch_id = ?", (batch_id,))
            row = cursor.fetchone()
            if row:
                return ExtractionBatch(**dict(row))
            return None

    # ==================== Draft Registration Operations ====================

    def insert_registration(self, registration: DraftRegistration) -> int:
        """
        Insert a draft registration record.

        Args:
            registration: DraftRegistration object

        Returns:
            Registration ID
        """
        with self._connect() as conn:
            cursor = conn.cursor()

            # Set extracted_at if not set
            if not registration.extracted_at:
                registration.extracted_at = datetime.now(timezone.utc).isoformat()

            cursor.execute(
                """
                INSERT INTO draft_registration (
                    batch_id, ancestry_url, familysearch_url, source_type,
                    rm_source_footnote, rm_source_short_footnote, rm_source_bibliography,
                    full_name, given_name, surname, birth_date, birth_place, age,
                    residence_street, residence_city, residence_county, residence_state,
                    contact_person_name, contact_person_relationship,
                    employer_name,
                    race, height, weight, complexion, eye_color, hair_color, other_characteristics,
                    registration_date, registration_place,
                    collection_name,
                    image_downloaded, image_file_path, notes, extracted_at,
                    rin, rin_link_status, rin_link_method, rin_link_notes, rin_linked_at,
                    rm_write_status, rm_write_error, rm_written_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    registration.batch_id,
                    registration.ancestry_url,
                    registration.familysearch_url,
                    registration.source_type,
                    registration.rm_source_footnote,
                    registration.rm_source_short_footnote,
                    registration.rm_source_bibliography,
                    registration.full_name,
                    registration.given_name,
                    registration.surname,
                    registration.birth_date,
                    registration.birth_place,
                    registration.age,
                    registration.residence_street,
                    registration.residence_city,
                    registration.residence_county,
                    registration.residence_state,
                    registration.contact_person_name,
                    registration.contact_person_relationship,
                    registration.employer_name,
                    registration.race,
                    registration.height,
                    registration.weight,
                    registration.complexion,
                    registration.eye_color,
                    registration.hair_color,
                    registration.other_characteristics,
                    registration.registration_date,
                    registration.registration_place,
                    registration.collection_name,
                    registration.image_downloaded,
                    registration.image_file_path,
                    registration.notes,
                    registration.extracted_at,
                    registration.rin,
                    registration.rin_link_status,
                    registration.rin_link_method,
                    registration.rin_link_notes,
                    registration.rin_linked_at,
                    registration.rm_write_status,
                    registration.rm_write_error,
                    registration.rm_written_at,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_registration_by_url(self, url: str) -> Optional[DraftRegistration]:
        """Get registration by URL (checks both ancestry_url and familysearch_url)."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM draft_registration
                WHERE ancestry_url = ? OR familysearch_url = ?
                """,
                (url, url)
            )
            row = cursor.fetchone()
            if row:
                return DraftRegistration(**dict(row))
            return None

    def update_image_info(
        self, registration_id: int, image_file_path: str, downloaded: bool = True
    ) -> None:
        """Update image download info for a registration."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE draft_registration
                SET image_downloaded = ?, image_file_path = ?
                WHERE registration_id = ?
                """,
                (1 if downloaded else 0, image_file_path, registration_id),
            )
            conn.commit()

    # ==================== RMTree Link Operations ====================

    def insert_rmtree_link(self, link: RMTreeLink) -> int:
        """Insert a link to RootsMagic database."""
        with self._connect() as conn:
            cursor = conn.cursor()

            if not link.linked_at:
                link.linked_at = datetime.now(timezone.utc).isoformat()

            cursor.execute(
                """
                INSERT INTO rmtree_link (
                    registration_id, rmtree_person_id, rmtree_source_id,
                    rmtree_media_id, linked_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    link.registration_id,
                    link.rmtree_person_id,
                    link.rmtree_source_id,
                    link.rmtree_media_id,
                    link.linked_at,
                ),
            )
            conn.commit()
            return cursor.lastrowid


    def get_registrations_by_person(self, person_id: int) -> list[DraftRegistration]:
        """Get all registrations for a specific RootsMagic person."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM draft_registration
                WHERE rin = ?
                ORDER BY registration_date
                """,
                (person_id,),
            )
            rows = cursor.fetchall()
            return [DraftRegistration(**dict(row)) for row in rows]

    def update_rin_link(
        self,
        registration_id: int,
        rin: int,
        method: str = "manual",
        notes: Optional[str] = None,
    ) -> None:
        """
        Mark a registration as linked to a RootsMagic person (RIN).

        Args:
            registration_id: Draft registration ID
            rin: RootsMagic PersonID
            method: How the match was made ('auto' or 'manual')
            notes: Optional notes about the match
        """
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE draft_registration
                SET rin = ?, rin_link_status = 'linked', rin_link_method = ?,
                    rin_link_notes = ?, rin_linked_at = ?
                WHERE registration_id = ?
                """,
                (rin, method, notes, datetime.now(timezone.utc).isoformat(), registration_id),
            )
            conn.commit()

    def update_rin_link_status(
        self,
        registration_id: int,
        status: str,
        notes: Optional[str] = None,
    ) -> None:
        """
        Update the RIN linking status without setting a RIN (e.g. skipped, needs_review).

        Args:
            registration_id: Draft registration ID
            status: New status ('pending' | 'skipped' | 'needs_review')
            notes: Optional reason
        """
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE draft_registration
                SET rin_link_status = ?, rin_link_notes = ?
                WHERE registration_id = ?
                """,
                (status, notes, registration_id),
            )
            conn.commit()

    def update_citations(
        self,
        registration_id: int,
        footnote: str,
        short_footnote: str,
        bibliography: str,
    ) -> None:
        """
        Update the three citation fields for a registration.

        Args:
            registration_id: Draft registration ID
            footnote: Full footnote text
            short_footnote: Short footnote text
            bibliography: Bibliography text
        """
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE draft_registration
                SET rm_source_footnote = ?,
                    rm_source_short_footnote = ?,
                    rm_source_bibliography = ?
                WHERE registration_id = ?
                """,
                (footnote, short_footnote, bibliography, registration_id),
            )
            conn.commit()

    def update_rm_write_status(
        self,
        registration_id: int,
        status: str,
        error: Optional[str] = None,
    ) -> None:
        """
        Update the RootsMagic write status for a registration.

        Args:
            registration_id: Draft registration ID
            status: New status ('completed' | 'failed' | 'pending')
            error: Error message if status is 'failed'
        """
        with self._connect() as conn:
            cursor = conn.cursor()
            written_at = datetime.now(timezone.utc).isoformat() if status == "completed" else None
            cursor.execute(
                """
                UPDATE draft_registration
                SET rm_write_status = ?, rm_write_error = ?, rm_written_at = ?
                WHERE registration_id = ?
                """,
                (status, error, written_at, registration_id),
            )
            conn.commit()

    # ==================== Statistics ====================

    def get_statistics(self) -> dict[str, Any]:
        """Get database statistics."""
        with self._connect() as conn:
            cursor = conn.cursor()

            stats = {}

            # Total registrations
            cursor.execute("SELECT COUNT(*) FROM draft_registration")
            stats["total_registrations"] = cursor.fetchone()[0]

            # By source type
            cursor.execute(
                """
                SELECT source_type, COUNT(*) as count
                FROM draft_registration
                WHERE source_type IS NOT NULL
                GROUP BY source_type
                """
            )
            stats["by_source"] = dict(cursor.fetchall())

            # Images downloaded
            cursor.execute(
                "SELECT COUNT(*) FROM draft_registration WHERE image_downloaded = 1"
            )
            stats["images_downloaded"] = cursor.fetchone()[0]

            # RIN linking status breakdown
            cursor.execute(
                """
                SELECT rin_link_status, COUNT(*) as count
                FROM draft_registration
                GROUP BY rin_link_status
                """
            )
            stats["rin_link_status"] = dict(cursor.fetchall())
            stats["linked_to_rmtree"] = stats["rin_link_status"].get("linked", 0)

            # RootsMagic write status breakdown
            cursor.execute(
                """
                SELECT rm_write_status, COUNT(*) as count
                FROM draft_registration
                GROUP BY rm_write_status
                """
            )
            stats["rm_write_status"] = dict(cursor.fetchall())

            # Total batches
            cursor.execute("SELECT COUNT(*) FROM extraction_batch")
            stats["total_batches"] = cursor.fetchone()[0]

            return stats


# Singleton instance
_repository: Optional[DraftRegistrationRepository] = None


def get_draft_repository(
    db_path: Path = DRAFT_DB_PATH,
) -> DraftRegistrationRepository:
    """Get singleton repository instance."""
    global _repository
    if _repository is None or _repository.db_path != db_path:
        _repository = DraftRegistrationRepository(db_path)
    return _repository
