"""Item Detail Panel component for dashboard."""

from datetime import datetime

from nicegui import ui

from rmcitecraft.database import batch_dashboard_queries


class ItemDetailPanel:
    """Detail panel showing full information about a selected batch item.

    Includes RootsMagic drill-down data (person details, families, citations).
    """

    def __init__(self, rm_database_path: str):
        """Initialize item detail panel.

        Args:
            rm_database_path: Path to RootsMagic database for drill-down queries
        """
        self.rm_database_path = rm_database_path
        self.current_item = None
        self.container = None

    def render(self, item_data: dict | None = None) -> None:
        """Render the item detail panel.

        Args:
            item_data: Batch item data dict (None = show empty state)
        """
        if self.container:
            self.container.clear()
        else:
            self.container = ui.column().classes('w-full')

        with self.container:
            if not item_data:
                self._render_empty_state()
                return

            self.current_item = item_data

            # Header
            with ui.card().classes('w-full bg-primary text-white'):
                with ui.row().classes('w-full justify-between items-center p-4'):
                    with ui.column():
                        ui.label('Item Details').classes('text-h6')
                        ui.label(item_data.get('person_name', 'Unknown')).classes('text-subtitle1')

                    ui.button(
                        '',
                        icon='close',
                        on_click=lambda: self.render(None)
                    ).props('flat round dense').tooltip('Close detail panel')

            # Content sections in expansion panels
            with ui.column().classes('w-full gap-2'):
                self._render_batch_info()
                self._render_person_info()
                self._render_families_info()
                self._render_citations_info()
                self._render_error_details()

    def _render_empty_state(self) -> None:
        """Render empty state when no item selected."""
        with ui.card().classes('w-full'):
            with ui.column().classes('items-center p-8 gap-4'):
                ui.icon('info').classes('text-6xl text-grey-5')
                ui.label('Select an item to view details').classes('text-grey-7')
                ui.label('Click the "View Details" button in the table').classes('text-sm text-grey-6')

    def _render_batch_info(self) -> None:
        """Render batch processing information."""
        item = self.current_item
        if not item:
            return

        with ui.expansion('Batch Processing Info', icon='info', value=True).classes('w-full'):
            with ui.column().classes('gap-2 p-2'):
                self._render_info_row('Item ID', str(item['id']))
                self._render_info_row('PersonID', str(item['person_id']))
                self._render_info_row('Memorial ID', item.get('memorial_id', 'N/A'))

                # Status with color badge
                status = item.get('status', 'unknown')
                status_color = self._get_status_color(status)
                with ui.row().classes('items-center gap-2'):
                    ui.label('Status:').classes('font-bold text-sm')
                    ui.badge(status.capitalize()).props(f'color={status_color}')

                # Timestamps
                if item.get('created_at'):
                    created = self._format_timestamp(item['created_at'])
                    self._render_info_row('Created', created)

                if item.get('updated_at'):
                    updated = self._format_timestamp(item['updated_at'])
                    self._render_info_row('Last Updated', updated)

                # Memorial URL with link button
                if item.get('memorial_url'):
                    with ui.row().classes('items-center gap-2'):
                        ui.label('Memorial URL:').classes('font-bold text-sm')
                        ui.button(
                            'Open Find a Grave',
                            icon='open_in_new',
                            on_click=lambda: ui.open(item['memorial_url'], new_tab=True)
                        ).props('dense outline size=sm color=blue')

    def _render_person_info(self) -> None:
        """Render RootsMagic person information."""
        item = self.current_item
        if not item:
            return

        person_id = item['person_id']

        # Query RootsMagic for person details
        try:
            person = batch_dashboard_queries.get_person_details(
                self.rm_database_path,
                person_id
            )

            if person:
                with ui.expansion('Person Information (RootsMagic)', icon='person').classes('w-full'):
                    with ui.column().classes('gap-2 p-2'):
                        # Name
                        full_name = self._format_person_name(person)
                        self._render_info_row('Full Name', full_name)

                        # Sex
                        sex_display = {0: 'Male', 1: 'Female', 2: 'Unknown'}.get(person.get('Sex', 2), 'Unknown')
                        self._render_info_row('Sex', sex_display)

                        # Birth
                        birth_info = []
                        if person.get('BirthYear'):
                            birth_info.append(str(person['BirthYear']))
                        if person.get('birth_date'):
                            birth_info.append(person['birth_date'])
                        if person.get('birth_place'):
                            birth_info.append(person['birth_place'])
                        if birth_info:
                            self._render_info_row('Birth', ' | '.join(birth_info))

                        # Death
                        death_info = []
                        if person.get('DeathYear'):
                            death_info.append(str(person['DeathYear']))
                        if person.get('death_date'):
                            death_info.append(person['death_date'])
                        if person.get('death_place'):
                            death_info.append(person['death_place'])
                        if death_info:
                            self._render_info_row('Death', ' | '.join(death_info))

        except Exception as e:
            with ui.expansion('Person Information (RootsMagic)', icon='person').classes('w-full'):
                ui.label(f'Error loading person data: {e}').classes('text-red text-sm p-2')

    def _render_families_info(self) -> None:
        """Render RootsMagic family information."""
        item = self.current_item
        if not item:
            return

        person_id = item['person_id']

        try:
            families = batch_dashboard_queries.get_person_families(
                self.rm_database_path,
                person_id
            )

            with ui.expansion('Family Relationships (RootsMagic)', icon='family_restroom').classes('w-full'):
                with ui.column().classes('gap-4 p-2'):
                    # Spouse families
                    if families['spouse_families']:
                        ui.label('Spouse Families:').classes('font-bold text-sm')
                        for family in families['spouse_families']:
                            self._render_family_card(family, person_id, is_child=False)

                    # Parent families
                    if families['parent_families']:
                        ui.label('Parent Families:').classes('font-bold text-sm mt-2')
                        for family in families['parent_families']:
                            self._render_family_card(family, person_id, is_child=True)

                    # No families
                    if not families['spouse_families'] and not families['parent_families']:
                        ui.label('No family relationships found').classes('text-sm text-grey-6')

        except Exception as e:
            with ui.expansion('Family Relationships (RootsMagic)', icon='family_restroom').classes('w-full'):
                ui.label(f'Error loading family data: {e}').classes('text-red text-sm p-2')

    def _render_citations_info(self) -> None:
        """Render RootsMagic citations information."""
        item = self.current_item
        if not item:
            return

        person_id = item['person_id']

        try:
            citations = batch_dashboard_queries.get_person_citations(
                self.rm_database_path,
                person_id
            )

            with ui.expansion('Citations (RootsMagic)', icon='format_quote').classes('w-full'):
                with ui.column().classes('gap-2 p-2'):
                    if citations:
                        ui.label(f'Found {len(citations)} citation(s)').classes('text-sm font-bold')

                        for citation in citations:
                            with ui.card().classes('w-full bg-grey-1 p-2'):
                                ui.label(citation['source_name']).classes('text-sm font-bold')
                                if citation.get('CitationName'):
                                    ui.label(citation['CitationName']).classes('text-xs text-grey-7')
                                ui.label(f"Citation ID: {citation['CitationID']} | Source ID: {citation['SourceID']}").classes('text-xs text-grey-6')
                    else:
                        ui.label('No citations found').classes('text-sm text-grey-6')

        except Exception as e:
            with ui.expansion('Citations (RootsMagic)', icon='format_quote').classes('w-full'):
                ui.label(f'Error loading citations: {e}').classes('text-red text-sm p-2')

    def _render_error_details(self) -> None:
        """Render error details if item failed."""
        item = self.current_item
        if not item or item.get('status') != 'failed':
            return

        error_message = item.get('error_message')
        if not error_message:
            return

        with ui.expansion('Error Details', icon='error', value=True).classes('w-full bg-red-1'):
            with ui.column().classes('gap-2 p-2'):
                ui.label('Error Message:').classes('font-bold text-sm text-red')
                ui.label(error_message).classes('text-sm font-mono bg-white p-2 rounded')

                # Retry count
                retry_count = item.get('retry_count', 0)
                if retry_count > 0:
                    self._render_info_row('Retry Count', str(retry_count))

    def _render_family_card(self, family: dict, person_id: int, is_child: bool) -> None:
        """Render a family card.

        Args:
            family: Family data dict
            person_id: Current person ID
            is_child: True if person is child in this family
        """
        with ui.card().classes('w-full bg-blue-1 p-2'):
            ui.label(f"Family ID: {family['FamilyID']}").classes('text-xs font-bold text-blue')

            # Father
            if family.get('father_surname') or family.get('father_given'):
                father_name = f"{family.get('father_given', '')} {family.get('father_surname', '')}".strip()
                role = '' if is_child else ' (You)' if family['FatherID'] == person_id else ''
                ui.label(f"Father: {father_name}{role}").classes('text-sm')

            # Mother
            if family.get('mother_surname') or family.get('mother_given'):
                mother_name = f"{family.get('mother_given', '')} {family.get('mother_surname', '')}".strip()
                role = '' if is_child else ' (You)' if family['MotherID'] == person_id else ''
                ui.label(f"Mother: {mother_name}{role}").classes('text-sm')

    def _render_info_row(self, label: str, value: str) -> None:
        """Render an information row.

        Args:
            label: Field label
            value: Field value
        """
        with ui.row().classes('gap-2'):
            ui.label(f'{label}:').classes('font-bold text-sm')
            ui.label(value).classes('text-sm')

    def _format_person_name(self, person: dict) -> str:
        """Format person name from components.

        Args:
            person: Person data dict

        Returns:
            Formatted full name
        """
        parts = []
        if person.get('Prefix'):
            parts.append(person['Prefix'])
        if person.get('Given'):
            parts.append(person['Given'])
        if person.get('Surname'):
            parts.append(person['Surname'])
        if person.get('Suffix'):
            parts.append(person['Suffix'])

        return ' '.join(parts) if parts else 'Unknown'

    def _format_timestamp(self, timestamp_str: str) -> str:
        """Format timestamp string.

        Args:
            timestamp_str: ISO format timestamp

        Returns:
            Formatted timestamp string
        """
        try:
            timestamp_str = timestamp_str.replace('Z', '+00:00')
            dt = datetime.fromisoformat(timestamp_str)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return timestamp_str

    def _get_status_color(self, status: str) -> str:
        """Get color for status.

        Args:
            status: Status string

        Returns:
            Color name
        """
        if status in ['completed', 'complete', 'created_citation']:
            return 'green'
        elif status == 'failed':
            return 'red'
        elif status in ['pending', 'queued']:
            return 'orange'
        elif status == 'skipped':
            return 'grey'
        else:
            return 'blue'

    def update(self, item_data: dict) -> None:
        """Update panel with new item data.

        Args:
            item_data: Batch item data dict
        """
        self.render(item_data)

    def clear(self) -> None:
        """Clear the panel and show empty state."""
        self.render(None)
