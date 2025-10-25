"""Main application entry point for RMCitecraft."""

import os

from fastapi.middleware.cors import CORSMiddleware
from nicegui import app, ui
from loguru import logger

from rmcitecraft.api import create_api_router
from rmcitecraft.config import get_config
from rmcitecraft.ui.tabs.citation_manager import CitationManagerTab


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

    # Store tab instances for cleanup
    citation_manager: CitationManagerTab | None = None

    @ui.page("/")
    def index() -> None:
        """Main application page."""
        nonlocal citation_manager

        ui.page_title("RMCitecraft - Census Citation Assistant")

        # Header
        with ui.header().classes("items-center justify-between bg-primary text-white"):
            ui.label("RMCitecraft").classes("text-2xl font-bold")
            with ui.row().classes("items-center gap-4"):
                ui.label("Census Citation Assistant for RootsMagic").classes("text-sm")
                ui.button(icon="settings", on_click=lambda: settings_dialog()).props(
                    "flat round dense"
                )

        # Main content with tabs
        with ui.tabs().classes("w-full") as tabs:
            tab_home = ui.tab("Home", icon="home")
            tab_citations = ui.tab("Citation Manager", icon="format_quote")
            tab_images = ui.tab("Image Manager", icon="image")

        with ui.tab_panels(tabs, value=tab_home).classes("w-full h-full"):
            # Home tab
            with ui.tab_panel(tab_home):
                with ui.column().classes("w-full items-center p-8"):
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

                        Click on **Citation Manager** to begin processing your citations.

                        """)

                    with ui.expansion("System Status", icon="info").classes(
                        "w-full max-w-4xl"
                    ):
                        ui.label(f"Database: {config.rm_database_path}").classes("text-sm")
                        ui.label(f"LLM Provider: {config.default_llm_provider}").classes(
                            "text-sm"
                        )
                        ui.label(f"Log Level: {config.log_level}").classes("text-sm")

            # Citation Manager tab
            with ui.tab_panel(tab_citations).classes("w-full h-full"):
                citation_manager = CitationManagerTab()
                citation_manager.render()

            # Image Manager tab (placeholder)
            with ui.tab_panel(tab_images):
                with ui.column().classes("w-full h-full items-center justify-center"):
                    ui.icon("image").classes("text-6xl text-gray-400")
                    ui.label("Image Manager").classes("text-2xl font-bold text-gray-600")
                    ui.label("Coming in Phase 3").classes("text-gray-500")

    def settings_dialog() -> None:
        """Show settings dialog."""
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label("Settings").classes("text-xl font-bold mb-4")
            ui.separator()

            with ui.column().classes("w-full gap-4 p-4"):
                ui.label(f"Database: {config.rm_database_path}").classes("text-sm")
                ui.label(f"LLM Provider: {config.default_llm_provider}").classes(
                    "text-sm"
                )
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
