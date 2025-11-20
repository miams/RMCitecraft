"""Dashboard queries that drill down into RootsMagic database.

These queries provide detailed information about persons, families, and citations
for display in the dashboard item detail panel.
"""

import sqlite3
from pathlib import Path
from typing import Any


def _get_db_connection(db_path: str) -> sqlite3.Connection:
    """Create database connection with ICU extension loaded.

    Args:
        db_path: Path to RootsMagic database

    Returns:
        Connection with ICU extension and RMNOCASE collation
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Load ICU extension for RMNOCASE collation
    conn.enable_load_extension(True)
    try:
        conn.load_extension('./sqlite-extension/icu.dylib')
        conn.execute(
            "SELECT icu_load_collation('en_US@colStrength=primary;caseLevel=off;normalization=on','RMNOCASE')"
        )
    finally:
        conn.enable_load_extension(False)

    return conn


def get_person_details(db_path: str, person_id: int) -> dict[str, Any] | None:
    """Get person details from RootsMagic database.

    Args:
        db_path: Path to RootsMagic database
        person_id: RootsMagic PersonID

    Returns:
        Dict with person details or None if not found
    """
    conn = _get_db_connection(db_path)
    cursor = conn.cursor()

    try:
        # Get person record with primary name
        cursor.execute("""
            SELECT
                p.PersonID,
                p.Sex,
                n.Surname,
                n.Given,
                n.Prefix,
                n.Suffix
            FROM PersonTable p
            LEFT JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
            WHERE p.PersonID = ?
        """, (person_id,))

        row = cursor.fetchone()
        if not row:
            return None

        person = dict(row)

        # Get birth event details
        cursor.execute("""
            SELECT
                e.Date as birth_date,
                pl.Name as birth_place
            FROM EventTable e
            LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
            WHERE e.OwnerID = ? AND e.OwnerType = 0 AND e.EventType = 1
        """, (person_id,))
        birth_row = cursor.fetchone()
        if birth_row:
            person['birth_date'] = birth_row['birth_date']
            person['birth_place'] = birth_row['birth_place']
        else:
            person['birth_date'] = None
            person['birth_place'] = None

        # Get death event details
        cursor.execute("""
            SELECT
                e.Date as death_date,
                pl.Name as death_place
            FROM EventTable e
            LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
            WHERE e.OwnerID = ? AND e.OwnerType = 0 AND e.EventType = 2
        """, (person_id,))
        death_row = cursor.fetchone()
        if death_row:
            person['death_date'] = death_row['death_date']
            person['death_place'] = death_row['death_place']
        else:
            person['death_date'] = None
            person['death_place'] = None

        return person

    finally:
        conn.close()


def get_person_families(db_path: str, person_id: int) -> dict[str, list[dict]]:
    """Get family relationships for person.

    Args:
        db_path: Path to RootsMagic database
        person_id: RootsMagic PersonID

    Returns:
        Dict with 'spouse_families' and 'parent_families' lists
    """
    conn = _get_db_connection(db_path)
    cursor = conn.cursor()

    families = {'spouse_families': [], 'parent_families': []}

    try:
        # Families where person is parent (spouse families)
        cursor.execute("""
            SELECT
                f.FamilyID,
                f.FatherID,
                f.MotherID,
                father.Surname as father_surname,
                father.Given as father_given,
                mother.Surname as mother_surname,
                mother.Given as mother_given
            FROM FamilyTable f
            LEFT JOIN NameTable father ON f.FatherID = father.OwnerID AND father.IsPrimary = 1
            LEFT JOIN NameTable mother ON f.MotherID = mother.OwnerID AND mother.IsPrimary = 1
            WHERE f.FatherID = ? OR f.MotherID = ?
        """, (person_id, person_id))

        families['spouse_families'] = [dict(row) for row in cursor.fetchall()]

        # Families where person is child (parent families)
        cursor.execute("""
            SELECT
                f.FamilyID,
                f.FatherID,
                f.MotherID,
                father.Surname as father_surname,
                father.Given as father_given,
                mother.Surname as mother_surname,
                mother.Given as mother_given
            FROM ChildTable c
            JOIN FamilyTable f ON c.FamilyID = f.FamilyID
            LEFT JOIN NameTable father ON f.FatherID = father.OwnerID AND father.IsPrimary = 1
            LEFT JOIN NameTable mother ON f.MotherID = mother.OwnerID AND mother.IsPrimary = 1
            WHERE c.ChildID = ?
        """, (person_id,))

        families['parent_families'] = [dict(row) for row in cursor.fetchall()]

        return families

    finally:
        conn.close()


def get_person_citations(db_path: str, person_id: int) -> list[dict[str, Any]]:
    """Get all citations for person.

    Args:
        db_path: Path to RootsMagic database
        person_id: RootsMagic PersonID

    Returns:
        List of citation dicts
    """
    conn = _get_db_connection(db_path)
    cursor = conn.cursor()

    try:
        # Direct person citations (OwnerType = 0)
        cursor.execute("""
            SELECT
                c.CitationID,
                c.CitationName,
                s.Name as source_name,
                s.SourceID,
                cl.OwnerType
            FROM CitationLinkTable cl
            JOIN CitationTable c ON cl.CitationID = c.CitationID
            JOIN SourceTable s ON c.SourceID = s.SourceID
            WHERE cl.OwnerType = 0 AND cl.OwnerID = ?
            ORDER BY s.Name COLLATE RMNOCASE
        """, (person_id,))

        return [dict(row) for row in cursor.fetchall()]

    finally:
        conn.close()


def get_source_details(db_path: str, source_id: int) -> dict[str, Any] | None:
    """Get source details including citation count.

    Args:
        db_path: Path to RootsMagic database
        source_id: RootsMagic SourceID

    Returns:
        Dict with source details or None if not found
    """
    conn = _get_db_connection(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                s.SourceID,
                s.Name,
                s.TemplateID,
                COUNT(c.CitationID) as citation_count
            FROM SourceTable s
            LEFT JOIN CitationTable c ON s.SourceID = c.SourceID
            WHERE s.SourceID = ?
            GROUP BY s.SourceID
        """, (source_id,))

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    finally:
        conn.close()
