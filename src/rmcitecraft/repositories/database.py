"""Database connection and management for RootsMagic .rmtree files."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from loguru import logger

from rmcitecraft.config import get_config


class DatabaseConnection:
    """Manages SQLite connection to RootsMagic database with RMNOCASE collation support."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        icu_extension_path: Optional[str] = None,
    ) -> None:
        """Initialize database connection manager.

        Args:
            db_path: Path to RootsMagic .rmtree file. If None, uses config.
            icu_extension_path: Path to ICU extension library. If None, uses config.
        """
        config = get_config()
        self.db_path = Path(db_path or config.rm_database_path)
        self.icu_extension_path = Path(
            icu_extension_path or config.sqlite_icu_extension
        )

        # Validate paths
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database file not found: {self.db_path}")
        if not self.icu_extension_path.exists():
            raise FileNotFoundError(
                f"ICU extension not found: {self.icu_extension_path}"
            )

        self._connection: Optional[sqlite3.Connection] = None

    def connect(self, read_only: bool = True) -> sqlite3.Connection:
        """Establish connection to RootsMagic database with RMNOCASE collation.

        Args:
            read_only: If True, open in read-only mode. Default is True for safety.

        Returns:
            SQLite connection object with RMNOCASE collation loaded.
        """
        # Close existing connection if any
        if self._connection:
            self._connection.close()

        # Construct connection URI for read-only mode
        uri = f"file:{self.db_path}?mode=ro" if read_only else str(self.db_path)

        # Connect to database
        self._connection = sqlite3.connect(
            uri, uri=read_only, check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row  # Enable column access by name

        try:
            # Load ICU extension for RMNOCASE collation
            self._connection.enable_load_extension(True)
            self._connection.load_extension(str(self.icu_extension_path))

            # Register RMNOCASE collation
            self._connection.execute(
                "SELECT icu_load_collation("
                "'en_US@colStrength=primary;caseLevel=off;normalization=on',"
                "'RMNOCASE'"
                ")"
            )

            self._connection.enable_load_extension(False)

            logger.info(
                f"Connected to RootsMagic database: {self.db_path} "
                f"(read_only={read_only})"
            )

        except sqlite3.Error as e:
            logger.error(f"Failed to load ICU extension: {e}")
            if self._connection:
                self._connection.close()
                self._connection = None
            raise

        return self._connection

    def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Database connection closed")

    @contextmanager
    def get_connection(
        self, read_only: bool = True
    ) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections.

        Args:
            read_only: If True, open in read-only mode.

        Yields:
            SQLite connection object.

        Example:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM CitationTable LIMIT 10")
        """
        conn = self.connect(read_only=read_only)
        try:
            yield conn
            if not read_only:
                conn.commit()
        except Exception as e:
            if not read_only:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            # Don't close here - allow reuse. Call close() explicitly when done.
            pass

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database transactions (read-write).

        Automatically commits on success, rolls back on error.

        Yields:
            SQLite connection object in read-write mode.

        Example:
            with db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE CitationTable SET Footnote = ? WHERE CitationID = ?",
                              (footnote, citation_id))
        """
        conn = self.connect(read_only=False)
        try:
            yield conn
            conn.commit()
            logger.debug("Transaction committed")
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction rolled back: {e}")
            raise
        finally:
            pass

    def test_connection(self) -> bool:
        """Test database connection and RMNOCASE collation.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Test RMNOCASE collation
                cursor.execute(
                    "SELECT Surname FROM NameTable "
                    "ORDER BY Surname COLLATE RMNOCASE LIMIT 1"
                )
                result = cursor.fetchone()
                if result:
                    logger.info("Database connection test successful")
                    return True
                return False
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False

    def __enter__(self) -> "DatabaseConnection":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore
        """Context manager exit."""
        self.close()
