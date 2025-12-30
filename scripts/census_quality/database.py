"""Database helper functions for census quality checking.

Contains functions for extracting data from RootsMagic database.
"""

import re
import sqlite3


def extract_field_from_blob(fields_blob: bytes | str | None, field_name: str) -> str:
    """Extract a field value from the Fields BLOB."""
    if not fields_blob:
        return ""
    try:
        if isinstance(fields_blob, bytes):
            text = fields_blob.decode("utf-8", errors="ignore")
        else:
            text = fields_blob
        pattern = rf"<Name>{field_name}</Name>\s*<Value>(.*?)</Value>"
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1) if match else ""
    except Exception:
        return ""


def get_sources_for_year(conn: sqlite3.Connection, year_key: int | str) -> list[dict]:
    """Get all census sources for a specific year with media counts.

    Args:
        conn: Database connection
        year_key: Either an integer year (1850, 1860, etc.) or a string key
                  like "1860-slave" for slave schedules.
    """
    cursor = conn.cursor()

    # Determine source name prefix based on year_key
    if isinstance(year_key, str) and year_key.endswith("-slave"):
        year = int(year_key.replace("-slave", ""))
        name_prefix = f"Fed Census Slave Schedule: {year},%"
    elif isinstance(year_key, str) and year_key.endswith("-mortality"):
        year = int(year_key.replace("-mortality", ""))
        name_prefix = f"Fed Census Mortality Schedule: {year},%"
    else:
        name_prefix = f"Fed Census: {year_key},%"

    cursor.execute(
        """
        SELECT
            s.SourceID,
            s.Name,
            s.Fields,
            (SELECT COUNT(*) FROM MediaLinkTable ml
             WHERE ml.OwnerID = s.SourceID AND ml.OwnerType = 3) as media_count
        FROM SourceTable s
        WHERE s.Name LIKE ?
        ORDER BY s.SourceID
    """,
        (name_prefix,),
    )

    sources = []
    for row in cursor.fetchall():
        source_id, name, fields_blob, media_count = row

        footnote = extract_field_from_blob(fields_blob, "Footnote")
        short_footnote = extract_field_from_blob(fields_blob, "ShortFootnote")
        bibliography = extract_field_from_blob(fields_blob, "Bibliography")

        sources.append(
            {
                "source_id": source_id,
                "name": name,
                "footnote": footnote,
                "short_footnote": short_footnote,
                "bibliography": bibliography,
                "media_count": media_count,
            }
        )

    return sources


def get_citation_quality_counts(
    conn: sqlite3.Connection, year_key: int | str
) -> dict[str, int]:
    """Get citation quality value counts for a census year.

    Args:
        conn: Database connection
        year_key: Either an integer year (1850, 1860, etc.) or a string key
                  like "1860-slave" for slave schedules.
    """
    cursor = conn.cursor()

    # Determine source name prefix based on year_key
    if isinstance(year_key, str) and year_key.endswith("-slave"):
        year = int(year_key.replace("-slave", ""))
        name_prefix = f"Fed Census Slave Schedule: {year},%"
    elif isinstance(year_key, str) and year_key.endswith("-mortality"):
        year = int(year_key.replace("-mortality", ""))
        name_prefix = f"Fed Census Mortality Schedule: {year},%"
    else:
        name_prefix = f"Fed Census: {year_key},%"

    cursor.execute(
        """
        SELECT cl.Quality, COUNT(*) as cnt
        FROM CitationLinkTable cl
        JOIN CitationTable c ON c.CitationID = cl.CitationID
        JOIN SourceTable s ON s.SourceID = c.SourceID
        WHERE s.Name LIKE ?
        GROUP BY cl.Quality
    """,
        (name_prefix,),
    )

    return {row[0]: row[1] for row in cursor.fetchall()}
