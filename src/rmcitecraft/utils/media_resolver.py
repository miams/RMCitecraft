"""Media path resolution utilities for RootsMagic database.

RootsMagic uses symbolic placeholders in MediaPath:
- ? = Media root directory (typically ~/Genealogy/RootsMagic/Files)
- ~ = User's home directory
- * = Database directory
"""

import os
from pathlib import Path

from loguru import logger


class MediaPathResolver:
    """Resolve RootsMagic media paths to absolute file system paths."""

    def __init__(
        self,
        media_root: str | None = None,
        database_path: str | None = None,
    ):
        """Initialize resolver with root directories.

        Args:
            media_root: Absolute path to media root directory (replaces ?).
                       Defaults to ~/Genealogy/RootsMagic/Files
            database_path: Path to .rmtree file (for * symbol).
                          If None, * symbol won't be resolved.
        """
        if media_root:
            self.media_root = Path(media_root).expanduser().resolve()
        else:
            # Default RootsMagic media location
            self.media_root = (
                Path.home() / "Genealogy" / "RootsMagic" / "Files"
            )

        self.database_dir: Path | None = None
        if database_path:
            self.database_dir = Path(database_path).parent.resolve()

        logger.debug(f"Media root: {self.media_root}")
        logger.debug(f"Database dir: {self.database_dir}")

    def resolve(
        self,
        media_path: str,
        media_file: str,
    ) -> Path | None:
        """Resolve RootsMagic media path to absolute path.

        Args:
            media_path: Path from MultimediaTable.MediaPath (may contain ?, ~, *)
            media_file: Filename from MultimediaTable.MediaFile

        Returns:
            Absolute Path object if resolved, None if path invalid

        Examples:
            >>> resolver = MediaPathResolver()
            >>> resolver.resolve("?\\Records - Census\\1930 Federal", "1930, Pa, Greene - Iams, George.jpg")
            Path("/Users/miams/Genealogy/RootsMagic/Files/Records - Census/1930 Federal/1930, Pa, Greene - Iams, George.jpg")
        """
        if not media_path or not media_file:
            logger.warning("Empty media_path or media_file")
            return None

        # Replace symbolic placeholders
        resolved_path = media_path

        if media_path.startswith("?"):
            # ? = Media root directory
            resolved_path = str(self.media_root) + media_path[1:]

        elif media_path.startswith("~"):
            # ~ = User's home directory
            resolved_path = str(Path.home()) + media_path[1:]

        elif media_path.startswith("*"):
            # * = Database directory
            if not self.database_dir:
                logger.error("Cannot resolve *: database_path not provided")
                return None
            resolved_path = str(self.database_dir) + media_path[1:]

        # Normalize path separators (handle Windows \ in database)
        resolved_path = resolved_path.replace("\\", os.sep)

        # Combine path and filename
        full_path = Path(resolved_path) / media_file

        # Verify file exists
        if not full_path.exists():
            logger.warning(f"Media file not found: {full_path}")
            return None

        logger.debug(f"Resolved: {media_path} + {media_file} -> {full_path}")
        return full_path

    def get_census_image_for_event(
        self,
        cursor,
        event_id: int,
    ) -> Path | None:
        """Get census image path for a given EventID.

        Args:
            cursor: Database cursor
            event_id: EventID from EventTable

        Returns:
            Path to census image, or None if not found
        """
        cursor.execute(
            """
            SELECT m.MediaPath, m.MediaFile
            FROM MultimediaTable m
            JOIN MediaLinkTable ml ON m.MediaID = ml.MediaID
            WHERE ml.OwnerID = ?
              AND ml.OwnerType = 2
              AND m.MediaPath LIKE '%Census%'
            ORDER BY m.MediaID DESC
            LIMIT 1
            """,
            (event_id,),
        )

        row = cursor.fetchone()
        if not row:
            logger.debug(f"No census image found for EventID {event_id}")
            return None

        media_path, media_file = row
        return self.resolve(media_path, media_file)

    def get_census_images_for_person(
        self,
        cursor,
        person_id: int,
    ) -> list[tuple[int, Path]]:
        """Get all census images for a person.

        Args:
            cursor: Database cursor
            person_id: PersonID from PersonTable

        Returns:
            List of (census_year, image_path) tuples, sorted by year descending
        """
        cursor.execute(
            """
            SELECT
                e.Date,
                m.MediaPath,
                m.MediaFile
            FROM MultimediaTable m
            JOIN MediaLinkTable ml ON m.MediaID = ml.MediaID
            JOIN EventTable e ON ml.OwnerID = e.EventID
            WHERE e.OwnerID = ?
              AND ml.OwnerType = 2
              AND m.MediaPath LIKE '%Census%'
            ORDER BY e.Date DESC
            """,
            (person_id,),
        )

        images = []
        for row in cursor.fetchall():
            date_str, media_path, media_file = row
            # Extract year from RootsMagic date format (e.g., "D.+19300000..+00000000..")
            year = int(date_str.split("+")[1][:4])

            image_path = self.resolve(media_path, media_file)
            if image_path:
                images.append((year, image_path))

        return images
