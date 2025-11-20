"""Export Tools Card component for dashboard."""

import csv
import json
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Callable

from nicegui import ui

from rmcitecraft.database.batch_state_repository import BatchStateRepository


class ExportToolsCard:
    """Export tools card for exporting dashboard data to various formats."""

    def __init__(
        self,
        state_repo: BatchStateRepository,
        session_id: str | None = None,
        on_export_complete: Callable[[str, str], None] | None = None,
    ):
        """Initialize export tools card.

        Args:
            state_repo: Batch state repository
            session_id: Optional session identifier (None = all sessions)
            on_export_complete: Callback when export completes (receives format, path)
        """
        self._state_repo = state_repo
        self.session_id = session_id
        self._on_export_complete = on_export_complete
        self.container = None

    def render(self) -> None:
        """Render the export tools card."""
        with ui.card().classes('w-full') as self.container:
            self._render_content()

    def _render_content(self) -> None:
        """Render the content inside the container."""
        # Header
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.label('Export Tools').classes('text-h6 text-primary')
                ui.button(
                    '',
                    icon='info',
                    on_click=self._show_info
                ).props('flat dense round size=sm').tooltip('Export options and formats')

        # Export options grid
        with ui.grid(columns=3).classes('w-full gap-4'):
            # Export Items CSV
            with ui.card().classes('cursor-pointer hover:shadow-lg transition-shadow') as card:
                card.on('click', lambda: self._export_items_csv())
                with ui.column().classes('items-center p-6 gap-3'):
                    ui.icon('table_chart').classes('text-5xl text-blue')
                    ui.label('Export Items (CSV)').classes('text-subtitle1 font-bold')
                    ui.label('All batch items with status and metadata').classes('text-caption text-grey-6 text-center')

            # Export Sessions JSON
            with ui.card().classes('cursor-pointer hover:shadow-lg transition-shadow') as card:
                card.on('click', lambda: self._export_sessions_json())
                with ui.column().classes('items-center p-6 gap-3'):
                    ui.icon('code').classes('text-5xl text-green')
                    ui.label('Export Sessions (JSON)').classes('text-subtitle1 font-bold')
                    ui.label('Session metadata with statistics').classes('text-caption text-grey-6 text-center')

            # Export Summary Report
            with ui.card().classes('cursor-pointer hover:shadow-lg transition-shadow') as card:
                card.on('click', lambda: self._export_summary_report())
                with ui.column().classes('items-center p-6 gap-3'):
                    ui.icon('description').classes('text-5xl text-purple')
                    ui.label('Summary Report (TXT)').classes('text-subtitle1 font-bold')
                    ui.label('Human-readable summary report').classes('text-caption text-grey-6 text-center')

        # Export history (if available)
        self._render_export_history()

    def _render_export_history(self) -> None:
        """Render recent exports history."""
        # For now, just show a placeholder
        # Could be enhanced to track exports in database
        with ui.card().classes('w-full mt-4 bg-grey-1'):
            with ui.column().classes('p-4 gap-2'):
                ui.label('Export History').classes('text-subtitle2 font-bold')
                ui.label('Recent exports will appear here').classes('text-sm text-grey-6')

    def _export_items_csv(self) -> None:
        """Export batch items to CSV file."""
        # Get items
        if self.session_id:
            items = self._state_repo.get_session_items(self.session_id)
            filename = f"batch_items_{self.session_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        else:
            items = []
            sessions = self._state_repo.get_all_sessions()
            for session in sessions:
                items.extend(self._state_repo.get_session_items(session['session_id']))
            filename = f"batch_items_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        if not items:
            ui.notify('No items to export', type='warning')
            return

        # Create CSV
        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                'id', 'session_id', 'person_id', 'person_name', 'memorial_id',
                'memorial_url', 'status', 'error_message', 'retry_count',
                'created_at', 'updated_at', 'last_attempt_at',
                'created_citation_id', 'created_source_id', 'created_burial_event_id',
                'has_images', 'image_count'
            ]
        )
        writer.writeheader()

        for item in items:
            # Calculate image info
            image_paths = item.get('downloaded_image_paths', [])
            if isinstance(image_paths, str):
                try:
                    image_paths = json.loads(image_paths)
                except json.JSONDecodeError:
                    image_paths = []

            writer.writerow({
                'id': item['id'],
                'session_id': item['session_id'],
                'person_id': item['person_id'],
                'person_name': item['person_name'],
                'memorial_id': item['memorial_id'],
                'memorial_url': item['memorial_url'],
                'status': item['status'],
                'error_message': item.get('error_message', ''),
                'retry_count': item.get('retry_count', 0),
                'created_at': item.get('created_at', ''),
                'updated_at': item.get('updated_at', ''),
                'last_attempt_at': item.get('last_attempt_at', ''),
                'created_citation_id': item.get('created_citation_id', ''),
                'created_source_id': item.get('created_source_id', ''),
                'created_burial_event_id': item.get('created_burial_event_id', ''),
                'has_images': 'Yes' if image_paths else 'No',
                'image_count': len(image_paths) if image_paths else 0
            })

        # Trigger download
        csv_content = output.getvalue()
        ui.download(csv_content.encode('utf-8'), filename)
        ui.notify(f'Exported {len(items)} items to {filename}', type='positive')

        if self._on_export_complete:
            self._on_export_complete('csv', filename)

    def _export_sessions_json(self) -> None:
        """Export sessions to JSON file."""
        sessions = self._state_repo.get_all_sessions()

        if not sessions:
            ui.notify('No sessions to export', type='warning')
            return

        # Enrich with statistics
        export_data = {
            'export_date': datetime.now().isoformat(),
            'total_sessions': len(sessions),
            'sessions': []
        }

        for session in sessions:
            session_data = dict(session)
            # Add statistics
            items = self._state_repo.get_session_items(session['session_id'])
            session_data['statistics'] = {
                'total_items': len(items),
                'completed': sum(1 for i in items if i['status'] in ['completed', 'complete', 'created_citation']),
                'failed': sum(1 for i in items if i['status'] == 'failed'),
                'pending': sum(1 for i in items if i['status'] in ['pending', 'queued']),
            }
            export_data['sessions'].append(session_data)

        # Trigger download
        filename = f"batch_sessions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        json_content = json.dumps(export_data, indent=2)
        ui.download(json_content.encode('utf-8'), filename)
        ui.notify(f'Exported {len(sessions)} sessions to {filename}', type='positive')

        if self._on_export_complete:
            self._on_export_complete('json', filename)

    def _export_summary_report(self) -> None:
        """Export human-readable summary report."""
        # Get master progress
        progress = self._state_repo.get_master_progress()
        sessions = self._state_repo.get_all_sessions()

        # Build report
        report = StringIO()
        report.write("=" * 80 + "\n")
        report.write("RMCitecraft Batch Processing Summary Report\n")
        report.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        report.write("=" * 80 + "\n\n")

        # Master Progress
        report.write("MASTER PROGRESS\n")
        report.write("-" * 80 + "\n")
        report.write(f"Total Items:     {progress['total_items']:,}\n")
        report.write(f"Completed:       {progress['completed']:,}\n")
        report.write(f"Failed:          {progress['failed']:,}\n")
        report.write(f"Pending:         {progress['pending']:,}\n")
        report.write(f"Skipped:         {progress['skipped']:,}\n")

        total = progress['completed'] + progress['failed']
        success_rate = (progress['completed'] / total * 100) if total > 0 else 0
        report.write(f"Success Rate:    {success_rate:.1f}%\n")
        report.write("\n")

        # Sessions
        report.write("SESSIONS\n")
        report.write("-" * 80 + "\n")
        for i, session in enumerate(sessions, 1):
            report.write(f"\n{i}. Session {session['session_id']}\n")
            report.write(f"   Status:         {session['status']}\n")
            report.write(f"   Created:        {session['created_at']}\n")
            report.write(f"   Total Items:    {session.get('total_items', 0):,}\n")
            report.write(f"   Completed:      {session.get('completed_count', 0):,}\n")
            report.write(f"   Errors:         {session.get('error_count', 0):,}\n")

        # Photos
        report.write("\n\nPHOTO STATISTICS\n")
        report.write("-" * 80 + "\n")
        photo_stats = self._state_repo.get_photo_statistics()
        report.write(f"Total Photos:           {photo_stats['total_photos']:,}\n")
        report.write(f"Items with Photos:      {photo_stats['items_with_photos']:,}\n")
        if photo_stats['photos_by_type']:
            report.write("\nPhotos by Type:\n")
            for photo_type, count in sorted(
                photo_stats['photos_by_type'].items(),
                key=lambda x: x[1],
                reverse=True
            ):
                report.write(f"  {photo_type:20s} {count:,}\n")

        # Errors
        report.write("\n\nERROR SUMMARY\n")
        report.write("-" * 80 + "\n")
        error_dist = self._state_repo.get_error_distribution()
        if error_dist:
            for error_type, count in sorted(
                error_dist.items(),
                key=lambda x: x[1],
                reverse=True
            ):
                pct = (count / progress['failed'] * 100) if progress['failed'] > 0 else 0
                report.write(f"{error_type:30s} {count:5,} ({pct:5.1f}%)\n")
        else:
            report.write("No errors detected\n")

        report.write("\n" + "=" * 80 + "\n")

        # Trigger download
        filename = f"batch_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        ui.download(report.getvalue().encode('utf-8'), filename)
        ui.notify(f'Exported summary report to {filename}', type='positive')

        if self._on_export_complete:
            self._on_export_complete('txt', filename)

    def _show_info(self) -> None:
        """Show information dialog explaining export tools."""
        with ui.dialog() as dialog, ui.card().classes('p-6'):
            ui.label('Export Tools Explained').classes('text-h6 text-primary mb-4')

            with ui.column().classes('gap-4'):
                ui.markdown('''
                **What are Export Tools?**

                Export tools allow you to extract dashboard data for external analysis,
                reporting, backup, or integration with other systems.

                **Export Formats:**

                **1. Items CSV**
                - Detailed list of all batch items
                - Includes status, errors, citations, images
                - Use for: Spreadsheet analysis, data science, reporting
                - Format: Standard CSV (comma-separated values)

                **2. Sessions JSON**
                - Session metadata with statistics
                - Machine-readable structured data
                - Use for: API integration, backup, programmatic analysis
                - Format: JSON with nested structure

                **3. Summary Report TXT**
                - Human-readable overview report
                - Master progress, session details, statistics
                - Use for: Documentation, stakeholder reports, archival
                - Format: Plain text with formatted sections

                **Session Filtering:**

                - **Current Session**: Export only selected session data
                - **All Sessions**: Export cumulative data across all sessions

                **Use Cases:**

                - **Backup**: Archive batch processing history
                - **Analysis**: Import into Excel, R, Python for custom analysis
                - **Reporting**: Generate reports for stakeholders
                - **Integration**: Feed data into other genealogy tools
                - **Debugging**: Share detailed data for troubleshooting
                - **Documentation**: Document batch processing for research notes

                **File Locations:**

                Exports are downloaded to your default browser download folder.
                Files are timestamped to prevent overwrites.
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
