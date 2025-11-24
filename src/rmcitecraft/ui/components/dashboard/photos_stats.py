"""Photos Statistics Card component for dashboard."""

from typing import Callable

from nicegui import ui

from rmcitecraft.database.batch_state_repository import FindAGraveBatchStateRepository


class PhotosStatsCard:
    """Photos statistics card showing breakdown of ingested images by photo type."""

    def __init__(
        self,
        state_repo: FindAGraveBatchStateRepository,
        session_id: str | None = None,
        on_click: Callable[[], None] | None = None,
    ):
        """Initialize photos statistics card.

        Args:
            state_repo: Batch state repository
            session_id: Optional session identifier (None = all sessions)
            on_click: Callback when user clicks the card
        """
        self._state_repo = state_repo
        self.session_id = session_id
        self._on_click = on_click
        self.container = None
        self.chart = None

    def render(self) -> None:
        """Render the photos statistics card."""
        with ui.card().classes('w-full') as self.container:
            self._render_content()

    def _render_content(self) -> None:
        """Render the content inside the container."""
        # Header
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.label('Photos Ingested').classes('text-h6 text-primary')
                ui.button(
                    '',
                    icon='info',
                    on_click=self._show_info
                ).props('flat dense round size=sm').tooltip('What are photo types?')
            ui.button(
                '',
                icon='refresh',
                on_click=self.update
            ).props('flat dense round').tooltip('Refresh statistics')

        # Get photo statistics
        stats = self._state_repo.get_photo_statistics(self.session_id)
        total_photos = stats['total_photos']
        items_with_photos = stats['items_with_photos']
        photos_by_type = stats['photos_by_type']

        # Summary statistics
        with ui.row().classes('w-full gap-4 mb-4'):
            with ui.card().classes('bg-blue-1 flex-1'):
                with ui.column().classes('items-center p-4 gap-1'):
                    ui.label(f'{total_photos:,}').classes('text-h4 text-blue font-bold')
                    ui.label('Total Photos').classes('text-caption text-grey-7')
            with ui.card().classes('bg-green-1 flex-1'):
                with ui.column().classes('items-center p-4 gap-1'):
                    ui.label(f'{items_with_photos:,}').classes('text-h4 text-green font-bold')
                    ui.label('Items with Photos').classes('text-caption text-grey-7')

        # Photo type breakdown chart
        if photos_by_type:
            self._render_chart(photos_by_type)
        else:
            # Empty state
            with ui.column().classes('items-center p-8'):
                ui.icon('photo_library').classes('text-6xl text-grey-5')
                ui.label('No photos ingested yet').classes('text-grey-7')
                if self.session_id:
                    ui.label('Process a batch to see photo statistics').classes('text-sm text-grey-6')

    def _render_chart(self, photos_by_type: dict[str, int]) -> None:
        """Render photo type breakdown chart.

        Args:
            photos_by_type: Dict mapping photo type to count
        """
        # Prepare data for ECharts
        chart_data = [
            {'value': count, 'name': photo_type}
            for photo_type, count in sorted(
                photos_by_type.items(),
                key=lambda x: x[1],
                reverse=True
            )
        ]

        # Color mapping for photo types
        color_map = {
            'Profile': '#4CAF50',      # Green
            'Headstone': '#2196F3',    # Blue
            'Monument': '#9C27B0',     # Purple
            'Grave': '#FF9800',        # Orange
            'Cemetery': '#795548',     # Brown
            'Document': '#607D8B',     # Blue Grey
            'Other': '#9E9E9E',        # Grey
            'Unknown': '#757575',      # Dark Grey
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
                    'name': 'Photos by Type',
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
            ui.label('Breakdown by Photo Type').classes('text-subtitle1 mb-2')
            self.chart = ui.echart(echart_options).classes('w-full h-80')

    def _show_info(self) -> None:
        """Show information dialog explaining photo types."""
        with ui.dialog() as dialog, ui.card().classes('p-6'):
            ui.label('Photo Types Explained').classes('text-h6 text-primary mb-4')

            with ui.column().classes('gap-4'):
                ui.markdown('''
                **What are photo types?**

                Find a Grave memorials contain various types of photos that are categorized during extraction:

                **Common Photo Types:**

                - **Profile**: Main memorial photo (usually headstone or portrait)
                - **Headstone**: Photos of the burial headstone or grave marker
                - **Monument**: Photos of larger memorial monuments or structures
                - **Grave**: Photos of the grave site or burial plot
                - **Cemetery**: Photos of the cemetery grounds or location
                - **Document**: Photos of documents (certificates, obituaries, etc.)
                - **Other**: Miscellaneous photos (flowers, decorations, etc.)

                **Business Value:**

                - Track which types of memorial photos are being collected
                - Identify memorials with comprehensive photo documentation
                - Understand the completeness of your genealogy photo archive
                - Prioritize memorials that need additional photo documentation

                **Note**: Photo type classification is based on Find a Grave's categorization and may vary by memorial.
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
