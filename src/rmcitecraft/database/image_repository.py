"""
Database repository for census image management.

Handles all database operations for MultimediaTable and MediaLinkTable,
following RootsMagic schema conventions.
"""

import sqlite3
from datetime import UTC, datetime

from loguru import logger

# US State abbreviations (postal codes)
STATE_ABBREVIATIONS = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
    "District of Columbia": "DC",
}


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

    def link_media_to_source(self, media_id: int, source_id: int) -> None:
        """
        Link media to source in MediaLinkTable.

        Args:
            media_id: MediaID from MultimediaTable
            source_id: SourceID from SourceTable

        Example:
            >>> repo.link_media_to_source(media_id=42, source_id=335)
        """
        cursor = self.conn.cursor()

        try:
            # Check if link already exists
            cursor.execute(
                """
                SELECT LinkID FROM MediaLinkTable
                WHERE MediaID = ? AND OwnerType = 3 AND OwnerID = ?
                """,
                (media_id, source_id),
            )

            if cursor.fetchone():
                logger.warning(f"Media {media_id} already linked to source {source_id}")
                return

            # Get next LinkID
            cursor.execute("SELECT COALESCE(MAX(LinkID), 0) + 1 FROM MediaLinkTable")
            link_id = cursor.fetchone()[0]

            # Current timestamp
            utc_mod_date = self._get_utc_timestamp()

            # Insert link (OwnerType=3 for Source)
            cursor.execute(
                """
                INSERT INTO MediaLinkTable (
                    LinkID, MediaID, OwnerType, OwnerID,
                    IsPrimary, UTCModDate
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (link_id, media_id, 3, source_id, 0, utc_mod_date),
            )

            self.conn.commit()
            logger.info(f"Linked media {media_id} to source {source_id}")

        except sqlite3.Error as e:
            self.conn.rollback()
            logger.error(f"Failed to link media to source: {e}")
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

    def generate_caption(self, year: int, county: str, state: str) -> str:
        """
        Generate caption for census image.

        Format: "Census: YYYY Fed Census - County, ST"
        Uses 2-letter postal code for state abbreviation.

        Args:
            year: Census year
            county: County name
            state: State full name (e.g., "Oklahoma")

        Returns:
            Formatted caption

        Example:
            >>> repo.generate_caption(1930, "Tulsa", "Oklahoma")
            'Census: 1930 Fed Census - Tulsa, OK'
        """
        # Get state abbreviation (default to full name if not found)
        state_abbr = STATE_ABBREVIATIONS.get(state, state)
        return f"Census: {year} Fed Census - {county}, {state_abbr}"

    def find_census_event(self, surname: str, given_name: str, year: int) -> int | None:
        """
        Find census event ID for a person and year.

        Args:
            surname: Person's surname
            given_name: Person's given name
            year: Census year

        Returns:
            EventID if found, None otherwise
        """
        cursor = self.conn.cursor()

        # Find person by name
        cursor.execute(
            """
            SELECT OwnerID
            FROM NameTable
            WHERE Surname COLLATE RMNOCASE = ?
              AND Given COLLATE RMNOCASE LIKE ?
              AND IsPrimary = 1
            LIMIT 1
            """,
            (surname, f"{given_name}%"),
        )

        person_row = cursor.fetchone()
        if not person_row:
            logger.warning(f"Person not found: {given_name} {surname}")
            return None

        person_id = person_row[0]

        # Find census event for that person and year
        cursor.execute(
            """
            SELECT EventID
            FROM EventTable
            WHERE OwnerID = ?
              AND EventType = 18
              AND Date LIKE ?
            LIMIT 1
            """,
            (person_id, f"%{year}%"),
        )

        event_row = cursor.fetchone()
        if event_row:
            return event_row[0]

        logger.warning(f"Census event not found for {given_name} {surname} ({year})")
        return None

    def find_citations_for_event(self, event_id: int) -> list[int]:
        """
        Find all citation IDs linked to an event.

        Args:
            event_id: EventID

        Returns:
            List of CitationIDs
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT CitationID
            FROM CitationLinkTable
            WHERE OwnerType = 2
              AND OwnerID = ?
            """,
            (event_id,),
        )

        return [row[0] for row in cursor.fetchall()]

    def find_citation_by_census_details(
        self, surname: str, given_name: str, year: int
    ) -> int | None:
        """
        Find CitationID by matching person name and census year.

        Args:
            surname: Person's surname
            given_name: Person's given name (can be abbreviated, e.g., "J Dorsey")
            year: Census year

        Returns:
            CitationID if found, None otherwise
        """
        cursor = self.conn.cursor()

        # Find person by name (handle abbreviated given names with LIKE)
        cursor.execute(
            """
            SELECT OwnerID
            FROM NameTable
            WHERE Surname COLLATE RMNOCASE = ?
              AND Given COLLATE RMNOCASE LIKE ?
              AND IsPrimary = 1
            LIMIT 1
            """,
            (surname, f"{given_name}%"),
        )

        person_row = cursor.fetchone()

        if not person_row:
            logger.debug(f"Person not found: {given_name} {surname}")
            return None

        person_id = person_row[0]

        # Find census event for that person and year
        cursor.execute(
            """
            SELECT EventID
            FROM EventTable
            WHERE OwnerID = ?
              AND EventType = 18
              AND Date LIKE ?
            LIMIT 1
            """,
            (person_id, f"%{year}%"),
        )

        event_row = cursor.fetchone()
        if not event_row:
            logger.debug(f"Census event not found for {given_name} {surname} ({year})")
            return None

        event_id = event_row[0]

        # Find citation linked to this event
        cursor.execute(
            """
            SELECT CitationID
            FROM CitationLinkTable
            WHERE OwnerType = 2
              AND OwnerID = ?
            LIMIT 1
            """,
            (event_id,),
        )

        citation_row = cursor.fetchone()
        if citation_row:
            return citation_row[0]

        logger.debug(f"Citation not found for EventID={event_id}")
        return None

    def find_event_for_citation(self, citation_id: int) -> int | None:
        """
        Find event ID linked to a citation.

        Args:
            citation_id: CitationID from CitationTable

        Returns:
            EventID if found, None otherwise
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT OwnerID
            FROM CitationLinkTable
            WHERE CitationID = ?
              AND OwnerType = 2
            LIMIT 1
            """,
            (citation_id,),
        )

        result = cursor.fetchone()
        return result[0] if result else None

    def get_person_id_for_event(self, event_id: int) -> int | None:
        """
        Get PersonID from EventID.

        Args:
            event_id: EventID from EventTable

        Returns:
            PersonID if found, None otherwise
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT OwnerID
            FROM EventTable
            WHERE EventID = ?
            LIMIT 1
            """,
            (event_id,),
        )

        result = cursor.fetchone()
        return result[0] if result else None

    def get_person_name_for_census(
        self, person_id: int, census_year: int
    ) -> tuple[str, str] | None:
        """
        Get person's name for census image filename.

        For males: Use name from NameTable (IsPrimary=1)
        For females: Check marital status at census time
            - If married or widowed: Use husband's surname
            - If single: Use maiden name

        Logic:
        1. Get person's Sex from PersonTable
        2. Get Given name and Surname from NameTable (IsPrimary=1)
        3. If Female (Sex=1):
           a. Find families where person is Mother (FamilyTable.MotherID)
           b. For each family, check if marriage event exists before census year
           c. Use husband's surname from most recent marriage before census
        4. Return (Given, Surname)

        Args:
            person_id: PersonID from PersonTable
            census_year: Census year (to determine marital status at that time)

        Returns:
            Tuple of (given_name, surname) or None if not found

        Example:
            >>> repo.get_person_name_for_census(1651, 1940)
            ('Jesse Dorsey', 'Iams')
        """
        cursor = self.conn.cursor()

        # Get person's Sex and primary name
        cursor.execute(
            """
            SELECT p.Sex, n.Given, n.Surname
            FROM PersonTable p
            JOIN NameTable n ON p.PersonID = n.OwnerID
            WHERE p.PersonID = ?
              AND n.IsPrimary = 1
            LIMIT 1
            """,
            (person_id,),
        )

        person_row = cursor.fetchone()
        if not person_row:
            logger.warning(f"Person not found: PersonID={person_id}")
            return None

        sex, given_name, maiden_surname = person_row

        # Sex: 0=Male, 1=Female, 2=Unknown
        # If male or unknown, use name from NameTable as-is
        if sex != 1:
            return (given_name, maiden_surname)

        # Female: Check for marriage before census year
        # Find all families where this person is the Mother
        cursor.execute(
            """
            SELECT FamilyID, FatherID
            FROM FamilyTable
            WHERE MotherID = ?
            """,
            (person_id,),
        )

        families = cursor.fetchall()
        if not families:
            # No families found - use maiden name
            logger.debug(f"No families found for PersonID={person_id}, using maiden name")
            return (given_name, maiden_surname)

        # For each family, find marriage events before census year
        # Track most recent marriage before census
        most_recent_marriage: tuple[int, int, int] | None = (
            None  # (marriage_year, family_id, father_id)
        )

        for family_id, father_id in families:
            # Find marriage event for this family
            # Marriage events have OwnerType=3 (Family) and EventType for Marriage
            # Query EventTable for marriage events linked to this family
            cursor.execute(
                """
                SELECT e.EventID, e.Date
                FROM EventTable e
                WHERE e.OwnerID = ?
                  AND e.EventType IN (
                    SELECT FactTypeID FROM FactTypeTable WHERE Name = 'Marriage'
                  )
                """,
                (family_id,),
            )

            marriage_events = cursor.fetchall()
            for event_id, date_str in marriage_events:
                if not date_str:
                    continue

                # Parse year from RootsMagic date format: "D.+YYYYMMDD..+00000000.."
                # Extract YYYY from the date string
                try:
                    # Date format: D.+19400101..+00000000..
                    # Extract year: characters after "+", take first 4
                    if "+1" in date_str or "+2" in date_str:
                        year_start = date_str.index("+") + 1
                        marriage_year = int(date_str[year_start : year_start + 4])

                        # Check if marriage is before census year
                        if marriage_year < census_year:
                            # Track most recent marriage
                            if (
                                most_recent_marriage is None
                                or marriage_year > most_recent_marriage[0]
                            ):
                                most_recent_marriage = (marriage_year, family_id, father_id)
                except (ValueError, IndexError) as e:
                    logger.warning(
                        f"Could not parse marriage date: {date_str} for EventID={event_id}: {e}"
                    )
                    continue

        # If we found a marriage before census year, use husband's surname
        if most_recent_marriage:
            marriage_year, family_id, father_id = most_recent_marriage

            if father_id:
                # Get husband's surname from NameTable
                cursor.execute(
                    """
                    SELECT Surname
                    FROM NameTable
                    WHERE OwnerID = ?
                      AND IsPrimary = 1
                    LIMIT 1
                    """,
                    (father_id,),
                )

                husband_row = cursor.fetchone()
                if husband_row:
                    husband_surname = husband_row[0]
                    logger.info(
                        f"Female PersonID={person_id} married in {marriage_year} "
                        f"(before census {census_year}), using husband's surname: {husband_surname}"
                    )
                    return (given_name, husband_surname)

        # No marriage found before census year - use maiden name
        logger.debug(
            f"No marriage before {census_year} for PersonID={person_id}, using maiden name"
        )
        return (given_name, maiden_surname)

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
