"""
Census Extraction Viewer/Editor Tab.

Provides UI for:
- Viewing extracted census data from FamilySearch
- Editing person records and extended fields
- Managing field-level quality assessments
- Linking to RootsMagic citations
- Triggering new extractions from ARK URLs
"""

import asyncio
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger
from nicegui import ui

from rmcitecraft.database.census_extraction_db import (
    CensusExtractionRepository,
    CensusPage,
    CensusPerson,
    FieldQuality,
    RMTreeLink,
    get_census_repository,
)


# Field categories for organized display
CORE_FIELDS = [
    ("full_name", "Full Name"),
    ("given_name", "Given Name"),
    ("surname", "Surname"),
    ("name_suffix", "Suffix"),
    ("sex", "Sex"),
    ("race", "Race"),
    ("age", "Age"),
    ("marital_status", "Marital Status"),
    ("relationship_to_head", "Relationship"),
    ("birthplace", "Birthplace"),
    ("birthplace_father", "Father's Birthplace"),
    ("birthplace_mother", "Mother's Birthplace"),
    ("occupation", "Occupation"),
    ("industry", "Industry"),
    ("worker_class", "Worker Class"),
]

PAGE_FIELDS = [
    ("census_year", "Census Year"),
    ("state", "State"),
    ("county", "County"),
    ("township_city", "Township/City"),
    ("enumeration_district", "E.D."),
    ("supervisor_district", "Supervisor District"),
    ("sheet_number", "Sheet Number"),
    ("sheet_letter", "Sheet Letter"),
    ("page_number", "Page Number"),
    ("stamp_number", "Stamp"),
    ("enumerator_name", "Enumerator"),
]

LEGIBILITY_OPTIONS = ["clear", "faded", "damaged", "illegible", ""]


class CensusExtractionViewerTab:
    """Census Extraction Viewer/Editor Tab."""

    def __init__(self):
        """Initialize the viewer tab."""
        self.repository = get_census_repository()
        self.selected_person: CensusPerson | None = None
        self.selected_page: CensusPage | None = None
        self.extended_fields: dict[str, Any] = {}
        self.quality_data: dict[str, FieldQuality] = {}
        self.is_editing: bool = False

        # UI references
        self.person_list_column: ui.column | None = None
        self.detail_column: ui.column | None = None
        self.quality_column: ui.column | None = None
        self.search_input: ui.input | None = None
        self.year_select: ui.select | None = None
        self.status_label: ui.label | None = None

        # Edit mode inputs (stored for saving)
        self.edit_inputs: dict[str, ui.input] = {}

    def render(self) -> None:
        """Render the census extraction viewer tab."""
        with ui.column().classes("w-full p-4 gap-4"):
            # Header
            with ui.row().classes("w-full items-center gap-4"):
                ui.icon("folder_open", size="2rem").classes("text-green-600")
                ui.label("Census Extraction Viewer").classes("text-2xl font-bold")
                ui.label("View and edit FamilySearch census extractions").classes(
                    "text-gray-500"
                )

            # Stats bar
            self._render_stats_bar()

            # Search/Filter controls
            with ui.row().classes("w-full items-center gap-4"):
                self.search_input = ui.input(
                    label="Search by name",
                    placeholder="Enter surname...",
                    on_change=lambda e: self._search_persons(),
                ).classes("w-64")

                self.year_select = ui.select(
                    options={
                        None: "All Years",
                        1950: "1950",
                        1940: "1940",
                        1930: "1930",
                        1920: "1920",
                        1910: "1910",
                        1900: "1900",
                    },
                    value=None,
                    label="Census Year",
                    on_change=lambda e: self._search_persons(),
                ).classes("w-32")

                ui.button("Search", icon="search", on_click=self._search_persons).props(
                    "color=primary"
                )

                ui.button(
                    "Import from URL", icon="cloud_download", on_click=self._show_import_dialog
                ).props("color=green")

                self.status_label = ui.label("").classes("text-sm text-gray-500 ml-auto")

            # Main content area - three columns
            with ui.row().classes("w-full gap-4"):
                # Left: Person list
                with ui.card().classes("w-1/4 p-2"):
                    ui.label("Extracted Persons").classes("font-bold mb-2")
                    with ui.scroll_area().classes("h-[500px]"):
                        self.person_list_column = ui.column().classes("w-full gap-1")

                # Center: Person details
                with ui.card().classes("w-2/5 p-2"):
                    ui.label("Person Details").classes("font-bold mb-2")
                    with ui.scroll_area().classes("h-[500px]"):
                        self.detail_column = ui.column().classes("w-full gap-2")
                        with self.detail_column:
                            ui.label("Select a person to view details").classes(
                                "text-gray-400 italic text-sm"
                            )

                # Right: Quality Assessment
                with ui.card().classes("flex-1 p-2"):
                    ui.label("Quality Assessment").classes("font-bold mb-2")
                    with ui.scroll_area().classes("h-[500px]"):
                        self.quality_column = ui.column().classes("w-full gap-2")
                        with self.quality_column:
                            ui.label("Select a person to assess quality").classes(
                                "text-gray-400 italic text-sm"
                            )

            # Load initial data
            self._search_persons()

    def _render_stats_bar(self) -> None:
        """Render statistics bar."""
        stats = self.repository.get_extraction_stats()

        with ui.row().classes("w-full items-center gap-6 bg-gray-100 p-2 rounded"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("people", size="sm").classes("text-blue-500")
                ui.label(f"{stats.get('total_persons', 0)} Persons").classes("text-sm")

            with ui.row().classes("items-center gap-2"):
                ui.icon("description", size="sm").classes("text-green-500")
                ui.label(f"{stats.get('total_pages', 0)} Pages").classes("text-sm")

            with ui.row().classes("items-center gap-2"):
                ui.icon("link", size="sm").classes("text-purple-500")
                ui.label(f"{stats.get('rmtree_links', 0)} RootsMagic Links").classes(
                    "text-sm"
                )

            # Year breakdown
            by_year = stats.get("by_year", {})
            if by_year:
                year_text = ", ".join(
                    f"{year}: {data['persons']}"
                    for year, data in sorted(by_year.items(), reverse=True)
                )
                ui.label(f"By Year: {year_text}").classes("text-xs text-gray-500 ml-auto")

    def _search_persons(self) -> None:
        """Search for persons based on current filters."""
        surname = self.search_input.value if self.search_input else None
        year = self.year_select.value if self.year_select else None

        persons = self.repository.search_persons(
            surname=surname if surname else None,
            census_year=year,
        )

        self._refresh_person_list(persons)
        self.status_label.set_text(f"Found {len(persons)} persons")

    def _refresh_person_list(self, persons: list[CensusPerson]) -> None:
        """Refresh the person list display."""
        self.person_list_column.clear()

        with self.person_list_column:
            if not persons:
                ui.label("No persons found").classes("text-gray-400 italic text-sm")
                return

            for person in persons:
                self._render_person_list_item(person)

    def _render_person_list_item(self, person: CensusPerson) -> None:
        """Render a single person in the list."""
        # Get page info for year display
        is_selected = (
            self.selected_person and self.selected_person.person_id == person.person_id
        )

        with ui.card().classes(
            f"w-full p-2 cursor-pointer hover:bg-blue-50 "
            f"{'bg-blue-100 border-blue-500' if is_selected else ''}"
        ).on("click", lambda p=person: self._select_person(p)):
            with ui.row().classes("items-center gap-2"):
                # Target indicator
                if person.is_target_person:
                    ui.icon("star", size="xs").classes("text-yellow-500")

                ui.label(person.full_name or f"{person.given_name} {person.surname}").classes(
                    "text-sm font-medium"
                )

            with ui.row().classes("items-center gap-2 text-xs text-gray-500"):
                if person.age:
                    ui.label(f"Age {person.age}")
                if person.birthplace:
                    ui.label(f"b. {person.birthplace}")
                if person.occupation:
                    ui.label(f"• {person.occupation}")

    def _select_person(self, person: CensusPerson) -> None:
        """Select a person and show details."""
        self.selected_person = person
        self.is_editing = False

        # Load extended fields
        self.extended_fields = self.repository.get_person_fields(person.person_id)

        # Load quality data
        qualities = self.repository.get_field_quality(person.person_id)
        self.quality_data = {q.field_name: q for q in qualities}

        # Load page info
        if person.page_id:
            with self.repository._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM census_page WHERE page_id = ?", (person.page_id,)
                ).fetchone()
                if row:
                    self.selected_page = self.repository._row_to_page(row)

        # Refresh displays
        self._refresh_detail_view()
        self._refresh_quality_view()
        self._search_persons()  # Refresh list to show selection

    def _refresh_detail_view(self) -> None:
        """Refresh the detail view for selected person."""
        self.detail_column.clear()
        self.edit_inputs.clear()

        with self.detail_column:
            if not self.selected_person:
                ui.label("Select a person to view details").classes(
                    "text-gray-400 italic text-sm"
                )
                return

            person = self.selected_person

            # Action buttons
            with ui.row().classes("w-full gap-2 mb-2"):
                if self.is_editing:
                    ui.button("Save", icon="save", on_click=self._save_person).props(
                        "color=green size=sm"
                    )
                    ui.button(
                        "Cancel", icon="close", on_click=self._cancel_edit
                    ).props("color=red size=sm outline")
                else:
                    ui.button("Edit", icon="edit", on_click=self._start_edit).props(
                        "color=primary size=sm"
                    )

                # FamilySearch link
                if person.familysearch_ark:
                    ui.button(
                        "View on FamilySearch",
                        icon="open_in_new",
                        on_click=lambda: ui.navigate.to(person.familysearch_ark, new_tab=True),
                    ).props("color=blue size=sm outline")

            # Person info section
            ui.label("Person Information").classes("font-bold text-sm mt-2")
            with ui.element("div").classes("grid grid-cols-2 gap-2"):
                for field_name, label in CORE_FIELDS:
                    value = getattr(person, field_name, "") or ""
                    self._render_field(field_name, label, value)

            # Extended fields section
            if self.extended_fields:
                ui.separator().classes("my-2")
                ui.label("Extended Fields").classes("font-bold text-sm")
                with ui.element("div").classes("grid grid-cols-2 gap-2"):
                    for field_name, value in sorted(self.extended_fields.items()):
                        # Clean up field name for display
                        display_name = field_name.replace("_", " ").title()
                        self._render_field(field_name, display_name, str(value))

            # Page info section
            if self.selected_page:
                ui.separator().classes("my-2")
                ui.label("Census Page Information").classes("font-bold text-sm")
                with ui.element("div").classes("grid grid-cols-2 gap-2"):
                    for field_name, label in PAGE_FIELDS:
                        value = getattr(self.selected_page, field_name, "") or ""
                        self._render_field(
                            f"page_{field_name}", label, str(value), editable=False
                        )

            # RootsMagic links
            links = self.repository.get_links_for_citation(person.person_id) if person.person_id else []
            # Actually get links by census_person_id
            with self.repository._connect() as conn:
                link_rows = conn.execute(
                    "SELECT * FROM rmtree_link WHERE census_person_id = ?",
                    (person.person_id,),
                ).fetchall()

            if link_rows:
                ui.separator().classes("my-2")
                ui.label("RootsMagic Links").classes("font-bold text-sm")
                for row in link_rows:
                    with ui.row().classes("items-center gap-2 text-xs"):
                        ui.icon("link", size="xs").classes("text-purple-500")
                        ui.label(f"Citation #{row['rmtree_citation_id']}")
                        if row["rmtree_person_id"]:
                            ui.label(f"Person #{row['rmtree_person_id']}")
                        ui.label(f"Confidence: {row['match_confidence']:.0%}").classes(
                            "text-gray-500"
                        )

            # Metadata
            ui.separator().classes("my-2")
            ui.label("Metadata").classes("font-bold text-sm text-gray-500")
            with ui.column().classes("text-xs text-gray-500"):
                ui.label(f"Person ID: {person.person_id}")
                ui.label(f"Page ID: {person.page_id}")
                if person.familysearch_ark:
                    ui.label(f"ARK: {person.familysearch_ark}").classes("break-all")

    def _render_field(
        self, field_name: str, label: str, value: str, editable: bool = True
    ) -> None:
        """Render a single field (view or edit mode)."""
        with ui.column().classes("gap-0"):
            ui.label(label).classes("text-xs text-gray-500")
            if self.is_editing and editable:
                inp = ui.input(value=value).classes("text-sm").props("dense")
                self.edit_inputs[field_name] = inp
            else:
                ui.label(value or "—").classes("text-sm")

    def _start_edit(self) -> None:
        """Enter edit mode."""
        self.is_editing = True
        self._refresh_detail_view()

    def _cancel_edit(self) -> None:
        """Cancel edit mode."""
        self.is_editing = False
        self._refresh_detail_view()

    def _save_person(self) -> None:
        """Save edited person data."""
        if not self.selected_person:
            return

        try:
            # Collect changes
            updates = {}
            extended_updates = {}

            for field_name, inp in self.edit_inputs.items():
                new_value = inp.value

                # Check if it's a core field or extended field
                if hasattr(self.selected_person, field_name):
                    old_value = getattr(self.selected_person, field_name) or ""
                    if str(new_value) != str(old_value):
                        updates[field_name] = new_value
                elif field_name in self.extended_fields:
                    if str(new_value) != str(self.extended_fields.get(field_name, "")):
                        extended_updates[field_name] = new_value

            # Update database
            if updates:
                with self.repository._connect() as conn:
                    for field_name, value in updates.items():
                        conn.execute(
                            f"UPDATE census_person SET {field_name} = ? WHERE person_id = ?",
                            (value, self.selected_person.person_id),
                        )
                    logger.info(f"Updated {len(updates)} core fields")

            if extended_updates:
                with self.repository._connect() as conn:
                    for field_name, value in extended_updates.items():
                        conn.execute(
                            """
                            UPDATE census_person_field
                            SET field_value = ?
                            WHERE person_id = ? AND field_name = ?
                            """,
                            (value, self.selected_person.person_id, field_name),
                        )
                    logger.info(f"Updated {len(extended_updates)} extended fields")

            ui.notify("Changes saved", type="positive")

            # Reload person data
            person = self.repository.get_person_by_ark(self.selected_person.familysearch_ark)
            if person:
                self._select_person(person)
            else:
                self.is_editing = False
                self._refresh_detail_view()

        except Exception as e:
            logger.error(f"Failed to save: {e}")
            ui.notify(f"Save failed: {e}", type="negative")

    def _refresh_quality_view(self) -> None:
        """Refresh the quality assessment view."""
        self.quality_column.clear()

        with self.quality_column:
            if not self.selected_person:
                ui.label("Select a person to assess quality").classes(
                    "text-gray-400 italic text-sm"
                )
                return

            person = self.selected_person

            # Add quality button
            ui.button(
                "Add Quality Assessment",
                icon="add",
                on_click=self._show_add_quality_dialog,
            ).props("color=green size=sm").classes("mb-2")

            # Existing quality assessments
            if self.quality_data:
                ui.label("Field Quality Assessments").classes("font-bold text-sm")

                for field_name, quality in sorted(self.quality_data.items()):
                    self._render_quality_item(quality)
            else:
                ui.label("No quality assessments yet").classes(
                    "text-gray-400 italic text-sm"
                )

            # Quick quality overview
            ui.separator().classes("my-3")
            ui.label("Quick Quality Check").classes("font-bold text-sm")
            ui.label(
                "Click a field to add quality assessment"
            ).classes("text-xs text-gray-500 mb-2")

            # List core fields with quality indicators
            with ui.column().classes("gap-1"):
                for field_name, label in CORE_FIELDS:
                    value = getattr(person, field_name, "") or ""
                    if value:
                        has_quality = field_name in self.quality_data
                        with ui.row().classes(
                            "items-center gap-2 cursor-pointer hover:bg-gray-100 p-1 rounded"
                        ).on("click", lambda fn=field_name: self._show_add_quality_dialog(fn)):
                            # Quality indicator
                            if has_quality:
                                q = self.quality_data[field_name]
                                color = self._get_confidence_color(q.confidence_score)
                                ui.icon("check_circle", size="xs").classes(color)
                            else:
                                ui.icon("radio_button_unchecked", size="xs").classes(
                                    "text-gray-300"
                                )

                            ui.label(f"{label}: {value}").classes("text-xs")

    def _render_quality_item(self, quality: FieldQuality) -> None:
        """Render a quality assessment item."""
        color = self._get_confidence_color(quality.confidence_score)

        with ui.card().classes("w-full p-2 mb-1"):
            with ui.row().classes("items-center gap-2"):
                ui.label(quality.field_name.replace("_", " ").title()).classes(
                    "font-medium text-sm"
                )

                # Confidence badge
                ui.badge(
                    f"{quality.confidence_score:.0%}",
                    color=color.replace("text-", ""),
                ).classes("text-xs")

                # Edit/Delete buttons
                ui.button(
                    icon="edit",
                    on_click=lambda q=quality: self._edit_quality(q),
                ).props("flat dense size=xs")
                ui.button(
                    icon="delete",
                    on_click=lambda q=quality: self._delete_quality(q),
                ).props("flat dense size=xs color=red")

            # Details
            with ui.column().classes("text-xs text-gray-500 mt-1"):
                if quality.source_legibility:
                    ui.label(f"Legibility: {quality.source_legibility}")
                if quality.transcription_note:
                    ui.label(f"Note: {quality.transcription_note}")
                if quality.human_verified:
                    ui.label(f"Verified by {quality.verified_by}").classes("text-green-600")

    def _get_confidence_color(self, score: float) -> str:
        """Get color class based on confidence score."""
        if score >= 0.9:
            return "text-green-600"
        elif score >= 0.7:
            return "text-yellow-600"
        elif score >= 0.5:
            return "text-orange-600"
        else:
            return "text-red-600"

    def _show_add_quality_dialog(self, field_name: str | None = None) -> None:
        """Show dialog to add quality assessment."""
        if not self.selected_person:
            return

        # Get available fields
        all_fields = [fn for fn, _ in CORE_FIELDS]
        all_fields.extend(self.extended_fields.keys())

        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label("Add Quality Assessment").classes("text-lg font-bold mb-2")

            field_select = ui.select(
                options=all_fields,
                value=field_name,
                label="Field",
            ).classes("w-full")

            confidence_slider = ui.slider(min=0, max=100, value=80).props(
                "label-always"
            )
            ui.label("Confidence Score").classes("text-xs text-gray-500")

            legibility_select = ui.select(
                options=LEGIBILITY_OPTIONS,
                value="clear",
                label="Source Legibility",
            ).classes("w-full")

            note_input = ui.textarea(
                label="Transcription Note", placeholder="Any notes about this field..."
            ).classes("w-full")

            verified_check = ui.checkbox("Human Verified")
            verified_by = ui.input(label="Verified By").classes("w-full")

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button(
                    "Save",
                    on_click=lambda: self._save_quality(
                        dialog,
                        field_select.value,
                        confidence_slider.value / 100,
                        legibility_select.value,
                        note_input.value,
                        verified_check.value,
                        verified_by.value,
                    ),
                ).props("color=green")

        dialog.open()

    def _save_quality(
        self,
        dialog,
        field_name: str,
        confidence: float,
        legibility: str,
        note: str,
        verified: bool,
        verified_by: str,
    ) -> None:
        """Save quality assessment."""
        if not self.selected_person or not field_name:
            ui.notify("Please select a field", type="warning")
            return

        quality = FieldQuality(
            person_id=self.selected_person.person_id,
            field_name=field_name,
            confidence_score=confidence,
            source_legibility=legibility,
            transcription_note=note,
            human_verified=verified,
            verified_by=verified_by if verified else "",
            verified_at=datetime.now() if verified else None,
        )

        try:
            self.repository.insert_field_quality(quality)
            ui.notify("Quality assessment saved", type="positive")
            dialog.close()

            # Reload quality data
            qualities = self.repository.get_field_quality(self.selected_person.person_id)
            self.quality_data = {q.field_name: q for q in qualities}
            self._refresh_quality_view()

        except Exception as e:
            logger.error(f"Failed to save quality: {e}")
            ui.notify(f"Save failed: {e}", type="negative")

    def _edit_quality(self, quality: FieldQuality) -> None:
        """Edit existing quality assessment."""
        # For simplicity, delete and re-add
        self._delete_quality(quality, confirm=False)
        self._show_add_quality_dialog(quality.field_name)

    def _delete_quality(self, quality: FieldQuality, confirm: bool = True) -> None:
        """Delete quality assessment."""

        def do_delete():
            with self.repository._connect() as conn:
                conn.execute(
                    "DELETE FROM field_quality WHERE quality_id = ?",
                    (quality.quality_id,),
                )
            ui.notify("Quality assessment deleted", type="info")

            # Reload
            qualities = self.repository.get_field_quality(self.selected_person.person_id)
            self.quality_data = {q.field_name: q for q in qualities}
            self._refresh_quality_view()

        if confirm:
            with ui.dialog() as dialog, ui.card():
                ui.label(f"Delete quality assessment for {quality.field_name}?")
                with ui.row().classes("justify-end gap-2 mt-4"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    ui.button(
                        "Delete",
                        on_click=lambda: (do_delete(), dialog.close()),
                    ).props("color=red")
            dialog.open()
        else:
            do_delete()

    def _show_import_dialog(self) -> None:
        """Show dialog to import from FamilySearch URL."""
        with ui.dialog() as self._import_dialog, ui.card().classes("w-[500px]"):
            ui.label("Import from FamilySearch").classes("text-lg font-bold mb-2")

            self._import_url_input = ui.input(
                label="FamilySearch ARK URL",
                placeholder="https://www.familysearch.org/ark:/61903/1:1:...",
            ).classes("w-full")

            self._import_year_select = ui.select(
                options={
                    1950: "1950",
                    1940: "1940",
                    1930: "1930",
                    1920: "1920",
                    1910: "1910",
                    1900: "1900",
                    1880: "1880",
                    1870: "1870",
                    1860: "1860",
                    1850: "1850",
                },
                value=1950,
                label="Census Year",
            ).classes("w-full")

            ui.label("Optional: Link to RootsMagic").classes("text-sm font-medium mt-2")
            self._import_citation_input = ui.input(
                label="CitationID", placeholder="e.g., 10370"
            ).classes("w-full")
            self._import_person_input = ui.input(
                label="PersonID (RIN)", placeholder="e.g., 2776"
            ).classes("w-full")

            self._import_status_label = ui.label("").classes("text-sm text-gray-500 mt-2")

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=self._import_dialog.close).props("flat")
                # NiceGUI handles async functions directly - don't use asyncio.create_task
                self._import_btn = ui.button(
                    "Import",
                    on_click=self._do_import,
                ).props("color=green")

        self._import_dialog.open()

    async def _do_import(self) -> None:
        """Perform the import operation using instance variables."""
        # Read values from instance variables
        url = self._import_url_input.value
        year = self._import_year_select.value
        citation_id = self._import_citation_input.value
        person_id = self._import_person_input.value

        if not url or "familysearch.org" not in url:
            ui.notify("Please enter a valid FamilySearch URL", type="warning")
            return

        from rmcitecraft.services.familysearch_census_extractor import (
            extract_census_from_citation,
        )

        try:
            self._import_btn.disable()
            self._import_status_label.set_text("Connecting to Chrome...")

            result = await extract_census_from_citation(
                url,
                year,
                rmtree_citation_id=int(citation_id) if citation_id else None,
                rmtree_person_id=int(person_id) if person_id else None,
            )

            if result.success:
                ui.notify(
                    f"Successfully imported: {result.extracted_data.get('primary_name', 'Unknown')}",
                    type="positive",
                )
                self._import_dialog.close()
                self._search_persons()  # Refresh list
            else:
                self._import_status_label.set_text(f"Error: {result.error_message}")
                ui.notify(f"Import failed: {result.error_message}", type="negative")

        except Exception as e:
            logger.error(f"Import failed: {e}")
            self._import_status_label.set_text(f"Error: {e}")
            ui.notify(f"Import failed: {e}", type="negative")
        finally:
            self._import_btn.enable()
