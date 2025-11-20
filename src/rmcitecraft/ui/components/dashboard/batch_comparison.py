"""Batch Comparison Card component for dashboard."""

from typing import Callable

from nicegui import ui

from rmcitecraft.database.batch_state_repository import BatchStateRepository


class BatchComparisonCard:
    """Batch comparison card for side-by-side session comparison."""

    def __init__(
        self,
        state_repo: BatchStateRepository,
        on_comparison_change: Callable[[str, str], None] | None = None,
    ):
        """Initialize batch comparison card.

        Args:
            state_repo: Batch state repository
            on_comparison_change: Callback when comparison selections change
        """
        self._state_repo = state_repo
        self._on_comparison_change = on_comparison_change
        self.session_a_id: str | None = None
        self.session_b_id: str | None = None
        self.container = None

    def render(self) -> None:
        """Render the batch comparison card."""
        with ui.card().classes('w-full') as self.container:
            self._render_content()

    def _render_content(self) -> None:
        """Render the content inside the container."""
        # Header
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.label('Batch Comparison').classes('text-h6 text-primary')
                ui.button(
                    '',
                    icon='info',
                    on_click=self._show_info
                ).props('flat dense round size=sm').tooltip('Compare two sessions')
            ui.button(
                '',
                icon='refresh',
                on_click=self.update
            ).props('flat dense round').tooltip('Refresh comparison')

        # Get all sessions
        sessions = self._state_repo.get_all_sessions()

        if len(sessions) < 2:
            # Not enough sessions to compare
            with ui.column().classes('items-center p-8'):
                ui.icon('compare_arrows').classes('text-6xl text-grey-5')
                ui.label('Need at least 2 sessions to compare').classes('text-grey-7')
                ui.label(f'Current sessions: {len(sessions)}').classes('text-sm text-grey-6')
            return

        # Session selectors
        with ui.row().classes('w-full gap-4 mb-4'):
            # Session A selector
            with ui.card().classes('flex-1 bg-blue-1'):
                with ui.column().classes('p-4 gap-2'):
                    ui.label('Session A').classes('text-subtitle1 font-bold text-blue')
                    session_options_a = {s['session_id']: self._format_session_label(s) for s in sessions}
                    ui.select(
                        options=list(session_options_a.values()),
                        label='Select Session A',
                        on_change=lambda e: self._on_session_a_change(e, session_options_a)
                    ).props('outlined dense').classes('w-full')

            # Session B selector
            with ui.card().classes('flex-1 bg-green-1'):
                with ui.column().classes('p-4 gap-2'):
                    ui.label('Session B').classes('text-subtitle1 font-bold text-green')
                    session_options_b = {s['session_id']: self._format_session_label(s) for s in sessions}
                    ui.select(
                        options=list(session_options_b.values()),
                        label='Select Session B',
                        on_change=lambda e: self._on_session_b_change(e, session_options_b)
                    ).props('outlined dense').classes('w-full')

        # Comparison results
        if self.session_a_id and self.session_b_id:
            self._render_comparison()
        else:
            with ui.column().classes('items-center p-8'):
                ui.icon('arrow_downward').classes('text-4xl text-grey-5')
                ui.label('Select two sessions to compare').classes('text-grey-6')

    def _format_session_label(self, session: dict) -> str:
        """Format session label for selector.

        Args:
            session: Session dict

        Returns:
            Formatted label string
        """
        from datetime import datetime
        created_at = datetime.fromisoformat(session['created_at'].replace('Z', '+00:00'))
        return f"{created_at.strftime('%Y-%m-%d %H:%M')} - {session['session_id'][:8]}... ({session['status']})"

    def _on_session_a_change(self, event, options_map: dict) -> None:
        """Handle session A selection change.

        Args:
            event: Selection event
            options_map: Map of session IDs to labels
        """
        # Find session ID by label
        label = event.value
        for session_id, session_label in options_map.items():
            if session_label == label:
                self.session_a_id = session_id
                break

        self.update()

    def _on_session_b_change(self, event, options_map: dict) -> None:
        """Handle session B selection change.

        Args:
            event: Selection event
            options_map: Map of session IDs to labels
        """
        # Find session ID by label
        label = event.value
        for session_id, session_label in options_map.items():
            if session_label == label:
                self.session_b_id = session_id
                break

        self.update()

    def _render_comparison(self) -> None:
        """Render comparison results."""
        # Get session data
        session_a = self._state_repo.get_session(self.session_a_id)
        session_b = self._state_repo.get_session(self.session_b_id)

        items_a = self._state_repo.get_session_items(self.session_a_id)
        items_b = self._state_repo.get_session_items(self.session_b_id)

        # Calculate statistics
        stats_a = self._calculate_session_stats(items_a)
        stats_b = self._calculate_session_stats(items_b)

        # Comparison table
        with ui.card().classes('w-full'):
            ui.label('Comparison Results').classes('text-subtitle1 mb-4')

            columns = [
                {'name': 'metric', 'label': 'Metric', 'field': 'metric', 'align': 'left'},
                {'name': 'session_a', 'label': 'Session A', 'field': 'session_a', 'align': 'right'},
                {'name': 'session_b', 'label': 'Session B', 'field': 'session_b', 'align': 'right'},
                {'name': 'difference', 'label': 'Difference', 'field': 'difference', 'align': 'right'},
                {'name': 'trend', 'label': 'Trend', 'field': 'trend', 'align': 'center'},
            ]

            rows = [
                {
                    'metric': 'Total Items',
                    'session_a': f"{stats_a['total']:,}",
                    'session_b': f"{stats_b['total']:,}",
                    'difference': f"{stats_b['total'] - stats_a['total']:+,}",
                    'trend': self._get_trend_icon(stats_b['total'] - stats_a['total']),
                    'trend_color': self._get_trend_color(stats_b['total'] - stats_a['total'])
                },
                {
                    'metric': 'Completed',
                    'session_a': f"{stats_a['completed']:,}",
                    'session_b': f"{stats_b['completed']:,}",
                    'difference': f"{stats_b['completed'] - stats_a['completed']:+,}",
                    'trend': self._get_trend_icon(stats_b['completed'] - stats_a['completed']),
                    'trend_color': self._get_trend_color(stats_b['completed'] - stats_a['completed'])
                },
                {
                    'metric': 'Failed',
                    'session_a': f"{stats_a['failed']:,}",
                    'session_b': f"{stats_b['failed']:,}",
                    'difference': f"{stats_b['failed'] - stats_a['failed']:+,}",
                    'trend': self._get_trend_icon(stats_a['failed'] - stats_b['failed']),  # Reversed: fewer failures is better
                    'trend_color': self._get_trend_color(stats_a['failed'] - stats_b['failed'])
                },
                {
                    'metric': 'Success Rate',
                    'session_a': f"{stats_a['success_rate']:.1f}%",
                    'session_b': f"{stats_b['success_rate']:.1f}%",
                    'difference': f"{stats_b['success_rate'] - stats_a['success_rate']:+.1f}%",
                    'trend': self._get_trend_icon(stats_b['success_rate'] - stats_a['success_rate']),
                    'trend_color': self._get_trend_color(stats_b['success_rate'] - stats_a['success_rate'])
                },
                {
                    'metric': 'Items with Photos',
                    'session_a': f"{stats_a['with_photos']:,}",
                    'session_b': f"{stats_b['with_photos']:,}",
                    'difference': f"{stats_b['with_photos'] - stats_a['with_photos']:+,}",
                    'trend': self._get_trend_icon(stats_b['with_photos'] - stats_a['with_photos']),
                    'trend_color': self._get_trend_color(stats_b['with_photos'] - stats_a['with_photos'])
                },
                {
                    'metric': 'Items with Citations',
                    'session_a': f"{stats_a['with_citations']:,}",
                    'session_b': f"{stats_b['with_citations']:,}",
                    'difference': f"{stats_b['with_citations'] - stats_a['with_citations']:+,}",
                    'trend': self._get_trend_icon(stats_b['with_citations'] - stats_a['with_citations']),
                    'trend_color': self._get_trend_color(stats_b['with_citations'] - stats_a['with_citations'])
                },
            ]

            table = ui.table(
                columns=columns,
                rows=rows,
                row_key='metric'
            ).classes('w-full')

            # Add custom styling for trend column
            table.add_slot('body-cell-trend', '''
                <q-td :props="props">
                    <q-icon :name="props.value" :color="props.row.trend_color" size="sm" />
                </q-td>
            ''')

        # Winner announcement
        if stats_b['success_rate'] > stats_a['success_rate']:
            winner = 'B'
            color = 'green'
        elif stats_a['success_rate'] > stats_b['success_rate']:
            winner = 'A'
            color = 'blue'
        else:
            winner = 'Tie'
            color = 'grey'

        with ui.card().classes(f'w-full bg-{color}-1 mt-4'):
            with ui.row().classes('w-full items-center gap-4 p-4'):
                ui.icon('emoji_events').classes(f'text-4xl text-{color}')
                if winner != 'Tie':
                    ui.label(f'Session {winner} has better success rate').classes(f'text-h6 text-{color}')
                else:
                    ui.label('Sessions have equal success rates').classes(f'text-h6 text-{color}')

    def _calculate_session_stats(self, items: list[dict]) -> dict:
        """Calculate session statistics.

        Args:
            items: List of batch items

        Returns:
            Dict with statistics
        """
        import json

        total = len(items)
        completed = sum(1 for i in items if i['status'] in ['completed', 'complete', 'created_citation'])
        failed = sum(1 for i in items if i['status'] == 'failed')

        success_rate = (completed / (completed + failed) * 100) if (completed + failed) > 0 else 0

        # Count items with photos
        with_photos = 0
        for item in items:
            if item.get('downloaded_image_paths'):
                paths = item['downloaded_image_paths']
                if isinstance(paths, str):
                    try:
                        paths = json.loads(paths)
                    except json.JSONDecodeError:
                        continue
                if paths:
                    with_photos += 1

        # Count items with citations
        with_citations = sum(1 for i in items if i.get('created_citation_id'))

        return {
            'total': total,
            'completed': completed,
            'failed': failed,
            'success_rate': success_rate,
            'with_photos': with_photos,
            'with_citations': with_citations,
        }

    def _get_trend_icon(self, diff: float) -> str:
        """Get trend icon based on difference.

        Args:
            diff: Difference value

        Returns:
            Icon name
        """
        if diff > 0:
            return 'trending_up'
        elif diff < 0:
            return 'trending_down'
        else:
            return 'trending_flat'

    def _get_trend_color(self, diff: float) -> str:
        """Get trend color based on difference.

        Args:
            diff: Difference value

        Returns:
            Color name
        """
        if diff > 0:
            return 'green'
        elif diff < 0:
            return 'red'
        else:
            return 'grey'

    def _show_info(self) -> None:
        """Show information dialog explaining batch comparison."""
        with ui.dialog() as dialog, ui.card().classes('p-6'):
            ui.label('Batch Comparison Explained').classes('text-h6 text-primary mb-4')

            with ui.column().classes('gap-4'):
                ui.markdown('''
                **What is Batch Comparison?**

                Batch Comparison allows you to compare metrics between two batch processing
                sessions to identify improvements, regressions, or patterns.

                **Metrics Compared:**

                - **Total Items**: Number of items processed
                - **Completed**: Successfully processed items
                - **Failed**: Items with errors
                - **Success Rate**: Percentage of successful completions
                - **Items with Photos**: Items with downloaded images
                - **Items with Citations**: Items with created citations

                **Trend Indicators:**

                - 🟢 **Trending Up** (green): Session B improved over Session A
                - 🔴 **Trending Down** (red): Session B declined from Session A
                - ⚫ **Flat** (grey): No change between sessions

                **Use Cases:**

                - **Process Improvement**: Did error fixes reduce failures?
                - **Performance Tracking**: Is success rate improving over time?
                - **Configuration Testing**: Compare different settings/approaches
                - **Quality Assurance**: Verify batch processing consistency
                - **Troubleshooting**: Identify when problems started

                **Winner Determination:**

                The session with the higher success rate is declared the "winner",
                as this indicates better overall batch processing quality.

                **Tips:**

                - Compare recent sessions to track improvements
                - Compare before/after sessions when testing fixes
                - Look for patterns in success rate trends
                - Investigate significant differences in failure counts
                ''')

                with ui.row().classes('w-full justify-end'):
                    ui.button('Close', on_click=dialog.close).props('color=primary')

        dialog.open()

    def update(self) -> None:
        """Update the card with new data."""
        if self.container:
            self.container.clear()
            with self.container:
                self._render_content()
