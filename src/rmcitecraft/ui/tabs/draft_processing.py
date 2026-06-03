"""WW II Draft Registration Batch Processing Tab for RMCitecraft.

Process CSV/XLSX files containing WW II draft registration records to create
citations, link to persons, and optionally download images.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger
from nicegui import ui

from rmcitecraft.config import get_config
from rmcitecraft.database.connection import connect_rmtree
from rmcitecraft.models.draft_record import DraftRecord, BatchResult, RecordResult
from rmcitecraft.models.draft_registration import (
    DraftAutomationBatchResult,
    DraftAutomationOptions,
)
from rmcitecraft.services.draft_batch_processor import (
    DraftBatchProcessor,
    ProcessingConfig,
)
from rmcitecraft.services.draft_file_reader import DraftFileReader
from rmcitecraft.services.draft_registration_service import DraftRegistrationService


@dataclass
class PersonInfo:
    """Person information from RootsMagic database."""
    given: str
    surname: str
    rin: int
    birth_date: Optional[str]
    birth_place: Optional[str]
    death_date: Optional[str]
    death_place: Optional[str]


class DraftProcessingTab:
    """WW II Draft Registration Batch Processing Tab component."""

    def __init__(self) -> None:
        """Initialize draft processing tab."""
        self.config = get_config()

        # State
        self.uploaded_file_path: Optional[Path] = None
        self.preview_records: list[DraftRecord] = []
        self.batch_result: Optional[BatchResult] = None
        self.processing: bool = False
        self.automation_processing: bool = False
        self.automation_result: Optional[DraftAutomationBatchResult] = None

        # Processing config
        self.skip_duplicates: bool = True
        self.validate_persons: bool = True
        self.stop_on_error: bool = False
        self.dry_run: bool = False

        # Surname letter filter (single uppercase letter, "" = no filter)
        self.surname_letter: str = ""
        self.surname_letter_input: Optional[ui.input] = None

        # Automation options
        self.workflow_mode: str = "standard"  # "standard", "ancestry_only", "metadata_only", "custom"
        self.discover_ancestry_urls: bool = True
        self.process_familysearch: bool = True
        self.process_ancestry: bool = False
        self.ancestry_metadata_only: bool = False
        self.automation_record_limit: int = 0
        self.automation_stop_event: Optional[asyncio.Event] = None
        self.automation_stop_requested: bool = False
        self._automation_progress_value: float = 0.0

        # UI component references
        self.upload_area: Optional[ui.upload] = None
        self.preview_container: Optional[ui.column] = None
        self.config_container: Optional[ui.column] = None
        self.results_container: Optional[ui.column] = None
        self.progress_container: Optional[ui.column] = None
        self.process_btn: Optional[ui.button] = None
        self.progress_bar: Optional[ui.linear_progress] = None
        self.progress_text: Optional[ui.label] = None
        self.progress_spinner: Optional[ui.spinner] = None
        self.automation_button: Optional[ui.button] = None
        self.automation_progress_bar: Optional[ui.linear_progress] = None
        self.automation_progress_text: Optional[ui.label] = None
        self.automation_spinner: Optional[ui.spinner] = None
        self.automation_results_container: Optional[ui.column] = None
        self.automation_stop_button: Optional[ui.button] = None

    def _format_rmdate_as_dd_mmm_yyyy(self, date_str: Optional[str]) -> Optional[str]:
        """Convert RootsMagic date string to dd-MMM-yyyy format.

        RootsMagic stores dates in EventTable.Date as packed format:
        - "D.+19220616..+00000000.." (exact: 16 Jun 1922)
        - "A.+19220000..+00000000.." (about 1922)
        - "B.+19220616..+00000000.." (before 16 Jun 1922)
        - "T.+19220616..+00000000.." (after 16 Jun 1922)

        Format: <modifier>.<+/-><YYYYMMDD>..<+/-><YYYYMMDD>..
        - modifier: D (exact), A (about), B (before), T (after), C (calculated), E (estimated)
        - YYYYMMDD: packed date (year=4 digits, month=2 digits, day=2 digits)

        This function formats them for display.
        """
        if not date_str or not date_str.strip():
            return None

        date_str = date_str.strip()

        # Check if this is RootsMagic packed format (starts with modifier and period)
        if len(date_str) > 2 and date_str[1] == '.':
            return self._parse_rm_packed_date(date_str)

        # Otherwise try standard text formats
        return self._parse_rm_display_date(date_str)

    def _parse_rm_packed_date(self, packed_date: str) -> Optional[str]:
        """Parse RootsMagic packed date format.

        Format: <modifier>.<+/-><YYYYMMDD>..<+/-><YYYYMMDD>..
        Example: "D.+19220616..+00000000.."

        Returns formatted date like "16 Jun 1922" or "Abt 1922"
        """
        try:
            parts = packed_date.split('.')
            if len(parts) < 2:
                return packed_date  # Can't parse, return as-is

            modifier = parts[0]  # D, A, B, T, C, E, etc.
            date_part = parts[1]  # "+19220616" or "-19220616"

            # Map modifier to qualifier
            qualifier_map = {
                'D': '',          # Exact (no qualifier)
                'A': 'Abt ',      # About
                'B': 'Bef ',      # Before
                'T': 'Aft ',      # After
                'C': 'Cal ',      # Calculated
                'E': 'Est ',      # Estimated
                'R': 'Bet ',      # Range/Between (uses both dates)
            }

            qualifier = qualifier_map.get(modifier, '')

            # Remove +/- sign
            if date_part.startswith(('+', '-')):
                date_part = date_part[1:]

            # Parse YYYYMMDD
            if len(date_part) >= 8:
                year_str = date_part[0:4]
                month_str = date_part[4:6]
                day_str = date_part[6:8]

                year = int(year_str)
                month = int(month_str)
                day = int(day_str)

                # Format based on precision
                if month == 0 and day == 0:
                    # Year only
                    return f"{qualifier}{year}"
                elif day == 0:
                    # Month and year
                    month_name = datetime(year, month, 1).strftime("%b")
                    return f"{qualifier}{month_name} {year}"
                else:
                    # Full date
                    date_obj = datetime(year, month, day)
                    return f"{qualifier}{date_obj.strftime('%d %b %Y')}"

            return packed_date  # Couldn't parse, return as-is

        except (ValueError, IndexError) as e:
            # Parsing failed, return as-is
            return packed_date

    def _parse_rm_display_date(self, date_str: str) -> Optional[str]:
        """Parse RootsMagic display date format (text dates).

        Handles formats like:
        - "25 Feb 1906" (full date)
        - "Feb 1906" (month year)
        - "1906" (year only)
        - "Abt 1906", "Bef 1906" (with qualifiers)
        """
        # Handle qualifiers (Abt, Bef, Aft, etc.)
        qualifier = ""
        if date_str.lower().startswith(("abt ", "about ", "bef ", "before ", "aft ", "after ", "bet ", "between ", "cal ", "est ")):
            parts = date_str.split(None, 1)
            if len(parts) == 2:
                qualifier = parts[0] + " "
                date_str = parts[1]

        # Try to parse common date formats
        date_formats = [
            "%d %b %Y",      # "25 Feb 1906"
            "%d %B %Y",      # "25 February 1906"
            "%b %Y",         # "Feb 1906"
            "%B %Y",         # "February 1906"
            "%Y",            # "1906"
            "%Y-%m-%d",      # "1906-02-25" (ISO)
            "%m/%d/%Y",      # "02/25/1906"
            "%d-%b-%Y",      # "25-Feb-1906"
        ]

        for fmt in date_formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                # Format based on precision
                if fmt == "%Y":
                    formatted = dt.strftime("%Y")
                elif fmt in ["%b %Y", "%B %Y"]:
                    formatted = dt.strftime("%b %Y")
                else:
                    formatted = dt.strftime("%d %b %Y")

                return qualifier + formatted
            except ValueError:
                continue

        # If no format matches, return as-is
        return date_str

    def _get_person_info_from_rmtree(self, rin: int) -> Optional[PersonInfo]:
        """Query RootsMagic database for person information."""
        try:
            conn = connect_rmtree(Path(self.config.rm_database_path))
            cursor = conn.cursor()

            query = """
                SELECT
                    n.Given,
                    n.Surname,
                    p.PersonID as RIN,
                    birth_e.Date as BirthDate,
                    birth_p.Name as BirthPlace,
                    death_e.Date as DeathDate,
                    death_p.Name as DeathPlace
                FROM PersonTable p
                JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
                LEFT JOIN EventTable birth_e ON birth_e.OwnerID = p.PersonID
                    AND birth_e.EventType = 1 AND birth_e.OwnerType = 0
                LEFT JOIN PlaceTable birth_p ON birth_p.PlaceID = birth_e.PlaceID
                LEFT JOIN EventTable death_e ON death_e.OwnerID = p.PersonID
                    AND death_e.EventType = 2 AND death_e.OwnerType = 0
                LEFT JOIN PlaceTable death_p ON death_p.PlaceID = death_e.PlaceID
                WHERE p.PersonID = ?
            """

            cursor.execute(query, (rin,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            return PersonInfo(
                given=row[0] or "",
                surname=row[1] or "",
                rin=row[2],
                birth_date=self._format_rmdate_as_dd_mmm_yyyy(row[3]),
                birth_place=row[4],
                death_date=self._format_rmdate_as_dd_mmm_yyyy(row[5]),
                death_place=row[6],
            )
        except Exception as e:
            logger.error(f"Error querying RootsMagic database for RIN {rin}: {e}", exc_info=True)
            return None

    def render(self) -> ui.column:
        """Render the draft processing tab."""
        with ui.column().classes("w-full p-4 gap-4") as container:
            # Header
            with ui.row().classes("w-full items-center gap-4"):
                ui.icon("military_tech", size="2rem").classes("text-blue-600")
                ui.label("WW II Draft Registration Processing").classes("text-2xl font-bold")

            with ui.card().classes("w-full p-3 bg-blue-50 border border-blue-200 mb-2"):
                ui.label("Use Section 4 to discover Ancestry URLs and scrape metadata → stores in ww2-draft.db").classes(
                    "text-sm font-semibold text-blue-900"
                )
                ui.label("Section 3 (RootsMagic database writer) is currently disabled").classes(
                    "text-xs text-blue-700"
                )

            # File Upload Section
            with ui.card().classes("w-full p-4"):
                ui.label("1. Upload File").classes("font-bold text-lg mb-2")
                ui.label(
                    "Upload a CSV or XLSX file containing WW II draft registration records"
                ).classes("text-sm text-gray-600 mb-2")

                with ui.row().classes("w-full items-center gap-4"):
                    self.upload_area = ui.upload(
                        label="Select CSV or XLSX file",
                        auto_upload=True,
                        on_upload=self._handle_file_upload,
                        on_rejected=lambda: ui.notify("Invalid file format. Use CSV or XLSX.", type="negative"),
                    ).props('accept=".csv,.xlsx"').classes("flex-1")

                    ui.button(
                        "Clear",
                        icon="clear",
                        on_click=self._clear_upload,
                    ).props("outline")

                # File info
                self.file_info_label = ui.label("No file uploaded").classes(
                    "text-sm text-gray-500 mt-2"
                )

            # Configuration Section - DISABLED (writes to RootsMagic database)
            with ui.card().classes("w-full p-4 bg-gray-50") as self.config_container:
                ui.label("3. RootsMagic Database Writer (DISABLED)").classes("font-bold text-lg mb-2 text-gray-600")

                # Warning banner
                with ui.card().classes("w-full p-3 bg-yellow-50 border-2 border-yellow-400 mb-3"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("warning", size="md").classes("text-yellow-700")
                        with ui.column().classes("gap-1"):
                            ui.label("This section writes Source and Citation records to RootsMagic database (.rmtree)").classes(
                                "font-semibold text-yellow-900"
                            )
                            ui.label("Currently disabled - citation format does not match requirements").classes(
                                "text-sm text-yellow-800"
                            )

                with ui.row().classes("w-full gap-4 flex-wrap opacity-50"):
                    ui.checkbox(
                        "Skip duplicates",
                        value=self.skip_duplicates,
                        on_change=lambda e: setattr(self, "skip_duplicates", e.value),
                    ).tooltip("Skip records that already have citations for the same source").props("disable")

                    ui.checkbox(
                        "Validate persons",
                        value=self.validate_persons,
                        on_change=lambda e: setattr(self, "validate_persons", e.value),
                    ).tooltip("Verify each RIN exists in the database before processing").props("disable")

                    ui.checkbox(
                        "Stop on first error",
                        value=self.stop_on_error,
                        on_change=lambda e: setattr(self, "stop_on_error", e.value),
                    ).tooltip("Stop processing if any record fails").props("disable")

                    ui.checkbox(
                        "Dry run (preview only)",
                        value=self.dry_run,
                        on_change=lambda e: setattr(self, "dry_run", e.value),
                    ).tooltip("Validate and preview processing without writing to database").props("disable")

            # Process Button - DISABLED
            with ui.row().classes("w-full items-center gap-4"):
                self.process_btn = ui.button(
                    "Process Records (DISABLED)",
                    icon="block",
                    on_click=lambda: ui.notify("RootsMagic database writer is disabled - citation format needs revision", type="warning"),
                ).props("color=grey size=lg outline")
                self.process_btn.disable()

                ui.button(
                    "Reset",
                    icon="refresh",
                    on_click=self._reset,
                ).props("outline")

            # Progress Section
            self.progress_container = ui.column().classes("w-full")
            with self.progress_container:
                self.progress_bar = ui.linear_progress(value=0).classes("w-full")
                self.progress_bar.set_visibility(False)

                with ui.row().classes("w-full items-center gap-2"):
                    self.progress_spinner = ui.spinner(size="sm")
                    self.progress_spinner.set_visibility(False)
                    self.progress_text = ui.label("Ready to process").classes(
                        "text-sm text-gray-500"
                    )

            # Results Section
            with ui.card().classes("w-full p-4") as self.results_container:
                ui.label("Results").classes("font-bold text-lg mb-2")
                self.results_content = ui.column().classes("w-full")
                with self.results_content:
                    ui.label("No results yet").classes("text-gray-400 italic text-sm")

            # Automation Section
            with ui.card().classes("w-full p-4 border-2 border-blue-400"):
                with ui.row().classes("items-center gap-2 mb-2"):
                    ui.icon("cloud_download", size="md").classes("text-blue-600")
                    ui.label("4. Download & Scrape Metadata").classes("font-bold text-lg")
                    ui.badge("ACTIVE WORKFLOW", color="blue").classes("ml-2")
                ui.label(
                    "Metadata: Always scraped from Ancestry (superior quality). "
                    "Images: Downloaded from FamilySearch (preferred) or Ancestry (fallback). "
                    "Results stored in ww2-draft.db (NOT RootsMagic database)"
                ).classes("text-sm text-gray-600 mb-3")

                # Workflow mode radio buttons
                ui.label("Workflow Mode:").classes("font-semibold text-sm mt-2 mb-1")
                with ui.row().classes("w-full gap-4"):
                    ui.radio(
                        ["standard", "ancestry_only", "metadata_only", "custom"],
                        value=self.workflow_mode,
                        on_change=lambda e: self._on_workflow_mode_change(e.value),
                    ).props("inline").bind_value(self, "workflow_mode").classes("gap-4")

                # Radio button labels with descriptions
                with ui.column().classes("w-full mt-2 mb-3 text-xs text-gray-600"):
                    ui.label("• Standard: FS images + Ancestry metadata (recommended)")
                    ui.label("• Ancestry only: Ancestry images + metadata (for Ancestry-only citations)")
                    ui.label("• Metadata only: Scrape Ancestry metadata, skip all image downloads")
                    ui.label("• Custom: Manual control via advanced options below")

                # Advanced/Debug Options (collapsible)
                with ui.expansion("Advanced / Debug Options", icon="settings").classes("w-full mt-3") as self.advanced_expansion:
                    with ui.column().classes("w-full gap-3 p-3"):
                        ui.label("Manual override controls for debugging:").classes("text-sm font-semibold mb-2")

                        ui.checkbox(
                            "Discover Ancestry URLs",
                            value=self.discover_ancestry_urls,
                            on_change=lambda e: self._on_advanced_checkbox_change("discover_ancestry_urls", e.value),
                        ).tooltip("Search AncestryLibrary to find URLs for FamilySearch citations")

                        ui.checkbox(
                            "Process FamilySearch URLs",
                            value=self.process_familysearch,
                            on_change=lambda e: self._on_advanced_checkbox_change("process_familysearch", e.value),
                        ).tooltip("Download images from FamilySearch (preferred source)")

                        ui.checkbox(
                            "Process Ancestry URLs",
                            value=self.process_ancestry,
                            on_change=lambda e: self._on_advanced_checkbox_change("process_ancestry", e.value),
                        ).tooltip("Download images from Ancestry (fallback source)")

                        ui.checkbox(
                            "Metadata Only Mode",
                            value=self.ancestry_metadata_only,
                            on_change=lambda e: self._on_advanced_checkbox_change("ancestry_metadata_only", e.value),
                        ).tooltip("Skip image downloads - only scrape and save metadata")

                with ui.row().classes("w-full gap-4 items-center mt-2"):
                    ui.label("Surname initial filter:").classes("text-sm font-medium")
                    self.surname_letter_input = ui.input(
                        placeholder="e.g. C",
                        value=self.surname_letter,
                        on_change=lambda e: self._on_surname_filter_change(e.value),
                    ).props('maxlength=1 dense outlined').classes("w-20").style("text-transform: uppercase")
                    ui.label("(blank = all surnames)").classes("text-xs text-gray-500")

                with ui.row().classes("w-full gap-4 items-center mt-2"):
                    ui.number(
                        "Max records (0 = all)",
                        value=self.automation_record_limit,
                        min=0,
                        max=500,
                        step=1,
                        on_change=lambda e: self._update_automation_record_limit(e.value),
                    ).tooltip("Limit how many rows are sent to the download workflow")

                with ui.row().classes("w-full items-center gap-3 mt-3"):
                    self.automation_button = ui.button(
                        "Run download workflow",
                        icon="cloud_download",
                        on_click=self._start_download_workflow,
                    ).props("color=primary")
                    self.automation_button.disable()

                    self.automation_stop_button = ui.button(
                        "Stop",
                        icon="stop",
                        on_click=self._stop_download_workflow,
                    ).props("color=negative")
                    self.automation_stop_button.disable()

                    ui.button(
                        "Clear download results",
                        icon="delete_outline",
                        on_click=self._clear_download_results,
                    ).props("outline")

                with ui.row().classes("w-full items-center gap-2 mt-3"):
                    self.automation_spinner = ui.spinner(size="sm")
                    self.automation_spinner.set_visibility(False)
                    self.automation_progress_bar = ui.linear_progress(value=0).classes("w-full")
                    self.automation_progress_bar.set_visibility(False)
                    self.automation_progress_text = ui.label("Ready").classes("text-sm text-gray-500")

                self.automation_results_container = ui.column().classes("w-full mt-3")
                with self.automation_results_container:
                    ui.label("No download workflow results yet").classes("text-gray-400 italic text-sm")

        return container

    async def _handle_file_upload(self, event) -> None:
        """Handle file upload event."""
        try:
            # Save uploaded file
            upload_dir = Path.home() / ".rmcitecraft" / "uploads"
            upload_dir.mkdir(parents=True, exist_ok=True)

            # NiceGUI v3 upload event has 'file' attribute
            # event.file is the uploaded file object with 'name' and async read() method
            filename = event.file.name
            file_path = upload_dir / filename

            # Read content from file object (async)
            content = await event.file.read()
            with open(file_path, "wb") as f:
                f.write(content)

            self.uploaded_file_path = file_path
            self.file_info_label.set_text(
                f"Uploaded: {filename} ({len(content) / 1024:.1f} KB)"
            )

            if self.automation_button:
                self.automation_button.enable()

            ui.notify(f"File uploaded: {filename}", type="positive")

        except Exception as e:
            logger.error(f"Error uploading file: {e}", exc_info=True)
            ui.notify(f"Error uploading file: {e}", type="negative")

    async def _start_processing(self) -> None:
        """Start batch processing - DISABLED."""
        ui.notify(
            "RootsMagic database writer is disabled. Use Section 4 (Download & Scrape Metadata) instead.",
            type="warning",
            position="top",
            timeout=5000,
        )
        return

        # Original code disabled below
        if not self.uploaded_file_path or self.processing:
            return

        self.processing = True
        self.process_btn.disable()
        self.progress_bar.set_visibility(True)
        self.progress_spinner.set_visibility(True)
        self.progress_text.set_text("Processing...")

        try:
            # Create processor with config
            processor_config = ProcessingConfig(
                db_path=Path(self.config.rm_database_path),
                skip_duplicates=self.skip_duplicates,
                validate_persons=self.validate_persons,
                stop_on_error=self.stop_on_error,
                dry_run=self.dry_run,
            )

            # Progress callback
            def on_progress(current: int, total: int, message: str):
                progress = current / total if total > 0 else 0
                self.progress_bar.set_value(progress)
                self.progress_text.set_text(
                    f"Processing {current}/{total}: {message}"
                )

            processor = DraftBatchProcessor(processor_config, progress_callback=on_progress)

            # Process file (run in executor to avoid blocking UI)
            self.batch_result = await asyncio.to_thread(
                processor.process_file, self.uploaded_file_path
            )

            # Display results
            self._display_results()

            # Notify
            if self.batch_result.errors == 0:
                ui.notify(
                    f"Processing complete: {self.batch_result.successful} successful",
                    type="positive",
                )
            else:
                ui.notify(
                    f"Processing complete with {self.batch_result.errors} errors",
                    type="warning",
                )

        except Exception as e:
            logger.error(f"Error processing batch: {e}", exc_info=True)
            ui.notify(f"Error processing batch: {e}", type="negative")

        finally:
            self.processing = False
            self.progress_bar.set_visibility(False)
            self.progress_spinner.set_visibility(False)
            self.progress_text.set_text("Processing complete")
            # Keep process_btn disabled - RootsMagic writer is disabled
            if self.uploaded_file_path:
                if self.automation_button:
                    self.automation_button.enable()

    async def _confirm_ancestry_url(self, person_name: str, ancestry_url: str, rin: int) -> bool:
        """Show confirmation dialog for discovered Ancestry URL with RootsMagic person data."""
        result_event = asyncio.Event()
        confirmed = False

        # Query RootsMagic database for person information
        person_info = self._get_person_info_from_rmtree(rin)

        def on_yes():
            nonlocal confirmed
            confirmed = True
            dialog.close()
            result_event.set()

        def on_no():
            nonlocal confirmed
            confirmed = False
            dialog.close()
            result_event.set()

        with ui.dialog() as dialog, ui.card().style("width: 720px; min-height: 450px").classes("p-6"):
            ui.label("Confirm Ancestry URL").classes("text-xl font-bold mb-4")

            # RootsMagic Person Information Panel
            with ui.card().classes("w-full p-4 mb-4").style("background-color: #f3f4f6; border: 1px solid #d1d5db"):
                ui.label("RootsMagic Person Information").classes("font-semibold text-sm mb-3")

                if person_info:
                    # Name
                    full_name = f"{person_info.given} {person_info.surname}".strip()
                    with ui.row().classes("w-full mb-2"):
                        ui.label("Name:").classes("font-semibold mr-2")
                        ui.label(full_name).classes("font-bold text-lg")

                    # RIN
                    with ui.row().classes("w-full mb-2"):
                        ui.label("RIN:").classes("font-semibold mr-2")
                        ui.label(str(person_info.rin)).classes("text-gray-600")

                    # Birth
                    with ui.row().classes("w-full mb-2"):
                        ui.label("Birth:").classes("font-semibold mr-2")
                        birth_info = []
                        if person_info.birth_date:
                            birth_info.append(person_info.birth_date)
                        if person_info.birth_place:
                            birth_info.append(person_info.birth_place)
                        birth_text = ", ".join(birth_info) if birth_info else "—"
                        ui.label(birth_text)

                    # Death
                    with ui.row().classes("w-full"):
                        ui.label("Death:").classes("font-semibold mr-2")
                        death_info = []
                        if person_info.death_date:
                            death_info.append(person_info.death_date)
                        if person_info.death_place:
                            death_info.append(person_info.death_place)
                        death_text = ", ".join(death_info) if death_info else "—"
                        ui.label(death_text)
                else:
                    # Fallback if query failed
                    ui.label(f"Name: {person_name}").classes("mb-2")
                    ui.label(f"RIN: {rin}").classes("text-gray-600")
                    ui.label("(Unable to load additional details)").classes("text-sm text-amber-600 italic")

            # Discovered Ancestry URL Panel
            with ui.card().classes("w-full p-4 mb-4").style("background-color: white; border: 1px solid #e5e7eb"):
                ui.label("Discovered Ancestry URL").classes("font-semibold text-sm mb-2")
                ui.label(ancestry_url).classes("text-sm break-all").style("color: #2563eb")

            # Question
            ui.label("Is this the correct Ancestry record for this person?").classes("text-center mb-4")

            # Buttons (Yes on left, No on right)
            with ui.row().classes("w-full justify-center gap-3"):
                ui.button("Yes", icon="check", on_click=on_yes).props("color=positive").style("min-width: 100px")
                ui.button("No", icon="cancel", on_click=on_no).props("color=negative").style("min-width: 100px")

            # Keyboard shortcuts using NiceGUI keyboard API
            ui.keyboard(on_key=lambda e: on_yes() if e.key in ['Enter', 'y', 'Y'] else (on_no() if e.key in ['n', 'N'] else None))

        dialog.open()
        await result_event.wait()
        return confirmed

    async def _start_download_workflow(self) -> None:
        """Run the Playwright download and metadata workflow."""
        if not self.uploaded_file_path or self.automation_processing:
            return

        self.automation_processing = True
        if self.automation_button:
            self.automation_button.disable()
        if self.automation_stop_button:
            self.automation_stop_button.enable()
        self.automation_stop_event = asyncio.Event()
        self.automation_stop_requested = False

        self._set_automation_progress(0.0, "Loading draft records…", busy=True)

        try:
            reader = DraftFileReader()
            records = await asyncio.to_thread(reader.read_file, self.uploaded_file_path)
            records = self._apply_surname_filter(records)

            if not records:
                letter = self.surname_letter.strip().upper()
                msg = (
                    f"No records match surname filter '{letter}'"
                    if letter and letter.isalpha()
                    else "No records found to process"
                )
                ui.notify(msg, type="warning")
                return

            options = DraftAutomationOptions(
                discover_ancestry_urls=self.discover_ancestry_urls,
                process_familysearch=self.process_familysearch,
                process_ancestry=self.process_ancestry,
                ancestry_metadata_only=self.ancestry_metadata_only,
                max_records=self.automation_record_limit or None,
                ancestry_url_confirmation_callback=self._confirm_ancestry_url if self.discover_ancestry_urls else None,
            )

            service = DraftRegistrationService(
                db_path=Path(self.config.draft_metadata_db_path),
                download_dir=Path(self.config.draft_download_dir),
            )

            def progress_callback(current: int, total: int, message: str) -> None:
                progress = current / total if total else 0
                self._set_automation_progress(progress, f"{current}/{total} • {message}", busy=True)

            self.automation_result = await service.run_batch(
                records,
                options,
                progress_callback=progress_callback,
                stop_event=self.automation_stop_event,
            )
            self._display_download_results()
            if self.automation_result.cancelled:
                ui.notify("Download workflow stopped by user", type="warning")
            else:
                ui.notify("Download workflow complete", type="positive")

        except Exception as e:  # pragma: no cover - UI level error handling
            logger.error(f"Error running download workflow: {e}", exc_info=True)
            ui.notify(f"Download workflow failed: {e}", type="negative")

        finally:
            self.automation_processing = False
            final_message = (
                "Download workflow stopped"
                if self.automation_result and self.automation_result.cancelled
                else "Download workflow complete"
            )
            self._set_automation_progress(0.0, final_message, busy=False)
            if self.uploaded_file_path and self.automation_button:
                self.automation_button.enable()
            if self.automation_stop_button:
                self.automation_stop_button.disable()
            self.automation_stop_event = None
            self.automation_stop_requested = False

    def _set_automation_progress(self, value: float, message: str, busy: bool) -> None:
        """Update automation progress UI elements."""
        self._automation_progress_value = value
        if self.automation_progress_bar:
            self.automation_progress_bar.set_value(value)
            self.automation_progress_bar.set_visibility(busy)

        if self.automation_spinner:
            self.automation_spinner.set_visibility(busy)

        if self.automation_progress_text:
            self.automation_progress_text.set_text(message)

    def _stop_download_workflow(self) -> None:
        """Signal the automation workflow to stop after the current record."""
        if not self.automation_processing or not self.automation_stop_event:
            return
        if self.automation_stop_event.is_set():
            return
        self.automation_stop_event.set()
        self.automation_stop_requested = True
        self._set_automation_progress(
            self._automation_progress_value,
            "Stopping after current record…",
            busy=True,
        )
        if self.automation_stop_button:
            self.automation_stop_button.disable()

    def _update_automation_record_limit(self, value) -> None:
        """Store sanitized automation record limit."""
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = 0
        self.automation_record_limit = max(0, parsed)

    def _apply_surname_filter(self, records: list[DraftRecord]) -> list[DraftRecord]:
        """Return records whose surname starts with self.surname_letter (case-insensitive).

        Returns all records unchanged if no valid single-letter filter is set.
        """
        letter = self.surname_letter.strip().upper()
        if not letter or not letter.isalpha():
            return records
        return [r for r in records if r.surname and r.surname[0].upper() == letter]

    def _on_surname_filter_change(self, value: str) -> None:
        """Handle surname letter filter input change."""
        raw = (value or "").strip().upper()
        self.surname_letter = raw if raw and raw.isalpha() else ""

    def _on_workflow_mode_change(self, mode: str) -> None:
        """Handle workflow mode radio button change."""
        self.workflow_mode = mode

        # Configure checkboxes based on workflow mode
        if mode == "standard":
            # FS images + Ancestry metadata
            self.discover_ancestry_urls = True
            self.process_familysearch = True
            self.process_ancestry = False
            self.ancestry_metadata_only = False
        elif mode == "ancestry_only":
            # Ancestry images + metadata
            self.discover_ancestry_urls = False
            self.process_familysearch = False
            self.process_ancestry = True
            self.ancestry_metadata_only = False
        elif mode == "metadata_only":
            # Metadata only, no images
            self.discover_ancestry_urls = True
            self.process_familysearch = False
            self.process_ancestry = False
            self.ancestry_metadata_only = True
        # mode == "custom" - don't change checkbox values

    def _on_advanced_checkbox_change(self, checkbox_name: str, value: bool) -> None:
        """Handle advanced checkbox change - switch to custom mode."""
        setattr(self, checkbox_name, value)
        # Any manual checkbox change switches to custom mode
        if self.workflow_mode != "custom":
            self.workflow_mode = "custom"

    def _display_download_results(self) -> None:
        """Render automation results summary."""
        if not self.automation_results_container:
            return

        self.automation_results_container.clear()

        if not self.automation_result or not self.automation_result.record_results:
            with self.automation_results_container:
                ui.label("No download workflow results yet").classes("text-gray-400 italic text-sm")
            return

        with self.automation_results_container:
            with ui.row().classes("w-full gap-4 mb-3"):
                with ui.card().classes("flex-1 p-3 bg-green-50 border border-green-200"):
                    ui.label("Successful").classes("text-xs text-gray-600")
                    ui.label(str(self.automation_result.successful)).classes(
                        "text-2xl font-bold text-green-700"
                    )

                with ui.card().classes("flex-1 p-3 bg-red-50 border border-red-200"):
                    ui.label("Errors").classes("text-xs text-gray-600")
                    ui.label(str(self.automation_result.errors)).classes(
                        "text-2xl font-bold text-red-700"
                    )

                with ui.card().classes("flex-1 p-3 bg-yellow-50 border border-yellow-200"):
                    ui.label("Skipped").classes("text-xs text-gray-600")
                    ui.label(str(self.automation_result.skipped)).classes(
                        "text-2xl font-bold text-yellow-700"
                    )

            if self.automation_result.cancelled:
                ui.label(
                    "Processing stopped before all rows finished. Remaining rows were not attempted."
                ).classes("text-sm text-amber-700")
            elif self.automation_result.limit_reached:
                ui.label(
                    "Stopped automatically after reaching the configured record limit."
                ).classes("text-sm text-blue-700")

            columns = [
                {"name": "row", "label": "Row", "field": "row", "align": "left"},
                {"name": "name", "label": "Name", "field": "name", "align": "left"},
                {"name": "status", "label": "Status", "field": "status", "align": "center"},
                {"name": "urltype", "label": "URL Type", "field": "urltype", "align": "center"},
                {"name": "reg", "label": "Registration ID", "field": "reg", "align": "center"},
                {"name": "ancestry", "label": "Discovered Ancestry URL", "field": "ancestry", "align": "left"},
                {"name": "message", "label": "Message", "field": "message", "align": "left"},
            ]

            rows = []
            for record_result in self.automation_result.record_results:
                if record_result.skipped:
                    status = "Skipped"
                elif record_result.success:
                    status = "Success"
                else:
                    status = "Error"

                message = record_result.message or record_result.skip_reason or ""
                rows.append({
                    "row": record_result.record.row_number,
                    "name": record_result.record.full_name,
                    "status": status,
                    "urltype": record_result.url_type or "—",
                    "reg": record_result.registration_id or "—",
                    "ancestry": record_result.discovered_ancestry_url or "—",
                    "message": message[:120] + "..." if len(message) > 120 else message,
                })

            ui.table(
                columns=columns,
                rows=rows,
                row_key="row",
                pagination={"rowsPerPage": 25},
            ).classes("w-full")

    def _clear_download_results(self) -> None:
        """Reset automation results UI."""
        self.automation_result = None
        if self.automation_results_container:
            self.automation_results_container.clear()
            with self.automation_results_container:
                ui.label("No download workflow results yet").classes("text-gray-400 italic text-sm")

    def _display_results(self) -> None:
        """Display processing results."""
        if not self.batch_result:
            return

        self.results_content.clear()
        with self.results_content:
            # Summary cards
            with ui.row().classes("w-full gap-4 mb-4"):
                # Success card
                with ui.card().classes("flex-1 p-4 bg-green-50 border border-green-200"):
                    ui.label("Successful").classes("text-xs text-gray-600")
                    ui.label(str(self.batch_result.successful)).classes(
                        "text-2xl font-bold text-green-700"
                    )

                # Errors card
                with ui.card().classes("flex-1 p-4 bg-red-50 border border-red-200"):
                    ui.label("Errors").classes("text-xs text-gray-600")
                    ui.label(str(self.batch_result.errors)).classes(
                        "text-2xl font-bold text-red-700"
                    )

                # Skipped card
                with ui.card().classes("flex-1 p-4 bg-yellow-50 border border-yellow-200"):
                    ui.label("Skipped").classes("text-xs text-gray-600")
                    ui.label(str(self.batch_result.skipped)).classes(
                        "text-2xl font-bold text-yellow-700"
                    )

                # Warnings card
                with ui.card().classes("flex-1 p-4 bg-orange-50 border border-orange-200"):
                    ui.label("Warnings").classes("text-xs text-gray-600")
                    ui.label(str(self.batch_result.warnings)).classes(
                        "text-2xl font-bold text-orange-700"
                    )

            # Processing info
            with ui.row().classes("w-full gap-4 text-sm text-gray-600"):
                ui.label(f"Processed: {self.batch_result.processed}/{self.batch_result.total_records}")
                ui.label(f"Time: {self.batch_result.processing_time:.2f}s")
                ui.label(
                    f"Rate: {self.batch_result.processed / self.batch_result.processing_time:.1f} records/sec"
                    if self.batch_result.processing_time > 0
                    else "Rate: N/A"
                )

            # Detailed results table
            ui.label("Detailed Results").classes("font-bold mt-4 mb-2")

            if self.batch_result.record_results:
                columns = [
                    {"name": "row", "label": "Row", "field": "row", "align": "left"},
                    {"name": "name", "label": "Name", "field": "name", "align": "left"},
                    {"name": "status", "label": "Status", "field": "status", "align": "center"},
                    {"name": "source", "label": "Source ID", "field": "source", "align": "center"},
                    {"name": "citation", "label": "Citation ID", "field": "citation", "align": "center"},
                    {"name": "message", "label": "Message", "field": "message", "align": "left"},
                ]

                rows = []
                for result in self.batch_result.record_results:
                    status = "✓ Success" if result.success else ("⊘ Skipped" if result.skipped else "✗ Error")
                    message = ""
                    if result.error_message:
                        message = result.error_message
                    elif result.skip_reason:
                        message = result.skip_reason
                    elif result.warning_messages:
                        message = "; ".join(result.warning_messages)

                    rows.append({
                        "row": result.record.row_number,
                        "name": result.record.full_name,
                        "status": status,
                        "source": result.source_id or "—",
                        "citation": result.citation_id or "—",
                        "message": message[:100] + "..." if len(message) > 100 else message,
                    })

                ui.table(
                    columns=columns,
                    rows=rows,
                    row_key="row",
                    pagination={"rowsPerPage": 25},
                ).classes("w-full")

    def _clear_upload(self) -> None:
        """Clear uploaded file and reset UI."""
        self.uploaded_file_path = None
        self.preview_records = []
        self.batch_result = None
        self.surname_letter = ""
        if self.surname_letter_input:
            self.surname_letter_input.set_value("")

        self.file_info_label.set_text("No file uploaded")

        self.results_content.clear()
        with self.results_content:
            ui.label("No results yet").classes("text-gray-400 italic text-sm")

        self.process_btn.disable()
        self.upload_area.reset()
        if self.automation_button:
            self.automation_button.disable()
        if self.automation_stop_button:
            self.automation_stop_button.disable()
        self.automation_stop_event = None
        self.automation_stop_requested = False
        self._clear_download_results()
        self._set_automation_progress(0.0, "Ready", busy=False)

        ui.notify("Upload cleared", type="info")

    def _reset(self) -> None:
        """Reset entire tab to initial state."""
        self._clear_upload()
        self.skip_duplicates = True
        self.validate_persons = True
        self.stop_on_error = False
        self.dry_run = False
