"""Error Log Service

Tracks errors and warnings for display in the UI.
Provides persistent error history that users can copy/review.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from loguru import logger


@dataclass
class ErrorEntry:
    """Represents an error or warning entry."""

    timestamp: float = field(default_factory=time.time)
    level: Literal["error", "warning", "info"] = "error"
    message: str = ""
    details: str | None = None
    context: str | None = None  # e.g., "Citation Manager", "Image Processing"

    @property
    def formatted_timestamp(self) -> str:
        """Get formatted timestamp string."""
        dt = datetime.fromtimestamp(self.timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "formatted_timestamp": self.formatted_timestamp,
            "level": self.level,
            "message": self.message,
            "details": self.details,
            "context": self.context,
        }


class ErrorLogService:
    """
    Service for tracking errors and warnings.

    Stores errors in memory for display in UI.
    Provides methods to add, retrieve, and clear errors.
    """

    def __init__(self, max_entries: int = 100):
        """
        Initialize error log service.

        Args:
            max_entries: Maximum number of entries to keep in memory
        """
        self._entries: list[ErrorEntry] = []
        self._max_entries = max_entries
        self._callbacks: list[callable] = []  # Callbacks for UI updates
        logger.info(f"Error log service initialized (max entries: {max_entries})")

    def add_error(
        self, message: str, details: str | None = None, context: str | None = None
    ) -> None:
        """
        Add an error entry.

        Args:
            message: Error message
            details: Optional detailed error information (stack trace, etc.)
            context: Optional context (e.g., "Citation Manager")
        """
        entry = ErrorEntry(
            level="error",
            message=message,
            details=details,
            context=context,
        )
        self._add_entry(entry)
        logger.error(f"Error logged: {message} (context: {context})")

    def add_warning(
        self, message: str, details: str | None = None, context: str | None = None
    ) -> None:
        """
        Add a warning entry.

        Args:
            message: Warning message
            details: Optional detailed information
            context: Optional context
        """
        entry = ErrorEntry(
            level="warning",
            message=message,
            details=details,
            context=context,
        )
        self._add_entry(entry)
        logger.warning(f"Warning logged: {message} (context: {context})")

    def add_info(
        self, message: str, details: str | None = None, context: str | None = None
    ) -> None:
        """
        Add an info entry.

        Args:
            message: Info message
            details: Optional detailed information
            context: Optional context
        """
        entry = ErrorEntry(
            level="info",
            message=message,
            details=details,
            context=context,
        )
        self._add_entry(entry)
        logger.info(f"Info logged: {message} (context: {context})")

    def _add_entry(self, entry: ErrorEntry) -> None:
        """Add entry to log and trigger callbacks."""
        self._entries.insert(0, entry)  # Most recent first

        # Trim to max entries
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[: self._max_entries]

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in error log callback: {e}")

    def get_entries(
        self, level: Literal["error", "warning", "info"] | None = None, limit: int | None = None
    ) -> list[ErrorEntry]:
        """
        Get error entries.

        Args:
            level: Optional filter by level
            limit: Optional limit number of entries

        Returns:
            List of error entries (most recent first)
        """
        entries = self._entries

        if level:
            entries = [e for e in entries if e.level == level]

        if limit:
            entries = entries[:limit]

        return entries

    def get_error_count(self) -> int:
        """Get count of error entries."""
        return len([e for e in self._entries if e.level == "error"])

    def get_warning_count(self) -> int:
        """Get count of warning entries."""
        return len([e for e in self._entries if e.level == "warning"])

    def clear(self) -> None:
        """Clear all entries."""
        self._entries.clear()
        logger.info("Error log cleared")

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in error log callback: {e}")

    def register_callback(self, callback: callable) -> None:
        """
        Register callback for when entries are added.

        Args:
            callback: Function to call when entries change
        """
        self._callbacks.append(callback)

    def export_text(self) -> str:
        """
        Export error log as plain text.

        Returns:
            Formatted text with all entries
        """
        lines = ["RMCitecraft Error Log", "=" * 50, ""]

        if not self._entries:
            lines.append("No errors logged.")
        else:
            for entry in self._entries:
                lines.append(f"[{entry.formatted_timestamp}] {entry.level.upper()}")
                if entry.context:
                    lines.append(f"Context: {entry.context}")
                lines.append(f"Message: {entry.message}")
                if entry.details:
                    lines.append(f"Details: {entry.details}")
                lines.append("-" * 50)

        return "\n".join(lines)


# Global error log service instance
_error_log_service: ErrorLogService | None = None


def get_error_log_service() -> ErrorLogService:
    """Get or create the global error log service instance."""
    global _error_log_service
    if _error_log_service is None:
        _error_log_service = ErrorLogService()
    return _error_log_service
