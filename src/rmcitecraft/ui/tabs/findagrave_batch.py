"""Find a Grave Batch Processing Tab UI."""

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from nicegui import ui

from rmcitecraft.config import get_config
from rmcitecraft.database.batch_state_repository import BatchStateRepository
from rmcitecraft.database.findagrave_queries import (
    check_citation_exists_detailed,
    create_burial_event_and_link_citation,
    create_cemetery_for_existing_location,
    create_findagrave_source_and_citation,
    create_location_and_cemetery,
    link_citation_to_families,
)
from rmcitecraft.database.image_repository import ImageRepository
from rmcitecraft.services.adaptive_timeout import AdaptiveTimeoutManager, TimingContext
from rmcitecraft.services.error_log import get_error_log_service
from rmcitecraft.services.findagrave_automation import get_findagrave_automation
from rmcitecraft.services.findagrave_batch import (
    FindAGraveBatchController,
    FindAGraveBatchItem,
    FindAGraveStatus,
)
from rmcitecraft.services.findagrave_formatter import (
    format_findagrave_citation,
    generate_image_filename,
    generate_source_name,
)
from rmcitecraft.services.page_health_monitor import (
    PageHealthMonitor,
    PageRecoveryManager,
)
from rmcitecraft.services.retry_strategy import RetryConfig, RetryStrategy


class FindAGraveBatchTab:
    """Find a Grave Batch Processing Tab component."""

    def __init__(self):
        """Initialize Find a Grave batch processing tab."""
        self.config = get_config()
        self.controller = FindAGraveBatchController()
        self.error_log = get_error_log_service()
        self.automation = get_findagrave_automation()

        # Robustness components
        self.state_repository = BatchStateRepository(
            db_path=self.config.findagrave_state_db_path
        )
        self.health_monitor = PageHealthMonitor(health_check_timeout_ms=2000)
        self.recovery_manager = PageRecoveryManager(self.health_monitor)
        self.timeout_manager = AdaptiveTimeoutManager(
            base_timeout_seconds=self.config.findagrave_base_timeout_seconds,
            window_size=self.config.findagrave_timeout_window_size,
        )
        self.retry_strategy = RetryStrategy(
            config=RetryConfig(
                max_retries=self.config.findagrave_max_retries,
                base_delay_seconds=self.config.findagrave_retry_base_delay_seconds,
            )
        )

        # State tracking
        self.current_session_id: str | None = None
        self.current_state_item_id: int | None = None
        self.checkpoint_counter = 0

        # UI component references
        self.container: ui.column | None = None
        self.header_container: ui.card | None = None
        self.queue_container: ui.column | None = None
        self.detail_container: ui.column | None = None
        self.selected_item_ids: set[int] = set()
        self.ui_context = None  # Store UI context for background tasks

        # Batch processing settings
        self.auto_download_images: bool = True  # Auto-download images during batch processing

    def render(self) -> ui.column:
        """Render the Find a Grave batch processing tab."""
        # Store UI context for background tasks
        self.ui_context = ui.context.client

        with ui.column().classes("w-full h-full gap-4") as self.container:
            self._render_header()

            if not self.controller.session:
                self._render_empty_state()
            else:
                self._render_batch_view()

        return self.container

    def _render_header(self) -> None:
        """Render header with session info and actions."""
        with ui.card().classes("w-full p-2") as self.header_container:
            with ui.row().classes("w-full items-center justify-between"):
                # Session info
                if self.controller.session:
                    session = self.controller.session
                    with ui.column().classes("gap-0"):
                        ui.label("Find a Grave Batch Processing").classes("font-bold text-lg")
                        ui.label(
                            f"{session.complete_count}/{session.total_count} complete "
                            f"({session.error_count} errors, {session.pending_count} pending)"
                        ).classes("text-sm text-gray-600")
                else:
                    ui.label("Find a Grave Batch Processing").classes("font-bold text-lg")

                # Actions
                with ui.row().classes("gap-1"):
                    # Batch processing options
                    if self.controller.session:
                        ui.checkbox(
                            "Auto-download images",
                            value=self.auto_download_images,
                            on_change=lambda e: setattr(self, 'auto_download_images', e.value),
                        ).props("dense").classes("text-sm")

                    ui.button(
                        "Load Batch",
                        icon="download",
                        on_click=self._show_load_dialog,
                    ).props("dense outline")

                    ui.button(
                        "Resume Session",
                        icon="replay",
                        on_click=self._show_resume_dialog,
                    ).props("dense outline")

                    ui.button(
                        "Reset State DB",
                        icon="delete_sweep",
                        on_click=self._show_reset_database_dialog,
                    ).props("dense outline color=orange").tooltip(
                        "Clear all batch state data (use after RootsMagic restore)"
                    )

                    if self.controller.session:
                        ui.button(
                            "Process",
                            icon="play_arrow",
                            on_click=self._start_batch_processing,
                        ).props("dense color=primary")

    def _render_empty_state(self) -> None:
        """Render empty state when no batch loaded."""
        with ui.column().classes("w-full items-center justify-center p-8"):
            ui.icon("account_box", size="xl").classes("text-gray-400")
            ui.label("No batch loaded").classes("text-gray-500 text-lg")
            ui.label("Click 'Load Batch' to begin").classes("text-gray-400 text-sm")

    def _render_batch_view(self) -> None:
        """Render batch processing view with queue and details."""
        with ui.row().classes("w-full gap-4").style(
            "height: 75vh; min-height: 75vh; max-height: 75vh; flex-wrap: nowrap; align-items: flex-start"
        ):
            # Left: Queue (35%)
            with ui.card().classes("p-2").style(
                "width: 35%; min-width: 35%; max-width: 35%; height: 100%; flex-shrink: 0; flex-grow: 0"
            ):
                with ui.row().classes("w-full items-center justify-between mb-2"):
                    ui.label("Memorial Queue").classes("font-bold text-sm")
                    with ui.row().classes("gap-1"):
                        ui.button(
                            "Select All",
                            icon="check_box",
                            on_click=self._select_all,
                        ).props("dense flat size=sm")
                        ui.button(
                            "Clear",
                            icon="check_box_outline_blank",
                            on_click=self._deselect_all,
                        ).props("dense flat size=sm")
                with ui.scroll_area().classes("w-full h-full"):
                    with ui.column().classes("w-full gap-1") as self.queue_container:
                        self._render_queue_items()

            # Right: Person Detail (65%)
            with ui.card().classes("p-2").style(
                "width: 65%; min-width: 65%; max-width: 65%; height: 100%; overflow-y: auto; flex-shrink: 0; flex-grow: 0"
            ):
                ui.label("Person Detail").classes("font-bold text-sm mb-2")
                with ui.column().classes("w-full") as self.detail_container:
                    self._render_item_details()

    def _render_queue_items(self) -> None:
        """Render queue items."""
        if not self.controller.session:
            return

        for item in self.controller.session.items:
            self._render_queue_item(item)

    def _render_queue_item(self, item: FindAGraveBatchItem) -> None:
        """Render a single queue item."""
        is_selected = (
            self.controller.session
            and item == self.controller.session.current_item
        )
        is_checked = item.person_id in self.selected_item_ids

        # Background color based on status
        if item.is_complete:
            status_color = "bg-green-50"
        elif item.is_error:
            status_color = "bg-red-50"
        elif item.needs_review:
            status_color = "bg-orange-50"
        else:
            status_color = "bg-white"

        border_class = "border-l-4 border-blue-500" if is_selected else "border-l-4 border-transparent"

        with ui.card().classes(
            f"w-full p-2 cursor-pointer hover:bg-gray-50 {status_color} {border_class}"
        ).on("click", lambda i=item: self._on_item_click(i)):
            with ui.row().classes("w-full items-start gap-2"):
                # Checkbox
                ui.checkbox(value=is_checked).on(
                    "update:model-value",
                    lambda e, pid=item.person_id: self._on_checkbox_change(pid, e.args),
                ).props("dense")

                # Status icon
                status_icon = self._get_status_icon(item.status)
                ui.icon(status_icon).classes("text-lg")

                # Item info
                with ui.column().classes("flex-grow gap-0"):
                    ui.label(item.full_name).classes("font-semibold text-sm")
                    dates = f"{item.birth_year or '?'}-{item.death_year or '?'}"
                    ui.label(dates).classes("text-xs text-gray-600")
                    ui.label(f"PersonID {item.person_id} | Memorial #{item.memorial_id}").classes("text-xs text-gray-500")

    def _render_item_details(self) -> None:
        """Render details for current item."""
        if not self.controller.session or not self.controller.session.current_item:
            ui.label("No item selected").classes("text-gray-500 italic text-center")
            return

        item = self.controller.session.current_item

        # Item header
        with ui.row().classes("w-full items-center justify-between mb-4"):
            with ui.column().classes("gap-0"):
                ui.label(item.full_name).classes("font-bold text-xl")
                dates = f"{item.birth_year or '?'}-{item.death_year or '?'}"
                ui.label(dates).classes("text-lg text-gray-600")

            # Action buttons
            with ui.row().classes("gap-2"):
                if item.status == FindAGraveStatus.QUEUED:
                    ui.button(
                        "Extract Data",
                        icon="download",
                        on_click=lambda: self._extract_item_data(item),
                    ).props("color=primary")

        # Memorial info
        with ui.card().classes("w-full p-4 mb-4"):
            ui.label("Memorial Information").classes("font-semibold mb-2")
            ui.label(f"Memorial ID: {item.memorial_id}").classes("text-sm")
            ui.label(f"URL: {item.url}").classes("text-sm break-all")

            if item.note:
                ui.label(f"Note: {item.note}").classes("text-sm text-gray-600")

        # Extracted data (if available)
        if item.extracted_data:
            self._render_extracted_data(item)

        # Photos (if available)
        if item.photos:
            self._render_photos(item)

        # Formatted citations (if available)
        if item.footnote:
            self._render_formatted_citations(item)

        # Error message (if applicable)
        if item.error:
            with ui.card().classes("w-full p-4 bg-red-50"):
                ui.label("Error").classes("font-semibold text-red-800")
                ui.label(item.error).classes("text-sm text-red-700")

    def _render_extracted_data(self, item: FindAGraveBatchItem) -> None:
        """Render extracted data from Find a Grave."""
        with ui.card().classes("w-full p-4 mb-4"):
            ui.label("Extracted Data").classes("font-semibold mb-2")

            data = item.extracted_data

            # Cemetery info
            if cemetery := data.get('cemeteryName'):
                ui.label(f"Cemetery: {cemetery}").classes("text-sm font-medium")

            if location := item.cemetery_location:
                ui.label(f"Location: {location}").classes("text-sm text-gray-700")

            # Contributor info
            if maintained := data.get('maintainedBy'):
                ui.label(f"{maintained}").classes("text-sm text-gray-600")

    def _render_formatted_citations(self, item: FindAGraveBatchItem) -> None:
        """Render formatted Evidence Explained citations."""
        with ui.card().classes("w-full p-4 mb-4 bg-green-50"):
            ui.label("Generated Citations (Evidence Explained)").classes("font-semibold text-green-800 mb-3")

            # Footnote
            with ui.column().classes("w-full mb-3"):
                ui.label("Footnote").classes("font-medium text-sm mb-1")
                ui.html(content=item.footnote or "", sanitize=False).classes("text-sm")

            ui.separator().classes("mb-3")

            # Short Footnote
            with ui.column().classes("w-full mb-3"):
                ui.label("Short Footnote").classes("font-medium text-sm mb-1")
                ui.html(content=item.short_footnote or "", sanitize=False).classes("text-sm")

            ui.separator().classes("mb-3")

            # Bibliography
            with ui.column().classes("w-full"):
                ui.label("Bibliography").classes("font-medium text-sm mb-1")
                ui.html(content=item.bibliography or "", sanitize=False).classes("text-sm")

    def _render_photos(self, item: FindAGraveBatchItem) -> None:
        """Render photos section."""
        with ui.card().classes("w-full p-4 mb-4"):
            ui.label(f"Photos ({len(item.photos)})").classes("font-semibold mb-2")

            with ui.column().classes("w-full gap-2"):
                for photo in item.photos:
                    with ui.row().classes("w-full items-center gap-4"):
                        # Photo type icon
                        if photo.get('photoType') == 'Person':
                            ui.icon('person').classes("text-blue-600")
                        else:
                            ui.icon('image').classes("text-gray-600")

                        # Photo info
                        with ui.column().classes("gap-0 flex-grow"):
                            photo_type = photo.get('photoType', 'Unknown')
                            ui.label(f"Type: {photo_type}").classes("text-sm font-medium")

                            if description := photo.get('description'):
                                ui.label(description).classes("text-sm italic text-gray-700 mb-1")

                            if added_by := photo.get('addedBy'):
                                ui.label(f"Added by: {added_by}").classes("text-xs text-gray-600")

                            if added_date := photo.get('addedDate'):
                                ui.label(f"Date: {added_date}").classes("text-xs text-gray-600")

                        # Download button
                        ui.button(
                            "Download",
                            icon="download",
                            on_click=lambda p=photo: self._download_photo(item, p),
                        ).props("dense outline")

    def _show_load_dialog(self) -> None:
        """Show dialog to load Find a Grave batch."""
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label("Load Find a Grave Batch").classes("font-bold text-lg mb-4")

            ui.label("Batch Size:").classes("font-medium mb-2")
            batch_size = ui.number(
                label="Number of people to load",
                value=20,
                min=1,
                max=500,
            ).props("outlined").classes("w-full mb-4")

            ui.label("Offset (starting position):").classes("font-medium mb-2")
            offset_input = ui.number(
                label="Skip first N people",
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
                    on_click=lambda: self._load_batch(
                        int(batch_size.value),
                        int(offset_input.value),
                        dialog,
                    ),
                ).props("color=primary")

        dialog.open()

    def _load_batch(self, batch_size: int, offset: int, dialog: ui.dialog) -> None:
        """Load Find a Grave batch from database."""
        dialog.close()

        ui.notify(f"Loading {batch_size} people (offset: {offset})...", type="info")

        try:
            from rmcitecraft.database.findagrave_queries import find_findagrave_people

            result = find_findagrave_people(
                db_path=str(self.config.rm_database_path),
                limit=batch_size,
                offset=offset,
            )

            if not result['people']:
                warning_msg = "No people found with Find a Grave URLs"
                ui.notify(warning_msg, type="warning")
                self.error_log.add_warning(warning_msg, context="Find a Grave Batch")
                return

            # Create session
            self.controller.create_session(result['people'])
            self.selected_item_ids = set()

            # Refresh UI
            self.container.clear()
            with self.container:
                self._render_header()
                self._render_batch_view()

            # Notify user
            load_msg = (
                f"Loaded {len(result['people'])} people "
                f"(examined {result['examined']}, excluded {result['excluded']})"
            )
            ui.notify(load_msg, type="positive")
            self.error_log.add_info(load_msg, context="Find a Grave Batch")

            # Log exclusion details if any were excluded
            if result['excluded'] > 0 and result.get('excluded_people'):
                excluded_people = result['excluded_people']
                excluded_names = [f"{p['full_name']} (ID {p['person_id']})" for p in excluded_people[:5]]

                if len(excluded_people) <= 5:
                    exclusion_detail = f"Excluded {len(excluded_people)} people (already have citations): {', '.join(excluded_names)}"
                else:
                    exclusion_detail = (
                        f"Excluded {len(excluded_people)} people (already have citations). "
                        f"First 5: {', '.join(excluded_names)}..."
                    )

                self.error_log.add_info(exclusion_detail, context="Find a Grave Batch")

        except Exception as e:
            logger.error(f"Failed to load batch: {e}")
            error_msg = f"Error loading batch: {e}"
            ui.notify(error_msg, type="negative")
            self.error_log.add_error(error_msg, context="Find a Grave Batch")

    def _show_resume_dialog(self) -> None:
        """Show dialog to resume an interrupted batch session."""
        # Get resumable sessions
        sessions = self.state_repository.get_resumable_sessions()

        if not sessions:
            ui.notify("No resumable sessions found", type="info")
            return

        with ui.dialog() as dialog, ui.card().classes("w-[600px]"):
            ui.label("Resume Batch Session").classes("font-bold text-lg mb-4")

            if not sessions:
                ui.label("No incomplete sessions found").classes("text-gray-500 italic")
                ui.button("Close", on_click=dialog.close).props("flat")
                dialog.open()
                return

            ui.label("Select a session to resume:").classes("font-medium mb-2")

            # Table of sessions
            with ui.column().classes("w-full gap-2 mb-4"):
                for session in sessions:
                    created_at = datetime.fromisoformat(session['created_at']).strftime("%Y-%m-%d %H:%M:%S")
                    status = session['status']
                    total = session['total_items']
                    completed = session['completed_count']
                    errors = session['error_count']
                    pending = total - completed

                    with ui.card().classes("w-full p-3"):
                        with ui.row().classes("w-full items-center justify-between gap-2"):
                            # Session info (clickable)
                            with ui.column().classes("gap-0 flex-grow cursor-pointer hover:bg-gray-50 p-2 rounded").on(
                                "click", lambda s=session, d=dialog: self._resume_session(s['session_id'], d)
                            ):
                                with ui.row().classes("w-full items-center justify-between"):
                                    with ui.column().classes("gap-0"):
                                        ui.label(f"Session: {session['session_id']}").classes("font-semibold text-sm")
                                        ui.label(f"Created: {created_at}").classes("text-xs text-gray-600")
                                        ui.label(f"Status: {status}").classes("text-xs text-gray-600")

                                    with ui.column().classes("gap-0 text-right"):
                                        ui.label(f"{completed}/{total} complete").classes("text-sm font-semibold")
                                        if errors > 0:
                                            ui.label(f"{errors} errors").classes("text-xs text-red-600")
                                        if pending > 0:
                                            ui.label(f"{pending} pending").classes("text-xs text-blue-600")

                            # Delete button
                            ui.button(
                                icon="delete",
                                on_click=lambda s=session, d=dialog: self._delete_session(s['session_id'], d)
                            ).props("flat color=red size=sm").tooltip("Delete this session")

            # Actions
            with ui.row().classes("w-full justify-between gap-2"):
                ui.button(
                    "Clear All Sessions",
                    on_click=lambda d=dialog: self._clear_all_sessions(d),
                    icon="delete_sweep"
                ).props("flat color=orange")
                ui.button("Cancel", on_click=dialog.close).props("flat")

        dialog.open()

    def _resume_session(self, session_id: str, dialog: ui.dialog) -> None:
        """Resume batch processing from saved session."""
        dialog.close()

        ui.notify(f"Resuming session {session_id}...", type="info")

        try:
            # Get session and items from state DB
            session = self.state_repository.get_session(session_id)
            if not session:
                ui.notify("Session not found", type="negative")
                return

            state_items = self.state_repository.get_session_items(session_id)
            if not state_items:
                ui.notify("No items found in session", type="negative")
                return

            # Get person IDs from state items
            person_ids = [item['person_id'] for item in state_items]

            # Query RootsMagic database for full person data
            from rmcitecraft.database.findagrave_queries import get_findagrave_people_by_ids

            people = get_findagrave_people_by_ids(
                db_path=str(self.config.rm_database_path),
                person_ids=person_ids,
            )

            if not people:
                ui.notify("Could not load people from RootsMagic database", type="negative")
                return

            # Create people dict for fast lookup
            people_by_id = {p['person_id']: p for p in people}

            # Reconstruct batch items from state + RootsMagic data
            batch_items = []
            for state_item in state_items:
                person_id = state_item['person_id']
                person = people_by_id.get(person_id)

                if not person:
                    logger.warning(f"Person {person_id} not found in RootsMagic database, skipping")
                    continue

                # Parse status from state DB
                status_str = state_item['status']
                if status_str == 'complete':
                    status = FindAGraveStatus.COMPLETE
                elif status_str == 'error':
                    status = FindAGraveStatus.ERROR
                elif status_str in ('extracting', 'extracted', 'creating_citation', 'created_citation', 'downloading_images'):
                    status = FindAGraveStatus.QUEUED  # Resume from queued state
                else:
                    status = FindAGraveStatus.QUEUED

                # Create batch item
                item = FindAGraveBatchItem(
                    person_id=person['person_id'],
                    link_id=person['link_id'],
                    surname=person['surname'],
                    given_name=person['given_name'],
                    full_name=person['full_name'],
                    birth_year=person['birth_year'],
                    death_year=person['death_year'],
                    sex=person['sex'],
                    memorial_id=state_item['memorial_id'],
                    url=state_item['memorial_url'],
                    note=person.get('note'),
                    status=status,
                    extracted_data=state_item.get('extracted_data') or {},
                    source_id=state_item.get('created_source_id'),
                    citation_id=state_item.get('created_citation_id'),
                    burial_event_id=state_item.get('created_burial_event_id'),
                    error=state_item.get('error_message'),
                )

                batch_items.append(item)

            # Create session directly (we already have FindAGraveBatchItem objects)
            self.controller.session = FindAGraveBatchSession(
                session_id=session_id,
                items=batch_items,
            )
            self.selected_item_ids = set()

            # Store session ID for continuation
            self.current_session_id = session_id

            # Refresh UI
            self.container.clear()
            with self.container:
                self._render_header()
                self._render_batch_view()

            # Notify user
            pending_count = sum(1 for item in batch_items if item.status == FindAGraveStatus.QUEUED)
            resume_msg = (
                f"Resumed session {session_id}: "
                f"{len(batch_items)} total items, {pending_count} pending"
            )
            ui.notify(resume_msg, type="positive")
            self.error_log.add_info(resume_msg, context="Find a Grave Batch")

            logger.info(f"Resumed batch session {session_id} with {len(batch_items)} items")

        except Exception as e:
            logger.error(f"Failed to resume session: {e}")
            error_msg = f"Error resuming session: {e}"
            ui.notify(error_msg, type="negative")
            self.error_log.add_error(error_msg, context="Find a Grave Batch")

    def _delete_session(self, session_id: str, dialog: ui.dialog) -> None:
        """Delete a single session."""
        try:
            self.state_repository.delete_session(session_id)
            ui.notify(f"Deleted session {session_id}", type="positive")
            logger.info(f"User deleted session: {session_id}")

            # Close and reopen dialog to refresh the list
            dialog.close()
            self._show_resume_dialog()

        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            ui.notify(f"Error deleting session: {e}", type="negative")

    def _clear_all_sessions(self, dialog: ui.dialog) -> None:
        """Clear all batch sessions with confirmation."""
        def confirm_clear():
            try:
                count = self.state_repository.clear_all_sessions()
                ui.notify(f"Cleared {count} sessions", type="warning")
                logger.warning(f"User cleared all batch sessions ({count} sessions)")

                # Close dialogs
                confirm_dialog.close()
                dialog.close()

            except Exception as e:
                logger.error(f"Failed to clear sessions: {e}")
                ui.notify(f"Error clearing sessions: {e}", type="negative")

        # Confirmation dialog
        with ui.dialog() as confirm_dialog, ui.card():
            ui.label("Clear All Sessions?").classes("font-bold text-lg mb-2")
            ui.label(
                "This will permanently delete ALL batch state data. "
                "Use this when you've restored your RootsMagic database from backup."
            ).classes("text-sm text-gray-700 mb-4 max-w-md")
            ui.label("This action cannot be undone.").classes("text-sm font-semibold text-red-600 mb-4")

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=confirm_dialog.close).props("flat")
                ui.button(
                    "Clear All Sessions",
                    on_click=confirm_clear,
                    icon="delete_sweep"
                ).props("color=red")

        confirm_dialog.open()

    def _show_reset_database_dialog(self) -> None:
        """Show dialog to reset state database (accessible anytime)."""
        def confirm_reset():
            try:
                count = self.state_repository.clear_all_sessions()
                ui.notify(f"Reset complete: cleared {count} sessions", type="warning")
                logger.warning(f"User reset state database ({count} sessions cleared)")
                confirm_dialog.close()

            except Exception as e:
                logger.error(f"Failed to reset state database: {e}")
                ui.notify(f"Error resetting database: {e}", type="negative")

        # Confirmation dialog
        with ui.dialog() as confirm_dialog, ui.card():
            ui.label("Reset State Database?").classes("font-bold text-lg mb-2")
            ui.label(
                "This will permanently delete ALL batch state data."
            ).classes("text-sm text-gray-700 mb-2")
            ui.label(
                "Use this when you've restored your RootsMagic database from backup "
                "and the state database is out of sync."
            ).classes("text-sm text-gray-700 mb-4 max-w-md")
            ui.label("This action cannot be undone.").classes("text-sm font-semibold text-red-600 mb-4")

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=confirm_dialog.close).props("flat")
                ui.button(
                    "Reset State Database",
                    on_click=confirm_reset,
                    icon="delete_sweep"
                ).props("color=red")

        confirm_dialog.open()

    async def _extract_item_data(self, item: FindAGraveBatchItem) -> None:
        """Extract data from Find a Grave for a single item."""
        item.status = FindAGraveStatus.EXTRACTING

        try:
            logger.info(f"Extracting data for {item.full_name}...")

            # Extract memorial data
            memorial_data = await self.automation.extract_memorial_data(item.url)

            if not memorial_data:
                raise Exception("Failed to extract memorial data")

            # Update item with extracted data
            self.controller.update_item_extracted_data(item, memorial_data)

            logger.info(f"Extracted data for {item.full_name}")

            # Refresh detail view
            self.detail_container.clear()
            with self.detail_container:
                self._render_item_details()

        except Exception as e:
            logger.error(f"Failed to extract data for {item.person_id}: {e}")
            self.controller.mark_item_error(item, str(e))

            # Refresh to show error
            self.detail_container.clear()
            with self.detail_container:
                self._render_item_details()

    def _get_spouse_surname(self, person_id: int) -> str | None:
        """
        Get spouse's surname for person (used when person has no surname).

        Args:
            person_id: Person ID

        Returns:
            Spouse's surname or None
        """
        from rmcitecraft.database.connection import connect_rmtree

        conn = connect_rmtree(self.config.rm_database_path)
        cursor = conn.cursor()

        try:
            # Find spouse through FamilyTable
            cursor.execute("""
                SELECT n.Surname
                FROM FamilyTable f
                JOIN NameTable n ON (CASE
                    WHEN f.MotherID = ? THEN f.FatherID
                    ELSE f.MotherID
                END) = n.OwnerID
                WHERE f.FatherID = ? OR f.MotherID = ?
                LIMIT 1
            """, (person_id, person_id, person_id))

            result = cursor.fetchone()
            return result[0] if result and result[0] else None

        finally:
            conn.close()

    async def _download_photo(self, item: FindAGraveBatchItem, photo: dict) -> None:
        """Download a photo from Find a Grave using browser automation."""
        ui.notify("Downloading photo...", type="info")

        try:
            # Determine surname for filename
            surname = item.surname
            if not surname or surname.strip() == '':
                # Try to get spouse's surname
                spouse_surname = self._get_spouse_surname(item.person_id)
                if spouse_surname:
                    surname = f"[{spouse_surname}]"
                else:
                    surname = ""

            # Determine photo type
            photo_type = photo.get('photoType', '').strip()
            logger.info(f"Photo type detected: '{photo_type}'")

            # Generate filename (all photos include maiden name if female)
            base_filename = generate_image_filename(
                surname=surname,
                given_name=item.given_name,
                maiden_name=item.maiden_name,
                birth_year=item.birth_year,
                death_year=item.death_year,
            )

            # Determine directory based on photo type
            if photo_type == 'Person':
                download_dir = Path.home() / "Genealogy/RootsMagic/Files/Pictures - People"
            elif photo_type == 'Family':
                # TODO: Confirm where Family photos should go
                download_dir = Path.home() / "Genealogy/RootsMagic/Files/Pictures - People"
            elif photo_type == 'Grave':
                download_dir = Path.home() / "Genealogy/RootsMagic/Files/Pictures - Cemetaries"
            else:
                # Other or undefined
                download_dir = Path.home() / "Genealogy/RootsMagic/Files/Pictures - Other"

            download_dir.mkdir(parents=True, exist_ok=True)

            # Check for existing files and add counter if needed (for Grave photos with multiples)
            filename = base_filename
            if photo_type == 'Grave':
                # Check if file exists, add counter
                base_name = base_filename.rsplit('.', 1)[0]  # Remove .jpg
                extension = base_filename.rsplit('.', 1)[1]  # Get extension
                counter = 1
                test_path = download_dir / filename

                while test_path.exists():
                    filename = f"{base_name}_{counter}.{extension}"
                    test_path = download_dir / filename
                    counter += 1

            download_path = download_dir / filename

            # Download photo using browser automation (maintains authentication)
            image_url = photo.get('imageUrl', '')
            success = await self.automation.download_photo(
                image_url,
                item.memorial_id,
                download_path,
            )

            if success:
                item.downloaded_images.append(str(download_path))
                success_msg = f"Downloaded photo to {download_path}"
                ui.notify(success_msg, type="positive")
                self.error_log.add_info(success_msg, context="Find a Grave Batch")

                # Create database record for the image and link to citation
                if item.citation_id:
                    try:
                        from rmcitecraft.database.findagrave_queries import create_findagrave_image_record

                        # Extract contributor and photo ID from photo metadata
                        contributor = photo.get('addedBy', '')
                        photo_id = photo.get('photoId', '')

                        # Create the media record and links
                        media_info = create_findagrave_image_record(
                            db_path=self.config.rm_database_path,
                            citation_id=item.citation_id,
                            person_id=item.person_id,
                            image_path=str(download_path),
                            photo_type=photo_type,
                            memorial_id=item.memorial_id,
                            photo_id=photo_id,
                            contributor=contributor,
                            person_name=item.extracted_data.get('personName', item.full_name),
                            cemetery_name=item.cemetery_name or '',
                            cemetery_city=item.extracted_data.get('cemeteryCity', ''),
                            cemetery_county=item.extracted_data.get('cemeteryCounty', ''),
                            cemetery_state=item.extracted_data.get('cemeteryState', ''),
                            media_root=self.config.rm_media_root_directory,
                        )

                        # Store media ID with the downloaded image info
                        item.downloaded_images[-1] = {
                            'path': str(download_path),
                            'media_id': media_info['media_id'],
                            'photo_type': photo_type,
                        }

                        db_msg = f"Created media record ID {media_info['media_id']} and linked to citation"
                        logger.info(db_msg)
                        self.error_log.add_info(db_msg, context="Find a Grave Batch")

                    except Exception as e:
                        error_msg = f"Failed to create database record for image: {e}"
                        logger.error(error_msg, exc_info=True)
                        self.error_log.add_error(error_msg, context="Find a Grave Batch")
                        # Don't fail the download itself, just log the database error
            else:
                error_msg = "Failed to download photo"
                ui.notify(error_msg, type="negative")
                self.error_log.add_error(error_msg, context="Find a Grave Batch")

        except Exception as e:
            logger.error(f"Error downloading photo: {e}", exc_info=True)
            error_msg = f"Error downloading photo: {e}"
            ui.notify(error_msg, type="negative")
            self.error_log.add_error(error_msg, context="Find a Grave Batch")

    async def _download_photo_for_batch(
        self,
        item: FindAGraveBatchItem,
        photo: dict,
        citation_id: int
    ) -> None:
        """
        Download a photo during batch processing (no UI notifications).

        Args:
            item: The batch item
            photo: Photo metadata from Find a Grave
            citation_id: Citation ID to link the image to
        """
        try:
            # Determine surname for filename
            surname = item.surname
            if not surname or surname.strip() == '':
                # Try to get spouse's surname
                spouse_surname = self._get_spouse_surname(item.person_id)
                if spouse_surname:
                    surname = f"[{spouse_surname}]"
                else:
                    surname = ""

            # Determine photo type
            photo_type = photo.get('photoType', '').strip()
            logger.info(f"Batch download - Photo type: '{photo_type}'")

            # Generate filename (all photos include maiden name if female)
            base_filename = generate_image_filename(
                surname=surname,
                given_name=item.given_name,
                maiden_name=item.maiden_name,
                birth_year=item.birth_year,
                death_year=item.death_year,
            )

            # Determine directory based on photo type
            if photo_type == 'Person':
                download_dir = Path.home() / "Genealogy/RootsMagic/Files/Pictures - People"
            elif photo_type == 'Family':
                download_dir = Path.home() / "Genealogy/RootsMagic/Files/Pictures - People"
            elif photo_type == 'Grave':
                download_dir = Path.home() / "Genealogy/RootsMagic/Files/Pictures - Cemetaries"
            else:
                download_dir = Path.home() / "Genealogy/RootsMagic/Files/Pictures - Other"

            download_dir.mkdir(parents=True, exist_ok=True)

            # Check for existing files and add counter if needed (for Grave photos)
            filename = base_filename
            if photo_type == 'Grave':
                base_name = base_filename.rsplit('.', 1)[0]
                extension = base_filename.rsplit('.', 1)[1]
                counter = 1
                test_path = download_dir / filename

                while test_path.exists():
                    filename = f"{base_name}_{counter}.{extension}"
                    test_path = download_dir / filename
                    counter += 1

            download_path = download_dir / filename

            # Download photo using browser automation
            image_url = photo.get('imageUrl', '')
            success = await self.automation.download_photo(
                image_url,
                item.memorial_id,
                download_path,
            )

            if success:
                logger.info(f"Successfully downloaded: {download_path}")

                # Create database record for the image and link to citation
                try:
                    from rmcitecraft.database.findagrave_queries import create_findagrave_image_record

                    contributor = photo.get('addedBy', '')
                    photo_id = photo.get('photoId', '')

                    # Create the media record and links
                    media_info = create_findagrave_image_record(
                        db_path=self.config.rm_database_path,
                        citation_id=citation_id,
                        person_id=item.person_id,
                        image_path=str(download_path),
                        photo_type=photo_type,
                        memorial_id=item.memorial_id,
                        photo_id=photo_id,
                        contributor=contributor,
                        person_name=item.extracted_data.get('personName', item.full_name),
                        cemetery_name=item.cemetery_name or '',
                        cemetery_city=item.extracted_data.get('cemeteryCity', ''),
                        cemetery_county=item.extracted_data.get('cemeteryCounty', ''),
                        cemetery_state=item.extracted_data.get('cemeteryState', ''),
                        media_root=self.config.rm_media_root_directory,
                    )

                    # Store in item's downloaded images list
                    item.downloaded_images.append({
                        'path': str(download_path),
                        'media_id': media_info['media_id'],
                        'photo_type': photo_type,
                    })

                    logger.info(f"Created media record ID {media_info['media_id']}")

                except Exception as db_error:
                    logger.error(f"Failed to create database record for image: {db_error}", exc_info=True)
                    self.error_log.add_error(
                        f"Failed to create database record for image: {db_error}",
                        context="Find a Grave Batch"
                    )
                    # Don't fail the download itself, just log the database error
            else:
                logger.warning(f"Failed to download photo from {image_url}")
                self.error_log.add_warning(
                    f"Failed to download photo for {item.full_name}",
                    context="Find a Grave Batch"
                )

        except Exception as e:
            logger.error(f"Error downloading photo in batch: {e}", exc_info=True)
            self.error_log.add_error(
                f"Error downloading photo for {item.full_name}: {e}",
                context="Find a Grave Batch"
            )
            raise

    async def _show_place_approval_dialog(
        self,
        item: FindAGraveBatchItem,
        match_info: dict,
    ) -> dict[str, any] | None:
        """
        Show place approval dialog and wait for user decision.

        Args:
            item: The batch item needing approval
            match_info: Match information including candidates

        Returns:
            Dictionary with 'action' ('add_new', 'select_existing', 'abort')
            and 'selected_place_id' if action is 'select_existing'
            Returns None if dialog was cancelled
        """
        # Use a mutable object to store result
        class Result:
            def __init__(self):
                self.action = None
                self.selected_place_id = None

        result = Result()
        candidates = match_info.get('candidates', [])
        cemetery_name = match_info.get('cemetery_name', '')
        location_name = match_info.get('findagrave_location', '')
        gazetteer_validation = match_info.get('gazetteer_validation', {})

        # Ensure we're in the correct UI context for creating the dialog
        if not self.ui_context:
            logger.error("No UI context available for place approval dialog")
            return None

        with self.ui_context:
            # Sort state for the table
            sort_by = {'field': 'combined_score', 'reverse': True}  # Default: sort by combined score descending
            selected_place_id = {'value': candidates[0]['place_id'] if candidates else None}

            def update_table():
                """Update the candidates table with current sort."""
                sorted_candidates = sorted(
                    candidates,
                    key=lambda x: x.get(sort_by['field'], 0),
                    reverse=sort_by['reverse']
                )

                table_container.clear()
                with table_container:
                    with ui.table(
                        columns=[
                            {'name': 'name', 'label': 'Place Name', 'field': 'name', 'align': 'left', 'sortable': True},
                            {'name': 'combined_score', 'label': 'Score', 'field': 'combined_score', 'align': 'right', 'sortable': True},
                            {'name': 'similarity', 'label': 'PlaceTable Match', 'field': 'similarity', 'align': 'right', 'sortable': True},
                            {'name': 'usage_count', 'label': 'Usage', 'field': 'usage_count', 'align': 'right', 'sortable': True},
                        ],
                        rows=sorted_candidates,
                        row_key='place_id',
                        selection='single',
                    ).props('dense flat bordered') as table:
                        table.classes('w-full')

                        # Set initial selection
                        if selected_place_id['value']:
                            table.selected = [next((c for c in sorted_candidates if c['place_id'] == selected_place_id['value']), None)]

                        # Handle selection change
                        def on_selection(e):
                            if e.selection:
                                selected_place_id['value'] = e.selection[0]['place_id']

                        table.on('selection', on_selection)

                        # Custom column formatting
                        table.add_slot('body-cell-combined_score', '''
                            <q-td key="combined_score" :props="props">
                                <strong>{{ props.row.combined_score }}</strong>
                            </q-td>
                        ''')

                        table.add_slot('body-cell-similarity', '''
                            <q-td key="similarity" :props="props">
                                {{ (props.row.similarity * 100).toFixed(1) }}%
                            </q-td>
                        ''')

            def toggle_sort(field):
                """Toggle sort field and direction."""
                if sort_by['field'] == field:
                    sort_by['reverse'] = not sort_by['reverse']
                else:
                    sort_by['field'] = field
                    sort_by['reverse'] = field in ['combined_score', 'similarity', 'usage_count']  # Default descending for scores
                update_table()

            with ui.dialog().props('persistent') as dialog, ui.card().classes('w-[800px]'):
                ui.label('Burial Place Approval Required').classes('text-lg font-bold mb-4')

                # Show Find a Grave information
                with ui.card().classes('w-full bg-blue-50 p-3 mb-4'):
                    ui.label('Find a Grave Information').classes('font-semibold mb-2')
                    ui.label(f'Cemetery: {cemetery_name}').classes('text-sm')
                    ui.label(f'Location: {location_name}').classes('text-sm')
                    ui.label(f'Person: {item.full_name}').classes('text-sm font-semibold')

                # Show proposed new place name
                with ui.card().classes('w-full bg-green-50 p-3 mb-4'):
                    ui.label('Proposed New Place').classes('font-semibold mb-2')
                    ui.label(f'Location: {location_name}').classes('text-sm')
                    ui.label(f'Cemetery: {cemetery_name}').classes('text-sm')

                # Show gazetteer validation status
                if gazetteer_validation:
                    confidence = gazetteer_validation.get('confidence', 'unknown')
                    validated_count = gazetteer_validation.get('validated_count', 0)
                    total_count = gazetteer_validation.get('total_components', 0)
                    components = gazetteer_validation.get('components', {})

                    # Determine card color based on confidence
                    if confidence == 'high':
                        card_class = 'w-full bg-green-100 p-3 mb-4'
                        icon = 'check_circle'
                        icon_color = 'positive'
                    elif confidence == 'medium':
                        card_class = 'w-full bg-yellow-50 p-3 mb-4'
                        icon = 'warning'
                        icon_color = 'warning'
                    else:
                        card_class = 'w-full bg-orange-50 p-3 mb-4'
                        icon = 'error_outline'
                        icon_color = 'negative'

                    with ui.card().classes(card_class):
                        with ui.row().classes('items-center gap-2 mb-2'):
                            ui.icon(icon).props(f'color={icon_color}')
                            ui.label('Gazetteer Validation').classes('font-semibold')
                            ui.label(f'({validated_count}/{total_count} components validated - {confidence} confidence)').classes('text-sm text-gray-600')

                        # Show component validation details
                        with ui.column().classes('gap-1'):
                            for comp_name in ['city', 'county', 'state', 'country']:
                                comp_data = components.get(comp_name, {})
                                comp_place_name = comp_data.get('name')

                                if comp_place_name:
                                    exists = comp_data.get('exists', False)
                                    fuzzy = comp_data.get('fuzzy', False)

                                    # Determine icon
                                    if exists:
                                        check_icon = '✓'
                                        check_color = 'text-green-600'
                                        match_type = ' (fuzzy)' if fuzzy else ''
                                    else:
                                        check_icon = '✗'
                                        check_color = 'text-red-600'
                                        match_type = ' (not found)'

                                    ui.html(
                                        content=f'<span class="{check_color} text-sm">'
                                        f'{check_icon} <strong>{comp_name.title()}:</strong> {comp_place_name}{match_type}'
                                        f'</span>',
                                        sanitize=False
                                    )

                # Show existing place candidates
                ui.label('Existing Places (Sorted by Combined Score)').classes('font-semibold mb-2')

                if candidates:
                    # Table container that will be updated when sorting
                    table_container = ui.column().classes('w-full')
                    update_table()
                else:
                    ui.label('No existing places found in database').classes('text-gray-500 italic')

                # Action buttons
                with ui.row().classes('w-full justify-end gap-2 mt-4'):
                    def on_add_new():
                        result.action = 'add_new'
                        dialog.close()

                    def on_select_existing():
                        if selected_place_id['value']:
                            result.action = 'select_existing'
                            result.selected_place_id = selected_place_id['value']
                            dialog.close()

                    def on_abort():
                        result.action = 'abort'
                        dialog.close()

                    ui.button(
                        'Add New Place',
                        icon='add_location',
                        on_click=on_add_new
                    ).props('color=primary')

                    ui.button(
                        'Select Existing Place',
                        icon='check_circle',
                        on_click=on_select_existing
                    ).props('color=positive').bind_enabled_from(selected_place_id, 'value', lambda v: v is not None)

                    ui.button(
                        'Abort Batch',
                        icon='cancel',
                        on_click=on_abort
                    ).props('color=negative outline')

            dialog.open()
            await dialog  # Wait for dialog to close

            # Return None if no action was taken
            if result.action is None:
                return None

            return {
                'action': result.action,
                'selected_place_id': result.selected_place_id,
        }

    def _show_citation_matching_report(self, report_data: list[dict]) -> None:
        """
        Display citation matching report after batch processing.

        Shows spouse and parent citation matching results with color coding:
        - Green for successful matches (above 60% threshold)
        - Red for failed matches (below 60% threshold)

        Args:
            report_data: List of dicts with person_name, person_id, spouse_matches, parent_match_info
        """
        # Filter to only entries with spouse or parent data
        entries_with_data = [
            entry for entry in report_data
            if entry.get('spouse_matches') or entry.get('parent_match_info')
        ]

        if not entries_with_data:
            return  # Nothing to report

        with ui.dialog().props('maximized') as report_dialog, ui.card().classes('w-full max-w-4xl p-6'):
            ui.label('Citation Matching Report').classes('text-2xl font-bold mb-4')

            # === SPOUSE MATCHING SECTION ===
            spouse_entries = [e for e in entries_with_data if e.get('spouse_matches')]

            if spouse_entries:
                ui.label('Spouse Citation Matches').classes('text-xl font-bold mt-4 mb-2')
                ui.label(f'{len(spouse_entries)} entr{"y" if len(spouse_entries) == 1 else "ies"} with spouse data').classes('text-sm text-gray-600 mb-4')

                # Table header
                with ui.grid(columns=6).classes('w-full gap-2 mb-2'):
                    ui.label('Target Name').classes('font-bold text-xs')
                    ui.label('Person ID').classes('font-bold text-xs')
                    ui.label('RM Spouse Name').classes('font-bold text-xs')
                    ui.label('Spouse ID').classes('font-bold text-xs')
                    ui.label('Find a Grave Name').classes('font-bold text-xs')
                    ui.label('Match %').classes('font-bold text-xs')

                # Table rows
                for entry in spouse_entries:
                    for spouse_match in entry['spouse_matches']:
                        matched = spouse_match['matched']
                        text_color = 'text-green-700' if matched else 'text-red-700'

                        with ui.grid(columns=6).classes(f'w-full gap-2 {text_color}'):
                            ui.label(entry['person_name']).classes('text-xs')
                            ui.label(str(entry['person_id'])).classes('text-xs')
                            ui.label(spouse_match['db_name'] or 'N/A').classes('text-xs')
                            ui.label(str(spouse_match['db_person_id']) if spouse_match['db_person_id'] else 'N/A').classes('text-xs')
                            ui.label(spouse_match['fg_name']).classes('text-xs')
                            ui.label(f"{spouse_match['match_score']:.1%}").classes('text-xs font-bold')

            # === PARENT MATCHING SECTION ===
            parent_entries = [e for e in entries_with_data if e.get('parent_match_info')]

            if parent_entries:
                ui.separator().classes('my-6')
                ui.label('Parent Citation Matches').classes('text-xl font-bold mt-4 mb-2')

                # Count successes and failures
                total_with_parents = len(parent_entries)
                successful_parents = sum(1 for e in parent_entries if e['parent_match_info'].get('matched'))
                failed_parents = total_with_parents - successful_parents

                ui.label(
                    f'({successful_parents}/{total_with_parents}) entries with parents successfully cited'
                ).classes('text-sm mb-4')

                if failed_parents > 0:
                    ui.label('Failures:').classes('text-md font-bold text-red-700 mt-2 mb-2')

                    for entry in parent_entries:
                        if not entry['parent_match_info'].get('matched'):
                            with ui.row().classes('text-xs text-red-700 ml-4'):
                                ui.label(f"{entry['person_name']} (Person ID {entry['person_id']}) - No parent family found in database")

            # Close button
            with ui.row().classes('w-full justify-end mt-6'):
                ui.button('Close', on_click=report_dialog.close).props('flat')

        report_dialog.open()

    def _show_image_download_summary(self) -> None:
        """Display summary of downloaded images after batch processing."""
        if not self.controller.session:
            return

        # Collect all downloaded images across all items
        total_images = 0
        images_by_type = {'Person': 0, 'Grave': 0, 'Family': 0, 'Other': 0}
        people_with_images = []

        for item in self.controller.session.items:
            if item.downloaded_images:
                person_images = []
                for img_info in item.downloaded_images:
                    # Handle both old format (string) and new format (dict)
                    if isinstance(img_info, dict):
                        photo_type = img_info.get('photo_type', 'Other')
                        images_by_type[photo_type] = images_by_type.get(photo_type, 0) + 1
                        person_images.append({
                            'type': photo_type,
                            'path': img_info.get('path', ''),
                            'media_id': img_info.get('media_id'),
                        })
                    else:
                        # Legacy string format
                        images_by_type['Other'] += 1
                        person_images.append({
                            'type': 'Other',
                            'path': str(img_info),
                            'media_id': None,
                        })
                    total_images += 1

                people_with_images.append({
                    'name': item.full_name,
                    'person_id': item.person_id,
                    'images': person_images,
                })

        # Only show summary if images were downloaded
        if total_images == 0:
            return

        # Create summary dialog
        with ui.dialog() as img_dialog, ui.card().classes('w-full max-w-2xl p-6'):
            ui.label('Downloaded Images Summary').classes('text-2xl font-bold mb-4')

            # Overall statistics
            with ui.row().classes('w-full gap-4 mb-4'):
                with ui.card().classes('p-3'):
                    ui.label(f'{total_images}').classes('text-3xl font-bold text-primary')
                    ui.label('Total Images').classes('text-sm text-gray-600')

                with ui.card().classes('p-3'):
                    ui.label(f'{len(people_with_images)}').classes('text-2xl font-bold text-primary')
                    ui.label('People with Images').classes('text-sm text-gray-600')

            # Images by type
            ui.label('Images by Type').classes('text-lg font-bold mt-4 mb-2')
            with ui.row().classes('w-full gap-2'):
                for photo_type, count in images_by_type.items():
                    if count > 0:
                        with ui.card().classes('p-2'):
                            ui.label(f'{count}').classes('text-xl font-bold')
                            ui.label(photo_type).classes('text-xs text-gray-600')

            # Details by person (collapsible)
            if len(people_with_images) <= 10:
                # Show expanded for small batches
                ui.label('Downloaded Images by Person').classes('text-lg font-bold mt-4 mb-2')
                for person_info in people_with_images:
                    with ui.expansion(
                        f"{person_info['name']} ({len(person_info['images'])} image{'s' if len(person_info['images']) != 1 else ''})",
                        icon='person'
                    ).classes('w-full'):
                        for img in person_info['images']:
                            with ui.row().classes('items-center gap-2 text-sm'):
                                ui.icon('image').classes('text-gray-400')
                                ui.label(f"{img['type']} Photo")
                                if img['media_id']:
                                    ui.label(f"(Media ID: {img['media_id']})").classes('text-xs text-gray-500')

            # Summary message
            ui.separator().classes('my-4')
            success_msg = f"Successfully downloaded {total_images} image{'s' if total_images != 1 else ''} for {len(people_with_images)} {'people' if len(people_with_images) != 1 else 'person'}"
            ui.label(success_msg).classes('text-sm text-green-600')

            # Log to error log
            self.error_log.add_info(success_msg, context="Find a Grave Batch")

            # Close button
            with ui.row().classes('w-full justify-end mt-4'):
                ui.button('Close', on_click=img_dialog.close).props('flat')

        img_dialog.open()

    async def _start_batch_processing(self) -> None:
        """Start batch processing of selected items with crash recovery and state persistence."""
        if not self.controller.session:
            warning_msg = "No batch loaded"
            ui.notify(warning_msg, type="warning")
            self.error_log.add_warning(warning_msg, context="Find a Grave Batch")
            return

        # Get items to process (selected or all pending)
        if self.selected_item_ids:
            items_to_process = [
                item for item in self.controller.session.items
                if item.person_id in self.selected_item_ids
            ]
        else:
            items_to_process = [
                item for item in self.controller.session.items
                if item.status == FindAGraveStatus.QUEUED
            ]

        if not items_to_process:
            warning_msg = "No items to process"
            ui.notify(warning_msg, type="warning")
            self.error_log.add_warning(warning_msg, context="Find a Grave Batch")
            return

        # Create session in state database for persistence
        session_id = f"batch_{int(datetime.now(timezone.utc).timestamp())}"
        self.current_session_id = session_id

        try:
            config_snapshot = {
                'base_timeout': self.config.findagrave_base_timeout_seconds,
                'max_retries': self.config.findagrave_max_retries,
                'adaptive_timeout_enabled': self.config.findagrave_enable_adaptive_timeout,
                'crash_recovery_enabled': self.config.findagrave_enable_crash_recovery,
            }

            self.state_repository.create_session(
                session_id=session_id,
                total_items=len(items_to_process),
                config_snapshot=config_snapshot,
            )
            self.state_repository.start_session(session_id)
            logger.info(f"Created state tracking session: {session_id}")

            # Create items in state database
            for item in items_to_process:
                self.state_repository.create_item(
                    session_id=session_id,
                    person_id=item.person_id,
                    memorial_id=item.memorial_id,
                    memorial_url=item.url,
                    person_name=item.full_name,
                )
        except Exception as e:
            logger.error(f"Failed to create state tracking session: {e}")
            # Continue without state tracking (non-fatal)

        # Create progress dialog
        with ui.dialog().props('persistent') as progress_dialog, ui.card().classes('w-96'):
            ui.label('Processing Find a Grave Memorials').classes('text-lg font-bold mb-4')

            progress_label = ui.label('Starting...').classes('text-sm mb-2')
            progress_bar = ui.linear_progress(value=0).props('instant-feedback')

            status_label = ui.label('').classes('text-xs text-gray-600 mt-2')
            health_label = ui.label('').classes('text-xs text-blue-600 mt-1')

        progress_dialog.open()

        processed = 0
        total = len(items_to_process)

        # Collect citation matching data for end-of-batch report
        citation_report_data = []

        # Reset recovery counter at start of batch
        if self.config.findagrave_enable_crash_recovery:
            self.recovery_manager.reset_recovery_counter()

        for i, item in enumerate(items_to_process, 1):
            # Update progress
            progress_label.text = f"Processing {i} of {total}: {item.full_name}"
            progress_bar.value = i / total
            status_label.text = f"{processed} completed"

            # Get state item ID for tracking
            try:
                state_items = self.state_repository.get_session_items(session_id)
                state_item = next(
                    (si for si in state_items if si['person_id'] == item.person_id),
                    None
                )
                self.current_state_item_id = state_item['id'] if state_item else None
            except Exception:
                self.current_state_item_id = None

            try:
                # ===== PHASE 1: PAGE HEALTH CHECK =====
                if self.config.findagrave_enable_crash_recovery:
                    health_label.text = "Checking page health..."

                    page = await self.automation.get_or_create_page()
                    health = await self.health_monitor.check_page_health(page)

                    if not health.is_healthy:
                        logger.warning(f"Page unhealthy: {health.error}")
                        health_label.text = f"⚠️ Page issue: {health.error}"

                        # Attempt recovery
                        status_label.text = "Recovering from page crash..."
                        recovered_page = await self.recovery_manager.attempt_recovery(
                            page, self.automation
                        )

                        if not recovered_page:
                            raise Exception(f"Failed to recover page: {health.error}")

                        logger.info("Page recovery successful")
                        health_label.text = "✓ Page recovered"
                    else:
                        health_label.text = "✓ Page healthy"

                # ===== PHASE 2: DUPLICATE CHECK =====
                status_label.text = "Checking for duplicates..."

                duplicate_check = check_citation_exists_detailed(
                    db_path=self.config.rm_database_path,
                    person_id=item.person_id,
                    memorial_id=item.memorial_id,
                    memorial_url=item.url,
                )

                if duplicate_check['exists']:
                    logger.warning(
                        f"Skipping {item.full_name} (PersonID {item.person_id}): {duplicate_check['details']}"
                    )
                    self.controller.mark_item_error(
                        item,
                        f"Duplicate: {duplicate_check['details']}"
                    )

                    if self.current_state_item_id:
                        self.state_repository.update_item_status(
                            self.current_state_item_id,
                            'error',
                            error_message=duplicate_check['details']
                        )

                    continue

                # ===== PHASE 3: EXTRACTION WITH RETRY & ADAPTIVE TIMEOUT =====
                item.status = FindAGraveStatus.EXTRACTING
                if self.current_state_item_id:
                    self.state_repository.update_item_status(
                        self.current_state_item_id,
                        'extracting'
                    )

                # Get current adaptive timeout
                if self.config.findagrave_enable_adaptive_timeout:
                    current_timeout = self.timeout_manager.get_current_timeout()
                    health_label.text = f"⏱️ Timeout: {current_timeout}s"
                else:
                    current_timeout = self.config.findagrave_base_timeout_seconds

                memorial_data = None
                extraction_start = time.time()

                # Wrap extraction in retry logic
                try:
                    async def extract_with_timeout():
                        """Extraction with adaptive timeout."""
                        return await self.automation.extract_memorial_data(
                            item.url,
                            timeout=current_timeout
                        )

                    memorial_data = await self.retry_strategy.retry_async(
                        extract_with_timeout
                    )

                    # Record successful extraction timing
                    extraction_duration = time.time() - extraction_start
                    self.timeout_manager.record_response_time(extraction_duration, success=True)

                    if self.current_state_item_id:
                        self.state_repository.record_metric(
                            operation='extraction',
                            duration_ms=int(extraction_duration * 1000),
                            success=True,
                            session_id=session_id
                        )

                except Exception as extraction_error:
                    # Record failed extraction timing
                    extraction_duration = time.time() - extraction_start
                    self.timeout_manager.record_response_time(extraction_duration, success=False)

                    if self.current_state_item_id:
                        self.state_repository.record_metric(
                            operation='extraction',
                            duration_ms=int(extraction_duration * 1000),
                            success=False,
                            session_id=session_id
                        )

                        # Increment retry count in state DB
                        retry_count = self.state_repository.increment_retry_count(
                            self.current_state_item_id
                        )

                        logger.error(
                            f"Extraction failed for {item.full_name} (PersonID {item.person_id}) "
                            f"(retry {retry_count}/{self.config.findagrave_max_retries}): "
                            f"{extraction_error}"
                        )

                    raise  # Re-raise to be caught by outer exception handler

                if not memorial_data:
                    raise Exception("Failed to extract memorial data")

                # Update item with extracted data
                self.controller.update_item_extracted_data(item, memorial_data)

                # Store extraction in state DB
                if self.current_state_item_id:
                    self.state_repository.update_item_extraction(
                        self.current_state_item_id,
                        extracted_data=memorial_data
                    )

                # ===== PHASE 4: CITATION FORMATTING =====
                status_label.text = "Formatting citation..."

                # Format citation using Find a Grave name (not database name)
                # Source name uses database name, but citations use Find a Grave name
                citation = format_findagrave_citation(
                    memorial_data=memorial_data,
                    person_name=memorial_data.get('personName', item.full_name),
                    birth_year=item.birth_year,
                    death_year=item.death_year,
                    maiden_name=memorial_data.get('maidenName'),
                )

                # Store formatted citations
                item.footnote = citation['footnote']
                item.short_footnote = citation['short_footnote']
                item.bibliography = citation['bibliography']

                # Generate source name
                source_name = generate_source_name(
                    surname=item.surname,
                    given_name=item.given_name,
                    maiden_name=memorial_data.get('maidenName'),
                    birth_year=item.birth_year,
                    death_year=item.death_year,
                    person_id=item.person_id,
                )

                # ===== PHASE 5: DATABASE WRITES =====
                status_label.text = "Writing to database..."

                if self.current_state_item_id:
                    self.state_repository.update_item_status(
                        self.current_state_item_id,
                        'creating_citation'
                    )

                citation_start = time.time()

                try:
                    result = create_findagrave_source_and_citation(
                        db_path=self.config.rm_database_path,
                        person_id=item.person_id,
                        source_name=source_name,
                        memorial_url=item.url,
                        footnote=citation['footnote'],
                        short_footnote=citation['short_footnote'],
                        bibliography=citation['bibliography'],
                        memorial_text=memorial_data.get('memorialText', ''),
                        source_comment=memorial_data.get('sourceComment', ''),
                    )

                    # Link citation directly to Person (ALWAYS)
                    try:
                        from rmcitecraft.database.findagrave_queries import link_citation_to_person
                        link_citation_to_person(
                            db_path=self.config.rm_database_path,
                            person_id=item.person_id,
                            citation_id=result['citation_id'],
                        )
                    except Exception as person_link_error:
                        logger.error(f"Failed to link citation to person: {person_link_error}")
                        # Don't fail the entire item, just log the error

                    # Link citation to families (conditional on family members mentioned)
                    try:
                        family_ids = link_citation_to_families(
                            db_path=self.config.rm_database_path,
                            person_id=item.person_id,
                            citation_id=result['citation_id'],
                            family_data=memorial_data.get('family'),
                        )
                        if family_ids:
                            logger.info(f"Linked citation to {len(family_ids)} parent families for {item.full_name} (PersonID {item.person_id})")
                    except Exception as family_link_error:
                        logger.warning(f"Failed to link citation to parent families: {family_link_error}")
                        # Don't fail the entire item, just log the warning

                    burial_event_id = None

                    # Create burial event BEFORE downloading images
                    # (so Grave/Cemetery photos can link to the burial event)
                    cemetery_name = memorial_data.get('cemeteryName', '')
                    cemetery_city = memorial_data.get('cemeteryCity', '')
                    cemetery_county = memorial_data.get('cemeteryCounty', '')
                    cemetery_state = memorial_data.get('cemeteryState', '')
                    cemetery_country = memorial_data.get('cemeteryCountry', '')

                    logger.info(
                        f"Burial event check for {item.full_name}:\n"
                        f"  Cemetery: {cemetery_name or 'NOT FOUND'}\n"
                        f"  City: {cemetery_city or 'NOT FOUND'}\n"
                        f"  County: {cemetery_county or 'NOT FOUND'}\n"
                        f"  State: {cemetery_state or 'NOT FOUND'}\n"
                        f"  Country: {cemetery_country or 'NOT FOUND'}"
                    )

                    if cemetery_name:
                        logger.info(f"Creating burial event for {item.full_name}...")

                        try:
                            burial_result = create_burial_event_and_link_citation(
                                db_path=self.config.rm_database_path,
                                person_id=item.person_id,
                                citation_id=result['citation_id'],
                                cemetery_name=cemetery_name,
                                cemetery_city=cemetery_city or '',
                                cemetery_county=cemetery_county or '',
                                cemetery_state=cemetery_state or '',
                                cemetery_country=cemetery_country or '',
                            )

                            # Successfully created burial event
                            burial_event_id = burial_result['burial_event_id']
                            logger.info(
                                f"Created burial event {burial_event_id} for {item.full_name}"
                            )

                        except Exception as burial_error:
                            logger.error(f"Failed to create burial event: {burial_error}", exc_info=True)
                            self.error_log.add_error(
                                f"Failed to create burial event for {item.full_name}: {burial_error}",
                                context="Find a Grave Batch"
                            )
                            # Don't fail the entire item, just log the error
                    else:
                        logger.warning(
                            f"No cemetery name found for {item.full_name} (PersonID {item.person_id}), skipping burial event creation"
                        )
                        self.error_log.add_warning(
                            f"No cemetery name found for {item.full_name} (PersonID {item.person_id}), skipping burial event",
                            context="Find a Grave Batch"
                        )

                    # Auto-download images AFTER burial event is created
                    # (so Grave/Cemetery photos can link to the burial event)
                    if self.auto_download_images and item.photos:
                        logger.info(f"Auto-downloading {len(item.photos)} photo(s) for {item.full_name}...")
                        status_label.text = f"Downloading {len(item.photos)} image(s)..."

                        for photo in item.photos:
                            try:
                                # Download photo using the same logic as manual download
                                await self._download_photo_for_batch(item, photo, result['citation_id'])
                            except Exception as photo_error:
                                logger.error(f"Failed to download photo: {photo_error}", exc_info=True)
                                self.error_log.add_warning(
                                    f"Failed to download photo for {item.full_name}: {photo_error}",
                                    context="Find a Grave Batch"
                                )
                                # Continue with other photos/processing

                    # Record citation creation timing
                    citation_duration = time.time() - citation_start
                    if self.current_state_item_id:
                        self.state_repository.record_metric(
                            operation='citation_creation',
                            duration_ms=int(citation_duration * 1000),
                            success=True,
                            session_id=session_id
                        )

                        # Update state DB with created citation IDs
                        self.state_repository.update_item_citation(
                            self.current_state_item_id,
                            citation_id=result['citation_id'],
                            source_id=result['source_id'],
                            burial_event_id=burial_event_id
                        )

                    # Mark as complete
                    self.controller.mark_item_complete(
                        item,
                        source_id=result['source_id'],
                        citation_id=result['citation_id'],
                        burial_event_id=burial_event_id,
                    )

                    status_label.text = f"{processed + 1} saved to database"

                except Exception as db_error:
                    logger.error(f"Database write failed: {db_error}")
                    self.error_log.add_error(
                        f"Database write failed for {item.full_name}: {db_error}",
                        context="Find a Grave Batch"
                    )
                    self.controller.mark_item_error(item, f"Database write failed: {db_error}")

                    # Record failure in state DB
                    if self.current_state_item_id:
                        self.state_repository.update_item_status(
                            self.current_state_item_id,
                            'error',
                            error_message=f"Database write failed: {db_error}"
                        )
                        self.state_repository.record_metric(
                            operation='citation_creation',
                            duration_ms=int((time.time() - citation_start) * 1000),
                            success=False,
                            session_id=session_id
                        )

                    continue

                processed += 1

                # ===== PHASE 6: CHECKPOINT =====
                # Mark complete in state DB
                if self.current_state_item_id:
                    self.state_repository.update_item_status(
                        self.current_state_item_id,
                        'complete'
                    )

                # Create checkpoint after configured interval
                self.checkpoint_counter += 1
                if self.checkpoint_counter >= self.config.findagrave_checkpoint_frequency:
                    try:
                        self.state_repository.create_checkpoint(
                            session_id=session_id,
                            last_processed_item_id=self.current_state_item_id or 0,
                            last_processed_person_id=item.person_id
                        )
                        self.checkpoint_counter = 0
                        logger.debug(f"Checkpoint created at item {i}/{total}")
                    except Exception as checkpoint_error:
                        logger.warning(f"Failed to create checkpoint: {checkpoint_error}")

                # Update session progress
                try:
                    self.state_repository.update_session_counts(
                        session_id=session_id,
                        completed_count=processed,
                    )
                except Exception:
                    pass  # Non-critical

                # Refresh queue
                self.queue_container.clear()
                with self.queue_container:
                    self._render_queue_items()

            except Exception as e:
                logger.error(f"Error processing item {item.full_name} (PersonID {item.person_id}): {e}")
                self.controller.mark_item_error(item, str(e))

                # Record error in state DB
                if self.current_state_item_id:
                    self.state_repository.update_item_status(
                        self.current_state_item_id,
                        'error',
                        error_message=str(e)
                    )

            # Small delay to allow UI update
            await asyncio.sleep(0.1)

        # Close progress dialog
        progress_dialog.close()

        # ===== COMPLETE SESSION IN STATE DB =====
        try:
            errors = total - processed
            self.state_repository.update_session_counts(
                session_id=session_id,
                completed_count=processed,
                error_count=errors
            )
            self.state_repository.complete_session(session_id)

            # Log performance summary
            metrics = self.state_repository.get_session_metrics(session_id)
            logger.info(f"Batch session {session_id} completed:")
            logger.info(f"  Total items: {total}")
            logger.info(f"  Successful: {processed}")
            logger.info(f"  Failed: {errors}")

            if metrics:
                for operation, stats in metrics.items():
                    logger.info(
                        f"  {operation}: avg={stats['avg_duration_ms']:.0f}ms, "
                        f"success_rate={stats['success_rate']:.1%}"
                    )

            # Log adaptive timeout stats
            timeout_stats = self.timeout_manager.get_statistics()
            logger.info(
                f"Adaptive timeout stats: "
                f"mean={timeout_stats['mean']:.1f}s, "
                f"current={timeout_stats['current_timeout']}s, "
                f"success_rate={timeout_stats['success_rate']:.1%}"
            )

        except Exception as state_error:
            logger.warning(f"Failed to finalize state session: {state_error}")

        # Show citation matching report if there's data to report
        if citation_report_data:
            self._show_citation_matching_report(citation_report_data)

        # Show image download summary
        self._show_image_download_summary()

        # Show completion notification BEFORE UI refresh
        completion_msg = f"Processed {processed} of {total} items"
        msg_type = "positive" if processed == total else "warning"
        ui.notify(completion_msg, type=msg_type)

        if msg_type == "positive":
            self.error_log.add_info(completion_msg, context="Find a Grave Batch")
        else:
            self.error_log.add_warning(completion_msg, context="Find a Grave Batch")

        # Clear checkbox selections after processing
        self.selected_item_ids.clear()

        # Refresh entire UI including header (to update summary stats)
        self.container.clear()
        with self.container:
            self._render_header()
            self._render_batch_view()

    def _on_item_click(self, item: FindAGraveBatchItem) -> None:
        """Handle item click."""
        if self.controller.session:
            self.controller.session.move_to_item(item.person_id)

            # Refresh detail view
            self.detail_container.clear()
            with self.detail_container:
                self._render_item_details()

            # Refresh queue to show selection
            self.queue_container.clear()
            with self.queue_container:
                self._render_queue_items()

    def _on_checkbox_change(self, person_id: int, checked: bool) -> None:
        """Handle checkbox change."""
        if checked:
            self.selected_item_ids.add(person_id)
        else:
            self.selected_item_ids.discard(person_id)

    def _select_all(self) -> None:
        """Select all items in the queue."""
        if not self.controller.session:
            return

        # Add all person IDs to selected set
        for item in self.controller.session.items:
            self.selected_item_ids.add(item.person_id)

        # Refresh queue to show checkboxes
        self.queue_container.clear()
        with self.queue_container:
            self._render_queue_items()

        ui.notify(f"Selected {len(self.selected_item_ids)} items", type="info")

    def _deselect_all(self) -> None:
        """Deselect all items in the queue."""
        if not self.controller.session:
            return

        # Clear selected set
        self.selected_item_ids.clear()

        # Refresh queue to show checkboxes
        self.queue_container.clear()
        with self.queue_container:
            self._render_queue_items()

        ui.notify("Cleared all selections", type="info")

    def _get_status_icon(self, status: FindAGraveStatus) -> str:
        """Get icon for status."""
        if status == FindAGraveStatus.COMPLETE:
            return "check_circle"
        elif status == FindAGraveStatus.ERROR:
            return "error"
        elif status == FindAGraveStatus.NEEDS_REVIEW:
            return "warning"
        elif status == FindAGraveStatus.EXTRACTING:
            return "sync"
        else:
            return "schedule"
