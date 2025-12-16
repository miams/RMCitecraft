"""
Census batch state repository for Census batch processing.

Manages state persistence for Census batches in separate SQLite database
(~/.rmcitecraft/batch_state.db) to enable crash recovery, resume capability,
and performance tracking.

CRITICAL: Uses census_batch_sessions and census_batch_items tables (separate
from Find a Grave tables) to support census-specific analytics and fields.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger


class CensusBatchStateRepository:
    """Repository for Census batch processing state persistence."""

    def __init__(self, db_path: str = "~/.rmcitecraft/batch_state.db"):
        """Initialize repository with state database path.

        Args:
            db_path: Path to state database (default: ~/.rmcitecraft/batch_state.db)
        """
        self.db_path = Path(db_path).expanduser()
        self._ensure_database_exists()

    def _ensure_database_exists(self) -> None:
        """Verify database exists and schema is initialized.

        Note: Migration 002 creates census tables, run by BatchStateRepository.
        """
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Batch state database not found: {self.db_path}. "
                "Initialize with BatchStateRepository first."
            )

        # Verify census tables exist
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='census_batch_sessions'
            """)

            if not cursor.fetchone():
                raise RuntimeError(
                    "Census batch tables not found. Run migration 002 first."
                )

    @contextmanager
    def _get_connection(self):
        """Get database connection with context manager.

        Yields:
            sqlite3.Connection: Database connection
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Access columns by name
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _now_iso() -> str:
        """Return current UTC timestamp as ISO format string.

        Returns ISO format string to avoid Python 3.12+ deprecation warning
        for datetime adapter in SQLite.

        Returns:
            str: ISO format timestamp (e.g., '2025-11-21T15:41:32.123456+00:00')
        """
        return datetime.now(timezone.utc).isoformat()

    # =========================================================================
    # Session Operations
    # =========================================================================

    def create_session(
        self,
        session_id: str,
        total_items: int,
        census_year: int | None = None,
        config_snapshot: dict[str, Any] | None = None,
    ) -> None:
        """Create new Census batch session.

        Args:
            session_id: Unique session identifier
            total_items: Total number of items in batch
            census_year: Census year filter (1790-1950) or None for all years
            config_snapshot: Configuration settings snapshot
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO census_batch_sessions (
                    session_id, created_at, status, total_items,
                    completed_count, error_count, census_year, config_snapshot
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                self._now_iso(),
                'queued',
                total_items,
                0,
                0,
                census_year,
                json.dumps(config_snapshot) if config_snapshot else None,
            ))
            conn.commit()
            year_str = f" (year: {census_year})" if census_year else ""
            logger.info(f"Created Census batch session: {session_id} ({total_items} items){year_str}")

    def start_session(self, session_id: str) -> None:
        """Mark session as started.

        Args:
            session_id: Session identifier
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE census_batch_sessions
                SET started_at = ?, status = 'running'
                WHERE session_id = ?
            """, (self._now_iso(), session_id))
            conn.commit()
            logger.info(f"Started Census batch session: {session_id}")

    def complete_session(self, session_id: str) -> None:
        """Mark session as completed.

        Args:
            session_id: Session identifier
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE census_batch_sessions
                SET completed_at = ?, status = 'completed'
                WHERE session_id = ?
            """, (self._now_iso(), session_id))
            conn.commit()
            logger.info(f"Completed Census batch session: {session_id}")

    def pause_session(self, session_id: str) -> None:
        """Mark session as paused.

        Args:
            session_id: Session identifier
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE census_batch_sessions
                SET status = 'paused'
                WHERE session_id = ?
            """, (session_id,))
            conn.commit()
            logger.info(f"Paused Census batch session: {session_id}")

    def delete_session(self, session_id: str) -> None:
        """Delete a session and all associated data.

        Deletes:
        - Session record
        - All batch items
        - All checkpoints
        - All performance metrics (where batch_type='census')

        Args:
            session_id: Session identifier
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Delete in order: metrics, checkpoints, items, session
            cursor.execute("""
                DELETE FROM performance_metrics
                WHERE session_id = ? AND batch_type = 'census'
            """, (session_id,))
            cursor.execute("DELETE FROM census_batch_checkpoints WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM census_batch_items WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM census_batch_sessions WHERE session_id = ?", (session_id,))

            conn.commit()
            logger.info(f"Deleted Census batch session and all associated data: {session_id}")

    def clear_all_sessions(self) -> int:
        """Clear all Census sessions and reset database.

        DANGEROUS: This deletes ALL Census batch state data.
        Use when RootsMagic database has been restored from backup
        and state database is out of sync.

        Returns:
            Number of sessions deleted
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Count sessions before deletion
            cursor.execute("SELECT COUNT(*) FROM census_batch_sessions")
            count = cursor.fetchone()[0]

            # Delete all Census data
            cursor.execute("DELETE FROM performance_metrics WHERE batch_type = 'census'")
            cursor.execute("DELETE FROM census_batch_checkpoints")
            cursor.execute("DELETE FROM census_batch_items")
            cursor.execute("DELETE FROM census_batch_sessions")

            conn.commit()
            logger.warning(f"Cleared all Census batch state data ({count} sessions deleted)")

        return count

    def update_session_counts(
        self,
        session_id: str,
        completed_count: int | None = None,
        error_count: int | None = None,
    ) -> None:
        """Update session progress counts.

        Args:
            session_id: Session identifier
            completed_count: Number of completed items
            error_count: Number of failed items
        """
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

            if updates:
                params.append(session_id)
                cursor.execute(f"""
                    UPDATE census_batch_sessions
                    SET {', '.join(updates)}
                    WHERE session_id = ?
                """, params)
                conn.commit()

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session data dict or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM census_batch_sessions WHERE session_id = ?
            """, (session_id,))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_resumable_sessions(self) -> list[dict[str, Any]]:
        """Get list of sessions that can be resumed.

        Returns:
            List of session data dicts
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM census_batch_sessions
                WHERE status IN ('running', 'paused', 'queued')
                ORDER BY created_at DESC
            """)

            return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # Item Operations
    # =========================================================================

    def create_item(
        self,
        session_id: str,
        person_id: int,
        person_name: str,
        census_year: int,
        state: str | None = None,
        county: str | None = None,
        citation_id: int | None = None,
        source_id: int | None = None,
    ) -> int:
        """Create Census batch item.

        Args:
            session_id: Session identifier
            person_id: RootsMagic person ID
            person_name: Person's full name
            census_year: Census year (1790-1950)
            state: US state abbreviation (e.g., "OH", "TX")
            county: County name
            citation_id: RootsMagic citation ID (required for unique tracking)
            source_id: RootsMagic source ID

        Returns:
            Item ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = self._now_iso()

            # Use INSERT OR IGNORE to handle duplicate citations gracefully
            # This can happen if the same citation appears multiple times
            cursor.execute("""
                INSERT OR IGNORE INTO census_batch_items (
                    session_id, person_id, person_name, census_year,
                    state, county, citation_id, source_id,
                    status, retry_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, person_id, person_name, census_year,
                state, county, citation_id, source_id,
                'queued', 0, now, now
            ))
            conn.commit()

            return cursor.lastrowid

    def update_item_status(
        self,
        item_id: int,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Update item status.

        Args:
            item_id: Item ID
            status: New status (queued, extracting, extracted, creating_citation,
                   created_citation, downloading_images, complete, error)
            error_message: Error message if status is 'error'
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE census_batch_items
                SET status = ?, error_message = ?, updated_at = ?, last_attempt_at = ?
                WHERE id = ?
            """, (status, error_message, self._now_iso(),
                  self._now_iso(), item_id))
            conn.commit()

    def increment_retry_count(self, item_id: int) -> int:
        """Increment item retry count.

        Args:
            item_id: Item ID

        Returns:
            New retry count
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE census_batch_items
                SET retry_count = retry_count + 1, updated_at = ?
                WHERE id = ?
            """, (self._now_iso(), item_id))
            conn.commit()

            cursor.execute("SELECT retry_count FROM census_batch_items WHERE id = ?", (item_id,))
            row = cursor.fetchone()
            return row[0] if row else 0

    def update_item_extraction(
        self,
        item_id: int,
        extracted_data: dict[str, Any],
    ) -> None:
        """Update item with extracted census data.

        Args:
            item_id: Item ID
            extracted_data: Extracted census data
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE census_batch_items
                SET extracted_data = ?, status = 'extracted', updated_at = ?
                WHERE id = ?
            """, (json.dumps(extracted_data), self._now_iso(), item_id))
            conn.commit()

    def update_item_citation(
        self,
        item_id: int,
        citation_id: int,
        source_id: int,
        event_id: int | None = None,
    ) -> None:
        """Update item with created citation IDs.

        Args:
            item_id: Item ID
            citation_id: Created citation ID
            source_id: Created source ID
            event_id: Created census event ID (if any)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE census_batch_items
                SET created_citation_id = ?, created_source_id = ?,
                    created_event_id = ?, status = 'created_citation', updated_at = ?
                WHERE id = ?
            """, (citation_id, source_id, event_id,
                  self._now_iso(), item_id))
            conn.commit()

    def update_item_images(
        self,
        item_id: int,
        image_paths: list[str],
    ) -> None:
        """Update item with downloaded image paths.

        Args:
            item_id: Item ID
            image_paths: List of downloaded image file paths
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE census_batch_items
                SET downloaded_image_paths = ?, updated_at = ?
                WHERE id = ?
            """, (json.dumps(image_paths), self._now_iso(), item_id))
            conn.commit()

    def mark_item_exported(self, item_id: int) -> None:
        """Mark item as exported to RootsMagic.

        Args:
            item_id: Item ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE census_batch_items
                SET export_status = 'exported', updated_at = ?
                WHERE id = ?
            """, (self._now_iso(), item_id))
            conn.commit()

    def get_item(self, item_id: int) -> dict[str, Any] | None:
        """Get item by ID.

        Args:
            item_id: Item ID

        Returns:
            Item data dict or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM census_batch_items WHERE id = ?", (item_id,))

            row = cursor.fetchone()
            if row:
                item = dict(row)
                # Parse JSON fields
                if item['extracted_data']:
                    item['extracted_data'] = json.loads(item['extracted_data'])
                if item['downloaded_image_paths']:
                    item['downloaded_image_paths'] = json.loads(item['downloaded_image_paths'])
                return item
            return None

    def get_session_items(
        self,
        session_id: str,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get items for session, optionally filtered by status.

        Args:
            session_id: Session identifier
            status: Optional status filter

        Returns:
            List of item data dicts
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if status:
                cursor.execute("""
                    SELECT * FROM census_batch_items
                    WHERE session_id = ? AND status = ?
                    ORDER BY id
                """, (session_id, status))
            else:
                cursor.execute("""
                    SELECT * FROM census_batch_items
                    WHERE session_id = ?
                    ORDER BY id
                """, (session_id,))

            items = []
            for row in cursor.fetchall():
                item = dict(row)
                # Parse JSON fields
                if item['extracted_data']:
                    item['extracted_data'] = json.loads(item['extracted_data'])
                if item['downloaded_image_paths']:
                    item['downloaded_image_paths'] = json.loads(item['downloaded_image_paths'])
                items.append(item)

            return items

    # =========================================================================
    # Checkpoint Operations
    # =========================================================================

    def create_checkpoint(
        self,
        session_id: str,
        last_processed_item_id: int,
        last_processed_person_id: int,
    ) -> None:
        """Create or update checkpoint for session.

        Args:
            session_id: Session identifier
            last_processed_item_id: Last processed item ID
            last_processed_person_id: Last processed person ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO census_batch_checkpoints (
                    session_id, last_processed_item_id, last_processed_person_id, checkpoint_at
                ) VALUES (?, ?, ?, ?)
            """, (session_id, last_processed_item_id, last_processed_person_id,
                  self._now_iso()))
            conn.commit()

    def get_checkpoint(self, session_id: str) -> dict[str, Any] | None:
        """Get checkpoint for session.

        Args:
            session_id: Session identifier

        Returns:
            Checkpoint data dict or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM census_batch_checkpoints WHERE session_id = ?
            """, (session_id,))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    # =========================================================================
    # Performance Metrics Operations
    # =========================================================================

    def record_metric(
        self,
        operation: str,
        duration_ms: int,
        success: bool,
        session_id: str | None = None,
    ) -> None:
        """Record performance metric for Census batch operation.

        Args:
            operation: Operation type (page_load, extraction, etc.)
            duration_ms: Duration in milliseconds
            success: Whether operation succeeded
            session_id: Optional session identifier
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO performance_metrics (
                    timestamp, operation, duration_ms, success, session_id, batch_type
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (self._now_iso(), operation, duration_ms, success, session_id, 'census'))
            conn.commit()

    def get_recent_metrics(
        self,
        operation: str,
        limit: int = 10,
        success_only: bool = True,
    ) -> list[int]:
        """Get recent performance metrics for operation.

        Args:
            operation: Operation type
            limit: Number of recent metrics to retrieve
            success_only: Only include successful operations

        Returns:
            List of duration values in milliseconds
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if success_only:
                cursor.execute("""
                    SELECT duration_ms FROM performance_metrics
                    WHERE operation = ? AND success = 1 AND batch_type = 'census'
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (operation, limit))
            else:
                cursor.execute("""
                    SELECT duration_ms FROM performance_metrics
                    WHERE operation = ? AND batch_type = 'census'
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (operation, limit))

            return [row[0] for row in cursor.fetchall()]

    def get_session_metrics(self, session_id: str) -> dict[str, Any]:
        """Get aggregated metrics for session.

        Args:
            session_id: Session identifier

        Returns:
            Dict with metrics by operation type
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    operation,
                    COUNT(*) as count,
                    AVG(duration_ms) as avg_duration,
                    MIN(duration_ms) as min_duration,
                    MAX(duration_ms) as max_duration,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count
                FROM performance_metrics
                WHERE session_id = ? AND batch_type = 'census'
                GROUP BY operation
            """, (session_id,))

            metrics = {}
            for row in cursor.fetchall():
                metrics[row[0]] = {
                    'count': row[1],
                    'avg_duration_ms': row[2],
                    'min_duration_ms': row[3],
                    'max_duration_ms': row[4],
                    'success_count': row[5],
                    'success_rate': row[5] / row[1] if row[1] > 0 else 0,
                }

            return metrics

    # =========================================================================
    # Dashboard Query Operations
    # =========================================================================

    def get_master_progress(self) -> dict[str, int]:
        """Get overall progress across all Census sessions.

        Returns:
            Dict with total_items, completed, failed, pending, skipped counts
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    COUNT(*) as total_items,
                    SUM(CASE WHEN status IN ('completed', 'complete', 'created_citation') THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN status IN ('queued', 'pending') THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped
                FROM census_batch_items
            """)

            row = cursor.fetchone()
            return {
                'total_items': row['total_items'] or 0,
                'completed': row['completed'] or 0,
                'failed': row['failed'] or 0,
                'pending': row['pending'] or 0,
                'skipped': row['skipped'] or 0,
            }

    def get_status_distribution(self, session_id: str | None = None) -> dict[str, int]:
        """Get status distribution for specific session or all sessions.

        Args:
            session_id: Optional session identifier (None = all sessions)

        Returns:
            Dict mapping status to count
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if session_id:
                cursor.execute("""
                    SELECT status, COUNT(*) as count
                    FROM census_batch_items
                    WHERE session_id = ?
                    GROUP BY status
                """, (session_id,))
            else:
                cursor.execute("""
                    SELECT status, COUNT(*) as count
                    FROM census_batch_items
                    GROUP BY status
                """)

            return {row['status']: row['count'] for row in cursor.fetchall()}

    def get_processing_timeline(
        self,
        session_id: str | None = None,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get processing timeline data for visualization.

        Args:
            session_id: Optional session identifier (None = all sessions)
            limit: Maximum number of items to return

        Returns:
            List of items with timestamp, person_id, person_name, status, error_message
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if session_id:
                cursor.execute("""
                    SELECT
                        updated_at as timestamp,
                        person_id,
                        person_name as full_name,
                        status,
                        error_message
                    FROM census_batch_items
                    WHERE session_id = ?
                      AND updated_at IS NOT NULL
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (session_id, limit))
            else:
                cursor.execute("""
                    SELECT
                        updated_at as timestamp,
                        person_id,
                        person_name as full_name,
                        status,
                        error_message
                    FROM census_batch_items
                    WHERE updated_at IS NOT NULL
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def get_error_distribution(self, session_id: str | None = None) -> dict[str, int]:
        """Get error distribution by error type.

        Args:
            session_id: Optional session identifier (None = all sessions)

        Returns:
            Dict mapping error type to count
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if session_id:
                cursor.execute("""
                    SELECT
                        COALESCE(
                            CASE
                                WHEN error_message LIKE '%Network%' OR error_message LIKE '%timeout%' THEN 'Network Error'
                                WHEN error_message LIKE '%Extract%' OR error_message LIKE '%parsing%' THEN 'Extraction Error'
                                WHEN error_message LIKE '%Validat%' THEN 'Validation Error'
                                ELSE 'Unknown Error'
                            END,
                            'Unknown Error'
                        ) as error_type,
                        COUNT(*) as count
                    FROM census_batch_items
                    WHERE session_id = ?
                      AND status = 'error'
                      AND error_message IS NOT NULL
                    GROUP BY error_type
                """, (session_id,))
            else:
                cursor.execute("""
                    SELECT
                        COALESCE(
                            CASE
                                WHEN error_message LIKE '%Network%' OR error_message LIKE '%timeout%' THEN 'Network Error'
                                WHEN error_message LIKE '%Extract%' OR error_message LIKE '%parsing%' THEN 'Extraction Error'
                                WHEN error_message LIKE '%Validat%' THEN 'Validation Error'
                                ELSE 'Unknown Error'
                            END,
                            'Unknown Error'
                        ) as error_type,
                        COUNT(*) as count
                    FROM census_batch_items
                    WHERE status = 'error'
                      AND error_message IS NOT NULL
                    GROUP BY error_type
                """)

            return {row['error_type']: row['count'] for row in cursor.fetchall()}

    def get_all_sessions(self) -> list[dict[str, Any]]:
        """Get all Census batch sessions ordered by creation date.

        Returns:
            List of session data dicts
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM census_batch_sessions
                ORDER BY created_at DESC
            """)

            return [dict(row) for row in cursor.fetchall()]

    def get_photo_statistics(self, session_id: str | None = None) -> dict[str, Any]:
        """Get photo statistics including breakdown by photo type.

        Args:
            session_id: Optional session identifier (None = all sessions)

        Returns:
            Dict with total_photos, photos_by_type, items_with_photos
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get items with photos
            if session_id:
                cursor.execute("""
                    SELECT downloaded_image_paths, extracted_data
                    FROM census_batch_items
                    WHERE session_id = ?
                      AND downloaded_image_paths IS NOT NULL
                      AND downloaded_image_paths != '[]'
                """, (session_id,))
            else:
                cursor.execute("""
                    SELECT downloaded_image_paths, extracted_data
                    FROM census_batch_items
                    WHERE downloaded_image_paths IS NOT NULL
                      AND downloaded_image_paths != '[]'
                """)

            # Count photos by type
            photo_types: dict[str, int] = {}
            total_photos = 0
            items_with_photos = 0

            for row in cursor.fetchall():
                items_with_photos += 1

                # Count downloaded images
                if row['downloaded_image_paths']:
                    paths = json.loads(row['downloaded_image_paths'])
                    total_photos += len(paths)

                # Parse extracted data for photo types (if applicable)
                if row['extracted_data']:
                    try:
                        data = json.loads(row['extracted_data'])
                        photos = data.get('photos', [])
                        for photo in photos:
                            photo_type = photo.get('type', 'Unknown')
                            photo_types[photo_type] = photo_types.get(photo_type, 0) + 1
                    except (json.JSONDecodeError, KeyError):
                        pass

            return {
                'total_photos': total_photos,
                'items_with_photos': items_with_photos,
                'photos_by_type': photo_types,
            }

    def get_citation_statistics(
        self,
        rm_database_path: str,
        session_id: str | None = None
    ) -> dict[str, Any]:
        """Get citation statistics including breakdown by application type.

        Queries both batch state DB and RootsMagic DB to determine how
        citations are applied (to persons, events, families, etc.).

        Args:
            rm_database_path: Path to RootsMagic database
            session_id: Optional session identifier (None = all sessions)

        Returns:
            Dict with total_citations, citations_by_owner_type, items_with_citations
        """
        # Get citation IDs from batch state
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if session_id:
                cursor.execute("""
                    SELECT created_citation_id, created_source_id
                    FROM census_batch_items
                    WHERE session_id = ?
                      AND created_citation_id IS NOT NULL
                """, (session_id,))
            else:
                cursor.execute("""
                    SELECT created_citation_id, created_source_id
                    FROM census_batch_items
                    WHERE created_citation_id IS NOT NULL
                """)

            citation_ids = [row['created_citation_id'] for row in cursor.fetchall()]
            items_with_citations = len(citation_ids)

        if not citation_ids:
            return {
                'total_citations': 0,
                'items_with_citations': 0,
                'citations_by_owner_type': {},
            }

        # Query RootsMagic database for citation links
        rm_conn = sqlite3.connect(rm_database_path)
        rm_conn.row_factory = sqlite3.Row
        rm_cursor = rm_conn.cursor()

        try:
            # Get citation links
            placeholders = ','.join('?' * len(citation_ids))
            rm_cursor.execute(f"""
                SELECT OwnerType, COUNT(*) as count
                FROM CitationLinkTable
                WHERE CitationID IN ({placeholders})
                GROUP BY OwnerType
            """, citation_ids)

            # Map OwnerType to readable names
            owner_type_names = {
                0: 'Person',
                1: 'Family',
                2: 'Event',
                3: 'Source',
                4: 'Citation',
                5: 'Place',
                6: 'Name',
                7: 'MediaLink',
            }

            citations_by_owner_type = {}
            for row in rm_cursor.fetchall():
                owner_type_name = owner_type_names.get(row['OwnerType'], f'Type {row["OwnerType"]}')
                citations_by_owner_type[owner_type_name] = row['count']

        finally:
            rm_conn.close()

        return {
            'total_citations': items_with_citations,
            'items_with_citations': items_with_citations,
            'citations_by_owner_type': citations_by_owner_type,
        }

    # =========================================================================
    # Census-Specific Query Operations
    # =========================================================================

    def get_year_distribution(self, session_id: str | None = None) -> dict[int, int]:
        """Get distribution of items by census year.

        Args:
            session_id: Optional session identifier (None = all sessions)

        Returns:
            Dict mapping census year to count
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if session_id:
                cursor.execute("""
                    SELECT census_year, COUNT(*) as count
                    FROM census_batch_items
                    WHERE session_id = ?
                    GROUP BY census_year
                    ORDER BY census_year
                """, (session_id,))
            else:
                cursor.execute("""
                    SELECT census_year, COUNT(*) as count
                    FROM census_batch_items
                    GROUP BY census_year
                    ORDER BY census_year
                """)

            return {row['census_year']: row['count'] for row in cursor.fetchall()}

    def get_state_distribution(self, session_id: str | None = None) -> dict[str, int]:
        """Get distribution of items by US state.

        Args:
            session_id: Optional session identifier (None = all sessions)

        Returns:
            Dict mapping state abbreviation to count
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if session_id:
                cursor.execute("""
                    SELECT state, COUNT(*) as count
                    FROM census_batch_items
                    WHERE session_id = ? AND state IS NOT NULL
                    GROUP BY state
                    ORDER BY count DESC
                """, (session_id,))
            else:
                cursor.execute("""
                    SELECT state, COUNT(*) as count
                    FROM census_batch_items
                    WHERE state IS NOT NULL
                    GROUP BY state
                    ORDER BY count DESC
                """)

            return {row['state']: row['count'] for row in cursor.fetchall()}

    def get_county_distribution(
        self,
        state: str,
        session_id: str | None = None
    ) -> dict[str, int]:
        """Get distribution of items by county within a state.

        Args:
            state: US state abbreviation (e.g., "OH", "TX")
            session_id: Optional session identifier (None = all sessions)

        Returns:
            Dict mapping county name to count
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if session_id:
                cursor.execute("""
                    SELECT county, COUNT(*) as count
                    FROM census_batch_items
                    WHERE session_id = ? AND state = ? AND county IS NOT NULL
                    GROUP BY county
                    ORDER BY count DESC
                """, (session_id, state))
            else:
                cursor.execute("""
                    SELECT county, COUNT(*) as count
                    FROM census_batch_items
                    WHERE state = ? AND county IS NOT NULL
                    GROUP BY county
                    ORDER BY count DESC
                """, (state,))

            return {row['county']: row['count'] for row in cursor.fetchall()}

    def get_year_and_state_distribution(
        self,
        session_id: str | None = None
    ) -> dict[tuple[int, str], int]:
        """Get distribution of items by census year AND state.

        Useful for heatmaps showing year vs state coverage.

        Args:
            session_id: Optional session identifier (None = all sessions)

        Returns:
            Dict mapping (census_year, state) tuples to count
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if session_id:
                cursor.execute("""
                    SELECT census_year, state, COUNT(*) as count
                    FROM census_batch_items
                    WHERE session_id = ? AND state IS NOT NULL
                    GROUP BY census_year, state
                    ORDER BY census_year, state
                """, (session_id,))
            else:
                cursor.execute("""
                    SELECT census_year, state, COUNT(*) as count
                    FROM census_batch_items
                    WHERE state IS NOT NULL
                    GROUP BY census_year, state
                    ORDER BY census_year, state
                """)

            return {(row['census_year'], row['state']): row['count'] for row in cursor.fetchall()}
