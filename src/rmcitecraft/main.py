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
from rmcitecraft.ui.tabs.dashboard import DashboardTab


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

                ui.button(
                    "Dashboard",
                    icon="dashboard",
                    on_click=lambda: show_dashboard()
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

                # Quick Links
                with ui.row().classes("w-full max-w-5xl gap-4"):
                    with ui.card().classes("flex-1 p-4 cursor-pointer hover:shadow-lg transition-shadow").on("click", lambda: show_batch_processing()):
                        with ui.row().classes("items-center gap-3"):
                            ui.icon("playlist_add_check", size="2rem").classes("text-blue-600")
                            with ui.column():
                                ui.label("Census Batch Processing").classes("font-bold text-lg")
                                ui.label("Process census citations 1790-1950").classes("text-sm text-gray-600")

                    with ui.card().classes("flex-1 p-4 cursor-pointer hover:shadow-lg transition-shadow").on("click", lambda: show_findagrave_batch()):
                        with ui.row().classes("items-center gap-3"):
                            ui.icon("account_box", size="2rem").classes("text-green-600")
                            with ui.column():
                                ui.label("Find a Grave Batch").classes("font-bold text-lg")
                                ui.label("5,376 memorials ready to process").classes("text-sm text-gray-600")

                    with ui.card().classes("flex-1 p-4 cursor-pointer hover:shadow-lg transition-shadow").on("click", lambda: show_citation_manager()):
                        with ui.row().classes("items-center gap-3"):
                            ui.icon("format_quote", size="2rem").classes("text-purple-600")
                            with ui.column():
                                ui.label("Citation Manager").classes("font-bold text-lg")
                                ui.label("Review and edit citations").classes("text-sm text-gray-600")

                # Core Features
                with ui.card().classes("w-full max-w-5xl p-6"):
                    ui.label("Core Features").classes("text-2xl font-bold mb-4")

                    with ui.row().classes("w-full gap-6"):
                        # Column 1: Census Processing
                        with ui.column().classes("flex-1 gap-2"):
                            ui.label("Census Citation Processing").classes("font-bold text-lg text-blue-700 mb-2")
                            ui.markdown("""
                                - **Full Census Coverage**: 1790-1950 (all decennial census years)
                                - **AI-Powered Extraction**: Multi-provider LLM support (Claude, GPT, Ollama)
                                - **Evidence Explained Format**: Footnote, short footnote, and bibliography
                                - **Missing Data Detection**: Intelligent prompts for incomplete fields
                                - **Browser Integration**: Side-by-side FamilySearch viewing
                                - **Image Automation**: Download, rename, organize census images
                                - **Batch Processing**: Process multiple citations with progress tracking
                            """).classes("text-sm")

                        # Column 2: Find a Grave
                        with ui.column().classes("flex-1 gap-2"):
                            ui.label("Find a Grave Integration").classes("font-bold text-lg text-green-700 mb-2")
                            ui.markdown("""
                                - **Browser Automation**: Playwright-based memorial extraction
                                - **Maiden Name Detection**: Automatic HTML parsing for maiden names
                                - **Photo Downloads**: Person, grave, and family photos
                                - **Cemetery Linking**: Geographic location and cemetery details
                                - **Burial Event Creation**: Automatic RootsMagic event records
                                - **Evidence Explained Citations**: Properly formatted Find a Grave sources
                                - **Database Integration**: 5,376+ memorial URLs ready to process
                            """).classes("text-sm")

                # Technical Capabilities
                with ui.card().classes("w-full max-w-5xl p-6"):
                    ui.label("Technical Architecture").classes("text-2xl font-bold mb-4")

                    with ui.row().classes("w-full gap-6"):
                        # Database Integration
                        with ui.column().classes("flex-1"):
                            ui.label("Database Integration").classes("font-bold text-lg mb-2")
                            ui.markdown("""
                                - **RMNOCASE Collation**: Full SQLite ICU extension support
                                - **BLOB Field Parsing**: XML extraction from CitationTable/SourceTable
                                - **Free-Form Sources**: TemplateID=0 citation storage
                                - **Transaction Safety**: Atomic database writes with rollback
                                - **Schema Validation**: RootsMagic 8/9 compatibility
                            """).classes("text-sm")

                        # Automation & Monitoring
                        with ui.column().classes("flex-1"):
                            ui.label("Automation & Monitoring").classes("font-bold text-lg mb-2")
                            ui.markdown("""
                                - **File Watcher**: Automatic download detection
                                - **Page Health Monitor**: Browser automation reliability
                                - **Adaptive Timeouts**: Dynamic performance optimization
                                - **Retry Strategies**: Configurable error recovery
                                - **State Persistence**: Resume interrupted batch sessions
                            """).classes("text-sm")

                        # AI & LLM
                        with ui.column().classes("flex-1"):
                            ui.label("AI-Powered Processing").classes("font-bold text-lg mb-2")
                            ui.markdown("""
                                - **Multi-Provider LLM**: Anthropic, OpenAI, Ollama support
                                - **Prompt Caching**: 90% token reduction on subsequent calls
                                - **Structured Output**: Pydantic validation for extraction
                                - **Cost Optimization**: Provider selection and local fallback
                                - **Census Transcriber**: AI-assisted data entry
                            """).classes("text-sm")

                # Workflow Overview
                with ui.card().classes("w-full max-w-5xl p-6"):
                    ui.label("How It Works").classes("text-2xl font-bold mb-4")

                    with ui.expansion("Census Citation Workflow", icon="filter_1").classes("w-full"):
                        ui.markdown("""
                            1. **Load Citations**: Select census year (1790-1950) from RootsMagic database
                            2. **AI Extraction**: LLM extracts structured data from FamilySearch text
                            3. **Review & Correct**: UI highlights missing fields with browser assistance
                            4. **Format Citations**: Generate Evidence Explained compliant output
                            5. **Image Download**: Automatic census image processing and linking
                            6. **Save to Database**: Write citations to SourceTable.Fields BLOB
                            7. **Quality Control**: Message log tracks all operations and errors
                        """).classes("text-sm")

                    with ui.expansion("Find a Grave Workflow", icon="filter_2").classes("w-full"):
                        ui.markdown("""
                            1. **Load Memorials**: Query database for Find a Grave URLs (5,376+ available)
                            2. **Browser Automation**: Playwright extracts memorial data and photos
                            3. **Maiden Name Detection**: Parse HTML for italicized maiden names
                            4. **Create Citations**: Generate Evidence Explained format sources
                            5. **Burial Events**: Create or link burial events with cemetery locations
                            6. **Photo Downloads**: Save to categorized directories (Person/Grave/Other)
                            7. **Database Export**: Write Source, Citation, Event, and Media records
                        """).classes("text-sm")

                    with ui.expansion("Image Management", icon="filter_3").classes("w-full"):
                        ui.markdown("""
                            1. **Download Detection**: File watcher monitors ~/Downloads folder
                            2. **Context Matching**: Links downloads to active citation context
                            3. **Filename Generation**: Standardized naming (Year, State, County - Surname, Given)
                            4. **Directory Mapping**: Organizes by census year and schedule type
                            5. **Media Records**: Creates RootsMagic MultimediaTable entries
                            6. **Citation Linking**: Links images to citations and events
                            7. **Caption Generation**: Auto-generates descriptive captions
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
                    with ui.row().classes("gap-4"):
                        with ui.column().classes("flex-1"):
                            ui.markdown("""
                                **Implementation Guides**
                                - [LLM Architecture](docs/architecture/LLM-ARCHITECTURE.md)
                                - [Database Schema](docs/reference/schema-reference.md)
                                - [Image Management](docs/architecture/IMAGE-MANAGEMENT-ARCHITECTURE.md)
                            """).classes("text-sm")
                        with ui.column().classes("flex-1"):
                            ui.markdown("""
                                **User Guides**
                                - [Image Workflow](docs/user-guides/IMAGE-WORKFLOW.md)
                                - [Batch Processing](docs/BATCH_PROCESSING_PHASE1_IMPLEMENTATION.md)
                                - [Find a Grave](docs/FINDAGRAVE-IMPLEMENTATION.md)
                            """).classes("text-sm")
                        with ui.column().classes("flex-1"):
                            ui.markdown("""
                                **Developer Docs**
                                - [CLAUDE.md](CLAUDE.md) - AI assistant guide
                                - [AGENTS.md](AGENTS.md) - Machine-readable instructions
                                - [PRD.md](PRD.md) - Product requirements
                            """).classes("text-sm")

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

        def show_dashboard() -> None:
            """Show batch operations dashboard view."""
            view_container.clear()
            with view_container:
                dashboard = DashboardTab(config)
                dashboard.render()

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
