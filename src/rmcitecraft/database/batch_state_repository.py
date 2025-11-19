"""
Batch state repository for Find a Grave batch processing.

Manages state persistence in separate SQLite database (~/.rmcitecraft/batch_state.db)
to enable crash recovery, resume capability, and performance tracking.

CRITICAL: This database is SEPARATE from RootsMagic database to avoid confusion.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger


class BatchStateRepository:
    """Repository for batch processing state persistence."""

    def __init__(self, db_path: str = "~/.rmcitecraft/batch_state.db"):
        """Initialize repository with state database path.

        Args:
            db_path: Path to state database (default: ~/.rmcitecraft/batch_state.db)
        """
        self.db_path = Path(db_path).expanduser()
        self._ensure_database_exists()

    def _ensure_database_exists(self) -> None:
        """Create database directory and initialize schema if needed."""
        # Create directory
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check if schema exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='schema_version'
            """)

            if not cursor.fetchone():
                logger.info(f"Initializing batch state database: {self.db_path}")
                self._run_migrations(conn)
            else:
                logger.debug(f"Batch state database already initialized: {self.db_path}")

    def _run_migrations(self, conn: sqlite3.Connection) -> None:
        """Run database migrations.

        Args:
            conn: Database connection
        """
        migrations_dir = Path(__file__).parent.parent.parent.parent / "migrations"
        migration_file = migrations_dir / "001_create_batch_state_tables.sql"

        if not migration_file.exists():
            raise FileNotFoundError(f"Migration file not found: {migration_file}")

        with open(migration_file) as f:
            migration_sql = f.read()

        conn.executescript(migration_sql)
        conn.commit()
        logger.info("Applied migration 001_create_batch_state_tables.sql")

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

    # =========================================================================
    # Session Operations
    # =========================================================================

    def create_session(
        self,
        session_id: str,
        total_items: int,
        config_snapshot: dict[str, Any] | None = None,
    ) -> None:
        """Create new batch session.

        Args:
            session_id: Unique session identifier
            total_items: Total number of items in batch
            config_snapshot: Configuration settings snapshot
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO batch_sessions (
                    session_id, created_at, status, total_items,
                    completed_count, error_count, config_snapshot
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                datetime.now(timezone.utc),
                'queued',
                total_items,
                0,
                0,
                json.dumps(config_snapshot) if config_snapshot else None,
            ))
            conn.commit()
            logger.info(f"Created batch session: {session_id} ({total_items} items)")

    def start_session(self, session_id: str) -> None:
        """Mark session as started.

        Args:
            session_id: Session identifier
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE batch_sessions
                SET started_at = ?, status = 'running'
                WHERE session_id = ?
            """, (datetime.now(timezone.utc), session_id))
            conn.commit()
            logger.info(f"Started batch session: {session_id}")

    def complete_session(self, session_id: str) -> None:
        """Mark session as completed.

        Args:
            session_id: Session identifier
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE batch_sessions
                SET completed_at = ?, status = 'completed'
                WHERE session_id = ?
            """, (datetime.now(timezone.utc), session_id))
            conn.commit()
            logger.info(f"Completed batch session: {session_id}")

    def pause_session(self, session_id: str) -> None:
        """Mark session as paused.

        Args:
            session_id: Session identifier
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE batch_sessions
                SET status = 'paused'
                WHERE session_id = ?
            """, (session_id,))
            conn.commit()
            logger.info(f"Paused batch session: {session_id}")

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
                    UPDATE batch_sessions
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
                SELECT * FROM batch_sessions WHERE session_id = ?
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
                SELECT * FROM batch_sessions
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
        memorial_id: str,
        memorial_url: str,
        person_name: str,
    ) -> int:
        """Create batch item.

        Args:
            session_id: Session identifier
            person_id: RootsMagic person ID
            memorial_id: Find a Grave memorial ID
            memorial_url: Find a Grave memorial URL
            person_name: Person's full name

        Returns:
            Item ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc)

            cursor.execute("""
                INSERT INTO batch_items (
                    session_id, person_id, memorial_id, memorial_url, person_name,
                    status, retry_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, person_id, memorial_id, memorial_url, person_name,
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
            status: New status
            error_message: Error message if status is 'error'
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE batch_items
                SET status = ?, error_message = ?, updated_at = ?, last_attempt_at = ?
                WHERE id = ?
            """, (status, error_message, datetime.now(timezone.utc),
                  datetime.now(timezone.utc), item_id))
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
                UPDATE batch_items
                SET retry_count = retry_count + 1, updated_at = ?
                WHERE id = ?
            """, (datetime.now(timezone.utc), item_id))
            conn.commit()

            cursor.execute("SELECT retry_count FROM batch_items WHERE id = ?", (item_id,))
            row = cursor.fetchone()
            return row[0] if row else 0

    def update_item_extraction(
        self,
        item_id: int,
        extracted_data: dict[str, Any],
    ) -> None:
        """Update item with extracted memorial data.

        Args:
            item_id: Item ID
            extracted_data: Extracted memorial data
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE batch_items
                SET extracted_data = ?, status = 'extracted', updated_at = ?
                WHERE id = ?
            """, (json.dumps(extracted_data), datetime.now(timezone.utc), item_id))
            conn.commit()

    def update_item_citation(
        self,
        item_id: int,
        citation_id: int,
        source_id: int,
        burial_event_id: int | None = None,
    ) -> None:
        """Update item with created citation IDs.

        Args:
            item_id: Item ID
            citation_id: Created citation ID
            source_id: Created source ID
            burial_event_id: Created burial event ID (if any)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE batch_items
                SET created_citation_id = ?, created_source_id = ?,
                    created_burial_event_id = ?, status = 'created_citation', updated_at = ?
                WHERE id = ?
            """, (citation_id, source_id, burial_event_id,
                  datetime.now(timezone.utc), item_id))
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
                UPDATE batch_items
                SET downloaded_image_paths = ?, updated_at = ?
                WHERE id = ?
            """, (json.dumps(image_paths), datetime.now(timezone.utc), item_id))
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
            cursor.execute("SELECT * FROM batch_items WHERE id = ?", (item_id,))

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
                    SELECT * FROM batch_items
                    WHERE session_id = ? AND status = ?
                    ORDER BY id
                """, (session_id, status))
            else:
                cursor.execute("""
                    SELECT * FROM batch_items
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
                INSERT OR REPLACE INTO batch_checkpoints (
                    session_id, last_processed_item_id, last_processed_person_id, checkpoint_at
                ) VALUES (?, ?, ?, ?)
            """, (session_id, last_processed_item_id, last_processed_person_id,
                  datetime.now(timezone.utc)))
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
                SELECT * FROM batch_checkpoints WHERE session_id = ?
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
        """Record performance metric.

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
                    timestamp, operation, duration_ms, success, session_id
                ) VALUES (?, ?, ?, ?, ?)
            """, (datetime.now(timezone.utc), operation, duration_ms, success, session_id))
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
                    WHERE operation = ? AND success = 1
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (operation, limit))
            else:
                cursor.execute("""
                    SELECT duration_ms FROM performance_metrics
                    WHERE operation = ?
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
                WHERE session_id = ?
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
