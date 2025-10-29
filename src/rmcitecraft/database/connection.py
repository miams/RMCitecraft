"""RootsMagic database connection with RMNOCASE collation support.

This module provides connection utilities for RootsMagic databases,
including ICU extension loading for the RMNOCASE collation.
"""

import sqlite3
from pathlib import Path

from loguru import logger


def connect_rmtree(
    db_path: str | Path, extension_path: str | Path = "./sqlite-extension/icu.dylib"
) -> sqlite3.Connection:
    """Connect to RootsMagic database with RMNOCASE collation support.

    CRITICAL: Always use this function instead of raw sqlite3.connect() to ensure
    RMNOCASE collation is available for text fields (Surname, Given, Name, etc.).

    Args:
        db_path: Path to .rmtree database file
        extension_path: Path to ICU extension library (default: ./sqlite-extension/icu.dylib)

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

    logger.debug(f"Connecting to RootsMagic database: {db_path}")

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
