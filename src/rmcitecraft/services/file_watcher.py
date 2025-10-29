"""
File system watcher for census image downloads.

Monitors downloads folder for new census images and triggers processing.
Uses watchdog library for cross-platform file system events.
"""

import time
from collections.abc import Callable
from pathlib import Path

from loguru import logger
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


class ImageFileHandler(FileSystemEventHandler):
    """
    Handles file system events for image downloads.

    Filters for image files and ignores partial downloads.
    """

    # Image extensions to monitor
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".tiff", ".tif"}

    # Partial download extensions to ignore
    PARTIAL_EXTENSIONS = {".crdownload", ".download", ".tmp", ".part"}

    def __init__(self, callback: Callable[[Path], None]):
        """
        Initialize file handler.

        Args:
            callback: Function to call when valid image file is detected.
                     Receives file path as argument.
        """
        super().__init__()
        self.callback = callback
        self._processing_files: set[Path] = set()

    def on_created(self, event: FileSystemEvent) -> None:
        """
        Handle file creation events.

        Args:
            event: File system event
        """
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Ignore if already processing
        if file_path in self._processing_files:
            return

        # Check if valid image file
        if self._is_valid_image(file_path):
            logger.info(f"New image detected: {file_path.name}")
            self._processing_files.add(file_path)
            self.callback(file_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        """
        Handle file modification events.

        Used to detect when partial downloads complete.

        Args:
            event: File system event
        """
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Check if partial download just completed and file is stable
        if (
            self._is_valid_image(file_path)
            and file_path not in self._processing_files
            and self._is_file_stable(file_path)
        ):
            logger.info(f"Download completed: {file_path.name}")
            self._processing_files.add(file_path)
            self.callback(file_path)

    def mark_processed(self, file_path: Path) -> None:
        """
        Mark file as processed (remove from tracking).

        Args:
            file_path: Path to processed file
        """
        self._processing_files.discard(file_path)

    def _is_valid_image(self, file_path: Path) -> bool:
        """
        Check if file is a valid image to process.

        Args:
            file_path: Path to check

        Returns:
            True if valid image file
        """
        # Check extension
        ext = file_path.suffix.lower()

        if ext in self.PARTIAL_EXTENSIONS:
            return False

        if ext not in self.IMAGE_EXTENSIONS:
            return False

        # File must exist and be readable
        if not file_path.exists():
            return False

        # Ignore hidden files
        return not file_path.name.startswith(".")

    def _is_file_stable(self, file_path: Path, wait_time: float = 1.0) -> bool:
        """
        Check if file has finished downloading (size no longer changing).

        Args:
            file_path: Path to check
            wait_time: Seconds to wait between size checks

        Returns:
            True if file size is stable
        """
        try:
            size1 = file_path.stat().st_size
            time.sleep(wait_time)
            size2 = file_path.stat().st_size

            return size1 == size2

        except (OSError, FileNotFoundError):
            return False


class FileWatcher:
    """
    Monitors downloads folder for new census images.

    Uses watchdog library for efficient file system monitoring.
    Automatically starts/stops observer thread.
    """

    def __init__(self, downloads_dir: Path | str, callback: Callable[[Path], None]) -> None:
        """
        Initialize file watcher.

        Args:
            downloads_dir: Directory to monitor (typically ~/Downloads)
            callback: Function to call when new image is detected
        """
        self.downloads_dir = Path(downloads_dir)
        self.callback = callback

        # Create event handler and observer
        self.handler = ImageFileHandler(callback)
        self.observer = Observer()

        # State
        self._running = False

        logger.debug(f"FileWatcher initialized for: {self.downloads_dir}")

    def start(self) -> None:
        """
        Start monitoring downloads folder.

        Raises:
            FileNotFoundError: If downloads directory doesn't exist
        """
        if self._running:
            logger.warning("FileWatcher already running")
            return

        if not self.downloads_dir.exists():
            raise FileNotFoundError(f"Downloads directory not found: {self.downloads_dir}")

        # Schedule observer
        self.observer.schedule(self.handler, str(self.downloads_dir), recursive=False)

        # Start observer thread
        self.observer.start()
        self._running = True

        logger.info(f"FileWatcher started: {self.downloads_dir}")

    def stop(self) -> None:
        """Stop monitoring downloads folder."""
        if not self._running:
            return

        self.observer.stop()
        self.observer.join()
        self._running = False

        logger.info("FileWatcher stopped")

    def is_running(self) -> bool:
        """
        Check if watcher is running.

        Returns:
            True if currently monitoring
        """
        return self._running

    def mark_processed(self, file_path: Path) -> None:
        """
        Mark file as processed (stop tracking it).

        Args:
            file_path: Path to processed file
        """
        self.handler.mark_processed(file_path)

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
