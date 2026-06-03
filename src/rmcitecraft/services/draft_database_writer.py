"""Service for writing draft registration data to RootsMagic database."""

from typing import Optional, Tuple
from pathlib import Path
import sqlite3
from loguru import logger

from rmcitecraft.database.connection import connect_rmtree
from rmcitecraft.models.citation_data import SourceData, CitationData


class DraftDatabaseWriter:
    """Write draft registration citations and sources to RootsMagic database.

    Handles:
    - Creating/finding sources in SourceTable
    - Creating citations in CitationTable
    - Linking citations to persons via CitationLinkTable
    - Duplicate detection
    - Transaction management for data integrity
    """

    def __init__(self, db_path: Path, read_only: bool = False):
        """Initialize the database writer.

        Args:
            db_path: Path to RootsMagic database
            read_only: If True, open database in read-only mode
        """
        self.db_path = db_path
        self.read_only = read_only
        self._conn: Optional[sqlite3.Connection] = None

    def __enter__(self):
        """Context manager entry - open database connection."""
        self._conn = connect_rmtree(self.db_path, read_only=self.read_only)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close database connection."""
        if self._conn:
            if exc_type is None and not self.read_only:
                self._conn.commit()
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Get database connection (must be used within context manager)."""
        if self._conn is None:
            raise RuntimeError("Database not connected. Use 'with DraftDatabaseWriter(...) as writer:'")
        return self._conn

    def create_or_find_source(self, source_data: SourceData) -> Tuple[int, bool]:
        """Create a new source or find existing one.

        Args:
            source_data: Source data to create/find

        Returns:
            Tuple of (source_id, created) where created=True if new source was created

        Raises:
            RuntimeError: If database is read-only
        """
        if self.read_only:
            raise RuntimeError("Cannot create source in read-only mode")

        # Check for duplicate first
        existing_id = self.check_duplicate_source(source_data)
        if existing_id:
            logger.info(f"Found existing source: {existing_id} - {source_data.name}")
            return existing_id, False

        # Create new source
        cursor = self.conn.cursor()

        # Get next SourceID
        cursor.execute("SELECT IFNULL(MAX(SourceID), 0) + 1 FROM SourceTable")
        source_id = cursor.fetchone()[0]

        # Get current timestamp for UTCModDate
        cursor.execute("SELECT julianday('now') - 2415018.5")
        utc_mod_date = cursor.fetchone()[0]

        # Insert source
        cursor.execute("""
            INSERT INTO SourceTable (
                SourceID, Name, RefNumber, ActualText, Comments,
                IsPrivate, TemplateID, Fields, UTCModDate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            source_id,
            source_data.name,
            source_data.ref_number or "",
            "",  # ActualText
            source_data.comments or "",
            0,  # IsPrivate
            source_data.template_id,
            source_data.fields_blob,
            utc_mod_date
        ))

        logger.info(f"Created new source: {source_id} - {source_data.name}")
        return source_id, True

    def check_duplicate_source(self, source_data: SourceData) -> Optional[int]:
        """Check if a source with the same name already exists.

        Args:
            source_data: Source data to check

        Returns:
            SourceID if duplicate found, None otherwise
        """
        cursor = self.conn.cursor()

        # Check for exact name match
        cursor.execute("""
            SELECT SourceID FROM SourceTable
            WHERE Name = ? COLLATE RMNOCASE
            LIMIT 1
        """, (source_data.name,))

        result = cursor.fetchone()
        return result[0] if result else None

    def check_duplicate_source_by_url(self, url: str) -> Optional[int]:
        """Check if a source with the given URL already exists.

        Used for AncestryLibrary sources where we match by URL.

        Args:
            url: URL to search for in ActualText or RefNumber fields

        Returns:
            SourceID if duplicate found, None otherwise
        """
        cursor = self.conn.cursor()

        # Check for URL in ActualText or RefNumber fields
        cursor.execute("""
            SELECT SourceID FROM SourceTable
            WHERE ActualText LIKE ? OR RefNumber LIKE ?
            LIMIT 1
        """, (f'%{url}%', f'%{url}%'))

        result = cursor.fetchone()
        return result[0] if result else None

    def create_citation(self, citation_data: CitationData) -> int:
        """Create a new citation.

        Args:
            citation_data: Citation data to create

        Returns:
            CitationID of created citation

        Raises:
            RuntimeError: If database is read-only
        """
        if self.read_only:
            raise RuntimeError("Cannot create citation in read-only mode")

        cursor = self.conn.cursor()

        # Get next CitationID
        cursor.execute("SELECT IFNULL(MAX(CitationID), 0) + 1 FROM CitationTable")
        citation_id = cursor.fetchone()[0]

        # Get current timestamp
        cursor.execute("SELECT julianday('now') - 2415018.5")
        utc_mod_date = cursor.fetchone()[0]

        # Insert citation
        cursor.execute("""
            INSERT INTO CitationTable (
                CitationID, SourceID, Comments, ActualText, RefNumber,
                Footnote, ShortFootnote, Bibliography,
                Fields, UTCModDate, CitationName
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            citation_id,
            citation_data.source_id,
            citation_data.comments or "",
            citation_data.actual_text or "",
            citation_data.ref_number or "",
            citation_data.footnote,
            citation_data.short_footnote,
            citation_data.bibliography,
            citation_data.fields_blob,
            utc_mod_date,
            ""  # CitationName (usually empty for free-form citations)
        ))

        logger.info(f"Created citation: {citation_id} for source {citation_data.source_id}")
        return citation_id

    def check_duplicate_citation(self, person_id: int, source_id: int) -> Optional[int]:
        """Check if a citation already exists for this person and source.

        Args:
            person_id: PersonID to check
            source_id: SourceID to check

        Returns:
            CitationID if duplicate found, None otherwise
        """
        cursor = self.conn.cursor()

        # Check for existing citation linked to this person and source
        cursor.execute("""
            SELECT c.CitationID
            FROM CitationTable c
            JOIN CitationLinkTable cl ON c.CitationID = cl.CitationID
            WHERE c.SourceID = ?
              AND cl.OwnerType = 0
              AND cl.OwnerID = ?
            LIMIT 1
        """, (source_id, person_id))

        result = cursor.fetchone()
        return result[0] if result else None

    def link_citation_to_person(self, citation_id: int, person_id: int,
                                quality: int = 0) -> int:
        """Link a citation to a person via CitationLinkTable.

        Args:
            citation_id: CitationID to link
            person_id: PersonID to link to
            quality: Quality score (0-3, default 0)

        Returns:
            LinkID of created link

        Raises:
            RuntimeError: If database is read-only
        """
        if self.read_only:
            raise RuntimeError("Cannot create citation link in read-only mode")

        cursor = self.conn.cursor()

        # Get next LinkID
        cursor.execute("SELECT IFNULL(MAX(LinkID), 0) + 1 FROM CitationLinkTable")
        link_id = cursor.fetchone()[0]

        # Get current timestamp
        cursor.execute("SELECT julianday('now') - 2415018.5")
        utc_mod_date = cursor.fetchone()[0]

        # Insert citation link
        cursor.execute("""
            INSERT INTO CitationLinkTable (
                LinkID, CitationID, OwnerType, OwnerID,
                SortOrder, Quality, UTCModDate
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            link_id,
            citation_id,
            0,  # OwnerType = 0 for Person
            person_id,
            0,  # SortOrder (0 = chronological by date)
            quality,
            utc_mod_date
        ))

        logger.info(f"Linked citation {citation_id} to person {person_id}")
        return link_id

    def verify_person_exists(self, person_id: int) -> bool:
        """Verify that a person exists in the database.

        Args:
            person_id: PersonID to verify

        Returns:
            True if person exists, False otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM PersonTable WHERE PersonID = ?", (person_id,))
        return cursor.fetchone() is not None

    def get_person_name(self, person_id: int) -> Optional[str]:
        """Get the primary name of a person.

        Args:
            person_id: PersonID to look up

        Returns:
            Full name (Given Surname) or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT Given, Surname
            FROM NameTable
            WHERE OwnerID = ? AND IsPrimary = 1
        """, (person_id,))

        result = cursor.fetchone()
        if result:
            given, surname = result
            return f"{given} {surname}".strip()
        return None

    def create_citation_for_person(self, person_id: int, source_data: SourceData,
                                   citation_data: CitationData) -> Tuple[int, int, int, bool]:
        """Complete workflow: create/find source, create citation, and link to person.

        This is the main method for adding a draft registration citation to a person.
        It handles all steps in a single transaction.

        Args:
            person_id: PersonID to attach citation to
            source_data: Source data
            citation_data: Citation data (source_id will be updated)

        Returns:
            Tuple of (source_id, citation_id, link_id, source_created)

        Raises:
            ValueError: If person doesn't exist
            RuntimeError: If database is read-only
        """
        if self.read_only:
            raise RuntimeError("Cannot create citation in read-only mode")

        # Verify person exists
        if not self.verify_person_exists(person_id):
            raise ValueError(f"Person ID {person_id} not found in database")

        # Create or find source
        source_id, source_created = self.create_or_find_source(source_data)

        # Update citation_data with source_id
        citation_data.source_id = source_id

        # Check for duplicate citation
        existing_citation_id = self.check_duplicate_citation(person_id, source_id)
        if existing_citation_id:
            logger.warning(
                f"Citation already exists for person {person_id} and source {source_id}. "
                f"Skipping citation creation."
            )
            # Return existing citation info
            return source_id, existing_citation_id, 0, source_created

        # Create citation
        citation_id = self.create_citation(citation_data)

        # Link to person
        link_id = self.link_citation_to_person(citation_id, person_id)

        person_name = self.get_person_name(person_id)
        logger.info(
            f"Successfully created citation for {person_name or f'Person {person_id}'}: "
            f"Source {source_id}, Citation {citation_id}"
        )

        return source_id, citation_id, link_id, source_created

    def get_source_citations_count(self, source_id: int) -> int:
        """Get the count of citations for a source.

        Args:
            source_id: SourceID to check

        Returns:
            Number of citations using this source
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM CitationTable WHERE SourceID = ?
        """, (source_id,))
        return cursor.fetchone()[0]

    def get_person_citations_count(self, person_id: int) -> int:
        """Get the count of citations for a person.

        Args:
            person_id: PersonID to check

        Returns:
            Number of citations linked to this person
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*)
            FROM CitationLinkTable
            WHERE OwnerType = 0 AND OwnerID = ?
        """, (person_id,))
        return cursor.fetchone()[0]
