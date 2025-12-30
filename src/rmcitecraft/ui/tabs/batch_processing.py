"""Batch Processing Tab for RMCitecraft.

This tab provides the batch citation processing interface with three panels:
- Left: Citation queue with status and filters
- Center: Data entry form for missing fields
- Right: Census image viewer

Implements robust batch processing architecture with:
- State persistence (CensusBatchStateRepository)
- Adaptive timeout management
- Retry strategy with exponential backoff
- Page health monitoring and crash recovery
- Six-phase processing loop
- Resume capability for interrupted batches
"""

import asyncio
import time
from datetime import datetime
from pathlib import Path

from loguru import logger
from nicegui import ui

from rmcitecraft.config import get_config
from rmcitecraft.database.census_batch_state_repository import CensusBatchStateRepository
from rmcitecraft.repositories import DatabaseConnection
from rmcitecraft.services.adaptive_timeout import AdaptiveTimeoutManager, TimingContext
from rmcitecraft.services.batch_processing import (
    BatchProcessingController,
    CitationBatchItem,
    BatchProcessingState,
    CitationStatus,
)
from rmcitecraft.services.familysearch_automation import (
    FamilySearchAutomation,
    CDPConnectionError,
)
from rmcitecraft.services.image_processing import get_image_processing_service
from rmcitecraft.services.message_log import get_message_log, MessageType
from rmcitecraft.services.page_health_monitor import (
    PageHealthMonitor,
    PageRecoveryManager,
)
from rmcitecraft.services.retry_strategy import RetryConfig, RetryStrategy
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

        # Robustness components (same pattern as Find a Grave)
        self._init_robustness_components()

        # State tracking for robustness
        self.current_session_id: str | None = None
        self.current_state_item_id: int | None = None
        self.checkpoint_counter = 0

        # State
        self.selected_census_year: int | None = None
        self.selected_citation_ids: set[int] = set()  # Track selected citations
        self.open_browser_tabs: bool = True  # Open new tab for each citation during extraction

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

    def _init_robustness_components(self) -> None:
        """Initialize robustness components for crash recovery and adaptive timeouts.

        These components are SEPARATE from Find a Grave and use census-specific
        tables and configuration settings.
        """
        # State repository for persistence (uses census_batch_* tables)
        try:
            self.state_repository = CensusBatchStateRepository(
                db_path=self.config.census_state_db_path
            )
            logger.info("Census batch state repository initialized")
        except (FileNotFoundError, RuntimeError) as e:
            # State DB doesn't exist yet or census tables not created
            # Will be created by FindAGraveBatchStateRepository when it runs migrations
            # (both share the same DB file)
            logger.warning(
                f"Census batch state repository not available: {e}. "
                "Run Find a Grave batch first to initialize migrations, "
                "or state tracking will be disabled."
            )
            self.state_repository = None

        # Page health monitor for crash detection
        self.health_monitor = PageHealthMonitor(health_check_timeout_ms=2000)
        self.recovery_manager = PageRecoveryManager(self.health_monitor)

        # Adaptive timeout manager for dynamic timeout adjustment
        self.timeout_manager = AdaptiveTimeoutManager(
            base_timeout_seconds=self.config.census_base_timeout_seconds,
            window_size=self.config.census_timeout_window_size,
        )

        # Retry strategy with exponential backoff
        self.retry_strategy = RetryStrategy(
            config=RetryConfig(
                max_retries=self.config.census_max_retries,
                base_delay_seconds=self.config.census_retry_base_delay_seconds,
            )
        )

    def _count_pending_exports(self) -> int:
        """Count total pending exports across all sessions in state database.

        Returns:
            Number of completed items with pending export status
        """
        if not self.state_repository:
            return 0

        try:
            count = 0
            all_sessions = self.state_repository.get_all_sessions()
            for session in all_sessions:
                items = self.state_repository.get_session_items(session["session_id"])
                count += sum(
                    1
                    for item in items
                    if item["status"] == "complete"
                    and item.get("export_status", "pending") == "pending"
                )
            return count
        except Exception as e:
            logger.warning(f"Error counting pending exports: {e}")
            return 0

    def _count_exported_items(self) -> int:
        """Count total exported items across all sessions in state database.

        Returns:
            Number of completed items with exported status
        """
        if not self.state_repository:
            return 0

        try:
            count = 0
            all_sessions = self.state_repository.get_all_sessions()
            for session in all_sessions:
                items = self.state_repository.get_session_items(session["session_id"])
                count += sum(
                    1
                    for item in items
                    if item["status"] == "complete" and item.get("export_status") == "exported"
                )
            return count
        except Exception as e:
            logger.warning(f"Error counting exported items: {e}")
            return 0

    def render(self) -> None:
        """Render the batch processing tab with sub-tabs."""
        with ui.column().classes("w-full h-full"):
            # Create sub-tabs for Batch Processing and Dashboard
            with ui.tabs().classes("w-full") as tabs:
                batch_tab = ui.tab("Batch Processing", icon="playlist_add_check")
                dashboard_tab = ui.tab("Dashboard", icon="dashboard")

            with ui.tab_panels(tabs, value=batch_tab).classes("w-full h-full"):
                # Tab 1: Batch Processing
                with ui.tab_panel(batch_tab).classes("w-full h-full"):
                    with ui.column().classes("w-full h-full gap-1 p-1"):
                        # Header with session controls (compact)
                        self._render_session_header()

                        # Three-panel layout container
                        with ui.row().classes(
                            "w-full flex-grow flex-nowrap gap-0"
                        ) as self.three_panel_container:
                            self._render_three_panels()

                        # Bottom status bar (only visible in Batch Processing)
                        with ui.row().classes(
                            "w-full items-center bg-gray-100 px-2 py-1 border-t"
                        ) as self.status_bar_container:
                            self._render_status_bar()

                        # Message log panel at bottom
                        self.message_log_panel = MessageLogPanel(self.message_log)
                        self.message_log_panel.render()

                # Tab 2: Census Dashboard
                with ui.tab_panel(dashboard_tab).classes("w-full h-full"):
                    self._render_census_dashboard()

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
        with ui.card().classes(
            "w-[35%] h-full flex-shrink-0 overflow-hidden p-1"
        ) as self.image_container:
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
                                on_click=lambda url=citation.familysearch_url: ui.run_javascript(
                                    f"window.open('{url}', '_blank')"
                                ),
                            ).props("flat dense").tooltip("Open in new tab")

                # Image viewer
                if self.controller.session.current_citation:
                    citation = self.controller.session.current_citation
                    # Show local image if available, otherwise show FamilySearch viewer
                    if citation.local_image_path:
                        self._render_local_image(
                            citation.local_image_path, citation.familysearch_url
                        )
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
                self.session_status_label = ui.label(self._get_session_status_text()).classes(
                    "text-sm text-gray-700 font-medium"
                )
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

                ui.button(
                    "Resume",
                    icon="replay",
                    on_click=self._show_resume_dialog,
                ).props("dense outline").tooltip("Resume interrupted session")

                ui.button(
                    icon="delete_sweep",
                    on_click=self._show_reset_state_db_dialog,
                ).props("dense flat color=orange").tooltip(
                    "Reset state DB (use after RootsMagic restore)"
                )

                # Check if there are pending exports in state DB (show Export even without active session)
                pending_export_count = self._count_pending_exports()
                if pending_export_count > 0 or self.controller.session:
                    ui.button(
                        f"Export ({pending_export_count})"
                        if pending_export_count > 0 and not self.controller.session
                        else "Export",
                        icon="save",
                        on_click=self._export_results,
                    ).props(
                        "dense outline color=green" if pending_export_count > 0 else "dense outline"
                    ).tooltip(
                        f"{pending_export_count} citations pending export"
                        if pending_export_count > 0
                        else "Export citations"
                    )

                if self.controller.session:
                    ui.button(
                        "Process",
                        icon="play_arrow",
                        on_click=self._start_batch_processing,
                    ).props("dense color=primary")

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
            year_select = (
                ui.select(
                    [1790 + (i * 10) for i in range(17)],  # 1790-1950
                    value=1920,
                )
                .props("outlined")
                .classes("w-full mb-4")
            )

            # Limit input
            ui.label("Number of Citations:").classes("font-medium mb-2")
            limit_input = (
                ui.number(
                    label="Limit",
                    value=10,
                    min=1,
                    max=1000,
                )
                .props("outlined")
                .classes("w-full mb-4")
            )

            # Offset input (for pagination)
            ui.label("Start at Entry # (Offset):").classes("font-medium mb-2")
            offset_input = (
                ui.number(
                    label="Offset",
                    value=0,
                    min=0,
                    max=10000,
                )
                .props("outlined")
                .classes("w-full mb-4")
            )

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
        self._notify_and_log(
            f"Loading {limit} citations for {census_year} census{offset_text}...", type="info"
        )

        try:
            # Import the find function from batch script
            from scripts.process_census_batch import find_census_citations

            # Find citations
            db_path = str(self.config.rm_database_path)
            result = find_census_citations(db_path, census_year, limit=limit, offset=offset)

            if not result["citations"]:
                self._notify_and_log(
                    f"No citations found for {census_year} census at offset {offset}",
                    type="warning",
                )
                return

            # Create batch session
            self.controller.create_session(census_year, result["citations"])

            # Clear any previous selections when loading new batch
            self.selected_citation_ids = set()

            # Provide feedback with explanation if count differs from requested
            examined = result["examined"]
            found = result["found"]
            excluded = result["excluded"]
            skipped_processed = result.get("skipped_processed", 0)

            if excluded > 0 or skipped_processed > 0:
                # Show which citations were excluded
                exclusion_reasons = []
                if excluded > 0:
                    exclusion_reasons.append(f"{excluded} without URLs")
                if skipped_processed > 0:
                    exclusion_reasons.append(f"{skipped_processed} already processed")
                exclusion_msg = ", ".join(exclusion_reasons)

                logger.info(
                    f"Examined {examined} citations, found {found} needing processing, excluded: {exclusion_msg}"
                )
                self._notify_and_log(
                    f"Loaded {found} citations (examined {examined}, excluded: {exclusion_msg})",
                    type="info",
                )
                # Log detailed explanation for message log
                if excluded > 0:
                    self.message_log.log_info(
                        f"To find excluded citations: Go to Citation Manager tab → Select census year filter → "
                        f"Look for citations with 'No URL' status",
                        source="Batch Processing - Info",
                    )
                if skipped_processed > 0:
                    self.message_log.log_info(
                        f"{skipped_processed} citations already have properly formatted Footnote, ShortFootnote, "
                        f"and Bibliography fields and were skipped.",
                        source="Batch Processing - Info",
                    )
                # Offer to show excluded citations
                with ui.dialog() as excluded_dialog, ui.card().classes("w-96"):
                    total_excluded = excluded + skipped_processed
                    ui.label(f"{total_excluded} Citations Excluded").classes(
                        "font-bold text-lg mb-2"
                    )

                    if excluded > 0:
                        ui.label(
                            f"{excluded} citations were skipped because they don't have FamilySearch URLs. "
                            "These citations cannot be processed automatically."
                        ).classes("text-sm mb-4")

                    if skipped_processed > 0:
                        ui.label(
                            f"{skipped_processed} citations were skipped because they are already properly processed "
                            "(Footnote ≠ ShortFootnote and all citation fields pass validation)."
                        ).classes("text-sm mb-4")

                    if excluded > 0:
                        ui.label("To find citations without URLs:").classes(
                            "font-semibold text-sm mb-2"
                        )
                        ui.label("1. Go to Citation Manager tab").classes("text-xs ml-4")
                        ui.label("2. Select census year filter").classes("text-xs ml-4")
                        ui.label("3. Look for citations with 'No URL' status").classes(
                            "text-xs ml-4"
                        )

                    ui.button("OK", on_click=excluded_dialog.close).props("color=primary").classes(
                        "mt-4"
                    )

                ui.button(
                    icon="info",
                    on_click=excluded_dialog.open,
                ).props("flat round dense").classes("text-blue-600").tooltip(
                    f"Why {total_excluded} excluded?"
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

    def _show_resume_dialog(self) -> None:
        """Show dialog to resume an interrupted batch session."""
        if not self.state_repository:
            ui.notify("State repository not available", type="warning")
            return

        # Get resumable sessions
        sessions = self.state_repository.get_resumable_sessions()

        if not sessions:
            ui.notify("No resumable sessions found", type="info")
            return

        with ui.dialog() as dialog, ui.card().classes("w-[600px]"):
            ui.label("Resume Census Batch Session").classes("font-bold text-lg mb-4")

            ui.label(
                "Select a session to resume. Sessions are saved automatically "
                "and can be resumed after crashes or pauses."
            ).classes("text-sm text-gray-600 mb-4")

            # Session table
            columns = [
                {
                    "name": "session_id",
                    "label": "Session ID",
                    "field": "session_id",
                    "align": "left",
                },
                {"name": "created", "label": "Created", "field": "created_at", "align": "left"},
                {"name": "status", "label": "Status", "field": "status", "align": "center"},
                {"name": "progress", "label": "Progress", "field": "progress", "align": "center"},
                {"name": "year", "label": "Census Year", "field": "census_year", "align": "center"},
            ]

            rows = []
            for s in sessions:
                total = s["total_items"]
                completed = s["completed_count"]
                progress = f"{completed}/{total}" if total > 0 else "0/0"
                rows.append(
                    {
                        "session_id": s["session_id"],
                        "created_at": s["created_at"][:19] if s["created_at"] else "N/A",
                        "status": s["status"],
                        "progress": progress,
                        "census_year": s["census_year"] or "All",
                    }
                )

            table = ui.table(
                columns=columns,
                rows=rows,
                row_key="session_id",
                selection="single",
            ).classes("w-full")

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dialog.close).props("flat")

                async def resume_selected():
                    selected = table.selected
                    if selected:
                        session_id = selected[0]["session_id"]
                        dialog.close()
                        await self._resume_session(session_id)

                ui.button(
                    "Resume",
                    icon="play_arrow",
                    on_click=resume_selected,
                ).props("color=primary")

        dialog.open()

    async def _resume_session(self, session_id: str) -> None:
        """Resume a batch session from the state database.

        Args:
            session_id: Session ID to resume
        """
        if not self.state_repository:
            ui.notify("State repository not available", type="warning")
            return

        # Get session info
        session = self.state_repository.get_session(session_id)
        if not session:
            ui.notify(f"Session {session_id} not found", type="negative")
            return

        # Get incomplete items
        items = self.state_repository.get_session_items(session_id)
        incomplete_items = [
            item
            for item in items
            if item["status"] not in ("complete", "extracted", "created_citation")
        ]

        if not incomplete_items:
            ui.notify("All items in session are complete", type="info")
            return

        # Set current session ID for state tracking
        self.current_session_id = session_id

        # Load citations for incomplete items
        census_year = session.get("census_year")
        self._notify_and_log(
            f"Resuming session {session_id}: {len(incomplete_items)} items remaining", type="info"
        )

        # Create a new controller session from incomplete items
        # (This requires loading the citations from RootsMagic again)
        from scripts.process_census_batch import find_census_citations

        db_path = str(self.config.rm_database_path)
        person_ids = [item["person_id"] for item in incomplete_items]

        # If no session-level census_year, get unique years from incomplete items
        if not census_year:
            census_years = list(
                set(item["census_year"] for item in incomplete_items if item.get("census_year"))
            )
            if not census_years:
                ui.notify("Cannot determine census years from session items", type="warning")
                return
            logger.info(f"Session has no census year filter, found years in items: {census_years}")
        else:
            census_years = [census_year]

        # Find citations for these specific person IDs across all relevant years
        all_citations = []
        for year in census_years:
            result = find_census_citations(
                db_path,
                year,
                limit=len(incomplete_items) + 100,  # Get extra to account for completed ones
            )
            if result["citations"]:
                all_citations.extend(result["citations"])

        if all_citations:
            # Filter to only incomplete items
            citations_to_process = [c for c in all_citations if c["person_id"] in person_ids]

            if citations_to_process:
                # Use first census year for display, or None for mixed years
                display_year = census_year if census_year else None
                self.controller.create_session(display_year, citations_to_process)
                self.selected_citation_ids = set()
                self._refresh_all_panels()
                self._notify_and_log(
                    f"Loaded {len(citations_to_process)} citations for resume", type="positive"
                )
            else:
                ui.notify("No matching citations found to resume", type="warning")
        else:
            ui.notify("No citations found for the session's census year(s)", type="warning")

    def _show_reset_state_db_dialog(self) -> None:
        """Show confirmation dialog to reset the census state database."""
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label("Reset Census State Database").classes(
                "font-bold text-lg text-orange-600 mb-4"
            )

            ui.label("This will delete ALL census batch state data including:").classes(
                "font-medium mb-2"
            )

            with ui.column().classes("ml-4 mb-4 text-sm text-gray-700"):
                ui.label("• All census batch sessions")
                ui.label("• All census batch item tracking")
                ui.label("• All census checkpoints")
                ui.label("• All census performance metrics")

            ui.label(
                "Use this after restoring the RootsMagic database from backup "
                "when the state database is out of sync."
            ).classes("text-sm text-gray-600 italic mb-4")

            ui.label("This does NOT affect Find a Grave batch state data.").classes(
                "text-sm font-medium text-blue-600 mb-4"
            )

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button(
                    "Reset",
                    icon="delete_sweep",
                    on_click=lambda: self._reset_state_db(dialog),
                ).props("color=orange")

        dialog.open()

    def _reset_state_db(self, dialog: ui.dialog) -> None:
        """Reset the census state database.

        Args:
            dialog: Dialog to close after reset
        """
        dialog.close()

        if not self.state_repository:
            ui.notify("State repository not available", type="warning")
            return

        try:
            count = self.state_repository.clear_all_sessions()
            self.current_session_id = None
            self.current_state_item_id = None
            self.checkpoint_counter = 0

            self._notify_and_log(
                f"Census state database reset: {count} sessions deleted", type="positive"
            )
        except Exception as e:
            logger.error(f"Failed to reset state database: {e}")
            self._notify_and_log(f"Error resetting state database: {e}", type="negative")

    async def _start_batch_processing(self) -> None:
        """Start automated batch processing of loaded citations.

        Implements six-phase processing with robustness components:
        - Phase 1: Page health check
        - Phase 2: Already extracted check
        - Phase 3: Extraction with retry & adaptive timeout
        - Phase 4: Image download
        - Phase 5: Status update & checkpoint
        - Phase 6: Metrics recording

        Behavior:
        - If citations are selected (checked): process only selected citations
        - If no selections: process all incomplete citations
        """
        if not self.controller.session:
            self._notify_and_log("No batch session loaded", type="warning")
            return

        # Get citations in queue display order (respects current sort setting)
        queue_ordered_citations = self._get_queue_ordered_citations()

        # Check if user has selected specific citations
        if self.selected_citation_ids:
            # Process only selected citations, maintaining queue order
            citations_to_process = [
                c for c in queue_ordered_citations if c.citation_id in self.selected_citation_ids
            ]
            self._notify_and_log(
                f"Processing {len(citations_to_process)} selected citations...", type="info"
            )
        else:
            # No selections - process all incomplete citations in queue order
            # Exclude complete and error items (they don't need processing)
            excluded_statuses = ["complete", "error"]
            citations_to_process = [
                c for c in queue_ordered_citations if c.status.value not in excluded_statuses
            ]

            # Log what we're skipping for transparency
            complete_count = sum(1 for c in queue_ordered_citations if c.status.value == "complete")
            error_count = sum(1 for c in queue_ordered_citations if c.status.value == "error")
            if complete_count > 0 or error_count > 0:
                logger.info(f"Skipping {complete_count} complete and {error_count} error citations")

            self._notify_and_log(
                f"Processing {len(citations_to_process)} incomplete citations "
                f"(skipping {complete_count} complete, {error_count} errors)...",
                type="info",
            )

        if not citations_to_process:
            self._notify_and_log("No citations to process", type="warning")
            return

        # Create session in state database for persistence/resume
        self._create_state_session(citations_to_process)

        # Create progress dialog with detailed status
        with ui.dialog().props("persistent") as progress_dialog, ui.card().classes("w-96"):
            ui.label("Census Batch Processing").classes("text-lg font-bold mb-4")

            progress_label = ui.label("Starting...").classes("text-sm mb-2")
            with ui.row().classes("w-full items-center gap-2"):
                progress_bar = (
                    ui.linear_progress(value=0, show_value=False)
                    .props("instant-feedback")
                    .classes("flex-grow")
                )
                progress_pct = ui.label("0.0%").classes("text-sm font-medium w-16 text-right")

            status_label = ui.label("").classes("text-xs text-gray-600 mt-2")
            health_label = ui.label("").classes("text-xs text-blue-600 mt-1")

            with ui.row().classes("gap-2 mt-4"):
                ui.button("Pause", on_click=lambda: self._pause_batch_processing()).props("flat")

        progress_dialog.open()

        # Mark session as started
        if self.state_repository and self.current_session_id:
            self.state_repository.start_session(self.current_session_id)

        processed = 0
        errors = 0
        skipped = 0
        total = len(citations_to_process)

        for i, citation in enumerate(citations_to_process, 1):
            # Update progress
            progress_label.text = f"Processing {i} of {total}: {citation.full_name}"
            pct = (i / total) * 100
            progress_bar.value = i / total
            progress_pct.text = f"{pct:.1f}%"
            status_label.text = f"{processed} completed, {errors} errors, {skipped} skipped"

            start_time = time.time()
            result = "error"  # Default to error, will be updated on success

            try:
                result = await self._process_single_citation_robust(
                    citation, health_label, status_label
                )

                if result == "processed":
                    processed += 1
                elif result == "skipped":
                    skipped += 1
                elif result == "error":
                    errors += 1
                elif result == "connection_error":
                    # Browser connection lost - stop batch processing
                    errors += 1
                    logger.error("Stopping batch: browser connection lost")
                    ui.notify(
                        "Batch stopped: Browser connection lost. "
                        "Please check Chrome is running and click 'Reconnect'.",
                        type="negative",
                        timeout=10000,
                    )
                    break  # Exit the processing loop

                # Refresh queue component only (don't destroy/recreate UI)
                if self.queue_component:
                    self.queue_component.refresh()

            except Exception as e:
                logger.error(f"Error processing citation {citation.citation_id}: {e}")
                self.controller.mark_citation_error(citation, str(e))
                result = "error"  # Ensure result is set for metrics
                errors += 1

                # Record error in state DB
                if self.state_repository and self.current_state_item_id:
                    self.state_repository.update_item_status(
                        self.current_state_item_id, "error", str(e)
                    )

            # Record metrics
            duration_ms = int((time.time() - start_time) * 1000)
            if self.state_repository and self.current_session_id:
                self.state_repository.record_metric(
                    operation="citation_creation",
                    duration_ms=duration_ms,
                    success=(result == "processed"),
                    session_id=self.current_session_id,
                )

            # Update session counts
            if self.state_repository and self.current_session_id:
                self.state_repository.update_session_counts(
                    self.current_session_id,
                    completed_count=processed,
                    error_count=errors,
                )

            # Small delay to allow UI update
            await asyncio.sleep(0.1)

        # Close progress dialog
        progress_dialog.close()

        # Mark session as completed
        if self.state_repository and self.current_session_id:
            self.state_repository.complete_session(self.current_session_id)

        # Show completion message
        self._notify_and_log(
            f"Batch processing complete! {processed} processed, {errors} errors, {skipped} skipped",
            type="positive",
        )

        # Refresh queue component (don't destroy/recreate entire UI)
        if self.queue_component:
            self.queue_component.refresh()

        # Refresh form if a citation is selected
        if self.controller.session and self.controller.session.current_citation:
            self._refresh_form_panel()

    def _create_state_session(self, citations: list[CitationBatchItem]) -> None:
        """Create a session in the state database for persistence/resume.

        Args:
            citations: List of citations to process
        """
        if not self.state_repository:
            logger.warning("State repository not available, skipping state tracking")
            return

        # Generate session ID
        self.current_session_id = f"census_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Get census year if filtering by year
        census_year = self.selected_census_year

        # Create session
        self.state_repository.create_session(
            session_id=self.current_session_id,
            total_items=len(citations),
            census_year=census_year,
            config_snapshot={
                "base_timeout": self.config.census_base_timeout_seconds,
                "max_retries": self.config.census_max_retries,
                "adaptive_timeout": self.config.census_enable_adaptive_timeout,
            },
        )

        # Create items for each citation (using citation_id for unique tracking)
        for citation in citations:
            self.state_repository.create_item(
                session_id=self.current_session_id,
                person_id=citation.person_id,
                person_name=citation.full_name,
                census_year=citation.census_year,
                state=citation.extracted_data.get("state") if citation.extracted_data else None,
                county=citation.extracted_data.get("county") if citation.extracted_data else None,
                citation_id=citation.citation_id,
                source_id=citation.source_id,
            )

        logger.info(
            f"Created census batch session {self.current_session_id} with {len(citations)} items"
        )

    def _get_queue_ordered_citations(self) -> list[CitationBatchItem]:
        """Get citations in the same order as displayed in the queue.

        Uses the queue component's sort setting to maintain consistent ordering
        between queue display and batch processing.

        Returns:
            List of citations in queue display order
        """
        if not self.controller.session:
            return []

        citations = self.controller.session.citations

        # Get sort setting from queue component (default to "name" if not available)
        sort_by = "name"
        if self.queue_component:
            sort_by = getattr(self.queue_component, "sort_by", "name")

        # Apply same sorting as queue component
        if sort_by == "name":
            return sorted(citations, key=lambda c: c.full_name)
        elif sort_by == "status":
            # Sort by status priority: ERROR, MANUAL_REVIEW, QUEUED, COMPLETE
            status_priority = {
                CitationStatus.ERROR: 0,
                CitationStatus.MANUAL_REVIEW: 1,
                CitationStatus.QUEUED: 2,
                CitationStatus.EXTRACTING: 3,
                CitationStatus.EXTRACTED: 4,
                CitationStatus.COMPLETE: 5,
            }
            return sorted(citations, key=lambda c: status_priority.get(c.status, 99))

        return citations

    def _pause_batch_processing(self) -> None:
        """Pause the current batch processing session."""
        if self.state_repository and self.current_session_id:
            self.state_repository.pause_session(self.current_session_id)
            self._notify_and_log("Batch processing paused", type="info")

    async def _process_single_citation_robust(
        self,
        citation: CitationBatchItem,
        health_label: ui.label,
        status_label: ui.label,
    ) -> str:
        """Process a single citation using six-phase robust processing.

        Args:
            citation: Citation to process
            health_label: UI label for health status
            status_label: UI label for status messages

        Returns:
            "processed", "skipped", or "error"
        """
        # Get or create state item ID
        if self.state_repository and self.current_session_id:
            items = self.state_repository.get_session_items(self.current_session_id)
            for item in items:
                if (
                    item["person_id"] == citation.person_id
                    and item["census_year"] == citation.census_year
                ):
                    self.current_state_item_id = item["id"]
                    break

        # Safety check: skip citations that are already complete
        if citation.status.value == "complete":
            logger.debug(f"Citation {citation.citation_id} already complete, skipping")
            return "skipped"

        # ===== PHASE 1: PAGE HEALTH CHECK =====
        if self.config.census_enable_crash_recovery:
            health_label.text = "Checking page health..."

            try:
                page = await self.familysearch_automation.get_or_create_page()
            except CDPConnectionError as e:
                # Browser connection lost during health check
                logger.error(f"Browser connection lost during health check: {e}")
                self.controller.mark_citation_error(citation, f"Browser connection lost: {e}")
                if self.state_repository and self.current_state_item_id:
                    self.state_repository.update_item_status(
                        self.current_state_item_id, "error", f"Browser connection lost: {e}"
                    )
                return "connection_error"

            if page:
                health = await self.health_monitor.check_page_health(page)

                if not health.is_healthy:
                    health_label.text = f"Page unhealthy: {health.error}"
                    logger.warning(f"Page health check failed: {health.error}")

                    # Attempt recovery
                    recovered_page = await self.recovery_manager.attempt_recovery(
                        page, self.familysearch_automation
                    )
                    if not recovered_page:
                        self.controller.mark_citation_error(
                            citation, f"Page recovery failed: {health.error}"
                        )
                        if self.state_repository and self.current_state_item_id:
                            self.state_repository.update_item_status(
                                self.current_state_item_id, "error", f"Page crash: {health.error}"
                            )
                        return "error"
                else:
                    health_label.text = "Page healthy"

        # ===== PHASE 2: ALREADY EXTRACTED CHECK =====
        status_label.text = "Checking extraction status..."

        if citation.extracted_data and citation.extracted_data.get("extraction_complete"):
            logger.debug(f"Citation {citation.citation_id} already extracted, skipping extraction")
            # Skip to image download if needed
            if not citation.has_existing_media:
                await self._download_citation_image(citation)
            return "skipped"

        # Check for missing URL
        if not citation.familysearch_url:
            self.controller.mark_citation_error(citation, "No FamilySearch URL available")
            if self.state_repository and self.current_state_item_id:
                self.state_repository.update_item_status(
                    self.current_state_item_id, "error", "No FamilySearch URL"
                )
            return "error"

        # Update state to extracting
        if self.state_repository and self.current_state_item_id:
            self.state_repository.update_item_status(self.current_state_item_id, "extracting")

        # ===== PHASE 3: EXTRACTION WITH RETRY & ADAPTIVE TIMEOUT =====
        status_label.text = "Extracting citation data..."

        # Get adaptive timeout
        timeout = self.timeout_manager.get_current_timeout()
        logger.debug(f"Using adaptive timeout: {timeout}s")

        retry_count = 0
        extracted_data = None

        while retry_count <= self.config.census_max_retries:
            try:
                start_time = time.time()

                # Time the extraction
                with TimingContext(self.timeout_manager, "familysearch_extraction"):
                    extracted_data = await self.familysearch_automation.extract_citation_data(
                        citation.familysearch_url, census_year=citation.census_year
                    )

                if extracted_data:
                    # Record successful extraction time
                    duration = time.time() - start_time
                    self.timeout_manager.record_response_time(duration, success=True)

                    if self.state_repository and self.current_session_id:
                        self.state_repository.record_metric(
                            operation="extraction",
                            duration_ms=int(duration * 1000),
                            success=True,
                            session_id=self.current_session_id,
                        )
                    break

            except CDPConnectionError as e:
                # Browser connection failed - stop batch processing immediately
                # Don't retry, don't continue to next item
                logger.error(f"Browser connection lost: {e}")
                self.controller.mark_citation_error(citation, f"Browser connection lost: {e}")
                if self.state_repository and self.current_state_item_id:
                    self.state_repository.update_item_status(
                        self.current_state_item_id, "error", f"Browser connection lost: {e}"
                    )
                # Return special status to signal caller to stop batch
                return "connection_error"

            except Exception as e:
                retry_count += 1
                logger.warning(f"Extraction attempt {retry_count} failed: {e}")

                # Check if should retry
                if self.retry_strategy.should_retry(e, retry_count - 1):
                    delay = self.retry_strategy.get_delay(retry_count - 1)
                    status_label.text = (
                        f"Retry {retry_count}/{self.config.census_max_retries} in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)

                    # Increment retry count in state DB
                    if self.state_repository and self.current_state_item_id:
                        self.state_repository.increment_retry_count(self.current_state_item_id)
                else:
                    # Non-retryable error
                    self.controller.mark_citation_error(citation, f"Extraction failed: {e}")
                    if self.state_repository and self.current_state_item_id:
                        self.state_repository.update_item_status(
                            self.current_state_item_id, "error", str(e)
                        )
                    return "error"

        if not extracted_data:
            self.controller.mark_citation_error(
                citation, "Failed to extract citation data after retries"
            )
            if self.state_repository and self.current_state_item_id:
                self.state_repository.update_item_status(
                    self.current_state_item_id, "error", "Extraction failed after retries"
                )
            return "error"

        # Update citation with extracted data
        self.controller.update_citation_extracted_data(citation, extracted_data)

        # Update state with extracted data
        if self.state_repository and self.current_state_item_id:
            self.state_repository.update_item_extraction(
                self.current_state_item_id,
                extracted_data,
            )

        # Open new browser tab for this citation if enabled
        if self.open_browser_tabs and citation.familysearch_url:
            await self.familysearch_automation.open_new_tab(citation.familysearch_url)

        # ===== PHASE 4: IMAGE DOWNLOAD =====
        status_label.text = "Downloading census image..."

        if not citation.has_existing_media:
            if self.state_repository and self.current_state_item_id:
                self.state_repository.update_item_status(
                    self.current_state_item_id, "downloading_images"
                )
            await self._download_citation_image(citation)

        # ===== PHASE 5: STATUS UPDATE =====
        status_label.text = "Updating status..."

        # Status already set by controller.update_citation_extracted_data():
        # - COMPLETE if validation passed
        # - Keeps current status if validation failed (needs manual review)

        # ===== PHASE 6: CHECKPOINT =====
        self.checkpoint_counter += 1
        if (
            self.state_repository
            and self.current_session_id
            and self.current_state_item_id
            and self.checkpoint_counter >= self.config.census_checkpoint_frequency
        ):
            self.state_repository.create_checkpoint(
                self.current_session_id,
                self.current_state_item_id,
                citation.person_id,
            )
            self.checkpoint_counter = 0
            logger.debug(f"Created checkpoint at item {self.current_state_item_id}")

        # Mark complete in state DB ONLY if validation passed.
        #
        # IMPORTANT: If validation failed (e.g., FamilySearch URL didn't render properly,
        # resulting in missing required fields like state, county, ED, etc.), we should
        # NOT mark the item as 'complete'. This allows it to be reprocessed in subsequent
        # batches after the underlying issue is fixed.
        #
        # Citation status values:
        #   - COMPLETE: All required fields extracted and validated successfully
        #   - MANUAL_REVIEW: Extraction ran but validation failed (missing fields)
        #
        if self.state_repository and self.current_state_item_id:
            if citation.status == CitationStatus.COMPLETE:
                self.state_repository.update_item_status(self.current_state_item_id, "complete")
                logger.info(f"Citation {citation.citation_id} marked complete - validation passed")
            else:
                # Keep status as 'extracted' so it can be reprocessed
                self.state_repository.update_item_status(
                    self.current_state_item_id,
                    "extracted",
                    f"Validation failed: {', '.join(citation.validation.errors) if citation.validation else 'Unknown'}",
                )
                logger.warning(
                    f"Citation {citation.citation_id} NOT marked complete - validation failed: "
                    f"{citation.validation.errors if citation.validation else 'No validation result'}"
                )

        # Reset recovery counter on success
        self.recovery_manager.reset_recovery_counter()

        return "processed"

    async def _process_single_citation(self, citation: CitationBatchItem) -> None:
        """Process a single citation (legacy method for backwards compatibility).

        This method is kept for backwards compatibility but delegates to the
        robust processing method.

        Args:
            citation: Citation to process
        """
        # Create a dummy label for the robust method
        with ui.label("") as health_label, ui.label("") as status_label:
            await self._process_single_citation_robust(citation, health_label, status_label)

    async def _download_citation_image(self, citation: CitationBatchItem) -> None:
        """Download census image for manual entry.

        Args:
            citation: Citation that needs an image
        """
        # Get image viewer URL from extracted data
        image_viewer_url = citation.extracted_data.get("image_viewer_url")

        if not image_viewer_url:
            logger.warning(
                f"No image viewer URL for citation {citation.citation_id}, cannot download image"
            )
            return

        try:
            # Create temp directory for downloaded images if it doesn't exist
            from pathlib import Path

            temp_dir = Path.home() / ".rmcitecraft" / "temp_images"
            temp_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename: YYYY_State_County_Surname_Given_CitationID.jpg
            census_year = citation.census_year
            state = citation.extracted_data.get("state", "Unknown")
            county = citation.extracted_data.get("county", "Unknown")
            surname = citation.surname
            given = citation.given_name
            cit_id = citation.citation_id

            # Sanitize filename components
            def sanitize(s: str) -> str:
                """Remove illegal filename characters."""
                return "".join(c for c in s if c.isalnum() or c in (" ", "-", "_")).strip()

            filename = f"{census_year}_{sanitize(state)}_{sanitize(county)}_{sanitize(surname)}_{sanitize(given)}_cit{cit_id}.jpg"
            download_path = temp_dir / filename

            logger.info(
                f"Downloading census image for citation {citation.citation_id} to {download_path}"
            )

            # Download the image using the image viewer URL (not the record URL)
            success = await self.familysearch_automation.download_census_image(
                image_viewer_url, download_path
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
        """Export batch processing results to database and organize image files.

        This function exports from TWO sources:
        1. In-memory session (current citations being processed)
        2. State database (ALL sessions with pending exports, not just current)
        """
        # CRITICAL: Sync any pending form data before export
        # NiceGUI's on_change fires on blur/Enter, so if user typed and clicked Export
        # without losing focus, the data might not be synced to the citation yet.
        if self.form_component:
            self.form_component.sync_form_data()

        # Check in-memory session - only include items updated THIS session
        # This prevents re-exporting citations that were already complete when loaded
        in_memory_citations = []
        if self.controller.session:
            in_memory_citations = [
                c
                for c in self.controller.session.citations
                if c.is_complete and c.updated_this_session
            ]

        # Get citation IDs from in-memory session to avoid double-counting
        in_memory_citation_ids = {c.citation_id for c in in_memory_citations}

        # Check state database for ALL completed items with pending export across ALL sessions
        state_db_only_count = 0
        sessions_with_pending = []
        if self.state_repository:
            all_sessions = self.state_repository.get_all_sessions()
            for session in all_sessions:
                session_id = session["session_id"]
                items = self.state_repository.get_session_items(session_id)
                pending_items = [
                    item
                    for item in items
                    if item["status"] == "complete"
                    and item.get("export_status", "pending") == "pending"
                    and item.get("citation_id") not in in_memory_citation_ids
                ]
                if pending_items:
                    sessions_with_pending.append(
                        {
                            "session_id": session_id,
                            "count": len(pending_items),
                            "census_year": session.get("census_year"),
                        }
                    )
                    state_db_only_count += len(pending_items)

        total_to_export = len(in_memory_citations) + state_db_only_count

        if total_to_export == 0:
            self._notify_and_log("No completed citations to export", type="warning")
            return

        # Confirm export with details about both sources
        with ui.dialog() as confirm_dialog, ui.card().classes("w-[450px]"):
            ui.label("Export Citations to Database").classes("text-lg font-bold mb-2")
            ui.label(f"Total citations to export: {total_to_export}").classes("mb-2 font-semibold")

            if len(in_memory_citations) > 0:
                ui.label(f"  • Current session (in memory): {len(in_memory_citations)}").classes(
                    "text-sm ml-4"
                )

            if sessions_with_pending:
                ui.label(f"  • From state database: {state_db_only_count}").classes("text-sm ml-4")
                # Show breakdown by session
                for sess in sessions_with_pending[:5]:  # Show max 5 sessions
                    year_str = f" ({sess['census_year']})" if sess.get("census_year") else ""
                    ui.label(
                        f"      - {sess['session_id'][-15:]}{year_str}: {sess['count']}"
                    ).classes("text-xs ml-8 text-gray-600")
                if len(sessions_with_pending) > 5:
                    ui.label(
                        f"      ... and {len(sessions_with_pending) - 5} more sessions"
                    ).classes("text-xs ml-8 text-gray-500 italic")

            ui.label("Census images will be renamed and moved to their final locations.").classes(
                "mb-4 mt-2"
            )

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=confirm_dialog.close).props("flat")
                # Call export directly (not as background task) to maintain UI context
                ui.button(
                    "Export",
                    on_click=lambda: self._do_export_all(
                        confirm_dialog, in_memory_citations, sessions_with_pending
                    ),
                ).props("color=primary")

        confirm_dialog.open()

    async def _do_export_all(
        self,
        dialog,
        in_memory_citations: list[CitationBatchItem],
        sessions_with_pending: list[dict],
    ) -> None:
        """Export citations from both in-memory session and state database.

        This method handles the case where a large batch was processed, the session
        was disconnected, and then resumed. The completed items from before the
        disconnect are only in the state database (not in memory), so we need to
        export from both sources.

        Args:
            dialog: Confirmation dialog to close
            in_memory_citations: Citations completed in the current in-memory session
            sessions_with_pending: List of session dicts with pending exports
        """
        dialog.close()

        # First export in-memory citations
        if in_memory_citations:
            await self._do_export_internal(in_memory_citations, "current session")

        # Then export state database items from all sessions with pending exports
        if sessions_with_pending and self.state_repository:
            # Get citation IDs from in-memory to avoid double-exporting
            in_memory_citation_ids = {c.citation_id for c in in_memory_citations}
            await self._export_from_state_db_all_sessions(
                sessions_with_pending, in_memory_citation_ids
            )

    async def _export_from_state_db(self) -> None:
        """Export completed items from the state database that aren't in the current session.

        This method reloads citation data from RootsMagic for items that were completed
        in a previous session (before disconnect/resume) and exports them.
        """
        if not self.state_repository or not self.current_session_id:
            return

        from scripts.process_census_batch import find_census_citations

        # Get all completed items from state DB
        items = self.state_repository.get_session_items(self.current_session_id)
        completed_items = [
            item
            for item in items
            if item["status"] == "complete" and item.get("export_status", "pending") == "pending"
        ]

        if not completed_items:
            return

        # Get citation IDs from in-memory session to exclude
        in_memory_citation_ids = set()
        if self.controller.session:
            in_memory_citation_ids = {c.citation_id for c in self.controller.session.citations}

        # Filter to only items not in memory
        items_to_export = [
            item
            for item in completed_items
            if item.get("citation_id") not in in_memory_citation_ids
        ]

        if not items_to_export:
            self._notify_and_log("All state DB items already in memory session", type="info")
            return

        self._notify_and_log(
            f"Exporting {len(items_to_export)} additional items from state database...", type="info"
        )

        # Show progress dialog
        with ui.dialog() as progress_dialog, ui.card().classes("p-6"):
            ui.label("Exporting from State Database...").classes("text-lg font-bold mb-4")
            progress_label = ui.label("Loading citation data...").classes("mb-2")
            progress_bar = ui.linear_progress(value=0).classes("mb-4")

        progress_dialog.open()

        exported_count = 0
        errors = []

        try:
            # Load and export each item
            db_path = str(self.config.rm_database_path)

            for i, item in enumerate(items_to_export):
                try:
                    progress_label.text = f"Processing {item.get('person_name', 'Unknown')} ({i + 1}/{len(items_to_export)})"
                    progress_bar.value = i / len(items_to_export)
                    await ui.context.client.connected()

                    # Load the citation from RootsMagic using stored extracted_data
                    citation_id = item.get("citation_id")
                    person_id = item.get("person_id")
                    census_year = item.get("census_year")
                    extracted_data_json = item.get("extracted_data")

                    if not citation_id or not extracted_data_json:
                        errors.append(
                            f"{item.get('person_name', 'Unknown')}: Missing citation_id or extracted_data"
                        )
                        continue

                    # Parse stored extracted data
                    import json

                    try:
                        extracted_data = (
                            json.loads(extracted_data_json)
                            if isinstance(extracted_data_json, str)
                            else extracted_data_json
                        )
                    except json.JSONDecodeError:
                        errors.append(
                            f"{item.get('person_name', 'Unknown')}: Invalid JSON in extracted_data"
                        )
                        continue

                    # Reload full citation data from database
                    result = find_census_citations(db_path, census_year, limit=1000)
                    matching_citation = None
                    for cit in result.get("citations", []):
                        if cit.get("citation_id") == citation_id:
                            matching_citation = cit
                            break

                    if not matching_citation:
                        errors.append(
                            f"{item.get('person_name', 'Unknown')}: Citation {citation_id} not found in database"
                        )
                        continue

                    # Create CitationBatchItem from the loaded data
                    given_name = matching_citation["given_name"]
                    surname = matching_citation["surname"]
                    full_name = f"{given_name} {surname}".strip()

                    batch_item = CitationBatchItem(
                        person_id=matching_citation["person_id"],
                        event_id=matching_citation["event_id"],
                        citation_id=matching_citation["citation_id"],
                        source_id=matching_citation["source_id"],
                        surname=surname,
                        given_name=given_name,
                        full_name=full_name,
                        census_year=census_year,
                        source_name=matching_citation.get("source_name", ""),
                        familysearch_url=matching_citation.get("familysearch_url"),
                    )

                    # Apply the stored extracted data
                    batch_item.extracted_data = extracted_data
                    batch_item.status = CitationStatus.COMPLETE

                    # Generate formatted citations
                    from rmcitecraft.services.citation_formatter import CensusFootnoteFormatter

                    formatter = CensusFootnoteFormatter()
                    merged = batch_item.merged_data
                    batch_item.footnote = formatter.format_footnote(merged)
                    batch_item.short_footnote = formatter.format_short_footnote(merged)
                    batch_item.bibliography = formatter.format_bibliography(merged)

                    # Write to database
                    await self._write_citation_to_database(batch_item)

                    # Mark as exported in state DB (using a custom update)
                    self.state_repository.mark_item_exported(item["id"])

                    exported_count += 1

                except Exception as e:
                    logger.error(f"Error exporting state DB item {item.get('id')}: {e}")
                    errors.append(f"{item.get('person_name', 'Unknown')}: {str(e)}")

            # Checkpoint database
            progress_label.text = "Checkpointing database..."
            progress_bar.value = 1.0

            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")

            progress_dialog.close()

            # Report results
            if errors:
                self._notify_and_log(
                    f"State DB export completed with {len(errors)} errors. Exported: {exported_count}",
                    type="warning",
                )
            else:
                self._notify_and_log(
                    f"Successfully exported {exported_count} citations from state database!",
                    type="positive",
                )

        except Exception as e:
            progress_dialog.close()
            logger.error(f"State DB export failed: {e}")
            self._notify_and_log(f"State DB export failed: {str(e)}", type="negative")

    async def _export_from_state_db_all_sessions(
        self,
        sessions_with_pending: list[dict],
        exclude_citation_ids: set[int],
    ) -> None:
        """Export completed items from ALL sessions with pending exports.

        This method handles exporting from multiple sessions, which is needed when
        a large batch was processed and the user has items pending export from
        previous sessions.

        Args:
            sessions_with_pending: List of dicts with session_id and count
            exclude_citation_ids: Citation IDs to skip (already in memory)
        """
        if not self.state_repository:
            return

        from rmcitecraft.services.citation_formatter import format_census_citation_preview
        import json

        # Collect all items to export from all sessions
        all_items_to_export = []
        for session_info in sessions_with_pending:
            session_id = session_info["session_id"]
            items = self.state_repository.get_session_items(session_id)
            pending_items = [
                item
                for item in items
                if item["status"] == "complete"
                and item.get("export_status", "pending") == "pending"
                and item.get("citation_id") not in exclude_citation_ids
            ]
            all_items_to_export.extend(pending_items)

        if not all_items_to_export:
            self._notify_and_log("No pending items to export from state database", type="info")
            return

        self._notify_and_log(
            f"Exporting {len(all_items_to_export)} items from state database ({len(sessions_with_pending)} sessions)...",
            type="info",
        )

        # Show progress dialog
        with ui.dialog() as progress_dialog, ui.card().classes("p-6"):
            ui.label("Exporting from State Database...").classes("text-lg font-bold mb-4")
            progress_label = ui.label("Loading citation data...").classes("mb-2")
            progress_bar = ui.linear_progress(value=0).classes("mb-4")

        progress_dialog.open()

        exported_count = 0
        images_processed = 0
        errors = []

        try:
            for i, item in enumerate(all_items_to_export):
                try:
                    progress_label.text = f"Processing {item.get('person_name', 'Unknown')} ({i + 1}/{len(all_items_to_export)})"
                    progress_bar.value = i / len(all_items_to_export)
                    await ui.context.client.connected()

                    citation_id = item.get("citation_id")
                    source_id = item.get("source_id")
                    person_id = item.get("person_id")
                    census_year = item.get("census_year")
                    extracted_data_json = item.get("extracted_data")

                    if not extracted_data_json:
                        errors.append(
                            f"{item.get('person_name', 'Unknown')}: Missing extracted_data"
                        )
                        continue

                    # Parse stored extracted data
                    try:
                        extracted_data = (
                            json.loads(extracted_data_json)
                            if isinstance(extracted_data_json, str)
                            else extracted_data_json
                        )
                    except json.JSONDecodeError:
                        errors.append(
                            f"{item.get('person_name', 'Unknown')}: Invalid JSON in extracted_data"
                        )
                        continue

                    # If no citation_id, try to find it by person_id and census_year
                    if not citation_id and person_id:
                        with self.db.transaction() as conn:
                            cursor = conn.cursor()
                            # Find census event for this person and year
                            # Date format is 'D.+YYYYMMDD..+00000000..' so year is at position 4
                            cursor.execute(
                                """
                                SELECT e.EventID, c.CitationID, c.SourceID
                                FROM EventTable e
                                JOIN CitationLinkTable cl ON cl.OwnerID = e.EventID AND cl.OwnerType = 2
                                JOIN CitationTable c ON c.CitationID = cl.CitationID
                                WHERE e.OwnerID = ?
                                  AND e.EventType = 18  -- Census event type
                                  AND substr(e.Date, 4, 4) = ?
                            """,
                                (person_id, str(census_year)),
                            )
                            row = cursor.fetchone()
                            if row:
                                citation_id = row[1]
                                source_id = row[2]

                    if not citation_id:
                        errors.append(
                            f"{item.get('person_name', 'Unknown')}: Could not find citation for person {person_id}, year {census_year}"
                        )
                        continue

                    # Query RootsMagic directly for this citation's source_id
                    if not source_id:
                        with self.db.transaction() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                """
                                SELECT SourceID FROM CitationTable WHERE CitationID = ?
                            """,
                                (citation_id,),
                            )
                            row = cursor.fetchone()
                            if row:
                                source_id = row[0]
                            else:
                                errors.append(
                                    f"{item.get('person_name', 'Unknown')}: Citation {citation_id} not found in RootsMagic"
                                )
                                continue

                    # Generate formatted citations using the preview formatter
                    formatted = format_census_citation_preview(extracted_data, census_year)

                    # Write to SourceTable.Fields and update Source Name brackets
                    from rmcitecraft.database.image_repository import ImageRepository

                    with self.db.transaction() as conn:
                        repo = ImageRepository(conn)
                        # 1. Update SourceTable.Fields BLOB
                        repo.update_source_fields(
                            source_id=source_id,
                            footnote=formatted["footnote"],
                            short_footnote=formatted["short_footnote"],
                            bibliography=formatted["bibliography"],
                        )

                        # 2. Update SourceTable.Name brackets with citation details
                        bracket_content = self._generate_bracket_content_from_data(
                            extracted_data, census_year
                        )
                        if bracket_content and bracket_content != "[]":
                            repo.update_source_name_brackets(source_id, bracket_content)

                    # 3. Process image if exists in temp_images
                    # Check if temp image exists for this citation
                    temp_dir = Path.home() / ".rmcitecraft" / "temp_images"
                    if temp_dir.exists():
                        # Find image file by citation_id pattern (ends with _citXXXX.jpg)
                        matching_images = list(temp_dir.glob(f"*_cit{citation_id}.jpg"))
                        if matching_images:
                            local_image_path = matching_images[0]

                            # MEDIA EXISTENCE CHECK: Prevent duplicate image imports.
                            #
                            # Census images in RootsMagic can be linked to any of three entity
                            # types via MediaLinkTable.OwnerType:
                            #   - Source (OwnerType=3): The source document
                            #   - Citation (OwnerType=4): The specific citation
                            #   - Event (OwnerType=2): The census event itself
                            #
                            # We must check ALL THREE to avoid downloading duplicates. An image
                            # might be linked only to the Event (e.g., from manual entry) while
                            # the Source has no direct media link.
                            has_existing_media = False
                            with self.db.transaction() as conn:
                                cursor = conn.cursor()

                                # First, find the Event linked to this Citation.
                                # CitationLinkTable connects citations to events (OwnerType=2 means Event).
                                cursor.execute(
                                    """
                                    SELECT cl.OwnerID FROM CitationLinkTable cl
                                    WHERE cl.CitationID = ? AND cl.OwnerType = 2
                                    LIMIT 1
                                """,
                                    (citation_id,),
                                )
                                event_row = cursor.fetchone()
                                event_id_for_check = event_row[0] if event_row else None

                                # Check for media linked to Source, Citation, OR Event
                                cursor.execute(
                                    """
                                    SELECT COUNT(*) FROM MediaLinkTable
                                    WHERE (OwnerID = ? AND OwnerType = 3)   -- Source
                                       OR (OwnerID = ? AND OwnerType = 4)   -- Citation
                                       OR (OwnerID = ? AND OwnerType = 2)   -- Event
                                """,
                                    (source_id, citation_id, event_id_for_check or 0),
                                )
                                has_existing_media = cursor.fetchone()[0] > 0

                            if not has_existing_media:
                                # Process the image
                                from datetime import datetime
                                from rmcitecraft.models.image import ImageMetadata
                                from rmcitecraft.services.image_processing import (
                                    get_image_processing_service,
                                )

                                image_service = get_image_processing_service()

                                access_date = extracted_data.get("access_date")
                                if not access_date:
                                    today = datetime.now()
                                    access_date = today.strftime("%-d %B %Y")

                                state = extracted_data.get("state", "")
                                county = extracted_data.get("county", "")
                                person_name = item.get("person_name", "")

                                # Parse surname and given from person_name
                                name_parts = person_name.split(" ", 1) if person_name else ["", ""]
                                given_name = name_parts[0] if name_parts else ""
                                surname = name_parts[1] if len(name_parts) > 1 else ""

                                # For "Surname, Given" format, swap
                                if "," in person_name:
                                    parts = person_name.split(",", 1)
                                    surname = parts[0].strip()
                                    given_name = parts[1].strip() if len(parts) > 1 else ""

                                metadata = ImageMetadata(
                                    image_id=f"batch_{citation_id}",
                                    citation_id=str(citation_id),
                                    year=census_year,
                                    state=state,
                                    county=county,
                                    surname=surname,
                                    given_name=given_name,
                                    familysearch_url=extracted_data.get("familysearch_url", ""),
                                    access_date=access_date,
                                    town_ward=extracted_data.get("town_ward"),
                                    enumeration_district=extracted_data.get("enumeration_district"),
                                    sheet=extracted_data.get("sheet"),
                                    line=extracted_data.get("line"),
                                    family_number=extracted_data.get("family_number"),
                                    dwelling_number=extracted_data.get("dwelling_number"),
                                )

                                image_service.register_pending_image(metadata)
                                result = image_service.process_downloaded_file(
                                    str(local_image_path)
                                )
                                if result:
                                    images_processed += 1
                                else:
                                    logger.warning(
                                        f"Failed to process image for {item.get('person_name')}"
                                    )

                    # Mark as exported
                    self.state_repository.mark_item_exported(item["id"])

                    exported_count += 1

                except Exception as e:
                    logger.error(f"Error exporting state DB item {item.get('id')}: {e}")
                    errors.append(f"{item.get('person_name', 'Unknown')}: {str(e)}")

            # Checkpoint database
            progress_label.text = "Checkpointing database..."
            progress_bar.value = 1.0

            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")

            progress_dialog.close()

            # Report results
            if errors:
                error_summary = f"First 5 errors:\n" + "\n".join(errors[:5])
                if len(errors) > 5:
                    error_summary += f"\n... and {len(errors) - 5} more"
                logger.warning(f"Export errors:\n{error_summary}")
                self._notify_and_log(
                    f"State DB export completed with {len(errors)} errors. Exported: {exported_count} citations, {images_processed} images.",
                    type="warning",
                )
            else:
                self._notify_and_log(
                    f"Successfully exported {exported_count} citations and {images_processed} images from state database!",
                    type="positive",
                )

        except Exception as e:
            progress_dialog.close()
            logger.error(f"State DB export failed: {e}")
            self._notify_and_log(f"State DB export failed: {str(e)}", type="negative")

    async def _repair_source_name_brackets(self) -> None:
        """[LEGACY/REPAIR] Fix Source Name brackets for exported items with empty brackets.

        NOTE: This is a one-time data repair function created to fix items that were
        exported before the export flow was corrected to include bracket updates.
        The normal export flow now properly updates brackets via _export_from_state_db_all_sessions.
        This function can be removed once all historical data has been repaired.

        This function finds all exported items in the state database and updates
        the SourceTable.Name field to include the citation details in brackets.
        """
        if not self.state_repository:
            self._notify_and_log("State repository not available", type="negative")
            return

        import json
        from rmcitecraft.database.image_repository import ImageRepository

        # Find all exported items
        all_sessions = self.state_repository.get_all_sessions()
        items_to_repair = []

        for session in all_sessions:
            items = self.state_repository.get_session_items(session["session_id"])
            for item in items:
                if item["status"] == "complete" and item.get("export_status") == "exported":
                    if item.get("extracted_data"):
                        items_to_repair.append(item)

        if not items_to_repair:
            self._notify_and_log("No exported items found to repair", type="info")
            return

        self._notify_and_log(
            f"Repairing Source Name brackets for {len(items_to_repair)} items...", type="info"
        )

        # Show progress dialog
        with ui.dialog() as progress_dialog, ui.card().classes("p-6"):
            ui.label("Repairing Source Name Brackets...").classes("text-lg font-bold mb-4")
            progress_label = ui.label("Processing...").classes("mb-2")
            progress_bar = ui.linear_progress(value=0).classes("mb-4")

        progress_dialog.open()

        repaired_count = 0
        skipped_count = 0
        errors = []

        try:
            for i, item in enumerate(items_to_repair):
                try:
                    progress_label.text = f"Processing {item.get('person_name', 'Unknown')} ({i + 1}/{len(items_to_repair)})"
                    progress_bar.value = i / len(items_to_repair)

                    # Yield to UI periodically
                    if i % 50 == 0:
                        await ui.context.client.connected()

                    # Parse extracted data
                    extracted_data_json = item.get("extracted_data")
                    try:
                        extracted_data = (
                            json.loads(extracted_data_json)
                            if isinstance(extracted_data_json, str)
                            else extracted_data_json
                        )
                    except json.JSONDecodeError:
                        errors.append(f"{item.get('person_name', 'Unknown')}: Invalid JSON")
                        continue

                    # Get source_id - either from item or look it up
                    source_id = item.get("source_id")
                    citation_id = item.get("citation_id")
                    person_id = item.get("person_id")
                    census_year = item.get("census_year")

                    if not source_id:
                        # Try to find via citation_id or person_id
                        with self.db.transaction() as conn:
                            cursor = conn.cursor()
                            if citation_id:
                                cursor.execute(
                                    "SELECT SourceID FROM CitationTable WHERE CitationID = ?",
                                    (citation_id,),
                                )
                                row = cursor.fetchone()
                                if row:
                                    source_id = row[0]
                            elif person_id and census_year:
                                cursor.execute(
                                    """
                                    SELECT c.SourceID
                                    FROM EventTable e
                                    JOIN CitationLinkTable cl ON cl.OwnerID = e.EventID AND cl.OwnerType = 2
                                    JOIN CitationTable c ON c.CitationID = cl.CitationID
                                    WHERE e.OwnerID = ? AND e.EventType = 18 AND substr(e.Date, 4, 4) = ?
                                """,
                                    (person_id, str(census_year)),
                                )
                                row = cursor.fetchone()
                                if row:
                                    source_id = row[0]

                    if not source_id:
                        errors.append(
                            f"{item.get('person_name', 'Unknown')}: Could not find source_id"
                        )
                        continue

                    # Check if source already has bracket content
                    with self.db.transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT Name FROM SourceTable WHERE SourceID = ?", (source_id,)
                        )
                        row = cursor.fetchone()
                        if not row:
                            errors.append(
                                f"{item.get('person_name', 'Unknown')}: Source {source_id} not found"
                            )
                            continue

                        current_name = row[0]
                        # Skip if brackets already have content
                        if "[]" not in current_name:
                            skipped_count += 1
                            continue

                    # Generate bracket content from extracted data
                    bracket_content = self._generate_bracket_content_from_data(
                        extracted_data, census_year
                    )

                    if bracket_content and bracket_content != "[]":
                        with self.db.transaction() as conn:
                            repo = ImageRepository(conn)
                            repo.update_source_name_brackets(source_id, bracket_content)
                        repaired_count += 1

                except Exception as e:
                    logger.error(f"Error repairing item {item.get('id')}: {e}")
                    errors.append(f"{item.get('person_name', 'Unknown')}: {str(e)}")

            # Checkpoint database
            progress_label.text = "Checkpointing database..."
            progress_bar.value = 1.0

            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")

            progress_dialog.close()

            # Report results
            msg = f"Repair complete: {repaired_count} updated, {skipped_count} already had content"
            if errors:
                msg += f", {len(errors)} errors"
                logger.warning(f"Repair errors (first 5): {errors[:5]}")
            self._notify_and_log(msg, type="positive" if not errors else "warning")

        except Exception as e:
            progress_dialog.close()
            logger.error(f"Repair failed: {e}")
            self._notify_and_log(f"Repair failed: {str(e)}", type="negative")

    async def _repair_missing_images(self) -> None:
        """[LEGACY/REPAIR] Download and link images for exported items missing media.

        NOTE: This is a one-time data repair function created to download images for
        items that were exported before images were downloaded during batch processing.
        The normal batch processing flow downloads images during _process_single_citation_robust.
        This function can be removed once all historical data has been repaired.

        This function:
        1. Finds exported items where the source has no media linked
        2. Downloads images from FamilySearch using stored image_viewer_url
        3. Processes and links images to source/citation/event
        """
        if not self.state_repository:
            self._notify_and_log("State repository not available", type="negative")
            return

        import json
        from pathlib import Path
        from rmcitecraft.database.image_repository import ImageRepository
        from rmcitecraft.models.image import ImageMetadata
        from rmcitecraft.services.image_processing import get_image_processing_service
        from rmcitecraft.services.familysearch_automation import FamilySearchAutomation

        # Find exported items that need images
        all_sessions = self.state_repository.get_all_sessions()
        items_needing_images = []

        self._notify_and_log("Scanning for items needing images...", type="info")

        for session in all_sessions:
            items = self.state_repository.get_session_items(session["session_id"])
            for item in items:
                if item["status"] != "complete" or item.get("export_status") != "exported":
                    continue
                if not item.get("extracted_data"):
                    continue

                # Parse extracted data to get image URL
                try:
                    extracted_data = (
                        json.loads(item["extracted_data"])
                        if isinstance(item["extracted_data"], str)
                        else item["extracted_data"]
                    )
                except json.JSONDecodeError:
                    continue

                image_url = extracted_data.get("image_viewer_url")
                if not image_url:
                    continue

                # Check if source already has media
                source_id = item.get("source_id")
                citation_id = item.get("citation_id")
                person_id = item.get("person_id")
                census_year = item.get("census_year")

                # Look up source_id if not stored
                if not source_id:
                    with self.db.transaction() as conn:
                        cursor = conn.cursor()
                        if citation_id:
                            cursor.execute(
                                "SELECT SourceID FROM CitationTable WHERE CitationID = ?",
                                (citation_id,),
                            )
                            row = cursor.fetchone()
                            if row:
                                source_id = row[0]
                        elif person_id and census_year:
                            cursor.execute(
                                """
                                SELECT c.SourceID, c.CitationID
                                FROM EventTable e
                                JOIN CitationLinkTable cl ON cl.OwnerID = e.EventID AND cl.OwnerType = 2
                                JOIN CitationTable c ON c.CitationID = cl.CitationID
                                WHERE e.OwnerID = ? AND e.EventType = 18 AND substr(e.Date, 4, 4) = ?
                            """,
                                (person_id, str(census_year)),
                            )
                            row = cursor.fetchone()
                            if row:
                                source_id = row[0]
                                citation_id = row[1]

                if not source_id:
                    continue

                # MEDIA EXISTENCE CHECK: Prevent duplicate image imports.
                #
                # Census images in RootsMagic can be linked to any of three entity
                # types via MediaLinkTable.OwnerType:
                #   - Source (OwnerType=3): The source document
                #   - Citation (OwnerType=4): The specific citation
                #   - Event (OwnerType=2): The census event itself
                #
                # We must check ALL THREE to avoid downloading duplicates. An image
                # might be linked only to the Event (e.g., from manual entry) while
                # the Source has no direct media link.
                with self.db.transaction() as conn:
                    cursor = conn.cursor()

                    # First, find the Event linked to this Citation (if we have a citation_id).
                    # CitationLinkTable connects citations to events (OwnerType=2 means Event).
                    event_id_for_check = None
                    if citation_id:
                        cursor.execute(
                            """
                            SELECT cl.OwnerID FROM CitationLinkTable cl
                            WHERE cl.CitationID = ? AND cl.OwnerType = 2
                            LIMIT 1
                        """,
                            (citation_id,),
                        )
                        event_row = cursor.fetchone()
                        event_id_for_check = event_row[0] if event_row else None

                    # Check for media linked to Source, Citation, OR Event
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM MediaLinkTable
                        WHERE (OwnerID = ? AND OwnerType = 3)   -- Source
                           OR (OwnerID = ? AND OwnerType = 4)   -- Citation
                           OR (OwnerID = ? AND OwnerType = 2)   -- Event
                    """,
                        (source_id, citation_id or 0, event_id_for_check or 0),
                    )
                    has_media = cursor.fetchone()[0] > 0

                if has_media:
                    continue  # Skip - already has media linked to Source, Citation, or Event

                items_needing_images.append(
                    {
                        "item": item,
                        "extracted_data": extracted_data,
                        "source_id": source_id,
                        "citation_id": citation_id,
                        "image_url": image_url,
                    }
                )

        if not items_needing_images:
            self._notify_and_log("All exported items already have media attached", type="positive")
            return

        self._notify_and_log(
            f"Found {len(items_needing_images)} items needing images. Starting download...",
            type="info",
        )

        # Show progress dialog
        with ui.dialog() as progress_dialog, ui.card().classes("p-6 w-[500px]"):
            ui.label("Downloading Missing Images").classes("text-lg font-bold mb-4")
            progress_label = ui.label("Initializing...").classes("mb-2")
            progress_bar = ui.linear_progress(value=0).classes("mb-4")
            status_label = ui.label("").classes("text-sm text-gray-600")

        progress_dialog.open()

        downloaded_count = 0
        skipped_count = 0
        errors = []

        try:
            # Initialize FamilySearch automation
            progress_label.text = "Connecting to browser..."
            await ui.context.client.connected()

            fs_automation = FamilySearchAutomation()
            connected = await fs_automation.connect_to_chrome()
            if not connected:
                raise RuntimeError(
                    "Could not connect to Chrome. Make sure Chrome is running with --remote-debugging-port=9222"
                )

            image_service = get_image_processing_service()

            for i, item_data in enumerate(items_needing_images):
                try:
                    item = item_data["item"]
                    extracted_data = item_data["extracted_data"]
                    source_id = item_data["source_id"]
                    citation_id = item_data["citation_id"]
                    image_url = item_data["image_url"]
                    census_year = item.get("census_year")

                    person_name = item.get("person_name", "Unknown")
                    progress_label.text = (
                        f"Downloading {person_name} ({i + 1}/{len(items_needing_images)})"
                    )
                    progress_bar.value = i / len(items_needing_images)
                    status_label.text = f"Downloaded: {downloaded_count} | Skipped: {skipped_count} | Errors: {len(errors)}"

                    # Yield to UI
                    if i % 5 == 0:
                        await ui.context.client.connected()

                    # Generate filename for download
                    state = extracted_data.get("state", "")
                    county = extracted_data.get("county", "")

                    # Get person's name from extracted data or item
                    surname = (
                        item.get("person_name", "").split()[-1] if item.get("person_name") else ""
                    )
                    given_name = (
                        " ".join(item.get("person_name", "").split()[:-1])
                        if item.get("person_name")
                        else ""
                    )

                    if not state or not county:
                        errors.append(f"{person_name}: Missing state/county")
                        continue

                    # Create temp download path
                    temp_filename = (
                        f"{census_year}, {state}, {county} - {surname}, {given_name}.jpg"
                    )
                    temp_path = (
                        Path(self.config.rm_media_root_directory)
                        / f"{census_year} Federal"
                        / temp_filename
                    )

                    # Ensure directory exists
                    temp_path.parent.mkdir(parents=True, exist_ok=True)

                    # Check if file already exists
                    if temp_path.exists():
                        logger.info(f"Image already exists: {temp_path}")
                        # Just need to link it to the source
                        await self._link_existing_image_to_source(
                            temp_path, source_id, citation_id, census_year
                        )
                        downloaded_count += 1
                        continue

                    # Download from FamilySearch
                    success = await fs_automation.download_census_image(image_url, temp_path)

                    if success:
                        # Register and process the image
                        metadata = ImageMetadata(
                            image_id=f"repair_{citation_id}",
                            citation_id=str(citation_id),
                            year=census_year,
                            state=state,
                            county=county,
                            surname=surname,
                            given_name=given_name,
                            familysearch_url=extracted_data.get("familysearch_url", ""),
                            access_date=extracted_data.get("access_date", ""),
                        )

                        image_service.register_pending_image(metadata)
                        result = image_service.process_downloaded_file(temp_path)

                        if result:
                            downloaded_count += 1
                        else:
                            # File was downloaded but couldn't be processed - still try to link
                            await self._link_existing_image_to_source(
                                temp_path, source_id, citation_id, census_year
                            )
                            downloaded_count += 1
                    else:
                        errors.append(f"{person_name}: Download failed")

                    # Add small delay between downloads to be respectful
                    await asyncio.sleep(1.0)

                except Exception as e:
                    logger.error(
                        f"Error downloading image for {item.get('person_name', 'Unknown')}: {e}"
                    )
                    errors.append(f"{item.get('person_name', 'Unknown')}: {str(e)}")

            # Cleanup
            await fs_automation.disconnect()

            # Checkpoint database
            progress_label.text = "Checkpointing database..."
            progress_bar.value = 1.0

            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")

            progress_dialog.close()

            # Report results
            msg = f"Image repair complete: {downloaded_count} downloaded"
            if skipped_count > 0:
                msg += f", {skipped_count} skipped"
            if errors:
                msg += f", {len(errors)} errors"
                logger.warning(f"Image repair errors (first 10): {errors[:10]}")
            self._notify_and_log(msg, type="positive" if not errors else "warning")

        except Exception as e:
            progress_dialog.close()
            logger.error(f"Image repair failed: {e}")
            self._notify_and_log(f"Image repair failed: {str(e)}", type="negative")

    async def _link_existing_image_to_source(
        self, image_path: Path, source_id: int, citation_id: int, census_year: int
    ) -> None:
        """Link an existing image file to a source in RootsMagic.

        Args:
            image_path: Path to the image file
            source_id: RootsMagic SourceID
            citation_id: RootsMagic CitationID
            census_year: Census year for directory structure
        """
        from rmcitecraft.database.image_repository import ImageRepository

        with self.db.transaction() as conn:
            repo = ImageRepository(conn)

            # Check if media record exists
            media_id = repo.find_media_by_file(image_path.name)

            if not media_id:
                # Create media record
                media_id = repo.create_media_record(
                    media_file=image_path.name,
                    media_path=f"Records - Census/{census_year} Federal",
                )

            # Link to source if not already linked
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) FROM MediaLinkTable WHERE MediaID = ? AND OwnerID = ? AND OwnerType = 3
            """,
                (media_id, source_id),
            )
            if cursor.fetchone()[0] == 0:
                repo.link_media_to_source(media_id, source_id)

            # Link to citation if not already linked
            cursor.execute(
                """
                SELECT COUNT(*) FROM MediaLinkTable WHERE MediaID = ? AND OwnerID = ? AND OwnerType = 4
            """,
                (media_id, citation_id),
            )
            if cursor.fetchone()[0] == 0:
                repo.link_media_to_citation(media_id, citation_id)

    def _generate_bracket_content_from_data(self, data: dict, year: int) -> str:
        """Generate bracket content from extracted data dict.

        Format varies by census year:
        - 1880-1950: [ED XX, sheet XX, line XX] (with "citing" prefix)
        - 1850-1870: [page XX, line YY] (no "citing" prefix, just page and line)
        - 1790-1840: [page XX] (no "citing" prefix)

        Args:
            data: Extracted census data dictionary
            year: Census year

        Returns:
            Formatted bracket content string
        """
        parts = []

        # Pre-1880 census: Simple format without "citing" prefix
        if year < 1880:
            page = data.get("page", "")
            line = data.get("line", "")

            if page:
                parts.append(f"page {page}")
            if line:
                parts.append(f"line {line}")

            if parts:
                return f"[{', '.join(parts)}]"
            return "[]"

        # 1880-1950: Include enumeration district with "citing" prefix
        ed = data.get("enumeration_district", "")
        if ed:
            parts.append(f"ED {ed}")

        # Sheet
        sheet = data.get("sheet", "")
        if sheet:
            parts.append(f"sheet {sheet}")

        # Line number
        line = data.get("line", "")
        if line:
            parts.append(f"line {line}")

        if parts:
            return f"[citing {', '.join(parts)}]"
        return "[]"

    async def _do_export_internal(
        self, completed_citations: list[CitationBatchItem], source_name: str = "session"
    ) -> None:
        """Internal export operation for a list of citations.

        Args:
            completed_citations: List of citations to export
            source_name: Description of source for logging
        """
        await self._do_export_impl(completed_citations, source_name)

    async def _do_export_impl(
        self, completed_citations: list[CitationBatchItem], source_name: str = "session"
    ) -> None:
        """Implementation of export operation."""
        from datetime import datetime

        from rmcitecraft.models.image import ImageMetadata
        from rmcitecraft.services.image_processing import get_image_processing_service

        # Show progress dialog
        with ui.dialog() as progress_dialog, ui.card().classes("p-6"):
            ui.label(f"Exporting from {source_name}...").classes("text-lg font-bold mb-4")
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

            # Build a lookup of state DB items by citation_id for efficient marking
            state_items_by_citation = {}
            if self.state_repository and self.current_session_id:
                items = self.state_repository.get_session_items(self.current_session_id)
                for item in items:
                    cit_id = item.get("citation_id")
                    if cit_id:
                        state_items_by_citation[cit_id] = item["id"]

            # Process each citation
            for i, citation in enumerate(completed_citations):
                try:
                    progress_label.text = (
                        f"Processing {citation.full_name} ({i + 1}/{len(completed_citations)})"
                    )
                    progress_bar.value = i / len(completed_citations)
                    await ui.context.client.connected()

                    # 1. Write citation fields to database
                    await self._write_citation_to_database(citation)
                    citations_written += 1

                    # 2. Mark as exported in state DB (if tracking this citation)
                    if citation.citation_id in state_items_by_citation:
                        self.state_repository.mark_item_exported(
                            state_items_by_citation[citation.citation_id]
                        )

                    # 3. Ensure existing media is linked to source and all citations
                    if citation.has_existing_media:
                        await self._ensure_existing_media_links(citation)

                    # 4. Process image if downloaded (skip if already has media)
                    if (
                        citation.local_image_path
                        and Path(citation.local_image_path).exists()
                        and not citation.has_existing_media
                    ):
                        # Create ImageMetadata from citation data
                        access_date = citation.merged_data.get("access_date")
                        if not access_date:
                            today = datetime.now()
                            access_date = today.strftime("%-d %B %Y")

                        state = citation.merged_data.get("state", "")
                        county = citation.merged_data.get("county", "")

                        if (not state or not county) and citation.source_name:
                            from rmcitecraft.parsers.source_name_parser import SourceNameParser

                            try:
                                parsed = SourceNameParser.parse(citation.source_name)
                                if parsed:
                                    if not state and parsed.get("state"):
                                        state = parsed["state"]
                                    if not county and parsed.get("county"):
                                        county = parsed["county"]
                            except Exception as e:
                                logger.warning(
                                    f"Could not parse source_name for {citation.full_name}: {e}"
                                )

                        if not state or not county:
                            errors.append(
                                f"{citation.full_name}: Missing state/county for image filename"
                            )
                            continue

                        metadata = ImageMetadata(
                            image_id=f"batch_{citation.citation_id}",
                            citation_id=str(citation.citation_id),
                            year=citation.census_year,
                            state=state,
                            county=county,
                            surname=citation.surname,
                            given_name=citation.given_name,
                            familysearch_url=citation.familysearch_url or "",
                            access_date=access_date,
                            town_ward=citation.merged_data.get("town_ward"),
                            enumeration_district=citation.merged_data.get("enumeration_district"),
                            sheet=citation.merged_data.get("sheet"),
                            line=citation.merged_data.get("line"),
                            family_number=citation.merged_data.get("family_number"),
                            dwelling_number=citation.merged_data.get("dwelling_number"),
                        )

                        image_service.register_pending_image(metadata)
                        result = image_service.process_downloaded_file(citation.local_image_path)
                        if result:
                            images_processed += 1
                        else:
                            errors.append(f"{citation.full_name}: Failed to process image")

                except Exception as e:
                    logger.error(f"Error exporting citation {citation.citation_id}: {e}")
                    errors.append(f"{citation.full_name}: {str(e)}")

            progress_bar.value = 1.0
            progress_label.text = "Checkpointing database..."

            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")

            progress_label.text = "Export complete!"
            await asyncio.sleep(0.5)
            progress_dialog.close()

            if errors:
                self._notify_and_log(
                    f"Export ({source_name}) completed with {len(errors)} errors. "
                    f"Written: {citations_written} citations, {images_processed} images.",
                    type="warning",
                )
            else:
                self._notify_and_log(
                    f"Successfully exported {citations_written} citations and {images_processed} images from {source_name}!",
                    type="positive",
                )

        except Exception as e:
            logger.error(f"Export failed: {e}")
            try:
                with self.db.transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except Exception:
                pass
            progress_dialog.close()
            self._notify_and_log(f"Export failed: {str(e)}", type="negative")

    async def _do_export(self, dialog, completed_citations: list[CitationBatchItem]) -> None:
        """Perform the actual export operation (legacy method for backwards compatibility)."""
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
                    progress_label.text = (
                        f"Processing {citation.full_name} ({i + 1}/{len(completed_citations)})"
                    )
                    progress_bar.value = i / len(completed_citations)
                    await ui.context.client.connected()  # Allow UI update

                    # 1. Write citation fields to database
                    await self._write_citation_to_database(citation)
                    citations_written += 1

                    # 2. Ensure existing media is linked to source and all citations
                    if citation.has_existing_media:
                        await self._ensure_existing_media_links(citation)

                    # 3. Process image if downloaded (skip if already has media in RootsMagic)
                    if (
                        citation.local_image_path
                        and Path(citation.local_image_path).exists()
                        and not citation.has_existing_media
                    ):
                        # Create ImageMetadata from citation data
                        # Generate access date in Evidence Explained format: "D Month YYYY"
                        access_date = citation.merged_data.get("access_date")
                        if not access_date:
                            # Generate today's date in correct format
                            today = datetime.now()
                            access_date = today.strftime("%-d %B %Y")  # e.g., "7 November 2024"

                        # Get state/county from merged_data, with fallback to source_name parsing
                        state = citation.merged_data.get("state", "")
                        county = citation.merged_data.get("county", "")

                        # If state/county are missing, try to parse from source_name
                        if (not state or not county) and citation.source_name:
                            from rmcitecraft.parsers.source_name_parser import SourceNameParser

                            try:
                                parsed = SourceNameParser.parse(citation.source_name)
                                if parsed:
                                    if not state and parsed.get("state"):
                                        state = parsed["state"]
                                        logger.debug(
                                            f"Got state '{state}' from source_name for {citation.full_name}"
                                        )
                                    if not county and parsed.get("county"):
                                        county = parsed["county"]
                                        logger.debug(
                                            f"Got county '{county}' from source_name for {citation.full_name}"
                                        )
                            except Exception as e:
                                logger.warning(
                                    f"Could not parse source_name for {citation.full_name}: {e}"
                                )

                        # Validate state/county before image processing
                        if not state or not county:
                            logger.error(
                                f"Cannot process image for {citation.full_name}: "
                                f"missing state='{state}' or county='{county}'"
                            )
                            errors.append(
                                f"{citation.full_name}: Missing state/county for image filename"
                            )
                            continue  # Skip image processing for this citation

                        metadata = ImageMetadata(
                            image_id=f"batch_{citation.citation_id}",
                            citation_id=str(citation.citation_id),  # Convert to string
                            year=citation.census_year,
                            state=state,
                            county=county,
                            surname=citation.surname,
                            given_name=citation.given_name,
                            familysearch_url=citation.familysearch_url or "",
                            access_date=access_date,
                            town_ward=citation.merged_data.get("town_ward"),
                            enumeration_district=citation.merged_data.get("enumeration_district"),
                            sheet=citation.merged_data.get("sheet"),
                            line=citation.merged_data.get("line"),
                            family_number=citation.merged_data.get("family_number"),
                            dwelling_number=citation.merged_data.get("dwelling_number"),
                        )

                        # Register metadata with image service before processing
                        image_service.register_pending_image(metadata)

                        # Process image (rename, move, create DB records)
                        result = image_service.process_downloaded_file(citation.local_image_path)
                        if result:
                            images_processed += 1
                            logger.info(
                                f"Processed image for {citation.full_name}: {result.final_filename}"
                            )
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
                    type="warning",
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
                    type="positive",
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

    def _generate_bracket_content(self, citation) -> str:
        """Generate bracket content for SourceTable.Name from extracted citation data.

        Format varies by census year:
        - 1880-1950: [ED XX, sheet XX, line XX] (with "citing" prefix)
        - 1850-1870: [page XX, line YY] (no "citing" prefix, just page and line)
        - 1790-1840: [page XX] (no "citing" prefix)

        Args:
            citation: CitationBatchItem with merged_data

        Returns:
            Formatted bracket content string (including brackets)
        """
        data = citation.merged_data
        year = citation.census_year
        parts = []

        # Pre-1880 census: Simple format without "citing" prefix
        if year < 1880:
            page = data.get("page", "")
            line = data.get("line", "")

            if page:
                parts.append(f"page {page}")
            if line:
                parts.append(f"line {line}")

            if parts:
                return f"[{', '.join(parts)}]"
            return "[]"

        # 1880-1950: Include enumeration district with "citing" prefix
        ed = data.get("enumeration_district", "")
        if ed:
            parts.append(f"ED {ed}")

        # Sheet
        sheet = data.get("sheet", "")
        if sheet:
            parts.append(f"sheet {sheet}")

        # Line number
        line = data.get("line", "")
        if line:
            parts.append(f"line {line}")

        if parts:
            return f"[citing {', '.join(parts)}]"
        return "[]"  # Keep empty brackets if no data available

    async def _write_citation_to_database(self, citation) -> None:
        """Write citation fields to SourceTable.Fields BLOB and update related records.

        For free-form sources (TemplateID=0), writes Footnote, ShortFootnote, Bibliography
        to SourceTable.Fields as XML. Also updates:
        - SourceTable.Name brackets with citation details
        - CitationLinkTable.Quality to "PDO" for census citations
        """
        from rmcitecraft.database.image_repository import ImageRepository

        # Get database connection in write mode
        with self.db.transaction() as conn:
            repo = ImageRepository(conn)

            # 1. Update SourceTable.Fields BLOB with formatted citations
            repo.update_source_fields(
                source_id=citation.source_id,
                footnote=citation.footnote,
                short_footnote=citation.short_footnote,
                bibliography=citation.bibliography,
            )

            # 2. Update SourceTable.Name brackets with citation details
            bracket_content = self._generate_bracket_content(citation)
            if bracket_content and bracket_content != "[]":
                repo.update_source_name_brackets(
                    source_id=citation.source_id,
                    bracket_content=bracket_content,
                )
                logger.debug(
                    f"Updated source name brackets for SourceID={citation.source_id}: {bracket_content}"
                )

            # 3. Update CitationLinkTable.Quality to "PDO" for census event citations
            self._update_citation_quality(conn, citation.citation_id, citation.event_id, "PDO")

            logger.info(
                f"Wrote citation fields to database for SourceID={citation.source_id} (CitationID={citation.citation_id})"
            )

    def _update_citation_quality(self, conn, citation_id: int, event_id: int, quality: str) -> None:
        """Update the Quality field in CitationLinkTable for a citation linked to an event.

        Args:
            conn: Database connection
            citation_id: CitationID from CitationTable
            event_id: EventID from EventTable
            quality: Quality code (e.g., "PDO" for Primary/Direct/Original)
        """
        cursor = conn.cursor()

        try:
            # Update Quality for citation linked to event (OwnerType=2)
            cursor.execute(
                """
                UPDATE CitationLinkTable
                SET Quality = ?
                WHERE CitationID = ? AND OwnerType = 2 AND OwnerID = ?
                """,
                (quality, citation_id, event_id),
            )

            if cursor.rowcount > 0:
                logger.debug(
                    f"Updated Quality to '{quality}' for CitationID={citation_id}, EventID={event_id}"
                )
            else:
                logger.warning(
                    f"No CitationLink found for CitationID={citation_id}, EventID={event_id}"
                )

        except Exception as e:
            logger.error(f"Failed to update citation quality: {e}")

    async def _ensure_existing_media_links(self, citation) -> None:
        """Ensure existing media is linked to source, event, and all related citations.

        When a citation already has media attached from a previous processing run,
        this method ensures proper links exist to:
        1. The source document
        2. The census event
        3. All citations for that event

        Args:
            citation: CitationBatchItem with has_existing_media=True
        """
        from rmcitecraft.database.image_repository import ImageRepository

        try:
            with self.db.transaction() as conn:
                repo = ImageRepository(conn)
                cursor = conn.cursor()

                # Find media linked to this citation (OwnerType=4 for citations)
                cursor.execute(
                    """
                    SELECT m.MediaID, m.MediaFile
                    FROM MultimediaTable m
                    JOIN MediaLinkTable ml ON m.MediaID = ml.MediaID
                    WHERE ml.OwnerID = ? AND ml.OwnerType = 4
                    """,
                    (citation.citation_id,),
                )
                media_rows = cursor.fetchall()

                if not media_rows:
                    logger.debug(f"No media found linked to CitationID={citation.citation_id}")
                    return

                for media_id, media_file in media_rows:
                    logger.debug(f"Ensuring links for MediaID={media_id} ({media_file})")

                    # Link to source (OwnerType=3) if not already linked
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM MediaLinkTable
                        WHERE MediaID = ? AND OwnerID = ? AND OwnerType = 3
                        """,
                        (media_id, citation.source_id),
                    )
                    if cursor.fetchone()[0] == 0:
                        repo.link_media_to_source(media_id, citation.source_id)
                        logger.info(f"Linked MediaID={media_id} to SourceID={citation.source_id}")

                    # Link to event (OwnerType=2) if not already linked
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM MediaLinkTable
                        WHERE MediaID = ? AND OwnerID = ? AND OwnerType = 2
                        """,
                        (media_id, citation.event_id),
                    )
                    if cursor.fetchone()[0] == 0:
                        repo.link_media_to_event(media_id, citation.event_id)
                        logger.info(f"Linked MediaID={media_id} to EventID={citation.event_id}")

                    # Find all other citations for this event and link media to them
                    citation_ids = repo.find_citations_for_event(citation.event_id)
                    for cit_id in citation_ids:
                        if cit_id != citation.citation_id:  # Skip the original citation
                            cursor.execute(
                                """
                                SELECT COUNT(*) FROM MediaLinkTable
                                WHERE MediaID = ? AND OwnerID = ? AND OwnerType = 4
                                """,
                                (media_id, cit_id),
                            )
                            if cursor.fetchone()[0] == 0:
                                repo.link_media_to_citation(media_id, cit_id)
                                logger.info(f"Linked MediaID={media_id} to CitationID={cit_id}")

                conn.commit()

        except Exception as e:
            logger.error(f"Failed to ensure existing media links: {e}")
            import traceback

            traceback.print_exc()

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
                                on_click=lambda url=citation.familysearch_url: ui.run_javascript(
                                    f"window.open('{url}', '_blank')"
                                ),
                            ).props("flat dense").tooltip("Open in new tab")

                # Image viewer
                if self.controller.session.current_citation:
                    citation = self.controller.session.current_citation
                    # Show local image if available, otherwise show FamilySearch viewer
                    if citation.local_image_path:
                        self._render_local_image(
                            citation.local_image_path, citation.familysearch_url
                        )
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
        with ui.element("div").classes("w-full overflow-auto p-0 relative") as container:
            container._props["id"] = "census-image-container"
            container._props["tabindex"] = "0"  # Make focusable for keyboard events
            container._props["style"] = (
                "height: 100%; max-height: 100%; flex: 0 0 auto;"  # Prevent flex resizing
            )

            # Zoom indicator (top-left overlay, positioned absolutely relative to container)
            zoom_label = ui.label("100%").classes(
                "absolute top-1 left-1 bg-black bg-opacity-60 text-white text-[10px] px-2 py-1 rounded z-10"
            )
            zoom_label._props["style"] = "position: sticky; top: 4px; left: 4px;"

            # Keyboard shortcuts hint (bottom-left overlay)
            shortcuts_label = ui.label("Z=400% zoom | =/- zoom | arrows=pan").classes(
                "absolute bottom-1 left-1 bg-black bg-opacity-60 text-white text-[9px] px-2 py-1 rounded z-10"
            )
            shortcuts_label._props["style"] = "position: sticky; bottom: 4px; left: 4px;"

            # Image (starts at fit-to-width, will scale but container stays fixed)
            img = ui.image(image_path).classes("object-contain transition-all duration-200")
            img._props["id"] = "census-image"
            img._props["style"] = "display: block; width: 100%; height: auto; min-height: 0;"

            # Optional: Link to view on FamilySearch
            if familysearch_url:
                with ui.row().classes("w-full justify-center gap-1 mt-1"):
                    ui.button(
                        "View on FamilySearch",
                        icon="open_in_new",
                        on_click=lambda: ui.run_javascript(
                            f"window.open('{familysearch_url}', '_blank')"
                        ),
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
        with ui.column().classes("w-full h-full items-center justify-center gap-1 p-1"):
            # Icon
            ui.icon("open_in_browser", size="1.5rem").classes("text-blue-500")

            # Title only
            ui.label("Census Image Available").classes("text-xs font-semibold")

            # Very short explanation
            ui.label("Images cannot be embedded").classes("text-[10px] text-gray-600 text-center")
            ui.label("(Login required)").classes("text-[9px] text-gray-500 text-center italic")

            # Compact button
            ui.button(
                "OPEN IMAGE",
                icon="launch",
                on_click=lambda: ui.run_javascript(f"window.open('{familysearch_url}', '_blank')"),
            ).props("color=primary dense size=sm").classes("text-[10px] px-2 py-1")

            # Minimal URL preview
            url_preview = (
                "..." + familysearch_url[-30:] if len(familysearch_url) > 30 else familysearch_url
            )
            ui.label(url_preview).classes("text-[8px] text-gray-400 font-mono break-all")

    def _notify_and_log(
        self, message: str, type: str = "info", source: str = "Batch Processing"
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

    def _render_census_dashboard(self) -> None:
        """Render the Census Dashboard tab (placeholder for census-specific visualizations)."""
        from rmcitecraft.database.census_batch_state_repository import CensusBatchStateRepository

        with ui.column().classes("w-full p-6 gap-6"):
            # Header
            ui.label("Census Dashboard").classes("text-3xl font-bold")
            ui.label("Monitor Census batch processing with year-based analytics").classes(
                "text-gray-600"
            )

            ui.separator()

            # Coming Soon Message
            with ui.card().classes("w-full p-8 bg-blue-50"):
                ui.label("Census-Specific Dashboard Coming Soon").classes("text-2xl font-bold mb-4")

                ui.markdown("""
                The Census Dashboard will include:
                
                **Year Breakdown:**
                - Distribution of census records by decade (1790-1950)
                - Year-over-year coverage chart
                
                **Geographic Mapping:**
                - Interactive US state map showing census coverage
                - County-level drill-down within states
                - Heat map visualization
                
                **Citation Quality:**
                - Completeness metrics (missing fields)
                - Photo attachment rates
                - Source quality distribution
                
                **Session Analytics:**
                - Processing timeline
                - Error distribution
                - Performance metrics
                """).classes("text-sm")

            # Temporary: Show that repo is ready
            with ui.card().classes("w-full p-4 bg-green-50"):
                ui.label("✓ Backend Ready").classes("text-lg font-bold text-green-700")
                ui.label(
                    "CensusBatchStateRepository created with census-specific analytics methods"
                ).classes("text-sm text-green-600")
