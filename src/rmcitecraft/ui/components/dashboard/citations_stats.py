"""Citations Statistics Card component for dashboard."""

from typing import Callable

from nicegui import ui

from rmcitecraft.database.batch_state_repository import FindAGraveBatchStateRepository


class CitationsStatsCard:
    """Citations statistics card showing breakdown of how citations are applied."""

    def __init__(
        self,
        state_repo: FindAGraveBatchStateRepository,
        rm_database_path: str,
        session_id: str | None = None,
        on_click: Callable[[], None] | None = None,
    ):
        """Initialize citations statistics card.

        Args:
            state_repo: Batch state repository
            rm_database_path: Path to RootsMagic database for citation link queries
            session_id: Optional session identifier (None = all sessions)
            on_click: Callback when user clicks the card
        """
        self._state_repo = state_repo
        self.rm_database_path = rm_database_path
        self.session_id = session_id
        self._on_click = on_click
        self.container = None
        self.chart = None

    def render(self) -> None:
        """Render the citations statistics card."""
        with ui.card().classes('w-full') as self.container:
            self._render_content()

    def _render_content(self) -> None:
        """Render the content inside the container."""
        # Header
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.label('Citations Created').classes('text-h6 text-primary')
                ui.button(
                    '',
                    icon='info',
                    on_click=self._show_info
                ).props('flat dense round size=sm').tooltip('How are citations applied?')
            ui.button(
                '',
                icon='refresh',
                on_click=self.update
            ).props('flat dense round').tooltip('Refresh statistics')

        # Get citation statistics
        try:
            stats = self._state_repo.get_citation_statistics(
                self.rm_database_path,
                self.session_id
            )
            total_citations = stats['total_citations']
            items_with_citations = stats['items_with_citations']
            citations_by_owner = stats['citations_by_owner_type']

            # Summary statistics
            with ui.row().classes('w-full gap-4 mb-4'):
                with ui.card().classes('bg-purple-1 flex-1'):
                    with ui.column().classes('items-center p-4 gap-1'):
                        ui.label(f'{total_citations:,}').classes('text-h4 text-purple font-bold')
                        ui.label('Total Citations').classes('text-caption text-grey-7')
                with ui.card().classes('bg-indigo-1 flex-1'):
                    with ui.column().classes('items-center p-4 gap-1'):
                        ui.label(f'{items_with_citations:,}').classes('text-h4 text-indigo font-bold')
                        ui.label('Items with Citations').classes('text-caption text-grey-7')

            # Citation application breakdown chart
            if citations_by_owner:
                self._render_chart(citations_by_owner)
            else:
                # Empty state
                with ui.column().classes('items-center p-8'):
                    ui.icon('format_quote').classes('text-6xl text-grey-5')
                    ui.label('No citations created yet').classes('text-grey-7')
                    if self.session_id:
                        ui.label('Process a batch to see citation statistics').classes('text-sm text-grey-6')

        except Exception as e:
            # Error state
            with ui.column().classes('items-center p-8'):
                ui.icon('error').classes('text-6xl text-red')
                ui.label('Error loading citation statistics').classes('text-red')
                ui.label(str(e)).classes('text-sm text-grey-6')

    def _render_chart(self, citations_by_owner: dict[str, int]) -> None:
        """Render citation application breakdown chart.

        Args:
            citations_by_owner: Dict mapping owner type to count
        """
        # Prepare data for ECharts
        chart_data = [
            {'value': count, 'name': owner_type}
            for owner_type, count in sorted(
                citations_by_owner.items(),
                key=lambda x: x[1],
                reverse=True
            )
        ]

        # Color mapping for owner types
        color_map = {
            'Person': '#9C27B0',       # Purple
            'Event': '#2196F3',        # Blue
            'Family': '#4CAF50',       # Green
            'Source': '#FF9800',       # Orange
            'Place': '#795548',        # Brown
            'Name': '#E91E63',         # Pink
            'Citation': '#607D8B',     # Blue Grey
            'MediaLink': '#00BCD4',    # Cyan
        }

        colors = [color_map.get(item['name'], '#9E9E9E') for item in chart_data]

        # ECharts configuration
        echart_options = {
            'tooltip': {
                'trigger': 'item',
                'formatter': '{b}: {c} ({d}%)'
            },
            'legend': {
                'orient': 'vertical',
                'left': 'left',
                'top': 'center',
            },
            'series': [
                {
                    'name': 'Citations by Application',
                    'type': 'pie',
                    'radius': ['40%', '70%'],
                    'center': ['60%', '50%'],
                    'avoidLabelOverlap': False,
                    'itemStyle': {
                        'borderRadius': 10,
                        'borderColor': '#fff',
                        'borderWidth': 2
                    },
                    'label': {
                        'show': True,
                        'position': 'outside',
                        'formatter': '{b}: {c}'
                    },
                    'emphasis': {
                        'label': {
                            'show': True,
                            'fontSize': 16,
                            'fontWeight': 'bold'
                        }
                    },
                    'labelLine': {
                        'show': True
                    },
                    'data': chart_data
                }
            ],
            'color': colors
        }

        with ui.card().classes('w-full'):
            ui.label('Breakdown by Application Type').classes('text-subtitle1 mb-2')
            self.chart = ui.echart(echart_options).classes('w-full h-80')

    def _show_info(self) -> None:
        """Show information dialog explaining citation applications."""
        with ui.dialog() as dialog, ui.card().classes('p-6'):
            ui.label('Citation Applications Explained').classes('text-h6 text-primary mb-4')

            with ui.column().classes('gap-4'):
                ui.markdown('''
                **How are citations applied?**

                Citations in RootsMagic can be linked to various types of genealogical data:

                **Application Types:**

                - **Person**: Citation attached directly to a person record (supports general facts about the person)
                - **Event**: Citation attached to a specific event (birth, death, burial, census, etc.)
                - **Family**: Citation attached to a family record (supports marriage, divorce, or family facts)
                - **Source**: Citation used to cite another source (rare, for source-of-source documentation)
                - **Place**: Citation attached to a place record (supports place name spellings or historical context)
                - **Name**: Citation attached to an alternate name (supports name variations or nicknames)
                - **MediaLink**: Citation attached to media items (photos, documents, etc.)

                **Business Value:**

                - Understand how Find a Grave citations are being structured in your database
                - Verify citations are attached to appropriate genealogical entities
                - Identify opportunities to add more specific event citations vs. general person citations
                - Track citation completeness across different record types

                **Best Practice**: Citations should typically be attached to **Events** (e.g., burial event) rather than directly to persons, as this provides more specific provenance for the cited information.

                **Note**: This data reflects citation links created by RMCitecraft during batch processing of Find a Grave memorials.
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
