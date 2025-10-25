"""Citation Manager Tab for RMCitecraft.

This tab provides the main citation management interface:
- Left panel: Citation list with census year selector and batch selection
- Right panel: Citation detail view (current vs. generated)
"""

import webbrowser
from typing import Optional

from loguru import logger
from nicegui import ui

from rmcitecraft.config import get_config
from rmcitecraft.models.citation import ParsedCitation
from rmcitecraft.parsers.citation_formatter import CitationFormatter
from rmcitecraft.parsers.familysearch_parser import FamilySearchParser
from rmcitecraft.repositories import CitationRepository, DatabaseConnection
from rmcitecraft.services.citation_import import get_citation_import_service
from rmcitecraft.services.command_queue import get_command_queue


class CitationManagerTab:
    """Citation Manager Tab component."""

    def __init__(self) -> None:
        """Initialize citation manager."""
        self.config = get_config()
        self.db = DatabaseConnection()
        self.repo = CitationRepository(self.db)
        self.parser = FamilySearchParser()
        self.formatter = CitationFormatter()

        # State
        self.selected_year: Optional[int] = None
        self.citations: list[dict] = []
        self.selected_citation: Optional[dict] = None
        self.parsed_citation: Optional[ParsedCitation] = None
        self.selected_citation_ids: set[int] = set()
        self.sort_by: str = "status"  # Default sort
        self.sort_reverse: bool = False

        # UI references (will be set when rendering)
        self.citation_list_container: Optional[ui.column] = None
        self.detail_container: Optional[ui.column] = None
        self.status_label: Optional[ui.label] = None
        self.pending_citations_container: Optional[ui.column] = None
        self.pending_badge: Optional[ui.badge] = None

        # Services
        self.citation_import_service = get_citation_import_service()
        self.command_queue = get_command_queue()

    def render(self) -> None:
        """Render the citation manager tab."""
        with ui.column().classes("w-full h-full gap-2"):
            # Top: Pending Citations from Extension (if any)
            self._render_pending_citations_section()

            # Middle: Citation Manager (collapsible)
            with ui.expansion("Citation Manager", icon="format_list_bulleted", value=True).classes(
                "w-full"
            ) as self.citation_manager_expansion:
                self._render_citation_manager_panel()

            # Bottom: Citation Details
            with ui.card().classes("w-full flex-grow"):
                self._render_citation_details_panel()

        # Auto-refresh pending citations every 5 seconds
        # Store timer reference so we can pause it when dialog is open
        self._refresh_timer = ui.timer(5.0, self._refresh_pending_citations)

    def _render_citation_manager_panel(self) -> None:
        """Render citation manager panel with list."""
        with ui.column().classes("w-full p-4 gap-4"):
            # Header
            ui.label("Citation Manager").classes("text-2xl font-bold")

            # Census year selector
            with ui.row().classes("w-full items-center gap-2"):
                ui.label("Census Year:").classes("text-sm font-medium w-24")

                # Get available census years from database
                years = self.repo.get_all_census_years()
                year_options = {year: f"{year} US Census" for year in sorted(years)}

                ui.select(
                    options=year_options,
                    value=None,
                    on_change=lambda e: self._on_year_selected(e.value),
                ).classes("w-64").props("outlined dense")

                self.status_label = ui.label("Select a census year to begin").classes(
                    "text-sm text-gray-600 flex-grow"
                )

                ui.button(
                    "Select All", on_click=self._on_select_all, icon="select_all"
                ).props("flat dense")

            # Sort controls
            with ui.row().classes("w-full items-center gap-2 px-2 py-1 bg-gray-50 border-b"):
                ui.label("Sort by:").classes("text-xs font-medium")

                ui.button(
                    "Status",
                    icon="sort",
                    on_click=lambda: self._on_sort_changed("status"),
                ).props("flat dense size=sm").classes("text-xs")

                ui.button(
                    "Name",
                    icon="sort_by_alpha",
                    on_click=lambda: self._on_sort_changed("name"),
                ).props("flat dense size=sm").classes("text-xs")

                ui.button(
                    "ID",
                    icon="tag",
                    on_click=lambda: self._on_sort_changed("id"),
                ).props("flat dense size=sm").classes("text-xs")

            # Citation list container (limit height to make it collapsible-friendly)
            with ui.scroll_area().classes("w-full border rounded").style("max-height: 400px"):
                self.citation_list_container = ui.column().classes("w-full p-2 gap-1")

    def _render_citation_details_panel(self) -> None:
        """Render citation details panel."""
        with ui.column().classes("w-full p-4 gap-4"):
            # Header
            ui.label("Citation Details").classes("text-2xl font-bold")

            # Detail container (will be populated when citation is selected)
            self.detail_container = ui.column().classes("w-full gap-4")

            with self.detail_container:
                ui.label("Select a citation to view details").classes(
                    "text-gray-500 italic"
                )

    def _on_year_selected(self, year: Optional[int]) -> None:
        """Handle census year selection.

        Args:
            year: Selected census year
        """
        if not year:
            return

        logger.info(f"Loading citations for {year}")
        self.selected_year = year
        self.selected_citation = None
        self.parsed_citation = None
        self.selected_citation_ids.clear()

        # Load citations from database
        self.citations = self.repo.get_citations_by_year(year)

        # Update status
        if self.status_label:
            self.status_label.set_text(f"Loaded {len(self.citations)} citations")

        # Update citation list
        self._update_citation_list()

        # Clear detail panel
        self._update_detail_panel()

    def _update_citation_list(self) -> None:
        """Update the citation list display with sorting."""
        if not self.citation_list_container:
            return

        self.citation_list_container.clear()

        with self.citation_list_container:
            if not self.citations:
                ui.label("No citations found for this year").classes(
                    "text-gray-500 italic p-4"
                )
                return

            # Sort citations based on current sort criteria
            sorted_citations = self._sort_citations(self.citations)

            for citation in sorted_citations:
                self._render_citation_item(citation)

    def _render_citation_item(self, citation: dict) -> None:
        """Render a single citation list item.

        Args:
            citation: Citation database row
        """
        citation_id = citation["CitationID"]
        source_name = citation["SourceName"]
        person_name = self._extract_person_name(source_name)

        # Parse citation to check for missing fields
        # Priority: Citation.Footnote > Source.Footnote > Free Form > SourceName
        parse_text = citation["Footnote"]

        # Try Source.Footnote from SourceFields BLOB
        if not parse_text:
            parse_text = self.repo.extract_field_from_blob(citation["SourceFields"], "Footnote")

        # Try Free Form citation from CitationFields BLOB
        if not parse_text and citation["TemplateID"] == 0:
            parse_text = self.repo.extract_freeform_text(citation["CitationFields"])

        # Fall back to SourceName
        if not parse_text:
            parse_text = source_name

        # Pass SourceName as second parameter for simplified format state/county extraction
        context_text = citation["ActualText"] if citation["ActualText"] else source_name

        parsed = self.parser.parse(
            parse_text, context_text, citation_id=citation_id
        )

        # Determine status
        has_formatted = bool(citation["Footnote"])
        is_complete = parsed.is_complete
        has_url = bool(parsed.familysearch_url)

        # Status icon and color (priority order)
        if not has_url:
            # Priority 1: Missing FamilySearch URL (critical error)
            status_icon = "error"
            status_color = "text-red-600"
            status_tooltip = "Missing FamilySearch URL"
            status_priority = 0  # Highest priority for sorting
        elif has_formatted:
            # Priority 2: Already formatted (complete)
            status_icon = "check_circle"
            status_color = "text-green-600"
            status_tooltip = "Already formatted"
            status_priority = 3  # Lowest priority (done)
        elif is_complete:
            # Priority 3: Ready to format
            status_icon = "radio_button_unchecked"
            status_color = "text-blue-600"
            status_tooltip = "Ready to format"
            status_priority = 2  # Medium priority
        else:
            # Priority 4: Missing fields
            status_icon = "warning"
            status_color = "text-amber-600"
            status_tooltip = f"Missing: {', '.join(parsed.missing_fields)}"
            status_priority = 1  # Higher priority than complete

        # Citation item card
        is_selected = citation_id in self.selected_citation_ids
        card_class = "cursor-pointer hover:bg-blue-50" + (
            " bg-blue-100" if is_selected else ""
        )

        with ui.card().classes(f"w-full p-2 {card_class}").on(
            "click", lambda c=citation: self._on_citation_selected(c)
        ):
            with ui.row().classes("w-full items-start gap-2"):
                # Checkbox for batch selection
                ui.checkbox(
                    value=is_selected,
                    on_change=lambda e, cid=citation_id: self._on_citation_checkbox_changed(
                        cid, e.value
                    ),
                ).props("dense").on("click.stop", lambda: None)  # Stop propagation

                # Status icon
                ui.icon(status_icon).classes(f"{status_color}").tooltip(status_tooltip)

                # Citation info
                with ui.column().classes("flex-grow gap-1"):
                    ui.label(person_name).classes("font-medium text-sm")
                    ui.label(source_name).classes("text-xs text-gray-600 truncate")

    def _on_citation_selected(self, citation: dict) -> None:
        """Handle citation selection.

        Args:
            citation: Selected citation database row
        """
        logger.debug(f"Citation selected: {citation['CitationID']}")
        self.selected_citation = citation

        # Determine what text to parse
        # Priority: Citation.Footnote > Source.Footnote > Free Form > SourceName
        parse_text = citation["Footnote"]

        # Try Source.Footnote from SourceFields BLOB
        if not parse_text:
            parse_text = self.repo.extract_field_from_blob(citation["SourceFields"], "Footnote")

        # Try Free Form citation from CitationFields BLOB
        if not parse_text and citation["TemplateID"] == 0:
            parse_text = self.repo.extract_freeform_text(citation["CitationFields"])

        # Fall back to SourceName
        if not parse_text:
            parse_text = citation["SourceName"]

        # Pass SourceName as second parameter for simplified format state/county extraction
        # Priority: ActualText if not empty, else SourceName
        context_text = citation["ActualText"] if citation["ActualText"] else citation["SourceName"]

        self.parsed_citation = self.parser.parse(
            parse_text,
            context_text,
            citation_id=citation["CitationID"],
        )

        # Update detail panel
        self._update_detail_panel()

    def _on_citation_checkbox_changed(self, citation_id: int, checked: bool) -> None:
        """Handle citation checkbox change.

        Args:
            citation_id: Citation ID
            checked: New checkbox state
        """
        if checked:
            self.selected_citation_ids.add(citation_id)
        else:
            self.selected_citation_ids.discard(citation_id)

        # Update status
        if self.status_label:
            selected_count = len(self.selected_citation_ids)
            total_count = len(self.citations)
            self.status_label.set_text(
                f"{selected_count} of {total_count} citations selected"
            )

    def _on_select_all(self) -> None:
        """Select/deselect all citations."""
        if len(self.selected_citation_ids) == len(self.citations):
            # Deselect all
            self.selected_citation_ids.clear()
        else:
            # Select all
            self.selected_citation_ids = {c["CitationID"] for c in self.citations}

        # Update UI
        self._update_citation_list()

        # Update status
        if self.status_label:
            selected_count = len(self.selected_citation_ids)
            total_count = len(self.citations)
            self.status_label.set_text(
                f"{selected_count} of {total_count} citations selected"
            )

    def _update_detail_panel(self) -> None:
        """Update the detail panel with selected citation."""
        if not self.detail_container:
            return

        self.detail_container.clear()

        with self.detail_container:
            if not self.selected_citation or not self.parsed_citation:
                ui.label("Select a citation to view details").classes(
                    "text-gray-500 italic"
                )
                return

            citation = self.selected_citation
            parsed = self.parsed_citation

            # Citation header with FamilySearch button
            with ui.row().classes("w-full items-center justify-between"):
                ui.label(f"Citation ID: {citation['CitationID']}").classes(
                    "text-xl font-bold"
                )

                # Add "Open FamilySearch" button if URL exists
                if parsed.familysearch_url:
                    ui.button(
                        "Open FamilySearch",
                        icon="open_in_new",
                        on_click=lambda: self._open_familysearch_url(parsed.familysearch_url),
                    ).props("color=primary flat")

            ui.separator()

            # Current citation (from database)
            with ui.expansion("Current Citation (Database)", icon="storage", value=True).classes(
                "w-full"
            ):
                with ui.column().classes("gap-2 p-2"):
                    ui.label("Source Name:").classes("text-xs font-medium text-gray-600")
                    ui.label(citation["SourceName"]).classes("text-sm mb-2")

                    # For Free Form citations (TemplateID = 0), extract text from CitationFields BLOB
                    if citation["TemplateID"] == 0:
                        freeform_text = self.repo.extract_freeform_text(citation["CitationFields"])
                        if freeform_text:
                            ui.label("Free Form Citation:").classes(
                                "text-xs font-medium text-gray-600"
                            )
                            ui.label(freeform_text).classes("text-sm bg-yellow-50 p-2 rounded mb-2")

                    # Extract Footnote, ShortFootnote, Bibliography from SourceFields BLOB
                    source_footnote = self.repo.extract_field_from_blob(citation["SourceFields"], "Footnote")
                    source_short = self.repo.extract_field_from_blob(citation["SourceFields"], "ShortFootnote")
                    source_bib = self.repo.extract_field_from_blob(citation["SourceFields"], "Bibliography")

                    # Show existing formatted citations from database (prefer CitationTable, fall back to SourceTable)
                    footnote_text = citation["Footnote"] or source_footnote
                    if footnote_text:
                        ui.label("Footnote (Database):").classes(
                            "text-xs font-medium text-gray-600"
                        )
                        ui.markdown(f"_{footnote_text}_").classes(
                            "text-sm bg-blue-50 p-2 rounded mb-2"
                        )
                    else:
                        ui.label("Footnote:").classes("text-xs font-medium text-gray-600")
                        ui.label("(not set)").classes("text-sm text-gray-400 italic mb-2")

                    short_text = citation["ShortFootnote"] or source_short
                    if short_text:
                        ui.label("Short Footnote (Database):").classes(
                            "text-xs font-medium text-gray-600"
                        )
                        ui.markdown(f"_{short_text}_").classes(
                            "text-sm bg-blue-50 p-2 rounded mb-2"
                        )
                    else:
                        ui.label("Short Footnote:").classes("text-xs font-medium text-gray-600")
                        ui.label("(not set)").classes("text-sm text-gray-400 italic mb-2")

                    bib_text = citation["Bibliography"] or source_bib
                    if bib_text:
                        ui.label("Bibliography (Database):").classes(
                            "text-xs font-medium text-gray-600"
                        )
                        ui.markdown(f"_{bib_text}_").classes(
                            "text-sm bg-blue-50 p-2 rounded mb-2"
                        )
                    else:
                        ui.label("Bibliography:").classes("text-xs font-medium text-gray-600")
                        ui.label("(not set)").classes("text-sm text-gray-400 italic mb-2")

            # Parsed data
            with ui.expansion("Parsed Data", icon="data_object", value=True).classes("w-full"):
                self._render_parsed_data(parsed)

            # Generated citation (if complete)
            if parsed.is_complete:
                with ui.expansion("Generated Citation", icon="auto_fix_high", value=True).classes(
                    "w-full"
                ):
                    self._render_generated_citation(parsed)
            else:
                # Show missing fields warning
                with ui.card().classes("w-full bg-amber-50 border-amber-200"):
                    with ui.row().classes("items-center gap-2 p-2"):
                        ui.icon("warning").classes("text-amber-600")
                        with ui.column().classes("flex-grow"):
                            ui.label("Citation Incomplete").classes("font-medium")
                            ui.label(
                                f"Missing fields: {', '.join(parsed.missing_fields)}"
                            ).classes("text-sm text-gray-700")

    def _render_parsed_data(self, parsed: ParsedCitation) -> None:
        """Render parsed citation data.

        Args:
            parsed: Parsed citation
        """
        with ui.column().classes("gap-2 p-2"):
            fields = [
                ("Census Year", parsed.census_year),
                ("State", parsed.state),
                ("County", parsed.county),
                ("Person Name", parsed.person_name),
                ("Town/Ward", parsed.town_ward),
                ("Enumeration District", parsed.enumeration_district),
                ("Sheet", parsed.sheet),
                ("Family Number", parsed.family_number),
                ("Dwelling Number", parsed.dwelling_number),
                ("FamilySearch URL", parsed.familysearch_url),
                ("Access Date", parsed.access_date),
            ]

            for label, value in fields:
                with ui.row().classes("gap-2 items-start"):
                    ui.label(f"{label}:").classes("text-xs font-medium text-gray-600 w-40")
                    if value:
                        ui.label(str(value)).classes("text-sm")
                    else:
                        ui.label("(not found)").classes("text-sm text-red-500 italic")

    def _render_generated_citation(self, parsed: ParsedCitation) -> None:
        """Render generated citation formats.

        Args:
            parsed: Parsed citation
        """
        footnote, short_footnote, bibliography = self.formatter.format(parsed)

        with ui.column().classes("gap-4 p-2"):
            # Footnote
            ui.label("Full Footnote:").classes("text-xs font-medium text-gray-600")
            ui.markdown(f"_{footnote}_").classes("text-sm bg-gray-50 p-2 rounded")

            # Short footnote
            ui.label("Short Footnote:").classes("text-xs font-medium text-gray-600")
            ui.markdown(f"_{short_footnote}_").classes("text-sm bg-gray-50 p-2 rounded")

            # Bibliography
            ui.label("Bibliography:").classes("text-xs font-medium text-gray-600")
            ui.markdown(f"_{bibliography}_").classes("text-sm bg-gray-50 p-2 rounded")

            # Action buttons
            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button(
                    "Copy Footnote",
                    icon="content_copy",
                    on_click=lambda: self._on_copy_footnote(footnote),
                ).props("outlined")
                ui.button(
                    "Update Database",
                    icon="save",
                    color="primary",
                    on_click=lambda: self._on_update_single_citation(parsed, footnote, short_footnote, bibliography),
                ).props("unelevated")

    def _extract_person_name(self, source_name: str) -> str:
        """Extract person name from source name.

        Args:
            source_name: RM Source Name

        Returns:
            Person name (surname, given) or source name if not found
        """
        # Pattern: Fed Census: YYYY, State, County [...] Surname, GivenName
        parts = source_name.split("]")
        if len(parts) >= 2:
            # Get everything after the last ']'
            name_part = parts[-1].strip()
            if name_part:
                return name_part

        return source_name

    def _open_familysearch_url(self, url: str) -> None:
        """Open FamilySearch URL in default browser.

        Args:
            url: FamilySearch URL to open
        """
        try:
            logger.info(f"Opening FamilySearch URL: {url}")
            webbrowser.open(url)
            ui.notify("Opening FamilySearch page in browser", type="positive")
        except Exception as e:
            logger.error(f"Failed to open FamilySearch URL: {e}")
            ui.notify(f"Failed to open browser: {str(e)}", type="negative")

    def _on_copy_footnote(self, footnote: str) -> None:
        """Copy footnote to clipboard.

        Args:
            footnote: Formatted footnote text
        """
        try:
            # Use NiceGUI's clipboard functionality
            ui.run_javascript(f'navigator.clipboard.writeText({footnote!r})')
            ui.notify("Footnote copied to clipboard", type="positive")
            logger.debug("Footnote copied to clipboard")
        except Exception as e:
            logger.error(f"Failed to copy footnote: {e}")
            ui.notify(f"Failed to copy: {str(e)}", type="negative")

    def _on_update_single_citation(
        self,
        parsed: ParsedCitation,
        footnote: str,
        short_footnote: str,
        bibliography: str,
    ) -> None:
        """Update a single citation in the database.

        Args:
            parsed: Parsed citation data
            footnote: Generated footnote
            short_footnote: Generated short footnote
            bibliography: Generated bibliography
        """
        try:
            logger.info(f"Updating citation {parsed.citation_id}")

            # Update database
            success = self.repo.update_citation_fields(
                citation_id=parsed.citation_id,
                footnote=footnote,
                short_footnote=short_footnote,
                bibliography=bibliography,
            )

            if success:
                ui.notify(
                    f"Citation {parsed.citation_id} updated successfully",
                    type="positive",
                )

                # Refresh the citation list to show updated status
                if self.selected_year:
                    self.citations = self.repo.get_citations_by_year(self.selected_year)
                    self._update_citation_list()

                # Reload the selected citation to show updated data
                if self.selected_citation:
                    self._on_citation_selected(self.selected_citation)
            else:
                ui.notify(
                    f"Failed to update citation {parsed.citation_id}",
                    type="negative",
                )
        except Exception as e:
            logger.error(f"Error updating citation: {e}")
            ui.notify(f"Error: {str(e)}", type="negative")

    def _get_citation_sort_key(self, citation: dict) -> tuple:
        """Get sort key for a citation based on current sort criteria.

        Args:
            citation: Citation database row

        Returns:
            Tuple containing sort keys
        """
        # Parse citation to get status info
        source_name = citation["SourceName"]
        parse_text = citation["Footnote"]

        if not parse_text:
            parse_text = self.repo.extract_field_from_blob(citation["SourceFields"], "Footnote")

        if not parse_text and citation["TemplateID"] == 0:
            parse_text = self.repo.extract_freeform_text(citation["CitationFields"])

        if not parse_text:
            parse_text = source_name

        context_text = citation["ActualText"] if citation["ActualText"] else source_name
        parsed = self.parser.parse(parse_text, context_text, citation_id=citation["CitationID"])

        # Calculate status priority
        has_formatted = bool(citation["Footnote"])
        is_complete = parsed.is_complete
        has_url = bool(parsed.familysearch_url)

        if not has_url:
            status_priority = 0  # Highest priority (missing URL)
        elif has_formatted:
            status_priority = 3  # Lowest priority (done)
        elif is_complete:
            status_priority = 2  # Medium priority
        else:
            status_priority = 1  # Higher priority (missing fields)

        person_name = self._extract_person_name(source_name)

        return {
            "status": status_priority,
            "name": person_name.lower(),
            "id": citation["CitationID"],
        }

    def _sort_citations(self, citations: list[dict]) -> list[dict]:
        """Sort citations based on current sort criteria.

        Args:
            citations: List of citation database rows

        Returns:
            Sorted list of citations
        """
        if not citations:
            return citations

        # Get sort keys for all citations
        citation_keys = [(c, self._get_citation_sort_key(c)) for c in citations]

        # Sort by selected criteria
        if self.sort_by == "status":
            sorted_citations = sorted(
                citation_keys,
                key=lambda x: (x[1]["status"], x[1]["name"]),
                reverse=self.sort_reverse,
            )
        elif self.sort_by == "name":
            sorted_citations = sorted(
                citation_keys,
                key=lambda x: x[1]["name"],
                reverse=self.sort_reverse,
            )
        elif self.sort_by == "id":
            sorted_citations = sorted(
                citation_keys,
                key=lambda x: x[1]["id"],
                reverse=self.sort_reverse,
            )
        else:
            sorted_citations = citation_keys

        return [c for c, _ in sorted_citations]

    def _on_sort_changed(self, sort_by: str) -> None:
        """Handle sort criteria change.

        Args:
            sort_by: Sort field (status, name, id)
        """
        # Toggle reverse if same field clicked
        if self.sort_by == sort_by:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_by = sort_by
            self.sort_reverse = False

        logger.debug(f"Sort changed to: {sort_by} (reverse={self.sort_reverse})")

        # Update UI
        self._update_citation_list()

        # Update status label
        if self.status_label:
            direction = "↓" if self.sort_reverse else "↑"
            self.status_label.set_text(
                f"Sorted by {sort_by} {direction} ({len(self.citations)} citations)"
            )

    def _render_pending_citations_section(self) -> None:
        """Render section for pending citations imported from extension."""
        pending = self.citation_import_service.get_pending()

        if not pending:
            # Don't show section if no pending citations
            return

        with ui.expansion(
            f"Pending Citations from Extension ({len(pending)})",
            icon="cloud_download",
            value=True
        ).classes("w-full bg-blue-50"):
            with ui.column().classes("w-full p-4 gap-2"):
                self.pending_citations_container = ui.column().classes("w-full gap-2")
                self._update_pending_citations_display()

    def _update_pending_citations_display(self) -> None:
        """Update the pending citations display."""
        if not self.pending_citations_container:
            return

        self.pending_citations_container.clear()

        pending = self.citation_import_service.get_pending()

        with self.pending_citations_container:
            if not pending:
                ui.label("No pending citations").classes("text-gray-500 italic")
                return

            for citation_data in pending:
                self._render_pending_citation_item(citation_data)

    def _render_pending_citation_item(self, citation_data: dict) -> None:
        """Render a single pending citation item.

        Args:
            citation_data: Citation data from import service
        """
        data = citation_data["data"]
        citation_id = citation_data["id"]

        person_name = data.get("name", "Unknown Person")
        census_year = data.get("censusYear", "Unknown")
        event_place = data.get("eventPlace", "Unknown Location")

        with ui.card().classes("w-full p-3 bg-white"):
            with ui.row().classes("w-full items-start gap-3"):
                # Citation info
                with ui.column().classes("flex-grow gap-1"):
                    ui.label(person_name).classes("font-medium text-base")
                    ui.label(f"{census_year} Census - {event_place}").classes(
                        "text-sm text-gray-600"
                    )

                    # Show key fields
                    fields = []
                    if data.get("enumerationDistrict"):
                        fields.append(f"ED: {data['enumerationDistrict']}")
                    if data.get("lineNumber"):
                        fields.append(f"Line: {data['lineNumber']}")
                    if data.get("sheetNumber"):
                        fields.append(f"Sheet: {data['sheetNumber']}")

                    if fields:
                        ui.label(" | ".join(fields)).classes("text-xs text-gray-500")

                # Action buttons
                with ui.column().classes("gap-2"):
                    ui.button(
                        "Download Image",
                        icon="download",
                        on_click=lambda cid=citation_id, url=data.get("familySearchUrl"): self._on_download_image_clicked(cid, url),
                    ).props("dense color=primary outlined")

                    ui.button(
                        "Process",
                        icon="play_arrow",
                        on_click=lambda cdata=citation_data: self._on_process_pending_citation(cdata),
                    ).props("dense color=positive")

                    ui.button(
                        "Dismiss",
                        icon="close",
                        on_click=lambda cid=citation_id: self._on_dismiss_pending_citation(cid),
                    ).props("dense flat")

    def _on_download_image_clicked(self, citation_id: str, familysearch_url: str) -> None:
        """Handle download image button click.

        Args:
            citation_id: Citation ID
            familysearch_url: FamilySearch URL for the citation
        """
        try:
            if not familysearch_url:
                ui.notify("No FamilySearch URL available", type="warning")
                return

            # Queue download_image command for extension
            command_id = self.command_queue.add(
                "download_image",
                {
                    "citation_id": citation_id,
                    "url": familysearch_url
                }
            )

            logger.info(f"Queued download_image command: {command_id} for citation {citation_id}")
            ui.notify("Download image command sent to extension", type="positive")

        except Exception as e:
            logger.error(f"Failed to queue download image command: {e}")
            ui.notify(f"Failed to queue command: {str(e)}", type="negative")

    def _on_process_pending_citation(self, citation_data: dict) -> None:
        """Process a pending citation (format and prepare for database).

        Args:
            citation_data: Citation data from import service
        """
        try:
            data = citation_data["data"]
            citation_id = citation_data["id"]

            logger.info(f"Processing pending citation: {citation_id}")

            # Show processing dialog
            self._show_citation_processing_dialog(citation_id, data)

        except Exception as e:
            logger.error(f"Failed to process pending citation: {e}")
            ui.notify(f"Failed to process: {str(e)}", type="negative")

    def _show_citation_processing_dialog(self, citation_id: str, data: dict) -> None:
        """Show dialog for processing a citation with missing data input and preview.

        Args:
            citation_id: Citation ID
            data: Citation data dictionary
        """
        logger.info(f"Opening processing dialog for citation: {citation_id}")

        # PAUSE THE AUTO-REFRESH TIMER while dialog is open
        # This prevents the table refresh from destroying the dialog
        if hasattr(self, '_refresh_timer'):
            self._refresh_timer.deactivate()
            logger.info("Paused auto-refresh timer")

        # Close any existing dialog first
        if hasattr(self, '_processing_dialog') and self._processing_dialog:
            try:
                self._processing_dialog.close()
                delattr(self, '_processing_dialog')
            except:
                pass

        # Create dialog with no_backdrop_dismiss AND persistent
        # Store as a strong reference to prevent garbage collection
        self._processing_dialog = ui.dialog()
        self._processing_dialog.props('no-backdrop-dismiss persistent maximized')

        # Add event handlers to track dialog lifecycle
        self._processing_dialog.on('show', lambda: logger.info(f"Dialog SHOWN for citation {citation_id}"))
        self._processing_dialog.on('hide', lambda: logger.warning(f"Dialog HIDDEN for citation {citation_id}"))
        self._processing_dialog.on('before-hide', lambda: logger.warning(f"Dialog BEFORE-HIDE event for citation {citation_id}"))

        census_year = data.get('censusYear', 'Unknown')
        logger.debug(f"Processing citation data: year={census_year}, name={data.get('name')}")

        normalized_data = self._normalize_extension_data(data)
        missing_fields = self._identify_missing_fields(data, census_year)
        logger.debug(f"Missing fields identified: {missing_fields}")

        with self._processing_dialog, ui.card().classes("w-full max-w-7xl h-[85vh]"):
            # Header with person info
            with ui.row().classes("w-full items-center justify-between p-3 bg-blue-50 mb-2"):
                with ui.column().classes("gap-0"):
                    ui.label(f"Person: {data.get('name', 'Unknown')}").classes("text-lg font-bold")
                    ui.label(f"{census_year} Census - {data.get('eventPlace', 'Unknown')}").classes("text-sm text-gray-600")

                # FamilySearch link in header
                if data.get('familySearchUrl'):
                    ui.button(
                        "Open FamilySearch Page",
                        icon="open_in_new",
                        on_click=lambda: webbrowser.open(data['familySearchUrl'])
                    ).props("dense outlined color=primary")

            # Two-column layout for compact display
            with ui.row().classes("w-full gap-2 flex-grow overflow-auto p-2"):
                # LEFT COLUMN - Data fields
                with ui.column().classes("w-1/2 gap-2"):
                    # Key citation fields (always visible, compact)
                    with ui.card().classes("w-full p-2"):
                        ui.label("Key Citation Fields").classes("text-sm font-bold mb-1")
                        self._render_compact_data(normalized_data, [
                            'censusYear', 'name', 'eventPlace', 'enumerationDistrict',
                            'sheetNumber', 'lineNumber', 'familyNumber'
                        ])

                    # Missing fields form (if any)
                    if missing_fields:
                        with ui.card().classes("w-full p-2 bg-amber-50"):
                            ui.label("⚠ Missing Required Fields").classes("text-sm font-bold mb-1 text-amber-800")
                            self._render_missing_fields_form(missing_fields, data)

                    # Additional fields (collapsed)
                    with ui.expansion("Additional Fields", icon="expand_more", value=False).classes("w-full"):
                        with ui.column().classes("gap-1 p-2"):
                            self._render_compact_data(normalized_data, [
                                'age', 'sex', 'birthYear', 'race', 'relationship',
                                'maritalStatus', 'occupation', 'industry'
                            ])

                    # Raw data (collapsed)
                    with ui.expansion("FamilySearch Raw Data", icon="cloud", value=False).classes("w-full"):
                        with ui.column().classes("gap-0 p-2 text-xs"):
                            for key, value in sorted(data.items()):
                                if value:
                                    ui.label(f"{key}: {value}").classes("text-xs break-all")

                # RIGHT COLUMN - Citation preview
                with ui.column().classes("w-1/2 gap-2"):
                    with ui.card().classes("w-full p-2 bg-green-50"):
                        ui.label("Generated Citations").classes("text-sm font-bold mb-2")

                        # Full Footnote
                        ui.label("Full Footnote:").classes("text-xs font-semibold text-gray-700 mt-1")
                        preview_footnote = self._generate_citation_preview(data)
                        ui.markdown(f"_{preview_footnote}_").classes("text-xs bg-white p-2 rounded")

                        # Short Footnote
                        ui.label("Short Footnote:").classes("text-xs font-semibold text-gray-700 mt-2")
                        preview_short = self._generate_short_citation_preview(data)
                        ui.markdown(f"_{preview_short}_").classes("text-xs bg-white p-2 rounded")

                        # Bibliography
                        ui.label("Bibliography:").classes("text-xs font-semibold text-gray-700 mt-2")
                        preview_bib = self._generate_bibliography_preview(data)
                        ui.markdown(f"_{preview_bib}_").classes("text-xs bg-white p-2 rounded")

                    # Citation format info
                    cite_format = normalized_data.get('citationFormat', 'Unknown')
                    with ui.card().classes("w-full p-2"):
                        ui.label("Citation Format Details").classes("text-xs font-bold mb-1")
                        ui.label(f"Format: {cite_format}").classes("text-xs")
                        if normalized_data.get('affiliatePublicationNumber'):
                            ui.label(f"NARA: {normalized_data['affiliatePublicationNumber']}").classes("text-xs")

            # Action buttons at bottom
            with ui.row().classes("w-full justify-end gap-2 p-3 border-t mt-2"):
                ui.button("Cancel", on_click=lambda: self._close_processing_dialog()).props("flat")
                ui.button(
                    "Save to RootsMagic",
                    icon="save",
                    on_click=lambda: self._save_processed_citation(self._processing_dialog, citation_id, data)
                ).props("color=primary unelevated")

        logger.info(f"Dialog content built successfully for citation {citation_id}")
        logger.info(f"About to open dialog... (dialog object: {self._processing_dialog})")

        try:
            self._processing_dialog.open()

            # Force dialog to be visible with JavaScript
            ui.run_javascript('''
                setTimeout(() => {
                    const dialogs = document.querySelectorAll('.q-dialog');
                    dialogs.forEach(dialog => {
                        if (dialog && dialog.style) {
                            dialog.style.display = 'flex';
                            dialog.style.visibility = 'visible';
                            dialog.style.opacity = '1';
                            dialog.style.zIndex = '9999';
                        }
                    });
                }, 100);
            ''')

            logger.info(f"Dialog.open() called successfully for citation {citation_id}")
        except Exception as e:
            logger.error(f"Exception while opening dialog: {e}", exc_info=True)
            raise

    def _close_processing_dialog(self) -> None:
        """Close the processing dialog."""
        logger.info("Close dialog method called")
        if hasattr(self, '_processing_dialog'):
            logger.info("Closing processing dialog...")
            self._processing_dialog.close()
            delattr(self, '_processing_dialog')
            logger.info("Processing dialog closed and reference removed")
        else:
            logger.warning("Close called but no _processing_dialog attribute found")

        # RESUME THE AUTO-REFRESH TIMER after dialog closes
        if hasattr(self, '_refresh_timer'):
            self._refresh_timer.activate()
            logger.info("Resumed auto-refresh timer")

    def _render_compact_data(self, data: dict, keys: list[str]) -> None:
        """Render data fields in a compact format.

        Args:
            data: Data dictionary
            keys: List of keys to display
        """
        for key in keys:
            value = data.get(key)
            if value:
                label_text = key.replace('_', ' ').title()
                with ui.row().classes("w-full items-start gap-1"):
                    ui.label(f"{label_text}:").classes("text-xs font-medium text-gray-700 w-32")
                    ui.label(str(value)).classes("text-xs text-gray-900 flex-grow break-all")

    def _identify_missing_fields(self, data: dict, census_year: int | str) -> list[str]:
        """Identify required fields that are missing based on census year.

        Args:
            data: Citation data dictionary
            census_year: Census year

        Returns:
            List of missing required field names
        """
        missing = []

        try:
            year = int(census_year) if census_year else 0

            # Always required
            if not data.get('name'):
                missing.append('name')
            if not data.get('eventPlace'):
                missing.append('eventPlace')

            # Year-specific requirements
            if year >= 1900 and year <= 1950:
                # 1900-1950: ED, sheet, family number typically required
                if not data.get('enumerationDistrict'):
                    missing.append('enumerationDistrict')
                if not data.get('sheetNumber'):
                    missing.append('sheetNumber')

        except (ValueError, TypeError):
            logger.warning(f"Invalid census year for missing field detection: {census_year}")

        return missing

    def _render_missing_fields_form(self, missing_fields: list[str], data: dict) -> None:
        """Render form inputs for missing required fields.

        Args:
            missing_fields: List of missing field names
            data: Citation data dictionary (will be updated with user input)
        """
        field_labels = {
            'name': 'Person Name',
            'eventPlace': 'Event Place (e.g., "Ohio, Noble")',
            'enumerationDistrict': 'Enumeration District (ED)',
            'sheetNumber': 'Sheet Number',
            'familyNumber': 'Family Number',
            'lineNumber': 'Line Number',
            'pageNumber': 'Page Number'
        }

        for field in missing_fields:
            label = field_labels.get(field, field.replace('_', ' ').title())
            with ui.row().classes("w-full items-center gap-2 mb-2"):
                ui.label(f"{label}:").classes("w-48")
                ui.input(
                    value=data.get(field, ''),
                    on_change=lambda e, f=field: data.update({f: e.value})
                ).classes("flex-grow").props("outlined dense")

    def _generate_citation_preview(self, data: dict) -> str:
        """Generate a preview of the formatted citation.

        Args:
            data: Citation data dictionary

        Returns:
            Preview text string
        """
        # Simplified preview for now
        # In a full implementation, this would call the citation formatter

        name = data.get('name', 'Unknown Person')
        year = data.get('censusYear', '????')
        place = data.get('eventPlace', 'Unknown Place')
        ed = data.get('enumerationDistrict', '')
        sheet = data.get('sheetNumber', '')
        family = data.get('familyNumber', '')
        url = data.get('familySearchUrl', '')

        preview = f"{year} U.S. census, {place}"

        if ed:
            preview += f", enumeration district (ED) {ed}"
        if sheet:
            preview += f", sheet {sheet}"
        if family:
            preview += f", family {family}"

        preview += f", {name}"

        if url:
            preview += f"; imaged, FamilySearch ({url})"

        return preview

    def _generate_short_citation_preview(self, data: dict) -> str:
        """Generate a preview of the short footnote citation format.

        Args:
            data: Citation data dictionary

        Returns:
            Short footnote preview text string
        """
        # Short footnote format: Census Year, State County, person name
        name = data.get('name', 'Unknown Person')
        year = data.get('censusYear', '????')
        place = data.get('eventPlace', 'Unknown Place')

        # Parse place into state and county
        place_parts = [p.strip() for p in place.split(',')]
        if len(place_parts) >= 2:
            # Assume format: "Township/City, County, State, Country"
            county = place_parts[-3] if len(place_parts) >= 3 else place_parts[-2]
            state = place_parts[-2] if len(place_parts) >= 3 else place_parts[-1]
            short_place = f"{state}, {county}"
        else:
            short_place = place

        return f"{year} U.S. census, {short_place}, {name}"

    def _generate_bibliography_preview(self, data: dict) -> str:
        """Generate a preview of the bibliography citation format.

        Args:
            data: Citation data dictionary

        Returns:
            Bibliography preview text string
        """
        # Bibliography format: Census year and location, then repository
        year = data.get('censusYear', '????')
        place = data.get('eventPlace', 'Unknown Place')

        # Parse place to get state and county
        place_parts = [p.strip() for p in place.split(',')]
        if len(place_parts) >= 2:
            county = place_parts[-3] if len(place_parts) >= 3 else place_parts[-2]
            state = place_parts[-2] if len(place_parts) >= 3 else place_parts[-1]
            bib_place = f"{state}, {county}"
        else:
            bib_place = place

        # Include NARA publication if available
        nara_pub = data.get('affiliatePublicationNumber', '')

        preview = f"{year} U.S. census, {bib_place}"

        if nara_pub:
            preview += f"; NARA microfilm publication {nara_pub}"

        preview += "; digital images, <i>FamilySearch</i>"

        return preview

    def _render_data_table(self, title: str, data: dict) -> None:
        """Render a data dictionary as a formatted table.

        Args:
            title: Table title
            data: Data dictionary to display
        """
        if not data:
            ui.label("No data available").classes("text-sm text-gray-500 italic")
            return

        # Create a grid layout for the data
        with ui.column().classes("w-full gap-1"):
            for key, value in sorted(data.items()):
                # Skip None values and internal fields
                if value is None or key.startswith('_'):
                    continue

                # Format the key as a readable label
                label = key.replace('_', ' ').replace('eventPlace', 'Event Place').title()

                # Format the value
                if isinstance(value, bool):
                    display_value = "Yes" if value else "No"
                elif isinstance(value, (list, dict)):
                    display_value = str(value)
                else:
                    display_value = str(value)

                # Create a row for this field
                with ui.row().classes("w-full items-start gap-2 py-1 border-b border-gray-100"):
                    ui.label(f"{label}:").classes("w-48 font-medium text-sm text-gray-700")
                    ui.label(display_value).classes("flex-grow text-sm text-gray-900 break-all")

    def _normalize_extension_data(self, data: dict) -> dict:
        """Normalize FamilySearch extension data into a consistent format.

        Args:
            data: Raw extension data dictionary

        Returns:
            Normalized data dictionary
        """
        normalized = {}

        # Census year - parse from eventDate if not directly available
        census_year = data.get('censusYear')
        if not census_year and data.get('eventDate'):
            # Try to extract year from eventDate
            event_date = str(data.get('eventDate', ''))
            if event_date.isdigit() and len(event_date) == 4:
                census_year = event_date
        normalized['censusYear'] = census_year

        # Person information
        normalized['name'] = data.get('name')
        normalized['sex'] = data.get('sex')
        normalized['age'] = data.get('age')
        normalized['birthYear'] = data.get('birthYear')
        normalized['birthplace'] = data.get('birthplace')
        normalized['race'] = data.get('race')
        normalized['relationship'] = data.get('relationship')
        normalized['maritalStatus'] = data.get('maritalStatus')
        normalized['occupation'] = data.get('occupation')
        normalized['industry'] = data.get('industry')

        # Location information
        normalized['eventPlace'] = data.get('eventPlace')
        normalized['eventPlaceOriginal'] = data.get('eventPlaceOriginal')

        # Parse place into components
        place = data.get('eventPlace', '')
        if place:
            place_parts = [p.strip() for p in place.split(',')]
            if len(place_parts) >= 4:
                normalized['township_city'] = place_parts[0]
                normalized['county'] = place_parts[1]
                normalized['state'] = place_parts[2]
                normalized['country'] = place_parts[3]
            elif len(place_parts) >= 3:
                normalized['county'] = place_parts[0]
                normalized['state'] = place_parts[1]
                normalized['country'] = place_parts[2]

        # Census location fields
        normalized['enumerationDistrict'] = data.get('enumerationDistrict')
        normalized['enumerationDistrictLocation'] = data.get('enumerationDistrictLocation')
        normalized['lineNumber'] = data.get('lineNumber')
        normalized['pageNumber'] = data.get('pageNumber')
        normalized['sheetNumber'] = data.get('sheetNumber')
        normalized['sheetLetter'] = data.get('sheetLetter')
        normalized['familyNumber'] = data.get('familyNumber')
        normalized['dwellingNumber'] = data.get('dwellingNumber')

        # Source metadata
        normalized['imageNumber'] = data.get('imageNumber')
        normalized['affiliatePublicationNumber'] = data.get('affiliatePublicationNumber')
        normalized['familySearchUrl'] = data.get('familySearchUrl')
        normalized['extractedAt'] = data.get('extractedAt')

        # Determine citation format based on census year
        if census_year:
            try:
                year = int(census_year)
                if year <= 1870:
                    normalized['citationFormat'] = 'pre-1880 (page number, no ED)'
                elif 1880 <= year <= 1940:
                    normalized['citationFormat'] = '1880-1940 (sheet number, ED required)'
                elif year == 1950:
                    normalized['citationFormat'] = '1950 (page number, ED required)'
            except (ValueError, TypeError):
                pass

        return normalized

    def _save_processed_citation(self, dialog: ui.dialog, citation_id: str, data: dict) -> None:
        """Save the processed citation (currently just removes from pending).

        Args:
            dialog: Dialog to close
            citation_id: Citation ID
            data: Updated citation data
        """
        try:
            # TODO: Implement actual database update
            # For now, just remove from pending queue
            self.citation_import_service.remove(citation_id)

            logger.info(f"Processed citation: {citation_id}")
            ui.notify("Citation processed successfully", type="positive")

            dialog.close()
            self._refresh_pending_citations()

        except Exception as e:
            logger.error(f"Failed to save processed citation: {e}")
            ui.notify(f"Failed to save: {str(e)}", type="negative")

    def _on_dismiss_pending_citation(self, citation_id: str) -> None:
        """Dismiss a pending citation.

        Args:
            citation_id: Citation ID to dismiss
        """
        try:
            self.citation_import_service.remove(citation_id)
            logger.info(f"Dismissed pending citation: {citation_id}")
            ui.notify("Citation dismissed", type="positive")
            self._refresh_pending_citations()
        except Exception as e:
            logger.error(f"Failed to dismiss citation: {e}")
            ui.notify(f"Failed to dismiss: {str(e)}", type="negative")

    def _refresh_pending_citations(self) -> None:
        """Refresh the pending citations display."""
        if self.pending_citations_container:
            self._update_pending_citations_display()

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.db:
            self.db.close()
