"""
Database repository for census image management.

Handles all database operations for MultimediaTable and MediaLinkTable,
following RootsMagic schema conventions.
"""

import sqlite3
from datetime import UTC, datetime

from loguru import logger


class ImageRepository:
    """
    Repository for census image database operations.

    Manages:
    - MultimediaTable (image records)
    - MediaLinkTable (links to events and citations)
    """

    def __init__(self, connection: sqlite3.Connection):
        """
        Initialize repository.

        Args:
            connection: SQLite database connection (with ICU extension loaded)
        """
        self.conn = connection

    def create_media_record(
        self,
        media_path: str,
        media_file: str,
        caption: str,
        ref_number: str,
        census_date: str,
    ) -> int:
        """
        Create new record in MultimediaTable.

        Args:
            media_path: Symbolic path (e.g., "?/Records - Census/1930 Federal")
            media_file: Filename only
            caption: Auto-generated caption from census details
            ref_number: FamilySearch ARK URL
            census_date: RootsMagic date format (e.g., "D.+19300401..+00000000..")

        Returns:
            MediaID of created record

        Example:
            >>> repo = ImageRepository(conn)
            >>> media_id = repo.create_media_record(
            ...     media_path="?/Records - Census/1930 Federal",
            ...     media_file="1930, Oklahoma, Tulsa - Iams, Jesse Dorsey.jpg",
            ...     caption="1930 U.S. Census - Jesse Dorsey Iams, Tulsa, Oklahoma",
            ...     ref_number="https://familysearch.org/ark:/61903/1:1:XXXX-XXX",
            ...     census_date="D.+19300401..+00000000.."
            ... )
        """
        cursor = self.conn.cursor()

        try:
            # Get next MediaID
            cursor.execute("SELECT COALESCE(MAX(MediaID), 0) + 1 FROM MultimediaTable")
            media_id = cursor.fetchone()[0]

            # Current timestamp for UTCModDate
            utc_mod_date = self._get_utc_timestamp()

            # Insert media record
            cursor.execute(
                """
                INSERT INTO MultimediaTable (
                    MediaID, MediaType, MediaPath, MediaFile,
                    Caption, RefNumber, Date, UTCModDate
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    media_id,
                    1,  # MediaType: 1 = Image
                    media_path,
                    media_file,
                    caption,
                    ref_number,
                    census_date,
                    utc_mod_date,
                ),
            )

            self.conn.commit()
            logger.info(f"Created media record: MediaID={media_id}, file={media_file}")

            return media_id

        except sqlite3.Error as e:
            self.conn.rollback()
            logger.error(f"Failed to create media record: {e}")
            raise

    def link_media_to_event(self, media_id: int, event_id: int, is_primary: bool = True) -> None:
        """
        Link media to census event in MediaLinkTable.

        Args:
            media_id: MediaID from MultimediaTable
            event_id: EventID from EventTable (census event)
            is_primary: Whether this is the primary image for the event

        Example:
            >>> repo.link_media_to_event(media_id=42, event_id=123)
        """
        cursor = self.conn.cursor()

        try:
            # Check if link already exists
            cursor.execute(
                """
                SELECT LinkID FROM MediaLinkTable
                WHERE MediaID = ? AND OwnerType = 2 AND OwnerID = ?
                """,
                (media_id, event_id),
            )

            if cursor.fetchone():
                logger.warning(f"Media {media_id} already linked to event {event_id}")
                return

            # Get next LinkID
            cursor.execute("SELECT COALESCE(MAX(LinkID), 0) + 1 FROM MediaLinkTable")
            link_id = cursor.fetchone()[0]

            # Current timestamp
            utc_mod_date = self._get_utc_timestamp()

            # Insert link (OwnerType=2 for Event)
            cursor.execute(
                """
                INSERT INTO MediaLinkTable (
                    LinkID, MediaID, OwnerType, OwnerID,
                    IsPrimary, UTCModDate
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (link_id, media_id, 2, event_id, 1 if is_primary else 0, utc_mod_date),
            )

            self.conn.commit()
            logger.info(f"Linked media {media_id} to event {event_id}")

        except sqlite3.Error as e:
            self.conn.rollback()
            logger.error(f"Failed to link media to event: {e}")
            raise

    def link_media_to_citation(self, media_id: int, citation_id: int) -> None:
        """
        Link media to citation in MediaLinkTable.

        Args:
            media_id: MediaID from MultimediaTable
            citation_id: CitationID from CitationTable

        Example:
            >>> repo.link_media_to_citation(media_id=42, citation_id=456)
        """
        cursor = self.conn.cursor()

        try:
            # Check if link already exists
            cursor.execute(
                """
                SELECT LinkID FROM MediaLinkTable
                WHERE MediaID = ? AND OwnerType = 4 AND OwnerID = ?
                """,
                (media_id, citation_id),
            )

            if cursor.fetchone():
                logger.warning(f"Media {media_id} already linked to citation {citation_id}")
                return

            # Get next LinkID
            cursor.execute("SELECT COALESCE(MAX(LinkID), 0) + 1 FROM MediaLinkTable")
            link_id = cursor.fetchone()[0]

            # Current timestamp
            utc_mod_date = self._get_utc_timestamp()

            # Insert link (OwnerType=4 for Citation)
            cursor.execute(
                """
                INSERT INTO MediaLinkTable (
                    LinkID, MediaID, OwnerType, OwnerID,
                    IsPrimary, UTCModDate
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (link_id, media_id, 4, citation_id, 0, utc_mod_date),
            )

            self.conn.commit()
            logger.info(f"Linked media {media_id} to citation {citation_id}")

        except sqlite3.Error as e:
            self.conn.rollback()
            logger.error(f"Failed to link media to citation: {e}")
            raise

    def find_media_by_file(self, media_file: str) -> int | None:
        """
        Find existing media record by filename.

        Used for duplicate detection.

        Args:
            media_file: Filename to search for

        Returns:
            MediaID if found, None otherwise

        Example:
            >>> existing_id = repo.find_media_by_file(
            ...     "1930, Oklahoma, Tulsa - Iams, Jesse Dorsey.jpg"
            ... )
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT MediaID FROM MultimediaTable
            WHERE MediaFile = ? COLLATE RMNOCASE
            """,
            (media_file,),
        )

        result = cursor.fetchone()
        return result[0] if result else None

    def get_media_for_citation(self, citation_id: int) -> list[dict]:
        """
        Get all media linked to a citation.

        Args:
            citation_id: CitationID

        Returns:
            List of media records (dicts with MediaID, MediaPath, MediaFile, Caption)

        Example:
            >>> media_list = repo.get_media_for_citation(citation_id=456)
            >>> for media in media_list:
            ...     print(f"{media['MediaFile']}: {media['Caption']}")
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT
                m.MediaID,
                m.MediaPath,
                m.MediaFile,
                m.Caption,
                m.RefNumber,
                m.Date
            FROM MultimediaTable m
            JOIN MediaLinkTable ml ON m.MediaID = ml.MediaID
            WHERE ml.OwnerType = 4 AND ml.OwnerID = ?
            ORDER BY m.MediaID
            """,
            (citation_id,),
        )

        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

    def get_media_for_event(self, event_id: int) -> list[dict]:
        """
        Get all media linked to an event.

        Args:
            event_id: EventID

        Returns:
            List of media records

        Example:
            >>> media_list = repo.get_media_for_event(event_id=123)
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT
                m.MediaID,
                m.MediaPath,
                m.MediaFile,
                m.Caption,
                m.RefNumber,
                m.Date,
                ml.IsPrimary
            FROM MultimediaTable m
            JOIN MediaLinkTable ml ON m.MediaID = ml.MediaID
            WHERE ml.OwnerType = 2 AND ml.OwnerID = ?
            ORDER BY ml.IsPrimary DESC, m.MediaID
            """,
            (event_id,),
        )

        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

    def delete_media_record(self, media_id: int) -> None:
        """
        Delete media record and all its links.

        Args:
            media_id: MediaID to delete

        Note:
            This does NOT delete the physical file, only database records.
        """
        cursor = self.conn.cursor()

        try:
            # Delete all links first
            cursor.execute("DELETE FROM MediaLinkTable WHERE MediaID = ?", (media_id,))

            # Delete media record
            cursor.execute("DELETE FROM MultimediaTable WHERE MediaID = ?", (media_id,))

            self.conn.commit()
            logger.info(f"Deleted media record: MediaID={media_id}")

        except sqlite3.Error as e:
            self.conn.rollback()
            logger.error(f"Failed to delete media record: {e}")
            raise

    def _get_utc_timestamp(self) -> float:
        """
        Get current UTC timestamp for UTCModDate field.

        Returns:
            Timestamp as float (seconds since epoch)
        """
        return datetime.now(UTC).timestamp()

    def generate_caption(self, year: int, person_name: str, location: str) -> str:
        """
        Generate caption for census image.

        Args:
            year: Census year
            person_name: Full name of person
            location: Location (e.g., "Tulsa, Oklahoma")

        Returns:
            Formatted caption

        Example:
            >>> repo.generate_caption(1930, "Jesse Dorsey Iams", "Tulsa, Oklahoma")
            '1930 U.S. Census - Jesse Dorsey Iams, Tulsa, Oklahoma'
        """
        return f"{year} U.S. Census - {person_name}, {location}"

    def format_census_date(self, year: int, month: int = 4, day: int = 1) -> str:
        """
        Format census date in RootsMagic format.

        RootsMagic date format: D.+YYYY0000..+00000000..
        - D. = prefix
        - +YYYYMMDD = date
        - .. = separator
        - +00000000 = time (unused)
        - .. = suffix

        Args:
            year: Census year
            month: Month (default 4 = April, typical census month)
            day: Day (default 1)

        Returns:
            RootsMagic formatted date string

        Example:
            >>> repo.format_census_date(1930)
            'D.+19300401..+00000000..'
        """
        date_str = f"{year:04d}{month:02d}{day:02d}"
        return f"D.+{date_str}..+00000000.."
