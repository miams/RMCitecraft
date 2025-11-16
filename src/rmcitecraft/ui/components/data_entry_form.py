"""Data Entry Form Component for Batch Processing.

This component displays a form for manual data entry, showing only missing
required fields with validation and live citation preview.
"""

from typing import Callable

from nicegui import ui

from rmcitecraft.parsers.citation_formatter import CitationFormatter
from rmcitecraft.services.batch_processing import CitationBatchItem


class DataEntryFormComponent:
    """Data entry form component with smart field display and validation."""

    def __init__(
        self,
        citation: CitationBatchItem | None = None,
        on_data_change: Callable[[dict], None] | None = None,
        on_submit: Callable[[], None] | None = None,
    ):
        """Initialize data entry form component.

        Args:
            citation: Citation being edited
            on_data_change: Callback when data changes
            on_submit: Callback when form is submitted
        """
        self.citation = citation
        self.on_data_change = on_data_change
        self.on_submit = on_submit

        # Form data
        self.form_data: dict[str, str] = {}

        # UI references
        self.container: ui.column | None = None
        self.preview_container: ui.column | None = None

        # Citation formatter for live preview
        self.formatter = CitationFormatter()

    def render(self) -> ui.column:
        """Render the data entry form component.

        Returns:
            Container element
        """
        with ui.column().classes("w-full h-full gap-4 p-4") as self.container:
            self._render_content()
        return self.container

    def _render_content(self) -> None:
        """Render the content inside the container."""
        if not self.citation:
            ui.label("No citation selected").classes("text-gray-500 italic text-center")
            return

        # Data entry form (info moved to status bar)
        missing_fields = self.citation.missing_fields

        # Show manual entry form if:
        # 1. Citation has missing fields (needs data entry)
        # 2. Citation is in QUEUED status (not yet processed - allow manual entry)
        # 3. Citation is in MANUAL_REVIEW status (processed but needs manual data)
        show_form = (
            missing_fields
            or self.citation.status.value == "queued"
            or self.citation.status.value == "manual_review"
        )

        if show_form:
            with ui.card().classes("w-full p-2"):
                # Heading with Update button parallel and right-aligned
                with ui.row().classes("w-full items-center justify-between mb-2"):
                    if missing_fields:
                        ui.label("Missing Required Fields").classes("font-semibold text-sm")
                    else:
                        with ui.column().classes("gap-0"):
                            ui.label("Manual Data Entry").classes("font-semibold text-sm")
                            ui.label("Enter census data from the FamilySearch image").classes("text-xs text-gray-600")

                    # Update button right-aligned
                    ui.button(
                        "Update",
                        icon="check",
                        on_click=self._on_submit_click,
                    ).props("dense color=primary")

                # Show input fields for missing fields, or all key fields if QUEUED
                fields_to_show = missing_fields if missing_fields else self._get_default_census_fields()

                for field in fields_to_show:
                    self._render_field_input(field)

        else:
            # No missing fields and already processed
            ui.label("✅ All required fields complete").classes("text-green-600 font-semibold")

        # Citation preview (shows completed citations or live preview)
        self._render_citation_preview()

    def _render_field_input(self, field: str) -> None:
        """Render input field for missing data.

        Args:
            field: Field name (snake_case)
        """
        # Get current value from form data or merged data
        current_value = self.form_data.get(field, self.citation.merged_data.get(field, ''))

        # DEBUG: Log what we're reading
        from loguru import logger
        logger.debug(f"Field '{field}': form_data={self.form_data.get(field)}, merged_data={self.citation.merged_data.get(field)}, final value='{current_value}'")

        # Field label and hint
        label, hint, placeholder = self._get_field_metadata(field)

        with ui.column().classes("w-full gap-0 mb-2"):
            # Label
            ui.label(f"{label}:").classes("font-medium text-xs")

            # Input field with faded placeholder
            field_input = ui.input(
                placeholder=placeholder,
                value=current_value,
                on_change=lambda e, f=field: self._on_field_change(f, e.value),
            ).props("outlined dense").classes("w-full placeholder:text-gray-300")

            # Hint text (if exists, very compact)
            if hint:
                ui.label(hint).classes("text-[10px] text-gray-500 italic")

            # Validation feedback (if validation exists)
            if self.citation.validation and field in self.citation.validation.errors:
                error_text = self.citation.validation.errors[field]
                ui.label(f"⚠️ {error_text}").classes("text-xs text-red-600")

    def _get_default_census_fields(self) -> list[str]:
        """Get default fields to show for manual entry based on census year.

        Returns:
            List of field names to display
        """
        year = self.citation.census_year

        # Common fields for all years
        fields = ['enumeration_district', 'sheet', 'line']

        # Add year-specific fields
        if 1850 <= year <= 1940:
            fields.append('family_number')

        if 1850 <= year <= 1880:
            fields.append('dwelling_number')

        # Township/Ward for location detail
        fields.append('town_ward')

        return fields

    def _get_field_metadata(self, field: str) -> tuple[str, str, str]:
        """Get metadata for field (label, hint, placeholder).

        Args:
            field: Field name

        Returns:
            Tuple of (label, hint, placeholder)
        """
        metadata = {
            'enumeration_district': (
                'Enumeration District (ED)',
                'Format: "XX-XXX" (e.g., "96-413")',
                '96-413',
            ),
            'sheet': (
                'Sheet Number',
                'Sheet or page number from census image',
                '9',
            ),
            'line': (
                'Line Number',
                'Line number on census page',
                '75',
            ),
            'family_number': (
                'Family Number',
                'Family or dwelling number (if applicable)',
                '57',
            ),
            'dwelling_number': (
                'Dwelling Number',
                'Dwelling number (for 1850-1880 census)',
                '42',
            ),
            'town_ward': (
                'Township/Ward',
                'Township, ward, or other subdivision',
                'Canton Township',
            ),
        }

        return metadata.get(field, (field.replace('_', ' ').title(), '', ''))

    def _render_formatted_citations(self) -> None:
        """Render formatted Evidence Explained citations."""
        with ui.card().classes("w-full p-4 mt-4 bg-green-50"):
            ui.label("Generated Citations (Evidence Explained)").classes("font-semibold text-md mb-2 text-green-800")

            # Citation IDs for reference
            with ui.row().classes("w-full items-center gap-4 mb-3 text-xs text-gray-600"):
                ui.label(f"EventID: {self.citation.event_id}")
                ui.label(f"CitationID: {self.citation.citation_id}")
                ui.label(f"PersonID: {self.citation.person_id}")

            # Footnote
            with ui.expansion("Footnote", icon="format_quote").classes("w-full mb-2"):
                ui.html(content=self.citation.footnote or "", sanitize=False).classes("text-sm p-2")

            # Short Footnote
            with ui.expansion("Short Footnote", icon="short_text").classes("w-full mb-2"):
                ui.html(content=self.citation.short_footnote or "", sanitize=False).classes("text-sm p-2")

            # Bibliography
            with ui.expansion("Bibliography", icon="menu_book").classes("w-full"):
                ui.html(content=self.citation.bibliography or "", sanitize=False).classes("text-sm p-2")

    def _render_citation_preview(self) -> None:
        """Render live citation preview container."""
        with ui.card().classes("w-full p-2 mt-2") as self.preview_container:
            self._render_citation_preview_content()

    def _render_citation_preview_content(self) -> None:
        """Render the content inside the citation preview."""
        # Check if citation is complete with formatted citations from database
        if self.citation.status.value == "complete" and self.citation.footnote:
            # Show completed citations from database
            ui.label("Citations (Evidence Explained)").classes("font-semibold text-sm mb-1 text-green-700")
            ui.label("From database").classes("text-[10px] text-gray-500 mb-2")

            # Footnote
            ui.label("Footnote").classes("font-medium text-xs text-gray-700 mb-0")
            ui.html(
                content=self.citation.footnote,
                sanitize=False
            ).classes("text-xs mb-2 p-1 bg-gray-50 rounded")

            # Short Footnote
            ui.label("Short Footnote").classes("font-medium text-xs text-gray-700 mb-0")
            ui.html(
                content=self.citation.short_footnote or "",
                sanitize=False
            ).classes("text-xs mb-2 p-1 bg-gray-50 rounded")

            # Bibliography
            ui.label("Bibliography").classes("font-medium text-xs text-gray-700 mb-0")
            ui.html(
                content=self.citation.bibliography or "",
                sanitize=False
            ).classes("text-xs p-1 bg-gray-50 rounded")
        else:
            # Show live preview for incomplete citations
            ui.label("Citation Preview (Live)").classes("font-semibold text-sm mb-1")
            ui.label("Updates as you type").classes("text-[10px] text-gray-500 mb-2")

            # Merge form data with extracted data
            preview_data = {**self.citation.extracted_data, **self.form_data}

            # Add person name and URL if not already present
            if 'person_name' not in preview_data:
                preview_data['person_name'] = self.citation.full_name
            if 'familysearch_url' not in preview_data and self.citation.familysearch_url:
                preview_data['familysearch_url'] = self.citation.familysearch_url

            year = self.citation.census_year

            # USE THE FORMATTER (single source of truth - ensures WYSIWYG)
            from rmcitecraft.services.citation_formatter import format_census_citation_preview

            try:
                formatted = format_census_citation_preview(preview_data, year)

                # Footnote
                ui.label("Footnote").classes("font-medium text-xs text-gray-700 mb-0")
                ui.html(
                    content=formatted['footnote'],
                    sanitize=False
                ).classes("text-xs mb-2 p-1 bg-gray-50 rounded")

                # Short Footnote
                ui.label("Short Footnote").classes("font-medium text-xs text-gray-700 mb-0")
                ui.html(
                    content=formatted['short_footnote'],
                    sanitize=False
                ).classes("text-xs mb-2 p-1 bg-gray-50 rounded")

                # Bibliography
                ui.label("Bibliography").classes("font-medium text-xs text-gray-700 mb-0")
                ui.html(
                    content=formatted['bibliography'],
                    sanitize=False
                ).classes("text-xs p-1 bg-gray-50 rounded")

            except Exception as e:
                from loguru import logger
                logger.warning(f"Citation preview formatting error: {e}")
                ui.label(f"Preview unavailable: {str(e)}").classes("text-xs text-orange-600 italic")

    def _on_field_change(self, field: str, value: str) -> None:
        """Handle field value change.

        Args:
            field: Field name
            value: New value
        """
        self.form_data[field] = value

        # Trigger callback
        if self.on_data_change:
            self.on_data_change(self.form_data)

        # Refresh preview
        if self.preview_container:
            self.preview_container.clear()
            with self.preview_container:
                self._render_citation_preview_content()

    def _on_submit_click(self) -> None:
        """Handle submit button click."""
        if self.on_submit:
            self.on_submit()
        else:
            ui.notify("Form submitted!", type="positive")

    def refresh(self) -> None:
        """Refresh the component UI."""
        if self.container:
            self.container.clear()
            with self.container:
                self._render_content()

    def update_citation(self, citation: CitationBatchItem | None) -> None:
        """Update the citation being edited.

        Args:
            citation: New citation to edit
        """
        from loguru import logger
        self.citation = citation
        self.form_data = {}  # Reset form data

        # DEBUG: Log citation data
        if citation:
            logger.debug(f"Form received citation {citation.citation_id}: merged_data keys={list(citation.merged_data.keys())}, merged_data={citation.merged_data}")
        else:
            logger.debug("Form received None citation")

        self.refresh()
