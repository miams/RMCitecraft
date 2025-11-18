"""Unified UI Logging Helper

Simplifies logging to both the error panel AND notifications.
Prevents confusion between message_log and error_log services.
"""

from nicegui import ui
from rmcitecraft.services.error_log import get_error_log_service


def log_error(message: str, context: str, notify: bool = True) -> None:
    """
    Log error to UI panel and optionally show notification.

    Args:
        message: Error message
        context: Source context (e.g., "Find a Grave Batch")
        notify: Whether to show ui.notify (default: True)
    """
    error_log = get_error_log_service()
    error_log.add_error(message, context=context)

    if notify:
        ui.notify(message, type="negative")


def log_warning(message: str, context: str, notify: bool = True) -> None:
    """
    Log warning to UI panel and optionally show notification.

    Args:
        message: Warning message
        context: Source context
        notify: Whether to show ui.notify (default: True)
    """
    error_log = get_error_log_service()
    error_log.add_warning(message, context=context)

    if notify:
        ui.notify(message, type="warning")


def log_info(message: str, context: str, notify: bool = False) -> None:
    """
    Log info to UI panel and optionally show notification.

    Args:
        message: Info message
        context: Source context
        notify: Whether to show ui.notify (default: False for info)
    """
    error_log = get_error_log_service()
    error_log.add_info(message, context=context)

    if notify:
        ui.notify(message, type="info")


def log_success(message: str, context: str, notify: bool = True) -> None:
    """
    Log success to UI panel and optionally show notification.

    Args:
        message: Success message
        context: Source context
        notify: Whether to show ui.notify (default: True)
    """
    error_log = get_error_log_service()
    error_log.add_info(message, context=context)

    if notify:
        ui.notify(message, type="positive")
