#!/usr/bin/env python3
"""
Example: Using RMNOCASE Collation in Python with RootsMagic Databases

RootsMagic uses a proprietary RMNOCASE collation sequence for case-insensitive
sorting. This example demonstrates how to load the ICU extension in Python to
enable RMNOCASE support when querying RootsMagic databases.

Prerequisites:
- ICU extension compiled for your platform (icu.dylib on macOS, icu.so on Linux)
- Modern SQLite version with extension support
- Python sqlite3 module (included in standard library)

Usage:
    python3 sqlite-extension/python_example.py
"""

import sqlite3
import sys


def connect_rmtree(db_path, extension_path="./sqlite-extension/icu.dylib"):
    """
    Connect to RootsMagic database with RMNOCASE collation support.

    Args:
        db_path: Path to .rmtree database file
        extension_path: Path to ICU extension library

    Returns:
        sqlite3.Connection object with RMNOCASE collation registered

    Raises:
        sqlite3.OperationalError: If extension cannot be loaded
    """
    conn = sqlite3.connect(db_path)

    # Enable extension loading
    conn.enable_load_extension(True)

    try:
        # Load ICU extension
        conn.load_extension(extension_path)

        # Register RMNOCASE collation using ICU
        # Parameters:
        #   - en_US: English locale
        #   - colStrength=primary: Case-insensitive comparison
        #   - caseLevel=off: Ignore case differences
        #   - normalization=on: Normalize Unicode characters
        conn.execute(
            "SELECT icu_load_collation(" "'en_US@colStrength=primary;caseLevel=off;normalization=on'," "'RMNOCASE')"
        )
    finally:
        # Disable extension loading (security best practice)
        conn.enable_load_extension(False)

    return conn


def example_queries():
    """Demonstrate various queries using RMNOCASE collation."""

    # Connect to database with RMNOCASE support
    conn = connect_rmtree("data/Iiams.rmtree")
    cursor = conn.cursor()

    print("=" * 80)
    print("RootsMagic Database Query Examples with RMNOCASE Collation")
    print("=" * 80)

    # Example 1: Count records in a table
    print("\n1. Count source templates:")
    cursor.execute("SELECT COUNT(*) FROM SourceTemplateTable")
    count = cursor.fetchone()[0]
    print(f"   Total templates: {count}")

    # Example 2: Order by text field with RMNOCASE
    print("\n2. Get surnames ordered case-insensitively:")
    cursor.execute(
        """
        SELECT DISTINCT Surname
        FROM NameTable
        WHERE Surname IS NOT NULL AND Surname != ''
        ORDER BY Surname COLLATE RMNOCASE
        LIMIT 10
    """
    )
    for row in cursor.fetchall():
        print(f"   - {row[0]}")

    # Example 3: Join tables with RMNOCASE fields
    print("\n3. Template usage statistics:")
    cursor.execute(
        """
        SELECT
            st.TemplateID,
            st.Name,
            COUNT(s.SourceID) as SourceCount
        FROM SourceTemplateTable st
        LEFT JOIN SourceTable s ON st.TemplateID = s.TemplateID
        WHERE st.TemplateID > 0
        GROUP BY st.TemplateID, st.Name
        HAVING COUNT(s.SourceID) > 0
        ORDER BY SourceCount DESC
        LIMIT 5
    """
    )
    print(f"   {'Template ID':<12} {'Source Count':<12} Template Name")
    print(f"   {'-'*12} {'-'*12} {'-'*40}")
    for tmpl_id, name, count in cursor.fetchall():
        print(f"   {tmpl_id:<12} {count:<12} {name}")

    # Example 4: Search with case-insensitive LIKE
    print("\n4. Find people with surname containing 'iams' (case-insensitive):")
    cursor.execute(
        """
        SELECT DISTINCT Surname, Given
        FROM NameTable
        WHERE Surname LIKE '%iams%' COLLATE RMNOCASE
        AND IsPrimary = 1
        LIMIT 5
    """
    )
    for surname, given in cursor.fetchall():
        print(f"   - {given} {surname}")

    # Example 5: Complex query with multiple joins
    print("\n5. Citations by template type:")
    cursor.execute(
        """
        SELECT
            st.Name as TemplateName,
            COUNT(c.CitationID) as CitationCount
        FROM CitationTable c
        JOIN SourceTable s ON c.SourceID = s.SourceID
        JOIN SourceTemplateTable st ON s.TemplateID = st.TemplateID
        WHERE s.TemplateID > 0
        GROUP BY st.TemplateID, st.Name
        ORDER BY CitationCount DESC
        LIMIT 5
    """
    )
    print(f"   {'Citations':<12} Template Name")
    print(f"   {'-'*12} {'-'*40}")
    for name, count in cursor.fetchall():
        print(f"   {count:<12} {name}")

    conn.close()
    print("\n" + "=" * 80)
    print("✓ All queries completed successfully")
    print("=" * 80)


def main():
    """Main entry point."""
    try:
        example_queries()
    except sqlite3.OperationalError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("\nPossible issues:", file=sys.stderr)
        print("1. ICU extension not found at ./sqlite-extension/icu.dylib", file=sys.stderr)
        print("2. Database not found at data/Iiams.rmtree", file=sys.stderr)
        print("3. SQLite not compiled with extension support", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
