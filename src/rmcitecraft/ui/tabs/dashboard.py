"""Dashboard tab for Find a Grave batch operations monitoring."""

from nicegui import ui

from rmcitecraft.config import Config
from rmcitecraft.database.batch_state_repository import BatchStateRepository
from rmcitecraft.ui.components.dashboard import MasterProgressCard, SessionSelectorCard


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
        self.config = config
        self.state_repo = BatchStateRepository()
        self.auto_refresh_enabled = True
        self.refresh_interval = 5  # seconds
        self.refresh_timer = None

        # Components
        self.master_progress = None
        self.session_selector = None
        self.current_session_id: str | None = None

    def render(self) -> None:
        """Render the dashboard tab."""
        with ui.column().classes('w-full p-4 gap-6'):
            # Header
            self._render_header()

            # Master Progress Card
            self.master_progress = MasterProgressCard(
                state_repo=self.state_repo,
                total_goal=5000
            )
            self.master_progress.render()

            # Session Selector Card
            self.session_selector = SessionSelectorCard(
                state_repo=self.state_repo,
                on_session_change=self._on_session_change
            )
            self.session_selector.render()

            # Placeholder for Phase 2+ components
            self._render_coming_soon()

        # Start auto-refresh timer
        self._setup_auto_refresh()

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

    def _render_coming_soon(self) -> None:
        """Render placeholder for Phase 2+ components."""
        with ui.card().classes('w-full bg-grey-1'):
            with ui.column().classes('items-center p-8 gap-4'):
                ui.icon('construction').classes('text-6xl text-grey-5')
                ui.label('Additional Dashboard Components Coming Soon').classes('text-h6 text-grey-7')
                ui.label(
                    'Phase 2 will add: Status Distribution Chart, Processing Timeline, Items Table'
                ).classes('text-sm text-grey-6')
                ui.label(
                    'Phase 3 will add: Error Analysis, Performance Heatmap, Item Detail Panel'
                ).classes('text-sm text-grey-6')
                ui.label(
                    'Phase 4+ will add: Outlier Detection, Cumulative Analytics, Export Tools'
                ).classes('text-sm text-grey-6')

    def _setup_auto_refresh(self) -> None:
        """Setup auto-refresh timer."""
        if self.refresh_timer:
            self.refresh_timer.deactivate()

        self.refresh_timer = ui.timer(
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
            self.refresh_timer.activate()
            ui.notify('Auto-refresh enabled', type='positive')
        else:
            self.refresh_timer.deactivate()
            ui.notify('Auto-refresh disabled', type='info')

    def _change_refresh_interval(self, event) -> None:
        """Change refresh interval.

        Args:
            event: Select event
        """
        self.refresh_interval = event.value

        # Recreate timer with new interval
        if self.refresh_timer:
            self.refresh_timer.deactivate()

        self.refresh_timer = ui.timer(
            self.refresh_interval,
            self._refresh_all_components,
            active=self.auto_refresh_enabled
        )

        ui.notify(f'Refresh interval set to {self.refresh_interval}s', type='info')

    def _refresh_all_components(self) -> None:
        """Refresh all dashboard components with latest data."""
        if not self.auto_refresh_enabled and self.refresh_timer:
            # Manual refresh - notify user
            ui.notify('Refreshing dashboard...', type='info', position='top')

        # Refresh master progress
        if self.master_progress:
            self.master_progress.update()

        # Refresh session selector
        if self.session_selector:
            self.session_selector._refresh_sessions()

        # Future: Refresh other components when added in Phase 2+

    def _on_session_change(self, session_id: str | None) -> None:
        """Handle session filter change.

        Args:
            session_id: Selected session ID or None for all sessions
        """
        self.current_session_id = session_id

        # Future: Update all filtered components (charts, tables, etc.)
        # For Phase 1, just update the stored session ID
