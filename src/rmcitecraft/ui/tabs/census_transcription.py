"""Census Transcription Tab for RMCitecraft.

Standalone AI-powered census image transcription using Gemini.
Queries RootsMagic database for census images and associated people.
"""

import asyncio
import re
import subprocess
import tempfile
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from loguru import logger
from nicegui import ui

from rmcitecraft.config import get_config
from rmcitecraft.repositories import DatabaseConnection
from rmcitecraft.services.census_transcriber import CensusTranscriber


def parse_footnote_context(footnote: str) -> dict:
    """Extract line number, sheet, and ED from citation footnote.

    Example footnote:
    "1940 U.S. census, Vanderburgh County, Indiana, Evansville,
     enumeration district (ED) 93-76, sheet 9A, line 24, Margaret Hanna Iams..."

    Returns:
        dict with keys: line_number, sheet, enumeration_district (all optional)
    """
    result = {}

    if not footnote:
        return result

    # Extract line number
    line_match = re.search(r'line\s+(\d+)', footnote, re.IGNORECASE)
    if line_match:
        result['target_line'] = int(line_match.group(1))

    # Extract sheet (e.g., "sheet 9A", "sheet 3B")
    sheet_match = re.search(r'sheet\s+(\d+[AB]?)', footnote, re.IGNORECASE)
    if sheet_match:
        result['sheet'] = sheet_match.group(1)

    # Extract enumeration district (various formats)
    # "ED 93-76", "enumeration district (ED) 93-76", "E.D. 95"
    ed_match = re.search(r'(?:enumeration district\s*\(ED\)|ED|E\.D\.)\s*(\d+(?:-\d+)?)', footnote, re.IGNORECASE)
    if ed_match:
        result['enumeration_district'] = ed_match.group(1)

    return result


@dataclass
class CensusImageRecord:
    """Census image with associated metadata from RootsMagic."""
    media_id: int
    media_path: str  # Full resolved path
    media_file: str  # Filename only
    caption: str
    census_year: int | None
    person_names: list[str] = field(default_factory=list)
    footnote: str = ""  # Citation footnote (contains line number)


class CensusTranscriptionTab:
    """Census Transcription Tab component."""

    CENSUS_YEARS = [1790, 1800, 1810, 1820, 1830, 1840, 1850, 1860, 1870, 1880, 1890, 1900, 1910, 1920, 1930, 1940, 1950]

    def __init__(self) -> None:
        """Initialize census transcription tab."""
        self.config = get_config()
        self.transcriber: CensusTranscriber | None = None
        self.is_transcribing: bool = False

        # Data
        self.census_images: list[CensusImageRecord] = []
        self.selected_image: CensusImageRecord | None = None
        self.filter_year: int | None = None

        # UI references (set during render)
        self.image_list_column: ui.column | None = None
        self.preview_column: ui.column | None = None
        self.results_column: ui.column | None = None
        self.status_label: ui.label | None = None
        self.load_button: ui.button | None = None
        self.progress_spinner: ui.spinner | None = None
        self.progress_container: ui.row | None = None
        self.elapsed_timer: ui.timer | None = None
        self.elapsed_label: ui.label | None = None
        self.start_time: float | None = None

    def render(self) -> None:
        """Render the census transcription tab."""
        with ui.column().classes("w-full p-4 gap-4"):
            # Header
            with ui.row().classes("w-full items-center gap-4"):
                ui.icon("auto_awesome", size="2rem").classes("text-purple-600")
                ui.label("Census Transcription").classes("text-2xl font-bold")
                ui.label("AI-powered extraction using Gemini").classes("text-gray-500")

            # Controls row
            with ui.row().classes("w-full items-center gap-4"):
                ui.select(
                    options={y: str(y) for y in self.CENSUS_YEARS},
                    value=None,
                    label="Census Year (required)",
                    on_change=lambda e: self._set_year(e.value)
                ).classes("w-40")

                self.load_button = ui.button(
                    "Load Census Images",
                    icon="refresh",
                    on_click=self._load_census_images
                ).props("color=primary")
                self.load_button.disable()  # Start disabled until year selected

                self.status_label = ui.label("Select a census year to begin").classes("text-sm text-gray-500")

                # Progress indicator (hidden by default)
                self.progress_container = ui.row().classes("items-center gap-2")
                self.progress_container.set_visibility(False)
                with self.progress_container:
                    self.progress_spinner = ui.spinner("dots", size="lg", color="purple")
                    self.elapsed_label = ui.label("0s").classes("text-sm text-purple-600 font-mono")

            # Three-column layout
            with ui.row().classes("w-full gap-4"):
                # Left: Image list
                with ui.card().classes("w-1/4 p-2"):
                    ui.label("Census Images").classes("font-bold mb-2")
                    with ui.scroll_area().classes("h-96"):
                        self.image_list_column = ui.column().classes("w-full gap-1")

                # Center: Preview
                with ui.card().classes("w-1/3 p-2"):
                    ui.label("Selected Image").classes("font-bold mb-2")
                    self.preview_column = ui.column().classes("w-full gap-2")
                    with self.preview_column:
                        ui.label("Select an image").classes("text-gray-400 italic text-sm")

                # Right: Results
                with ui.card().classes("flex-1 p-2"):
                    ui.label("Transcription Results").classes("font-bold mb-2")
                    with ui.scroll_area().classes("h-96"):
                        self.results_column = ui.column().classes("w-full gap-2")

    def _set_year(self, year: int | None) -> None:
        """Set the census year and enable/disable load button."""
        self.filter_year = year
        if year:
            self.load_button.enable()
            self.status_label.set_text(f"Click 'Load Census Images' to find {year} census images")
        else:
            self.load_button.disable()
            self.status_label.set_text("Select a census year to begin")

    def _show_progress(self, message: str) -> None:
        """Show progress indicator with message."""
        import time
        self.start_time = time.time()
        self.status_label.set_text(message)
        self.progress_container.set_visibility(True)
        self.elapsed_label.set_text("0s")

        # Create timer to update elapsed time
        def update_elapsed():
            if self.start_time and self.is_transcribing:
                elapsed = int(time.time() - self.start_time)
                minutes = elapsed // 60
                seconds = elapsed % 60
                if minutes > 0:
                    self.elapsed_label.set_text(f"{minutes}m {seconds}s")
                else:
                    self.elapsed_label.set_text(f"{seconds}s")

        self.elapsed_timer = ui.timer(1.0, update_elapsed)

    def _hide_progress(self) -> None:
        """Hide progress indicator."""
        self.progress_container.set_visibility(False)
        if self.elapsed_timer:
            self.elapsed_timer.cancel()
            self.elapsed_timer = None
        self.start_time = None

    def _load_census_images(self) -> None:
        """Load census images from RootsMagic database for selected year.

        OPTIMIZED: Uses batch queries instead of N+1 pattern.
        Previous: 1 + 4*N queries (1,377 for 344 images)
        New: 3 queries total regardless of image count
        """
        if not self.filter_year:
            ui.notify("Please select a census year first", type="warning")
            return

        self.status_label.set_text(f"Loading {self.filter_year} census images...")

        try:
            db = DatabaseConnection()
            with db.connect(read_only=True) as conn:
                cursor = conn.cursor()

                # Create temporary index for MediaLinkTable.MediaID if not exists
                # This dramatically speeds up all per-image lookups
                try:
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS temp.idxMediaLinkMediaID
                        ON MediaLinkTable(MediaID, OwnerType)
                    """)
                except Exception:
                    # temp schema may not exist, continue without
                    pass

                # OPTIMIZED QUERY 1: Get all census images for year
                # Use folder-based patterns for better index utilization
                # Pattern: Census/1940/ or Records - Census/1940
                year_str = str(self.filter_year)
                cursor.execute("""
                    SELECT m.MediaID, m.MediaPath, m.MediaFile, m.Caption
                    FROM MultimediaTable m
                    WHERE m.MediaType = 1
                    AND (
                        m.MediaPath LIKE '%Census%' || ? || '%'
                        OR m.MediaFile LIKE ? || '%'
                        OR m.MediaPath LIKE '%' || ? || '%'
                    )
                    ORDER BY m.MediaFile
                """, (year_str, year_str, year_str))
                image_rows = cursor.fetchall()

                if not image_rows:
                    self.census_images = []
                    self.status_label.set_text(f"No images found for {self.filter_year} census")
                    self._refresh_list()
                    return

                # Build lookup of MediaID -> image data
                media_ids = [row[0] for row in image_rows]
                image_data = {
                    row[0]: {
                        'media_path': row[1],
                        'media_file': row[2],
                        'caption': row[3],
                        'people': [],
                        'footnote': ''
                    }
                    for row in image_rows
                }

                # OPTIMIZED QUERY 2: Batch fetch ALL people for ALL images in one query
                # Uses IN clause with parameterized placeholders
                placeholders = ','.join('?' * len(media_ids))
                cursor.execute(f"""
                    WITH media_people AS (
                        -- Direct link: Media → Person
                        SELECT ml.MediaID, n.Surname || ', ' || n.Given AS name
                        FROM MediaLinkTable ml
                        JOIN NameTable n ON ml.OwnerID = n.OwnerID AND n.IsPrimary = 1
                        WHERE ml.MediaID IN ({placeholders}) AND ml.OwnerType = 0

                        UNION

                        -- Via citation: Media → Citation → Event → Person
                        SELECT ml.MediaID, n.Surname || ', ' || n.Given AS name
                        FROM MediaLinkTable ml
                        JOIN CitationLinkTable cl ON ml.OwnerID = cl.CitationID
                        JOIN EventTable e ON cl.OwnerID = e.EventID AND cl.OwnerType = 2
                        JOIN NameTable n ON e.OwnerID = n.OwnerID AND n.IsPrimary = 1
                        WHERE ml.MediaID IN ({placeholders}) AND ml.OwnerType = 4

                        UNION

                        -- Via witnesses: Media → Citation → Event → Witness → Person
                        SELECT ml.MediaID, n.Surname || ', ' || n.Given AS name
                        FROM MediaLinkTable ml
                        JOIN CitationLinkTable cl ON ml.OwnerID = cl.CitationID
                        JOIN EventTable e ON cl.OwnerID = e.EventID AND cl.OwnerType = 2
                        JOIN WitnessTable w ON e.EventID = w.EventID
                        JOIN NameTable n ON w.PersonID = n.OwnerID AND n.IsPrimary = 1
                        WHERE ml.MediaID IN ({placeholders}) AND ml.OwnerType = 4
                    )
                    SELECT MediaID, name FROM media_people WHERE name IS NOT NULL
                """, media_ids * 3)  # 3x because used in 3 subqueries

                for media_id, name in cursor.fetchall():
                    if media_id in image_data and name:
                        if name not in image_data[media_id]['people']:
                            image_data[media_id]['people'].append(name)

                # OPTIMIZED QUERY 3: Batch fetch ALL footnotes for ALL images
                cursor.execute(f"""
                    SELECT ml.MediaID, c.Footnote, s.TemplateID, s.Fields
                    FROM MediaLinkTable ml
                    JOIN CitationTable c ON ml.OwnerID = c.CitationID
                    JOIN SourceTable s ON c.SourceID = s.SourceID
                    WHERE ml.MediaID IN ({placeholders}) AND ml.OwnerType = 4
                """, media_ids)

                import xml.etree.ElementTree as ET
                for media_id, cit_footnote, template_id, source_fields in cursor.fetchall():
                    if media_id not in image_data:
                        continue

                    footnote = ""
                    # For template-based sources, use CitationTable.Footnote
                    if template_id != 0 and cit_footnote:
                        footnote = cit_footnote
                    # For free-form sources (TemplateID=0), parse SourceTable.Fields
                    elif source_fields:
                        try:
                            xml_data = source_fields.decode('utf-8') if isinstance(source_fields, bytes) else source_fields
                            root = ET.fromstring(xml_data)
                            footnote_elem = root.find('.//Field[Name="Footnote"]/Value')
                            if footnote_elem is not None and footnote_elem.text:
                                footnote = footnote_elem.text
                        except ET.ParseError:
                            pass

                    if footnote and not image_data[media_id]['footnote']:
                        image_data[media_id]['footnote'] = footnote

                # Build final image list
                self.census_images = []
                for media_id in media_ids:
                    data = image_data[media_id]
                    full_path = self._resolve_path(data['media_path'], data['media_file'])
                    year = self._extract_year(data['media_file'] or data['media_path'] or "")

                    self.census_images.append(CensusImageRecord(
                        media_id=media_id,
                        media_path=full_path,
                        media_file=data['media_file'] or "",
                        caption=data['caption'] or "",
                        census_year=year,
                        person_names=data['people'][:15],
                        footnote=data['footnote'],
                    ))

            self.status_label.set_text(f"Found {len(self.census_images)} images for {self.filter_year} census")
            self._refresh_list()

        except Exception as e:
            logger.error(f"Database error: {e}")
            self.status_label.set_text(f"Error: {e}")
            ui.notify(f"Database error: {e}", type="negative")

    def _resolve_path(self, media_path: str, media_file: str) -> str:
        """Resolve RootsMagic path symbols."""
        if not media_path:
            return media_file or ""

        # Normalize backslashes to forward slashes (RootsMagic stores Windows-style paths)
        path = media_path.replace("\\", "/")

        if path.startswith("?"):
            path = str(Path(self.config.rm_media_root_directory) / path[1:].lstrip("/"))
        elif path.startswith("~"):
            path = str(Path.home() / path[1:].lstrip("/"))
        elif path.startswith("*"):
            path = str(Path(self.config.rm_database_path).parent / path[1:].lstrip("/"))

        if media_file and not path.endswith(media_file):
            path = str(Path(path) / media_file)

        return path

    def _extract_year(self, text: str) -> int | None:
        """Extract census year from text."""
        import re
        for year in self.CENSUS_YEARS:
            if str(year) in text:
                return year
        match = re.search(r'\b(1[789]\d0|19[0-5]0)\b', text)
        if match:
            y = int(match.group(1))
            return y if y in self.CENSUS_YEARS else None
        return None

    def _get_people(self, cursor, media_id: int) -> list[str]:
        """Get people associated with media, including witnesses (shared census facts).

        NOTE: This method is kept for individual lookups but is no longer used
        in batch loading. The _load_census_images method uses a single batch
        query for all images instead of calling this N times.
        """
        try:
            # Direct link: Media → Person
            cursor.execute("""
                SELECT DISTINCT n.Surname || ', ' || n.Given
                FROM MediaLinkTable ml
                JOIN NameTable n ON ml.OwnerID = n.OwnerID AND n.IsPrimary = 1
                WHERE ml.MediaID = ? AND ml.OwnerType = 0
                LIMIT 10
            """, (media_id,))
            direct = [r[0] for r in cursor.fetchall() if r[0]]

            # Via citation: Media → Citation → Event → Person (event owner)
            cursor.execute("""
                SELECT DISTINCT n.Surname || ', ' || n.Given
                FROM MediaLinkTable ml
                JOIN CitationLinkTable cl ON ml.OwnerID = cl.CitationID AND ml.OwnerType = 4
                JOIN EventTable e ON cl.OwnerID = e.EventID AND cl.OwnerType = 2
                JOIN NameTable n ON e.OwnerID = n.OwnerID AND n.IsPrimary = 1
                WHERE ml.MediaID = ?
                LIMIT 10
            """, (media_id,))
            via_citation = [r[0] for r in cursor.fetchall() if r[0]]

            # Via witnesses: Media → Citation → Event → Witness → Person (shared census facts)
            cursor.execute("""
                SELECT DISTINCT n.Surname || ', ' || n.Given
                FROM MediaLinkTable ml
                JOIN CitationLinkTable cl ON ml.OwnerID = cl.CitationID AND ml.OwnerType = 4
                JOIN EventTable e ON cl.OwnerID = e.EventID AND cl.OwnerType = 2
                JOIN WitnessTable w ON e.EventID = w.EventID
                JOIN NameTable n ON w.PersonID = n.OwnerID AND n.IsPrimary = 1
                WHERE ml.MediaID = ?
                LIMIT 20
            """, (media_id,))
            via_witness = [r[0] for r in cursor.fetchall() if r[0]]

            return list(set(direct + via_citation + via_witness))[:15]
        except Exception as e:
            logger.warning(f"Failed to get people for {media_id}: {e}")
            return []

    def _get_footnote(self, cursor, media_id: int) -> str:
        """Get footnote from citation linked to media (contains line number).

        For free-form sources (TemplateID=0), the footnote is stored in
        SourceTable.Fields BLOB as XML, not in CitationTable.Footnote.

        NOTE: This method is kept for individual lookups but is no longer used
        in batch loading. The _load_census_images method uses a single batch
        query for all images instead of calling this N times.
        """
        import xml.etree.ElementTree as ET

        try:
            # Media → Citation → Source (get both citation footnote and source fields)
            cursor.execute("""
                SELECT c.Footnote, s.TemplateID, s.Fields
                FROM MediaLinkTable ml
                JOIN CitationTable c ON ml.OwnerID = c.CitationID
                JOIN SourceTable s ON c.SourceID = s.SourceID
                WHERE ml.MediaID = ? AND ml.OwnerType = 4
                LIMIT 1
            """, (media_id,))
            row = cursor.fetchone()

            if not row:
                return ""

            cit_footnote, template_id, source_fields = row

            # For template-based sources, use CitationTable.Footnote
            if template_id != 0 and cit_footnote:
                return cit_footnote

            # For free-form sources (TemplateID=0), parse SourceTable.Fields XML
            if source_fields:
                try:
                    xml_data = source_fields.decode('utf-8') if isinstance(source_fields, bytes) else source_fields
                    root = ET.fromstring(xml_data)
                    footnote_elem = root.find('.//Field[Name="Footnote"]/Value')
                    if footnote_elem is not None and footnote_elem.text:
                        return footnote_elem.text
                except ET.ParseError as e:
                    logger.warning(f"Failed to parse source fields XML for {media_id}: {e}")

            return ""
        except Exception as e:
            logger.warning(f"Failed to get footnote for {media_id}: {e}")
            return ""

    def _refresh_list(self) -> None:
        """Refresh the image list."""
        self.image_list_column.clear()

        with self.image_list_column:
            if not self.census_images:
                ui.label("No images found").classes("text-gray-400 italic text-sm")
                return

            for img in self.census_images:
                self._render_list_item(img)

    def _render_list_item(self, img: CensusImageRecord) -> None:
        """Render a list item."""
        exists = Path(img.media_path).exists()

        with ui.card().classes(
            f"w-full p-2 cursor-pointer hover:bg-blue-50 {'opacity-50' if not exists else ''}"
        ).on("click", lambda i=img: self._select_image(i)):
            with ui.row().classes("items-center gap-2"):
                if img.census_year:
                    ui.badge(str(img.census_year), color="blue")
                name = img.media_file[:30] + "..." if len(img.media_file) > 30 else img.media_file
                ui.label(name).classes("text-xs font-mono truncate")

            if img.person_names:
                ui.label(", ".join(img.person_names[:2])).classes("text-xs text-gray-500 truncate")

            if not exists:
                ui.label("Not found").classes("text-xs text-red-500")

    def _select_image(self, img: CensusImageRecord) -> None:
        """Select an image."""
        self.selected_image = img
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        """Refresh the preview panel."""
        self.preview_column.clear()

        with self.preview_column:
            if not self.selected_image:
                ui.label("Select an image").classes("text-gray-400 italic text-sm")
                return

            img = self.selected_image
            exists = Path(img.media_path).exists()

            # Info
            ui.label(img.media_file or "Unknown").classes("font-bold text-sm")
            if img.census_year:
                ui.badge(f"{img.census_year} Census", color="blue")

            # Footnote (contains line number)
            if img.footnote:
                ui.label("Citation:").classes("text-xs font-bold mt-2")
                ui.label(img.footnote).classes("text-xs text-gray-600 break-words")

            # People
            if img.person_names:
                ui.label(f"People ({len(img.person_names)}):").classes("text-xs font-bold mt-2")
                for name in img.person_names[:8]:
                    ui.label(f"• {name}").classes("text-xs")

            # Extract FamilySearch ARK URL from footnote if present
            ark_url = self._extract_ark_url(img.footnote) if img.footnote else None
            if ark_url:
                ui.label("FamilySearch Link:").classes("text-xs font-bold mt-2 text-green-600")
                with ui.row().classes("items-center gap-1"):
                    ui.icon("link", size="xs").classes("text-green-500")
                    ui.link(
                        "View on FamilySearch",
                        ark_url,
                        new_tab=True
                    ).classes("text-xs text-green-600")

            # Preview or error
            if exists:
                ui.image(img.media_path).classes("w-full max-h-48 object-contain mt-2")
                with ui.row().classes("w-full gap-2 mt-2"):
                    # NiceGUI handles async functions directly when passed to on_click
                    ui.button(
                        "Transcribe with Gemini",
                        icon="auto_awesome",
                        on_click=self._transcribe
                    ).props("color=purple").classes("flex-1")
                    ui.button(
                        "Full Screen",
                        icon="fullscreen",
                        on_click=self._open_image_in_browser
                    ).props("color=blue outline")

                # Add FamilySearch import button if ARK URL found
                if ark_url:
                    ui.button(
                        "Import from FamilySearch",
                        icon="cloud_download",
                        on_click=lambda url=ark_url: self._import_from_familysearch(url)
                    ).props("color=green size=sm").classes("w-full mt-1")
            else:
                ui.label("File not found").classes("text-red-500 mt-2")
                ui.label(img.media_path).classes("text-xs text-gray-400 break-all")

    async def _transcribe(self) -> None:
        """Transcribe the selected image with context from database."""
        import traceback

        # FIRST LINE - log immediately to confirm button click is received
        logger.info("=" * 60)
        logger.info("_transcribe() called - button click received")
        print(">>> _transcribe() called - button click received", flush=True)

        try:
            if self.is_transcribing:
                logger.warning("Transcription already in progress, ignoring click")
                ui.notify("Transcription already in progress", type="warning")
                return

            if not self.selected_image:
                logger.warning("No image selected")
                ui.notify("No image selected", type="warning")
                return

            img = self.selected_image
            logger.info(f"Selected image: {img.media_file}")
            logger.info(f"Image path: {img.media_path}")

            if not Path(img.media_path).exists():
                logger.error(f"Image file not found: {img.media_path}")
                ui.notify("Image file not found", type="negative")
                return

            year = img.census_year or 1950
            self.is_transcribing = True

            # Show progress indicator
            logger.info(f"Starting transcription for {year} census")
            ui.notify(f"Starting transcription for {year} census...", type="info")
            self._show_progress(f"Transcribing {year} census (this may take 2-3 minutes)...")

            # Parse footnote for line number, sheet, ED
            footnote_context = parse_footnote_context(img.footnote)
            logger.info(f"Footnote context: {footnote_context}")

            # Log targeting info
            if img.person_names:
                logger.info(f"Target names from database: {img.person_names}")

            # Initialize transcriber
            if not self.transcriber:
                self.status_label.set_text("Initializing transcriber...")
                logger.info("Creating CensusTranscriber instance...")
                print(">>> Creating CensusTranscriber...", flush=True)

                try:
                    self.transcriber = CensusTranscriber(model='gemini-3-pro-preview')
                    logger.info(f"CensusTranscriber created with provider: {self.transcriber.provider.name}")
                    print(f">>> CensusTranscriber created: {self.transcriber.provider.name}", flush=True)
                except Exception as init_error:
                    logger.error(f"Failed to create CensusTranscriber: {init_error}")
                    logger.error(traceback.format_exc())
                    print(f">>> ERROR creating transcriber: {init_error}", flush=True)
                    raise

            # Call LLM
            self.status_label.set_text(f"Calling LLM for {year} census...")
            logger.info(f"Calling transcribe_census for {img.media_path}")
            print(f">>> Calling LLM for {year} census...", flush=True)

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._do_transcribe(img, year, footnote_context)
            )

            logger.info(f"Transcription complete, confidence: {result.confidence}")
            print(f">>> Transcription complete: {result.confidence}", flush=True)

            self._show_results(result, img)
            self.status_label.set_text("Transcription complete")
            ui.notify("Transcription complete!", type="positive")

        except Exception as e:
            error_msg = f"Transcription error: {e}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            print(f">>> ERROR: {error_msg}", flush=True)
            print(traceback.format_exc(), flush=True)
            ui.notify(error_msg, type="negative")
            self.status_label.set_text(f"Error: {e}")
        finally:
            self.is_transcribing = False
            self._hide_progress()
            logger.info("_transcribe() finished")
            print(">>> _transcribe() finished", flush=True)

    def _do_transcribe(self, img: CensusImageRecord, year: int, footnote_context: dict):
        """Synchronous transcription wrapper for executor."""
        logger.info(f"_do_transcribe called for year {year}")
        print(f">>> _do_transcribe called for {img.media_file}", flush=True)

        try:
            result = self.transcriber.transcribe_census(
                img.media_path,
                year,
                target_names=img.person_names if img.person_names else None,
                **footnote_context
            )
            logger.info(f"transcribe_census returned: confidence={result.confidence}")
            return result
        except Exception as e:
            logger.error(f"transcribe_census failed: {e}")
            print(f">>> transcribe_census FAILED: {e}", flush=True)
            raise

    def _open_image_in_browser(self) -> None:
        """Open the census image in a browser tab for full-screen viewing."""
        if not self.selected_image:
            ui.notify("No image selected", type="warning")
            return

        image_path = Path(self.selected_image.media_path)
        if not image_path.exists():
            ui.notify(f"Image file not found: {image_path}", type="negative")
            return

        # Open image file directly in browser
        try:
            webbrowser.open(f"file://{image_path}")
            logger.info(f"Opened image in browser: {image_path}")
            ui.notify("Image opened in browser", type="positive")
        except Exception as e:
            logger.error(f"Failed to open image in browser: {e}")
            ui.notify(f"Error opening image: {e}", type="negative")

    def _generate_census_html(self, result, img: CensusImageRecord) -> str:
        """Generate HTML file displaying census transcription results.

        Creates an HTML table formatted to resemble the 1950 census form layout
        with all columns and highlighting for target and sample rows.

        Returns:
            Path to the generated HTML file
        """
        records = result.data.get('records', [])
        page_info = result.data.get('page_info', {})
        metadata = result.metadata or {}

        census_year = metadata.get('census_year', img.census_year or 'Unknown')
        target_names = metadata.get('target_names', img.person_names or [])
        warnings = metadata.get('warnings', [])

        # Get location info from page_info or extract from footnote
        state = page_info.get('state', '')
        county = page_info.get('county', '')
        township = page_info.get('township', page_info.get('city', ''))
        ed = page_info.get('enumeration_district', '')
        stamp = page_info.get('page_number', page_info.get('stamp', ''))

        # Build target surnames list for highlighting
        target_surnames = []
        for name in target_names:
            if ',' in name:
                target_surnames.append(name.split(',')[0].strip().lower())
            else:
                target_surnames.append(name.split()[0].strip().lower())

        # Define columns based on census year
        if census_year == 1950:
            columns = [
                ('line_number', 'Line', '40px'),
                ('street_address', 'Address', '120px'),
                ('household_number', 'HH#', '40px'),
                ('name', 'Name', '180px'),
                ('relationship', 'Rel', '60px'),
                ('race', 'Race', '40px'),
                ('sex', 'Sex', '35px'),
                ('age', 'Age', '35px'),
                ('marital_status', 'Mar', '40px'),
                ('birthplace', 'Birthplace', '80px'),
                ('citizenship', 'Cit', '40px'),
                ('occupation', 'Occupation', '120px'),
                ('industry', 'Industry', '100px'),
                ('class_of_worker', 'Class', '40px'),
            ]
        else:
            # Default columns for other years
            columns = [
                ('line_number', 'Line', '40px'),
                ('name', 'Name', '180px'),
                ('relationship', 'Rel', '60px'),
                ('sex', 'Sex', '35px'),
                ('race', 'Race', '40px'),
                ('age', 'Age', '35px'),
                ('marital_status', 'Mar', '40px'),
                ('birthplace', 'Birthplace', '80px'),
                ('occupation', 'Occupation', '120px'),
            ]

        # Sample lines for 1950 census
        sample_lines = {6, 11, 16, 21, 26} if census_year == 1950 else set()

        # Build HTML
        html_parts = [f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{census_year} Census Transcription - E.D. {ed}</title>
    <style>
        body {{
            font-family: 'Courier New', monospace;
            font-size: 11px;
            margin: 20px;
            background: #f5f5f5;
        }}
        h1 {{
            font-family: Arial, sans-serif;
            font-size: 18px;
            color: #333;
        }}
        .header-info {{
            font-family: Arial, sans-serif;
            margin-bottom: 15px;
            padding: 10px;
            background: #e0e0e0;
            border-radius: 4px;
        }}
        .header-info strong {{
            color: #333;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th {{
            background: #2c3e50;
            color: white;
            padding: 6px 4px;
            text-align: left;
            font-size: 10px;
            position: sticky;
            top: 0;
        }}
        td {{
            border: 1px solid #ccc;
            padding: 4px;
            vertical-align: top;
        }}
        tr:nth-child(even) {{
            background: #f9f9f9;
        }}
        tr.target-row {{
            background: #fff3cd !important;
            font-weight: bold;
        }}
        tr.sample-row {{
            background: #d4edda !important;
        }}
        tr.household-start {{
            border-top: 3px solid #333;
        }}
        .legend {{
            font-family: Arial, sans-serif;
            margin-top: 15px;
            padding: 10px;
            background: #e8e8e8;
            border-radius: 4px;
            font-size: 11px;
        }}
        .legend-item {{
            display: inline-block;
            margin-right: 20px;
            padding: 2px 8px;
        }}
        .legend-target {{
            background: #fff3cd;
        }}
        .legend-sample {{
            background: #d4edda;
        }}
        .stats {{
            font-family: Arial, sans-serif;
            margin-top: 10px;
            font-size: 11px;
            color: #666;
        }}
        .warnings {{
            margin-top: 10px;
            padding: 10px;
            background: #fff3cd;
            border-radius: 4px;
            font-family: Arial, sans-serif;
        }}
        .warnings h3 {{
            margin: 0 0 5px 0;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <h1>{census_year} U.S. Census Transcription</h1>
    <div class="header-info">
        <strong>Location:</strong> {state}, {county} County, {township}<br>
        <strong>E.D.:</strong> {ed} | <strong>{"Stamp" if census_year == 1950 else "Sheet"}:</strong> {stamp}<br>
        <strong>Image:</strong> {img.media_file}<br>
        <strong>Confidence:</strong> {result.confidence:.0%} | <strong>Records:</strong> {len(records)}
    </div>

    <table>
        <thead>
            <tr>
''']

        # Add column headers
        for col_id, col_label, col_width in columns:
            html_parts.append(f'                <th style="width: {col_width}">{col_label}</th>\n')
        html_parts.append('            </tr>\n        </thead>\n        <tbody>\n')

        # Track households for border styling
        prev_household = None

        # Add data rows
        for i, record in enumerate(records):
            # Determine row classes
            classes = []

            # Check if target row
            record_name = str(record.get('name', '')).lower()
            is_target = any(surname in record_name for surname in target_surnames)
            if is_target:
                classes.append('target-row')

            # Check if sample row
            line_num = record.get('line_number')
            if line_num in sample_lines:
                classes.append('sample-row')

            # Check for household boundary
            current_household = record.get('household_number', record.get('dwelling_number'))
            if current_household and current_household != prev_household and i > 0:
                classes.append('household-start')
            prev_household = current_household

            class_str = f' class="{" ".join(classes)}"' if classes else ''
            html_parts.append(f'            <tr{class_str}>\n')

            for col_id, _, _ in columns:
                value = record.get(col_id, '')
                if value is None:
                    value = ''
                html_parts.append(f'                <td>{value}</td>\n')

            html_parts.append('            </tr>\n')

        html_parts.append('        </tbody>\n    </table>\n')

        # Add legend
        html_parts.append('''
    <div class="legend">
        <span class="legend-item legend-target">■ Target individuals</span>
        <span class="legend-item legend-sample">■ Sample rows (additional questions)</span>
        <span class="legend-item">━ Thick border = household boundary</span>
    </div>
''')

        # Add warnings if any
        if warnings:
            html_parts.append('    <div class="warnings">\n        <h3>Validation Warnings:</h3>\n        <ul>\n')
            for warning in warnings:
                html_parts.append(f'            <li>{warning}</li>\n')
            html_parts.append('        </ul>\n    </div>\n')

        # Add stats
        html_parts.append(f'''
    <div class="stats">
        Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} |
        Target names: {", ".join(target_names[:5]) if target_names else "None specified"}
    </div>
</body>
</html>
''')

        # Write to temp file
        html_content = ''.join(html_parts)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_file = Path(tempfile.gettempdir()) / f"census_transcription_{census_year}_{timestamp}.html"
        html_file.write_text(html_content, encoding='utf-8')

        logger.info(f"Generated census HTML: {html_file}")
        return str(html_file)

    def _open_results_in_browser(self) -> None:
        """Generate HTML results and open in browser tab."""
        if not hasattr(self, '_last_result') or not self._last_result:
            ui.notify("No transcription results available", type="warning")
            return

        if not self.selected_image:
            ui.notify("No image selected", type="warning")
            return

        try:
            html_path = self._generate_census_html(self._last_result, self.selected_image)
            webbrowser.open(f"file://{html_path}")
            logger.info(f"Opened results in browser: {html_path}")
            ui.notify("Results opened in browser", type="positive")
        except Exception as e:
            logger.error(f"Failed to open results in browser: {e}")
            ui.notify(f"Error: {e}", type="negative")

    def _show_results(self, result, img: CensusImageRecord) -> None:
        """Show transcription results."""
        # Store result for browser display
        self._last_result = result

        self.results_column.clear()

        records = result.data.get('records', [])

        with self.results_column:
            # Summary
            ui.label(f"Confidence: {result.confidence:.0%}").classes(
                "text-sm px-2 py-1 rounded " +
                ("bg-green-100 text-green-700" if result.confidence >= 0.8 else "bg-yellow-100 text-yellow-700")
            )
            ui.label(f"{len(records)} records extracted").classes("text-sm")

            # Browser view buttons
            with ui.row().classes("gap-2 mt-2"):
                ui.button(
                    "View Results",
                    icon="open_in_new",
                    on_click=self._open_results_in_browser
                ).props("color=purple size=sm").classes("text-xs")
                ui.button(
                    "View Image",
                    icon="image",
                    on_click=self._open_image_in_browser
                ).props("color=blue size=sm outline").classes("text-xs")

            # Match check
            if img.person_names:
                ui.label("Database matches:").classes("text-xs font-bold mt-2 text-blue-600")
                for name in img.person_names[:5]:
                    surname = name.split(",")[0].strip().lower()
                    matched = any(surname in r.get('name', '').lower() for r in records)
                    icon = "✓" if matched else "?"
                    ui.label(f"{icon} {name}").classes(f"text-xs {'text-green-600' if matched else 'text-gray-400'}")

            ui.separator().classes("my-2")

            # Table
            if records:
                columns = [
                    {'name': 'name', 'label': 'Name', 'field': 'name', 'align': 'left'},
                    {'name': 'age', 'label': 'Age', 'field': 'age', 'align': 'center'},
                    {'name': 'rel', 'label': 'Rel', 'field': 'relationship', 'align': 'left'},
                    {'name': 'birthplace', 'label': 'Birthplace', 'field': 'birthplace', 'align': 'left'},
                ]
                rows = [{'id': i, **{c['field']: r.get(c['field'], '') for c in columns}} for i, r in enumerate(records)]
                ui.table(columns=columns, rows=rows, row_key='id').classes("w-full").props("dense flat")

        ui.notify(f"Extracted {len(records)} records", type="positive")

    def _extract_ark_url(self, text: str) -> str | None:
        """Extract FamilySearch ARK URL from text (e.g., footnote).

        Args:
            text: Text that may contain a FamilySearch URL

        Returns:
            ARK URL if found, None otherwise
        """
        if not text:
            return None

        # Pattern for FamilySearch ARK URLs
        # Examples:
        #   https://www.familysearch.org/ark:/61903/1:1:6XKG-DP65
        #   https://familysearch.org/ark:/61903/1:1:M61S-SL1
        ark_pattern = r'https?://(?:www\.)?familysearch\.org/ark:/\d+/[\d:A-Z-]+'
        match = re.search(ark_pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)

        return None

    def _import_from_familysearch(self, ark_url: str) -> None:
        """Import census data from FamilySearch ARK URL.

        Opens a dialog to confirm and perform the import.
        """
        if not self.selected_image:
            ui.notify("No image selected", type="warning")
            return

        img = self.selected_image

        # Store import context for async handler
        self._import_ark_url = ark_url
        self._import_census_year = img.census_year or 1950

        with ui.dialog() as self._import_dialog, ui.card().classes("w-[500px]"):
            ui.label("Import from FamilySearch").classes("text-lg font-bold mb-2")

            ui.label(f"Import transcription data for:").classes("text-sm")
            ui.label(img.media_file).classes("text-sm font-mono text-gray-600")

            ui.separator().classes("my-2")

            ui.label("FamilySearch URL:").classes("text-xs font-bold")
            ui.label(ark_url).classes("text-xs text-blue-600 break-all")

            ui.label(f"Census Year: {self._import_census_year}").classes("text-sm mt-2")

            if img.person_names:
                ui.label(f"Target persons: {', '.join(img.person_names[:3])}").classes(
                    "text-xs text-gray-500"
                )

            self._import_status_label = ui.label("").classes("text-sm text-gray-500 mt-2")

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=self._import_dialog.close).props("flat")
                # NiceGUI handles async functions directly - don't use asyncio.ensure_future
                self._import_btn = ui.button(
                    "Import",
                    icon="cloud_download",
                    on_click=self._do_familysearch_import,
                ).props("color=green")

        self._import_dialog.open()

    async def _do_familysearch_import(self) -> None:
        """Perform the FamilySearch import using stored context."""
        from rmcitecraft.services.familysearch_census_extractor import (
            extract_census_from_citation,
        )

        ark_url = self._import_ark_url
        census_year = self._import_census_year

        try:
            self._import_btn.disable()
            self._import_status_label.set_text("Connecting to Chrome...")

            # NiceGUI handles async functions properly - just await directly
            result = await extract_census_from_citation(ark_url, census_year)

            if result.success:
                name = result.extracted_data.get("primary_name", "Unknown")
                ui.notify(
                    f"Successfully imported: {name}",
                    type="positive",
                )
                self._import_status_label.set_text(f"Imported: {name}")

                # Show success message
                ui.notify("Data saved to census.db - view in Census Extractions tab", type="info")

            else:
                self._import_status_label.set_text(f"Error: {result.error_message}")
                ui.notify(f"Import failed: {result.error_message}", type="negative")

        except Exception as e:
            logger.error(f"FamilySearch import failed: {e}")
            self._import_status_label.set_text(f"Error: {e}")
            ui.notify(f"Import failed: {e}", type="negative")
        finally:
            self._import_btn.enable()
