"""Processing Timeline Chart component for dashboard."""

from datetime import datetime
from typing import Callable

from nicegui import ui

from rmcitecraft.database.batch_state_repository import BatchStateRepository


class ProcessingTimelineChart:
    """Processing timeline line chart showing batch item processing over time."""

    def __init__(
        self,
        state_repo: BatchStateRepository,
        session_id: str | None = None,
        limit: int = 100,
        on_point_click: Callable[[dict], None] | None = None,
    ):
        """Initialize processing timeline chart.

        Args:
            state_repo: Batch state repository
            session_id: Optional session identifier (None = all sessions)
            limit: Maximum number of items to display (default: 100)
            on_point_click: Callback when user clicks a data point (receives item data)
        """
        self._state_repo = state_repo  # Private
        self.session_id = session_id
        self.limit = limit
        self._on_point_click = on_point_click  # Private to avoid JSON serialization
        self.chart = None
        self.container = None

    def render(self) -> None:
        """Render the processing timeline chart."""
        with ui.card().classes("w-full") as self.container:
            self._render_content()

    def _render_content(self) -> None:
        """Render the content inside the container."""
        # Header
        with ui.row().classes("w-full justify-between items-center mb-4"):
            ui.label("Processing Timeline").classes("text-h6 text-primary")

            with ui.row().classes("gap-2"):
                # Limit selector
                ui.select(
                    [50, 100, 200, 500],
                    value=self.limit,
                    label="Items",
                    on_change=lambda e: self._change_limit(e.value),
                ).props("dense outlined").classes("w-24")

                ui.button("", icon="refresh", on_click=self.update).props(
                    "flat dense round"
                ).tooltip("Refresh timeline")

        # Get timeline data
        timeline_data = self._state_repo.get_processing_timeline(
            session_id=self.session_id, limit=self.limit
        )

        # If no data, show message
        if not timeline_data:
            with ui.column().classes("items-center p-8"):
                ui.icon("timeline").classes("text-6xl text-grey-5")
                ui.label("No processing history yet").classes("text-grey-7")
            return

        # Prepare data for chart (reverse to show oldest first)
        timeline_data = list(reversed(timeline_data))

        # Extract timestamps and format
        timestamps = []
        statuses = []
        person_names = []
        person_ids = []

        for item in timeline_data:
            # Parse timestamp
            timestamp_str = item["timestamp"]
            try:
                if isinstance(timestamp_str, str):
                    # Handle both ISO format and SQLite format
                    timestamp_str = timestamp_str.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(timestamp_str)
                else:
                    dt = timestamp_str

                timestamps.append(dt.strftime("%m/%d %H:%M"))
            except Exception:
                timestamps.append("N/A")

            # Map status to numeric value for visualization
            status = item.get("status", "unknown")
            status_value = {
                "completed": 1,
                "complete": 1,
                "created_citation": 1,
                "failed": 0,
                "pending": 0.5,
                "queued": 0.5,
            }.get(status, 0.5)

            statuses.append(status_value)
            person_names.append(item.get("full_name", "Unknown"))
            person_ids.append(item.get("person_id", 0))

        # Status color mapping
        def get_status_color(status_value):
            if status_value == 1:
                return "#4CAF50"  # Green for completed
            elif status_value == 0:
                return "#F44336"  # Red for failed
            else:
                return "#FFC107"  # Yellow for pending

        # Build series data with colors and tooltips
        series_data_with_tooltip = [
            {
                "value": status,
                "itemStyle": {"color": get_status_color(status)},
                "tooltip": {
                    "formatter": (
                        f"{person_names[i]}<br/>"
                        f"PersonID: {person_ids[i]}<br/>"
                        f"Time: {timestamps[i]}<br/>"
                        f"Status: {'✓ Completed' if status == 1 else '✗ Failed' if status == 0 else '⋯ Pending'}"
                    )
                },
            }
            for i, status in enumerate(statuses)
        ]

        # ECharts timeline configuration
        chart_options = {
            "tooltip": {
                "trigger": "item",  # Changed from 'axis' to 'item'
            },
            "grid": {
                "left": "3%",
                "right": "4%",
                "bottom": "3%",
                "top": "10%",
                "containLabel": True,
            },
            "xAxis": {
                "type": "category",
                "data": timestamps,
                "name": "Time",
                "nameLocation": "middle",
                "nameGap": 30,
                "axisLabel": {"rotate": 45, "fontSize": 10},
            },
            "yAxis": {
                "type": "value",
                "name": "Status",
                "min": 0,
                "max": 1,
                "axisLabel": {
                    "formatter": "{value}",  # Simple template string
                    "interval": 0,
                    "align": "center",
                },
                # Use fixed labels at y=0, 0.5, 1
                "data": [
                    {"value": 0, "textStyle": {"color": "#000"}},
                    {"value": 0.5, "textStyle": {"color": "#000"}},
                    {"value": 1, "textStyle": {"color": "#000"}},
                ],
            },
            "series": [
                {
                    "name": "Processing Status",
                    "type": "scatter",
                    "data": series_data_with_tooltip,  # Use tooltip-enhanced data
                    "symbolSize": 8,
                    "emphasis": {
                        "itemStyle": {
                            "shadowBlur": 10,
                            "shadowOffsetX": 0,
                            "shadowColor": "rgba(0, 0, 0, 0.5)",
                        }
                    },
                }
            ],
            "dataZoom": [
                {
                    "type": "slider",
                    "show": True,
                    "start": 0,
                    "end": 100,
                    "height": 20,
                    "bottom": 10,
                },
                {"type": "inside", "start": 0, "end": 100},
            ],
        }

        # Render chart
        self.chart = ui.echart(chart_options).classes("w-full h-80")

        # Summary stats
        completed_count = sum(1 for s in statuses if s == 1)
        failed_count = sum(1 for s in statuses if s == 0)
        pending_count = len(statuses) - completed_count - failed_count

        with ui.row().classes("w-full gap-4 mt-4 justify-center"):
            self._render_stat_badge("Completed", completed_count, "#4CAF50")
            self._render_stat_badge("Failed", failed_count, "#F44336")
            self._render_stat_badge("Pending", pending_count, "#FFC107")
            self._render_stat_badge("Total Shown", len(timeline_data), "#2196F3")

    def _render_stat_badge(self, label: str, value: int, color: str) -> None:
        """Render a statistics badge.

        Args:
            label: Badge label
            value: Badge value
            color: Badge color
        """
        with ui.card().classes("p-3").style(f"border-top: 3px solid {color}"):
            ui.label(str(value)).classes("text-h5 font-bold").style(f"color: {color}")
            ui.label(label).classes("text-xs text-grey-7")

    def _change_limit(self, new_limit: int) -> None:
        """Change the number of items displayed.

        Args:
            new_limit: New limit value
        """
        self.limit = new_limit
        self.update()

    def update(self, session_id: str | None = None) -> None:
        """Update the chart with new data.

        Args:
            session_id: Optional session identifier to filter by (None = all sessions)
        """
        if session_id is not None:
            self.session_id = session_id

        # Rebuild chart
        if self.container:
            self.container.clear()
            with self.container:
                self._render_content()

    def set_session_filter(self, session_id: str | None) -> None:
        """Set the session filter and update chart.

        Args:
            session_id: Session identifier or None for all sessions
        """
        self.update(session_id)
