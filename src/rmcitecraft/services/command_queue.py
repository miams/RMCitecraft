"""
Command Queue Manager for Extension Communication

Manages commands sent from RMCitecraft to the browser extension.
Commands are queued and polled by the extension every 2 seconds.
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from loguru import logger


@dataclass
class Command:
    """Represents a command to be executed by the extension."""

    id: str
    type: str
    data: Dict
    created_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending, completed, failed, expired

    def is_expired(self, max_age_minutes: int = 5) -> bool:
        """Check if command has expired."""
        age_seconds = time.time() - self.created_at
        return age_seconds > (max_age_minutes * 60)

    def to_dict(self) -> Dict:
        """Convert command to dictionary for API response."""
        return {
            "id": self.id,
            "type": self.type,
            "data": self.data,
            "created_at": self.created_at,
            "status": self.status,
        }


class CommandQueue:
    """
    In-memory command queue for extension communication.

    Thread-safe queue that manages commands sent to the browser extension.
    Automatically cleans up expired commands.
    """

    def __init__(self, max_age_minutes: int = 5):
        """
        Initialize command queue.

        Args:
            max_age_minutes: Maximum age of commands before expiration (default: 5)
        """
        self._commands: Dict[str, Command] = {}
        self._max_age_minutes = max_age_minutes
        logger.info(f"Command queue initialized (max age: {max_age_minutes} minutes)")

    def add(self, command_type: str, data: Optional[Dict] = None) -> str:
        """
        Add a command to the queue.

        Args:
            command_type: Type of command (e.g., "download_image", "ping")
            data: Optional data payload for the command

        Returns:
            Command ID (UUID)
        """
        command_id = str(uuid.uuid4())
        command = Command(
            id=command_id,
            type=command_type,
            data=data or {},
        )

        self._commands[command_id] = command
        logger.info(f"Added command to queue: {command_type} (ID: {command_id})")

        # Clean up expired commands
        self._cleanup_expired()

        return command_id

    def get_pending(self) -> List[Dict]:
        """
        Get all pending commands.

        Returns:
            List of pending command dictionaries
        """
        # Clean up expired commands first
        self._cleanup_expired()

        # Return all pending commands
        pending = [
            cmd.to_dict()
            for cmd in self._commands.values()
            if cmd.status == "pending"
        ]

        if pending:
            logger.debug(f"Returning {len(pending)} pending command(s)")

        return pending

    def complete(self, command_id: str, response: Optional[Dict] = None) -> bool:
        """
        Mark a command as completed and remove from queue.

        Args:
            command_id: ID of the command to complete
            response: Optional response data from extension

        Returns:
            True if command was found and completed, False otherwise
        """
        if command_id not in self._commands:
            logger.warning(f"Attempted to complete unknown command: {command_id}")
            return False

        command = self._commands[command_id]
        command.status = "completed"

        logger.info(
            f"Command completed: {command.type} (ID: {command_id})"
            + (f" with response: {response}" if response else "")
        )

        # Remove from queue
        del self._commands[command_id]

        return True

    def fail(self, command_id: str, error: Optional[str] = None) -> bool:
        """
        Mark a command as failed and remove from queue.

        Args:
            command_id: ID of the command to fail
            error: Optional error message

        Returns:
            True if command was found and failed, False otherwise
        """
        if command_id not in self._commands:
            logger.warning(f"Attempted to fail unknown command: {command_id}")
            return False

        command = self._commands[command_id]
        command.status = "failed"

        logger.warning(
            f"Command failed: {command.type} (ID: {command_id})"
            + (f" - Error: {error}" if error else "")
        )

        # Remove from queue
        del self._commands[command_id]

        return True

    def get(self, command_id: str) -> Optional[Dict]:
        """
        Get a command by ID.

        Args:
            command_id: ID of the command

        Returns:
            Command dictionary if found, None otherwise
        """
        command = self._commands.get(command_id)
        return command.to_dict() if command else None

    def clear(self) -> int:
        """
        Clear all commands from the queue.

        Returns:
            Number of commands cleared
        """
        count = len(self._commands)
        self._commands.clear()
        logger.info(f"Cleared {count} command(s) from queue")
        return count

    def _cleanup_expired(self) -> int:
        """
        Remove expired commands from the queue.

        Returns:
            Number of commands removed
        """
        expired_ids = [
            cmd_id
            for cmd_id, cmd in self._commands.items()
            if cmd.is_expired(self._max_age_minutes)
        ]

        for cmd_id in expired_ids:
            command = self._commands[cmd_id]
            logger.warning(
                f"Removing expired command: {command.type} (ID: {cmd_id}, "
                f"age: {(time.time() - command.created_at) / 60:.1f} minutes)"
            )
            del self._commands[cmd_id]

        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired command(s)")

        return len(expired_ids)

    def get_stats(self) -> Dict:
        """
        Get queue statistics.

        Returns:
            Dictionary with queue statistics
        """
        pending = sum(1 for cmd in self._commands.values() if cmd.status == "pending")

        return {
            "total": len(self._commands),
            "pending": pending,
            "max_age_minutes": self._max_age_minutes,
        }


# Global singleton instance
_command_queue: Optional[CommandQueue] = None


def get_command_queue() -> CommandQueue:
    """
    Get the global command queue instance.

    Returns:
        CommandQueue singleton instance
    """
    global _command_queue
    if _command_queue is None:
        _command_queue = CommandQueue()
    return _command_queue
