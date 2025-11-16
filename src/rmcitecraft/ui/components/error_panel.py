"""Error Panel Component

Displays persistent error log with copy/export functionality.
"""

from nicegui import ui

from rmcitecraft.services.error_log import ErrorEntry, get_error_log_service


def create_error_panel() -> None:
    """Create a persistent error/warning panel at the bottom of the page."""
    error_service = get_error_log_service()

    # Container for the error panel (initially hidden)
    error_container = ui.column().classes("w-full")

    # Track visibility state
    is_visible = {"value": False}

    def update_badge():
        """Update the error count badge."""
        error_count = error_service.get_error_count()
        warning_count = error_service.get_warning_count()

        if error_count > 0:
            badge.text = str(error_count)
            badge.classes("bg-red-500")
            badge.visible = True
        elif warning_count > 0:
            badge.text = str(warning_count)
            badge.classes("bg-orange-500")
            badge.visible = True
        else:
            badge.visible = False

    def toggle_panel():
        """Toggle error panel visibility."""
        is_visible["value"] = not is_visible["value"]
        error_container.visible = is_visible["value"]

        if is_visible["value"]:
            render_entries()

    def render_entries():
        """Render error entries in the panel."""
        error_container.clear()

        with error_container:
            with ui.card().classes("w-full"):
                # Header with controls
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("Error & Warning Log").classes("text-lg font-bold")

                    with ui.row().classes("gap-2"):
                        ui.button("Copy All", icon="content_copy", on_click=copy_all).props(
                            "flat dense"
                        )
                        ui.button("Clear", icon="clear_all", on_click=clear_log).props("flat dense")
                        ui.button("Close", icon="close", on_click=toggle_panel).props("flat dense")

                # Entries
                entries = error_service.get_entries()

                if not entries:
                    ui.label("No errors or warnings logged.").classes("text-gray-500 p-4")
                else:
                    with ui.scroll_area().classes("w-full h-64"):
                        for entry in entries:
                            render_entry(entry)

    def render_entry(entry: ErrorEntry):
        """Render a single error entry."""
        # Color based on level
        color_class = {
            "error": "bg-red-50 border-red-300",
            "warning": "bg-orange-50 border-orange-300",
            "info": "bg-blue-50 border-blue-300",
        }.get(entry.level, "bg-gray-50 border-gray-300")

        icon = {"error": "error", "warning": "warning", "info": "info"}.get(entry.level, "help")

        with ui.card().classes(f"w-full {color_class} border-l-4 mb-2"):
            with ui.row().classes("w-full items-start gap-2"):
                # Icon
                ui.icon(icon).classes(f"text-2xl").style(
                    f"color: {'#dc2626' if entry.level == 'error' else '#f97316' if entry.level == 'warning' else '#3b82f6'}"
                )

                # Content
                with ui.column().classes("flex-grow gap-1"):
                    # Timestamp and context
                    with ui.row().classes("items-center gap-2"):
                        ui.label(entry.formatted_timestamp).classes("text-xs text-gray-500")
                        if entry.context:
                            ui.badge(entry.context).classes("text-xs")

                    # Message
                    ui.label(entry.message).classes("font-semibold")

                    # Details (if any)
                    if entry.details:
                        with ui.expansion("Details", icon="info").classes("text-sm"):
                            ui.code(entry.details).classes("text-xs whitespace-pre-wrap")

                # Copy button
                ui.button(
                    icon="content_copy",
                    on_click=lambda e=entry: copy_entry(e),
                ).props("flat dense round").classes("text-xs")

    def copy_entry(entry: ErrorEntry):
        """Copy a single entry to clipboard."""
        text = f"[{entry.formatted_timestamp}] {entry.level.upper()}"
        if entry.context:
            text += f" - {entry.context}"
        text += f"\n{entry.message}"
        if entry.details:
            text += f"\n\nDetails:\n{entry.details}"

        ui.clipboard.write(text)
        ui.notify("Copied to clipboard", type="positive", position="top")

    def copy_all():
        """Copy all entries to clipboard."""
        text = error_service.export_text()
        ui.clipboard.write(text)
        ui.notify("All errors copied to clipboard", type="positive", position="top")

    def clear_log():
        """Clear the error log."""
        error_service.clear()
        render_entries()
        update_badge()
        ui.notify("Error log cleared", type="positive", position="top")

    # Register callback for updates
    def on_error_change():
        """Called when errors are added."""
        update_badge()
        if is_visible["value"]:
            render_entries()

    error_service.register_callback(on_error_change)

    # Floating button to show/hide panel
    with ui.page_sticky(position="bottom-right", x_offset=20, y_offset=20):
        with ui.button(icon="bug_report", on_click=toggle_panel).props("fab").classes(
            "bg-gray-700"
        ).style("position: relative;"):
            # Badge for error count
            badge = (
                ui.badge()
                .props("floating color=red")
                .classes("text-xs")
                .style("top: -4px; right: -4px;")
            )
            badge.visible = False

    # Initial badge update
    update_badge()


def show_error_notification(
    message: str,
    details: str | None = None,
    context: str | None = None,
    timeout: int = 5,
) -> None:
    """
    Show error notification and log to error service.

    Args:
        message: Error message
        details: Optional detailed error information
        context: Optional context string
        timeout: Notification timeout in seconds (0 = never dismiss)
    """
    error_service = get_error_log_service()
    error_service.add_error(message, details, context)

    # Show notification with longer timeout
    ui.notify(
        message,
        type="negative",
        position="top",
        timeout=timeout * 1000 if timeout > 0 else 0,
        close_button=True,
    )


def show_warning_notification(
    message: str,
    details: str | None = None,
    context: str | None = None,
    timeout: int = 5,
) -> None:
    """
    Show warning notification and log to error service.

    Args:
        message: Warning message
        details: Optional detailed information
        context: Optional context string
        timeout: Notification timeout in seconds (0 = never dismiss)
    """
    error_service = get_error_log_service()
    error_service.add_warning(message, details, context)

    # Show notification
    ui.notify(
        message,
        type="warning",
        position="top",
        timeout=timeout * 1000 if timeout > 0 else 0,
        close_button=True,
    )
