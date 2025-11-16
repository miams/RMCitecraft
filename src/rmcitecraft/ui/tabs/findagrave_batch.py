"""Find a Grave Batch Processing Tab UI."""

import asyncio
from pathlib import Path

from loguru import logger
from nicegui import ui

from rmcitecraft.config import get_config
from rmcitecraft.services.findagrave_batch import (
    FindAGraveBatchController,
    FindAGraveBatchItem,
    FindAGraveStatus,
)
from rmcitecraft.services.findagrave_automation import get_findagrave_automation
from rmcitecraft.services.findagrave_formatter import (
    format_findagrave_citation,
    generate_source_name,
    generate_image_filename,
)
from rmcitecraft.database.findagrave_queries import (
    create_findagrave_source_and_citation,
    create_burial_event_and_link_citation,
)
from rmcitecraft.services.message_log import get_message_log


class FindAGraveBatchTab:
    """Find a Grave Batch Processing Tab component."""

    def __init__(self):
        """Initialize Find a Grave batch processing tab."""
        self.config = get_config()
        self.controller = FindAGraveBatchController()
        self.message_log = get_message_log()
        self.automation = get_findagrave_automation()

        # UI component references
        self.container: ui.column | None = None
        self.header_container: ui.card | None = None
        self.queue_container: ui.column | None = None
        self.detail_container: ui.column | None = None
        self.selected_item_ids: set[int] = set()

    def render(self) -> ui.column:
        """Render the Find a Grave batch processing tab."""
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
                    ui.button(
                        "Load Batch",
                        icon="download",
                        on_click=self._show_load_dialog,
                    ).props("dense outline")

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
                ui.label("Memorial Queue").classes("font-bold text-sm mb-2")
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
                ui.notify("No people found with Find a Grave URLs", type="warning")
                return

            # Create session
            self.controller.create_session(result['people'])
            self.selected_item_ids = set()

            # Refresh UI
            self.container.clear()
            with self.container:
                self._render_header()
                self._render_batch_view()

            ui.notify(
                f"Loaded {len(result['people'])} people "
                f"(examined {result['examined']}, excluded {result['excluded']})",
                type="positive",
            )

        except Exception as e:
            logger.error(f"Failed to load batch: {e}")
            ui.notify(f"Error loading batch: {e}", type="negative")

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
                ui.notify(f"Downloaded photo to {download_path}", type="positive")
            else:
                ui.notify("Failed to download photo", type="negative")

        except Exception as e:
            logger.error(f"Error downloading photo: {e}", exc_info=True)
            ui.notify(f"Error: {e}", type="negative")

    async def _start_batch_processing(self) -> None:
        """Start batch processing of selected items."""
        if not self.controller.session:
            ui.notify("No batch loaded", type="warning")
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
            ui.notify("No items to process", type="warning")
            return

        # Create progress dialog
        with ui.dialog().props('persistent') as progress_dialog, ui.card().classes('w-96'):
            ui.label('Processing Find a Grave Memorials').classes('text-lg font-bold mb-4')

            progress_label = ui.label('Starting...').classes('text-sm mb-2')
            progress_bar = ui.linear_progress(value=0).props('instant-feedback')

            status_label = ui.label('').classes('text-xs text-gray-600 mt-2')

        progress_dialog.open()

        processed = 0
        total = len(items_to_process)

        for i, item in enumerate(items_to_process, 1):
            # Update progress
            progress_label.text = f"Processing {i} of {total}: {item.full_name}"
            progress_bar.value = i / total
            status_label.text = f"{processed} completed"

            try:
                # Extract memorial data
                item.status = FindAGraveStatus.EXTRACTING
                memorial_data = await self.automation.extract_memorial_data(item.url)

                if not memorial_data:
                    raise Exception("Failed to extract memorial data")

                # Update item with extracted data
                self.controller.update_item_extracted_data(item, memorial_data)

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

                # Write to database
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

                    burial_event_id = None

                    # Create burial event if cemetery information is available
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
                                cemetery_city=memorial_data.get('cemeteryCity', ''),
                                cemetery_county=memorial_data.get('cemeteryCounty', ''),
                                cemetery_state=memorial_data.get('cemeteryState', ''),
                                cemetery_country=memorial_data.get('cemeteryCountry', ''),
                            )

                            if burial_result['needs_approval']:
                                match_info = burial_result.get('match_info', {})
                                cemetery_name = match_info.get('cemetery_name', 'Unknown')
                                findagrave_loc = match_info.get('findagrave_location', 'Unknown')
                                best_match = match_info.get('best_match_name') or 'No matches found'
                                best_match_id = match_info.get('best_match_id')
                                similarity = match_info.get('similarity', 0)

                                # Format match details
                                if best_match_id:
                                    match_detail = f"{best_match} (PlaceID {best_match_id}, {similarity:.1%})"
                                else:
                                    match_detail = "No matches found"

                                logger.warning(
                                    f"Burial event for {item.full_name} requires user approval:\n"
                                    f"  Cemetery: {cemetery_name}\n"
                                    f"  Find a Grave: {findagrave_loc}\n"
                                    f"  Best Match: {match_detail}"
                                )

                                # Create detailed note for user
                                item.note = (
                                    f"⚠️ Burial place needs approval\n"
                                    f"Cemetery: {cemetery_name}\n"
                                    f"Location: {findagrave_loc}\n"
                                    f"Best match: {match_detail}"
                                )

                                # Notify user during batch processing
                                if best_match_id:
                                    ui.notify(
                                        f"⚠️ {item.full_name}: Burial place needs approval "
                                        f"({similarity:.1%} match to PlaceID {best_match_id})",
                                        type="warning",
                                    )
                                else:
                                    ui.notify(
                                        f"⚠️ {item.full_name}: Burial place needs approval "
                                        f"(no existing matches)",
                                        type="warning",
                                    )
                            else:
                                burial_event_id = burial_result['burial_event_id']
                                logger.info(
                                    f"Created burial event {burial_event_id} for {item.full_name}"
                                )

                        except Exception as burial_error:
                            logger.error(f"Failed to create burial event: {burial_error}", exc_info=True)
                            # Don't fail the entire item, just log the error
                    else:
                        logger.warning(
                            f"No cemetery name found for {item.full_name}, skipping burial event creation"
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
                    self.controller.mark_item_error(item, f"Database write failed: {db_error}")
                    continue

                processed += 1

                # Refresh queue
                self.queue_container.clear()
                with self.queue_container:
                    self._render_queue_items()

            except Exception as e:
                logger.error(f"Error processing item {item.person_id}: {e}")
                self.controller.mark_item_error(item, str(e))

            # Small delay to allow UI update
            await asyncio.sleep(0.1)

        # Close progress dialog
        progress_dialog.close()

        # Show completion notification BEFORE UI refresh
        ui.notify(
            f"Processed {processed} of {total} items",
            type="positive" if processed == total else "warning"
        )

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
