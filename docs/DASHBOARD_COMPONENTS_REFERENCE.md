# Dashboard Components Reference

**Quick reference guide for Find a Grave batch operations dashboard components**

This document provides a concise catalog of all dashboard components with their data requirements and interactivity specifications.

---

## Component Catalog

### 1. Master Progress Card

**Purpose**: Track overall progress toward 5000-URL goal across all sessions

**Data Requirements**:
- `batch_items.status` (all sessions)
- Count: total, completed, failed, pending, skipped

**Interactivity**:
- None (read-only display)
- Auto-refreshes every 5 seconds

**Layout**: Full width, top of dashboard

**NiceGUI Component**: `ui.card()` with `ui.linear_progress()`

---

### 2. Session Selector Card

**Purpose**: Switch between batch sessions or view cumulative data

**Data Requirements**:
- `batch_sessions` table (all sessions)
- Session metadata: session_id, created_at, total_items, status

**Interactivity**:
- Dropdown to select session
- "All Sessions" option for cumulative view
- "Compare Sessions" button for side-by-side comparison

**Layout**: Full width, below master progress

**NiceGUI Component**: `ui.card()` with `ui.select()`

---

### 3. Status Distribution (Pie Chart)

**Purpose**: Visualize status breakdown (completed/failed/pending/skipped)

**Data Requirements**:
- `batch_items.status` (filtered by session or all)
- Count per status

**Query**:
```sql
SELECT status, COUNT(*) as count
FROM batch_items
WHERE session_id = ? OR ? IS NULL
GROUP BY status
```

**Interactivity**:
- Click slice to filter items table by status
- Hover to see exact counts
- Updates when session changes

**Layout**: Half width, left column

**NiceGUI Component**: `ui.echart()` (pie chart)

**Color Scheme**:
- Completed: Green (#4CAF50)
- Failed: Red (#F44336)
- Pending: Yellow (#FFC107)
- Skipped: Grey (#9E9E9E)

---

### 4. Processing Timeline (Line Chart)

**Purpose**: Show extraction duration over time to identify performance trends

**Data Requirements**:
- `batch_items.completed_at` (timestamp)
- `batch_items.extraction_duration_ms`
- Last 100 completed items (or configurable limit)

**Query**:
```sql
SELECT
    completed_at as timestamp,
    extraction_duration_ms,
    full_name,
    person_id
FROM batch_items
WHERE session_id = ? AND status = 'completed'
ORDER BY completed_at DESC
LIMIT 100
```

**Interactivity**:
- Zoom/pan timeline
- Hover to see person name and exact duration
- Click point to view item detail

**Layout**: Half width, right column

**NiceGUI Component**: `ui.echart()` (line chart with area fill)

---

### 5. Error Analysis (Tree Map)

**Purpose**: Visualize error distribution by type

**Data Requirements**:
- `batch_items.error_type` (failed items)
- Count per error type

**Query**:
```sql
SELECT error_type, COUNT(*) as count
FROM batch_items
WHERE session_id = ? AND status = 'failed' AND error_type IS NOT NULL
GROUP BY error_type
```

**Interactivity**:
- Click error type to filter items table
- Hover to see count
- Color coded by severity

**Layout**: One-third width

**NiceGUI Component**: `ui.echart()` (treemap)

**Color Scheme**:
- Network errors: Orange
- Extraction errors: Red
- Validation errors: Yellow
- Unknown: Grey

---

### 6. Error Scatter Plot

**Purpose**: Identify items with both long duration and errors

**Data Requirements**:
- `batch_items.extraction_duration_ms`
- `batch_items.error_message` length (as proxy for error complexity)

**Interactivity**:
- Click point to view item detail
- Zoom/pan
- Identify outliers (items with both slow extraction AND errors)

**Layout**: One-third width

**NiceGUI Component**: `ui.echart()` (scatter plot)

---

### 7. Performance Heatmap

**Purpose**: Identify bottlenecks in processing pipeline

**Data Requirements**:
- `performance_metrics` table
- Average duration by operation type (extraction, source_creation, citation_creation, etc.)

**Query**:
```sql
SELECT
    operation_type,
    AVG(duration_ms) as avg_duration,
    MIN(duration_ms) as min_duration,
    MAX(duration_ms) as max_duration
FROM performance_metrics
WHERE session_id = ?
GROUP BY operation_type
```

**Interactivity**:
- Hover to see min/max/avg durations
- Click operation to see all instances

**Layout**: One-third width

**NiceGUI Component**: `ui.echart()` (heatmap)

---

### 8. Items Table

**Purpose**: Searchable, filterable table of all batch items

**Data Requirements**:
- `batch_items` table (all fields)
- Pagination: 100 items per page

**Query**:
```sql
SELECT
    item_id,
    person_id,
    full_name,
    url,
    status,
    extraction_duration_ms,
    error_type,
    error_message,
    created_at,
    completed_at
FROM batch_items
WHERE session_id = ?
  AND (full_name LIKE ? OR person_id = ?)
  AND (status = ? OR ? = 'All')
ORDER BY item_id DESC
LIMIT 100 OFFSET ?
```

**Interactivity**:
- Text search (name, PersonID, URL)
- Filter by status dropdown
- Sort by column (click header)
- Click row to view item detail
- "Open URL" button (opens Find a Grave page)
- "View in RootsMagic" button (future: deep link)

**Layout**: Full width, central area

**NiceGUI Component**: `ui.table()` with slots

**Columns**:
1. PersonID (sortable)
2. Name (sortable)
3. Status (sortable, filterable)
4. Duration (sortable)
5. Error Type (filterable)
6. Actions (View, Open URL)

---

### 9. Item Detail Panel

**Purpose**: Deep dive into single item with RootsMagic data

**Data Requirements**:
- `batch_items` (selected item)
- RootsMagic `PersonTable`, `NameTable`, `FamilyTable` (drill-down)
- RootsMagic `CitationTable`, `SourceTable` (show created citations)

**Queries** (via `batch_dashboard_queries.py`):
- `get_person_details()` - Name, birth/death dates/places
- `get_person_families()` - Spouse and parent families
- `get_person_citations()` - All citations for person

**Interactivity**:
- Accordion sections (Person Info, Families, Citations, Error Details)
- "Open URL" button
- "View in RootsMagic" button
- "Retry" button (for failed items)

**Layout**: Right sidebar (one-third width) or modal dialog

**NiceGUI Component**: `ui.card()` with `ui.expansion()` for sections

**Sections**:
1. **Person Info**: Name, birth/death, PersonID
2. **Families**: Spouse families, parent families (from RootsMagic)
3. **Citations**: Created citations (source name, citation name)
4. **Processing Details**: Duration, timestamps, status
5. **Error Details**: Error type, message, stack trace

---

### 10. Outlier Detection Card

**Purpose**: Alert user to outliers and anomalies

**Data Requirements**:
- Statistical analysis of `extraction_duration_ms` (mean, variance, z-score)
- Pattern detection (repeated errors, missing data)

**Query** (statistical outliers):
```sql
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
    (i.extraction_duration_ms - s.mean) / SQRT(s.variance) as z_score
FROM batch_items i, stats s
WHERE i.session_id = ?
  AND ABS((i.extraction_duration_ms - s.mean) / SQRT(s.variance)) > 3.0
ORDER BY ABS((i.extraction_duration_ms - s.mean) / SQRT(s.variance)) DESC
```

**Outlier Types**:
1. **Statistical**: Extraction duration >3σ from mean
2. **Pattern**: Same error repeated >5 times
3. **Quality**: Missing expected data (no cemetery, no family)

**Interactivity**:
- Click outlier to view item detail
- "Dismiss" button (mark outlier as reviewed)
- Filter by outlier type

**Layout**: Full width, below master progress

**NiceGUI Component**: `ui.card()` with `ui.table()` (outlier list)

---

### 11. Cumulative Analytics Card

**Purpose**: Show cumulative statistics across all sessions

**Data Requirements**:
- `batch_items` (all sessions)
- Aggregate counts, averages, trends

**Metrics**:
- Total items processed (all time)
- Average extraction duration (all time)
- Success rate trend (by month)
- Most common errors (all time)

**Interactivity**:
- None (read-only display)
- Auto-refreshes every 5 seconds

**Layout**: Full width, top of cumulative section

**NiceGUI Component**: `ui.card()` with statistics grid

---

### 12. Session Comparison View

**Purpose**: Compare two sessions side-by-side

**Data Requirements**:
- `batch_sessions` (two selected sessions)
- Side-by-side metrics (status distribution, avg duration, error rates)

**Interactivity**:
- Select two sessions from dropdown
- View metrics side-by-side
- Highlight differences

**Layout**: Full width modal or dedicated section

**NiceGUI Component**: `ui.dialog()` with two-column layout

---

### 13. Export Tools

**Purpose**: Export dashboard data for external analysis

**Export Formats**:
1. **CSV**: Items table, session summary
2. **JSON**: Full batch state (items, sessions, metrics)
3. **PDF**: Dashboard snapshot with charts

**Interactivity**:
- Export buttons (CSV, JSON, PDF)
- Select what to export (current session, all sessions, filtered items)
- Download to local file

**Layout**: Top-right corner (button group)

**NiceGUI Component**: `ui.button_group()` with download handlers

---

## Data Requirements Matrix

| Component | State DB Tables | RootsMagic Tables | External Data |
|-----------|----------------|-------------------|---------------|
| Master Progress | batch_items | - | - |
| Session Selector | batch_sessions | - | - |
| Status Distribution | batch_items | - | - |
| Processing Timeline | batch_items | - | - |
| Error Analysis | batch_items | - | - |
| Error Scatter Plot | batch_items | - | - |
| Performance Heatmap | performance_metrics | - | - |
| Items Table | batch_items | - | - |
| Item Detail | batch_items | PersonTable, NameTable, FamilyTable, CitationTable, SourceTable | - |
| Outlier Detection | batch_items | - | Statistical calculations |
| Cumulative Analytics | batch_items, batch_sessions | - | - |
| Session Comparison | batch_sessions, batch_items | - | - |
| Export Tools | batch_items, batch_sessions, performance_metrics | - | File system |

---

## Interactivity Quick Reference

### Click Actions

| Component | Click Target | Action |
|-----------|-------------|---------|
| Status Distribution | Pie slice | Filter items table by status |
| Processing Timeline | Data point | View item detail |
| Error Analysis | Error type | Filter items table by error |
| Error Scatter Plot | Data point | View item detail |
| Performance Heatmap | Operation cell | Show all instances |
| Items Table | Row | View item detail in panel |
| Items Table | "Open URL" button | Open Find a Grave page in browser |
| Items Table | "View in RootsMagic" button | Open RootsMagic to PersonID (future) |
| Outlier Detection | Outlier row | View item detail |
| Session Selector | Compare button | Open session comparison view |

### Hover Actions

| Component | Hover Target | Tooltip |
|-----------|-------------|---------|
| Status Distribution | Pie slice | Status name, count, percentage |
| Processing Timeline | Data point | Person name, PersonID, duration |
| Error Analysis | Error box | Error type, count |
| Performance Heatmap | Cell | Operation, min/avg/max duration |

### Filter/Search Actions

| Component | Control | Effect |
|-----------|---------|--------|
| Session Selector | Dropdown | Filter all components by session |
| Items Table | Search input | Filter rows by name/PersonID/URL |
| Items Table | Status dropdown | Filter rows by status |
| Outlier Detection | Type dropdown | Filter outliers by type |

---

## Layout Presets

### Preset 1: Overview (Default)

**Purpose**: High-level overview for monitoring progress

**Layout**:
```
┌─────────────────────────────────────────────┐
│ Master Progress Card                         │
├─────────────────────────────────────────────┤
│ Session Selector                             │
├──────────────────────┬──────────────────────┤
│ Status Distribution  │ Processing Timeline  │
│ (Pie Chart)          │ (Line Chart)         │
├──────────────────────┴──────────────────────┤
│ Items Table                                  │
│ (Searchable/Filterable)                      │
└─────────────────────────────────────────────┘
```

**Components**: 4 components
**Best For**: Quick progress checks, monitoring running batches

---

### Preset 2: Detailed Analysis

**Purpose**: Deep dive into errors and performance

**Layout**:
```
┌──────────────┬──────────────┬──────────────┐
│ Master       │ Session      │ Outlier      │
│ Progress     │ Selector     │ Detection    │
├──────────────┼──────────────┼──────────────┤
│ Status       │ Error        │ Performance  │
│ Distribution │ Analysis     │ Heatmap      │
├──────────────┴──────────────┼──────────────┤
│ Items Table                 │ Item Detail  │
│ (Searchable)                │ Panel        │
└─────────────────────────────┴──────────────┘
```

**Components**: 7 components
**Best For**: Troubleshooting errors, identifying bottlenecks

---

### Preset 3: Monitoring

**Purpose**: Real-time monitoring with outlier alerts

**Layout**:
```
┌─────────────────────────────────────────────┐
│ Master Progress Card                         │
├─────────────────────────────────────────────┤
│ Outlier Detection (Alerts)                   │
├─────────────────────────────────────────────┤
│ Processing Timeline (Last 100 items)         │
├─────────────────────────────────────────────┤
│ Performance Heatmap                          │
├─────────────────────────────────────────────┤
│ Items Table (Recent failures)                │
└─────────────────────────────────────────────┘
```

**Components**: 5 components
**Best For**: Monitoring long-running batches, catching issues early

---

### Preset 4: Cumulative View

**Purpose**: Overview of all sessions (5000+ URLs)

**Layout**:
```
┌─────────────────────────────────────────────┐
│ Cumulative Analytics Card                    │
├──────────────────────┬──────────────────────┤
│ All Sessions         │ All Sessions         │
│ Status Distribution  │ Error Analysis       │
├──────────────────────┴──────────────────────┤
│ Items Table (All Sessions, Searchable)       │
└─────────────────────────────────────────────┘
```

**Components**: 3 components
**Best For**: Understanding overall project status, identifying global patterns

---

## Auto-Refresh Behavior

### Refresh Intervals

| Component | Default Interval | Configurable |
|-----------|-----------------|--------------|
| Master Progress | 5 seconds | Yes (5/10/30/60s) |
| Session Selector | On demand | No |
| Status Distribution | 5 seconds | Yes |
| Processing Timeline | 10 seconds | Yes |
| Error Analysis | 5 seconds | Yes |
| Items Table | 10 seconds | Yes |
| Item Detail | On demand | No |
| Outlier Detection | 30 seconds | Yes |
| Performance Heatmap | 30 seconds | Yes |

### Refresh Controls

- **Global Toggle**: Enable/disable auto-refresh for all components
- **Per-Component Toggle**: Enable/disable auto-refresh for individual components
- **Manual Refresh**: "Refresh Now" button for immediate update
- **Smart Refresh**: Pause auto-refresh when user is interacting (scrolling, hovering)

---

## Responsive Design

### Breakpoints

- **Desktop (>1200px)**: Full layout with sidebars
- **Tablet (768px-1200px)**: Stacked layout, no sidebars
- **Mobile (<768px)**: Single column, minimal components

### Mobile Optimization

**Show on Mobile**:
- Master Progress
- Session Selector
- Status Distribution
- Items Table (simplified columns)

**Hide on Mobile**:
- Performance Heatmap
- Error Scatter Plot
- Item Detail Panel (use modal instead)

---

## Color Scheme

### Status Colors

- **Completed**: Green (#4CAF50)
- **Failed**: Red (#F44336)
- **Pending**: Yellow (#FFC107)
- **Skipped**: Grey (#9E9E9E)

### Error Colors

- **Network Error**: Orange (#FF9800)
- **Extraction Error**: Red (#F44336)
- **Validation Error**: Yellow (#FFC107)
- **Unknown Error**: Grey (#9E9E9E)

### Performance Colors (Heatmap)

- **Fast (<1s)**: Green (#4CAF50)
- **Medium (1-3s)**: Yellow (#FFC107)
- **Slow (>3s)**: Orange (#FF9800)
- **Very Slow (>10s)**: Red (#F44336)

---

## Accessibility

### Keyboard Navigation

- **Tab**: Navigate between components
- **Enter**: Activate selected item
- **Arrow Keys**: Navigate table rows, chart points
- **Escape**: Close modal/dialog

### Screen Reader Support

- All charts have text alternatives (data tables)
- Form controls have labels
- Status changes announced via ARIA live regions

### High Contrast Mode

- Support system high contrast settings
- Ensure 4.5:1 contrast ratio for text
- Use patterns in addition to colors (for color blindness)

---

## Performance Optimization

### Data Volume Handling

- **Pagination**: 100 items per page in tables
- **Lazy Loading**: Load detail data only when requested
- **Debouncing**: Search input debounced 300ms
- **Caching**: Cache aggregate queries (5-second TTL)

### Chart Optimization

- **Data Sampling**: Timeline shows max 100 points, "Load More" for full history
- **Data Zoom**: Use ECharts `dataZoom` for large datasets
- **Progressive Rendering**: Render critical components first

---

## Future Enhancements

### Phase 7+

1. **Real-time Updates**: WebSocket connection for live progress
2. **Notifications**: Desktop notifications for completed batches, errors
3. **RootsMagic Deep Links**: Open RootsMagic to specific PersonID
4. **Batch Actions**: Bulk retry failed items, bulk skip items
5. **Custom Reports**: User-defined queries and visualizations
6. **Data Export Scheduling**: Automated daily/weekly exports
7. **Trend Analysis**: ML-based anomaly detection, predicted completion time

---

**Last Updated**: 2025-11-20
