"""Citation Queue Component for Batch Processing.

This component displays a scrollable list of citations with status indicators,
filters, and multi-select capabilities.
"""

from typing import Callable

from nicegui import ui

from rmcitecraft.services.batch_processing import CitationBatchItem, CitationStatus


class CitationQueueComponent:
    """Citation queue component with virtual scrolling and filtering."""

    def __init__(
        self,
        citations: list[CitationBatchItem],
        on_citation_click: Callable[[CitationBatchItem], None] | None = None,
        on_selection_change: Callable[[set[int]], None] | None = None,
    ):
        """Initialize citation queue component.

        Args:
            citations: List of citations to display
            on_citation_click: Callback when citation is clicked
            on_selection_change: Callback when selection changes
        """
        self.citations = citations
        self.on_citation_click = on_citation_click
        self.on_selection_change = on_selection_change

        # State
        self.selected_citation: CitationBatchItem | None = None
        self.selected_ids: set[int] = set()
        self.filter_status: str = "all"  # all, incomplete, complete, error
        self.sort_by: str = "name"  # name, status

        # UI references
        self.container: ui.column | None = None
        self.status_label: ui.label | None = None

    def render(self) -> ui.column:
        """Render the citation queue component.

        Returns:
            Container element
        """
        with ui.column().classes("w-full h-full gap-2") as self.container:
            self._render_content()
        return self.container

    def _render_content(self) -> None:
        """Render the content inside the container."""
        # Header with status summary (compact)
        with ui.row().classes("w-full items-center justify-between p-1 bg-blue-100 rounded"):
            self.status_label = ui.label(self._get_status_text()).classes("text-xs font-medium")
            ui.button(icon="refresh", on_click=self.refresh).props("flat dense round").classes(
                "text-xs"
            )

        # Batch actions at top
        self._render_batch_actions()

        # Filters and sorting
        with ui.row().classes("w-full items-center gap-2 p-2"):
            ui.label("Filter:").classes("text-xs")
            ui.select(
                ["all", "incomplete", "complete", "error"],
                value=self.filter_status,
                on_change=lambda e: self._on_filter_change(e.value),
            ).props("dense outlined").classes("flex-grow")

            ui.label("Sort:").classes("text-xs")
            ui.select(
                ["name", "status"],
                value=self.sort_by,
                on_change=lambda e: self._on_sort_change(e.value),
            ).props("dense outlined").classes("flex-grow")

        # Citation list (scrollable) - taller to accommodate ~20 entries
        with ui.scroll_area().classes("w-full").style("min-height: 600px; max-height: 70vh;"):
            with ui.column().classes("w-full gap-1"):
                for citation in self._get_filtered_sorted_citations():
                    self._render_citation_item(citation)

    def _render_citation_item(self, citation: CitationBatchItem) -> None:
        """Render a single citation item.

        Args:
            citation: Citation to render
        """
        is_selected = citation == self.selected_citation
        is_checked = citation.citation_id in self.selected_ids

        # Background color based on status and selection
        bg_class = "bg-blue-50" if is_selected else "bg-white"
        border_class = "border-l-4 border-blue-500" if is_selected else "border-l-4 border-transparent"

        with ui.card().classes(
            f"w-full p-2 cursor-pointer hover:bg-gray-50 {bg_class} {border_class}"
        ).on("click", lambda c=citation: self._on_citation_click(c)):
            with ui.row().classes("w-full items-start gap-2"):
                # Checkbox for multi-select
                checkbox = ui.checkbox(value=is_checked).on(
                    "update:model-value",
                    lambda e, cid=citation.citation_id: self._on_checkbox_change(cid, e.args),
                ).props("dense")

                # Status icon
                status_icon, status_color = self._get_status_icon_color(citation.status)
                ui.icon(status_icon).classes(f"text-{status_color} text-lg")

                # Citation info
                with ui.column().classes("flex-grow gap-0"):
                    # Name
                    ui.label(citation.full_name).classes("font-semibold text-sm")

                    # Status text
                    status_text = self._get_citation_status_text(citation)
                    ui.label(status_text).classes(f"text-{status_color} text-xs")

                    # Missing fields (if applicable)
                    if citation.needs_manual_entry and citation.missing_fields:
                        missing_text = f"Missing: {', '.join(citation.missing_fields)}"
                        ui.label(missing_text).classes("text-orange-600 text-xs italic")

    def _render_batch_actions(self) -> None:
        """Render batch action buttons."""
        with ui.row().classes("w-full items-center gap-2 p-2"):
            selected_count = len(self.selected_ids)
            total_count = len(self.citations)

            # Count incomplete citations
            incomplete_count = sum(
                1 for c in self.citations
                if c.needs_manual_entry or c.status == CitationStatus.QUEUED
            )

            # Select All / Deselect All button
            all_selected = selected_count == total_count and total_count > 0
            ui.button(
                "Deselect All" if all_selected else f"Select All ({total_count})",
                icon="check_box_outline_blank" if all_selected else "select_all",
                on_click=self._toggle_select_all,
            ).props("dense").classes("text-xs")

            # Select Incomplete button (only show if there are incomplete items)
            if incomplete_count > 0 and incomplete_count < total_count:
                ui.button(
                    f"Select Incomplete ({incomplete_count})",
                    icon="check_box",
                    on_click=self._toggle_select_incomplete,
                ).props("dense").classes("text-xs")

    def _get_status_icon_color(self, status: CitationStatus) -> tuple[str, str]:
        """Get icon and color for citation status.

        Args:
            status: Citation status

        Returns:
            Tuple of (icon_name, color_name)
        """
        if status == CitationStatus.COMPLETE:
            return "check_circle", "green-600"
        elif status == CitationStatus.ERROR:
            return "error", "red-600"
        elif status == CitationStatus.MANUAL_REVIEW:
            return "warning", "orange-600"
        elif status == CitationStatus.EXTRACTING:
            return "sync", "blue-600"
        else:  # QUEUED
            return "schedule", "gray-500"

    def _get_citation_status_text(self, citation: CitationBatchItem) -> str:
        """Get status text for citation.

        Args:
            citation: Citation item

        Returns:
            Status text string
        """
        if citation.status == CitationStatus.COMPLETE:
            if citation.has_existing_media:
                return "Complete - Citation updated"
            return "Complete - New image downloaded"
        elif citation.status == CitationStatus.ERROR:
            return f"Error: {citation.error or 'Unknown error'}"
        elif citation.status == CitationStatus.MANUAL_REVIEW:
            return "Needs manual entry"
        elif citation.status == CitationStatus.EXTRACTING:
            return "Extracting from FamilySearch..."
        else:  # QUEUED
            return "Queued"

    def _get_status_text(self) -> str:
        """Get summary status text (compact).

        Returns:
            Status summary string
        """
        total = len(self.citations)
        complete = sum(1 for c in self.citations if c.is_complete)
        error = sum(1 for c in self.citations if c.is_error)
        return f"{complete}/{total} complete ({error} errors)"

    def _get_filtered_sorted_citations(self) -> list[CitationBatchItem]:
        """Get filtered and sorted list of citations.

        Returns:
            Filtered and sorted citations
        """
        # Filter
        filtered = self.citations
        if self.filter_status == "incomplete":
            filtered = [c for c in filtered if c.needs_manual_entry or c.status == CitationStatus.QUEUED]
        elif self.filter_status == "complete":
            filtered = [c for c in filtered if c.is_complete]
        elif self.filter_status == "error":
            filtered = [c for c in filtered if c.is_error]

        # Sort
        if self.sort_by == "name":
            filtered = sorted(filtered, key=lambda c: c.full_name)
        elif self.sort_by == "status":
            # Sort by status priority: ERROR, MANUAL_REVIEW, QUEUED, COMPLETE
            status_priority = {
                CitationStatus.ERROR: 0,
                CitationStatus.MANUAL_REVIEW: 1,
                CitationStatus.QUEUED: 2,
                CitationStatus.EXTRACTING: 3,
                CitationStatus.COMPLETE: 4,
            }
            filtered = sorted(filtered, key=lambda c: status_priority.get(c.status, 99))

        return filtered

    def _on_citation_click(self, citation: CitationBatchItem) -> None:
        """Handle citation click event.

        Args:
            citation: Clicked citation
        """
        self.selected_citation = citation
        if self.on_citation_click:
            self.on_citation_click(citation)
        self.refresh()

    def _on_checkbox_change(self, citation_id: int, checked: bool) -> None:
        """Handle checkbox change event.

        Args:
            citation_id: Citation ID
            checked: Checkbox state
        """
        if checked:
            self.selected_ids.add(citation_id)
        else:
            self.selected_ids.discard(citation_id)

        if self.on_selection_change:
            self.on_selection_change(self.selected_ids)

        # Refresh to update "Process Selected" button enabled state
        self.refresh()

    def _on_filter_change(self, value: str) -> None:
        """Handle filter change.

        Args:
            value: New filter value
        """
        self.filter_status = value
        self.refresh()

    def _on_sort_change(self, value: str) -> None:
        """Handle sort change.

        Args:
            value: New sort value
        """
        self.sort_by = value
        self.refresh()

    def _toggle_select_all(self) -> None:
        """Toggle between selecting all citations and deselecting all."""
        total_count = len(self.citations)

        # If all are selected, deselect all
        if len(self.selected_ids) == total_count and total_count > 0:
            self.selected_ids.clear()
        else:
            # Otherwise, select all
            self.selected_ids = {c.citation_id for c in self.citations}

        if self.on_selection_change:
            self.on_selection_change(self.selected_ids)
        self.refresh()

    def _toggle_select_incomplete(self) -> None:
        """Toggle between selecting all incomplete and deselecting all."""
        incomplete_count = sum(
            1 for c in self.citations
            if c.needs_manual_entry or c.status == CitationStatus.QUEUED
        )

        # If all incomplete are selected, deselect all
        if len(self.selected_ids) == incomplete_count and incomplete_count > 0:
            self.selected_ids.clear()
        else:
            # Otherwise, select all incomplete
            self.selected_ids = {
                c.citation_id
                for c in self.citations
                if c.needs_manual_entry or c.status == CitationStatus.QUEUED
            }

        if self.on_selection_change:
            self.on_selection_change(self.selected_ids)
        self.refresh()

    def refresh(self) -> None:
        """Refresh the component UI."""
        if self.container:
            self.container.clear()
            with self.container:
                # Re-render content only (not the container itself)
                self._render_content()

    def update_citations(self, citations: list[CitationBatchItem]) -> None:
        """Update the citation list.

        Args:
            citations: New list of citations
        """
        self.citations = citations
        if self.status_label:
            self.status_label.text = self._get_status_text()
        self.refresh()
