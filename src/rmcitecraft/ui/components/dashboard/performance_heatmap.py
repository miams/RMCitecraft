"""Performance Heatmap Card component for dashboard."""

from typing import Callable

from nicegui import ui

from rmcitecraft.database.batch_state_repository import BatchStateRepository


class PerformanceHeatmapCard:
    """Performance heatmap card showing operation durations and bottlenecks."""

    def __init__(
        self,
        state_repo: BatchStateRepository,
        session_id: str | None = None,
        on_cell_click: Callable[[dict], None] | None = None,
    ):
        """Initialize performance heatmap card.

        Args:
            state_repo: Batch state repository
            session_id: Optional session identifier (None = all sessions)
            on_cell_click: Callback when user clicks a heatmap cell
        """
        self._state_repo = state_repo
        self.session_id = session_id
        self._on_cell_click = on_cell_click
        self.container = None
        self.chart = None

    def render(self) -> None:
        """Render the performance heatmap card."""
        with ui.card().classes('w-full') as self.container:
            self._render_content()

    def _render_content(self) -> None:
        """Render the content inside the container."""
        # Header
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.label('Performance Metrics').classes('text-h6 text-primary')
                ui.button(
                    '',
                    icon='info',
                    on_click=self._show_info
                ).props('flat dense round size=sm').tooltip('Understanding performance metrics')
            ui.button(
                '',
                icon='refresh',
                on_click=self.update
            ).props('flat dense round').tooltip('Refresh metrics')

        # Get performance metrics
        if self.session_id:
            metrics = self._state_repo.get_session_metrics(self.session_id)
        else:
            # Aggregate across all sessions
            sessions = self._state_repo.get_all_sessions()
            metrics = {}
            for session in sessions:
                session_metrics = self._state_repo.get_session_metrics(session['session_id'])
                for op_type, op_metrics in session_metrics.items():
                    if op_type not in metrics:
                        metrics[op_type] = {
                            'count': 0,
                            'avg_duration_ms': [],
                            'min_duration_ms': float('inf'),
                            'max_duration_ms': 0,
                            'success_count': 0,
                            'success_rate': 0,
                        }
                    metrics[op_type]['count'] += op_metrics['count']
                    metrics[op_type]['avg_duration_ms'].append(op_metrics['avg_duration_ms'])
                    metrics[op_type]['min_duration_ms'] = min(
                        metrics[op_type]['min_duration_ms'],
                        op_metrics['min_duration_ms']
                    )
                    metrics[op_type]['max_duration_ms'] = max(
                        metrics[op_type]['max_duration_ms'],
                        op_metrics['max_duration_ms']
                    )
                    metrics[op_type]['success_count'] += op_metrics['success_count']

            # Average the averages (weighted by count)
            for op_type in metrics:
                if metrics[op_type]['count'] > 0:
                    metrics[op_type]['success_rate'] = (
                        metrics[op_type]['success_count'] / metrics[op_type]['count']
                    )
                    avg_list = metrics[op_type]['avg_duration_ms']
                    metrics[op_type]['avg_duration_ms'] = sum(avg_list) / len(avg_list)

        if metrics:
            # Summary statistics
            self._render_summary(metrics)

            # Heatmap visualization
            self._render_heatmap(metrics)

            # Performance table
            self._render_performance_table(metrics)
        else:
            # Empty state
            with ui.column().classes('items-center p-8'):
                ui.icon('speed').classes('text-6xl text-grey-5')
                ui.label('No performance data available').classes('text-grey-7')
                if self.session_id:
                    ui.label('Process a batch to see performance metrics').classes('text-sm text-grey-6')

    def _render_summary(self, metrics: dict[str, dict]) -> None:
        """Render performance summary cards.

        Args:
            metrics: Performance metrics dict
        """
        # Calculate overall statistics
        total_ops = sum(m['count'] for m in metrics.values())
        avg_success_rate = (
            sum(m['success_rate'] for m in metrics.values()) / len(metrics)
            if metrics else 0
        )
        slowest_op = max(metrics.items(), key=lambda x: x[1]['avg_duration_ms']) if metrics else None

        with ui.row().classes('w-full gap-4 mb-4'):
            with ui.card().classes('bg-blue-1 flex-1'):
                with ui.column().classes('items-center p-4 gap-1'):
                    ui.label(f'{total_ops:,}').classes('text-h4 text-blue font-bold')
                    ui.label('Total Operations').classes('text-caption text-grey-7')

            with ui.card().classes('bg-green-1 flex-1'):
                with ui.column().classes('items-center p-4 gap-1'):
                    ui.label(f'{avg_success_rate * 100:.1f}%').classes('text-h4 text-green font-bold')
                    ui.label('Avg Success Rate').classes('text-caption text-grey-7')

            if slowest_op:
                with ui.card().classes('bg-orange-1 flex-1'):
                    with ui.column().classes('items-center p-4 gap-1'):
                        ui.label(slowest_op[0]).classes('text-h4 text-orange font-bold')
                        ui.label(
                            f'{slowest_op[1]["avg_duration_ms"]:.0f}ms avg'
                        ).classes('text-caption text-grey-7')

    def _render_heatmap(self, metrics: dict[str, dict]) -> None:
        """Render performance heatmap.

        Args:
            metrics: Performance metrics dict
        """
        # Prepare data for heatmap
        # X-axis: metric types (avg, min, max, success rate)
        # Y-axis: operation types
        operations = sorted(metrics.keys())
        metric_types = ['Avg Duration', 'Min Duration', 'Max Duration', 'Success Rate']

        heatmap_data = []
        for i, op in enumerate(operations):
            op_metrics = metrics[op]
            heatmap_data.append([0, i, op_metrics['avg_duration_ms']])
            heatmap_data.append([1, i, op_metrics['min_duration_ms']])
            heatmap_data.append([2, i, op_metrics['max_duration_ms']])
            heatmap_data.append([3, i, op_metrics['success_rate'] * 100])  # Convert to percentage

        # ECharts heatmap configuration
        echart_options = {
            'tooltip': {
                'position': 'top',
                # Build tooltip content with operation and metric labels
                'formatter': '{b}<br/>{c}' + (' ms' if metric_types else '')
            },
            'grid': {
                'height': '70%',
                'top': '10%',
                'left': '20%'
            },
            'xAxis': {
                'type': 'category',
                'data': metric_types,
                'splitArea': {
                    'show': True
                },
                'axisLabel': {
                    'interval': 0,
                    'rotate': 0
                }
            },
            'yAxis': {
                'type': 'category',
                'data': operations,
                'splitArea': {
                    'show': True
                },
                'axisLabel': {
                    'interval': 0
                }
            },
            'visualMap': {
                'min': 0,
                'max': max([d[2] for d in heatmap_data]) if heatmap_data else 100,
                'calculable': True,
                'orient': 'horizontal',
                'left': 'center',
                'bottom': '5%',
                'inRange': {
                    'color': ['#50a3ba', '#eac736', '#d94e5d']  # Blue -> Yellow -> Red
                }
            },
            'series': [
                {
                    'name': 'Performance',
                    'type': 'heatmap',
                    'data': heatmap_data,
                    'label': {
                        'show': True,
                        'fontSize': 11,
                        'color': '#000'
                    },
                    'emphasis': {
                        'itemStyle': {
                            'shadowBlur': 10,
                            'shadowColor': 'rgba(0, 0, 0, 0.5)'
                        }
                    }
                }
            ]
        }

        with ui.card().classes('w-full'):
            ui.label('Performance Heatmap').classes('text-subtitle1 mb-2')
            ui.label('Darker colors indicate slower operations or lower success rates').classes('text-caption text-grey-6 mb-2')
            self.chart = ui.echart(echart_options).classes('w-full h-96')

    def _render_performance_table(self, metrics: dict[str, dict]) -> None:
        """Render performance details table.

        Args:
            metrics: Performance metrics dict
        """
        with ui.card().classes('w-full mt-4'):
            ui.label('Performance Details').classes('text-subtitle1 mb-2')

            # Create table data
            columns = [
                {'name': 'operation', 'label': 'Operation', 'field': 'operation', 'sortable': True, 'align': 'left'},
                {'name': 'count', 'label': 'Count', 'field': 'count', 'sortable': True, 'align': 'right'},
                {'name': 'avg_ms', 'label': 'Avg (ms)', 'field': 'avg_ms', 'sortable': True, 'align': 'right'},
                {'name': 'min_ms', 'label': 'Min (ms)', 'field': 'min_ms', 'sortable': True, 'align': 'right'},
                {'name': 'max_ms', 'label': 'Max (ms)', 'field': 'max_ms', 'sortable': True, 'align': 'right'},
                {'name': 'success_rate', 'label': 'Success Rate', 'field': 'success_rate', 'sortable': True, 'align': 'right'},
                {'name': 'status', 'label': 'Status', 'field': 'status', 'sortable': True, 'align': 'center'},
            ]

            rows = []
            for op_type, op_metrics in sorted(metrics.items(), key=lambda x: x[1]['avg_duration_ms'], reverse=True):
                status = self._get_performance_status(op_metrics)

                rows.append({
                    'operation': op_type,
                    'count': op_metrics['count'],
                    'avg_ms': f"{op_metrics['avg_duration_ms']:.1f}",
                    'min_ms': f"{op_metrics['min_duration_ms']:.1f}",
                    'max_ms': f"{op_metrics['max_duration_ms']:.1f}",
                    'success_rate': f"{op_metrics['success_rate'] * 100:.1f}%",
                    'status': status,
                    'status_color': self._get_status_color(status)
                })

            table = ui.table(
                columns=columns,
                rows=rows,
                row_key='operation'
            ).classes('w-full')

            # Add custom styling for status column
            table.add_slot('body-cell-status', '''
                <q-td :props="props">
                    <q-badge :color="props.row.status_color" :label="props.value" />
                </q-td>
            ''')

    def _get_performance_status(self, metrics: dict) -> str:
        """Determine performance status.

        Args:
            metrics: Operation metrics dict

        Returns:
            Status string (Excellent, Good, Slow, Critical)
        """
        avg_ms = metrics['avg_duration_ms']
        success_rate = metrics['success_rate']

        if success_rate < 0.5:
            return 'Critical'
        elif avg_ms > 5000:  # > 5 seconds
            return 'Slow'
        elif avg_ms > 2000:  # > 2 seconds
            return 'Good'
        else:
            return 'Excellent'

    def _get_status_color(self, status: str) -> str:
        """Get color for status.

        Args:
            status: Status string

        Returns:
            Color name
        """
        return {
            'Excellent': 'green',
            'Good': 'blue',
            'Slow': 'orange',
            'Critical': 'red'
        }.get(status, 'grey')

    def _show_info(self) -> None:
        """Show information dialog explaining performance metrics."""
        with ui.dialog() as dialog, ui.card().classes('p-6'):
            ui.label('Performance Metrics Explained').classes('text-h6 text-primary mb-4')

            with ui.column().classes('gap-4'):
                ui.markdown('''
                **What are Performance Metrics?**

                Performance metrics track the duration and success rate of batch processing
                operations, helping identify bottlenecks and optimize workflow efficiency.

                **Operation Types:**

                - **page_load**: Time to fetch Find a Grave memorial page
                - **extraction**: Time to parse memorial data and images
                - **citation_creation**: Time to create RootsMagic source and citation
                - **image_download**: Time to download memorial photos
                - **database_write**: Time to write data to RootsMagic database

                **Metrics:**

                - **Avg Duration**: Mean operation time (lower is better)
                - **Min Duration**: Fastest operation time (best case)
                - **Max Duration**: Slowest operation time (worst case, outlier detection)
                - **Success Rate**: Percentage of successful operations (higher is better)

                **Performance Status:**

                - **Excellent**: < 2 seconds, > 50% success rate
                - **Good**: 2-5 seconds, > 50% success rate
                - **Slow**: > 5 seconds (bottleneck warning)
                - **Critical**: < 50% success rate (needs immediate attention)

                **Business Value:**

                - **Identify bottlenecks**: Which operation is slowest?
                - **Optimize workflow**: Focus on high-duration operations
                - **Detect issues**: Low success rates indicate systemic problems
                - **Estimate completion**: Use avg duration to project batch completion time

                **Recommended Actions:**

                - **Slow page loads**: Check network speed, use parallel processing
                - **Slow extraction**: Optimize parser, reduce complexity
                - **Slow database writes**: Check disk I/O, optimize queries
                - **Low success rates**: Review error logs, fix root causes
                ''')

                with ui.row().classes('w-full justify-end'):
                    ui.button('Close', on_click=dialog.close).props('color=primary')

        dialog.open()

    def update(self, session_id: str | None = None) -> None:
        """Update the card with new data.

        Args:
            session_id: Optional session identifier to filter by (None = all sessions)
        """
        if session_id is not None:
            self.session_id = session_id

        if self.container:
            self.container.clear()
            with self.container:
                self._render_content()

    def set_session_filter(self, session_id: str | None) -> None:
        """Set the session filter and update card.

        Args:
            session_id: Session identifier or None for all sessions
        """
        self.update(session_id)
