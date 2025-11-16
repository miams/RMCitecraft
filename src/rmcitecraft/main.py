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

    logger.info("Starting RMCitecraft application")

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
            with view_container, ui.column().classes("w-full items-center p-8"):
                with ui.card().classes("w-full max-w-4xl p-6"):
                    ui.markdown("""
                        ## Welcome to RMCitecraft

                        This application helps you:

                        1. **Transform FamilySearch Citations** - Convert placeholder citations
                           into *Evidence Explained* compliant format
                        2. **Manage Census Images** - Automatically process, rename, and organize
                           downloaded census images

                        ### Foundation Complete ✓

                        The following components are now working:

                        - ✓ Project structure and configuration
                        - ✓ Database connection with RMNOCASE collation support
                        - ✓ FamilySearch citation parser (1790-1950)
                        - ✓ Evidence Explained citation formatter
                        - ✓ LLM integration (Anthropic, OpenAI, Ollama)
                        - ✓ Unit tests (18 tests passing)
                        - ✓ Citation Manager UI

                        ### Get Started

                        Click on **Batch Processing** or **Citation Manager** to begin.

                        """)

                with ui.expansion("System Status", icon="info").classes("w-full max-w-4xl"):
                    ui.label(f"Database: {config.rm_database_path}").classes("text-sm")
                    ui.label(f"LLM Provider: {config.default_llm_provider}").classes("text-sm")
                    ui.label(f"Log Level: {config.log_level}").classes("text-sm")

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
