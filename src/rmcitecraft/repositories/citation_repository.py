"""Repository for accessing citation data from RootsMagic database."""

import sqlite3
import xml.etree.ElementTree as ET

from loguru import logger

from rmcitecraft.repositories.database import DatabaseConnection


class CitationRepository:
    """Data access layer for RootsMagic citations."""

    def __init__(self, db: DatabaseConnection) -> None:
        """Initialize citation repository.

        Args:
            db: Database connection manager.
        """
        self.db = db

    @staticmethod
    def extract_field_from_blob(fields_blob: bytes, field_name: str) -> str | None:
        """Extract a field value from Fields BLOB XML.

        Args:
            fields_blob: XML BLOB from CitationTable.Fields or SourceTable.Fields
            field_name: Name of field to extract (e.g., "Page", "Footnote", "ShortFootnote", "Bibliography")

        Returns:
            Text from the specified field, or None if not found
        """
        if not fields_blob:
            return None

        try:
            # Remove UTF-8 BOM if present (EFBBBF)
            if fields_blob[:3] == b'\xef\xbb\xbf':
                fields_blob = fields_blob[3:]

            # Parse XML
            root = ET.fromstring(fields_blob)

            # Find Field with matching Name
            for field in root.findall('.//Field'):
                name_elem = field.find('Name')
                value_elem = field.find('Value')
                if name_elem is not None and value_elem is not None:
                    if name_elem.text == field_name:
                        return value_elem.text

            return None
        except Exception as e:
            logger.warning(f"Failed to parse Fields BLOB for {field_name}: {e}")
            return None

    @staticmethod
    def extract_freeform_text(fields_blob: bytes) -> str | None:
        """Extract citation text from Fields BLOB (for Free Form citations).

        This is a convenience wrapper around extract_field_from_blob for the "Page" field.

        Args:
            fields_blob: XML BLOB from CitationTable.Fields

        Returns:
            Text from the "Page" field, or None if not found
        """
        return CitationRepository.extract_field_from_blob(fields_blob, "Page")

    def get_citations_by_year(self, census_year: int) -> list[sqlite3.Row]:
        """Get all census citations for a specific year.

        Includes population schedules, slave schedules, and mortality schedules.

        Args:
            census_year: Census year (e.g., 1900, 1910, etc.)

        Returns:
            List of citation rows matching the census year.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    c.CitationID,
                    c.CitationName,
                    c.ActualText,
                    c.RefNumber,
                    c.Footnote,
                    c.ShortFootnote,
                    c.Bibliography,
                    c.Fields AS CitationFields,
                    s.Name AS SourceName,
                    s.TemplateID,
                    s.Fields AS SourceFields
                FROM CitationTable c
                JOIN SourceTable s ON c.SourceID = s.SourceID
                WHERE s.Name LIKE ?
                   OR s.Name LIKE ?
                   OR s.Name LIKE ?
                ORDER BY s.Name COLLATE RMNOCASE
                """,
                (
                    f"Fed Census: {census_year}%",
                    f"Fed Census Slave Schedule: {census_year}%",
                    f"Fed Census Mortality Schedule: {census_year}%",
                ),
            )
            results = cursor.fetchall()
            logger.debug(f"Found {len(results)} citations for year {census_year}")
            return results

    def get_citation_by_id(self, citation_id: int) -> sqlite3.Row | None:
        """Get a single citation by ID.

        Args:
            citation_id: Citation ID.

        Returns:
            Citation row or None if not found.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    c.CitationID,
                    c.CitationName,
                    c.ActualText,
                    c.RefNumber,
                    c.Footnote,
                    c.ShortFootnote,
                    c.Bibliography,
                    c.Comments,
                    s.Name AS SourceName,
                    s.SourceID
                FROM CitationTable c
                JOIN SourceTable s ON c.SourceID = s.SourceID
                WHERE c.CitationID = ?
                """,
                (citation_id,),
            )
            return cursor.fetchone()

    def update_citation_fields(
        self,
        citation_id: int,
        footnote: str,
        short_footnote: str,
        bibliography: str,
    ) -> bool:
        """Update citation formatted fields.

        Args:
            citation_id: Citation ID to update.
            footnote: Formatted footnote text.
            short_footnote: Formatted short footnote text.
            bibliography: Formatted bibliography text.

        Returns:
            True if update successful, False otherwise.
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE CitationTable
                    SET Footnote = ?,
                        ShortFootnote = ?,
                        Bibliography = ?
                    WHERE CitationID = ?
                    """,
                    (footnote, short_footnote, bibliography, citation_id),
                )
                rows_affected = cursor.rowcount

                if rows_affected > 0:
                    logger.info(f"Updated citation {citation_id}")
                    return True
                else:
                    logger.warning(f"No citation found with ID {citation_id}")
                    return False

        except sqlite3.Error as e:
            logger.error(f"Failed to update citation {citation_id}: {e}")
            return False

    def get_all_census_years(self) -> list[int]:
        """Get list of all census years present in the database.

        Returns:
            Sorted list of unique census years.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT substr(s.Name, 13, 4) AS Year
                FROM SourceTable s
                WHERE s.Name LIKE 'Fed Census: ____,%'
                ORDER BY Year
                """
            )
            results = cursor.fetchall()
            years = [int(row[0]) for row in results if row[0].isdigit()]
            logger.debug(f"Found census years: {years}")
            return years

    def citation_has_media(self, citation_id: int) -> bool:
        """Check if citation has linked media.

        Args:
            citation_id: Citation ID.

        Returns:
            True if citation has media linked, False otherwise.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM MediaLinkTable
                WHERE OwnerType = 4 AND OwnerID = ?
                """,
                (citation_id,),
            )
            count = cursor.fetchone()[0]
            return count > 0
