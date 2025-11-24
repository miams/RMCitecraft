"""Error Analysis Card component for dashboard."""

from typing import Callable

from nicegui import ui

from rmcitecraft.database.batch_state_repository import FindAGraveBatchStateRepository


class ErrorAnalysisCard:
    """Error analysis card showing hierarchical breakdown of errors using tree map."""

    def __init__(
        self,
        state_repo: FindAGraveBatchStateRepository,
        session_id: str | None = None,
        on_error_click: Callable[[str], None] | None = None,
    ):
        """Initialize error analysis card.

        Args:
            state_repo: Batch state repository
            session_id: Optional session identifier (None = all sessions)
            on_error_click: Callback when user clicks an error category
        """
        self._state_repo = state_repo
        self.session_id = session_id
        self._on_error_click = on_error_click
        self.container = None
        self.chart = None

    def render(self) -> None:
        """Render the error analysis card."""
        with ui.card().classes('w-full') as self.container:
            self._render_content()

    def _render_content(self) -> None:
        """Render the content inside the container."""
        # Header
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.label('Error Analysis').classes('text-h6 text-primary')
                ui.button(
                    '',
                    icon='info',
                    on_click=self._show_info
                ).props('flat dense round size=sm').tooltip('Understanding error patterns')
            ui.button(
                '',
                icon='refresh',
                on_click=self.update
            ).props('flat dense round').tooltip('Refresh analysis')

        # Get error distribution
        error_dist = self._state_repo.get_error_distribution(self.session_id)

        if error_dist:
            # Get total failed items
            total_failed = sum(error_dist.values())

            # Summary
            with ui.row().classes('w-full gap-4 mb-4'):
                with ui.card().classes('bg-red-1 flex-1'):
                    with ui.column().classes('items-center p-4 gap-1'):
                        ui.label(f'{total_failed:,}').classes('text-h4 text-red font-bold')
                        ui.label('Total Errors').classes('text-caption text-grey-7')

                with ui.card().classes('bg-orange-1 flex-1'):
                    with ui.column().classes('items-center p-4 gap-1'):
                        ui.label(f'{len(error_dist):,}').classes('text-h4 text-orange font-bold')
                        ui.label('Error Types').classes('text-caption text-grey-7')

            # Tree map visualization
            self._render_tree_map(error_dist, total_failed)

            # Error details table
            self._render_error_table(error_dist)
        else:
            # Empty state
            with ui.column().classes('items-center p-8'):
                ui.icon('check_circle').classes('text-6xl text-green')
                ui.label('No errors detected').classes('text-grey-7')
                ui.label('All items processed successfully!').classes('text-sm text-grey-6')

    def _render_tree_map(self, error_dist: dict[str, int], total: int) -> None:
        """Render error distribution tree map.

        Args:
            error_dist: Dict mapping error type to count
            total: Total number of errors
        """
        # Prepare data for tree map
        chart_data = []
        for error_type, count in sorted(error_dist.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total * 100) if total > 0 else 0
            chart_data.append({
                'name': error_type,
                'value': count,
                'percentage': percentage
            })

        # Color mapping for error types
        color_map = {
            'Network Error': '#EF5350',        # Red
            'Extraction Error': '#FF7043',    # Deep Orange
            'Validation Error': '#FFA726',    # Orange
            'Database Error': '#AB47BC',      # Purple
            'Timeout Error': '#EC407A',       # Pink
            'Unknown Error': '#78909C',       # Blue Grey
        }

        # ECharts tree map configuration
        echart_options = {
            'tooltip': {
                'trigger': 'item',
                'formatter': '{b}<br/>Count: {c}<br/>Percentage: {d}%'
            },
            'series': [
                {
                    'type': 'treemap',
                    'data': chart_data,
                    'visibleMin': 10,
                    'label': {
                        'show': True,
                        'formatter': '{b}\\n{c}'
                    },
                    'itemStyle': {
                        'borderColor': '#fff',
                        'borderWidth': 2,
                        'gapWidth': 2
                    },
                    'levels': [
                        {
                            'itemStyle': {
                                'borderWidth': 0,
                                'gapWidth': 5
                            }
                        },
                        {
                            'itemStyle': {
                                'gapWidth': 1
                            }
                        }
                    ],
                    'roam': False,
                    'breadcrumb': {
                        'show': False
                    }
                }
            ]
        }

        # Add colors to data
        for item in chart_data:
            item['itemStyle'] = {
                'color': color_map.get(item['name'], '#90A4AE')
            }

        with ui.card().classes('w-full'):
            ui.label('Error Distribution Tree Map').classes('text-subtitle1 mb-2')
            ui.label('Size represents frequency of each error type').classes('text-caption text-grey-6 mb-2')
            self.chart = ui.echart(echart_options).classes('w-full h-96')

    def _render_error_table(self, error_dist: dict[str, int]) -> None:
        """Render error details table.

        Args:
            error_dist: Dict mapping error type to count
        """
        with ui.card().classes('w-full mt-4'):
            ui.label('Error Details').classes('text-subtitle1 mb-2')

            # Sort by count descending
            sorted_errors = sorted(error_dist.items(), key=lambda x: x[1], reverse=True)
            total = sum(error_dist.values())

            # Create table data
            columns = [
                {'name': 'error_type', 'label': 'Error Type', 'field': 'error_type', 'sortable': True, 'align': 'left'},
                {'name': 'count', 'label': 'Count', 'field': 'count', 'sortable': True, 'align': 'right'},
                {'name': 'percentage', 'label': 'Percentage', 'field': 'percentage', 'sortable': True, 'align': 'right'},
                {'name': 'severity', 'label': 'Severity', 'field': 'severity', 'sortable': True, 'align': 'center'},
            ]

            rows = []
            for error_type, count in sorted_errors:
                percentage = (count / total * 100) if total > 0 else 0
                severity = self._get_error_severity(error_type)

                rows.append({
                    'error_type': error_type,
                    'count': count,
                    'percentage': f'{percentage:.1f}%',
                    'severity': severity,
                    'severity_color': self._get_severity_color(severity)
                })

            table = ui.table(
                columns=columns,
                rows=rows,
                row_key='error_type'
            ).classes('w-full')

            # Add custom styling for severity column
            table.add_slot('body-cell-severity', '''
                <q-td :props="props">
                    <q-badge :color="props.row.severity_color" :label="props.value" />
                </q-td>
            ''')

    def _get_error_severity(self, error_type: str) -> str:
        """Determine error severity level.

        Args:
            error_type: Error type string

        Returns:
            Severity level (Critical, High, Medium, Low)
        """
        if 'Database' in error_type:
            return 'Critical'
        elif 'Validation' in error_type:
            return 'High'
        elif 'Extraction' in error_type or 'Network' in error_type:
            return 'Medium'
        else:
            return 'Low'

    def _get_severity_color(self, severity: str) -> str:
        """Get color for severity level.

        Args:
            severity: Severity level

        Returns:
            Color name
        """
        return {
            'Critical': 'red',
            'High': 'orange',
            'Medium': 'amber',
            'Low': 'blue-grey'
        }.get(severity, 'grey')

    def _show_info(self) -> None:
        """Show information dialog explaining error analysis."""
        with ui.dialog() as dialog, ui.card().classes('p-6'):
            ui.label('Error Analysis Explained').classes('text-h6 text-primary mb-4')

            with ui.column().classes('gap-4'):
                ui.markdown('''
                **What is Error Analysis?**

                Error analysis helps identify patterns in batch processing failures,
                enabling you to prioritize fixes and understand root causes.

                **Error Categories:**

                - **Network Error**: Connection timeouts, DNS failures, HTTP errors
                - **Extraction Error**: Failed to parse memorial data or images
                - **Validation Error**: Invalid or incomplete data (missing required fields)
                - **Database Error**: RootsMagic database write failures (critical!)
                - **Timeout Error**: Operations exceeded time limits
                - **Unknown Error**: Unclassified errors requiring investigation

                **Severity Levels:**

                - **Critical**: Database errors that could corrupt data
                - **High**: Validation errors preventing citation creation
                - **Medium**: Extraction/network errors requiring retry
                - **Low**: Minor issues with fallback handling

                **Business Value:**

                - **Identify systemic issues**: Network problems vs. data quality issues
                - **Prioritize fixes**: Focus on high-frequency or critical errors
                - **Monitor trends**: Track error rates over multiple sessions
                - **Improve success rate**: Address root causes to increase completion rate

                **Recommended Actions:**

                - **Network Errors**: Check internet connection, retry batch
                - **Extraction Errors**: Review memorial format changes, update parser
                - **Validation Errors**: Review memorial data completeness
                - **Database Errors**: Stop immediately, restore from backup if needed
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
