"""
Census Transcription Repository for batch extraction from FamilySearch.

Manages state persistence for census transcription batches in the shared
batch state database (~/.rmcitecraft/batch_state.db).

This is DIFFERENT from CensusBatchStateRepository which tracks Citation Batch
Processing (updating existing RootsMagic citations). This tracks Transcription
Processing (extracting data from FamilySearch into census.db).

Key tables:
- census_transcription_sessions: Batch session metadata
- census_transcription_items: Individual citation extraction state
- processed_census_images: Duplicate prevention by image ARK
- census_transcription_checkpoints: Resume support
"""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class TranscriptionItem:
    """Data class for a census transcription queue item."""

    item_id: int | None = None
    session_id: str = ""
    rmtree_citation_id: int = 0
    rmtree_person_id: int | None = None
    person_name: str = ""
    census_year: int = 0
    state: str = ""
    county: str = ""
    familysearch_ark: str = ""
    image_ark: str = ""
    status: str = "queued"
    skip_reason: str = ""
    error_message: str = ""
    retry_count: int = 0
    census_db_person_id: int | None = None
    census_db_page_id: int | None = None
    household_extracted_count: int = 0
    extraction_method: str = ""
    line_number: int | None = None
    first_line_flag: bool = False
    last_line_flag: bool = False
    edge_warning_message: str = ""


@dataclass
class ProcessedImage:
    """Data class for a processed census image."""

    image_ark: str = ""
    census_year: int = 0
    state: str = ""
    county: str = ""
    enumeration_district: str = ""
    sheet_number: str = ""
    stamp_number: str = ""
    first_processed_at: str = ""
    last_processed_at: str = ""
    first_session_id: str = ""
    total_persons_extracted: int = 0
    census_db_page_id: int | None = None


class CensusTranscriptionRepository:
    """Repository for census transcription batch processing state."""

    def __init__(self, db_path: str = "~/.rmcitecraft/batch_state.db"):
        """Initialize repository with state database path.

        Args:
            db_path: Path to state database (default: ~/.rmcitecraft/batch_state.db)
        """
        self.db_path = Path(db_path).expanduser()
        self._ensure_database_exists()

    def _ensure_database_exists(self) -> None:
        """Verify database exists and transcription tables are initialized.

        Note: Migration 004 creates transcription tables, run by BatchStateRepository.
        """
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Batch state database not found: {self.db_path}. "
                "Initialize with FindAGraveBatchStateRepository first."
            )

        # Verify transcription tables exist
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='census_transcription_sessions'
            """)

            if not cursor.fetchone():
                raise RuntimeError(
                    "Census transcription tables not found. Run migration 004 first."
                )

    @contextmanager
    def _get_connection(self):
        """Get database connection with context manager."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _now_iso() -> str:
        """Return current UTC timestamp as ISO format string."""
        return datetime.now(UTC).isoformat()

    # =========================================================================
    # Session Operations
    # =========================================================================

    def create_session(
        self,
        session_id: str,
        total_items: int,
        census_year: int | None = None,
        state_filter: str | None = None,
        config_snapshot: dict[str, Any] | None = None,
    ) -> None:
        """Create new transcription session.

        Args:
            session_id: Unique session identifier
            total_items: Total number of items in batch
            census_year: Census year filter (1790-1950) or None for all
            state_filter: Optional state abbreviation filter
            config_snapshot: Configuration settings snapshot
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO census_transcription_sessions (
                    session_id, created_at, status, total_items,
                    completed_count, error_count, skipped_count,
                    edge_warning_count, census_year, state_filter, config_snapshot
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                self._now_iso(),
                'queued',
                total_items,
                0, 0, 0, 0,
                census_year,
                state_filter,
                json.dumps(config_snapshot) if config_snapshot else None,
            ))
            conn.commit()
            year_str = f" (year: {census_year})" if census_year else ""
            state_str = f" (state: {state_filter})" if state_filter else ""
            logger.info(
                f"Created transcription session: {session_id} "
                f"({total_items} items){year_str}{state_str}"
            )

    def start_session(self, session_id: str) -> None:
        """Mark session as started."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE census_transcription_sessions
                SET started_at = ?, status = 'running'
                WHERE session_id = ?
            """, (self._now_iso(), session_id))
            conn.commit()
            logger.info(f"Started transcription session: {session_id}")

    def complete_session(self, session_id: str) -> None:
        """Mark session as completed."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE census_transcription_sessions
                SET completed_at = ?, status = 'completed'
                WHERE session_id = ?
            """, (self._now_iso(), session_id))
            conn.commit()
            logger.info(f"Completed transcription session: {session_id}")

    def pause_session(self, session_id: str) -> None:
        """Mark session as paused."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE census_transcription_sessions
                SET status = 'paused'
                WHERE session_id = ?
            """, (session_id,))
            conn.commit()
            logger.info(f"Paused transcription session: {session_id}")

    def fail_session(self, session_id: str, error_message: str = "") -> None:
        """Mark session as failed."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE census_transcription_sessions
                SET completed_at = ?, status = 'failed'
                WHERE session_id = ?
            """, (self._now_iso(), session_id))
            conn.commit()
            logger.error(f"Failed transcription session: {session_id} - {error_message}")

    def update_session_counts(
        self,
        session_id: str,
        completed_count: int | None = None,
        error_count: int | None = None,
        skipped_count: int | None = None,
        edge_warning_count: int | None = None,
    ) -> None:
        """Update session progress counts."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            updates = []
            params = []

            if completed_count is not None:
                updates.append("completed_count = ?")
                params.append(completed_count)
            if error_count is not None:
                updates.append("error_count = ?")
                params.append(error_count)
            if skipped_count is not None:
                updates.append("skipped_count = ?")
                params.append(skipped_count)
            if edge_warning_count is not None:
                updates.append("edge_warning_count = ?")
                params.append(edge_warning_count)

            if updates:
                params.append(session_id)
                cursor.execute(f"""
                    UPDATE census_transcription_sessions
                    SET {', '.join(updates)}
                    WHERE session_id = ?
                """, params)
                conn.commit()

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM census_transcription_sessions WHERE session_id = ?
            """, (session_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_resumable_sessions(self) -> list[dict[str, Any]]:
        """Get list of sessions that can be resumed."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM census_transcription_sessions
                WHERE status IN ('running', 'paused', 'queued')
                ORDER BY created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_all_sessions(self) -> list[dict[str, Any]]:
        """Get all transcription sessions."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM census_transcription_sessions
                ORDER BY created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def delete_session(self, session_id: str) -> None:
        """Delete a session and all associated data."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Items and checkpoints cascade-delete via FK
            cursor.execute(
                "DELETE FROM census_transcription_checkpoints WHERE session_id = ?",
                (session_id,)
            )
            cursor.execute(
                "DELETE FROM census_transcription_items WHERE session_id = ?",
                (session_id,)
            )
            cursor.execute(
                "DELETE FROM census_transcription_sessions WHERE session_id = ?",
                (session_id,)
            )
            conn.commit()
            logger.info(f"Deleted transcription session: {session_id}")

    # =========================================================================
    # Item Operations
    # =========================================================================

    def create_item(
        self,
        session_id: str,
        rmtree_citation_id: int,
        rmtree_person_id: int | None,
        person_name: str,
        census_year: int,
        familysearch_ark: str,
        state: str | None = None,
        county: str | None = None,
    ) -> int:
        """Create transcription item.

        Returns:
            Item ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = self._now_iso()
            cursor.execute("""
                INSERT INTO census_transcription_items (
                    session_id, rmtree_citation_id, rmtree_person_id, person_name,
                    census_year, state, county, familysearch_ark, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, rmtree_citation_id, rmtree_person_id, person_name,
                census_year, state, county, familysearch_ark, 'queued',
                now, now
            ))
            conn.commit()
            return cursor.lastrowid

    def create_items_bulk(self, items: list[dict[str, Any]]) -> int:
        """Create multiple items in one transaction.

        Args:
            items: List of dicts with keys matching create_item params

        Returns:
            Number of items created
        """
        if not items:
            return 0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = self._now_iso()

            values = [
                (
                    item['session_id'],
                    item['rmtree_citation_id'],
                    item.get('rmtree_person_id'),
                    item.get('person_name', ''),
                    item['census_year'],
                    item.get('state'),
                    item.get('county'),
                    item.get('familysearch_ark', ''),
                    'queued',
                    now, now
                )
                for item in items
            ]

            cursor.executemany("""
                INSERT INTO census_transcription_items (
                    session_id, rmtree_citation_id, rmtree_person_id, person_name,
                    census_year, state, county, familysearch_ark, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, values)
            conn.commit()
            return len(values)

    def update_item_status(
        self,
        item_id: int,
        status: str,
        error_message: str | None = None,
        skip_reason: str | None = None,
    ) -> None:
        """Update item status."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE census_transcription_items
                SET status = ?, error_message = ?, skip_reason = ?,
                    updated_at = ?, last_attempt_at = ?
                WHERE item_id = ?
            """, (status, error_message, skip_reason,
                  self._now_iso(), self._now_iso(), item_id))
            conn.commit()

    def update_item_extraction(
        self,
        item_id: int,
        image_ark: str,
        census_db_person_id: int,
        census_db_page_id: int,
        household_extracted_count: int = 0,
        extraction_method: str = "table_arks",
        line_number: int | None = None,
        first_line_flag: bool = False,
        last_line_flag: bool = False,
        edge_warning_message: str = "",
    ) -> None:
        """Update item with extraction results."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE census_transcription_items
                SET image_ark = ?, census_db_person_id = ?, census_db_page_id = ?,
                    household_extracted_count = ?, extraction_method = ?,
                    line_number = ?, first_line_flag = ?, last_line_flag = ?,
                    edge_warning_message = ?, status = 'extracted', updated_at = ?
                WHERE item_id = ?
            """, (
                image_ark, census_db_person_id, census_db_page_id,
                household_extracted_count, extraction_method,
                line_number, 1 if first_line_flag else 0, 1 if last_line_flag else 0,
                edge_warning_message, self._now_iso(), item_id
            ))
            conn.commit()

    def complete_item(self, item_id: int) -> None:
        """Mark item as complete."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE census_transcription_items
                SET status = 'complete', updated_at = ?
                WHERE item_id = ?
            """, (self._now_iso(), item_id))
            conn.commit()

    def increment_retry_count(self, item_id: int) -> int:
        """Increment item retry count and return new count."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE census_transcription_items
                SET retry_count = retry_count + 1, updated_at = ?
                WHERE item_id = ?
            """, (self._now_iso(), item_id))
            conn.commit()

            cursor.execute(
                "SELECT retry_count FROM census_transcription_items WHERE item_id = ?",
                (item_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else 0

    def get_item(self, item_id: int) -> TranscriptionItem | None:
        """Get item by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM census_transcription_items WHERE item_id = ?",
                (item_id,)
            )
            row = cursor.fetchone()
            return self._row_to_item(row) if row else None

    def get_session_items(
        self,
        session_id: str,
        status: str | None = None,
    ) -> list[TranscriptionItem]:
        """Get items for session, optionally filtered by status."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("""
                    SELECT * FROM census_transcription_items
                    WHERE session_id = ? AND status = ?
                    ORDER BY item_id
                """, (session_id, status))
            else:
                cursor.execute("""
                    SELECT * FROM census_transcription_items
                    WHERE session_id = ?
                    ORDER BY item_id
                """, (session_id,))
            return [self._row_to_item(row) for row in cursor.fetchall()]

    def get_pending_items(self, session_id: str) -> list[TranscriptionItem]:
        """Get items that need processing (queued or error with retries left)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM census_transcription_items
                WHERE session_id = ?
                  AND (status = 'queued' OR (status = 'error' AND retry_count < 3))
                ORDER BY item_id
            """, (session_id,))
            return [self._row_to_item(row) for row in cursor.fetchall()]

    def get_edge_warning_items(self, session_id: str) -> list[TranscriptionItem]:
        """Get items with edge warnings (first/last line flags)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM census_transcription_items
                WHERE session_id = ?
                  AND (first_line_flag = 1 OR last_line_flag = 1)
                ORDER BY item_id
            """, (session_id,))
            return [self._row_to_item(row) for row in cursor.fetchall()]

    def _row_to_item(self, row: sqlite3.Row) -> TranscriptionItem:
        """Convert database row to TranscriptionItem."""
        return TranscriptionItem(
            item_id=row['item_id'],
            session_id=row['session_id'],
            rmtree_citation_id=row['rmtree_citation_id'],
            rmtree_person_id=row['rmtree_person_id'],
            person_name=row['person_name'] or '',
            census_year=row['census_year'],
            state=row['state'] or '',
            county=row['county'] or '',
            familysearch_ark=row['familysearch_ark'] or '',
            image_ark=row['image_ark'] or '',
            status=row['status'],
            skip_reason=row['skip_reason'] or '',
            error_message=row['error_message'] or '',
            retry_count=row['retry_count'],
            census_db_person_id=row['census_db_person_id'],
            census_db_page_id=row['census_db_page_id'],
            household_extracted_count=row['household_extracted_count'] or 0,
            extraction_method=row['extraction_method'] or '',
            line_number=row['line_number'],
            first_line_flag=bool(row['first_line_flag']),
            last_line_flag=bool(row['last_line_flag']),
            edge_warning_message=row['edge_warning_message'] or '',
        )

    # =========================================================================
    # Processed Images (Duplicate Prevention)
    # =========================================================================

    def is_image_processed(self, image_ark: str) -> bool:
        """Check if an image has already been processed."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM processed_census_images WHERE image_ark = ?",
                (image_ark,)
            )
            return cursor.fetchone() is not None

    def get_processed_image(self, image_ark: str) -> ProcessedImage | None:
        """Get processed image info."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM processed_census_images WHERE image_ark = ?",
                (image_ark,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return ProcessedImage(
                image_ark=row['image_ark'],
                census_year=row['census_year'],
                state=row['state'] or '',
                county=row['county'] or '',
                enumeration_district=row['enumeration_district'] or '',
                sheet_number=row['sheet_number'] or '',
                stamp_number=row['stamp_number'] or '',
                first_processed_at=row['first_processed_at'] or '',
                last_processed_at=row['last_processed_at'] or '',
                first_session_id=row['first_session_id'] or '',
                total_persons_extracted=row['total_persons_extracted'] or 0,
                census_db_page_id=row['census_db_page_id'],
            )

    def mark_image_processed(
        self,
        image_ark: str,
        census_year: int,
        state: str,
        county: str,
        enumeration_district: str,
        sheet_number: str,
        stamp_number: str,
        census_db_page_id: int,
        person_count: int,
        session_id: str,
    ) -> None:
        """Mark an image as processed to prevent duplicate extraction."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = self._now_iso()

            # Use INSERT OR REPLACE to handle re-processing
            cursor.execute("""
                INSERT OR REPLACE INTO processed_census_images (
                    image_ark, census_year, state, county, enumeration_district,
                    sheet_number, stamp_number, first_processed_at, last_processed_at,
                    first_session_id, total_persons_extracted, census_db_page_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?,
                    COALESCE((SELECT first_processed_at FROM processed_census_images WHERE image_ark = ?), ?),
                    ?,
                    COALESCE((SELECT first_session_id FROM processed_census_images WHERE image_ark = ?), ?),
                    ?, ?)
            """, (
                image_ark, census_year, state, county, enumeration_district,
                sheet_number, stamp_number,
                image_ark, now,  # first_processed_at: keep existing or use now
                now,  # last_processed_at
                image_ark, session_id,  # first_session_id: keep existing or use current
                person_count, census_db_page_id
            ))
            conn.commit()
            logger.debug(f"Marked image as processed: {image_ark}")

    def get_processed_images_count(
        self,
        census_year: int | None = None,
        state: str | None = None,
    ) -> int:
        """Get count of processed images with optional filters."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT COUNT(*) FROM processed_census_images WHERE 1=1"
            params = []

            if census_year:
                query += " AND census_year = ?"
                params.append(census_year)
            if state:
                query += " AND state = ?"
                params.append(state)

            cursor.execute(query, params)
            return cursor.fetchone()[0]

    # =========================================================================
    # Checkpoint Operations
    # =========================================================================

    def create_checkpoint(
        self,
        session_id: str,
        last_processed_item_id: int,
        last_processed_citation_id: int,
    ) -> None:
        """Create or update checkpoint for session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO census_transcription_checkpoints (
                    session_id, last_processed_item_id, last_processed_citation_id,
                    checkpoint_at
                ) VALUES (?, ?, ?, ?)
            """, (session_id, last_processed_item_id, last_processed_citation_id,
                  self._now_iso()))
            conn.commit()

    def get_checkpoint(self, session_id: str) -> dict[str, Any] | None:
        """Get checkpoint for session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM census_transcription_checkpoints WHERE session_id = ?
            """, (session_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # =========================================================================
    # Analytics Queries
    # =========================================================================

    def get_session_summary(self, session_id: str) -> dict[str, Any]:
        """Get summary statistics for a session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    COUNT(*) as total_items,
                    SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors,
                    SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped,
                    SUM(CASE WHEN status IN ('queued', 'extracting') THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN first_line_flag = 1 OR last_line_flag = 1 THEN 1 ELSE 0 END) as edge_warnings,
                    SUM(household_extracted_count) as total_household_extracted
                FROM census_transcription_items
                WHERE session_id = ?
            """, (session_id,))
            row = cursor.fetchone()
            return {
                'total_items': row['total_items'] or 0,
                'completed': row['completed'] or 0,
                'errors': row['errors'] or 0,
                'skipped': row['skipped'] or 0,
                'pending': row['pending'] or 0,
                'edge_warnings': row['edge_warnings'] or 0,
                'total_household_extracted': row['total_household_extracted'] or 0,
            }

    def get_status_distribution(self, session_id: str) -> dict[str, int]:
        """Get status distribution for a session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM census_transcription_items
                WHERE session_id = ?
                GROUP BY status
            """, (session_id,))
            return {row['status']: row['count'] for row in cursor.fetchall()}

    def get_extraction_method_distribution(self, session_id: str) -> dict[str, int]:
        """Get distribution of extraction methods used."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT extraction_method, COUNT(*) as count
                FROM census_transcription_items
                WHERE session_id = ? AND extraction_method IS NOT NULL
                GROUP BY extraction_method
            """, (session_id,))
            return {row['extraction_method']: row['count'] for row in cursor.fetchall()}
