"""Master Progress Card component for dashboard."""

from nicegui import ui

from rmcitecraft.database.batch_state_repository import BatchStateRepository


class MasterProgressCard:
    """Master progress card showing overall batch processing progress toward goal."""

    def __init__(self, state_repo: BatchStateRepository, total_goal: int = 5000):
        """Initialize master progress card.

        Args:
            state_repo: Batch state repository
            total_goal: Total number of items to process (default: 5000)
        """
        self._state_repo = state_repo  # Private
        self.total_goal = total_goal
        self.container = None
        self.progress_bar = None
        self.stat_boxes = {}

    def render(self) -> None:
        """Render the master progress card."""
        with ui.card().classes('w-full') as self.container:
            self._render_content()

    def _render_content(self) -> None:
        """Render the content inside the container."""
        # Header
        with ui.row().classes('w-full justify-between items-center mb-4'):
            ui.label('Master Progress').classes('text-h6 text-primary')
            ui.button(
                '',
                icon='refresh',
                on_click=self.update
            ).props('flat dense round').tooltip('Refresh progress')

        # Get current progress
        progress = self._state_repo.get_master_progress()
        completed = progress['completed']
        failed = progress['failed']
        pending = progress['pending']
        skipped = progress['skipped']
        total_items = progress['total_items']

        # Calculate progress percentage
        progress_pct = (completed / self.total_goal) * 100 if self.total_goal > 0 else 0

        # Progress bar
        with ui.column().classes('w-full gap-1'):
            with ui.row().classes('w-full justify-between'):
                ui.label(f'{completed:,} / {self.total_goal:,} items completed').classes('text-sm')
                ui.label(f'{progress_pct:.1f}%').classes('text-sm font-bold text-green')

            self.progress_bar = ui.linear_progress(
                value=completed / self.total_goal if self.total_goal > 0 else 0
            ).props('size=25px color=green')

        # Statistics grid
        with ui.grid(columns=4).classes('w-full gap-4 mt-6'):
            self.stat_boxes['total'] = self._create_stat_box(
                'Total Goal',
                f'{self.total_goal:,}',
                'flag',
                'blue'
            )
            self.stat_boxes['completed'] = self._create_stat_box(
                'Completed',
                f'{completed:,}',
                'check_circle',
                'green'
            )
            self.stat_boxes['remaining'] = self._create_stat_box(
                'Remaining',
                f'{self.total_goal - completed:,}',
                'pending',
                'orange'
            )
            self.stat_boxes['success_rate'] = self._create_stat_box(
                'Success Rate',
                f'{self._calculate_success_rate(completed, failed):.1f}%',
                'analytics',
                'purple'
            )

        # Additional stats row
        with ui.grid(columns=3).classes('w-full gap-4 mt-4'):
            self._create_small_stat_box('Failed', f'{failed:,}', 'error', 'red')
            self._create_small_stat_box('Pending', f'{pending:,}', 'schedule', 'amber')
            self._create_small_stat_box('Skipped', f'{skipped:,}', 'skip_next', 'grey')

    def _create_stat_box(
        self,
        label: str,
        value: str,
        icon: str,
        color: str
    ) -> ui.card:
        """Create a statistics box.

        Args:
            label: Stat label
            value: Stat value
            icon: Material icon name
            color: Color name

        Returns:
            Card element containing the stat box
        """
        with ui.card().classes(f'bg-{color}-1') as card:
            with ui.row().classes('items-center gap-3 p-2'):
                ui.icon(icon).classes(f'text-4xl text-{color}')
                with ui.column().classes('gap-0'):
                    ui.label(value).classes(f'text-h5 text-{color} font-bold')
                    ui.label(label).classes('text-caption text-grey-7')
        return card

    def _create_small_stat_box(
        self,
        label: str,
        value: str,
        icon: str,
        color: str
    ) -> None:
        """Create a small statistics box.

        Args:
            label: Stat label
            value: Stat value
            icon: Material icon name
            color: Color name
        """
        with ui.card().classes('bg-grey-1'):
            with ui.row().classes('items-center gap-2 p-2'):
                ui.icon(icon).classes(f'text-2xl text-{color}')
                with ui.column().classes('gap-0'):
                    ui.label(value).classes(f'text-h6 text-{color}')
                    ui.label(label).classes('text-caption text-grey-7')

    def _calculate_success_rate(self, completed: int, failed: int) -> float:
        """Calculate success rate percentage.

        Args:
            completed: Number of completed items
            failed: Number of failed items

        Returns:
            Success rate as percentage
        """
        total = completed + failed
        if total == 0:
            return 0.0
        return (completed / total) * 100

    def update(self) -> None:
        """Update the progress card with latest data."""
        # Get latest progress
        progress = self._state_repo.get_master_progress()
        completed = progress['completed']
        failed = progress['failed']
        pending = progress['pending']
        skipped = progress['skipped']

        # Update progress bar
        progress_pct = (completed / self.total_goal) * 100 if self.total_goal > 0 else 0
        if self.progress_bar:
            self.progress_bar.value = completed / self.total_goal if self.total_goal > 0 else 0

        # Update stat boxes (would need to rebuild or use reactive bindings)
        # For now, we'll just refresh the entire container
        if self.container:
            self.container.clear()
            with self.container:
                self._render_content()
