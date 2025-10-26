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

        # Pan offsets (percentage of image size)
        self.pan_x = 0.0
        self.pan_y = 0.0

        # UI elements (set during render)
        self.image_element: Optional[ui.image] = None
        self.container: Optional[ui.element] = None
        self.scroll_area: Optional[ui.scroll_area] = None

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
                self.position_label = ui.label("Position: Loading...").classes("text-xs text-gray-600")

            ui.separator()

            # Image container with scrolling
            self.scroll_area = ui.scroll_area().classes("w-full h-96 bg-gray-100")
            with self.scroll_area:
                if self.image_path and self.image_path.exists():
                    self.image_element = ui.image(str(self.image_path)).classes(
                        "cursor-move"
                    )
                    self._update_image_style()
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
        self.pan_x = 0.0
        self.pan_y = 0.0

        if self.image_element:
            self.image_element.set_source(str(image_path))
            self._update_image_style()

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
        self._update_image_style()

        # Update zoom label
        zoom_pct = int(self.zoom_level * 100)
        self.zoom_label.set_text(f"{zoom_pct}%")

        logger.debug(f"Zoom set to {zoom_pct}%")

    def _pan(self, dx: float, dy: float) -> None:
        """Pan image by given offset.

        Args:
            dx: Horizontal offset in pixels
            dy: Vertical offset in pixels
        """
        self.pan_x += dx
        self.pan_y += dy
        self._update_image_style()

        logger.debug(f"Pan offset: ({self.pan_x}, {self.pan_y})")

    def _reset_pan(self) -> None:
        """Reset pan to center."""
        self.pan_x = 0.0
        self.pan_y = 0.0
        self._update_image_style()

    def _update_image_style(self) -> None:
        """Update image CSS for zoom and pan."""
        if not self.image_element:
            return

        # Apply transform: scale for zoom, translate for pan
        transform = f"scale({self.zoom_level}) translate({self.pan_x}px, {self.pan_y}px)"

        self.image_element.style(
            f"transform: {transform}; transform-origin: top left; transition: transform 0.2s;"
        )

    async def _update_scroll_position(self) -> None:
        """Poll and update scroll position display."""
        if not self.position_label:
            return

        try:
            # Get scroll position via JavaScript
            result = await ui.run_javascript('''
                (() => {
                    const el = document.querySelector('.q-scrollarea__content');
                    if (el) {
                        return {
                            scrollLeft: Math.round(el.scrollLeft),
                            scrollTop: Math.round(el.scrollTop)
                        };
                    }
                    return {scrollLeft: 0, scrollTop: 0};
                })()
            ''', timeout=1.0)

            if result:
                scroll_x = result.get('scrollLeft', 0)
                scroll_y = result.get('scrollTop', 0)

                # Update label
                zoom_pct = int(self.zoom_level * 100)
                self.position_label.set_text(
                    f"Zoom: {zoom_pct}% | Scroll: X={scroll_x}px, Y={scroll_y}px"
                )
        except Exception as e:
            # Silently fail - don't spam logs
            pass

    def get_position(self) -> dict:
        """Get current zoom and pan position.

        Returns:
            Dictionary with zoom_level, pan_x, pan_y values
        """
        return {
            "zoom_level": self.zoom_level,
            "zoom_percent": int(self.zoom_level * 100),
            "pan_x": self.pan_x,
            "pan_y": self.pan_y,
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

        # If scroll positions are provided, use them directly
        if scroll_x > 0 or scroll_y > 0:
            if self.scroll_area:
                # Use NiceGUI's scroll_to method with pixel coordinates
                self.scroll_area.scroll_to(pixels_x=scroll_x, pixels_y=scroll_y)
                logger.info(f"Scrolled to ({scroll_x}px, {scroll_y}px) at {zoom*100:.0f}% zoom")
        else:
            # Legacy percentage-based positioning
            self.pan_x = -x_percent * 100
            self.pan_y = -y_percent * 100
            self._update_image_style()
            logger.info(
                f"Positioned to ({x_percent*100:.0f}%, {y_percent*100:.0f}%) at {zoom*100:.0f}% zoom"
            )


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
