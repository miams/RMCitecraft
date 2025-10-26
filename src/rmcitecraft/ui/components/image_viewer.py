"""Census image viewer component with zoom and pan controls.

Provides an embedded image viewer for displaying census images
alongside citation editing forms.
"""

from pathlib import Path
from typing import Optional

from loguru import logger
from nicegui import ui


class CensusImageViewer:
    """Interactive image viewer with zoom and pan controls."""

    def __init__(
        self,
        image_path: Optional[Path] = None,
        initial_zoom: float = 1.0,
        max_zoom: float = 3.0,
        min_zoom: float = 0.5,
    ):
        """Initialize image viewer.

        Args:
            image_path: Path to image file to display
            initial_zoom: Initial zoom level (1.0 = 100%)
            max_zoom: Maximum zoom level (3.0 = 300%)
            min_zoom: Minimum zoom level (0.5 = 50%)
        """
        self.image_path = image_path
        self.zoom_level = initial_zoom
        self.max_zoom = max_zoom
        self.min_zoom = min_zoom

        # UI elements (set during render)
        self.image_element: Optional[ui.image] = None
        self.container: Optional[ui.element] = None
        self.scroll_container: Optional[ui.element] = None  # Plain div with overflow
        self.scroll_area_id: Optional[str] = None  # Unique ID for targeting

    def render(self) -> None:
        """Render the image viewer UI component."""
        with ui.card().classes("w-full h-full") as self.container:
            # Toolbar with controls
            with ui.row().classes("w-full items-center gap-2 p-2"):
                ui.label("Census Image").classes("text-lg font-semibold")
                ui.space()

                # Zoom controls
                ui.button(
                    icon="zoom_out",
                    on_click=self._zoom_out,
                ).props("flat dense").tooltip("Zoom Out (Ctrl -)")

                zoom_pct = int(self.zoom_level * 100)
                self.zoom_label = ui.label(f"{zoom_pct}%").classes("text-sm")

                ui.button(
                    icon="zoom_in",
                    on_click=self._zoom_in,
                ).props("flat dense").tooltip("Zoom In (Ctrl +)")

                ui.button(
                    icon="zoom_out_map",
                    on_click=self._reset_zoom,
                ).props("flat dense").tooltip("Reset Zoom (Ctrl 0)")

                ui.separator().props("vertical")

                # Preset zoom levels
                ui.button(
                    "100%",
                    on_click=lambda: self._set_zoom(1.0),
                ).props("flat dense size=sm")

                ui.button(
                    "150%",
                    on_click=lambda: self._set_zoom(1.5),
                ).props("flat dense size=sm")

                ui.button(
                    "200%",
                    on_click=lambda: self._set_zoom(2.0),
                ).props("flat dense size=sm")

                ui.button(
                    "275%",
                    on_click=lambda: self._set_zoom(2.75),
                ).props("flat dense size=sm")

                ui.separator().props("vertical")

                # Position display
                self.position_label = ui.label("").classes("text-xs text-gray-600")

            ui.separator()

            # Image container with scrolling
            # Generate unique ID for this scroll area
            import random
            self.scroll_area_id = f"census-scroll-{random.randint(1000, 9999)}"

            # Use a plain div with overflow instead of ui.scroll_area for better control
            self.scroll_container = ui.element('div').classes(f'w-full bg-gray-100 {self.scroll_area_id}').style(
                'height: 24rem; overflow: auto;'
            )
            with self.scroll_container:
                if self.image_path and self.image_path.exists():
                    # Set initial zoom by changing image width (not CSS transform)
                    # This makes the container actually scrollable
                    zoom_pct = int(self.zoom_level * 100)
                    self.image_element = ui.image(str(self.image_path)).classes(
                        "cursor-move"
                    ).style(f'width: {zoom_pct}%; height: auto; display: block; max-width: none; max-height: none;')
                else:
                    with ui.column().classes("w-full h-full items-center justify-center"):
                        ui.icon("image_not_supported", size="4rem").classes(
                            "text-gray-400"
                        )
                        ui.label("No image available").classes("text-gray-500")

            # Add timer to poll scroll position
            if self.image_path and self.image_path.exists():
                # Poll scroll position every 500ms
                ui.timer(0.5, self._update_scroll_position)

            # Pan controls (alternative to mouse drag)
            with ui.row().classes("w-full items-center justify-center gap-2 p-2"):
                ui.button(
                    icon="arrow_upward",
                    on_click=lambda: self._pan(0, -10),
                ).props("flat dense").tooltip("Pan Up")

                with ui.column().classes("gap-2"):
                    with ui.row().classes("gap-2"):
                        ui.button(
                            icon="arrow_back",
                            on_click=lambda: self._pan(-10, 0),
                        ).props("flat dense").tooltip("Pan Left")

                        ui.button(
                            icon="center_focus_strong",
                            on_click=self._reset_pan,
                        ).props("flat dense").tooltip("Center")

                        ui.button(
                            icon="arrow_forward",
                            on_click=lambda: self._pan(10, 0),
                        ).props("flat dense").tooltip("Pan Right")

                ui.button(
                    icon="arrow_downward",
                    on_click=lambda: self._pan(0, 10),
                ).props("flat dense").tooltip("Pan Down")

    def set_image(self, image_path: Path) -> None:
        """Change the displayed image.

        Args:
            image_path: Path to new image file
        """
        self.image_path = image_path
        self.zoom_level = 1.0

        if self.image_element:
            self.image_element.set_source(str(image_path))
            self._set_zoom(1.0)

    def _zoom_in(self) -> None:
        """Increase zoom level by 25%."""
        self._set_zoom(min(self.zoom_level + 0.25, self.max_zoom))

    def _zoom_out(self) -> None:
        """Decrease zoom level by 25%."""
        self._set_zoom(max(self.zoom_level - 0.25, self.min_zoom))

    def _reset_zoom(self) -> None:
        """Reset zoom to 100%."""
        self._set_zoom(1.0)

    def _set_zoom(self, level: float) -> None:
        """Set zoom to specific level.

        Args:
            level: Zoom level (1.0 = 100%, 1.5 = 150%, etc.)
        """
        self.zoom_level = max(self.min_zoom, min(level, self.max_zoom))

        # Update image size (not CSS transform) to make scroll area work
        if self.image_element:
            zoom_pct = int(self.zoom_level * 100)
            self.image_element.style(f'width: {zoom_pct}%; height: auto; display: block; max-width: none; max-height: none;')

        # Update zoom label
        zoom_pct = int(self.zoom_level * 100)
        self.zoom_label.set_text(f"{zoom_pct}%")

    def _pan(self, dx: float, dy: float) -> None:
        """Pan image by scrolling the container.

        Args:
            dx: Horizontal offset in pixels
            dy: Vertical offset in pixels
        """
        if self.scroll_container:
            self.scroll_container.run_method('scrollBy', dx, dy)

    def _reset_pan(self) -> None:
        """Reset pan to top-left."""
        if self.scroll_container:
            self.scroll_container.run_method('scrollTo', 0, 0)

    async def _update_scroll_position(self) -> None:
        """Poll and update scroll position display."""
        if not self.position_label:
            return

        try:
            # Get scroll position via JavaScript
            viewer_id = self.scroll_area_id or "unknown"
            result = await ui.run_javascript(f'''
                (() => {{
                    const scrollContainer = document.querySelector('.{viewer_id}');
                    if (scrollContainer) {{
                        return {{
                            found: true,
                            scrollLeft: Math.round(scrollContainer.scrollLeft),
                            scrollTop: Math.round(scrollContainer.scrollTop)
                        }};
                    }}
                    return {{found: false, scrollLeft: 0, scrollTop: 0}};
                }})()
            ''', timeout=2.0)

            if result and result.get('found'):
                scroll_x = result.get('scrollLeft', 0)
                scroll_y = result.get('scrollTop', 0)
                zoom_pct = int(self.zoom_level * 100)
                self.position_label.set_text(f"Zoom: {zoom_pct}% | X={scroll_x}px, Y={scroll_y}px")
            else:
                self.position_label.set_text(f"Zoom: {int(self.zoom_level * 100)}%")

        except Exception as e:
            logger.warning(f"Could not update scroll position: {e}")

    def get_position(self) -> dict:
        """Get current zoom level.

        Returns:
            Dictionary with zoom_level and zoom_percent values
        """
        return {
            "zoom_level": self.zoom_level,
            "zoom_percent": int(self.zoom_level * 100),
        }

    def position_to_area(
        self,
        x_percent: float = 0.0,
        y_percent: float = 0.0,
        zoom: float = 1.5,
        scroll_x: int = 0,
        scroll_y: int = 0,
    ) -> None:
        """Position viewport to specific area of image.

        Args:
            x_percent: Horizontal position (0.0 = left, 1.0 = right) - deprecated, use scroll_x
            y_percent: Vertical position (0.0 = top, 1.0 = bottom) - deprecated, use scroll_y
            zoom: Zoom level to apply
            scroll_x: Horizontal scroll position in pixels
            scroll_y: Vertical scroll position in pixels

        Example:
            # Position to specific scroll coordinates at 275% zoom
            viewer.position_to_area(zoom=2.75, scroll_x=500, scroll_y=50)
        """
        self._set_zoom(zoom)

        # Scroll to position if provided
        if scroll_x > 0 or scroll_y > 0:
            if self.scroll_container:
                self.scroll_container.run_method('scrollTo', scroll_x, scroll_y)
                logger.info(f"Scrolled to ({scroll_x}px, {scroll_y}px) at {zoom*100:.0f}% zoom")


def create_census_image_viewer(
    image_path: Optional[Path] = None,
    initial_zoom: float = 1.0,
) -> CensusImageViewer:
    """Factory function to create and render census image viewer.

    Args:
        image_path: Path to image file
        initial_zoom: Initial zoom level (1.0 = 100%)

    Returns:
        CensusImageViewer instance (already rendered)

    Example:
        >>> viewer = create_census_image_viewer(
        ...     image_path=Path("census.jpg"),
        ...     initial_zoom=1.5
        ... )
        >>> # Later, update image:
        >>> viewer.set_image(Path("another_census.jpg"))
        >>> # Position to top-right at 150% zoom:
        >>> viewer.position_to_area(x_percent=1.0, y_percent=0.0, zoom=1.5)
    """
    viewer = CensusImageViewer(
        image_path=image_path,
        initial_zoom=initial_zoom,
    )
    viewer.render()
    return viewer
