"""Message logging service for capturing UI notifications."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class MessageType(Enum):
    """Message type classifications."""

    INFO = "info"
    POSITIVE = "positive"
    WARNING = "warning"
    NEGATIVE = "negative"
    ERROR = "error"


@dataclass
class LoggedMessage:
    """A logged message with metadata."""

    timestamp: datetime
    message: str
    type: MessageType
    source: str | None = None
    details: dict[str, Any] | None = None

    @property
    def formatted_timestamp(self) -> str:
        """Get formatted timestamp string."""
        return self.timestamp.strftime("%H:%M:%S")

    @property
    def icon(self) -> str:
        """Get icon for message type."""
        icons = {
            MessageType.INFO: "info",
            MessageType.POSITIVE: "check_circle",
            MessageType.WARNING: "warning",
            MessageType.NEGATIVE: "error",
            MessageType.ERROR: "error_outline",
        }
        return icons.get(self.type, "info")

    @property
    def color_class(self) -> str:
        """Get CSS color class for message type."""
        colors = {
            MessageType.INFO: "text-blue-600",
            MessageType.POSITIVE: "text-green-600",
            MessageType.WARNING: "text-orange-600",
            MessageType.NEGATIVE: "text-red-600",
            MessageType.ERROR: "text-red-700",
        }
        return colors.get(self.type, "text-gray-600")


class MessageLog:
    """Service for logging UI messages."""

    def __init__(self, max_messages: int = 1000):
        """Initialize message log.

        Args:
            max_messages: Maximum number of messages to retain
        """
        self.max_messages = max_messages
        self.messages: list[LoggedMessage] = []
        self._listeners: list[callable] = []

    def log(
        self,
        message: str,
        type: MessageType = MessageType.INFO,
        source: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log a message.

        Args:
            message: Message text
            type: Message type
            source: Source of the message (e.g., "Batch Processing", "Citation Manager")
            details: Additional metadata
        """
        logged_message = LoggedMessage(
            timestamp=datetime.now(),
            message=message,
            type=type,
            source=source,
            details=details,
        )

        self.messages.append(logged_message)

        # Trim to max size (circular buffer)
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)

        # Notify listeners
        self._notify_listeners(logged_message)

    def log_info(self, message: str, source: str | None = None) -> None:
        """Log an info message."""
        self.log(message, MessageType.INFO, source)

    def log_success(self, message: str, source: str | None = None) -> None:
        """Log a success message."""
        self.log(message, MessageType.POSITIVE, source)

    def log_warning(self, message: str, source: str | None = None) -> None:
        """Log a warning message."""
        self.log(message, MessageType.WARNING, source)

    def log_error(self, message: str, source: str | None = None) -> None:
        """Log an error message."""
        self.log(message, MessageType.NEGATIVE, source)

    def get_messages(
        self, filter_type: MessageType | None = None, limit: int | None = None
    ) -> list[LoggedMessage]:
        """Get logged messages.

        Args:
            filter_type: Filter by message type (None = all)
            limit: Maximum number of messages to return (None = all)

        Returns:
            List of logged messages (most recent first)
        """
        messages = self.messages[::-1]  # Reverse to show most recent first

        if filter_type:
            messages = [m for m in messages if m.type == filter_type]

        if limit:
            messages = messages[:limit]

        return messages

    def clear(self) -> None:
        """Clear all logged messages."""
        self.messages.clear()
        self._notify_listeners(None)

    def add_listener(self, callback: callable) -> None:
        """Add a listener for new messages.

        Args:
            callback: Function to call when new message is logged
        """
        self._listeners.append(callback)

    def remove_listener(self, callback: callable) -> None:
        """Remove a listener.

        Args:
            callback: Listener to remove
        """
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_listeners(self, message: LoggedMessage | None) -> None:
        """Notify all listeners of new message.

        Args:
            message: New message (None if cleared)
        """
        for listener in self._listeners:
            try:
                listener(message)
            except Exception:
                pass  # Don't let listener errors break logging


# Global message log instance
_message_log: MessageLog | None = None


def get_message_log() -> MessageLog:
    """Get the global message log instance."""
    global _message_log
    if _message_log is None:
        _message_log = MessageLog()
    return _message_log
