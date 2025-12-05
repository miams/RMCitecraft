---
priority: reference
topics: [database, citation, batch, findagrave, testing]
---

# Dashboard Implementation Plan

**Technical implementation guide for Find a Grave batch operations dashboard**

This document provides technical implementation details for the dashboard design specified in `DASHBOARD_DESIGN.md`.

---

## Table of Contents

1. [File Structure](#file-structure)
2. [NiceGUI Component Mapping](#nicegui-component-mapping)
3. [State Database Enhancements](#state-database-enhancements)
4. [RootsMagic Drill-Down Queries](#rootsmagic-drill-down-queries)
5. [Auto-Refresh Strategy](#auto-refresh-strategy)
6. [Layout Persistence](#layout-persistence)
7. [Implementation Phases](#implementation-phases)

---

## File Structure

### New Files

```
src/rmcitecraft/
├── ui/
│   ├── tabs/
│   │   ├── dashboard.py                # Main dashboard tab (NEW)
│   │   └── findagrave_batch.py         # Existing batch tab
│   └── components/
│       ├── dashboard/                   # Dashboard-specific components (NEW)
│       │   ├── __init__.py
│       │   ├── master_progress.py      # Master progress card
│       │   ├── session_selector.py      # Session selector
│       │   ├── status_distribution.py   # Status pie chart
│       │   ├── processing_timeline.py   # Timeline chart
│       │   ├── error_analysis.py        # Error tree map
│       │   ├── performance_heatmap.py   # Performance heatmap
│       │   ├── items_table.py           # Searchable items table
│       │   ├── item_detail.py           # Item detail panel
│       │   ├── outlier_detection.py     # Outlier alerts
│       │   └── export_tools.py          # Export buttons
│       └── drag_layout.py               # Drag-and-drop layout manager (NEW)
└── database/
    ├── batch_dashboard_queries.py       # Dashboard-specific queries (NEW)
    └── batch_state_repository.py       # Enhanced with dashboard queries

tests/
└── unit/
    └── ui/
        └── components/
            └── dashboard/               # Dashboard component tests (NEW)
```

### Modified Files

- `src/rmcitecraft/ui/main_window.py` - Add dashboard tab to main navigation
- `src/rmcitecraft/database/batch_state_repository.py` - Add dashboard query methods

---

## NiceGUI Component Mapping

### Component Usage Patterns

All visualizations use **NiceGUI's built-in `ui.echart()`** (Apache ECharts integration, no extra dependencies).

### 1. Master Progress Card

**Component**: `ui.card()` with custom styling

```python
# src/rmcitecraft/ui/components/dashboard/master_progress.py

from nicegui import ui

class MasterProgressCard:
    def __init__(self, total_goal: int = 5000):
        self.total_goal = total_goal
        self.container = None

    def render(self):
        with ui.card().classes('w-full'):
            ui.label('Master Progress').classes('text-h6')

            # Query total completed
            completed = self._get_completed_count()
            remaining = self.total_goal - completed

            # Progress bar
            ui.linear_progress(completed / self.total_goal).props('size=30px')

            # Statistics grid
            with ui.grid(columns=4).classes('w-full gap-4 mt-4'):
                self._stat_box('Total Goal', self.total_goal, 'flag')
                self._stat_box('Completed', completed, 'check_circle', 'green')
                self._stat_box('Remaining', remaining, 'pending', 'orange')
                self._stat_box('Success Rate', f"{self._success_rate():.1f}%", 'analytics')

    def _stat_box(self, label, value, icon, color='blue'):
        with ui.card().classes(f'text-{color}'):
            with ui.row().classes('items-center'):
                ui.icon(icon).classes('text-3xl')
                with ui.column():
                    ui.label(str(value)).classes('text-h5')
                    ui.label(label).classes('text-caption')
```

### 2. Status Distribution (Pie Chart)

**Component**: `ui.echart()`

```python
# src/rmcitecraft/ui/components/dashboard/status_distribution.py

from nicegui import ui

class StatusDistributionChart:
    def __init__(self, session_id: int | None = None):
        self.session_id = session_id
        self.chart = None

    def render(self):
        with ui.card().classes('w-full'):
            ui.label('Status Distribution').classes('text-h6')

            # Get status counts
            status_data = self._get_status_counts()

            # ECharts pie chart
            self.chart = ui.echart({
                'tooltip': {'trigger': 'item'},
                'legend': {'orient': 'vertical', 'left': 'left'},
                'series': [{
                    'name': 'Status',
                    'type': 'pie',
                    'radius': '50%',
                    'data': [
                        {'value': status_data['completed'], 'name': 'Completed', 'itemStyle': {'color': '#4CAF50'}},
                        {'value': status_data['failed'], 'name': 'Failed', 'itemStyle': {'color': '#F44336'}},
                        {'value': status_data['pending'], 'name': 'Pending', 'itemStyle': {'color': '#FFC107'}},
                        {'value': status_data['skipped'], 'name': 'Skipped', 'itemStyle': {'color': '#9E9E9E'}},
                    ],
                    'emphasis': {
                        'itemStyle': {
                            'shadowBlur': 10,
                            'shadowOffsetX': 0,
                            'shadowColor': 'rgba(0, 0, 0, 0.5)'
                        }
                    }
                }]
            })
```

### 3. Processing Timeline (Line Chart)

**Component**: `ui.echart()`

```python
# src/rmcitecraft/ui/components/dashboard/processing_timeline.py

from nicegui import ui
from datetime import datetime

class ProcessingTimelineChart:
    def render(self):
        with ui.card().classes('w-full'):
            ui.label('Processing Timeline').classes('text-h6')

            # Get timeline data (extraction duration by timestamp)
            timeline_data = self._get_timeline_data()

            # Format for ECharts
            timestamps = [datetime.fromisoformat(d['timestamp']).strftime('%m/%d %H:%M')
                         for d in timeline_data]
            durations = [d['extraction_duration_ms'] / 1000 for d in timeline_data]  # Convert to seconds

            self.chart = ui.echart({
                'xAxis': {
                    'type': 'category',
                    'data': timestamps,
                    'name': 'Time'
                },
                'yAxis': {
                    'type': 'value',
                    'name': 'Extraction Duration (s)'
                },
                'series': [{
                    'data': durations,
                    'type': 'line',
                    'smooth': True,
                    'areaStyle': {'opacity': 0.3}
                }],
                'tooltip': {'trigger': 'axis'}
            })
```

### 4. Items Table (Searchable)

**Component**: `ui.table()` with search and filters

```python
# src/rmcitecraft/ui/components/dashboard/items_table.py

from nicegui import ui

class ItemsTable:
    def __init__(self, session_id: int | None = None):
        self.session_id = session_id
        self.table = None
        self.search_input = None

    def render(self):
        with ui.card().classes('w-full'):
            ui.label('Batch Items').classes('text-h6')

            # Search and filters
            with ui.row().classes('w-full gap-4 mb-4'):
                self.search_input = ui.input('Search').props('outlined dense').classes('flex-grow')
                self.search_input.on('input', self._on_search)

                # Status filter
                ui.select(
                    ['All', 'Completed', 'Failed', 'Pending', 'Skipped'],
                    value='All',
                    on_change=self._on_filter_change
                ).props('outlined dense')

            # Table
            columns = [
                {'name': 'person_id', 'label': 'PersonID', 'field': 'person_id', 'sortable': True},
                {'name': 'full_name', 'label': 'Name', 'field': 'full_name', 'sortable': True, 'align': 'left'},
                {'name': 'status', 'label': 'Status', 'field': 'status', 'sortable': True},
                {'name': 'extraction_duration_ms', 'label': 'Duration (s)', 'field': 'extraction_duration_ms', 'sortable': True},
                {'name': 'error_type', 'label': 'Error', 'field': 'error_type'},
                {'name': 'actions', 'label': 'Actions', 'field': 'actions'},
            ]

            rows = self._get_items()

            self.table = ui.table(columns=columns, rows=rows, row_key='item_id')
            self.table.add_slot('body-cell-actions', '''
                <q-td :props="props">
                    <q-btn size="sm" flat dense round icon="visibility" @click="$parent.$emit('view', props.row)" />
                    <q-btn size="sm" flat dense round icon="open_in_new" @click="$parent.$emit('open_url', props.row)" />
                </q-td>
            ''')

            # Event handlers
            self.table.on('view', self._on_view_item)
            self.table.on('open_url', self._on_open_url)
```

### 5. Error Analysis (Tree Map)

**Component**: `ui.echart()`

```python
# src/rmcitecraft/ui/components/dashboard/error_analysis.py

from nicegui import ui

class ErrorAnalysisChart:
    def render(self):
        with ui.card().classes('w-full'):
            ui.label('Error Analysis').classes('text-h6')

            # Get error distribution
            error_data = self._get_error_distribution()

            # Format for treemap
            tree_data = [
                {
                    'name': error_type,
                    'value': count,
                    'itemStyle': {'color': self._error_color(error_type)}
                }
                for error_type, count in error_data.items()
            ]

            self.chart = ui.echart({
                'series': [{
                    'type': 'treemap',
                    'data': tree_data,
                    'label': {
                        'show': True,
                        'formatter': '{b}\n{c}'
                    }
                }]
            })
```

### 6. Performance Heatmap

**Component**: `ui.echart()`

```python
# src/rmcitecraft/ui/components/dashboard/performance_heatmap.py

from nicegui import ui

class PerformanceHeatmap:
    def render(self):
        with ui.card().classes('w-full'):
            ui.label('Performance Heatmap').classes('text-h6')

            # Get performance metrics by operation type
            metrics = self._get_performance_metrics()

            # Format for heatmap
            operations = list(metrics.keys())
            data = [[i, 0, metrics[op]['avg_duration']] for i, op in enumerate(operations)]

            self.chart = ui.echart({
                'tooltip': {'position': 'top'},
                'grid': {'height': '50%', 'top': '10%'},
                'xAxis': {
                    'type': 'category',
                    'data': operations,
                    'splitArea': {'show': True}
                },
                'yAxis': {
                    'type': 'category',
                    'data': ['Duration (ms)'],
                    'splitArea': {'show': True}
                },
                'visualMap': {
                    'min': 0,
                    'max': max([m['avg_duration'] for m in metrics.values()]),
                    'calculable': True,
                    'orient': 'horizontal',
                    'left': 'center',
                    'bottom': '15%'
                },
                'series': [{
                    'name': 'Performance',
                    'type': 'heatmap',
                    'data': data,
                    'label': {'show': True},
                    'emphasis': {
                        'itemStyle': {
                            'shadowBlur': 10,
                            'shadowColor': 'rgba(0, 0, 0, 0.5)'
                        }
                    }
                }]
            })
```

---

## State Database Enhancements

### New Query Methods

Add to `src/rmcitecraft/database/batch_state_repository.py`:

```python
def get_master_progress(self) -> dict:
    """Get overall progress across all sessions."""
    with self._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                COUNT(*) as total_items,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped
            FROM batch_items
        """)
        return dict(cursor.fetchone())

def get_status_distribution(self, session_id: int | None = None) -> dict:
    """Get status distribution for specific session or all sessions."""
    with self._get_connection() as conn:
        cursor = conn.cursor()
        if session_id:
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM batch_items
                WHERE session_id = ?
                GROUP BY status
            """, (session_id,))
        else:
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM batch_items
                GROUP BY status
            """)
        return {row['status']: row['count'] for row in cursor.fetchall()}

def get_processing_timeline(self, session_id: int | None = None, limit: int = 100) -> list[dict]:
    """Get processing timeline data."""
    with self._get_connection() as conn:
        cursor = conn.cursor()
        if session_id:
            cursor.execute("""
                SELECT
                    completed_at as timestamp,
                    extraction_duration_ms,
                    full_name,
                    person_id
                FROM batch_items
                WHERE session_id = ?
                  AND status = 'completed'
                  AND completed_at IS NOT NULL
                ORDER BY completed_at DESC
                LIMIT ?
            """, (session_id, limit))
        else:
            cursor.execute("""
                SELECT
                    completed_at as timestamp,
                    extraction_duration_ms,
                    full_name,
                    person_id
                FROM batch_items
                WHERE status = 'completed'
                  AND completed_at IS NOT NULL
                ORDER BY completed_at DESC
                LIMIT ?
            """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

def get_error_distribution(self, session_id: int | None = None) -> dict:
    """Get error distribution by error type."""
    with self._get_connection() as conn:
        cursor = conn.cursor()
        if session_id:
            cursor.execute("""
                SELECT error_type, COUNT(*) as count
                FROM batch_items
                WHERE session_id = ? AND status = 'failed' AND error_type IS NOT NULL
                GROUP BY error_type
            """, (session_id,))
        else:
            cursor.execute("""
                SELECT error_type, COUNT(*) as count
                FROM batch_items
                WHERE status = 'failed' AND error_type IS NOT NULL
                GROUP BY error_type
            """)
        return {row['error_type']: row['count'] for row in cursor.fetchall()}

def get_performance_metrics(self, session_id: int | None = None) -> dict:
    """Get average performance by operation type."""
    with self._get_connection() as conn:
        cursor = conn.cursor()

        # Get metrics from performance_metrics table
        if session_id:
            cursor.execute("""
                SELECT
                    operation_type,
                    AVG(duration_ms) as avg_duration,
                    MIN(duration_ms) as min_duration,
                    MAX(duration_ms) as max_duration,
                    COUNT(*) as count
                FROM performance_metrics
                WHERE session_id = ?
                GROUP BY operation_type
            """, (session_id,))
        else:
            cursor.execute("""
                SELECT
                    operation_type,
                    AVG(duration_ms) as avg_duration,
                    MIN(duration_ms) as min_duration,
                    MAX(duration_ms) as max_duration,
                    COUNT(*) as count
                FROM performance_metrics
                GROUP BY operation_type
            """)

        return {
            row['operation_type']: {
                'avg_duration': row['avg_duration'],
                'min_duration': row['min_duration'],
                'max_duration': row['max_duration'],
                'count': row['count']
            }
            for row in cursor.fetchall()
        }

def detect_outliers(self, session_id: int | None = None, threshold_sigma: float = 3.0) -> list[dict]:
    """Detect outlier items based on statistical analysis."""
    with self._get_connection() as conn:
        cursor = conn.cursor()

        # Get items with extraction duration > 3σ from mean
        if session_id:
            cursor.execute("""
                WITH stats AS (
                    SELECT
                        AVG(extraction_duration_ms) as mean,
                        (AVG(extraction_duration_ms * extraction_duration_ms) -
                         AVG(extraction_duration_ms) * AVG(extraction_duration_ms)) as variance
                    FROM batch_items
                    WHERE session_id = ? AND status = 'completed'
                )
                SELECT
                    i.item_id,
                    i.person_id,
                    i.full_name,
                    i.extraction_duration_ms,
                    i.error_message,
                    (i.extraction_duration_ms - s.mean) / SQRT(s.variance) as z_score
                FROM batch_items i, stats s
                WHERE i.session_id = ?
                  AND ABS((i.extraction_duration_ms - s.mean) / SQRT(s.variance)) > ?
                ORDER BY ABS((i.extraction_duration_ms - s.mean) / SQRT(s.variance)) DESC
            """, (session_id, session_id, threshold_sigma))
        else:
            cursor.execute("""
                WITH stats AS (
                    SELECT
                        AVG(extraction_duration_ms) as mean,
                        (AVG(extraction_duration_ms * extraction_duration_ms) -
                         AVG(extraction_duration_ms) * AVG(extraction_duration_ms)) as variance
                    FROM batch_items
                    WHERE status = 'completed'
                )
                SELECT
                    i.item_id,
                    i.person_id,
                    i.full_name,
                    i.extraction_duration_ms,
                    i.error_message,
                    (i.extraction_duration_ms - s.mean) / SQRT(s.variance) as z_score
                FROM batch_items i, stats s
                WHERE ABS((i.extraction_duration_ms - s.mean) / SQRT(s.variance)) > ?
                ORDER BY ABS((i.extraction_duration_ms - s.mean) / SQRT(s.variance)) DESC
            """, (threshold_sigma,))

        return [dict(row) for row in cursor.fetchall()]
```

---

## RootsMagic Drill-Down Queries

### New Query File

Create `src/rmcitecraft/database/batch_dashboard_queries.py`:

```python
"""Dashboard queries that drill down into RootsMagic database."""

import sqlite3
from pathlib import Path

def get_person_details(db_path: str, person_id: int) -> dict:
    """Get person details from RootsMagic database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get person record
    cursor.execute("""
        SELECT
            p.PersonID,
            p.Sex,
            p.BirthYear,
            p.DeathYear,
            n.Surname,
            n.Given,
            n.Prefix,
            n.Suffix
        FROM PersonTable p
        LEFT JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
        WHERE p.PersonID = ?
    """, (person_id,))

    person = dict(cursor.fetchone())

    # Get birth place
    cursor.execute("""
        SELECT pl.Name as birth_place
        FROM EventTable e
        LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
        WHERE e.OwnerID = ? AND e.OwnerType = 0 AND e.EventType = 1
    """, (person_id,))
    birth_row = cursor.fetchone()
    person['birth_place'] = birth_row['birth_place'] if birth_row else None

    # Get death place
    cursor.execute("""
        SELECT pl.Name as death_place
        FROM EventTable e
        LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
        WHERE e.OwnerID = ? AND e.OwnerType = 0 AND e.EventType = 2
    """, (person_id,))
    death_row = cursor.fetchone()
    person['death_place'] = death_row['death_place'] if death_row else None

    conn.close()
    return person

def get_person_families(db_path: str, person_id: int) -> dict:
    """Get family relationships for person."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    families = {'spouse_families': [], 'parent_families': []}

    # Families where person is parent
    cursor.execute("""
        SELECT
            f.FamilyID,
            f.FatherID,
            f.MotherID,
            father.Surname as father_surname,
            father.Given as father_given,
            mother.Surname as mother_surname,
            mother.Given as mother_given
        FROM FamilyTable f
        LEFT JOIN NameTable father ON f.FatherID = father.OwnerID AND father.IsPrimary = 1
        LEFT JOIN NameTable mother ON f.MotherID = mother.OwnerID AND mother.IsPrimary = 1
        WHERE f.FatherID = ? OR f.MotherID = ?
    """, (person_id, person_id))

    families['spouse_families'] = [dict(row) for row in cursor.fetchall()]

    # Families where person is child
    cursor.execute("""
        SELECT
            f.FamilyID,
            f.FatherID,
            f.MotherID,
            father.Surname as father_surname,
            father.Given as father_given,
            mother.Surname as mother_surname,
            mother.Given as mother_given
        FROM ChildTable c
        JOIN FamilyTable f ON c.FamilyID = f.FamilyID
        LEFT JOIN NameTable father ON f.FatherID = father.OwnerID AND father.IsPrimary = 1
        LEFT JOIN NameTable mother ON f.MotherID = mother.OwnerID AND mother.IsPrimary = 1
        WHERE c.ChildID = ?
    """, (person_id,))

    families['parent_families'] = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return families

def get_person_citations(db_path: str, person_id: int) -> list[dict]:
    """Get all citations for person."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Direct person citations
    cursor.execute("""
        SELECT
            c.CitationID,
            c.CitationName,
            s.Name as source_name,
            s.SourceID,
            cl.OwnerType
        FROM CitationLinkTable cl
        JOIN CitationTable c ON cl.CitationID = c.CitationID
        JOIN SourceTable s ON c.SourceID = s.SourceID
        WHERE cl.OwnerType = 0 AND cl.OwnerID = ?
    """, (person_id,))

    citations = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return citations

def get_source_details(db_path: str, source_id: int) -> dict:
    """Get source details including citation count."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            s.SourceID,
            s.Name,
            s.TemplateID,
            COUNT(c.CitationID) as citation_count
        FROM SourceTable s
        LEFT JOIN CitationTable c ON s.SourceID = c.SourceID
        WHERE s.SourceID = ?
        GROUP BY s.SourceID
    """, (source_id,))

    source = dict(cursor.fetchone())

    conn.close()
    return source
```

---

## Auto-Refresh Strategy

### Reactive Updates with NiceGUI

NiceGUI supports reactive updates using UI bindings and timers.

```python
# src/rmcitecraft/ui/tabs/dashboard.py

from nicegui import ui
from rmcitecraft.database.batch_state_repository import BatchStateRepository

class Dashboard:
    def __init__(self, config):
        self.config = config
        self.state_repo = BatchStateRepository()
        self.auto_refresh_enabled = True
        self.refresh_interval = 5  # seconds

    def render(self):
        with ui.column().classes('w-full'):
            # Auto-refresh toggle
            with ui.row().classes('w-full justify-between mb-4'):
                ui.label('Dashboard').classes('text-h4')

                with ui.row():
                    ui.switch('Auto-refresh', value=True, on_change=self._toggle_auto_refresh)
                    ui.select(
                        [5, 10, 30, 60],
                        value=5,
                        label='Refresh interval (s)',
                        on_change=self._change_refresh_interval
                    )

            # Dashboard components
            self.master_progress = MasterProgressCard()
            self.status_chart = StatusDistributionChart()
            # ... other components

            # Start auto-refresh timer
            self.refresh_timer = ui.timer(self.refresh_interval, self._refresh_all_components)

    def _refresh_all_components(self):
        """Refresh all dashboard components."""
        if not self.auto_refresh_enabled:
            return

        # Update each component
        self.master_progress.update()
        self.status_chart.update()
        # ... other components

    def _toggle_auto_refresh(self, e):
        self.auto_refresh_enabled = e.value
        if e.value:
            self.refresh_timer.activate()
        else:
            self.refresh_timer.deactivate()

    def _change_refresh_interval(self, e):
        self.refresh_interval = e.value
        self.refresh_timer.interval = e.value
```

### Manual Refresh Button

Add manual refresh button for immediate updates:

```python
with ui.row():
    ui.button('Refresh Now', icon='refresh', on_click=self._refresh_all_components)
```

---

## Layout Persistence

### Drag-and-Drop Layout System

Use NiceGUI's grid system with local storage for layout persistence.

```python
# src/rmcitecraft/ui/components/drag_layout.py

from nicegui import ui
import json

class DragLayout:
    """Configurable drag-and-drop layout manager with persistence."""

    def __init__(self, layout_key: str = 'dashboard_layout'):
        self.layout_key = layout_key
        self.components = {}
        self.grid = None

    def add_component(self, component_id: str, component, row: int, col: int, width: int = 1, height: int = 1):
        """Register a component with initial position."""
        self.components[component_id] = {
            'component': component,
            'row': row,
            'col': col,
            'width': width,
            'height': height
        }

    def render(self):
        """Render grid with components in saved or default positions."""
        # Load saved layout from local storage
        layout = self._load_layout()

        # Create responsive grid
        with ui.grid(columns=12).classes('w-full gap-4') as self.grid:
            for component_id, config in self.components.items():
                # Get saved position or use default
                position = layout.get(component_id, {
                    'row': config['row'],
                    'col': config['col'],
                    'width': config['width'],
                    'height': config['height']
                })

                # Render component with drag handle
                with ui.column().classes(f'col-span-{position["width"]}'):
                    with ui.card().classes('w-full'):
                        # Drag handle
                        with ui.row().classes('w-full justify-between cursor-move bg-grey-2 p-2').on('dragstart', lambda e, cid=component_id: self._on_drag_start(e, cid)):
                            ui.icon('drag_indicator')
                            ui.button('', icon='close', on_click=lambda cid=component_id: self._remove_component(cid)).props('flat dense')

                        # Component content
                        config['component'].render()

        # Save button
        ui.button('Save Layout', icon='save', on_click=self._save_layout)
        ui.button('Reset Layout', icon='restore', on_click=self._reset_layout)

    def _load_layout(self) -> dict:
        """Load layout from local storage."""
        # In NiceGUI, use app.storage.user for persistence
        from nicegui import app
        layout_json = app.storage.user.get(self.layout_key, '{}')
        return json.loads(layout_json)

    def _save_layout(self):
        """Save current layout to local storage."""
        from nicegui import app
        layout = {
            cid: {
                'row': config['row'],
                'col': config['col'],
                'width': config['width'],
                'height': config['height']
            }
            for cid, config in self.components.items()
        }
        app.storage.user[self.layout_key] = json.dumps(layout)
        ui.notify('Layout saved', type='positive')

    def _reset_layout(self):
        """Reset to default layout."""
        from nicegui import app
        app.storage.user[self.layout_key] = '{}'
        ui.notify('Layout reset. Refresh page to apply.', type='warning')

    def _remove_component(self, component_id: str):
        """Remove component from layout."""
        if component_id in self.components:
            del self.components[component_id]
            ui.notify(f'Removed {component_id}. Save layout to persist.', type='info')
```

### Layout Presets

Provide predefined layouts for common use cases:

```python
LAYOUT_PRESETS = {
    'overview': {
        'master_progress': {'row': 0, 'col': 0, 'width': 12, 'height': 1},
        'status_distribution': {'row': 1, 'col': 0, 'width': 6, 'height': 2},
        'processing_timeline': {'row': 1, 'col': 6, 'width': 6, 'height': 2},
        'items_table': {'row': 3, 'col': 0, 'width': 12, 'height': 3},
    },
    'detailed': {
        'master_progress': {'row': 0, 'col': 0, 'width': 6, 'height': 1},
        'session_selector': {'row': 0, 'col': 6, 'width': 6, 'height': 1},
        'status_distribution': {'row': 1, 'col': 0, 'width': 4, 'height': 2},
        'error_analysis': {'row': 1, 'col': 4, 'width': 4, 'height': 2},
        'performance_heatmap': {'row': 1, 'col': 8, 'width': 4, 'height': 2},
        'items_table': {'row': 3, 'col': 0, 'width': 8, 'height': 3},
        'item_detail': {'row': 3, 'col': 8, 'width': 4, 'height': 3},
    },
    'monitoring': {
        'master_progress': {'row': 0, 'col': 0, 'width': 12, 'height': 1},
        'processing_timeline': {'row': 1, 'col': 0, 'width': 12, 'height': 2},
        'outlier_detection': {'row': 3, 'col': 0, 'width': 12, 'height': 2},
        'performance_heatmap': {'row': 5, 'col': 0, 'width': 12, 'height': 2},
    }
}
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1)

**Goal**: Basic dashboard with master progress and session selector

**Tasks**:
1. Create dashboard tab in main navigation
2. Implement `MasterProgressCard` component
3. Implement `SessionSelectorCard` component
4. Add `get_master_progress()` to state repository
5. Add basic auto-refresh mechanism
6. Write unit tests for components

**Deliverables**:
- Dashboard tab accessible from main window
- Master progress card showing total/completed/remaining
- Session selector for switching between batches
- 5-second auto-refresh

---

### Phase 2: Status & Timeline (Week 2)

**Goal**: Visualize status distribution and processing timeline

**Tasks**:
1. Implement `StatusDistributionChart` (pie chart)
2. Implement `ProcessingTimelineChart` (line chart)
3. Add `get_status_distribution()` to state repository
4. Add `get_processing_timeline()` to state repository
5. Integrate charts with session selector (filter by session)
6. Write unit tests

**Deliverables**:
- Status pie chart (completed/failed/pending/skipped)
- Processing timeline showing extraction duration over time
- Charts update when session changes

---

### Phase 3: Items Table & Detail (Week 3)

**Goal**: Searchable items table with drill-down to RootsMagic data

**Tasks**:
1. Implement `ItemsTable` component with search/filter
2. Implement `ItemDetailPanel` component
3. Create `batch_dashboard_queries.py` with RootsMagic queries
4. Add drill-down queries (person details, families, citations)
5. Add "View in RootsMagic" button (open RootsMagic to PersonID)
6. Write unit tests

**Deliverables**:
- Searchable/filterable items table
- Item detail panel showing RootsMagic data (name, dates, families, citations)
- Click item to view details
- Export table to CSV

---

### Phase 4: Error Analysis (Week 4)

**Goal**: Visualize errors and identify patterns

**Tasks**:
1. Implement `ErrorAnalysisChart` (tree map)
2. Implement error scatter plot (duration vs error count)
3. Add `get_error_distribution()` to state repository
4. Add error pattern detection algorithm
5. Add "View Error Details" drill-down
6. Write unit tests

**Deliverables**:
- Error tree map showing error type distribution
- Error scatter plot showing which items have errors
- Click error to see affected items

---

### Phase 5: Performance & Outliers (Week 5)

**Goal**: Performance monitoring and outlier detection

**Tasks**:
1. Implement `PerformanceHeatmap` component
2. Implement `OutlierDetectionCard` component
3. Add `get_performance_metrics()` to state repository
4. Add `detect_outliers()` with statistical analysis
5. Add outlier alert system (notifications)
6. Write unit tests

**Deliverables**:
- Performance heatmap showing operation durations
- Outlier detection card with alerts
- Statistical analysis (>3σ from mean)
- Pattern detection (repeated errors)

---

### Phase 6: Advanced Features (Week 6)

**Goal**: Layout customization and export tools

**Tasks**:
1. Implement `DragLayout` component
2. Add layout persistence (local storage)
3. Add layout presets (overview, detailed, monitoring)
4. Implement export tools (CSV, JSON, PDF)
5. Add cumulative analytics across all sessions
6. Write comprehensive integration tests

**Deliverables**:
- Drag-and-drop layout customization
- Layout persistence across sessions
- 3 predefined layout presets
- Export dashboard data to CSV/JSON/PDF
- Cumulative analytics (all sessions combined)

---

## Testing Strategy

### Unit Tests

Each component should have unit tests covering:
- Data fetching (mocked state repository)
- Rendering (component structure)
- User interactions (clicks, searches, filters)
- Edge cases (empty data, errors)

```python
# tests/unit/ui/components/dashboard/test_master_progress.py

def test_master_progress_card_renders(mocker):
    """Test that master progress card renders with correct data."""
    mock_repo = mocker.Mock()
    mock_repo.get_master_progress.return_value = {
        'total_items': 5000,
        'completed': 1234,
        'failed': 56,
        'pending': 3710,
        'skipped': 0
    }

    card = MasterProgressCard(state_repo=mock_repo)
    # Assert card contains expected elements

def test_master_progress_card_calculates_success_rate(mocker):
    """Test success rate calculation."""
    mock_repo = mocker.Mock()
    mock_repo.get_master_progress.return_value = {
        'completed': 80,
        'failed': 20
    }

    card = MasterProgressCard(state_repo=mock_repo)
    assert card.success_rate() == 80.0  # 80/(80+20)
```

### Integration Tests

Test dashboard integration with real state database:

```python
# tests/integration/ui/test_dashboard_integration.py

def test_dashboard_loads_with_real_data(test_db_path):
    """Test dashboard loads successfully with real batch state data."""
    # Create test batch session with items
    # Render dashboard
    # Assert all components visible
```

---

## Performance Considerations

### Data Volume

With 5000+ items, optimize queries:

1. **Pagination**: Limit table results to 100 items per page
2. **Lazy Loading**: Load detail data only when requested
3. **Caching**: Cache aggregate queries (refresh every 5 seconds)
4. **Indexing**: Ensure state DB has indexes on `session_id`, `status`, `person_id`

### Chart Performance

ECharts can handle large datasets efficiently:
- Use `dataZoom` for timeline charts (allows zooming/panning)
- Limit initial render to 100-200 data points
- Provide "Load More" button for full history

---

## Next Steps

1. Review implementation plan with user
2. Create Phase 1 branch: `feat/dashboard-phase1`
3. Implement foundation components
4. Write tests for Phase 1
5. Get user feedback on UI/UX
6. Iterate through remaining phases

---

**Last Updated**: 2025-11-20
