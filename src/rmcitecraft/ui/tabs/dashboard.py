"""Dashboard tab for Find a Grave batch operations monitoring."""

from nicegui import ui

from rmcitecraft.config import Config
from rmcitecraft.database.batch_state_repository import BatchStateRepository
from rmcitecraft.ui.components.dashboard import (
    CitationsStatsCard,
    ItemDetailPanel,
    ItemsTable,
    MasterProgressCard,
    PhotosStatsCard,
    ProcessingTimelineChart,
    SessionSelectorCard,
    StatusDistributionChart,
)


class DashboardTab:
    """Dashboard tab for monitoring Find a Grave batch operations.

    Provides visibility into batch processing operations across thousands of URLs,
    with drill-down capabilities and outlier detection.
    """

    def __init__(self, config: Config):
        """Initialize dashboard tab.

        Args:
            config: Application configuration
        """
        self._config = config  # Private to avoid JSON serialization
        self._state_repo = BatchStateRepository()
        self.auto_refresh_enabled = True
        self.refresh_interval = 5  # seconds
        self._refresh_timer = None

        # Components
        self._master_progress = None
        self._session_selector = None
        self._status_distribution = None
        self._processing_timeline = None
        self._photos_stats = None
        self._citations_stats = None
        self._items_table = None
        self._item_detail = None
        self.current_session_id: str | None = None

    def render(self) -> None:
        """Render the complete dashboard with all phases."""
        from loguru import logger
        logger.info("DashboardTab.render() starting - FULL DASHBOARD")

        # Main container
        with ui.column().classes('w-full p-4 gap-6'):
            # Header with controls
            self._render_header()

            # Phase 1: Master Progress + Session Selector
            self._master_progress = MasterProgressCard(self._state_repo)
            self._master_progress.render()

            self._session_selector = SessionSelectorCard(
                self._state_repo,
                on_session_change=self._on_session_change
            )
            self._session_selector.render()

            # Phase 2: Charts (2-column layout)
            with ui.grid(columns=2).classes('w-full gap-4'):
                # Status Distribution Chart
                self._status_distribution = StatusDistributionChart(
                    self._state_repo,
                    session_id=self.current_session_id,
                    on_status_click=self._on_status_click
                )
                self._status_distribution.render()

                # Processing Timeline Chart
                self._processing_timeline = ProcessingTimelineChart(
                    self._state_repo,
                    session_id=self.current_session_id,
                    on_point_click=self._on_timeline_point_click
                )
                self._processing_timeline.render()

            # Phase 2.5: Photos & Citations Statistics (2-column layout)
            with ui.grid(columns=2).classes('w-full gap-4'):
                # Photos Statistics
                self._photos_stats = PhotosStatsCard(
                    self._state_repo,
                    session_id=self.current_session_id
                )
                self._photos_stats.render()

                # Citations Statistics
                self._citations_stats = CitationsStatsCard(
                    self._state_repo,
                    self._config.rm_database_path,
                    session_id=self.current_session_id
                )
                self._citations_stats.render()

            # Phase 3: Items Table + Detail Panel (2-column layout)
            with ui.grid(columns=2).classes('w-full gap-4'):
                # Items Table (searchable/filterable)
                self._items_table = ItemsTable(
                    self._state_repo,
                    session_id=self.current_session_id,
                    on_row_click=self._on_table_row_click
                )
                self._items_table.render()

                # Item Detail Panel (RootsMagic drill-down)
                self._item_detail = ItemDetailPanel(
                    rm_database_path=self._config.rm_database_path
                )
                self._item_detail.render()

            # Phase 4+ placeholder
            self._render_coming_soon_phase4()

            # Setup auto-refresh
            self._setup_auto_refresh()

        logger.info("Complete dashboard rendered successfully")


    def _render_header(self) -> None:
        """Render dashboard header with controls."""
        with ui.card().classes('w-full bg-primary text-white'):
            with ui.row().classes('w-full justify-between items-center p-4'):
                # Title
                with ui.column().classes('gap-1'):
                    ui.label('Find a Grave Batch Operations Dashboard').classes('text-h5')
                    ui.label(
                        'Monitor progress, analyze errors, and track performance'
                    ).classes('text-caption opacity-80')

                # Controls
                with ui.row().classes('gap-2'):
                    # Auto-refresh toggle
                    with ui.row().classes('items-center gap-2 bg-white/20 rounded px-3 py-1'):
                        ui.switch(
                            'Auto-refresh',
                            value=True,
                            on_change=self._toggle_auto_refresh
                        ).props('dense').classes('text-white')

                        ui.select(
                            [5, 10, 30, 60],
                            value=5,
                            label='Interval (s)',
                            on_change=self._change_refresh_interval
                        ).props('dense dark outlined').classes('w-32')

                    # Manual refresh button
                    ui.button(
                        'Refresh Now',
                        icon='refresh',
                        on_click=self._refresh_all_components
                    ).props('dense outline')

    def _render_coming_soon_phase4(self) -> None:
        """Render placeholder for Phase 4+ components."""
        with ui.card().classes('w-full bg-grey-1'):
            with ui.column().classes('items-center p-8 gap-4'):
                ui.icon('construction').classes('text-6xl text-grey-5')
                ui.label('Additional Dashboard Components Coming Soon').classes('text-h6 text-grey-7')
                ui.label(
                    'Phase 4 will add: Error Analysis (tree map), Performance Heatmap, Media Gallery'
                ).classes('text-sm text-grey-6')
                ui.label(
                    'Phase 5+ will add: Outlier Detection, Cumulative Analytics, Export Tools'
                ).classes('text-sm text-grey-6')

    def _setup_auto_refresh(self) -> None:
        """Setup auto-refresh timer."""
        if self._refresh_timer:
            self._refresh_timer.deactivate()

        self._refresh_timer = ui.timer(
            self.refresh_interval,
            self._refresh_all_components,
            active=self.auto_refresh_enabled
        )

    def _toggle_auto_refresh(self, event) -> None:
        """Toggle auto-refresh on/off.

        Args:
            event: Switch event
        """
        self.auto_refresh_enabled = event.value

        if self.auto_refresh_enabled:
            self._refresh_timer.activate()
            ui.notify('Auto-refresh enabled', type='positive')
        else:
            self._refresh_timer.deactivate()
            ui.notify('Auto-refresh disabled', type='info')

    def _change_refresh_interval(self, event) -> None:
        """Change refresh interval.

        Args:
            event: Select event
        """
        self.refresh_interval = event.value

        # Recreate timer with new interval
        if self._refresh_timer:
            self._refresh_timer.deactivate()

        self._refresh_timer = ui.timer(
            self.refresh_interval,
            self._refresh_all_components,
            active=self.auto_refresh_enabled
        )

        ui.notify(f'Refresh interval set to {self.refresh_interval}s', type='info')

    def _refresh_all_components(self) -> None:
        """Refresh all dashboard components with latest data."""
        if not self.auto_refresh_enabled and self._refresh_timer:
            # Manual refresh - notify user
            ui.notify('Refreshing dashboard...', type='info', position='top')

        # Refresh master progress
        if self._master_progress:
            self._master_progress.update()

        # Refresh session selector
        if self._session_selector:
            self._session_selector._refresh_sessions()

        # Refresh Phase 2 charts
        if self._status_distribution:
            self._status_distribution.update()

        if self._processing_timeline:
            self._processing_timeline.update()

        # Refresh Phase 2.5 statistics
        if self._photos_stats:
            self._photos_stats.update()

        if self._citations_stats:
            self._citations_stats.update()

        # Refresh Phase 3 components
        if self._items_table:
            self._items_table.update()

    def _on_session_change(self, session_id: str | None) -> None:
        """Handle session filter change.

        Args:
            session_id: Selected session ID or None for all sessions
        """
        self.current_session_id = session_id

        # Update Phase 2 charts with new session filter
        if self._status_distribution:
            self._status_distribution.set_session_filter(session_id)

        if self._processing_timeline:
            self._processing_timeline.set_session_filter(session_id)

        # Update Phase 2.5 statistics with new session filter
        if self._photos_stats:
            self._photos_stats.set_session_filter(session_id)

        if self._citations_stats:
            self._citations_stats.set_session_filter(session_id)

        # Update Phase 3 components with new session filter
        if self._items_table:
            self._items_table.set_session_filter(session_id)

    def _on_status_click(self, status: str) -> None:
        """Handle status pie chart slice click.

        Args:
            status: Clicked status name
        """
        # Filter items table by clicked status
        if self._items_table:
            self._items_table.set_status_filter(status)
            ui.notify(f'Filtered table by status: {status}', type='info')

    def _on_timeline_point_click(self, item_data: dict) -> None:
        """Handle timeline chart point click.

        Args:
            item_data: Timeline item data
        """
        # Show item detail panel
        if self._item_detail and item_data:
            self._item_detail.update(item_data)
            ui.notify(f'Viewing details for: {item_data.get("full_name", "Unknown")}', type='info')

    def _on_table_row_click(self, item_data: dict) -> None:
        """Handle items table row click.

        Args:
            item_data: Table row item data
        """
        # Show item detail panel
        if self._item_detail:
            self._item_detail.update(item_data)
            ui.notify(f'Viewing details for: {item_data.get("person_name", "Unknown")}', type='info')
