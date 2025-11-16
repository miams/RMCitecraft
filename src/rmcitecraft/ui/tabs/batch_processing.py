"""Batch Processing Tab for RMCitecraft.

This tab provides the batch citation processing interface with three panels:
- Left: Citation queue with status and filters
- Center: Data entry form for missing fields
- Right: Census image viewer
"""

import asyncio
from pathlib import Path

from loguru import logger
from nicegui import ui

from rmcitecraft.config import get_config
from rmcitecraft.repositories import DatabaseConnection
from rmcitecraft.services.batch_processing import (
    BatchProcessingController,
    CitationBatchItem,
    BatchProcessingState,
)
from rmcitecraft.services.familysearch_automation import FamilySearchAutomation
from rmcitecraft.services.image_processing import get_image_processing_service
from rmcitecraft.services.message_log import get_message_log, MessageType
from rmcitecraft.ui.components.citation_queue import CitationQueueComponent
from rmcitecraft.ui.components.data_entry_form import DataEntryFormComponent
from rmcitecraft.ui.components.image_viewer import create_census_image_viewer
from rmcitecraft.ui.components.message_log_panel import MessageLogPanel


class BatchProcessingTab:
    """Batch Processing Tab component."""

    def __init__(self) -> None:
        """Initialize batch processing tab."""
        self.config = get_config()
        self.db = DatabaseConnection()
        self.controller = BatchProcessingController()

        # Services
        self.familysearch_automation = FamilySearchAutomation()
        self.message_log = get_message_log()
        try:
            self.image_service = get_image_processing_service()
        except RuntimeError as e:
            logger.warning(f"Image processing service not available: {e}")
            self.image_service = None

        # State
        self.selected_census_year: int | None = None
        self.selected_citation_ids: set[int] = set()  # Track selected citations

        # UI component references
        self.queue_component: CitationQueueComponent | None = None
        self.form_component: DataEntryFormComponent | None = None
        self.message_log_panel: MessageLogPanel | None = None
        self.queue_container: ui.column | None = None
        self.form_container: ui.column | None = None
        self.image_container: ui.column | None = None
        self.session_status_label: ui.label | None = None
        self.three_panel_container: ui.row | None = None
        self.header_container: ui.card | None = None
        self.status_bar_container: ui.row | None = None

    def render(self) -> None:
        """Render the batch processing tab."""
        with ui.column().classes("w-full h-full gap-1 p-1"):
            # Header with session controls (compact)
            self._render_session_header()

            # Three-panel layout container
            with ui.row().classes("w-full flex-grow flex-nowrap gap-0") as self.three_panel_container:
                self._render_three_panels()

            # Bottom status bar (only visible in Batch Processing)
            with ui.row().classes("w-full items-center bg-gray-100 px-2 py-1 border-t") as self.status_bar_container:
                self._render_status_bar()

            # Message log panel at bottom
            self.message_log_panel = MessageLogPanel(self.message_log)
            self.message_log_panel.render()

    def _render_three_panels(self) -> None:
        """Render the three-panel layout."""
        if not self.controller.session:
            # No session - show placeholder
            with ui.card().classes("w-full h-full items-center justify-center"):
                ui.label("Load citations to begin batch processing").classes(
                    "text-gray-500 italic text-lg"
                )
            return

        # Session exists - render panels directly (already inside row container)
        # Left panel: Citation queue (35% width)
        with ui.card().classes("w-[35%] h-full flex-shrink-0 p-1"):
            ui.label("Citation Queue").classes("font-bold text-sm mb-1")
            self.queue_component = CitationQueueComponent(
                citations=self.controller.session.citations,
                on_citation_click=self._on_citation_selected,
                on_selection_change=self._on_selection_changed,
                on_process_selected=self._on_process_selected,
            )
            with ui.column().classes("w-full h-full") as self.queue_container:
                self.queue_component.container = self.queue_container
                self.queue_component._render_content()

        # Center panel: Data entry form (30% width)
        with ui.card().classes("w-[30%] h-full flex-shrink-0 overflow-auto p-1"):
            if self.controller.session.current_citation:
                self.form_component = DataEntryFormComponent(
                    citation=self.controller.session.current_citation,
                    on_data_change=self._on_form_data_changed,
                    on_submit=self._on_form_submitted,
                )
                with ui.column().classes("w-full h-full gap-2") as self.form_container:
                    self.form_component.container = self.form_container
                    self.form_component._render_content()
            else:
                with ui.column().classes("w-full h-full items-center justify-center"):
                    ui.label("Select a citation to begin").classes(
                        "text-gray-500 italic text-center"
                    )

        # Right panel: Census image viewer (35% width, extra compact)
        with ui.card().classes("w-[35%] h-full flex-shrink-0 overflow-hidden p-1") as self.image_container:
            with ui.column().classes("w-full h-full gap-0"):
                # Header (compact)
                with ui.row().classes("w-full items-center justify-between p-1 border-b"):
                    ui.label("Census Image").classes("font-semibold text-sm")

                    if self.controller.session.current_citation:
                        citation = self.controller.session.current_citation
                        if citation.familysearch_url:
                            # Open in new tab button
                            ui.button(
                                icon="open_in_new",
                                on_click=lambda url=citation.familysearch_url: ui.run_javascript(f"window.open('{url}', '_blank')"),
                            ).props("flat dense").tooltip("Open in new tab")

                # Image viewer
                if self.controller.session.current_citation:
                    citation = self.controller.session.current_citation
                    # Show local image if available, otherwise show FamilySearch viewer
                    if citation.local_image_path:
                        self._render_local_image(citation.local_image_path, citation.familysearch_url)
                    elif citation.familysearch_url:
                        self._render_familysearch_viewer(citation.familysearch_url)
                    else:
                        with ui.column().classes("w-full h-full items-center justify-center"):
                            ui.icon("link_off", size="2rem").classes("text-gray-400")
                            ui.label("No FamilySearch URL").classes("text-gray-500 text-xs")
                else:
                    with ui.column().classes("w-full h-full items-center justify-center"):
                        ui.icon("image", size="2rem").classes("text-gray-400")
                        ui.label("Select a citation").classes("text-gray-500 text-xs")

    def _render_session_header(self) -> None:
        """Render session header with controls."""
        with ui.card().classes("w-full p-1") as self.header_container:
            self._render_header_content()

    def _render_header_content(self) -> None:
        """Render the content inside the header (compact single line)."""
        with ui.row().classes("w-full items-center justify-between"):
            # Session status (compact)
            if self.controller.session:
                self.session_status_label = ui.label(
                    self._get_session_status_text()
                ).classes("text-sm text-gray-700 font-medium")
            else:
                self.session_status_label = ui.label("No active session").classes(
                    "text-sm text-gray-500 italic"
                )

            # Actions (compact buttons)
            with ui.row().classes("gap-1"):
                ui.button(
                    "Load",
                    icon="download",
                    on_click=self._show_load_dialog,
                ).props("dense outline")

                if self.controller.session:
                    ui.button(
                        "Process",
                        icon="play_arrow",
                        on_click=self._start_batch_processing,
                    ).props("dense color=primary")

                    ui.button(
                        "Export",
                        icon="save",
                        on_click=self._export_results,
                    ).props("dense outline")

    def _render_status_bar(self) -> None:
        """Render bottom status bar showing current citation info."""
        if not self.controller.session or not self.controller.session.current_citation:
            ui.label("No citation selected").classes("text-xs text-gray-500 italic")
            return

        citation = self.controller.session.current_citation

        # Compact status info
        with ui.row().classes("items-center gap-4 text-xs text-gray-700"):
            ui.label(f"Data Entry: {citation.full_name}").classes("font-medium")
            ui.label(f"Person ID: {citation.person_id}")
            ui.label(f"Event ID: {citation.event_id}")
            ui.label(f"Citation ID: {citation.citation_id}")
            ui.label(
                f"{citation.census_year} U.S. Census - "
                f"{citation.extracted_data.get('county', 'Unknown')}, "
                f"{citation.extracted_data.get('state', 'Unknown')}"
            )

    def _show_load_dialog(self) -> None:
        """Show dialog to load citations for batch processing."""
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label("Load Citations for Batch Processing").classes("font-bold text-lg mb-4")

            # Census year selector
            ui.label("Select Census Year:").classes("font-medium mb-2")
            year_select = ui.select(
                [1790 + (i * 10) for i in range(17)],  # 1790-1950
                value=1940,
            ).props("outlined").classes("w-full mb-4")

            # Limit input
            ui.label("Number of Citations:").classes("font-medium mb-2")
            limit_input = ui.number(
                label="Limit",
                value=10,
                min=1,
                max=1000,
            ).props("outlined").classes("w-full mb-4")

            # Offset input (for pagination)
            ui.label("Start at Entry # (Offset):").classes("font-medium mb-2")
            offset_input = ui.number(
                label="Offset",
                value=0,
                min=0,
                max=10000,
            ).props("outlined").classes("w-full mb-4")

            # Actions
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button(
                    "Load",
                    icon="download",
                    on_click=lambda: self._load_citations(
                        year_select.value,
                        int(limit_input.value),
                        int(offset_input.value),
                        dialog,
                    ),
                ).props("color=primary")

        dialog.open()

    def _load_citations(self, census_year: int, limit: int, offset: int, dialog: ui.dialog) -> None:
        """Load citations from database for batch processing.

        Args:
            census_year: Census year to load
            limit: Maximum number of citations to load
            offset: Number of citations to skip (for pagination)
            dialog: Dialog to close after loading
        """
        dialog.close()

        offset_text = f" starting at entry {offset + 1}" if offset > 0 else ""
        self._notify_and_log(f"Loading {limit} citations for {census_year} census{offset_text}...", type="info")

        try:
            # Import the find function from batch script
            from process_census_batch import find_census_citations

            # Find citations
            db_path = str(self.config.rm_database_path)
            result = find_census_citations(db_path, census_year, limit=limit, offset=offset)

            if not result['citations']:
                self._notify_and_log(f"No citations found for {census_year} census at offset {offset}", type="warning")
                return

            # Create batch session
            self.controller.create_session(census_year, result['citations'])

            # Clear any previous selections when loading new batch
            self.selected_citation_ids = set()

            # Provide feedback with explanation if count differs from requested
            examined = result['examined']
            found = result['found']
            excluded = result['excluded']

            if excluded > 0:
                # Show which citations were excluded
                missing_count = excluded
                logger.info(
                    f"Examined {examined} citations, found {found} with URLs, excluded {excluded} without URLs"
                )
                self._notify_and_log(
                    f"Loaded {found} citations (examined {examined}, excluded {excluded} without URLs)",
                    type="info",
                )
                # Log detailed explanation for message log
                self.message_log.log_info(
                    f"To find excluded citations: Go to Citation Manager tab → Select census year filter → "
                    f"Look for citations with 'No URL' status",
                    source="Batch Processing - Info"
                )
                # Offer to show excluded citations
                with ui.dialog() as excluded_dialog, ui.card().classes("w-96"):
                    ui.label(f"{excluded} Citations Excluded").classes("font-bold text-lg mb-2")
                    ui.label(
                        f"{excluded} citations were skipped because they don't have FamilySearch URLs. "
                        "These citations cannot be processed automatically."
                    ).classes("text-sm mb-4")

                    ui.label("To find these citations:").classes("font-semibold text-sm mb-2")
                    ui.label("1. Go to Citation Manager tab").classes("text-xs ml-4")
                    ui.label("2. Select census year filter").classes("text-xs ml-4")
                    ui.label("3. Look for citations with 'No URL' status").classes("text-xs ml-4")

                    ui.button("OK", on_click=excluded_dialog.close).props("color=primary").classes("mt-4")

                ui.button(
                    icon="info",
                    on_click=excluded_dialog.open,
                ).props("flat round dense").classes("text-blue-600").tooltip(
                    f"Why {excluded} excluded?"
                )
            else:
                self._notify_and_log(
                    f"Loaded {found} citations for {census_year} census",
                    type="positive",
                )

            # Refresh UI
            self._refresh_all_panels()

        except Exception as e:
            logger.error(f"Failed to load citations: {e}")
            self._notify_and_log(f"Error loading citations: {e}", type="negative")

    async def _start_batch_processing(self) -> None:
        """Start automated batch processing of loaded citations.

        Behavior:
        - If citations are selected (checked): process only selected citations
        - If no selections: process all incomplete citations
        """
        if not self.controller.session:
            self._notify_and_log("No batch session loaded", type="warning")
            return

        # Check if user has selected specific citations
        if self.selected_citation_ids:
            # Process only selected citations
            citations_to_process = [
                c for c in self.controller.session.citations
                if c.citation_id in self.selected_citation_ids
            ]
            self._notify_and_log(
                f"Processing {len(citations_to_process)} selected citations...",
                type="info"
            )
        else:
            # No selections - process all incomplete citations
            citations_to_process = [
                c for c in self.controller.session.citations
                if c.status.value in ["queued", "manual_review"]
            ]
            self._notify_and_log(
                f"Processing all {len(citations_to_process)} incomplete citations...",
                type="info"
            )

        if not citations_to_process:
            self._notify_and_log("No citations to process", type="warning")
            return

        # Create progress dialog
        with ui.dialog().props('persistent') as progress_dialog, ui.card().classes('w-96'):
            ui.label('Batch Processing').classes('text-lg font-bold mb-4')

            progress_label = ui.label('Starting...').classes('text-sm mb-2')
            progress_bar = ui.linear_progress(value=0).props('instant-feedback')

            status_label = ui.label('').classes('text-xs text-gray-600 mt-2')

        progress_dialog.open()

        processed = 0
        errors = 0
        total = len(citations_to_process)

        for i, citation in enumerate(citations_to_process, 1):
            # Update progress
            progress_label.text = f"Processing {i} of {total}: {citation.full_name}"
            progress_bar.value = i / total
            status_label.text = f"{processed} completed, {errors} errors"

            try:
                await self._process_single_citation(citation)
                processed += 1

                # Refresh queue component only (don't destroy/recreate UI)
                if self.queue_component:
                    self.queue_component.refresh()

            except Exception as e:
                logger.error(f"Error processing citation {citation.citation_id}: {e}")
                self.controller.mark_citation_error(citation, str(e))
                errors += 1

            # Small delay to allow UI update
            await asyncio.sleep(0.1)

        # Close progress dialog
        progress_dialog.close()

        # Show completion message
        self._notify_and_log(
            f"Batch processing complete! {processed} processed, {errors} errors",
            type="positive"
        )

        # Refresh queue component (don't destroy/recreate entire UI)
        if self.queue_component:
            self.queue_component.refresh()

        # Refresh form if a citation is selected
        if self.controller.session and self.controller.session.current_citation:
            self._refresh_form_panel()

    async def _process_single_citation(self, citation: CitationBatchItem) -> None:
        """Process a single citation (extraction and image download if needed).

        Args:
            citation: Citation to process
        """
        if not citation.familysearch_url:
            self.controller.mark_citation_error(citation, "No FamilySearch URL available")
            return

        # Extract data from FamilySearch with year-specific extraction logic
        extracted_data = await self.familysearch_automation.extract_citation_data(
            citation.familysearch_url,
            census_year=citation.census_year
        )

        if not extracted_data:
            self.controller.mark_citation_error(citation, "Failed to extract citation data")
            return

        # Update citation with extracted data
        self.controller.update_citation_extracted_data(citation, extracted_data)

        # If citation needs manual review and doesn't have existing media, download the image
        if citation.needs_manual_entry and not citation.has_existing_media:
            await self._download_citation_image(citation)

    async def _download_citation_image(self, citation: CitationBatchItem) -> None:
        """Download census image for manual entry.

        Args:
            citation: Citation that needs an image
        """
        # Get image viewer URL from extracted data
        image_viewer_url = citation.extracted_data.get('image_viewer_url')

        if not image_viewer_url:
            logger.warning(f"No image viewer URL for citation {citation.citation_id}, cannot download image")
            return

        try:
            # Create temp directory for downloaded images if it doesn't exist
            from pathlib import Path
            temp_dir = Path.home() / ".rmcitecraft" / "temp_images"
            temp_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename: YYYY_State_County_Surname_Given_CitationID.jpg
            census_year = citation.census_year
            state = citation.extracted_data.get('state', 'Unknown')
            county = citation.extracted_data.get('county', 'Unknown')
            surname = citation.surname
            given = citation.given_name
            cit_id = citation.citation_id

            # Sanitize filename components
            def sanitize(s: str) -> str:
                """Remove illegal filename characters."""
                return "".join(c for c in s if c.isalnum() or c in (' ', '-', '_')).strip()

            filename = f"{census_year}_{sanitize(state)}_{sanitize(county)}_{sanitize(surname)}_{sanitize(given)}_cit{cit_id}.jpg"
            download_path = temp_dir / filename

            logger.info(f"Downloading census image for citation {citation.citation_id} to {download_path}")

            # Download the image using the image viewer URL (not the record URL)
            success = await self.familysearch_automation.download_census_image(
                image_viewer_url,
                download_path
            )

            if success:
                # Store the local path on the citation
                citation.local_image_path = str(download_path)
                logger.info(f"Successfully downloaded image to {download_path}")
                # Don't notify here - we're in async processing context
            else:
                logger.warning(f"Failed to download image for citation {citation.citation_id}")
                # Don't notify here - we're in async processing context

        except Exception as e:
            logger.error(f"Error downloading image for citation {citation.citation_id}: {e}")
            # Don't notify here - we're in async processing context

    def _on_citation_selected(self, citation: CitationBatchItem) -> None:
        """Handle citation selection from queue.

        Args:
            citation: Selected citation
        """
        if self.controller.session:
            # Update session current citation
            self.controller.session.move_to_citation(citation.citation_id)

            # Refresh form, image viewer, and status bar
            self._refresh_form_panel()
            self._refresh_image_panel()
            self._refresh_status_bar()

    def _on_selection_changed(self, selected_ids: set[int]) -> None:
        """Handle multi-selection change in queue.

        Args:
            selected_ids: Set of selected citation IDs
        """
        self.selected_citation_ids = selected_ids
        logger.debug(f"Selection changed: {len(selected_ids)} citations selected")

    async def _on_process_selected(self, selected_ids: set[int]) -> None:
        """Handle process selected button click.

        Args:
            selected_ids: Set of selected citation IDs to process
        """
        if not selected_ids:
            self._notify_and_log("No citations selected", type="warning")
            return

        self._notify_and_log(f"Processing {len(selected_ids)} selected citations...", type="info")

        # Get citations by ID
        citations_to_process = [
            c for c in self.controller.session.citations
            if c.citation_id in selected_ids
        ]

        # Create progress dialog
        with ui.dialog().props('persistent') as progress_dialog, ui.card().classes('w-96'):
            ui.label('Processing Citations').classes('text-lg font-bold mb-4')

            progress_label = ui.label('Starting...').classes('text-sm mb-2')
            progress_bar = ui.linear_progress(value=0).props('instant-feedback')

            status_label = ui.label('').classes('text-xs text-gray-600 mt-2')

        progress_dialog.open()

        processed = 0
        total = len(citations_to_process)

        for i, citation in enumerate(citations_to_process, 1):
            if citation.status.value in ["queued", "manual_review"]:
                # Update progress
                progress_label.text = f"Processing {i} of {total}: {citation.full_name}"
                progress_bar.value = i / total
                status_label.text = f"{processed} completed, {i - processed - 1} errors"

                try:
                    await self._process_single_citation(citation)
                    processed += 1

                    # Refresh queue component only (don't destroy/recreate UI)
                    if self.queue_component:
                        self.queue_component.refresh()

                except Exception as e:
                    logger.error(f"Error processing citation {citation.citation_id}: {e}")
                    self.controller.mark_citation_error(citation, str(e))

                # Small delay to allow UI update
                await asyncio.sleep(0.1)

        # Calculate errors
        error_count = total - processed

        # Log completion
        logger.info(f"Batch processing complete: {processed} processed, {error_count} errors")

        # Close progress dialog
        progress_dialog.close()

        # Refresh queue component (don't destroy/recreate entire UI)
        if self.queue_component:
            self.queue_component.refresh()

        # Refresh form if a citation is selected
        if self.controller.session and self.controller.session.current_citation:
            self._refresh_form_panel()

        # Note: Cannot use ui.notify or ui.timer here - dialog context is deleted
        # User will see results in the refreshed queue component

    def _on_form_data_changed(self, form_data: dict) -> None:
        """Handle form data change.

        Args:
            form_data: Updated form data
        """
        if self.controller.session and self.controller.session.current_citation:
            # Update citation with manual data
            self.controller.update_citation_manual_data(
                self.controller.session.current_citation,
                form_data,
            )

            # Refresh queue to show updated status
            if self.queue_component:
                self.queue_component.refresh()

    def _on_form_submitted(self) -> None:
        """Handle form submission."""
        if not self.controller.session or not self.controller.session.current_citation:
            return

        citation = self.controller.session.current_citation

        if citation.validation and citation.validation.is_valid:
            self._notify_and_log(f"Citation for {citation.full_name} complete!", type="positive")

            # Move to next citation
            if self.controller.session.move_to_next():
                self._refresh_form_panel()
                self._refresh_image_panel()
                if self.queue_component:
                    self.queue_component.refresh()
            else:
                self._notify_and_log("All citations processed!", type="positive")
        else:
            self._notify_and_log("Please fix validation errors before submitting", type="warning")

    async def _export_results(self) -> None:
        """Export batch processing results to database and organize image files."""
        if not self.controller.session:
            self._notify_and_log("No batch session loaded", type="warning")
            return

        session = self.controller.session
        completed_citations = [c for c in session.citations if c.is_complete]

        if not completed_citations:
            self._notify_and_log("No completed citations to export", type="warning")
            return

        # Confirm export
        with ui.dialog() as confirm_dialog, ui.card():
            ui.label("Export Citations to Database").classes("text-lg font-bold mb-2")
            ui.label(f"This will write {len(completed_citations)} completed citations to the database.").classes("mb-2")
            ui.label("Census images will be renamed and moved to their final locations.").classes("mb-4")

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=confirm_dialog.close).props("flat")
                # Call export directly (not as background task) to maintain UI context
                ui.button("Export", on_click=lambda: self._do_export(
                    confirm_dialog, completed_citations
                )).props("color=primary")

        confirm_dialog.open()

    async def _do_export(self, dialog, completed_citations: list[CitationBatchItem]) -> None:
        """Perform the actual export operation."""
        from datetime import datetime

        from rmcitecraft.models.image import ImageMetadata
        from rmcitecraft.services.image_processing import get_image_processing_service

        dialog.close()

        # Show progress dialog (UI context is maintained since we're not in background task)
        with ui.dialog() as progress_dialog, ui.card().classes("p-6"):
            ui.label("Exporting to Database...").classes("text-lg font-bold mb-4")
            progress_label = ui.label("Processing citations...").classes("mb-2")
            progress_bar = ui.linear_progress(value=0).classes("mb-4")

        progress_dialog.open()

        # Track results
        citations_written = 0
        images_processed = 0
        errors = []

        try:
            # Get services
            image_service = get_image_processing_service()

            # Process each citation
            for i, citation in enumerate(completed_citations):
                try:
                    progress_label.text = f"Processing {citation.full_name} ({i+1}/{len(completed_citations)})"
                    progress_bar.value = i / len(completed_citations)
                    await ui.context.client.connected()  # Allow UI update

                    # 1. Write citation fields to database
                    await self._write_citation_to_database(citation)
                    citations_written += 1

                    # 2. Process image if downloaded
                    if citation.local_image_path and Path(citation.local_image_path).exists():
                        # Create ImageMetadata from citation data
                        # Generate access date in Evidence Explained format: "D Month YYYY"
                        access_date = citation.merged_data.get('access_date')
                        if not access_date:
                            # Generate today's date in correct format
                            today = datetime.now()
                            access_date = today.strftime("%-d %B %Y")  # e.g., "7 November 2024"

                        metadata = ImageMetadata(
                            image_id=f"batch_{citation.citation_id}",
                            citation_id=str(citation.citation_id),  # Convert to string
                            year=citation.census_year,
                            state=citation.merged_data.get('state', ''),
                            county=citation.merged_data.get('county', ''),
                            surname=citation.surname,
                            given_name=citation.given_name,
                            familysearch_url=citation.familysearch_url or '',
                            access_date=access_date,
                            town_ward=citation.merged_data.get('town_ward'),
                            enumeration_district=citation.merged_data.get('enumeration_district'),
                            sheet=citation.merged_data.get('sheet'),
                            line=citation.merged_data.get('line'),
                            family_number=citation.merged_data.get('family_number'),
                            dwelling_number=citation.merged_data.get('dwelling_number'),
                        )

                        # Register metadata with image service before processing
                        image_service.register_pending_image(metadata)

                        # Process image (rename, move, create DB records)
                        result = image_service.process_downloaded_file(citation.local_image_path)
                        if result:
                            images_processed += 1
                            logger.info(f"Processed image for {citation.full_name}: {result.final_filename}")
                        else:
                            errors.append(f"{citation.full_name}: Failed to process image")

                except Exception as e:
                    logger.error(f"Error exporting citation {citation.citation_id}: {e}")
                    errors.append(f"{citation.full_name}: {str(e)}")

            # Update progress to 100%
            progress_bar.value = 1.0
            progress_label.text = "Checkpointing database..."

            # Checkpoint WAL to ensure changes are visible to RootsMagic
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                logger.info("WAL checkpoint completed - changes committed to main database file")

            progress_label.text = "Export complete!"

            # Wait a moment before closing
            await asyncio.sleep(0.5)
            progress_dialog.close()

            # Show results
            if errors:
                error_msg = "\n".join(errors[:5])  # Show first 5 errors
                if len(errors) > 5:
                    error_msg += f"\n... and {len(errors) - 5} more"
                self._notify_and_log(
                    f"Export completed with {len(errors)} errors. "
                    f"Written: {citations_written} citations, {images_processed} images. "
                    f"Restart RootsMagic to see changes.",
                    type="warning"
                )
                # Show error details
                with ui.dialog() as error_dialog, ui.card():
                    ui.label("Export Errors").classes("text-lg font-bold mb-2")
                    ui.label(error_msg).classes("whitespace-pre-wrap mb-4")
                    ui.button("Close", on_click=error_dialog.close)
                error_dialog.open()
            else:
                self._notify_and_log(
                    f"Successfully exported {citations_written} citations and {images_processed} images! "
                    f"Restart RootsMagic to see changes.",
                    type="positive"
                )

        except Exception as e:
            logger.error(f"Export failed: {e}")

            # Checkpoint WAL even on failure (partial data may have been written)
            try:
                with self.db.transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    logger.info("WAL checkpoint completed after error")
            except Exception as checkpoint_error:
                logger.error(f"Failed to checkpoint WAL after error: {checkpoint_error}")

            progress_dialog.close()
            self._notify_and_log(f"Export failed: {str(e)}", type="negative")

    async def _write_citation_to_database(self, citation) -> None:
        """Write citation fields to SourceTable.Fields BLOB.

        For free-form sources (TemplateID=0), writes Footnote, ShortFootnote, Bibliography
        to SourceTable.Fields as XML.
        """
        from rmcitecraft.database.image_repository import ImageRepository

        # Get database connection in write mode
        with self.db.transaction() as conn:
            repo = ImageRepository(conn)

            # Update SourceTable.Fields BLOB with formatted citations
            repo.update_source_fields(
                source_id=citation.source_id,
                footnote=citation.footnote,
                short_footnote=citation.short_footnote,
                bibliography=citation.bibliography,
            )

            logger.info(f"Wrote citation fields to database for SourceID={citation.source_id} (CitationID={citation.citation_id})")

    def _get_session_status_text(self) -> str:
        """Get session status text.

        Returns:
            Status text string
        """
        if not self.controller.session:
            return "No active session"

        summary = self.controller.get_session_summary()
        return (
            f"{summary['census_year']} Census: "
            f"{summary['complete']}/{summary['total']} complete "
            f"({summary['progress_percentage']:.0f}%)"
        )

    def _refresh_all_panels(self) -> None:
        """Refresh all UI panels by re-rendering the three-panel container."""
        # Refresh header to show/hide buttons based on session state
        if self.header_container:
            self.header_container.clear()
            with self.header_container:
                self._render_header_content()

        # Refresh three-panel container
        if self.three_panel_container:
            self.three_panel_container.clear()
            with self.three_panel_container:
                self._render_three_panels()

        # Refresh status bar
        self._refresh_status_bar()

    def _refresh_status_bar(self) -> None:
        """Refresh bottom status bar."""
        if self.status_bar_container:
            self.status_bar_container.clear()
            with self.status_bar_container:
                self._render_status_bar()

    def _refresh_queue_panel(self) -> None:
        """Refresh citation queue panel."""
        if self.queue_component and self.controller.session:
            self.queue_component.update_citations(self.controller.session.citations)

    def _refresh_form_panel(self) -> None:
        """Refresh data entry form panel."""
        if self.form_component and self.controller.session:
            self.form_component.update_citation(self.controller.session.current_citation)

    def _refresh_image_panel(self) -> None:
        """Refresh image viewer panel."""
        if not self.image_container or not self.controller.session:
            return

        # Clear and re-render image container
        self.image_container.clear()
        with self.image_container:
            with ui.column().classes("w-full h-full gap-0"):
                # Header (compact)
                with ui.row().classes("w-full items-center justify-between p-1 border-b"):
                    ui.label("Census Image").classes("font-semibold text-sm")

                    if self.controller.session.current_citation:
                        citation = self.controller.session.current_citation
                        if citation.familysearch_url:
                            # Open in new tab button
                            ui.button(
                                icon="open_in_new",
                                on_click=lambda url=citation.familysearch_url: ui.run_javascript(f"window.open('{url}', '_blank')"),
                            ).props("flat dense").tooltip("Open in new tab")

                # Image viewer
                if self.controller.session.current_citation:
                    citation = self.controller.session.current_citation
                    # Show local image if available, otherwise show FamilySearch viewer
                    if citation.local_image_path:
                        self._render_local_image(citation.local_image_path, citation.familysearch_url)
                    elif citation.familysearch_url:
                        self._render_familysearch_viewer(citation.familysearch_url)
                    else:
                        with ui.column().classes("w-full h-full items-center justify-center"):
                            ui.icon("link_off", size="2rem").classes("text-gray-400")
                            ui.label("No FamilySearch URL").classes("text-gray-500 text-xs")
                else:
                    with ui.column().classes("w-full h-full items-center justify-center"):
                        ui.icon("image", size="2rem").classes("text-gray-400")
                        ui.label("Select a citation").classes("text-gray-500 text-xs")

    def _render_local_image(self, image_path: str, familysearch_url: str | None = None) -> None:
        """Render locally downloaded census image with keyboard zoom/pan controls.

        Args:
            image_path: Path to local image file
            familysearch_url: Optional FamilySearch URL for opening in browser

        Keyboard controls:
            Z - Toggle 400% zoom (top-right)
            = - Zoom in 25%
            - - Zoom out 25%
            Arrow keys - Pan 90% of viewport
        """
        from pathlib import Path

        # Check if image file exists
        if not Path(image_path).exists():
            logger.warning(f"Image file not found: {image_path}")
            with ui.column().classes("w-full h-full items-center justify-center"):
                ui.icon("broken_image", size="2rem").classes("text-red-400")
                ui.label("Image file not found").classes("text-red-500 text-xs")
            return

        # Scrollable container with keyboard controls (FIXED HEIGHT, scrollable content)
        with ui.element('div').classes("w-full overflow-auto p-0 relative") as container:
            container._props['id'] = 'census-image-container'
            container._props['tabindex'] = '0'  # Make focusable for keyboard events
            container._props['style'] = 'height: 100%; max-height: 100%; flex: 0 0 auto;'  # Prevent flex resizing

            # Zoom indicator (top-left overlay, positioned absolutely relative to container)
            zoom_label = ui.label("100%").classes("absolute top-1 left-1 bg-black bg-opacity-60 text-white text-[10px] px-2 py-1 rounded z-10")
            zoom_label._props['style'] = 'position: sticky; top: 4px; left: 4px;'

            # Keyboard shortcuts hint (bottom-left overlay)
            shortcuts_label = ui.label("Z=400% zoom | =/- zoom | arrows=pan").classes(
                "absolute bottom-1 left-1 bg-black bg-opacity-60 text-white text-[9px] px-2 py-1 rounded z-10"
            )
            shortcuts_label._props['style'] = 'position: sticky; bottom: 4px; left: 4px;'

            # Image (starts at fit-to-width, will scale but container stays fixed)
            img = ui.image(image_path).classes("object-contain transition-all duration-200")
            img._props['id'] = 'census-image'
            img._props['style'] = 'display: block; width: 100%; height: auto; min-height: 0;'

            # Optional: Link to view on FamilySearch
            if familysearch_url:
                with ui.row().classes("w-full justify-center gap-1 mt-1"):
                    ui.button(
                        "View on FamilySearch",
                        icon="open_in_new",
                        on_click=lambda: ui.run_javascript(f"window.open('{familysearch_url}', '_blank')")
                    ).props("dense size=sm").classes("text-[10px]")

        # JavaScript for keyboard controls
        ui.run_javascript(f"""
        (function() {{
            const container = document.getElementById('census-image-container');
            const image = document.getElementById('census-image');
            const zoomLabel = container.querySelector('.absolute.top-1');

            if (!container || !image) return;

            // State
            let currentZoom = 100;  // Start at 100% (fit-to-width)
            let isQuickZoom = false;  // Is 400% quick zoom active?
            let savedScroll = {{ x: 0, y: 0 }};  // Saved scroll position for toggle

            const MIN_ZOOM = 25;
            const MAX_ZOOM = 800;
            const QUICK_ZOOM = 400;

            // Update zoom display
            function updateZoom(zoom) {{
                currentZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoom));
                // Set image width directly
                image.style.width = currentZoom + '%';
                zoomLabel.textContent = Math.round(currentZoom) + '%';
            }}

            // Scroll to top-right corner
            function scrollToTopRight() {{
                // Use setTimeout to ensure image has resized before calculating scroll
                setTimeout(() => {{
                    // Scroll to the maximum possible right position
                    container.scrollLeft = container.scrollWidth - container.clientWidth + 100;
                    container.scrollTop = 0;
                }}, 150);
            }}

            // Save current scroll position
            function saveScroll() {{
                savedScroll = {{
                    x: container.scrollLeft,
                    y: container.scrollTop
                }};
            }}

            // Restore saved scroll position
            function restoreScroll() {{
                container.scrollLeft = savedScroll.x;
                container.scrollTop = savedScroll.y;
            }}

            // Pan image (90% of viewport)
            function pan(direction) {{
                const panAmount = 0.9;
                switch(direction) {{
                    case 'up':
                        container.scrollTop -= container.clientHeight * panAmount;
                        break;
                    case 'down':
                        container.scrollTop += container.clientHeight * panAmount;
                        break;
                    case 'left':
                        container.scrollLeft -= container.clientWidth * panAmount;
                        break;
                    case 'right':
                        container.scrollLeft += container.clientWidth * panAmount;
                        break;
                }}
            }}

            // Keyboard event handler
            container.addEventListener('keydown', (e) => {{
                // Don't intercept if user is typing in an input field
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {{
                    return;
                }}

                switch(e.key) {{
                    case 'z':
                    case 'Z':
                        e.preventDefault();
                        if (isQuickZoom) {{
                            // Toggle back to original zoom
                            isQuickZoom = false;
                            updateZoom(100);  // Back to fit-to-width
                            // Wait for image to resize, then restore scroll
                            setTimeout(restoreScroll, 150);
                        }} else {{
                            // Save current position and zoom to 400%
                            saveScroll();
                            isQuickZoom = true;
                            updateZoom(QUICK_ZOOM);
                            // Wait for image to resize, then scroll to top-right
                            scrollToTopRight();
                        }}
                        break;

                    case '=':
                    case '+':
                        e.preventDefault();
                        isQuickZoom = false;  // Exit quick zoom mode
                        updateZoom(currentZoom + 25);
                        break;

                    case '-':
                    case '_':
                        e.preventDefault();
                        isQuickZoom = false;  // Exit quick zoom mode
                        updateZoom(currentZoom - 25);
                        break;

                    case 'ArrowUp':
                        e.preventDefault();
                        pan('up');
                        break;

                    case 'ArrowDown':
                        e.preventDefault();
                        pan('down');
                        break;

                    case 'ArrowLeft':
                        e.preventDefault();
                        pan('left');
                        break;

                    case 'ArrowRight':
                        e.preventDefault();
                        pan('right');
                        break;
                }}
            }});

            // Auto-focus container when image loads
            image.addEventListener('load', () => {{
                container.focus();
            }});

            // Focus container on click
            container.addEventListener('click', () => {{
                container.focus();
            }});

            // Visual feedback when focused
            container.addEventListener('focus', () => {{
                container.style.outline = '2px solid #3b82f6';
            }});
            container.addEventListener('blur', () => {{
                container.style.outline = 'none';
            }});
        }})();
        """)

    def _render_familysearch_viewer(self, familysearch_url: str) -> None:
        """Render FamilySearch viewer with open button.

        Args:
            familysearch_url: FamilySearch URL to display

        Note:
            FamilySearch blocks iframe embedding due to X-Frame-Options security policy.
            Users must open the link in a browser window.
        """
        # FamilySearch blocks iframe embedding, so show helpful UI instead (ultra compact for 35% column)
        with ui.column().classes('w-full h-full items-center justify-center gap-1 p-1'):
            # Icon
            ui.icon('open_in_browser', size='1.5rem').classes('text-blue-500')

            # Title only
            ui.label('Census Image Available').classes('text-xs font-semibold')

            # Very short explanation
            ui.label('Images cannot be embedded').classes('text-[10px] text-gray-600 text-center')
            ui.label('(Login required)').classes('text-[9px] text-gray-500 text-center italic')

            # Compact button
            ui.button(
                'OPEN IMAGE',
                icon='launch',
                on_click=lambda: ui.run_javascript(f"window.open('{familysearch_url}', '_blank')")
            ).props('color=primary dense size=sm').classes('text-[10px] px-2 py-1')

            # Minimal URL preview
            url_preview = '...' + familysearch_url[-30:] if len(familysearch_url) > 30 else familysearch_url
            ui.label(url_preview).classes('text-[8px] text-gray-400 font-mono break-all')

    def _notify_and_log(
        self,
        message: str,
        type: str = "info",
        source: str = "Batch Processing"
    ) -> None:
        """Display notification and log message.

        Args:
            message: Message text
            type: Notification type (info, positive, warning, negative)
            source: Source of message (default: "Batch Processing")
        """
        # Show notification to user
        ui.notify(message, type=type)

        # Log to message log
        message_type_map = {
            "info": MessageType.INFO,
            "positive": MessageType.POSITIVE,
            "warning": MessageType.WARNING,
            "negative": MessageType.NEGATIVE,
            "error": MessageType.ERROR,
        }
        log_type = message_type_map.get(type, MessageType.INFO)
        self.message_log.log(message, type=log_type, source=source)
