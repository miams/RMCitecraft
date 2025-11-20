"""Items Table component for dashboard."""

from typing import Callable

from nicegui import ui

from rmcitecraft.database.batch_state_repository import BatchStateRepository


class ItemsTable:
    """Searchable, filterable table of batch items with pagination."""

    def __init__(
        self,
        state_repo: BatchStateRepository,
        session_id: str | None = None,
        on_row_click: Callable[[dict], None] | None = None,
        page_size: int = 50
    ):
        """Initialize items table.

        Args:
            state_repo: Batch state repository
            session_id: Optional session identifier (None = all sessions)
            on_row_click: Callback when user clicks a row (receives item data)
            page_size: Number of items per page (default: 50)
        """
        self._state_repo = state_repo  # Private
        self.session_id = session_id
        self._on_row_click = on_row_click  # Private to avoid JSON serialization
        self.page_size = page_size

        # Filter state
        self.search_query = ""
        self.status_filter = "All"
        self.current_page = 0

        # UI components
        self.container = None
        self.table = None
        self.search_input = None
        self.status_select = None
        self.pagination_label = None

    def render(self) -> None:
        """Render the items table."""
        with ui.card().classes('w-full') as self.container:
            self._render_content()

    def _render_content(self) -> None:
        """Render the content inside the container."""
        # Header
        with ui.row().classes('w-full justify-between items-center mb-4'):
                ui.label('Batch Items').classes('text-h6 text-primary')

                with ui.row().classes('gap-2'):
                    ui.button(
                        '',
                        icon='refresh',
                        on_click=self.update
                    ).props('flat dense round').tooltip('Refresh table')

            # Search and filters
            with ui.row().classes('w-full gap-4 mb-4'):
                # Search input
                self.search_input = ui.input(
                    placeholder='Search by name or PersonID...'
                ).props('outlined dense').classes('flex-grow')
                self.search_input.on('input', lambda e: self._on_search_change(e.value))

                # Status filter
                self.status_select = ui.select(
                    ['All', 'Completed', 'Failed', 'Pending', 'Skipped'],
                    value=self.status_filter,
                    label='Status',
                    on_change=lambda e: self._on_status_filter_change(e.value)
                ).props('outlined dense').classes('w-40')

                # Page size selector
                ui.select(
                    [25, 50, 100, 200],
                    value=self.page_size,
                    label='Per Page',
                    on_change=lambda e: self._on_page_size_change(e.value)
                ).props('outlined dense').classes('w-32')

            # Get filtered items
            items = self._get_filtered_items()

            # Table
            if items:
                # Define columns
                columns = [
                    {'name': 'person_id', 'label': 'PersonID', 'field': 'person_id', 'sortable': True, 'align': 'left'},
                    {'name': 'person_name', 'label': 'Name', 'field': 'person_name', 'sortable': True, 'align': 'left'},
                    {'name': 'status', 'label': 'Status', 'field': 'status', 'sortable': True, 'align': 'center'},
                    {'name': 'memorial_id', 'label': 'Memorial ID', 'field': 'memorial_id', 'sortable': False, 'align': 'left'},
                    {'name': 'created_at', 'label': 'Created', 'field': 'created_at', 'sortable': True, 'align': 'left'},
                    {'name': 'actions', 'label': 'Actions', 'field': 'actions', 'sortable': False, 'align': 'center'},
                ]

                # Prepare rows
                rows = self._prepare_rows(items)

                # Create table
                self.table = ui.table(
                    columns=columns,
                    rows=rows,
                    row_key='id',
                    pagination={'rowsPerPage': self.page_size}
                ).classes('w-full')

                # Add custom styling for status column
                self.table.add_slot('body-cell-status', '''
                    <q-td :props="props">
                        <q-badge :color="props.row.status_color" :label="props.value" />
                    </q-td>
                ''')

                # Add actions column with buttons
                self.table.add_slot('body-cell-actions', '''
                    <q-td :props="props">
                        <q-btn size="sm" flat dense round icon="visibility"
                               @click="$parent.$emit('view', props.row)"
                               color="primary">
                            <q-tooltip>View Details</q-tooltip>
                        </q-btn>
                        <q-btn size="sm" flat dense round icon="open_in_new"
                               @click="$parent.$emit('open_url', props.row)"
                               color="blue">
                            <q-tooltip>Open Find a Grave</q-tooltip>
                        </q-btn>
                    </q-td>
                ''')

                # Event handlers
                self.table.on('view', self._on_view_item)
                self.table.on('open_url', self._on_open_url)

                # Pagination info
                total_items = len(items)
                total_pages = (total_items + self.page_size - 1) // self.page_size

                with ui.row().classes('w-full justify-between items-center mt-4'):
                    self.pagination_label = ui.label(
                        f'Showing {len(rows)} of {total_items} items'
                    ).classes('text-sm text-grey-7')

            else:
                # Empty state
                with ui.column().classes('items-center p-8'):
                    ui.icon('inbox').classes('text-6xl text-grey-5')
                    ui.label('No items found').classes('text-grey-7')
                    if self.search_query or self.status_filter != 'All':
                        ui.label('Try adjusting your filters').classes('text-sm text-grey-6')

    def _get_filtered_items(self) -> list[dict]:
        """Get items filtered by session, search, and status.

        Returns:
            List of filtered item dicts
        """
        # Get items from repository
        if self.session_id:
            items = self._state_repo.get_session_items(self.session_id)
        else:
            # Get all items across all sessions
            items = []
            sessions = self._state_repo.get_all_sessions()
            for session in sessions:
                items.extend(self._state_repo.get_session_items(session['session_id']))

        # Apply search filter
        if self.search_query:
            query_lower = self.search_query.lower()
            items = [
                item for item in items
                if (query_lower in item['person_name'].lower() if item['person_name'] else False)
                   or (query_lower in str(item['person_id']))
                   or (query_lower in item['memorial_id'] if item['memorial_id'] else False)
            ]

        # Apply status filter
        if self.status_filter != 'All':
            status_map = {
                'Completed': ['completed', 'complete', 'created_citation'],
                'Failed': ['failed'],
                'Pending': ['pending', 'queued'],
                'Skipped': ['skipped'],
            }
            allowed_statuses = status_map.get(self.status_filter, [])
            items = [item for item in items if item['status'] in allowed_statuses]

        return items

    def _prepare_rows(self, items: list[dict]) -> list[dict]:
        """Prepare table rows from items.

        Args:
            items: List of item dicts

        Returns:
            List of row dicts formatted for ui.table
        """
        rows = []
        for item in items:
            # Format created_at timestamp
            created_at = item.get('created_at', '')
            if created_at:
                from datetime import datetime
                try:
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    created_at_str = dt.strftime('%Y-%m-%d %H:%M')
                except Exception:
                    created_at_str = created_at
            else:
                created_at_str = 'N/A'

            # Determine status color
            status = item.get('status', 'unknown')
            if status in ['completed', 'complete', 'created_citation']:
                status_display = 'Completed'
                status_color = 'green'
            elif status == 'failed':
                status_display = 'Failed'
                status_color = 'red'
            elif status in ['pending', 'queued']:
                status_display = 'Pending'
                status_color = 'orange'
            elif status == 'skipped':
                status_display = 'Skipped'
                status_color = 'grey'
            else:
                status_display = status.capitalize()
                status_color = 'blue'

            rows.append({
                'id': item['id'],
                'person_id': item['person_id'],
                'person_name': item['person_name'] or 'Unknown',
                'status': status_display,
                'status_color': status_color,
                'memorial_id': item['memorial_id'] or 'N/A',
                'memorial_url': item['memorial_url'],
                'created_at': created_at_str,
                'error_message': item.get('error_message'),
                '_item_data': item  # Store full item for callbacks
            })

        return rows

    def _on_search_change(self, value: str) -> None:
        """Handle search input change.

        Args:
            value: Search query
        """
        self.search_query = value
        self.current_page = 0
        self._rebuild_table()

    def _on_status_filter_change(self, value: str) -> None:
        """Handle status filter change.

        Args:
            value: Selected status
        """
        self.status_filter = value
        self.current_page = 0
        self._rebuild_table()

    def _on_page_size_change(self, value: int) -> None:
        """Handle page size change.

        Args:
            value: New page size
        """
        self.page_size = value
        self.current_page = 0
        self._rebuild_table()

    def _on_view_item(self, event) -> None:
        """Handle view item click.

        Args:
            event: Click event with row data
        """
        if self._on_row_click:
            item_data = event.args.get('_item_data')
            if item_data:
                self._on_row_click(item_data)

    def _on_open_url(self, event) -> None:
        """Handle open URL click.

        Args:
            event: Click event with row data
        """
        memorial_url = event.args.get('memorial_url')
        if memorial_url:
            ui.open(memorial_url, new_tab=True)

    def _rebuild_table(self) -> None:
        """Rebuild the table with current filters."""
        if self.container:
            self.container.clear()
            with self.container:
                self._render_content()

    def update(self, session_id: str | None = None) -> None:
        """Update the table with new data.

        Args:
            session_id: Optional session identifier to filter by (None = all sessions)
        """
        if session_id is not None:
            self.session_id = session_id

        self._rebuild_table()

    def set_session_filter(self, session_id: str | None) -> None:
        """Set the session filter and update table.

        Args:
            session_id: Session identifier or None for all sessions
        """
        self.update(session_id)

    def set_status_filter(self, status: str) -> None:
        """Set the status filter and update table.

        Args:
            status: Status to filter by ('All', 'Completed', 'Failed', 'Pending', 'Skipped')
        """
        self.status_filter = status
        if self.status_select:
            self.status_select.value = status
        self._rebuild_table()
