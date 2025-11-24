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

        # Container for current view
        view_container = ui.column().classes("w-full h-full")

        # Header with integrated navigation
        with ui.header().classes("items-center justify-between bg-primary text-white"):
            with ui.row().classes("items-center gap-6"):
                # RMCitecraft as home link (using button styled as text)
                ui.button(
                    "RMCitecraft",
                    on_click=lambda: show_home()
                ).props("flat").classes("text-2xl font-bold text-white hover:bg-blue-700")

                # Navigation buttons integrated into header
                ui.button(
                    "Census Batch",
                    icon="playlist_add_check",
                    on_click=lambda: show_batch_processing()
                ).props("flat").classes("text-white")

                ui.button(
                    "Find a Grave",
                    icon="account_box",
                    on_click=lambda: show_findagrave_batch()
                ).props("flat").classes("text-white")

                ui.button(
                    "Citation Manager",
                    icon="format_quote",
                    on_click=lambda: show_citation_manager()
                ).props("flat").classes("text-white")

            with ui.row().classes("items-center gap-4"):
                ui.label("Citation Assistant for RootsMagic").classes("text-sm")
                ui.button(icon="settings", on_click=lambda: settings_dialog()).props(
                    "flat round dense"
                )

        def show_home() -> None:
            """Show home view."""
            view_container.clear()
            with view_container, ui.column().classes("w-full items-center p-8 gap-6"):
                # Hero Section
                with ui.card().classes("w-full max-w-5xl p-8 bg-gradient-to-r from-blue-50 to-indigo-50"):
                    ui.label("RMCitecraft").classes("text-4xl font-bold text-blue-900 mb-2")
                    ui.label("Professional Citation Management for RootsMagic").classes("text-xl text-gray-700 mb-4")
                    ui.markdown("""
                        Automate the transformation of genealogy citations into **Evidence Explained** compliant format.
                        Process census records and Find a Grave memorials with AI-powered extraction, intelligent batch processing,
                        and seamless RootsMagic database integration.
                    """).classes("text-gray-600")

                # Quick Action Buttons
                with ui.row().classes("w-full max-w-5xl gap-4 justify-center"):
                    ui.button("Census Batch", icon="playlist_add_check", on_click=lambda: show_batch_processing()).props("size=lg").classes("bg-blue-600 text-white")
                    ui.button("Find a Grave", icon="account_box", on_click=lambda: show_findagrave_batch()).props("size=lg").classes("bg-green-600 text-white")
                    ui.button("Citation Manager", icon="format_quote", on_click=lambda: show_citation_manager()).props("size=lg").classes("bg-purple-600 text-white")

                # Core Features
                with ui.card().classes("w-full max-w-5xl p-6"):
                    ui.label("Core Features").classes("text-2xl font-bold mb-4")

                    with ui.row().classes("w-full gap-6"):
                        # Column 1: Census Processing
                        with ui.column().classes("flex-1 gap-2"):
                            ui.label("Census Citation Processing").classes("font-bold text-lg text-blue-700 mb-2")
                            ui.markdown("""
                                - **1790-1950 Coverage**: All decennial census years
                                - **AI Extraction**: Multi-provider LLM (Claude, GPT, Ollama)
                                - **Evidence Explained Format**: Footnote, short footnote, bibliography
                                - **Browser Integration**: Side-by-side FamilySearch viewing for missing data
                                - **Image Automation**: Download, rename, organize, and link census images
                            """).classes("text-sm")

                        # Column 2: Find a Grave
                        with ui.column().classes("flex-1 gap-2"):
                            ui.label("Find a Grave Integration").classes("font-bold text-lg text-green-700 mb-2")
                            ui.markdown("""
                                - **5,376+ Memorials**: Batch process Find a Grave URLs from RootsMagic
                                - **Browser Automation**: Playwright extraction with maiden name detection
                                - **Photo Downloads**: Person, grave, and family photos with categorization
                                - **Burial Events**: Auto-create events with cemetery locations and details
                                - **Dashboard Analytics**: Monitor processing status, success rates, and errors across batches
                                - **State Persistence**: Resume interrupted sessions with checkpoint recovery
                            """).classes("text-sm")

                # Technical Capabilities (Consolidated)
                with ui.card().classes("w-full max-w-5xl p-6"):
                    ui.label("Technical Capabilities").classes("text-2xl font-bold mb-4")

                    with ui.row().classes("w-full gap-6"):
                        # Left column
                        with ui.column().classes("flex-1"):
                            ui.label("Database & Integration").classes("font-bold text-lg mb-2")
                            ui.markdown("""
                                - RMNOCASE collation support (SQLite ICU)
                                - BLOB field parsing for free-form sources
                                - Transaction safety with atomic writes
                                - File watcher for automatic downloads
                            """).classes("text-sm")

                        # Right column
                        with ui.column().classes("flex-1"):
                            ui.label("AI & Automation").classes("font-bold text-lg mb-2")
                            ui.markdown("""
                                - Multi-provider LLM with prompt caching (90% token reduction)
                                - Page health monitoring and adaptive timeouts
                                - Retry strategies with configurable recovery
                                - Census transcriber for AI-assisted data entry
                            """).classes("text-sm")

                # Workflow Overview (Simplified)
                with ui.card().classes("w-full max-w-5xl p-6"):
                    ui.label("How It Works").classes("text-2xl font-bold mb-4")

                    with ui.expansion("Census Workflow", icon="filter_1").classes("w-full"):
                        ui.markdown("""
                            Load census year → AI extracts data → Review/correct missing fields →
                            Generate Evidence Explained citations → Auto-download/organize images →
                            Save to database with quality control logging
                        """).classes("text-sm")

                    with ui.expansion("Find a Grave Workflow", icon="filter_2").classes("w-full"):
                        ui.markdown("""
                            Load memorial batch → Browser automation extracts data & photos →
                            Detect maiden names → Create burial events with cemetery locations →
                            Generate Evidence Explained citations → Save to database →
                            Dashboard monitors progress with error tracking
                        """).classes("text-sm")

                # System Status
                with ui.expansion("System Status & Configuration", icon="settings").classes("w-full max-w-5xl"):
                    with ui.column().classes("gap-2 p-2"):
                        ui.label("Database Configuration").classes("font-bold")
                        ui.label(f"Database: {config.rm_database_path}").classes("text-sm font-mono")
                        ui.label(f"Working Copy: {Path(config.rm_database_path).name}").classes("text-sm text-gray-600")

                        ui.separator()

                        ui.label("LLM Configuration").classes("font-bold")
                        ui.label(f"Provider: {config.default_llm_provider}").classes("text-sm")
                        ui.label(f"Model: {getattr(config, f'{config.default_llm_provider}_model', 'N/A')}").classes("text-sm")

                        ui.separator()

                        ui.label("Application Settings").classes("font-bold")
                        ui.label(f"Log Level: {config.log_level}").classes("text-sm")
                        ui.label(f"Log File: {config.log_file}").classes("text-sm font-mono")

                # Documentation Links
                with ui.card().classes("w-full max-w-5xl p-6 bg-gray-50"):
                    ui.label("Documentation & Resources").classes("text-xl font-bold mb-3")
                    with ui.row().classes("gap-4 w-full"):
                        # Implementation Guides
                        with ui.column().classes("flex-1 gap-2"):
                            ui.label("Implementation Guides").classes("font-bold text-sm mb-1")
                            ui.link("LLM Architecture", "docs/architecture/LLM-ARCHITECTURE.md", new_tab=True).classes("text-sm text-blue-600 hover:underline")
                            ui.link("Database Schema", "docs/reference/schema-reference.md", new_tab=True).classes("text-sm text-blue-600 hover:underline")
                            ui.link("Image Management", "docs/architecture/IMAGE-MANAGEMENT-ARCHITECTURE.md", new_tab=True).classes("text-sm text-blue-600 hover:underline")
                            ui.link("Batch Processing Architecture", "docs/architecture/BATCH_PROCESSING_ARCHITECTURE.md", new_tab=True).classes("text-sm text-blue-600 hover:underline")

                        # User Guides
                        with ui.column().classes("flex-1 gap-2"):
                            ui.label("User Guides").classes("font-bold text-sm mb-1")
                            ui.link("Image Workflow", "docs/user-guides/IMAGE-WORKFLOW.md", new_tab=True).classes("text-sm text-blue-600 hover:underline")
                            ui.link("Batch Processing", "docs/BATCH_PROCESSING_PHASE1_IMPLEMENTATION.md", new_tab=True).classes("text-sm text-blue-600 hover:underline")
                            ui.link("Find a Grave", "docs/FINDAGRAVE-IMPLEMENTATION.md", new_tab=True).classes("text-sm text-blue-600 hover:underline")
                            ui.link("Dashboard Design", "docs/DASHBOARD_DESIGN.md", new_tab=True).classes("text-sm text-blue-600 hover:underline")

                        # Developer Docs
                        with ui.column().classes("flex-1 gap-2"):
                            ui.label("Developer Docs").classes("font-bold text-sm mb-1")
                            ui.link("CLAUDE.md", "CLAUDE.md", new_tab=True).classes("text-sm text-blue-600 hover:underline").tooltip("AI assistant guide")
                            ui.link("AGENTS.md", "AGENTS.md", new_tab=True).classes("text-sm text-blue-600 hover:underline").tooltip("Machine-readable instructions")
                            ui.link("PRD.md", "PRD.md", new_tab=True).classes("text-sm text-blue-600 hover:underline").tooltip("Product requirements")
                            ui.link("README.md", "README.md", new_tab=True).classes("text-sm text-blue-600 hover:underline").tooltip("Project overview")

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
