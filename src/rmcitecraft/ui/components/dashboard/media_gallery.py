"""Media Gallery Card component for dashboard."""

import json
from pathlib import Path
from typing import Callable

from nicegui import ui

from rmcitecraft.database.batch_state_repository import FindAGraveBatchStateRepository


class MediaGalleryCard:
    """Media gallery card showing downloaded memorial photos in visual grid."""

    def __init__(
        self,
        state_repo: FindAGraveBatchStateRepository,
        session_id: str | None = None,
        on_image_click: Callable[[dict], None] | None = None,
        max_display: int = 50,
    ):
        """Initialize media gallery card.

        Args:
            state_repo: Batch state repository
            session_id: Optional session identifier (None = all sessions)
            on_image_click: Callback when user clicks an image
            max_display: Maximum number of images to display (default: 50)
        """
        self._state_repo = state_repo
        self.session_id = session_id
        self._on_image_click = on_image_click
        self.max_display = max_display
        self.container = None
        self.gallery = None

    def render(self) -> None:
        """Render the media gallery card."""
        with ui.card().classes('w-full') as self.container:
            self._render_content()

    def _render_content(self) -> None:
        """Render the content inside the container."""
        # Header
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.label('Media Gallery').classes('text-h6 text-primary')
                ui.button(
                    '',
                    icon='info',
                    on_click=self._show_info
                ).props('flat dense round size=sm').tooltip('About the media gallery')
            with ui.row().classes('gap-2'):
                ui.select(
                    [25, 50, 100, 200],
                    value=self.max_display,
                    label='Display',
                    on_change=lambda e: self._change_display_limit(e.value)
                ).props('dense outlined').classes('w-32')
                ui.button(
                    '',
                    icon='refresh',
                    on_click=self.update
                ).props('flat dense round').tooltip('Refresh gallery')

        # Get items with photos
        items = self._get_items_with_photos()

        if items:
            # Summary
            total_photos = sum(len(item['image_paths']) for item in items)

            with ui.row().classes('w-full gap-4 mb-4'):
                with ui.card().classes('bg-blue-1 flex-1'):
                    with ui.column().classes('items-center p-4 gap-1'):
                        ui.label(f'{total_photos:,}').classes('text-h4 text-blue font-bold')
                        ui.label('Total Photos').classes('text-caption text-grey-7')

                with ui.card().classes('bg-green-1 flex-1'):
                    with ui.column().classes('items-center p-4 gap-1'):
                        ui.label(f'{len(items):,}').classes('text-h4 text-green font-bold')
                        ui.label('Memorials with Photos').classes('text-caption text-grey-7')

            # Display limit notice
            if total_photos > self.max_display:
                ui.label(
                    f'Showing first {self.max_display} of {total_photos:,} photos'
                ).classes('text-sm text-grey-6 mb-2')

            # Photo gallery grid
            self._render_gallery(items)
        else:
            # Empty state
            with ui.column().classes('items-center p-8'):
                ui.icon('photo_library').classes('text-6xl text-grey-5')
                ui.label('No photos downloaded yet').classes('text-grey-7')
                if self.session_id:
                    ui.label('Process a batch with image downloads to see photos').classes('text-sm text-grey-6')

    def _get_items_with_photos(self) -> list[dict]:
        """Get batch items that have downloaded photos.

        Returns:
            List of items with photo data
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

        # Filter to items with photos
        items_with_photos = []
        for item in items:
            if item.get('downloaded_image_paths'):
                image_paths = item['downloaded_image_paths']
                if isinstance(image_paths, str):
                    try:
                        image_paths = json.loads(image_paths)
                    except json.JSONDecodeError:
                        continue

                if image_paths:  # Non-empty list
                    # Get photo types from extracted_data if available
                    photo_types = {}
                    if item.get('extracted_data'):
                        try:
                            extracted = item['extracted_data']
                            if isinstance(extracted, str):
                                extracted = json.loads(extracted)
                            photos = extracted.get('photos', [])
                            for i, photo in enumerate(photos):
                                if i < len(image_paths):
                                    photo_types[image_paths[i]] = photo.get('type', 'Unknown')
                        except (json.JSONDecodeError, KeyError):
                            pass

                    items_with_photos.append({
                        'id': item['id'],
                        'person_id': item['person_id'],
                        'person_name': item['person_name'],
                        'memorial_id': item['memorial_id'],
                        'memorial_url': item['memorial_url'],
                        'image_paths': image_paths,
                        'photo_types': photo_types,
                    })

        return items_with_photos

    def _render_gallery(self, items: list[dict]) -> None:
        """Render photo gallery grid.

        Args:
            items: List of items with photo data
        """
        with ui.card().classes('w-full'):
            ui.label('Photo Gallery').classes('text-subtitle1 mb-4')

            # Collect all photos with metadata
            photos = []
            for item in items:
                for img_path in item['image_paths']:
                    photo_type = item['photo_types'].get(img_path, 'Unknown')
                    photos.append({
                        'path': img_path,
                        'person_name': item['person_name'],
                        'memorial_id': item['memorial_id'],
                        'memorial_url': item['memorial_url'],
                        'photo_type': photo_type,
                        'item_id': item['id'],
                    })

                    # Stop at display limit
                    if len(photos) >= self.max_display:
                        break

                if len(photos) >= self.max_display:
                    break

            # Render gallery grid
            with ui.element('div').classes('grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4'):
                for photo in photos:
                    self._render_photo_card(photo)

    def _render_photo_card(self, photo: dict) -> None:
        """Render individual photo card.

        Args:
            photo: Photo metadata dict
        """
        path = Path(photo['path'])

        # Check if file exists
        if not path.exists():
            # Show placeholder for missing file
            with ui.card().classes('cursor-pointer hover:shadow-lg transition-shadow'):
                with ui.column().classes('items-center p-4 gap-2'):
                    ui.icon('broken_image').classes('text-6xl text-grey-5')
                    ui.label('Image not found').classes('text-xs text-grey-6')
                    ui.label(path.name).classes('text-xs text-grey-6 text-center line-clamp-2')
            return

        # Render photo with metadata
        with ui.card().classes('cursor-pointer hover:shadow-lg transition-shadow') as card:
            # Image
            with ui.element('div').classes('relative'):
                ui.image(str(path)).classes('w-full h-48 object-cover')

                # Photo type badge (overlay)
                with ui.element('div').classes('absolute top-2 right-2'):
                    ui.badge(photo['photo_type']).props(f'color={self._get_photo_type_color(photo["photo_type"])}')

            # Metadata
            with ui.column().classes('p-2 gap-1'):
                ui.label(photo['person_name']).classes('text-sm font-bold line-clamp-1')
                ui.label(f"Memorial: {photo['memorial_id']}").classes('text-xs text-grey-6')

            # Click handler
            card.on('click', lambda p=photo: self._on_photo_click(p))

    def _get_photo_type_color(self, photo_type: str) -> str:
        """Get color for photo type badge.

        Args:
            photo_type: Photo type string

        Returns:
            Color name
        """
        return {
            'Profile': 'green',
            'Headstone': 'blue',
            'Monument': 'purple',
            'Grave': 'orange',
            'Cemetery': 'brown',
            'Document': 'blue-grey',
            'Other': 'grey',
            'Unknown': 'grey',
        }.get(photo_type, 'grey')

    def _on_photo_click(self, photo: dict) -> None:
        """Handle photo click.

        Args:
            photo: Photo metadata dict
        """
        # Show photo details dialog
        with ui.dialog() as dialog, ui.card().classes('w-full max-w-4xl'):
            # Header
            with ui.row().classes('w-full justify-between items-center p-4 bg-primary text-white'):
                with ui.column():
                    ui.label(photo['person_name']).classes('text-h6')
                    ui.label(f"Memorial: {photo['memorial_id']}").classes('text-caption')
                ui.button('', icon='close', on_click=dialog.close).props('flat round dense')

            # Image
            ui.image(photo['path']).classes('w-full max-h-screen-75 object-contain')

            # Metadata
            with ui.card().classes('w-full bg-grey-1'):
                with ui.column().classes('p-4 gap-2'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('category').classes('text-blue')
                        ui.label(f"Photo Type: {photo['photo_type']}").classes('text-sm')

                    with ui.row().classes('items-center gap-2'):
                        ui.icon('folder').classes('text-blue')
                        ui.label(f"File: {Path(photo['path']).name}").classes('text-sm')

                    with ui.row().classes('items-center gap-2'):
                        ui.icon('link').classes('text-blue')
                        ui.button(
                            'Open Find a Grave Memorial',
                            icon='open_in_new',
                            on_click=lambda url=photo['memorial_url']: ui.run_javascript(f'window.open("{url}", "_blank")')
                        ).props('dense outline size=sm color=blue')

        dialog.open()

        # Callback
        if self._on_image_click:
            self._on_image_click(photo)

    def _change_display_limit(self, limit: int) -> None:
        """Change display limit and refresh.

        Args:
            limit: New display limit
        """
        self.max_display = limit
        self.update()
        ui.notify(f'Display limit set to {limit} photos', type='info')

    def _show_info(self) -> None:
        """Show information dialog explaining media gallery."""
        with ui.dialog() as dialog, ui.card().classes('p-6'):
            ui.label('Media Gallery Explained').classes('text-h6 text-primary mb-4')

            with ui.column().classes('gap-4'):
                ui.markdown('''
                **What is the Media Gallery?**

                The Media Gallery provides a visual overview of all downloaded memorial
                photos from Find a Grave, allowing you to quickly browse and inspect images.

                **Features:**

                - **Visual Grid**: Thumbnail view of all downloaded photos
                - **Photo Types**: Color-coded badges showing photo categories
                - **Quick Preview**: Click any photo to view full size
                - **Metadata**: Person name, memorial ID, and file location
                - **Direct Links**: Open Find a Grave memorial page from photo details

                **Photo Organization:**

                Photos are organized by memorial and labeled with their type:
                - Profile, Headstone, Monument, Grave, Cemetery, Document, etc.

                **Performance:**

                - Default display limit: 50 photos
                - Adjust limit: 25, 50, 100, or 200 photos
                - Higher limits may slow page rendering

                **Business Value:**

                - **Quality Check**: Visually verify downloaded images
                - **Completeness**: Identify memorials with missing photos
                - **Research Aid**: Quick visual reference during genealogy work
                - **Documentation**: Track visual evidence collection progress

                **Troubleshooting:**

                - **Broken Image Icons**: File was deleted or moved
                - **Missing Photos**: Check batch processing logs for download errors
                - **Slow Loading**: Reduce display limit or filter by session
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
