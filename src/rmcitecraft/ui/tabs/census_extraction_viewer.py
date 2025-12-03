"""
Census Extraction Viewer/Editor Tab.

Provides UI for:
- Viewing extracted census data from FamilySearch
- Editing person records and extended fields
- Managing field-level quality assessments
- Linking to RootsMagic citations
- Viewing dynamically generated census form templates
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger
from nicegui import ui

from rmcitecraft.database.census_extraction_db import (
    CensusPage,
    CensusPerson,
    FieldQuality,
    RMTreeLink,
    get_census_repository,
)
from rmcitecraft.services.census_rmtree_matcher import (
    CensusRMTreeMatcher,
    MatchCandidate,
    MatchResult,
    create_matcher,
)

# State abbreviations for compact display
STATE_ABBREVIATIONS = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC",
}

# NOTE: Sample lines in the 1950 census vary by form version (5 versions of Form P1).
# We determine if a person is a sample person by checking if they have sample line
# field data (columns 21-33), NOT by hardcoded line numbers.

# Field categories organized by census form sections
IDENTITY_FIELDS = [
    ("full_name", "Name"),
    ("relationship_to_head", "Relationship"),
    ("sex", "Sex"),
    ("race", "Race"),
    ("age", "Age"),
    ("marital_status", "Marital"),
    ("birthplace", "Birthplace"),
]

EMPLOYMENT_FIELDS = [
    ("employment_status", "Status (15)"),
    ("any_work_last_week", "Work Last Wk (16)"),
    ("looking_for_work", "Looking (17)"),
    ("has_job_not_at_work", "Job Not At Work (18)"),
    ("hours_worked", "Hours (19)"),
    ("occupation", "Occupation (20a)"),
    ("industry", "Industry (20b)"),
    ("worker_class", "Class (20c)"),
]

SAMPLE_LINE_FIELDS = [
    # Residence 1949
    ("residence_1949_same_house", "Same House 1949 (21)"),
    ("residence_1949_on_farm", "On Farm 1949 (22)"),
    ("residence_1949_same_county", "Same County 1949 (23)"),
    ("residence_1949_different_location", "Different Location (24)"),
    # Education
    ("highest_grade_attended", "Highest Grade (26)"),
    ("completed_grade", "Completed (27)"),
    ("school_attendance", "School Since Feb (28)"),
    # Income
    ("weeks_looking_for_work", "Wks Looking (29)"),
    ("weeks_worked_1949", "Wks Worked 1949 (30)"),
    ("income_wages_1949", "Wages 1949 (31)"),
    ("income_self_employment_1949", "Self-Emp 1949 (32)"),
    ("income_other_1949", "Other Inc 1949 (33)"),
    # Veteran
    ("veteran_status", "Veteran"),
    ("veteran_ww1", "WW1"),
    ("veteran_ww2", "WW2"),
]

DWELLING_FIELDS = [
    ("dwelling_number", "Dwelling #"),
    ("household_id", "Household ID"),
    ("street_name", "Street"),
    ("house_number", "House #"),
    ("is_dwelling_on_farm", "On Farm (4)"),
    ("farm_3_plus_acres", "3+ Acres (5)"),
]

LEGIBILITY_OPTIONS = ["clear", "faded", "damaged", "illegible", ""]


def get_state_abbrev(state: str) -> str:
    """Get state abbreviation, or return original if not found."""
    return STATE_ABBREVIATIONS.get(state, state[:2].upper() if state else "")


class CensusExtractionViewerTab:
    """Census Extraction Viewer/Editor Tab with improved UX."""

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
        self.secondary_tabs: ui.tabs | None = None
        self.quality_panel: ui.column | None = None
        self.metadata_panel: ui.column | None = None
        self.search_input: ui.input | None = None
        self.year_select: ui.select | None = None
        self.status_label: ui.label | None = None

        # Expansion states
        self.sample_expanded: bool = True
        self.links_expanded: bool = False

        # Edit mode inputs
        self.edit_inputs: dict[str, ui.input] = {}

        # Field history cache
        self.field_history: dict[str, list] = {}  # field_name -> list of history entries

    def render(self) -> None:
        """Render the census extraction viewer tab."""
        with ui.column().classes("w-full p-4 gap-4"):
            # Header
            self._render_header()

            # Stats bar
            self._render_stats_bar()

            # Search/Filter controls
            self._render_search_controls()

            # Main content area - three columns
            with ui.row().classes("w-full gap-4"):
                # Left: Person list (25%)
                with ui.card().classes("w-1/4 p-2"):
                    ui.label("Extracted Persons").classes("font-bold mb-2")
                    with ui.scroll_area().classes("h-[550px]"):
                        self.person_list_column = ui.column().classes("w-full gap-1")

                # Center: Person details (50%)
                with ui.card().classes("w-1/2 p-2"):
                    with ui.scroll_area().classes("h-[550px]"):
                        self.detail_column = ui.column().classes("w-full gap-3")
                        with self.detail_column:
                            self._render_empty_detail_state()

                # Right: Secondary panel (25%) - Tabbed
                with ui.card().classes("w-1/4 p-2"):
                    self.secondary_tabs = ui.tabs().classes("w-full")
                    with self.secondary_tabs:
                        quality_tab = ui.tab("Quality", icon="verified")
                        metadata_tab = ui.tab("Metadata", icon="info")

                    with ui.tab_panels(self.secondary_tabs, value=quality_tab).classes("w-full"):
                        with ui.tab_panel(quality_tab):
                            with ui.scroll_area().classes("h-[480px]"):
                                self.quality_panel = ui.column().classes("w-full gap-2")
                                with self.quality_panel:
                                    ui.label("Select a person").classes("text-gray-400 italic text-sm")

                        with ui.tab_panel(metadata_tab):
                            with ui.scroll_area().classes("h-[480px]"):
                                self.metadata_panel = ui.column().classes("w-full gap-2")
                                with self.metadata_panel:
                                    ui.label("Select a person").classes("text-gray-400 italic text-sm")

            # Load initial data
            self._search_persons()

    def _render_header(self) -> None:
        """Render page header."""
        with ui.row().classes("w-full items-center gap-4"):
            ui.icon("folder_open", size="2rem").classes("text-green-600")
            ui.label("Census Extraction Viewer").classes("text-2xl font-bold")
            ui.label("View and verify FamilySearch census extractions").classes("text-gray-500")

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
                ui.label(f"{stats.get('rmtree_links', 0)} RootsMagic Links").classes("text-sm")

            # Year breakdown
            by_year = stats.get("by_year", {})
            if by_year:
                year_text = ", ".join(
                    f"{year}: {data['persons']}"
                    for year, data in sorted(by_year.items(), reverse=True)
                )
                ui.label(f"By Year: {year_text}").classes("text-xs text-gray-500 ml-auto")

    def _render_search_controls(self) -> None:
        """Render search and filter controls."""
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

            ui.button("Search", icon="search", on_click=self._search_persons).props("color=primary")

            ui.button(
                "Import from URL", icon="cloud_download", on_click=self._show_import_dialog
            ).props("color=green")

            self.status_label = ui.label("").classes("text-sm text-gray-500 ml-auto")

    def _render_empty_detail_state(self) -> None:
        """Render placeholder when no person selected."""
        with ui.column().classes("w-full h-full items-center justify-center"):
            ui.icon("person_search", size="4rem").classes("text-gray-300")
            ui.label("Select a person to view details").classes("text-gray-400 italic")

    # =========================================================================
    # Person List
    # =========================================================================

    def _search_persons(self) -> None:
        """Search for persons based on current filters."""
        surname = self.search_input.value if self.search_input else None
        year = self.year_select.value if self.year_select else None

        persons = self.repository.search_persons(
            surname=surname if surname else None,
            census_year=year,
        )

        self._refresh_person_list(persons)
        if self.status_label:
            self.status_label.set_text(f"Found {len(persons)} persons")

    def _refresh_person_list(self, persons: list[CensusPerson]) -> None:
        """Refresh the person list display."""
        self.person_list_column.clear()

        with self.person_list_column:
            if not persons:
                ui.label("No persons found").classes("text-gray-400 italic text-sm")
                return

            # Group by page for context
            persons_by_page: dict[int, list[tuple[CensusPerson, CensusPage | None]]] = {}
            page_cache: dict[int, CensusPage] = {}

            for person in persons:
                if person.page_id not in page_cache:
                    with self.repository._connect() as conn:
                        row = conn.execute(
                            "SELECT * FROM census_page WHERE page_id = ?", (person.page_id,)
                        ).fetchone()
                        if row:
                            page_cache[person.page_id] = self.repository._row_to_page(row)

                page = page_cache.get(person.page_id)
                if person.page_id not in persons_by_page:
                    persons_by_page[person.page_id] = []
                persons_by_page[person.page_id].append((person, page))

            for page_id, person_page_list in persons_by_page.items():
                for person, page in person_page_list:
                    self._render_person_list_item(person, page)

    def _render_person_list_item(self, person: CensusPerson, page: CensusPage | None) -> None:
        """Render enhanced person list item."""
        is_selected = (
            self.selected_person and self.selected_person.person_id == person.person_id
        )

        with ui.card().classes(
            f"w-full p-2 cursor-pointer hover:bg-blue-50 "
            f"{'bg-blue-100 border-blue-500 border-2' if is_selected else 'border border-gray-200'}"
        ).on("click", lambda p=person: self._select_person(p)):
            # Top row: Line#, Name, Year badge
            with ui.row().classes("w-full items-center gap-2"):
                # Target indicator - person whose ARK was used to initiate the extraction
                if person.is_target_person:
                    ui.icon("star", size="xs").classes("text-yellow-500").tooltip(
                        "Target person - extraction was initiated from this person's FamilySearch record"
                    )

                # Line number
                if person.line_number:
                    ui.badge(f"L{person.line_number}", color="gray").classes("text-xs")

                # Name
                name = person.full_name or f"{person.given_name} {person.surname}"
                ui.label(name).classes("text-sm font-medium flex-1 truncate")

                # Year badge
                if page:
                    ui.badge(str(page.census_year), color="blue").classes("text-xs")

            # Bottom row: Location, Age
            with ui.row().classes("w-full items-center gap-2 text-xs text-gray-500 mt-1"):
                if page:
                    state_abbrev = get_state_abbrev(page.state)
                    location = f"{page.county} Co., {state_abbrev}"
                    ui.label(location).classes("truncate")

                    # ED and Sheet/Page
                    if page.enumeration_district:
                        ed_display = f"ED {page.enumeration_district}"
                        sheet = page.sheet_number or page.page_number or page.stamp_number
                        if sheet:
                            ed_display += f", Sh {sheet}"
                        ui.label(ed_display).classes("text-gray-400")

                if person.age:
                    ui.label(f"Age {person.age}")

    # =========================================================================
    # Person Details
    # =========================================================================

    def _select_person(self, person: CensusPerson) -> None:
        """Select a person and show details."""
        self.selected_person = person
        self.is_editing = False

        # Load extended fields
        self.extended_fields = self.repository.get_person_fields(person.person_id)

        # Load quality data
        qualities = self.repository.get_field_quality(person.person_id)
        self.quality_data = {q.field_name: q for q in qualities}

        # Load field history
        history_list = self.repository.get_field_history(person.person_id)
        self.field_history = {}
        for h in history_list:
            if h.field_name not in self.field_history:
                self.field_history[h.field_name] = []
            self.field_history[h.field_name].append(h)

        # Load page info
        if person.page_id:
            with self.repository._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM census_page WHERE page_id = ?", (person.page_id,)
                ).fetchone()
                if row:
                    self.selected_page = self.repository._row_to_page(row)

        # Refresh all displays
        self._refresh_detail_view()
        self._refresh_quality_panel()
        self._refresh_metadata_panel()
        self._search_persons()  # Refresh list to show selection

    def _refresh_detail_view(self) -> None:
        """Refresh the main detail view with organized cards."""
        self.detail_column.clear()
        self.edit_inputs.clear()

        with self.detail_column:
            if not self.selected_person:
                self._render_empty_detail_state()
                return

            person = self.selected_person
            page = self.selected_page

            # Card A: Census Location & Source (FIRST - provides context)
            self._render_location_card(page, person)

            # Card B: Person Identity
            self._render_identity_card(person)

            # Card C: Dwelling Info
            self._render_dwelling_card(person)

            # Card D: Employment (if applicable)
            self._render_employment_card(person)

            # Card E: Sample Line Data (expandable, shows if person has sample field data)
            # Note: _render_sample_line_card checks for actual sample field data presence
            self._render_sample_line_card(person)

            # Card F: RootsMagic Links (expandable)
            self._render_links_card(person)

    def _render_location_card(self, page: CensusPage | None, person: CensusPerson) -> None:
        """Render the Census Location & Source card (always first)."""
        with ui.card().classes("w-full p-3 bg-blue-50 border-blue-200"):
            # Header with year
            with ui.row().classes("w-full items-center gap-2 mb-2"):
                ui.icon("location_on", size="sm").classes("text-blue-600")
                year = page.census_year if page else "Unknown"
                state = page.state if page else ""
                county = page.county if page else ""
                ui.label(f"{year} Census - {county} County, {state}").classes("font-bold text-blue-800")

            # Location details grid
            if page:
                with ui.element("div").classes("grid grid-cols-2 gap-x-4 gap-y-1 text-sm"):
                    if page.township_city:
                        ui.label("Township/City:").classes("text-gray-600")
                        ui.label(page.township_city)

                    if page.enumeration_district:
                        ui.label("E.D.:").classes("text-gray-600")
                        ui.label(page.enumeration_district)

                    sheet = page.sheet_number or page.page_number
                    if sheet:
                        label = "Sheet:" if page.sheet_number else "Page:"
                        ui.label(label).classes("text-gray-600")
                        display = sheet
                        if page.sheet_letter:
                            display += page.sheet_letter
                        ui.label(display)

                    if page.stamp_number:
                        ui.label("Stamp:").classes("text-gray-600")
                        ui.label(page.stamp_number)

                    if page.enumeration_date:
                        ui.label("Date:").classes("text-gray-600")
                        ui.label(page.enumeration_date)

                    if page.enumerator_name:
                        ui.label("Enumerator:").classes("text-gray-600")
                        ui.label(page.enumerator_name)

            # Action buttons
            with ui.row().classes("w-full gap-2 mt-3"):
                if person.familysearch_ark:
                    ui.button(
                        "FamilySearch",
                        icon="open_in_new",
                        on_click=lambda: ui.navigate.to(person.familysearch_ark, new_tab=True),
                    ).props("color=blue size=sm outline dense")

                if page:
                    ui.button(
                        "View Census Form",
                        icon="description",
                        on_click=lambda: self._view_census_form(page.page_id),
                    ).props("color=green size=sm outline dense")

                    ui.button(
                        "Match to RootsMagic",
                        icon="link",
                        on_click=lambda: self._show_match_dialog(page.page_id),
                    ).props("color=purple size=sm outline dense")

                # Edit/Save buttons
                if self.is_editing:
                    ui.button("Save", icon="save", on_click=self._save_person).props(
                        "color=green size=sm dense"
                    )
                    ui.button("Cancel", icon="close", on_click=self._cancel_edit).props(
                        "color=red size=sm outline dense"
                    )
                else:
                    ui.button("Edit", icon="edit", on_click=self._start_edit).props(
                        "color=primary size=sm outline dense"
                    )

    def _render_identity_card(self, person: CensusPerson) -> None:
        """Render the Person Identity card."""
        with ui.card().classes("w-full p-3"):
            with ui.row().classes("w-full items-center gap-2 mb-2"):
                ui.icon("person", size="sm").classes("text-gray-600")
                ui.label("Person Identity").classes("font-bold")
                if person.line_number:
                    ui.badge(f"Line {person.line_number}", color="gray").classes("text-xs")

            with ui.element("div").classes("grid grid-cols-2 gap-x-4 gap-y-1"):
                for field_name, label in IDENTITY_FIELDS:
                    value = getattr(person, field_name, "") or ""
                    self._render_field_row(field_name, label, str(value))

                # Parents' birthplaces
                if person.birthplace_father:
                    self._render_field_row("birthplace_father", "Father's Birth", person.birthplace_father)
                if person.birthplace_mother:
                    self._render_field_row("birthplace_mother", "Mother's Birth", person.birthplace_mother)

    def _render_dwelling_card(self, person: CensusPerson) -> None:
        """Render dwelling/household information."""
        # Check if we have any dwelling data (unless in edit mode)
        has_data = any(
            self.extended_fields.get(fn) or getattr(person, fn, None)
            for fn, _ in DWELLING_FIELDS
        )
        if not has_data and not self.is_editing:
            return

        with ui.card().classes("w-full p-3"):
            with ui.row().classes("w-full items-center gap-2 mb-2"):
                ui.icon("home", size="sm").classes("text-gray-600")
                ui.label("Dwelling Information").classes("font-bold")

            with ui.element("div").classes("grid grid-cols-2 gap-x-4 gap-y-1"):
                for field_name, label in DWELLING_FIELDS:
                    value = self.extended_fields.get(field_name, "") or getattr(person, field_name, "") or ""
                    # In edit mode, show all fields; in view mode, only show fields with values
                    if value or self.is_editing:
                        self._render_field_row(field_name, label, str(value))

    def _render_employment_card(self, person: CensusPerson) -> None:
        """Render employment information (Cols 15-20)."""
        # Check if we have any employment data (unless in edit mode)
        has_data = any(
            self.extended_fields.get(fn) or getattr(person, fn, None)
            for fn, _ in EMPLOYMENT_FIELDS
        )
        if not has_data and not self.is_editing:
            return

        with ui.card().classes("w-full p-3"):
            with ui.row().classes("w-full items-center gap-2 mb-2"):
                ui.icon("work", size="sm").classes("text-gray-600")
                ui.label("Employment (Cols 15-20)").classes("font-bold")

            with ui.element("div").classes("grid grid-cols-2 gap-x-4 gap-y-1"):
                for field_name, label in EMPLOYMENT_FIELDS:
                    value = self.extended_fields.get(field_name, "") or getattr(person, field_name, "") or ""
                    # In edit mode, show all fields; in view mode, only show fields with values
                    if value or self.is_editing:
                        self._render_field_row(field_name, label, str(value))

    def _render_sample_line_card(self, person: CensusPerson) -> None:
        """Render sample line data (Cols 21-33) - expandable."""
        # Check if we have sample line data (unless in edit mode)
        has_data = any(self.extended_fields.get(fn) for fn, _ in SAMPLE_LINE_FIELDS)
        if not has_data and not self.is_editing:
            return

        with ui.expansion(
            "Sample Line Data (Cols 21-33)",
            icon="analytics",
            value=self.sample_expanded,
            on_value_change=lambda e: setattr(self, 'sample_expanded', e.value),
        ).classes("w-full bg-green-50"):
            with ui.element("div").classes("grid grid-cols-2 gap-x-4 gap-y-1 p-2"):
                for field_name, label in SAMPLE_LINE_FIELDS:
                    value = self.extended_fields.get(field_name, "")
                    # In edit mode, show all fields; in view mode, only show fields with values
                    if value or self.is_editing:
                        self._render_field_row(field_name, label, str(value))

    def _render_links_card(self, person: CensusPerson) -> None:
        """Render RootsMagic links - expandable."""
        with self.repository._connect() as conn:
            link_rows = conn.execute(
                "SELECT * FROM rmtree_link WHERE census_person_id = ?",
                (person.person_id,),
            ).fetchall()

        if not link_rows:
            return

        with ui.expansion(
            f"RootsMagic Links ({len(link_rows)})",
            icon="link",
            value=self.links_expanded,
            on_value_change=lambda e: setattr(self, 'links_expanded', e.value),
        ).classes("w-full"):
            for row in link_rows:
                with ui.row().classes("w-full items-center gap-2 p-1 text-sm"):
                    ui.icon("link", size="xs").classes("text-purple-500")
                    if row["rmtree_citation_id"]:
                        ui.label(f"Citation #{row['rmtree_citation_id']}")
                    if row["rmtree_person_id"]:
                        ui.label(f"Person #{row['rmtree_person_id']}")
                    ui.badge(f"{row['match_confidence']:.0%}", color="purple").classes("text-xs")

    def _render_field_row(self, field_name: str, label: str, value: str) -> None:
        """Render a single field row (view or edit mode)."""
        # Quality indicator
        has_quality = field_name in self.quality_data
        has_history = field_name in self.field_history and len(self.field_history[field_name]) > 0
        quality_color = ""
        if has_quality:
            q = self.quality_data[field_name]
            quality_color = self._get_confidence_color(q.confidence_score)

        # Label with optional history indicator
        with ui.row().classes("items-center gap-1"):
            ui.label(f"{label}:").classes(f"text-gray-600 text-sm {quality_color}")
            if has_history:
                ui.icon("history", size="xs").classes(
                    "text-blue-500 cursor-pointer hover:text-blue-700"
                ).tooltip("View edit history").on(
                    "click", lambda fn=field_name: self._show_field_history_dialog(fn)
                )

        if self.is_editing:
            inp = ui.input(value=value).classes("text-sm").props("dense")
            self.edit_inputs[field_name] = inp
        else:
            display_value = value or "—"
            label_classes = "text-sm"
            if has_quality:
                label_classes += f" {quality_color}"
            ui.label(display_value).classes(label_classes)

    def _view_census_form(self, page_id: int) -> None:
        """Open census form in a new browser tab."""
        try:
            from rmcitecraft.services.census_form_renderer import CensusFormRenderer
            import tempfile
            import subprocess

            renderer = CensusFormRenderer()
            html = renderer.render_page(page_id, embed_css=True)

            # Save to a temp file with .html extension
            temp_dir = Path(tempfile.gettempdir())
            temp_file = temp_dir / f"census_form_{page_id}.html"
            temp_file.write_text(html)

            # Open with system default browser (macOS)
            subprocess.run(["open", str(temp_file)], check=True)
            ui.notify("Census form opened in browser", type="positive")

        except Exception as e:
            logger.error(f"Failed to render census form: {e}")
            ui.notify(f"Failed to render form: {e}", type="negative")

    # =========================================================================
    # Quality Panel
    # =========================================================================

    def _refresh_quality_panel(self) -> None:
        """Refresh the quality assessment panel."""
        self.quality_panel.clear()

        with self.quality_panel:
            if not self.selected_person:
                ui.label("Select a person").classes("text-gray-400 italic text-sm")
                return

            person = self.selected_person

            # Add quality button
            ui.button(
                "Add Assessment",
                icon="add",
                on_click=self._show_add_quality_dialog,
            ).props("color=green size=sm").classes("mb-2")

            # Existing quality assessments
            if self.quality_data:
                ui.label("Assessments").classes("font-bold text-sm")
                for _, quality in sorted(self.quality_data.items()):
                    self._render_quality_item(quality)
            else:
                ui.label("No quality assessments").classes("text-gray-400 italic text-sm")

            # Quick quality checklist
            ui.separator().classes("my-2")
            ui.label("Quick Check").classes("font-bold text-sm")
            ui.label("Click field to assess").classes("text-xs text-gray-500 mb-1")

            with ui.column().classes("gap-0"):
                for field_name, label in IDENTITY_FIELDS[:6]:  # Core fields only
                    value = getattr(person, field_name, "") or ""
                    if value:
                        has_quality = field_name in self.quality_data
                        with ui.row().classes(
                            "items-center gap-1 cursor-pointer hover:bg-gray-100 p-1 rounded text-xs"
                        ).on("click", lambda fn=field_name: self._show_add_quality_dialog(fn)):
                            if has_quality:
                                q = self.quality_data[field_name]
                                color = self._get_confidence_color(q.confidence_score)
                                ui.icon("check_circle", size="xs").classes(color)
                            else:
                                ui.icon("radio_button_unchecked", size="xs").classes("text-gray-300")
                            ui.label(f"{label}: {value}").classes("truncate")

    def _render_quality_item(self, quality: FieldQuality) -> None:
        """Render a quality assessment item."""
        color = self._get_confidence_color(quality.confidence_score)

        with ui.card().classes("w-full p-2 mb-1"):
            with ui.row().classes("items-center gap-2"):
                ui.label(quality.field_name.replace("_", " ").title()).classes("text-xs font-medium flex-1")
                ui.badge(f"{quality.confidence_score:.0%}", color=color.replace("text-", "")).classes("text-xs")
                ui.button(icon="delete", on_click=lambda q=quality: self._delete_quality(q)).props("flat dense size=xs color=red")

            if quality.source_legibility or quality.transcription_note:
                with ui.column().classes("text-xs text-gray-500"):
                    if quality.source_legibility:
                        ui.label(f"Legibility: {quality.source_legibility}")
                    if quality.transcription_note:
                        ui.label(f"Note: {quality.transcription_note}")

    # =========================================================================
    # Metadata Panel
    # =========================================================================

    def _refresh_metadata_panel(self) -> None:
        """Refresh the metadata panel."""
        self.metadata_panel.clear()

        with self.metadata_panel:
            if not self.selected_person:
                ui.label("Select a person").classes("text-gray-400 italic text-sm")
                return

            person = self.selected_person
            page = self.selected_page

            ui.label("Database IDs").classes("font-bold text-sm")
            with ui.column().classes("text-xs text-gray-600 gap-1"):
                ui.label(f"Person ID: {person.person_id}")
                ui.label(f"Page ID: {person.page_id}")
                if person.familysearch_person_id:
                    ui.label(f"FS Person ID: {person.familysearch_person_id}")

            if person.familysearch_ark:
                ui.separator().classes("my-2")
                ui.label("FamilySearch ARK").classes("font-bold text-sm")
                ui.label(person.familysearch_ark).classes("text-xs text-gray-600 break-all")

            if page:
                ui.separator().classes("my-2")
                ui.label("Page Metadata").classes("font-bold text-sm")
                with ui.column().classes("text-xs text-gray-600 gap-1"):
                    if page.familysearch_film:
                        ui.label(f"Film: {page.familysearch_film}")
                    if page.familysearch_image_url:
                        ui.label("Image URL:").classes("font-medium")
                        ui.label(page.familysearch_image_url).classes("break-all text-blue-600")

    # =========================================================================
    # Edit Mode
    # =========================================================================

    def _start_edit(self) -> None:
        """Enter edit mode."""
        self.is_editing = True
        self._refresh_detail_view()

    def _cancel_edit(self) -> None:
        """Cancel edit mode."""
        self.is_editing = False
        self._refresh_detail_view()

    def _save_person(self) -> None:
        """Save edited person data with version control."""
        if not self.selected_person:
            logger.warning("Save called but no person selected")
            return

        person_id = self.selected_person.person_id
        logger.info(f"Saving changes for person {person_id} ({self.selected_person.full_name})")
        logger.debug(f"Edit inputs: {list(self.edit_inputs.keys())}")

        try:
            updates = {}
            extended_updates = {}
            extended_inserts = {}

            for field_name, inp in self.edit_inputs.items():
                new_value = inp.value if inp.value else ""

                if hasattr(self.selected_person, field_name):
                    old_value = getattr(self.selected_person, field_name)
                    old_value = str(old_value) if old_value is not None else ""
                    if new_value != old_value:
                        logger.debug(f"Core field change: {field_name}: '{old_value}' -> '{new_value}'")
                        updates[field_name] = (old_value, new_value)
                elif field_name in self.extended_fields:
                    # Update existing extended field
                    old_value = str(self.extended_fields.get(field_name, "") or "")
                    if new_value != old_value:
                        logger.debug(f"Extended field update: {field_name}: '{old_value}' -> '{new_value}'")
                        extended_updates[field_name] = (old_value, new_value)
                else:
                    # New extended field (wasn't in database before)
                    if new_value:  # Only insert if there's a value
                        logger.debug(f"New extended field: {field_name} = '{new_value}'")
                        extended_inserts[field_name] = new_value

            # Apply core field updates
            if updates:
                logger.info(f"Updating {len(updates)} core fields: {list(updates.keys())}")
                with self.repository._connect() as conn:
                    for field_name, (old_value, new_value) in updates.items():
                        conn.execute(
                            f"UPDATE census_person SET {field_name} = ? WHERE person_id = ?",
                            (new_value, person_id),
                        )
                    conn.commit()  # Explicit commit
                # Record history separately
                for field_name, (old_value, new_value) in updates.items():
                    self.repository.record_field_change(
                        person_id=person_id,
                        field_name=field_name,
                        old_value=old_value,
                        new_value=new_value,
                        source="manual_edit",
                    )

            # Apply extended field updates
            if extended_updates:
                logger.info(f"Updating {len(extended_updates)} extended fields: {list(extended_updates.keys())}")
                with self.repository._connect() as conn:
                    for field_name, (old_value, new_value) in extended_updates.items():
                        conn.execute(
                            """UPDATE census_person_field SET field_value = ?
                               WHERE person_id = ? AND field_name = ?""",
                            (new_value, person_id, field_name),
                        )
                    conn.commit()  # Explicit commit
                # Record history separately
                for field_name, (old_value, new_value) in extended_updates.items():
                    self.repository.record_field_change(
                        person_id=person_id,
                        field_name=field_name,
                        old_value=old_value,
                        new_value=new_value,
                        source="manual_edit",
                    )

            # Insert new extended fields
            if extended_inserts:
                logger.info(f"Inserting {len(extended_inserts)} new extended fields: {list(extended_inserts.keys())}")
                with self.repository._connect() as conn:
                    for field_name, value in extended_inserts.items():
                        conn.execute(
                            """INSERT INTO census_person_field (person_id, field_name, field_value)
                               VALUES (?, ?, ?)""",
                            (person_id, field_name, value),
                        )
                    conn.commit()  # Explicit commit
                # Record history separately
                for field_name, value in extended_inserts.items():
                    self.repository.insert_field_history(
                        person_id=person_id,
                        field_name=field_name,
                        field_value=value,
                        field_source="manual_edit",
                        is_original=False,
                    )

            changes_count = len(updates) + len(extended_updates) + len(extended_inserts)
            if changes_count > 0:
                logger.info(f"Successfully saved {changes_count} field changes for person {person_id}")
                ui.notify(f"Saved {changes_count} changes", type="positive")
            else:
                logger.info("No changes detected")
                ui.notify("No changes to save", type="info")

            # Reload person data and refresh view
            self.is_editing = False
            ark = self.selected_person.familysearch_ark
            if ark:
                person = self.repository.get_person_by_ark(ark)
                if person:
                    self._select_person(person)
                    return
            # Fallback: just refresh the view
            self._refresh_detail_view()

        except Exception as e:
            logger.error(f"Failed to save: {e}", exc_info=True)
            ui.notify(f"Save failed: {e}", type="negative")

    # =========================================================================
    # Field History Dialog
    # =========================================================================

    def _show_field_history_dialog(self, field_name: str) -> None:
        """Show dialog with field edit history."""
        history = self.field_history.get(field_name, [])
        if not history:
            ui.notify("No history available", type="info")
            return

        with ui.dialog() as dialog, ui.card().classes("w-[500px]"):
            ui.label(f"Edit History: {field_name.replace('_', ' ').title()}").classes(
                "text-lg font-bold mb-2"
            )

            with ui.column().classes("w-full gap-2"):
                for entry in history:
                    # Format timestamp as "02 Dec 2025, 9:36am" in local time
                    dt = entry.created_at
                    hour = dt.hour % 12 or 12  # Convert 0 to 12 for 12am
                    am_pm = "am" if dt.hour < 12 else "pm"
                    timestamp = f"{dt.day:02d} {dt.strftime('%b')} {dt.year}, {hour}:{dt.minute:02d}{am_pm}"
                    source_label = {
                        "familysearch": "FamilySearch Import",
                        "manual_edit": "Manual Edit",
                        "ai_transcription": "AI Transcription",
                    }.get(entry.field_source, entry.field_source)

                    with ui.card().classes(
                        f"w-full p-2 {'bg-green-50 border-green-200' if entry.is_original else 'bg-gray-50'}"
                    ):
                        with ui.row().classes("w-full items-center gap-2"):
                            if entry.is_original:
                                ui.badge("Original", color="green").classes("text-xs")
                            ui.label(source_label).classes("text-xs text-gray-500")
                            ui.label(timestamp).classes("text-xs text-gray-400 ml-auto")

                        ui.label(entry.field_value or "(empty)").classes(
                            "text-sm font-medium mt-1"
                        )

                        if entry.created_by:
                            ui.label(f"By: {entry.created_by}").classes(
                                "text-xs text-gray-400"
                            )

            with ui.row().classes("w-full justify-end mt-4"):
                ui.button("Close", on_click=dialog.close).props("flat")

        dialog.open()

    # =========================================================================
    # Quality Dialog
    # =========================================================================

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

        all_fields = [fn for fn, _ in IDENTITY_FIELDS]
        all_fields.extend(self.extended_fields.keys())

        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label("Add Quality Assessment").classes("text-lg font-bold mb-2")

            field_select = ui.select(options=all_fields, value=field_name, label="Field").classes("w-full")
            confidence_slider = ui.slider(min=0, max=100, value=80).props("label-always")
            ui.label("Confidence Score").classes("text-xs text-gray-500")
            legibility_select = ui.select(options=LEGIBILITY_OPTIONS, value="clear", label="Legibility").classes("w-full")
            note_input = ui.textarea(label="Note", placeholder="Any notes...").classes("w-full")
            verified_check = ui.checkbox("Human Verified")
            verified_by = ui.input(label="Verified By").classes("w-full")

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button(
                    "Save",
                    on_click=lambda: self._save_quality(
                        dialog, field_select.value, confidence_slider.value / 100,
                        legibility_select.value, note_input.value,
                        verified_check.value, verified_by.value,
                    ),
                ).props("color=green")

        dialog.open()

    def _save_quality(self, dialog, field_name, confidence, legibility, note, verified, verified_by) -> None:
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

            qualities = self.repository.get_field_quality(self.selected_person.person_id)
            self.quality_data = {q.field_name: q for q in qualities}
            self._refresh_quality_panel()
            self._refresh_detail_view()

        except Exception as e:
            logger.error(f"Failed to save quality: {e}")
            ui.notify(f"Save failed: {e}", type="negative")

    def _delete_quality(self, quality: FieldQuality) -> None:
        """Delete quality assessment."""
        with ui.dialog() as dialog, ui.card():
            ui.label(f"Delete assessment for {quality.field_name}?")
            with ui.row().classes("justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button(
                    "Delete",
                    on_click=lambda: self._do_delete_quality(quality, dialog),
                ).props("color=red")
        dialog.open()

    def _do_delete_quality(self, quality: FieldQuality, dialog) -> None:
        """Actually delete quality assessment."""
        with self.repository._connect() as conn:
            conn.execute("DELETE FROM field_quality WHERE quality_id = ?", (quality.quality_id,))
        ui.notify("Deleted", type="info")
        dialog.close()

        qualities = self.repository.get_field_quality(self.selected_person.person_id)
        self.quality_data = {q.field_name: q for q in qualities}
        self._refresh_quality_panel()
        self._refresh_detail_view()

    # =========================================================================
    # Import Dialog
    # =========================================================================

    def _show_import_dialog(self) -> None:
        """Show dialog to import from FamilySearch URL."""
        with ui.dialog() as self._import_dialog, ui.card().classes("w-[500px]"):
            ui.label("Import from FamilySearch").classes("text-lg font-bold mb-2")

            self._import_url_input = ui.input(
                label="FamilySearch ARK URL",
                placeholder="https://www.familysearch.org/ark:/61903/1:1:...",
            ).classes("w-full")

            self._import_year_select = ui.select(
                options={1950: "1950", 1940: "1940", 1930: "1930", 1920: "1920",
                         1910: "1910", 1900: "1900", 1880: "1880"},
                value=1950,
                label="Census Year",
            ).classes("w-full")

            ui.label("Optional: Link to RootsMagic").classes("text-sm font-medium mt-2")
            self._import_citation_input = ui.input(label="CitationID", placeholder="e.g., 10370").classes("w-full")
            self._import_person_input = ui.input(label="PersonID (RIN)", placeholder="e.g., 2776").classes("w-full")

            with ui.row().classes("w-full items-center gap-2 mt-2"):
                self._import_spinner = ui.spinner(size="sm").classes("hidden")
                self._import_status_label = ui.label("").classes("text-sm text-gray-500")

            self._import_result_card = ui.card().classes("w-full mt-2 p-3 bg-green-50 hidden")
            with self._import_result_card:
                self._import_result_icon = ui.icon("check_circle", size="md").classes("text-green-600")
                self._import_result_text = ui.label("").classes("text-sm font-medium")
                self._import_result_details = ui.label("").classes("text-xs text-gray-600")

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                self._import_cancel_btn = ui.button("Cancel", on_click=self._import_dialog.close).props("flat")
                self._import_btn = ui.button("Import", on_click=self._do_import).props("color=green")
                self._import_close_btn = ui.button("Close", on_click=self._close_import_and_refresh).props("color=primary").classes("hidden")

        self._import_dialog.open()

    def _close_import_and_refresh(self) -> None:
        """Close import dialog and refresh."""
        self._import_dialog.close()
        self._search_persons()

    async def _do_import(self) -> None:
        """Perform import from FamilySearch."""
        url = self._import_url_input.value
        year = self._import_year_select.value
        citation_id = self._import_citation_input.value
        person_id = self._import_person_input.value

        if not url or "familysearch.org" not in url:
            ui.notify("Please enter a valid FamilySearch URL", type="warning")
            return

        from rmcitecraft.services.familysearch_census_extractor import extract_census_from_citation

        try:
            self._import_btn.disable()
            self._import_cancel_btn.disable()
            self._import_spinner.classes(remove="hidden")
            self._import_result_card.classes(add="hidden")
            self._import_status_label.set_text("Extracting data...")

            await ui.context.client.connected()

            result = await extract_census_from_citation(
                url, year,
                rmtree_citation_id=int(citation_id) if citation_id else None,
                rmtree_person_id=int(person_id) if person_id else None,
            )

            self._import_spinner.classes(add="hidden")

            if result.success:
                name = result.extracted_data.get("primary_name", "Unknown")
                household_count = len(result.related_persons) if result.related_persons else 0
                total_persons = 1 + household_count  # Primary person + household members

                # Log import summary
                self._log_import_summary(result, year, citation_id, person_id)

                self._import_status_label.set_text("")
                self._import_result_card.classes(remove="hidden", add="bg-green-50")
                self._import_result_icon.classes(remove="text-red-600", add="text-green-600")
                self._import_result_icon.props("name=check_circle")
                self._import_result_text.set_text(f"Extracted: {name}")
                self._import_result_details.set_text(f"{total_persons} persons imported")

                ui.notify(f"Imported {total_persons} persons from census page", type="positive")

                # Auto-close dialog and refresh
                self._close_import_and_refresh()
            else:
                self._import_result_card.classes(remove="hidden bg-green-50", add="bg-red-50")
                self._import_result_icon.classes(remove="text-green-600", add="text-red-600")
                self._import_result_icon.props("name=error")
                self._import_result_text.set_text("Failed")
                self._import_result_details.set_text(result.error_message or "Unknown error")
                self._import_btn.enable()
                self._import_cancel_btn.enable()
                ui.notify(f"Failed: {result.error_message}", type="negative")

        except Exception as e:
            logger.error(f"Import failed: {e}")
            self._import_spinner.classes(add="hidden")
            self._import_result_card.classes(remove="hidden bg-green-50", add="bg-red-50")
            self._import_result_text.set_text("Error")
            self._import_result_details.set_text(str(e))
            self._import_btn.enable()
            self._import_cancel_btn.enable()
            ui.notify(f"Import failed: {e}", type="negative")

    def _log_import_summary(
        self,
        result: Any,
        year: int,
        citation_id: str | None,
        person_id: str | None,
    ) -> None:
        """Log detailed import summary with target persons and RootsMagic links."""
        # Get all imported persons from the result
        primary_name = result.extracted_data.get("primary_name", "Unknown")
        primary_line = result.extracted_data.get("line_number", "?")
        household_count = len(result.related_persons) if result.related_persons else 0
        total_persons = 1 + household_count

        # Build summary
        log_lines = [
            f"Census Import Complete: {year} Census",
            f"  Total persons imported: {total_persons}",
            f"  Primary person: {primary_name} (Line {primary_line})",
        ]

        # Add household members
        if result.related_persons:
            log_lines.append(f"  Household members ({household_count}):")
            for member in result.related_persons:
                member_name = member.get("full_name", member.get("name", "Unknown"))
                member_line = member.get("line_number", "?")
                log_lines.append(f"    - {member_name} (Line {member_line})")

        # Query for RootsMagic links (target persons)
        target_persons = []
        try:
            with self.repository._connect() as conn:
                # Find persons linked to RootsMagic from this import
                rows = conn.execute("""
                    SELECT cp.full_name, cp.line_number, cp.is_target_person,
                           rl.rmtree_person_id, rl.rmtree_citation_id
                    FROM census_person cp
                    LEFT JOIN rmtree_link rl ON cp.person_id = rl.census_person_id
                    WHERE cp.is_target_person = 1
                    ORDER BY cp.created_at DESC
                    LIMIT 10
                """).fetchall()

                for row in rows:
                    if row["rmtree_person_id"] or row["rmtree_citation_id"]:
                        target_persons.append({
                            "name": row["full_name"],
                            "line": row["line_number"],
                            "rin": row["rmtree_person_id"],
                            "citation_id": row["rmtree_citation_id"],
                        })
        except Exception as e:
            logger.warning(f"Could not query RootsMagic links: {e}")

        # Add target persons with RootsMagic links
        if target_persons:
            log_lines.append("  Target persons linked to RootsMagic:")
            for tp in target_persons:
                rin_str = f"RIN {tp['rin']}" if tp['rin'] else ""
                cit_str = f"CitationID {tp['citation_id']}" if tp['citation_id'] else ""
                link_info = ", ".join(filter(None, [rin_str, cit_str]))
                log_lines.append(f"    ★ {tp['name']} (Line {tp['line']}) - {link_info}")
        elif citation_id or person_id:
            # If user provided RootsMagic IDs, note them
            link_parts = []
            if citation_id:
                link_parts.append(f"CitationID {citation_id}")
            if person_id:
                link_parts.append(f"RIN {person_id}")
            log_lines.append(f"  RootsMagic link requested: {', '.join(link_parts)}")

        # Log the summary
        logger.info("\n".join(log_lines))

    # =========================================================================
    # RootsMagic Matching Dialog
    # =========================================================================

    def _show_match_dialog(self, page_id: int) -> None:
        """Show dialog to match census persons to RootsMagic."""
        with ui.dialog() as dialog, ui.card().classes("w-[800px] max-h-[90vh]"):
            ui.label("Match Census to RootsMagic").classes("text-xl font-bold mb-2")

            # Citation ID input
            with ui.row().classes("w-full items-end gap-4 mb-4"):
                citation_input = ui.input(
                    label="RootsMagic Citation ID",
                    placeholder="e.g., 10681",
                ).classes("w-48")

                ark_input = ui.input(
                    label="FamilySearch ARK URL (optional)",
                    placeholder="Leave blank to use page data",
                ).classes("flex-1")

                find_btn = ui.button("Find Matches", icon="search").props("color=primary")

            # Results container
            results_container = ui.column().classes("w-full gap-2")

            # Status area
            with ui.row().classes("w-full items-center gap-2"):
                status_spinner = ui.spinner(size="sm").classes("hidden")
                status_label = ui.label("").classes("text-sm text-gray-500")

            async def do_match():
                citation_id = citation_input.value
                ark_url = ark_input.value

                if not citation_id:
                    ui.notify("Please enter a Citation ID", type="warning")
                    return

                try:
                    citation_id = int(citation_id)
                except ValueError:
                    ui.notify("Citation ID must be a number", type="warning")
                    return

                # Show spinner
                status_spinner.classes(remove="hidden")
                status_label.set_text("Searching for matches...")
                results_container.clear()

                try:
                    matcher = create_matcher()

                    # Get the ARK from the current page if not provided
                    if not ark_url:
                        # Get persons on this page to find an ARK
                        census_persons = self.repository.get_persons_on_page(page_id)
                        if census_persons:
                            ark_url = census_persons[0].familysearch_ark

                    if not ark_url:
                        status_spinner.classes(add="hidden")
                        status_label.set_text("No FamilySearch ARK available")
                        return

                    # Run matching
                    result = matcher.match_citation_to_census(
                        citation_id=citation_id,
                        ark_url=ark_url,
                        threshold=0.5,
                        create_links=False,  # Don't auto-create links
                    )

                    status_spinner.classes(add="hidden")

                    if not result:
                        status_label.set_text("No matching data found")
                        return

                    # Display results
                    self._render_match_results(
                        results_container, result, matcher, dialog
                    )

                except Exception as e:
                    logger.error(f"Matching failed: {e}", exc_info=True)
                    status_spinner.classes(add="hidden")
                    status_label.set_text(f"Error: {e}")
                    ui.notify(f"Matching failed: {e}", type="negative")

            find_btn.on("click", do_match)

            # Close button
            with ui.row().classes("w-full justify-end mt-4"):
                ui.button("Close", on_click=dialog.close).props("flat")

        dialog.open()

    def _render_match_results(
        self,
        container: ui.column,
        result: MatchResult,
        matcher: CensusRMTreeMatcher,
        dialog,
    ) -> None:
        """Render matching results in the dialog."""
        with container:
            # Summary header
            with ui.card().classes("w-full p-3 bg-blue-50"):
                with ui.row().classes("w-full items-center gap-4"):
                    ui.icon("analytics", size="md").classes("text-blue-600")
                    ui.label(f"{result.census_year} Census Matching").classes("font-bold")
                    ui.badge(f"{result.success_rate:.0%} Match Rate", color="blue")

                with ui.row().classes("w-full gap-4 text-sm mt-2"):
                    ui.label(f"Matched: {len(result.matches)}")
                    ui.label(f"Unmatched RM: {len(result.unmatched_rm)}")
                    ui.label(f"Unmatched Census: {len(result.unmatched_census)}")

            # Matches section
            if result.matches:
                ui.label("Matches").classes("font-bold text-lg mt-4 mb-2")
                match_checkboxes: dict[int, ui.checkbox] = {}

                for match in result.matches:
                    with ui.card().classes("w-full p-3 border-l-4 border-green-500"):
                        with ui.row().classes("w-full items-start gap-4"):
                            # Checkbox to select for linking
                            cb = ui.checkbox("", value=True).classes("mt-1")
                            match_checkboxes[match.rm_person.person_id] = cb

                            # RM Person
                            with ui.column().classes("flex-1"):
                                ui.label("RootsMagic").classes("text-xs text-gray-500")
                                ui.label(match.rm_person.full_name).classes("font-medium")
                                with ui.row().classes("gap-2 text-xs text-gray-600"):
                                    ui.label(f"RIN {match.rm_person.person_id}")
                                    ui.label(f"{match.rm_person.relationship}")
                                    if match.rm_person.birth_year:
                                        ui.label(f"b.{match.rm_person.birth_year}")

                            # Arrow
                            ui.icon("arrow_forward", size="md").classes("text-gray-400 self-center")

                            # Census Person
                            with ui.column().classes("flex-1"):
                                ui.label("Census").classes("text-xs text-gray-500")
                                ui.label(match.census_person.full_name).classes("font-medium")
                                with ui.row().classes("gap-2 text-xs text-gray-600"):
                                    ui.label(f"Age {match.census_person.age or '?'}")
                                    ui.label(match.census_person.relationship)
                                    ui.label(match.census_person.sex)

                            # Score badge
                            score_color = self._get_match_score_color(match.score)
                            with ui.column().classes("items-end"):
                                ui.badge(f"{match.score:.0%}", color=score_color).classes("text-lg")
                                ui.label("confidence").classes("text-xs text-gray-400")

                        # Score breakdown (expandable)
                        with ui.expansion("Score Details", icon="info").classes("w-full mt-2 text-xs"):
                            with ui.row().classes("w-full gap-4"):
                                for key, value in match.score_breakdown.items():
                                    pct = value / sum(match.score_breakdown.values()) * 100 if match.score_breakdown else 0
                                    ui.label(f"{key}: {value:.2f} ({pct:.0f}%)")

                # Create Links button
                async def create_selected_links():
                    selected = [
                        m for m in result.matches
                        if match_checkboxes.get(m.rm_person.person_id, ui.checkbox()).value
                    ]

                    if not selected:
                        ui.notify("No matches selected", type="warning")
                        return

                    created = 0
                    for match in selected:
                        try:
                            link = RMTreeLink(
                                census_person_id=match.census_person.person_id,
                                rmtree_person_id=match.rm_person.person_id,
                                rmtree_citation_id=result.citation_id,
                                rmtree_event_id=result.event_id,
                                rmtree_database=str(matcher.rmtree_path),
                                match_confidence=match.score,
                                match_method="manual_confirm",
                            )
                            self.repository.insert_rmtree_link(link)
                            created += 1
                        except Exception as e:
                            logger.warning(f"Failed to create link for {match.rm_person.full_name}: {e}")

                    ui.notify(f"Created {created} RootsMagic links", type="positive")
                    dialog.close()
                    self._search_persons()  # Refresh list

                with ui.row().classes("w-full justify-center mt-4"):
                    ui.button(
                        f"Create Links for Selected ({len(result.matches)})",
                        icon="link",
                        on_click=create_selected_links,
                    ).props("color=green")

            # Unmatched RM Persons (data quality alert)
            if result.unmatched_rm:
                ui.label("Unmatched RootsMagic Persons").classes("font-bold text-lg mt-4 mb-2")
                with ui.card().classes("w-full p-3 bg-yellow-50 border-l-4 border-yellow-500"):
                    ui.label(
                        "These persons are on the RootsMagic citation but NOT found on the census page. "
                        "This may indicate they were enumerated on a different page."
                    ).classes("text-sm text-yellow-800 mb-2")

                    for rm_person in result.unmatched_rm:
                        with ui.row().classes("items-center gap-2 text-sm"):
                            ui.icon("warning", size="sm").classes("text-yellow-600")
                            ui.label(rm_person.full_name).classes("font-medium")
                            ui.label(f"(RIN {rm_person.person_id}, {rm_person.relationship})").classes("text-gray-500")

            # Unmatched Census Persons
            if result.unmatched_census:
                ui.label("Unmatched Census Persons").classes("font-bold text-lg mt-4 mb-2")
                with ui.card().classes("w-full p-3 bg-gray-50"):
                    ui.label(
                        "These census persons were not matched to any RootsMagic person on the citation."
                    ).classes("text-sm text-gray-600 mb-2")

                    for census_person in result.unmatched_census:
                        with ui.row().classes("items-center gap-2 text-sm"):
                            ui.icon("person_outline", size="sm").classes("text-gray-400")
                            ui.label(census_person.full_name).classes("font-medium")
                            ui.label(f"(Age {census_person.age or '?'}, {census_person.relationship})").classes("text-gray-500")

    def _get_match_score_color(self, score: float) -> str:
        """Get color name for match score badge."""
        if score >= 0.9:
            return "green"
        elif score >= 0.7:
            return "yellow"
        elif score >= 0.5:
            return "orange"
        else:
            return "red"

    # =========================================================================
    # Clear Database
    # =========================================================================

    def _show_clear_database_dialog(self) -> None:
        """Show confirmation dialog to clear database."""
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label("Clear Census Database").classes("text-lg font-bold text-red-600")
            ui.label("This will permanently delete ALL extracted data.").classes("text-sm text-gray-600 my-2")

            stats = self.repository.get_extraction_stats()
            ui.label(f"Data: {stats.get('total_persons', 0)} persons, {stats.get('total_pages', 0)} pages").classes("text-sm font-medium")

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Delete All", icon="delete_forever", on_click=lambda: self._clear_database(dialog)).props("color=red")

        dialog.open()

    def _clear_database(self, dialog) -> None:
        """Clear all census.db data."""
        try:
            with self.repository._connect() as conn:
                conn.execute("DELETE FROM rmtree_link")
                conn.execute("DELETE FROM census_relationship")
                conn.execute("DELETE FROM field_quality")
                conn.execute("DELETE FROM census_person_field")
                conn.execute("DELETE FROM census_person")
                conn.execute("DELETE FROM census_page")
                conn.execute("DELETE FROM extraction_batch")
                conn.execute("DELETE FROM sqlite_sequence")

            ui.notify("Database cleared", type="positive")
            dialog.close()

            self.selected_person = None
            self.selected_page = None
            self.extended_fields = {}
            self.quality_data = {}

            self.render()

        except Exception as e:
            logger.error(f"Failed to clear database: {e}")
            ui.notify(f"Failed: {e}", type="negative")
