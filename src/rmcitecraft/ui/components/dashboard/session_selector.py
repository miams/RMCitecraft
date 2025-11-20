"""Session Selector Card component for dashboard."""

from datetime import datetime
from typing import Callable

from nicegui import ui

from rmcitecraft.database.batch_state_repository import BatchStateRepository


class SessionSelectorCard:
    """Session selector card for switching between batch sessions."""

    def __init__(
        self,
        state_repo: BatchStateRepository,
        on_session_change: Callable[[str | None], None] | None = None
    ):
        """Initialize session selector card.

        Args:
            state_repo: Batch state repository
            on_session_change: Callback function when session changes (receives session_id or None for all)
        """
        self.state_repo = state_repo
        self.on_session_change = on_session_change
        self.selected_session_id: str | None = None
        self.selector = None
        self.container = None

    def render(self) -> None:
        """Render the session selector card."""
        with ui.card().classes('w-full') as self.container:
            # Header
            with ui.row().classes('w-full justify-between items-center mb-4'):
                ui.label('Session Filter').classes('text-h6 text-primary')
                ui.button(
                    '',
                    icon='refresh',
                    on_click=self._refresh_sessions
                ).props('flat dense round').tooltip('Refresh sessions list')

            # Get all sessions
            sessions = self.state_repo.get_all_sessions()

            # Build options list
            options = [{'label': 'All Sessions (Cumulative)', 'value': None}]

            for session in sessions:
                # Format session label
                created_at = datetime.fromisoformat(session['created_at'].replace('Z', '+00:00'))
                label = f"{created_at.strftime('%Y-%m-%d %H:%M')} - {session['session_id'][:8]}... ({session['status']})"

                options.append({
                    'label': label,
                    'value': session['session_id']
                })

            # Session selector
            with ui.row().classes('w-full gap-4 items-center'):
                ui.label('View:').classes('text-sm font-bold')

                self.selector = ui.select(
                    options=[opt['label'] for opt in options],
                    value='All Sessions (Cumulative)',
                    on_change=self._on_session_selected
                ).props('outlined dense').classes('flex-grow')

                # Store mapping of labels to session IDs
                self._option_map = {opt['label']: opt['value'] for opt in options}

            # Session details (if specific session selected)
            if self.selected_session_id:
                self._render_session_details()

    def _on_session_selected(self, event) -> None:
        """Handle session selection change.

        Args:
            event: Selection event
        """
        selected_label = event.value
        self.selected_session_id = self._option_map.get(selected_label)

        # Call callback if provided
        if self.on_session_change:
            self.on_session_change(self.selected_session_id)

        # Refresh session details
        if self.container:
            self.container.clear()
            with self.container:
                self.render()

        # Notify user
        if self.selected_session_id:
            ui.notify(f'Viewing session: {self.selected_session_id[:16]}...', type='info')
        else:
            ui.notify('Viewing all sessions (cumulative)', type='info')

    def _render_session_details(self) -> None:
        """Render details for selected session."""
        if not self.selected_session_id:
            return

        session = self.state_repo.get_session(self.selected_session_id)
        if not session:
            return

        # Session details card
        with ui.card().classes('bg-blue-1 mt-4'):
            with ui.column().classes('gap-2 p-2'):
                # Session ID
                with ui.row().classes('items-center gap-2'):
                    ui.icon('fingerprint').classes('text-blue')
                    ui.label(f'Session ID: {session["session_id"]}').classes('text-sm font-mono')

                # Created at
                created_at = datetime.fromisoformat(session['created_at'].replace('Z', '+00:00'))
                with ui.row().classes('items-center gap-2'):
                    ui.icon('schedule').classes('text-blue')
                    ui.label(f'Created: {created_at.strftime("%Y-%m-%d %H:%M:%S")}').classes('text-sm')

                # Status
                status_color = {
                    'queued': 'grey',
                    'running': 'blue',
                    'paused': 'orange',
                    'completed': 'green',
                    'failed': 'red'
                }.get(session['status'], 'grey')

                with ui.row().classes('items-center gap-2'):
                    ui.icon('info').classes(f'text-{status_color}')
                    ui.label(f'Status: {session["status"]}').classes(f'text-sm text-{status_color} font-bold')

                # Progress
                completed_count = session['completed_count'] or 0
                total_items = session['total_items'] or 0
                error_count = session['error_count'] or 0

                with ui.row().classes('items-center gap-2'):
                    ui.icon('analytics').classes('text-blue')
                    ui.label(
                        f'Progress: {completed_count}/{total_items} items '
                        f'({error_count} errors)'
                    ).classes('text-sm')

                # Progress bar
                progress_pct = (completed_count / total_items) * 100 if total_items > 0 else 0
                ui.linear_progress(
                    value=completed_count / total_items if total_items > 0 else 0
                ).props('size=15px color=blue')

    def _refresh_sessions(self) -> None:
        """Refresh sessions list."""
        if self.container:
            self.container.clear()
            with self.container:
                self.render()

        ui.notify('Sessions list refreshed', type='positive')

    def get_selected_session_id(self) -> str | None:
        """Get currently selected session ID.

        Returns:
            Selected session ID or None for all sessions
        """
        return self.selected_session_id
