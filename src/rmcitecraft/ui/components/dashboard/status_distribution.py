"""Status Distribution Chart component for dashboard."""

from typing import Callable

from nicegui import ui

from rmcitecraft.database.batch_state_repository import BatchStateRepository


class StatusDistributionChart:
    """Status distribution pie chart showing completed/failed/pending/skipped breakdown."""

    def __init__(
        self,
        state_repo: BatchStateRepository,
        session_id: str | None = None,
        on_status_click: Callable[[str], None] | None = None
    ):
        """Initialize status distribution chart.

        Args:
            state_repo: Batch state repository
            session_id: Optional session identifier (None = all sessions)
            on_status_click: Callback when user clicks a status slice (receives status name)
        """
        self._state_repo = state_repo  # Private
        self.session_id = session_id
        self._on_status_click = on_status_click  # Private to avoid JSON serialization
        self.chart = None
        self.container = None

    def render(self) -> None:
        """Render the status distribution pie chart."""
        with ui.card().classes('w-full') as self.container:
            # Header
            with ui.row().classes('w-full justify-between items-center mb-4'):
                ui.label('Status Distribution').classes('text-h6 text-primary')
                ui.button(
                    '',
                    icon='refresh',
                    on_click=self.update
                ).props('flat dense round').tooltip('Refresh chart')

            # Get status distribution
            status_data = self._state_repo.get_status_distribution(self.session_id)

            # Map status values to display names
            status_mapping = {
                'completed': 'Completed',
                'complete': 'Completed',
                'created_citation': 'Completed',
                'failed': 'Failed',
                'pending': 'Pending',
                'queued': 'Pending',
                'skipped': 'Skipped',
            }

            # Aggregate statuses with same display name
            aggregated_data = {}
            for status, count in status_data.items():
                display_name = status_mapping.get(status, status.capitalize())
                aggregated_data[display_name] = aggregated_data.get(display_name, 0) + count

            # If no data, show message
            if not aggregated_data or sum(aggregated_data.values()) == 0:
                with ui.column().classes('items-center p-8'):
                    ui.icon('pie_chart').classes('text-6xl text-grey-5')
                    ui.label('No batch items yet').classes('text-grey-7')
                return

            # Color scheme
            status_colors = {
                'Completed': '#4CAF50',  # Green
                'Failed': '#F44336',     # Red
                'Pending': '#FFC107',    # Yellow
                'Skipped': '#9E9E9E',    # Grey
            }

            # Build chart data
            chart_data = [
                {
                    'value': count,
                    'name': status,
                    'itemStyle': {'color': status_colors.get(status, '#2196F3')}
                }
                for status, count in aggregated_data.items()
            ]

            # ECharts pie chart configuration
            chart_options = {
                'tooltip': {
                    'trigger': 'item',
                    'formatter': '{b}: {c} ({d}%)'
                },
                'legend': {
                    'orient': 'vertical',
                    'left': 'left',
                    'top': 'middle',
                    'textStyle': {
                        'fontSize': 14
                    }
                },
                'series': [{
                    'name': 'Status',
                    'type': 'pie',
                    'radius': ['40%', '70%'],  # Donut chart
                    'center': ['60%', '50%'],
                    'avoidLabelOverlap': False,
                    'itemStyle': {
                        'borderRadius': 10,
                        'borderColor': '#fff',
                        'borderWidth': 2
                    },
                    'label': {
                        'show': True,
                        'formatter': '{b}\n{c}',
                        'fontSize': 12
                    },
                    'emphasis': {
                        'label': {
                            'show': True,
                            'fontSize': 16,
                            'fontWeight': 'bold'
                        },
                        'itemStyle': {
                            'shadowBlur': 10,
                            'shadowOffsetX': 0,
                            'shadowColor': 'rgba(0, 0, 0, 0.5)'
                        }
                    },
                    'data': chart_data
                }]
            }

            # Render chart
            self.chart = ui.echart(chart_options).classes('w-full h-64')

            # Summary stats below chart
            total = sum(aggregated_data.values())
            with ui.grid(columns=len(aggregated_data)).classes('w-full gap-2 mt-4'):
                for status, count in aggregated_data.items():
                    percentage = (count / total * 100) if total > 0 else 0
                    self._render_stat_chip(status, count, percentage, status_colors.get(status, '#2196F3'))

    def _render_stat_chip(self, status: str, count: int, percentage: float, color: str) -> None:
        """Render a status statistic chip.

        Args:
            status: Status name
            count: Item count
            percentage: Percentage of total
            color: Status color
        """
        with ui.card().classes('p-2').style(f'border-left: 4px solid {color}'):
            ui.label(status).classes('text-sm font-bold')
            with ui.row().classes('items-baseline gap-1'):
                ui.label(str(count)).classes('text-h6')
                ui.label(f'({percentage:.1f}%)').classes('text-xs text-grey-6')

    def update(self, session_id: str | None = None) -> None:
        """Update the chart with new data.

        Args:
            session_id: Optional session identifier to filter by (None = all sessions)
        """
        if session_id is not None:
            self.session_id = session_id

        # Rebuild chart
        if self.container:
            self.container.clear()
            with self.container:
                self.render()

        ui.notify('Status distribution updated', type='positive', position='top')

    def set_session_filter(self, session_id: str | None) -> None:
        """Set the session filter and update chart.

        Args:
            session_id: Session identifier or None for all sessions
        """
        self.update(session_id)
