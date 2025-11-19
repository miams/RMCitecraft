"""RootsMagic database connection with RMNOCASE collation support.

This module provides connection utilities for RootsMagic databases,
including ICU extension loading for the RMNOCASE collation.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger


def connect_rmtree(
    db_path: str | Path,
    extension_path: str | Path = "./sqlite-extension/icu.dylib",
    read_only: bool = True,
) -> sqlite3.Connection:
    """Connect to RootsMagic database with RMNOCASE collation support.

    CRITICAL: Always use this function instead of raw sqlite3.connect() to ensure
    RMNOCASE collation is available for text fields (Surname, Given, Name, etc.).

    Args:
        db_path: Path to .rmtree database file
        extension_path: Path to ICU extension library (default: ./sqlite-extension/icu.dylib)
        read_only: Open database in read-only mode (default: True for safety)

    Returns:
        sqlite3.Connection object with RMNOCASE collation registered

    Raises:
        sqlite3.OperationalError: If extension cannot be loaded
        FileNotFoundError: If database or extension file not found
    """
    db_path = Path(db_path)
    extension_path = Path(extension_path)

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    if not extension_path.exists():
        raise FileNotFoundError(f"ICU extension not found: {extension_path}")

    logger.debug(f"Connecting to RootsMagic database: {db_path} (read_only={read_only})")

    # Build URI for read-only mode
    if read_only:
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(str(db_path))

    # Enable extension loading
    conn.enable_load_extension(True)

    try:
        # Load ICU extension
        conn.load_extension(str(extension_path))
        logger.debug(f"Loaded ICU extension from {extension_path}")

        # Register RMNOCASE collation using ICU
        # Parameters:
        #   - en_US: English locale
        #   - colStrength=primary: Case-insensitive comparison
        #   - caseLevel=off: Ignore case differences
        #   - normalization=on: Normalize Unicode characters
        conn.execute(
            "SELECT icu_load_collation("
            "'en_US@colStrength=primary;caseLevel=off;normalization=on',"
            "'RMNOCASE')"
        )
        logger.debug("Registered RMNOCASE collation")

    finally:
        # Disable extension loading (security best practice)
        conn.enable_load_extension(False)

    return conn


@contextmanager
def atomic_batch_operation(
    rm_db_path: str | Path,
    state_db_path: str | Path,
    extension_path: str | Path = "./sqlite-extension/icu.dylib",
):
    """Context manager for atomic batch operations across both databases.

    Ensures that operations on RootsMagic database and state database are
    atomic - either both succeed or both are rolled back.

    CRITICAL: This manages TWO separate databases:
    1. RootsMagic database (rm_db_path) - genealogy data
    2. State database (state_db_path) - batch processing state

    Args:
        rm_db_path: Path to RootsMagic .rmtree database
        state_db_path: Path to batch state database
        extension_path: Path to ICU extension for RMNOCASE collation

    Yields:
        Tuple of (rm_conn, state_conn, created_records tracker)

    Example:
        ```python
        with atomic_batch_operation(rm_db, state_db) as (rm_conn, state_conn, tracker):
            # Create citation in RootsMagic DB
            cursor = rm_conn.cursor()
            cursor.execute("INSERT INTO CitationTable (...) VALUES (...)")
            citation_id = cursor.lastrowid
            tracker['citation_id'] = citation_id

            # Update state DB
            cursor = state_conn.cursor()
            cursor.execute("UPDATE batch_items SET status = 'complete' WHERE id = ?", (item_id,))

            # Both commits happen automatically on success
            # Both rollback automatically on exception
        ```
    """
    # Track created records for detailed logging on rollback
    created_records: dict[str, Any] = {}

    # Connect to both databases
    rm_conn = connect_rmtree(rm_db_path, extension_path, read_only=False)
    state_conn = sqlite3.connect(str(Path(state_db_path).expanduser()))

    try:
        # Begin transactions on both databases
        rm_conn.execute("BEGIN IMMEDIATE")
        state_conn.execute("BEGIN IMMEDIATE")

        logger.debug("Started atomic transaction on both databases")

        # Yield connections and tracker to caller
        yield rm_conn, state_conn, created_records

        # Commit both databases if no exception
        rm_conn.commit()
        state_conn.commit()

        logger.info(
            f"Committed atomic transaction successfully "
            f"(created: {', '.join(created_records.keys())})"
        )

    except Exception as e:
        # Rollback both databases on any error
        logger.error(f"Rolling back atomic transaction due to error: {e}")

        try:
            rm_conn.rollback()
            logger.debug("Rolled back RootsMagic database")
        except Exception as rb_error:
            logger.error(f"Error rolling back RootsMagic database: {rb_error}")

        try:
            state_conn.rollback()
            logger.debug("Rolled back state database")
        except Exception as rb_error:
            logger.error(f"Error rolling back state database: {rb_error}")

        # Log what was attempted
        if created_records:
            logger.warning(
                f"Rolled back creation of: {', '.join(created_records.keys())}"
            )

        # Re-raise original exception
        raise

    finally:
        # Close connections
        rm_conn.close()
        state_conn.close()
        logger.debug("Closed database connections")


class RollbackError(Exception):
    """Exception to explicitly trigger rollback of atomic operation."""

    pass
