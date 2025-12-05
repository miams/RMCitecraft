"""Census Batch Transcription Tab for RMCitecraft.

Batch import of census data from FamilySearch based on RootsMagic sources.
Replaces the modal dialog approach with a dedicated tab.
"""

from loguru import logger
from nicegui import ui

from rmcitecraft.services.census_transcription_batch import (
    CensusTranscriptionBatchService,
    QueueItem,
    QueueStats,
    get_batch_service,
)


class CensusBatchTranscriptionTab:
    """Census Batch Transcription Tab component."""

    CENSUS_YEARS = [1950, 1940, 1930, 1920, 1910, 1900, 1890, 1880, 1870, 1860, 1850]

    def __init__(self) -> None:
        """Initialize census batch transcription tab."""
        self.batch_service: CensusTranscriptionBatchService | None = None
        self.batch_queue: list[QueueItem] = []
        self.batch_stats: QueueStats | None = None
        self.batch_selected: set[int] = set()  # Set of selected source IDs
        self.batch_processing: bool = False
        self.batch_session_id: str | None = None
        self.batch_sort_by: str = "location"  # "location" or "name"

    def render(self) -> None:
        """Render the census batch transcription tab."""
        with ui.column().classes("w-full p-4 gap-4"):
            # Header
            with ui.row().classes("w-full items-center gap-4"):
                ui.icon("playlist_add", size="2rem").classes("text-purple-600")
                ui.label("Census Batch Transcriptions").classes("text-2xl font-bold")
                ui.label("Import census data from FamilySearch for multiple sources").classes(
                    "text-gray-500"
                )

            # Filter and sort controls
            with ui.card().classes("w-full p-4"):
                with ui.row().classes("w-full items-center gap-4 flex-wrap"):
                    self._year_select = ui.select(
                        options={None: "All Years", **{y: str(y) for y in self.CENSUS_YEARS}},
                        value=None,
                        label="Census Year",
                    ).classes("w-32")

                    self._sort_select = ui.select(
                        options={
                            "location": "Sort by State, County",
                            "name": "Sort by Surname",
                        },
                        value="location",
                        label="Sort Order",
                        on_change=lambda e: self._on_sort_change(e.value),
                    ).classes("w-48")

                    ui.button(
                        "Load Queue", icon="refresh", on_click=self._load_batch_queue
                    ).props("color=primary")

                # Statistics display
                with ui.row().classes("w-full items-center gap-4 mt-2"):
                    self._stats_label = ui.label(
                        "Select a census year and click 'Load Queue' to begin"
                    ).classes("text-sm")

            # Main content - Queue and Progress side by side
            with ui.row().classes("w-full gap-4"):
                # Queue list (left side, 2/3 width)
                with ui.card().classes("w-2/3 p-4"):
                    ui.label("Sources to Import").classes("font-bold text-lg mb-2")

                    # Selection controls
                    with ui.row().classes("w-full items-center gap-2 mb-2 flex-wrap"):
                        ui.button(
                            "Select Next 10",
                            icon="add",
                            on_click=lambda: self._batch_select_next(10),
                        ).props("size=sm outline")
                        ui.button(
                            "Select Next 25",
                            icon="add",
                            on_click=lambda: self._batch_select_next(25),
                        ).props("size=sm outline")
                        ui.button(
                            "Select Next 100",
                            icon="add",
                            on_click=lambda: self._batch_select_next(100),
                        ).props("size=sm outline color=purple")
                        ui.button(
                            "Select All", icon="select_all", on_click=self._batch_select_all
                        ).props("size=sm outline")
                        ui.button(
                            "Deselect All", icon="deselect", on_click=self._batch_deselect_all
                        ).props("size=sm outline")

                        self._selected_label = ui.label("0 selected").classes(
                            "text-sm font-medium ml-auto"
                        )

                    # Offset controls for selecting records starting at an offset
                    with ui.row().classes("w-full items-center gap-2 mb-2"):
                        ui.label("Skip first:").classes("text-sm")
                        self._offset_input = ui.number(
                            value=0, min=0, step=10
                        ).props("dense outlined size=sm").classes("w-24")
                        ui.label("records").classes("text-sm text-gray-500")
                        ui.button(
                            "Apply Offset & Select 100",
                            icon="skip_next",
                            on_click=self._batch_select_with_offset,
                        ).props("size=sm outline color=secondary")

                    # Queue table
                    with ui.scroll_area().classes("h-[450px] w-full border rounded"):
                        self._queue_container = ui.column().classes("w-full gap-1 p-2")
                        with self._queue_container:
                            ui.label("Click 'Load Queue' to find sources").classes(
                                "text-gray-400 italic text-sm"
                            )

                # Progress and actions (right side, 1/3 width)
                with ui.card().classes("w-1/3 p-4"):
                    ui.label("Processing").classes("font-bold text-lg mb-2")

                    # Process button
                    self._process_btn = ui.button(
                        "Process Selected",
                        icon="play_arrow",
                        on_click=self._start_batch_processing,
                    ).props("color=purple").classes("w-full")
                    self._process_btn.disable()

                    # Progress section
                    self._progress_container = ui.column().classes("w-full mt-4")
                    with self._progress_container:
                        self._progress_bar = ui.linear_progress(value=0).classes("w-full")
                        self._progress_bar.set_visibility(False)
                        with ui.row().classes("w-full items-center gap-2"):
                            self._progress_spinner = ui.spinner(size="sm")
                            self._progress_spinner.set_visibility(False)
                            self._progress_text = ui.label("Ready to process").classes(
                                "text-sm text-gray-500"
                            )

                    # Edge warnings section
                    ui.label("Edge Warnings").classes("font-bold mt-4 mb-2")
                    with ui.scroll_area().classes("h-[200px] w-full border rounded"):
                        self._edge_warnings_container = ui.column().classes("w-full gap-1 p-2")
                        with self._edge_warnings_container:
                            ui.label("No warnings yet").classes("text-gray-400 italic text-sm")

    async def _load_batch_queue(self) -> None:
        """Load the batch queue from RootsMagic."""
        self._stats_label.set_text("Loading...")

        try:
            # Initialize batch service if needed
            if not self.batch_service:
                self.batch_service = get_batch_service()

            # Build queue with stats
            year_filter = self._year_select.value
            sort_by = self._sort_select.value
            self.batch_queue, self.batch_stats = await self.batch_service.build_transcription_queue(
                census_year=year_filter,
                sort_by=sort_by,
            )
            self.batch_selected.clear()

            # Update stats display
            year_str = str(year_filter) if year_filter else "All Years"
            self._stats_label.set_text(
                f"{year_str}: {self.batch_stats.total_sources} total sources | "
                f"{self.batch_stats.already_processed} already processed | "
                f"{self.batch_stats.remaining} remaining"
            )
            self._refresh_queue_display()

        except Exception as e:
            logger.error(f"Failed to load batch queue: {e}")
            self._stats_label.set_text(f"Error: {e}")
            ui.notify(f"Failed to load queue: {e}", type="negative")

    def _on_sort_change(self, sort_by: str) -> None:
        """Handle sort order change - re-sort the existing queue."""
        self.batch_sort_by = sort_by
        if self.batch_queue:
            if sort_by == "name":
                self.batch_queue.sort(key=lambda x: (x.surname.lower(), x.person_name.lower()))
            else:  # location
                self.batch_queue.sort(
                    key=lambda x: (x.state.lower(), x.county.lower(), x.surname.lower())
                )
            self._refresh_queue_display()

    def _batch_select_next(self, count: int) -> None:
        """Select the next N unselected items in the queue."""
        added = 0
        for item in self.batch_queue:
            if item.rmtree_citation_id not in self.batch_selected:
                self.batch_selected.add(item.rmtree_citation_id)
                added += 1
                if added >= count:
                    break
        self._refresh_queue_display()
        if added > 0:
            ui.notify(f"Selected {added} sources", type="info")

    def _batch_select_with_offset(self) -> None:
        """Select 100 items starting from the offset position."""
        offset = int(self._offset_input.value or 0)
        count = 100

        # Clear current selection
        self.batch_selected.clear()

        # Skip the first 'offset' items, then select 'count' items
        skipped = 0
        added = 0
        for item in self.batch_queue:
            if skipped < offset:
                skipped += 1
                continue
            self.batch_selected.add(item.rmtree_citation_id)
            added += 1
            if added >= count:
                break

        self._refresh_queue_display()
        if added > 0:
            ui.notify(f"Selected {added} sources starting at position {offset}", type="info")
        else:
            ui.notify(f"No sources found at offset {offset}", type="warning")

    def _batch_select_all(self) -> None:
        """Select all items in the queue."""
        for item in self.batch_queue:
            self.batch_selected.add(item.rmtree_citation_id)
        self._refresh_queue_display()

    def _batch_deselect_all(self) -> None:
        """Deselect all items."""
        self.batch_selected.clear()
        self._refresh_queue_display()

    def _refresh_queue_display(self) -> None:
        """Refresh the queue display."""
        self._queue_container.clear()

        with self._queue_container:
            if not self.batch_queue:
                ui.label("No unprocessed sources found matching filters").classes(
                    "text-gray-400 italic text-sm"
                )
                self._update_selection_count()
                return

            # Flat list display
            for item in self.batch_queue:
                self._render_queue_item(item)

        self._update_selection_count()

    def _render_queue_item(self, item: QueueItem) -> None:
        """Render a single queue item with checkbox."""
        is_selected = item.rmtree_citation_id in self.batch_selected

        with ui.card().classes(
            f"w-full p-2 {'bg-purple-50 border-purple-200' if is_selected else ''}"
        ), ui.row().classes("w-full items-center gap-2"):
            # Checkbox
            ui.checkbox(
                value=is_selected,
                on_change=lambda e, sid=item.rmtree_citation_id: self._toggle_selection(
                    sid, e.value
                ),
            )

            # Person info
            with ui.column().classes("flex-1"):
                ui.label(item.person_name).classes("font-medium text-sm")
                location = f"{item.county} Co., {item.state}" if item.county else item.state
                ui.label(location).classes("text-xs text-gray-500")

            # Census year badge - only show when "All Years" filter is selected
            if item.census_year and self._year_select.value is None:
                ui.badge(str(item.census_year), color="blue").classes("text-xs")

    def _toggle_selection(self, source_id: int, selected: bool) -> None:
        """Toggle selection of an item."""
        if selected:
            self.batch_selected.add(source_id)
        else:
            self.batch_selected.discard(source_id)
        self._update_selection_count()

    def _update_selection_count(self) -> None:
        """Update the selection count label."""
        count = len(self.batch_selected)
        self._selected_label.set_text(f"{count} selected")
        if count > 0:
            self._process_btn.enable()
        else:
            self._process_btn.disable()

    async def _start_batch_processing(self) -> None:
        """Start processing the selected batch items."""
        if not self.batch_selected:
            ui.notify("No items selected", type="warning")
            return

        if self.batch_processing:
            ui.notify("Batch processing already in progress", type="warning")
            return

        self.batch_processing = True
        self._process_btn.disable()
        self._progress_bar.set_visibility(True)
        self._progress_spinner.set_visibility(True)
        self._edge_warnings_container.clear()

        with self._edge_warnings_container:
            ui.label("Processing...").classes("text-gray-400 italic text-sm")

        # Filter queue to selected items
        selected_items = [
            item
            for item in self.batch_queue
            if item.rmtree_citation_id in self.batch_selected
        ]

        try:
            # Create session
            session_id = self.batch_service.create_session_from_queue(
                selected_items,
                census_year=self._year_select.value,
            )
            self.batch_session_id = session_id

            # Define progress callback
            def on_progress(completed: int, total: int, current_name: str) -> None:
                progress = completed / total if total > 0 else 0
                self._progress_bar.set_value(progress)
                self._progress_text.set_text(f"Processing {completed}/{total}: {current_name}")

            # Define edge warning callback
            edge_warnings_added = [0]  # Use list to allow mutation in nested function

            def on_edge_warning(message: str, item_data: dict) -> None:
                if edge_warnings_added[0] == 0:
                    self._edge_warnings_container.clear()
                edge_warnings_added[0] += 1
                with self._edge_warnings_container, ui.row().classes(
                    "items-center gap-1 text-xs"
                ):
                    ui.icon("warning", size="xs").classes("text-yellow-500")
                    ui.label(message).classes("text-yellow-700")

            # Run batch processing
            result = await self.batch_service.process_batch(
                session_id,
                on_progress=on_progress,
                on_edge_warning=on_edge_warning,
            )

            # Show results
            self._progress_text.set_text(
                f"Complete! {result.completed} imported, {result.errors} errors, "
                f"{result.skipped} skipped, {result.edge_warnings} edge warnings"
            )
            self._progress_spinner.set_visibility(False)

            if edge_warnings_added[0] == 0:
                self._edge_warnings_container.clear()
                with self._edge_warnings_container:
                    ui.label("No edge warnings").classes("text-gray-400 italic text-sm")

            ui.notify(
                f"Batch import complete: {result.completed} imported",
                type="positive" if result.errors == 0 else "warning",
            )

            # Reload the queue to reflect processed items
            await self._load_batch_queue()

        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            self._progress_text.set_text(f"Error: {e}")
            ui.notify(f"Batch processing failed: {e}", type="negative")

        finally:
            self.batch_processing = False
            self._process_btn.enable()
