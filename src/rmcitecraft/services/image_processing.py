"""
Image processing service for census images.

Orchestrates the complete workflow:
1. File detection (FileWatcher)
2. Filename generation (FilenameGenerator)
3. Directory mapping (DirectoryMapper)
4. File moving/organizing
5. Database integration (ImageRepository)
6. Status tracking
"""

import shutil
import sqlite3
from pathlib import Path

from loguru import logger

from rmcitecraft.database.image_repository import ImageRepository
from rmcitecraft.models.image import ImageMetadata, ImageStatus
from rmcitecraft.services.directory_mapper import DirectoryMapper
from rmcitecraft.services.filename_generator import FilenameGenerator


class ImageProcessingService:
    """
    Orchestrates census image processing workflow.

    Coordinates all services to handle image download detection,
    file organization, and database linking.

    Thread-safe: Creates new database connections per operation to avoid
    SQLite threading issues (FileWatcher runs in separate thread).
    """

    def __init__(
        self,
        db_path: Path | str,
        icu_extension_path: Path | str,
        media_root: Path | str,
    ):
        """
        Initialize image processing service.

        Args:
            db_path: Path to RootsMagic database file
            icu_extension_path: Path to ICU extension for RMNOCASE
            media_root: Root directory for RootsMagic media files
        """
        self.db_path = Path(db_path)
        self.icu_extension_path = Path(icu_extension_path)

        # Initialize services
        self.filename_gen = FilenameGenerator()
        self.dir_mapper = DirectoryMapper(media_root)

        # Active image tracking (in-memory)
        self._active_images: dict[str, ImageMetadata] = {}

        logger.info("ImageProcessingService initialized")

    def _get_db_connection(self) -> sqlite3.Connection:
        """
        Create a new database connection for this thread.

        Thread-safe: Each call creates a new connection with RMNOCASE support.
        SQLite connections cannot be shared across threads.

        Returns:
            New database connection with ICU extension loaded
        """
        from rmcitecraft.database.connection import connect_rmtree

        return connect_rmtree(
            db_path=self.db_path,
            extension_path=self.icu_extension_path,
        )

    def register_pending_image(self, metadata: ImageMetadata) -> None:
        """
        Register an image as pending download.

        Called when user clicks "Download Image" button.
        Sets up context for when file watcher detects the download.

        Args:
            metadata: Image metadata with census details

        Example:
            >>> metadata = ImageMetadata(
            ...     image_id="img_123",
            ...     citation_id="cit_456",
            ...     year=1930,
            ...     state="Oklahoma",
            ...     county="Tulsa",
            ...     surname="Iams",
            ...     given_name="Jesse Dorsey",
            ...     familysearch_url="https://...",
            ...     access_date="24 July 2015"
            ... )
            >>> service.register_pending_image(metadata)
        """
        metadata.update_status(ImageStatus.PENDING)
        self._active_images[metadata.image_id] = metadata

        logger.info(
            f"Registered pending image: {metadata.image_id} "
            f"for {metadata.given_name} {metadata.surname} ({metadata.year})"
        )

    def process_downloaded_file(self, file_path: Path) -> ImageMetadata | None:
        """
        Process a newly downloaded census image file.

        Called by FileWatcher when new image detected in downloads folder.

        Steps:
        1. Match to active/pending image context
        2. Generate standardized filename
        3. Determine destination directory
        4. Check for duplicates
        5. Move and rename file
        6. Create database records
        7. Update status

        Args:
            file_path: Path to downloaded file in downloads folder

        Returns:
            Updated ImageMetadata if successful, None if failed

        Example:
            >>> file_path = Path("~/Downloads/image.jpg")
            >>> result = service.process_downloaded_file(file_path)
            >>> if result:
            ...     print(f"Processed: {result.final_filename}")
        """
        logger.info(f"Processing downloaded file: {file_path.name}")

        try:
            # Match to pending image
            metadata = self._match_to_pending_image(file_path)

            if not metadata:
                logger.warning(
                    f"No pending image found for: {file_path.name}. "
                    "Download may have occurred without context."
                )
                return None

            # Update status
            metadata.download_path = file_path
            metadata.update_status(ImageStatus.DOWNLOADED)

            # Generate standardized filename
            extension = self.filename_gen.extract_extension(file_path)
            filename = self.filename_gen.generate_filename(
                year=metadata.year,
                state=metadata.state,
                county=metadata.county,
                surname=metadata.surname,
                given_name=metadata.given_name,
                extension=extension,
            )
            metadata.final_filename = filename

            # Check for duplicate (thread-safe database access)
            db_conn = self._get_db_connection()
            try:
                image_repo = ImageRepository(db_conn)
                existing_media_id = image_repo.find_media_by_file(filename)
            finally:
                db_conn.close()

            if existing_media_id:
                logger.info(
                    f"Duplicate image detected: {filename} (existing MediaID={existing_media_id})"
                )
                metadata.update_status(ImageStatus.DUPLICATE)
                metadata.media_id = existing_media_id

                # Link existing media to new citation if needed
                self._link_existing_media(metadata)

                # Delete downloaded file (duplicate)
                file_path.unlink()

                return metadata

            # Move and organize file
            metadata.update_status(ImageStatus.PROCESSING)
            final_path = self._move_to_destination(file_path, metadata)
            metadata.final_path = final_path

            # Create database records
            self._create_database_records(metadata)

            # Success
            metadata.update_status(ImageStatus.LINKED)
            logger.info(f"Successfully processed image: {filename} (MediaID={metadata.media_id})")

            return metadata

        except Exception as e:
            logger.error(f"Failed to process image: {e}")
            if metadata:
                metadata.update_status(ImageStatus.FAILED, error=str(e))
            return None

    def _match_to_pending_image(self, file_path: Path) -> ImageMetadata | None:
        """
        Match downloaded file to pending image context.

        Strategy:
        1. Check if any pending images exist
        2. Use most recently registered pending image (FIFO)

        Args:
            file_path: Downloaded file path

        Returns:
            Matched ImageMetadata or None
        """
        # Get pending images
        pending = [img for img in self._active_images.values() if img.status == ImageStatus.PENDING]

        if not pending:
            return None

        # Use most recent (last registered)
        # In future: Could use filename hints or extension context
        return pending[-1]

    def _move_to_destination(self, source_path: Path, metadata: ImageMetadata) -> Path:
        """
        Move file to appropriate census directory with standardized name.

        Args:
            source_path: Current file location (downloads folder)
            metadata: Image metadata

        Returns:
            Final destination path

        Raises:
            OSError: If file move fails
        """
        # Ensure destination directory exists
        dest_dir = self.dir_mapper.ensure_directory_exists(metadata.year, metadata.schedule_type)

        # Build final path
        dest_path = dest_dir / metadata.final_filename

        # Move file
        logger.debug(f"Moving: {source_path} -> {dest_path}")
        shutil.move(str(source_path), str(dest_path))

        return dest_path

    def _create_database_records(self, metadata: ImageMetadata) -> None:
        """
        Create MultimediaTable record and MediaLinkTable entries.

        Thread-safe: Creates new database connection for this operation.

        Args:
            metadata: Image metadata (updated with media_id)

        Raises:
            sqlite3.Error: If database operations fail
        """
        # Create new connection for this thread
        db_conn = self._get_db_connection()

        try:
            # Create repository with thread-specific connection
            image_repo = ImageRepository(db_conn)

            # Get symbolic path for RootsMagic
            symbolic_path = self.dir_mapper.get_symbolic_path(metadata.year, metadata.schedule_type)

            # Generate caption: "Census: 1930 Fed Census - Tulsa, OK"
            caption = image_repo.generate_caption(metadata.year, metadata.county, metadata.state)

            # Format census date
            census_date = image_repo.format_census_date(metadata.year)

            # Create media record
            media_id = image_repo.create_media_record(
                media_path=symbolic_path,
                media_file=metadata.final_filename,
                caption=caption,
                ref_number=metadata.familysearch_url,
                census_date=census_date,
            )

            metadata.media_id = media_id

            # Find census event by person name and year
            event_id = image_repo.find_census_event(
                metadata.surname, metadata.given_name, metadata.year
            )

            if event_id:
                logger.info(f"Found census event: EventID={event_id}")

                # Link image to event
                image_repo.link_media_to_event(media_id, event_id)
                metadata.event_id = event_id

                # Find and link to all citations for this event
                citation_ids = image_repo.find_citations_for_event(event_id)
                if citation_ids:
                    logger.info(f"Found {len(citation_ids)} citation(s) for event: {citation_ids}")
                    for cit_id in citation_ids:
                        image_repo.link_media_to_citation(media_id, cit_id)
                else:
                    logger.warning(f"No citations found for EventID={event_id}")
            else:
                logger.warning(
                    f"Census event not found for {metadata.given_name} "
                    f"{metadata.surname} ({metadata.year})"
                )

        finally:
            # Always close connection
            db_conn.close()

    def _link_existing_media(self, metadata: ImageMetadata) -> None:
        """
        Link existing media to new citation (duplicate handling).

        Thread-safe: Creates new database connection for this operation.

        Args:
            metadata: Image metadata with existing media_id
        """
        if not metadata.media_id:
            return

        # Create new connection for this thread
        db_conn = self._get_db_connection()

        try:
            # Create repository with thread-specific connection
            image_repo = ImageRepository(db_conn)

            # Link to new citation
            image_repo.link_media_to_citation(metadata.media_id, int(metadata.citation_id))

            # Link to event if provided
            if metadata.event_id:
                image_repo.link_media_to_event(metadata.media_id, metadata.event_id)

        finally:
            # Always close connection
            db_conn.close()

    def get_image_status(self, image_id: str) -> ImageStatus | None:
        """
        Get current status of an image.

        Args:
            image_id: Image ID

        Returns:
            Current status or None if not found
        """
        metadata = self._active_images.get(image_id)
        return metadata.status if metadata else None

    def get_active_images(self) -> list[ImageMetadata]:
        """
        Get all active (non-completed) images.

        Returns:
            List of active image metadata
        """
        return [
            img
            for img in self._active_images.values()
            if img.status not in [ImageStatus.LINKED, ImageStatus.DUPLICATE]
        ]

    def get_failed_images(self) -> list[ImageMetadata]:
        """
        Get all failed images.

        Returns:
            List of failed image metadata
        """
        return [img for img in self._active_images.values() if img.status == ImageStatus.FAILED]

    def retry_failed_image(self, image_id: str) -> bool:
        """
        Retry processing a failed image.

        Args:
            image_id: Image ID to retry

        Returns:
            True if retry initiated, False if not allowed
        """
        metadata = self._active_images.get(image_id)

        if not metadata or not metadata.can_retry():
            return False

        # Reset to pending
        metadata.update_status(ImageStatus.PENDING)
        logger.info(f"Retrying image: {image_id}")

        return True

    def clear_completed_images(self) -> int:
        """
        Remove completed/duplicate images from active tracking.

        Returns:
            Number of images cleared
        """
        completed = [
            img_id
            for img_id, img in self._active_images.items()
            if img.status in [ImageStatus.LINKED, ImageStatus.DUPLICATE]
        ]

        for img_id in completed:
            del self._active_images[img_id]

        logger.debug(f"Cleared {len(completed)} completed images")
        return len(completed)


# Global singleton instance
_image_processing_service: ImageProcessingService | None = None


def get_image_processing_service() -> ImageProcessingService:
    """
    Get the global image processing service instance.

    Lazy initialization - service is created on first access.
    Requires database connection and media root path from config.

    Returns:
        ImageProcessingService singleton instance

    Raises:
        RuntimeError: If required configuration is missing
    """
    global _image_processing_service

    if _image_processing_service is None:
        # Import here to avoid circular dependencies
        from rmcitecraft.config import get_config

        config = get_config()

        if not config.rm_media_root_directory:
            raise RuntimeError(
                "RM_MEDIA_ROOT_DIRECTORY not configured. "
                "Set in .env file to enable image management."
            )

        # Create service with database paths (thread-safe)
        # Each operation creates its own connection
        _image_processing_service = ImageProcessingService(
            db_path=config.rm_database_path,
            icu_extension_path=config.sqlite_icu_extension,
            media_root=config.rm_media_root_directory,
        )

        logger.info("ImageProcessingService singleton initialized (thread-safe mode)")

    return _image_processing_service
