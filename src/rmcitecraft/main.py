"""Main application entry point for RMCitecraft."""

import os
from pathlib import Path

from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from nicegui import app, ui

from rmcitecraft.api import create_api_router
from rmcitecraft.config import get_config
from rmcitecraft.services.file_watcher import FileWatcher
from rmcitecraft.services.image_processing import get_image_processing_service
from rmcitecraft.ui.components.error_panel import create_error_panel
from rmcitecraft.ui.tabs.citation_manager import CitationManagerTab
from rmcitecraft.ui.tabs.batch_processing import BatchProcessingTab
from rmcitecraft.ui.tabs.findagrave_batch import FindAGraveBatchTab
from rmcitecraft.ui.tabs.census_transcription import CensusTranscriptionTab
from rmcitecraft.ui.tabs.census_extraction_viewer import CensusExtractionViewerTab


def _cleanup_services(file_watcher: FileWatcher | None) -> None:
    """Clean up services on application shutdown.

    Args:
        file_watcher: File watcher instance (if started)
    """
    if file_watcher and file_watcher.is_running():
        logger.info("Stopping file watcher...")
        file_watcher.stop()
        logger.info("File watcher stopped")


def setup_app() -> None:
    """Set up the RMCitecraft application routes and UI."""
    config = get_config()

    # Configure file logging
    log_path = Path(config.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Add file sink for all logs (rotation at 10 MB, keep 5 old files)
    logger.add(
        log_path,
        rotation="10 MB",
        retention=5,
        level=config.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        backtrace=True,
        diagnose=True,
    )

    logger.info("Starting RMCitecraft application")
    logger.info(f"Logging to file: {log_path}")

    # Configure CORS for browser extension communication
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins (extension runs on chrome-extension://)
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add API routes for browser extension communication
    api_router = create_api_router()
    app.include_router(api_router)

    logger.info("REST API endpoints configured")

    # Initialize file watcher for image downloads (if configured)
    file_watcher: FileWatcher | None = None
    try:
        # Get image processing service (validates configuration)
        image_service = get_image_processing_service()

        # Get downloads directory (typically ~/Downloads)
        downloads_dir = Path.home() / "Downloads"

        if downloads_dir.exists():
            # Create file watcher with callback to image processing service
            file_watcher = FileWatcher(
                downloads_dir=downloads_dir,
                callback=image_service.process_downloaded_file,
            )
            file_watcher.start()
            logger.info(f"File watcher started: monitoring {downloads_dir}")
        else:
            logger.warning(f"Downloads directory not found: {downloads_dir}")

    except RuntimeError as e:
        logger.warning(f"Image processing not configured: {e}")
    except Exception as e:
        logger.error(f"Failed to start file watcher: {e}")

    # Store cleanup handlers
    app.on_shutdown(lambda: _cleanup_services(file_watcher))

    # Store tab instances for cleanup
    citation_manager: CitationManagerTab | None = None

    @ui.page("/")
    def index() -> None:
        """Main application page."""
        nonlocal citation_manager

        ui.page_title("RMCitecraft - Census Citation Assistant")

        # Track current view for context-sensitive utilities
        current_view = {"name": "Home", "key": "home"}

        # Container for current view
        view_container = ui.column().classes("w-full h-full")

        # UI references for dynamic updates
        current_view_label = None
        utility_menu = None

        # Header - minimal, efficient design
        with ui.header().classes("items-center justify-between bg-primary text-white py-1 px-4"):
            # Left side: Hamburger menu + Title + Current view
            with ui.row().classes("items-center gap-3"):
                # Hamburger menu
                with ui.button(icon="menu").props("flat round dense").classes("text-white"):
                    with ui.menu().classes("bg-white text-gray-800"):
                        ui.menu_item(
                            "Home",
                            on_click=lambda: (show_home(), update_view("Home", "home")),
                        ).classes("hover:bg-blue-50")
                        ui.separator()
                        ui.menu_item(
                            "Census Batch Processing",
                            on_click=lambda: (show_batch_processing(), update_view("Census Batch", "census_batch")),
                        ).props("icon=playlist_add_check")
                        ui.menu_item(
                            "Find a Grave",
                            on_click=lambda: (show_findagrave_batch(), update_view("Find a Grave", "findagrave")),
                        ).props("icon=account_box")
                        ui.menu_item(
                            "Citation Manager",
                            on_click=lambda: (show_citation_manager(), update_view("Citation Manager", "citation_manager")),
                        ).props("icon=format_quote")
                        ui.menu_item(
                            "Census Transcription",
                            on_click=lambda: (show_census_transcription(), update_view("Census Transcription", "census_transcription")),
                        ).props("icon=auto_awesome")
                        ui.menu_item(
                            "Census Extractions",
                            on_click=lambda: (show_census_extraction_viewer(), update_view("Census Extractions", "census_extractions")),
                        ).props("icon=folder_open")

                # App title (clickable to go home)
                ui.button(
                    "RMCiteCraft",
                    on_click=lambda: (show_home(), update_view("Home", "home"))
                ).props("flat dense").classes("text-xl font-bold text-white hover:bg-blue-700 px-2")

                # Separator
                ui.label("|").classes("text-blue-300 mx-1")

                # Current view indicator
                current_view_label = ui.label("Home").classes("text-sm text-blue-100")

            # Center: Tagline
            ui.label("Citation Assistant for RootsMagic").classes("text-xs text-blue-200 hidden md:block")

            # Right side: Context-sensitive utility menu + Settings
            with ui.row().classes("items-center gap-1"):
                # Utility button with context menu
                with ui.button(icon="build").props("flat round dense").classes("text-white") as utility_btn:
                    utility_menu = ui.menu().classes("bg-white text-gray-800")
                    with utility_menu:
                        # Default utilities (shown on Home)
                        ui.label("Utilities").classes("px-4 py-1 text-xs text-gray-500 font-bold")
                        ui.menu_item(
                            "Log Settings",
                            on_click=lambda: show_log_settings_dialog(),
                        ).props("icon=bug_report")
                        ui.menu_item(
                            "View Log File",
                            on_click=lambda: show_log_viewer(),
                        ).props("icon=description")
                        ui.separator()
                        ui.menu_item(
                            "Database Info",
                            on_click=lambda: show_database_info(),
                        ).props("icon=storage")

                # Settings button
                ui.button(icon="settings", on_click=lambda: settings_dialog()).props(
                    "flat round dense"
                ).classes("text-white")

        def update_view(name: str, key: str) -> None:
            """Update the current view indicator and utility menu."""
            nonlocal current_view
            current_view["name"] = name
            current_view["key"] = key
            if current_view_label:
                current_view_label.set_text(name)
            # Update utility menu based on context
            update_utility_menu(key)

        def update_utility_menu(view_key: str) -> None:
            """Update utility menu items based on current view."""
            if not utility_menu:
                return
            utility_menu.clear()
            with utility_menu:
                ui.label("Utilities").classes("px-4 py-1 text-xs text-gray-500 font-bold")

                if view_key == "census_extractions":
                    ui.menu_item(
                        "Clear Census DB",
                        on_click=lambda: trigger_clear_census_db(),
                    ).props("icon=delete_forever").classes("text-red-600")
                    ui.menu_item(
                        "Export Data",
                        on_click=lambda: ui.notify("Export not implemented", type="info"),
                    ).props("icon=file_download")
                    ui.separator()

                elif view_key == "findagrave":
                    ui.menu_item(
                        "Reset Failed Items",
                        on_click=lambda: ui.notify("Reset not implemented", type="info"),
                    ).props("icon=refresh")
                    ui.menu_item(
                        "Export Report",
                        on_click=lambda: ui.notify("Export not implemented", type="info"),
                    ).props("icon=assessment")
                    ui.separator()

                elif view_key == "census_batch":
                    ui.menu_item(
                        "Clear Batch State",
                        on_click=lambda: ui.notify("Clear state not implemented", type="info"),
                    ).props("icon=clear_all")
                    ui.separator()

                # Common utilities always available
                ui.menu_item(
                    "Log Settings",
                    on_click=lambda: show_log_settings_dialog(),
                ).props("icon=bug_report")
                ui.menu_item(
                    "View Log File",
                    on_click=lambda: show_log_viewer(),
                ).props("icon=description")
                ui.separator()
                ui.menu_item(
                    "Database Info",
                    on_click=lambda: show_database_info(),
                ).props("icon=storage")

        def trigger_clear_census_db() -> None:
            """Trigger census DB clear from the census extraction viewer."""
            # Find and call the clear method on the census viewer
            from rmcitecraft.database.census_extraction_db import get_census_repository
            repo = get_census_repository()

            with ui.dialog() as dialog, ui.card().classes("w-96"):
                ui.label("Clear Census Database").classes("text-lg font-bold text-red-600")
                ui.label("This will permanently delete ALL extracted data.").classes("text-sm text-gray-600 my-2")
                stats = repo.get_extraction_stats()
                ui.label(f"Data: {stats.get('total_persons', 0)} persons, {stats.get('total_pages', 0)} pages").classes("text-sm font-medium")

                with ui.row().classes("w-full justify-end gap-2 mt-4"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")

                    def do_clear():
                        with repo._connect() as conn:
                            conn.execute("DELETE FROM rmtree_link")
                            conn.execute("DELETE FROM census_relationship")
                            conn.execute("DELETE FROM field_quality")
                            conn.execute("DELETE FROM census_person_field")
                            conn.execute("DELETE FROM census_person")
                            conn.execute("DELETE FROM census_page")
                            conn.execute("DELETE FROM extraction_batch")
                        ui.notify("Census database cleared", type="positive")
                        dialog.close()
                        # Refresh the view
                        show_census_extraction_viewer()
                        update_view("Census Extractions", "census_extractions")

                    ui.button("Delete All", icon="delete_forever", on_click=do_clear).props("color=red")
            dialog.open()

        def show_log_settings_dialog() -> None:
            """Show log settings dialog."""
            with ui.dialog() as dialog, ui.card().classes("w-96"):
                ui.label("Log Settings").classes("text-lg font-bold mb-2")
                ui.label(f"Current Level: {config.log_level}").classes("text-sm mb-2")

                level_select = ui.select(
                    options=["DEBUG", "INFO", "WARNING", "ERROR"],
                    value=config.log_level,
                    label="Log Level",
                ).classes("w-full")

                ui.label("Note: Changes take effect on app restart").classes("text-xs text-gray-500 mt-2")

                with ui.row().classes("w-full justify-end gap-2 mt-4"):
                    ui.button("Close", on_click=dialog.close).props("flat")
            dialog.open()

        def show_log_viewer() -> None:
            """Show log file viewer."""
            log_path = Path(config.log_file)
            content = ""
            if log_path.exists():
                try:
                    content = log_path.read_text()[-10000:]  # Last 10KB
                except Exception as e:
                    content = f"Error reading log: {e}"

            with ui.dialog() as dialog, ui.card().classes("w-[80vw] h-[70vh]"):
                with ui.row().classes("w-full items-center justify-between mb-2"):
                    ui.label("Application Log").classes("text-lg font-bold")
                    ui.button(icon="close", on_click=dialog.close).props("flat round dense")
                ui.label(f"File: {log_path}").classes("text-xs text-gray-500 mb-2")
                with ui.scroll_area().classes("w-full flex-1 bg-gray-900 rounded"):
                    ui.html(f"<pre class='text-xs text-green-400 p-2 whitespace-pre-wrap'>{content}</pre>", sanitize=False)
            dialog.open()

        def show_database_info() -> None:
            """Show database information dialog."""
            with ui.dialog() as dialog, ui.card().classes("w-96"):
                ui.label("Database Information").classes("text-lg font-bold mb-2")
                ui.separator()
                ui.label("RootsMagic Database").classes("font-bold text-sm mt-2")
                ui.label(f"Path: {config.rm_database_path}").classes("text-xs font-mono")
                db_path = Path(config.rm_database_path)
                if db_path.exists():
                    size_mb = db_path.stat().st_size / (1024 * 1024)
                    ui.label(f"Size: {size_mb:.1f} MB").classes("text-xs")
                    ui.label("Status: Connected").classes("text-xs text-green-600")
                else:
                    ui.label("Status: Not Found").classes("text-xs text-red-600")

                ui.separator()
                ui.label("Census Extraction DB").classes("font-bold text-sm mt-2")
                from rmcitecraft.database.census_extraction_db import get_census_repository
                repo = get_census_repository()
                stats = repo.get_extraction_stats()
                ui.label(f"Persons: {stats.get('total_persons', 0)}").classes("text-xs")
                ui.label(f"Pages: {stats.get('total_pages', 0)}").classes("text-xs")

                with ui.row().classes("w-full justify-end mt-4"):
                    ui.button("Close", on_click=dialog.close).props("flat")
            dialog.open()

        def show_home() -> None:
            """Show home view."""
            view_container.clear()
            with view_container, ui.column().classes("w-full items-center p-6 gap-4"):
                # Hero Section - Compact
                with ui.card().classes("w-full max-w-6xl p-6 bg-gradient-to-r from-blue-50 to-indigo-50"):
                    with ui.row().classes("items-center gap-4"):
                        ui.icon("auto_stories", size="3rem").classes("text-blue-700")
                        with ui.column().classes("flex-1"):
                            ui.label("RMCiteCraft").classes("text-3xl font-bold text-blue-900")
                            ui.label("Citation Assistant for RootsMagic").classes("text-lg text-gray-600")
                    ui.label(
                        "Transform genealogy citations into Evidence Explained format with AI-powered extraction and automation."
                    ).classes("text-sm text-gray-500 mt-2")

                # 5 Function Cards - Main Grid
                ui.label("Functions").classes("text-xl font-bold text-gray-700 self-start max-w-6xl w-full")

                with ui.row().classes("w-full max-w-6xl gap-3"):
                    # Card 1: Census Batch Processing
                    with ui.card().classes(
                        "flex-1 p-4 cursor-pointer hover:shadow-lg transition-shadow border-l-4 border-blue-500"
                    ).on("click", lambda: (show_batch_processing(), update_view("Census Batch", "census_batch"))):
                        with ui.row().classes("items-center gap-2 mb-2"):
                            ui.icon("playlist_add_check", size="md").classes("text-blue-600")
                            ui.label("Census Batch").classes("font-bold text-blue-800")
                        ui.label("Batch process FamilySearch census records with AI extraction").classes("text-xs text-gray-600")
                        with ui.row().classes("mt-2 gap-1 flex-wrap"):
                            ui.badge("1790-1950", color="blue").props("outline").classes("text-xs")
                            ui.badge("AI", color="blue").props("outline").classes("text-xs")
                            ui.badge("Images", color="blue").props("outline").classes("text-xs")

                    # Card 2: Find a Grave
                    with ui.card().classes(
                        "flex-1 p-4 cursor-pointer hover:shadow-lg transition-shadow border-l-4 border-green-500"
                    ).on("click", lambda: (show_findagrave_batch(), update_view("Find a Grave", "findagrave"))):
                        with ui.row().classes("items-center gap-2 mb-2"):
                            ui.icon("account_box", size="md").classes("text-green-600")
                            ui.label("Find a Grave").classes("font-bold text-green-800")
                        ui.label("Extract memorial data, photos, and create burial events").classes("text-xs text-gray-600")
                        with ui.row().classes("mt-2 gap-1 flex-wrap"):
                            ui.badge("Automation", color="green").props("outline").classes("text-xs")
                            ui.badge("Photos", color="green").props("outline").classes("text-xs")
                            ui.badge("Events", color="green").props("outline").classes("text-xs")

                    # Card 3: Citation Manager
                    with ui.card().classes(
                        "flex-1 p-4 cursor-pointer hover:shadow-lg transition-shadow border-l-4 border-purple-500"
                    ).on("click", lambda: (show_citation_manager(), update_view("Citation Manager", "citation_manager"))):
                        with ui.row().classes("items-center gap-2 mb-2"):
                            ui.icon("format_quote", size="md").classes("text-purple-600")
                            ui.label("Citation Manager").classes("font-bold text-purple-800")
                        ui.label("View and manage Evidence Explained citations in RootsMagic").classes("text-xs text-gray-600")
                        with ui.row().classes("mt-2 gap-1 flex-wrap"):
                            ui.badge("Browse", color="purple").props("outline").classes("text-xs")
                            ui.badge("Edit", color="purple").props("outline").classes("text-xs")
                            ui.badge("Validate", color="purple").props("outline").classes("text-xs")

                with ui.row().classes("w-full max-w-6xl gap-3"):
                    # Card 4: Census Transcription
                    with ui.card().classes(
                        "flex-1 p-4 cursor-pointer hover:shadow-lg transition-shadow border-l-4 border-amber-500"
                    ).on("click", lambda: (show_census_transcription(), update_view("Census Transcription", "census_transcription"))):
                        with ui.row().classes("items-center gap-2 mb-2"):
                            ui.icon("auto_awesome", size="md").classes("text-amber-600")
                            ui.label("Census Transcription").classes("font-bold text-amber-800")
                        ui.label("AI-assisted transcription from census images with schema validation").classes("text-xs text-gray-600")
                        with ui.row().classes("mt-2 gap-1 flex-wrap"):
                            ui.badge("AI OCR", color="amber").props("outline").classes("text-xs")
                            ui.badge("Schema", color="amber").props("outline").classes("text-xs")
                            ui.badge("1950", color="amber").props("outline").classes("text-xs")

                    # Card 5: Census Extractions
                    with ui.card().classes(
                        "flex-1 p-4 cursor-pointer hover:shadow-lg transition-shadow border-l-4 border-teal-500"
                    ).on("click", lambda: (show_census_extraction_viewer(), update_view("Census Extractions", "census_extractions"))):
                        with ui.row().classes("items-center gap-2 mb-2"):
                            ui.icon("folder_open", size="md").classes("text-teal-600")
                            ui.label("Census Extractions").classes("font-bold text-teal-800")
                        ui.label("View, verify, and edit extracted FamilySearch census data").classes("text-xs text-gray-600")
                        with ui.row().classes("mt-2 gap-1 flex-wrap"):
                            ui.badge("Verify", color="teal").props("outline").classes("text-xs")
                            ui.badge("Edit", color="teal").props("outline").classes("text-xs")
                            ui.badge("Quality", color="teal").props("outline").classes("text-xs")

                    # Spacer to balance the row
                    ui.element("div").classes("flex-1")

                # Quick Stats Row
                with ui.card().classes("w-full max-w-6xl p-3 bg-gray-50"):
                    with ui.row().classes("w-full justify-around items-center"):
                        # Census DB stats
                        from rmcitecraft.database.census_extraction_db import get_census_repository
                        repo = get_census_repository()
                        stats = repo.get_extraction_stats()

                        with ui.column().classes("items-center"):
                            ui.label(f"{stats.get('total_persons', 0)}").classes("text-2xl font-bold text-blue-600")
                            ui.label("Census Persons").classes("text-xs text-gray-500")

                        ui.separator().props("vertical").classes("h-8")

                        with ui.column().classes("items-center"):
                            ui.label(f"{stats.get('total_pages', 0)}").classes("text-2xl font-bold text-green-600")
                            ui.label("Census Pages").classes("text-xs text-gray-500")

                        ui.separator().props("vertical").classes("h-8")

                        with ui.column().classes("items-center"):
                            ui.label(f"{stats.get('rmtree_links', 0)}").classes("text-2xl font-bold text-purple-600")
                            ui.label("RootsMagic Links").classes("text-xs text-gray-500")

                        ui.separator().props("vertical").classes("h-8")

                        db_path = Path(config.rm_database_path)
                        db_status = "Connected" if db_path.exists() else "Not Found"
                        db_color = "text-green-600" if db_path.exists() else "text-red-600"
                        with ui.column().classes("items-center"):
                            ui.icon("storage", size="md").classes(db_color)
                            ui.label(db_status).classes(f"text-xs {db_color}")

                # Collapsible sections
                with ui.expansion("System Configuration", icon="settings").classes("w-full max-w-6xl"):
                    with ui.row().classes("w-full gap-6 p-2"):
                        with ui.column().classes("flex-1"):
                            ui.label("Database").classes("font-bold text-sm")
                            ui.label(f"{config.rm_database_path}").classes("text-xs font-mono text-gray-600")
                        with ui.column().classes("flex-1"):
                            ui.label("LLM Provider").classes("font-bold text-sm")
                            ui.label(f"{config.default_llm_provider}").classes("text-xs text-gray-600")
                        with ui.column().classes("flex-1"):
                            ui.label("Log Level").classes("font-bold text-sm")
                            ui.label(f"{config.log_level}").classes("text-xs text-gray-600")

                with ui.expansion("Documentation", icon="menu_book").classes("w-full max-w-6xl"):
                    with ui.row().classes("gap-6 p-2 flex-wrap"):
                        ui.link("Database Schema", "docs/reference/schema-reference.md", new_tab=True).classes("text-sm text-blue-600")
                        ui.link("LLM Architecture", "docs/architecture/LLM-ARCHITECTURE.md", new_tab=True).classes("text-sm text-blue-600")
                        ui.link("Batch Processing", "docs/architecture/BATCH_PROCESSING_ARCHITECTURE.md", new_tab=True).classes("text-sm text-blue-600")
                        ui.link("Census DB Schema", "docs/reference/CENSUS_EXTRACTION_DATABASE_SCHEMA.md", new_tab=True).classes("text-sm text-blue-600")
                        ui.link("CLAUDE.md", "CLAUDE.md", new_tab=True).classes("text-sm text-blue-600")
                        ui.link("README", "README.md", new_tab=True).classes("text-sm text-blue-600")

        def show_batch_processing() -> None:
            """Show census batch processing view."""
            view_container.clear()
            with view_container:
                batch_processing = BatchProcessingTab()
                batch_processing.render()

        def show_findagrave_batch() -> None:
            """Show Find a Grave batch processing view."""
            view_container.clear()
            with view_container:
                findagrave_batch = FindAGraveBatchTab()
                findagrave_batch.render()

        def show_citation_manager() -> None:
            """Show citation manager view."""
            nonlocal citation_manager
            view_container.clear()
            with view_container:
                citation_manager = CitationManagerTab()
                citation_manager.render()

        def show_census_transcription() -> None:
            """Show census transcription view."""
            view_container.clear()
            with view_container:
                census_transcription = CensusTranscriptionTab()
                census_transcription.render()

        def show_census_extraction_viewer() -> None:
            """Show census extraction viewer."""
            view_container.clear()
            with view_container:
                census_viewer = CensusExtractionViewerTab()
                census_viewer.render()

        # Show home by default
        show_home()

        # Global error panel (floating button in bottom-right)
        create_error_panel()

    def settings_dialog() -> None:
        """Show settings dialog."""
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label("Settings").classes("text-xl font-bold mb-4")
            ui.separator()

            with ui.column().classes("w-full gap-4 p-4"):
                ui.label(f"Database: {config.rm_database_path}").classes("text-sm")
                ui.label(f"LLM Provider: {config.default_llm_provider}").classes("text-sm")
                ui.label(f"Log Level: {config.log_level}").classes("text-sm")

                ui.separator()

                ui.button("Close", on_click=dialog.close).props("flat")

        dialog.open()


def main() -> None:
    """Entry point for the RMCitecraft application."""
    import sys

    # Trick NiceGUI into thinking we're in __main__
    # This is needed when called as an entry point script
    original_main = sys.modules.get("__main__")
    sys.modules["__main__"] = sys.modules[__name__]

    try:
        # Set up the app routes
        setup_app()

        # Run the application
        # Native mode can be toggled via RMCITECRAFT_NATIVE environment variable
        native_mode = os.getenv("RMCITECRAFT_NATIVE", "false").lower() == "true"

        logger.info(f"Running in {'native' if native_mode else 'browser'} mode")

        ui.run(
            title="RMCitecraft",
            native=native_mode,
            reload=not native_mode,  # Only reload in browser mode
            show=True,
            port=8080,
        )
    finally:
        # Restore original __main__
        if original_main:
            sys.modules["__main__"] = original_main


if __name__ in {"__main__", "__mp_main__"}:
    main()
