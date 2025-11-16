"""Message Log Panel Component."""

from nicegui import ui

from rmcitecraft.services.message_log import MessageLog, MessageType, LoggedMessage


class MessageLogPanel:
    """Panel displaying logged messages with filtering."""

    def __init__(self, message_log: MessageLog):
        """Initialize message log panel.

        Args:
            message_log: Message log service instance
        """
        self.message_log = message_log
        self.filter_type: MessageType | None = None
        self.is_expanded: bool = False
        self.container: ui.column | None = None
        self.messages_container: ui.column | None = None

        # Register as listener for new messages
        self.message_log.add_listener(self._on_new_message)

    def render(self) -> ui.card:
        """Render the message log panel.

        Returns:
            Container element
        """
        with ui.card().classes("w-full") as self.container:
            self._render_content()
        return self.container

    def _render_content(self) -> None:
        """Render panel content."""
        # Header with expand/collapse
        with ui.row().classes("w-full items-center justify-between p-2 bg-gray-100 cursor-pointer").on(
            "click", self._toggle_expanded
        ):
            with ui.row().classes("items-center gap-2"):
                ui.icon("history" if self.is_expanded else "history").classes("text-lg")
                ui.label("Message Log").classes("font-semibold")

                # Message count badge
                total_messages = len(self.message_log.messages)
                if total_messages > 0:
                    ui.badge(str(total_messages)).props("color=blue")

            # Expand/collapse icon
            ui.icon("expand_less" if self.is_expanded else "expand_more").classes("text-lg")

        # Expanded content
        if self.is_expanded:
            self._render_expanded_content()

    def _render_expanded_content(self) -> None:
        """Render expanded panel content."""
        # Filter and action buttons
        with ui.row().classes("w-full items-center gap-2 p-2 border-b"):
            ui.label("Filter:").classes("text-sm")

            filter_options = {
                "all": "All",
                "info": "Info",
                "positive": "Success",
                "warning": "Warnings",
                "negative": "Errors",
            }

            ui.select(
                filter_options,
                value="all",
                on_change=lambda e: self._on_filter_change(e.value),
            ).props("dense outlined").classes("flex-grow")

            ui.button(
                "Clear Log",
                icon="delete",
                on_click=self._clear_log,
            ).props("flat dense").classes("text-xs")

            ui.button(
                "Export",
                icon="download",
                on_click=self._export_log,
            ).props("flat dense").classes("text-xs")

        # Messages list (scrollable)
        with ui.scroll_area().classes("w-full h-64"):
            with ui.column().classes("w-full gap-1 p-2") as self.messages_container:
                self._render_messages()

    def _render_messages(self) -> None:
        """Render message list."""
        messages = self.message_log.get_messages(filter_type=self.filter_type, limit=100)

        if not messages:
            ui.label("No messages to display").classes("text-gray-500 italic text-center p-4")
            return

        for message in messages:
            self._render_message(message)

    def _render_message(self, message: LoggedMessage) -> None:
        """Render a single message.

        Args:
            message: Message to render
        """
        with ui.row().classes("w-full items-start gap-2 p-2 hover:bg-gray-50 rounded"):
            # Icon
            ui.icon(message.icon).classes(f"{message.color_class} text-lg")

            # Content
            with ui.column().classes("flex-grow gap-0"):
                # Message text
                ui.label(message.message).classes(f"{message.color_class} text-sm")

                # Timestamp and source
                metadata_parts = [message.formatted_timestamp]
                if message.source:
                    metadata_parts.append(message.source)

                ui.label(" • ".join(metadata_parts)).classes("text-xs text-gray-500")

                # Details (if present)
                if message.details:
                    with ui.expansion("Details", icon="info").classes("text-xs mt-1"):
                        for key, value in message.details.items():
                            ui.label(f"{key}: {value}").classes("text-xs")

    def _toggle_expanded(self) -> None:
        """Toggle expanded state."""
        self.is_expanded = not self.is_expanded
        self.refresh()

    def _on_filter_change(self, value: str) -> None:
        """Handle filter change.

        Args:
            value: Selected filter value
        """
        if value == "all":
            self.filter_type = None
        else:
            self.filter_type = MessageType(value)

        self._refresh_messages()

    def _clear_log(self) -> None:
        """Clear message log."""
        self.message_log.clear()
        self._refresh_messages()
        ui.notify("Message log cleared", type="info")

    def _export_log(self) -> None:
        """Export message log to file."""
        # TODO: Implement export functionality
        ui.notify("Export not yet implemented", type="warning")

    def _on_new_message(self, message: LoggedMessage | None) -> None:
        """Handle new message from log.

        Args:
            message: New message (None if cleared)
        """
        # Refresh messages list
        if self.is_expanded and self.messages_container:
            self._refresh_messages()

    def refresh(self) -> None:
        """Refresh the entire panel."""
        if self.container:
            self.container.clear()
            with self.container:
                self._render_content()

    def _refresh_messages(self) -> None:
        """Refresh only the messages list."""
        if self.messages_container:
            self.messages_container.clear()
            with self.messages_container:
                self._render_messages()
