# Find a Grave Batch Operations Dashboard - Design Specification

**Version**: 1.0
**Date**: 2025-11-19
**Status**: Design Phase

## Executive Summary

This document specifies a comprehensive, interactive dashboard for monitoring Find a Grave batch processing operations in RMCitecraft. The dashboard addresses the need to track progress across 5000+ memorial URLs processed over weeks or months, with deep drill-down capabilities and outlier detection.

### Key Objectives

1. **Situational Awareness**: Understand overall progress toward 5000-item goal
2. **Outlier Detection**: Identify processing anomalies, errors, and performance bottlenecks
3. **Drill-Down Analysis**: Navigate from high-level metrics to individual item details
4. **Configurable Layout**: User-customizable dashboard components and arrangement
5. **Actionable Insights**: Surface issues requiring immediate attention

---

## Architecture Overview

### Data Sources

1. **State Database** (`~/.rmcitecraft/batch_state.db`)
   - Primary source for session, item, and metrics data
   - Tables: `batch_sessions`, `batch_items`, `batch_checkpoints`, `performance_metrics`

2. **RootsMagic Database** (user's `.rmtree` file)
   - Drill-down queries for citation details, family relationships
   - Verification of data quality (orphaned citations, missing links)

### Dashboard Structure

```
┌─────────────────────────────────────────────────────────────┐
│  SECTION 1: Global Overview (Always Pinned)                │
│  - Master Progress | Active Sessions | Health Indicators   │
├─────────────────────────────────────────────────────────────┤
│  SECTION 2: Session Analytics (Tabbed View)                │
│  - Session Selector | Performance Charts | Error Analysis  │
├─────────────────────────────────────────────────────────────┤
│  SECTION 3: Item-Level Details (Drill-Down Table)          │
│  - Searchable Items Table | Item Detail Slide-Out Panel    │
├─────────────────────────────────────────────────────────────┤
│  SECTION 4: Cumulative Analytics (Historical View)         │
│  - Progress Over Time | Quality Metrics | Comparisons      │
├─────────────────────────────────────────────────────────────┤
│  SECTION 5: Outlier & Anomaly Detection                    │
│  - Automated Alerts | Manual Investigation Tools           │
├─────────────────────────────────────────────────────────────┤
│  SECTION 6: Administrative Tools                           │
│  - Batch Management | Export/Reporting | Settings          │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Specifications

## SECTION 1: Global Overview

### 1.1 Master Progress Card

**Objective**: Track cumulative progress toward 5000-item goal across all sessions

**Data Source**:
```python
# Aggregate from all sessions
SELECT
    SUM(completed_items) as total_completed,
    COUNT(DISTINCT session_id) as total_sessions
FROM batch_sessions
```

**Metrics Displayed**:
- Total items processed: `4,237 / 5,000` (84.7%)
- Items processed last 7 days: `215`
- Items processed last 30 days: `892`
- Estimated completion date: `Jan 15, 2026` (based on recent velocity)
- Total errors (lifetime): `143` (2.9%)

**Visualization**:
- **Primary**: Large circular progress gauge (0-100%)
  - Color: Green (>80%), Yellow (50-80%), Red (<50%)
  - Center text: Completion percentage
- **Secondary**: Sparkline showing daily completion rate (last 30 days)

**Interactivity**:
- Click gauge → Open session filter dialog
- Click sparkline → Zoom to daily breakdown chart

**Layout**: Full-width card, fixed at top, 200px height

---

### 1.2 Active Sessions Summary

**Objective**: Quick visibility into currently running or suspended sessions

**Data Source**:
```python
SELECT * FROM batch_sessions
WHERE status IN ('active', 'suspended')
ORDER BY updated_at DESC
```

**Metrics Per Session**:
- Session name
- Status badge (Active: pulsing green, Suspended: orange)
- Progress: `45 / 100` items (45%)
- Last updated: `5 minutes ago`

**Visualization**:
- Compact horizontal cards (max 3 visible, scroll for more)
- Status icon with animation (pulsing for active)

**Interactivity**:
- Click card → Load session in Session Analytics section
- Hover → Show session tooltip (start time, error count)
- Resume button on suspended sessions

**Layout**: Row of cards below Master Progress, auto-hide if no active/suspended sessions

---

### 1.3 Health Indicators

**Objective**: At-a-glance system health across all operations

**Data Source**:
```python
# Error rate last 24h
SELECT
    COUNT(*) FILTER (WHERE success = 0) * 100.0 / COUNT(*) as error_rate
FROM performance_metrics
WHERE created_at > datetime('now', '-24 hours')

# Average extraction time (last 100 items)
SELECT AVG(duration_ms) as avg_extraction
FROM performance_metrics
WHERE operation = 'extraction'
ORDER BY created_at DESC
LIMIT 100
```

**Indicators**:

1. **Error Rate** (Last 24h)
   - Green: <5%
   - Yellow: 5-10%
   - Red: >10%

2. **Avg Extraction Time** (Last 100 items)
   - Green: <3000ms
   - Yellow: 3000-5000ms
   - Red: >5000ms

3. **Retry Rate** (Items requiring retries)
   - Green: <10%
   - Yellow: 10-20%
   - Red: >20%

4. **Browser Health**
   - Green: No timeouts in last hour
   - Yellow: 1-3 timeouts
   - Red: >3 timeouts

**Visualization**:
- 4 circular traffic lights (green/yellow/red)
- Value displayed in center of each circle
- Trend arrow (↑ improving, ↓ degrading, → stable)

**Interactivity**:
- Click any indicator → Open detailed health report dialog
- Hover → Show calculation details

**Layout**: 4-column grid, compact (100px height per indicator)

---

## SECTION 2: Session Analytics

### 2.1 Session Selector & Comparison

**Objective**: Switch between sessions or compare multiple sessions side-by-side

**Data Source**:
```python
SELECT session_id, session_name, created_at, status,
       total_items, completed_items
FROM batch_sessions
ORDER BY created_at DESC
```

**Features**:
- **Single Session Mode**: Dropdown selector
  - Shows: Session name, date, progress
  - Default: Most recent session
- **Comparison Mode**: Multi-select (up to 3 sessions)
  - Charts show overlaid data for comparison
- **Date Range Filter**: Filter sessions by creation date

**Visualization**:
- Horizontal timeline showing all sessions
- Each session = vertical bar at its date
- Bar height = completion percentage
- Bar color = status (green/orange/red)

**Interactivity**:
- Click timeline bar → Select session
- Shift+click → Add to comparison
- Drag timeline → Pan to different date range
- Scroll → Zoom timeline

**Layout**: Full-width below Global Overview, 150px height

---

### 2.2 Session Performance Dashboard

**Objective**: Deep dive into selected session's performance metrics

#### 2.2A Status Distribution (Pie Chart)

**Data Source**:
```python
SELECT status, COUNT(*) as count
FROM batch_items
WHERE session_id = ?
GROUP BY status
```

**Visualization**: Pie chart (ECharts)
- Slices: Complete (green), Failed (red), Pending (gray), Skipped (orange)
- Labels: Count + percentage
- Donut style with center showing total count

**Interactivity**:
- Click slice → Filter items table to that status
- Hover → Highlight corresponding rows in table

**Layout**: 1/3 width, 300px height

---

#### 2.2B Processing Timeline (Line Chart)

**Data Source**:
```python
SELECT
    bi.person_name,
    pm.duration_ms,
    pm.operation,
    bi.retry_count
FROM batch_items bi
JOIN performance_metrics pm ON pm.session_id = bi.session_id
WHERE bi.session_id = ?
ORDER BY bi.created_at
```

**Visualization**: Multi-series line chart (ECharts)
- X-axis: Item index (1-100)
- Y-axis: Duration (ms)
- Series:
  - Extraction time (blue line)
  - Citation creation time (green line)
  - Image download time (purple line)
- Error markers: Red dots at item index where errors occurred
- Outlier highlighting: Yellow background for items >3σ from mean

**Interactivity**:
- Hover point → Tooltip with person name, exact duration
- Click point → Open item detail panel
- Zoom: Drag to select range
- Legend click → Toggle series visibility

**Layout**: 2/3 width, 400px height

---

#### 2.2C Retry Analysis (Horizontal Bar Chart)

**Data Source**:
```python
SELECT retry_count, COUNT(*) as count
FROM batch_items
WHERE session_id = ?
GROUP BY retry_count
ORDER BY retry_count
```

**Visualization**: Horizontal bar chart (ECharts)
- Y-axis: Retry count (0, 1, 2, 3, 4+)
- X-axis: Number of items
- Bar color gradient: Green (0 retries) → Red (4+ retries)

**Interactivity**:
- Click bar → Filter items table to that retry count
- Hover → Show percentage of total

**Layout**: 1/2 width, 300px height

---

#### 2.2D Hourly Throughput (Bar Chart)

**Data Source**:
```python
SELECT
    strftime('%H', completed_at) as hour,
    COUNT(*) as items_completed
FROM batch_items
WHERE session_id = ? AND status = 'completed'
GROUP BY hour
ORDER BY hour
```

**Visualization**: Vertical bar chart (ECharts)
- X-axis: Hour of day (0-23)
- Y-axis: Items completed
- Bar color: Time-of-day gradient (night=dark, day=light)

**Insight**: Identify optimal processing times (browser performance patterns)

**Interactivity**:
- Hover → Show exact count + peak indicator
- Click bar → Show items completed in that hour

**Layout**: 1/2 width, 300px height

---

### 2.3 Error Analysis

#### 2.3A Error Type Breakdown (Tree Map)

**Data Source**:
```python
SELECT
    CASE
        WHEN error_message LIKE '%timeout%' THEN 'Timeout'
        WHEN error_message LIKE '%extraction%' THEN 'Extraction Failed'
        WHEN error_message LIKE '%citation%' THEN 'Citation Creation Failed'
        WHEN error_message LIKE '%duplicate%' THEN 'Duplicate Detected'
        ELSE 'Other'
    END as error_category,
    COUNT(*) as count
FROM batch_items
WHERE session_id = ? AND status = 'failed'
GROUP BY error_category
```

**Visualization**: Tree map (ECharts)
- Rectangle size: Proportional to error frequency
- Rectangle color: Error severity (red shades)
- Label: Category name + count

**Interactivity**:
- Click rectangle → Filter error details table
- Hover → Show percentage of total errors

**Layout**: 1/2 width, 350px height

---

#### 2.3B Error Timeline (Scatter Plot)

**Data Source**:
```python
SELECT
    created_at,
    error_message,
    retry_count,
    person_name
FROM batch_items
WHERE session_id = ? AND status = 'failed'
ORDER BY created_at
```

**Visualization**: Scatter plot (ECharts)
- X-axis: Time (batch processing timeline)
- Y-axis: Error category (categorical axis)
- Point size: Retry count
- Point color: By error category

**Pattern Detection**: Clusters suggest systemic issues (e.g., all timeouts in 2-hour window)

**Interactivity**:
- Click point → Item detail panel
- Lasso select → Bulk actions (retry all selected)
- Hover → Tooltip with person name, error message

**Layout**: 1/2 width, 350px height

---

### 2.4 Performance Heatmap

**Objective**: Identify performance bottlenecks by operation and time

**Data Source**:
```python
SELECT
    operation,
    strftime('%H', created_at) as hour,
    AVG(duration_ms) as avg_duration
FROM performance_metrics
WHERE session_id = ?
GROUP BY operation, hour
```

**Visualization**: Heatmap (ECharts)
- Rows: Operation type (extraction, citation_creation, image_download)
- Columns: Hour of day or batch position percentiles (0-10%, 10-20%, ...)
- Cell color: Duration (green=fast <2s, yellow=medium 2-5s, red=slow >5s)

**Outlier Detection**: Red cells highlight slow operations requiring investigation

**Interactivity**:
- Click cell → Filter items table to that operation + time bucket
- Hover → Show exact average duration + item count

**Layout**: Full width, 250px height

---

## SECTION 3: Item-Level Details

### 3.1 Searchable Items Table

**Objective**: Find and analyze individual batch items

**Data Source**:
```python
SELECT
    bi.person_id,
    bi.person_name,
    bi.status,
    bi.retry_count,
    bi.error_message,
    bi.memorial_url,
    pm_extract.duration_ms as extraction_time,
    COUNT(fam.citation_id) as family_link_count,
    json_array_length(bi.downloaded_image_paths) as image_count
FROM batch_items bi
LEFT JOIN performance_metrics pm_extract
    ON pm_extract.session_id = bi.session_id
    AND pm_extract.operation = 'extraction'
LEFT JOIN CitationLinkTable fam
    ON fam.OwnerType = 1  -- Family links
WHERE bi.session_id = ?
```

**Columns**:
1. **Person Name** (sortable, clickable)
   - Links to person detail panel
2. **PersonID** (sortable)
3. **Status** (filterable dropdown)
   - Icon: ✓ (complete), ✗ (failed), ⌛ (pending), ⊘ (skipped)
4. **Extraction Time** (sortable, ms)
   - Color-coded: Green (<3s), Yellow (3-5s), Red (>5s)
5. **Retry Count** (sortable)
   - Badge if >0
6. **Error Message** (searchable, truncated)
   - Hover for full message
   - Click to expand
7. **Family Links** (sortable)
   - Count of family citations created
8. **Images** (sortable)
   - Count of downloaded images
9. **Actions**
   - Re-run button (if failed)
   - View Details button
   - Delete button (with confirmation)

**Features**:
- **Full-text search**: Person name, error message
- **Multi-column sort**: Shift+click for secondary sort
- **Filters**:
  - Status (dropdown multi-select)
  - Retry count (slider: 0-5+)
  - Has errors (checkbox)
  - Has images (checkbox)
  - Extraction time range (slider)
- **Bulk actions**:
  - Select multiple rows (checkbox)
  - Retry all selected
  - Export selected to CSV
- **Pagination**: 50 items per page (configurable: 25/50/100)
- **Export**: CSV download (all columns + full error messages)

**Visualization**: NiceGUI `ui.table()` with custom styling

**Layout**: Full width, variable height (min 400px, max 800px with scroll)

---

### 3.2 Item Detail Panel (Slide-Out Drawer)

**Objective**: Comprehensive view of a single item's processing history and results

**Triggered**: Click row in items table

**Panel Structure**: Right-side drawer (800px width), full height, scrollable

#### Section A: Person Info
- **Display**:
  - Person Name (large header)
  - PersonID, Birth Year, Death Year
  - Memorial URL (clickable button → opens in new tab)
  - Find a Grave Memorial ID

#### Section B: Processing History Timeline
- **Visualization**: Vertical timeline (stepper component)
- **Stages**:
  1. ⏱ **Queued**: Timestamp when added to batch
  2. 🌐 **Page Load**: Duration, success/failure
  3. 📄 **Extraction**: Duration, retry count
  4. 📝 **Citation Creation**: Duration, SourceID, CitationID created
  5. 🖼 **Images Downloaded**: Count, total duration
  6. ✅ **Complete**: Final timestamp

- **Each stage shows**:
  - Timestamp
  - Duration (if applicable)
  - Status icon (✓/✗)
  - Error message (if failed)
  - Retry indicators (attempt 1/3, 2/3, etc.)

#### Section C: Citation Details
- **Query RootsMagic**:
```python
SELECT s.SourceID, c.CitationID, s.Name as source_name
FROM SourceTable s
JOIN CitationTable c ON s.SourceID = c.SourceID
WHERE s.Name LIKE '%{person_name}%'
```

- **Display**:
  - SourceID: `7477`
  - CitationID: `14259`
  - Source Name: `Find a Grave: Iams, John (1834-1900) RIN 719`
  - **Formatted Citations** (expandable):
    - Footnote (formatted, line-wrapped)
    - Short Footnote
    - Bibliography

#### Section D: Family Linkage Analysis
- **Query**:
```python
# Families where person is PARENT
SELECT f.FamilyID, f.FatherID, f.MotherID
FROM FamilyTable f
WHERE f.FatherID = ? OR f.MotherID = ?

# Families where person is CHILD
SELECT f.FamilyID, f.FatherID, f.MotherID
FROM FamilyTable f
JOIN ChildTable c ON f.FamilyID = c.FamilyID
WHERE c.ChildID = ?
```

- **Display**: Expandable sections
  - **Parent Families** (where person is parent):
    - Family ID: `2069`
    - Spouse: Alice Jane Kimball (PersonID 5924)
    - Citation Link: ✓ Created (spouse mentioned in biography)
  - **Child Families** (where person is child):
    - Family ID: `270`
    - Parents: Rezin Iames + Eleanor Riley
    - Citation Link: ✓ Created (parents mentioned in biography)

- **Link Status Logic**:
  - ✓ Green checkmark: Citation link created
  - ✗ Red X: Citation link NOT created
  - Reason: "(spouse not mentioned)" or "(parents not mentioned)"

#### Section E: Downloaded Images
- **Display**: Thumbnail grid (3 columns)
  - Each thumbnail: 150px × 150px
  - Image type badge: Person / Grave / Family / Cemetery
  - File path (truncated, hover for full)
  - Click thumbnail → Open full-size lightbox

- **If no images**: Gray placeholder with "No images downloaded"

#### Section F: Error Details (if status = 'failed')
- **Display**:
  - Error Type (bold): `TimeoutError`
  - Full Error Message (monospace font, scrollable)
  - Stack Trace (collapsible accordion)
  - **Suggested Fix** (AI-generated based on error pattern):
    - "Timeout errors often resolve with retry. Click Retry button below."
  - **Action Buttons**:
    - Retry Now (green button)
    - Mark as Reviewed (dismiss from outliers)

**Footer Actions**:
- Close button
- Re-run Item button (if failed/incomplete)
- Delete Item button (with confirmation)

**Layout**: Slide-out from right edge, 800px width, overlay with semi-transparent backdrop

---

## SECTION 4: Cumulative Analytics

### 4.1 Progress Over Time (Area Chart)

**Objective**: Visualize cumulative progress toward 5000-goal with forecasting

**Data Source**:
```python
SELECT
    DATE(completed_at) as date,
    COUNT(*) as items_completed
FROM batch_items
WHERE status = 'completed'
GROUP BY DATE(completed_at)
ORDER BY date
```

**Visualization**: Area chart (ECharts)
- X-axis: Date (daily granularity)
- Y-axis: Cumulative items completed
- **Series**:
  1. Actual progress (solid blue area)
  2. Goal line at 5,000 (dashed red horizontal line)
  3. Forecast (dotted gray line, linear regression from last 30 days)

**Metrics Overlay** (top-right corner):
- Current velocity: `23.5 items/day` (average last 30 days)
- Estimated completion date: `Jan 15, 2026`
- Days remaining: `57 days`

**Interactivity**:
- Hover date → Tooltip showing daily count
- Click date range → Zoom to that period
- Toggle forecast visibility (checkbox)

**Layout**: Full width, 350px height

---

### 4.2 Quality Metrics Dashboard

**Objective**: Monitor data quality and completeness over time

#### 4.2A Citation Completeness Gauge

**Data Source**:
```python
# Items with all 3 citation forms
SELECT COUNT(*) * 100.0 / (SELECT COUNT(*) FROM batch_items WHERE status = 'completed')
FROM batch_items bi
JOIN CitationTable c ON ...
WHERE c.Footnote IS NOT NULL
  AND c.ShortFootnote IS NOT NULL
  AND c.Bibliography IS NOT NULL
```

**Visualization**: Semi-circular gauge (ECharts)
- Value: `94.2%` (items with complete citations)
- Color: Green (>95%), Yellow (90-95%), Red (<90%)

**Sub-Metrics**:
- % with family links: `87.3%`
- % with images: `76.4%`

**Layout**: 1/3 width, 200px height

---

#### 4.2B Data Quality Alerts

**Objective**: Surface data quality issues requiring attention

**Queries**:
```python
# Missing cemetery names
SELECT COUNT(*) FROM batch_items
WHERE status = 'completed'
  AND json_extract(extracted_data, '$.cemeteryName') IS NULL

# Orphaned citations (no links)
SELECT COUNT(*) FROM CitationTable c
LEFT JOIN CitationLinkTable cl ON c.CitationID = cl.CitationID
WHERE cl.LinkID IS NULL

# Duplicate memorial IDs
SELECT memorial_id, COUNT(*)
FROM batch_items
GROUP BY memorial_id
HAVING COUNT(*) > 1
```

**Display**: Alert cards (stacked vertically)
- **Card 1**: Missing Cemetery Names
  - Count: `12 items`
  - Severity: Warning (orange)
  - Action: "Review Items" button

- **Card 2**: Orphaned Citations
  - Count: `3 citations`
  - Severity: Error (red)
  - Action: "Investigate" button

- **Card 3**: Duplicate Detections
  - Count: `5 duplicates`
  - Severity: Warning (orange)
  - Action: "Review Duplicates" button

**Interactivity**: Click card → Open filtered items table

**Layout**: 2/3 width, variable height (auto-stack cards)

---

### 4.3 Session Comparison Matrix

**Objective**: Compare multiple sessions side-by-side

**Data Source**:
```python
SELECT
    session_name,
    created_at,
    total_items,
    completed_items,
    failed_items,
    AVG(extraction_time) as avg_extraction,
    error_rate
FROM batch_sessions
WHERE session_id IN (selected_session_ids)
```

**Visualization**: Comparison table

**Columns**:
- Session Name
- Date
- Total Items
- Completion Rate (% with progress bar)
- Avg Extraction Time (ms, color-coded)
- Error Rate (%, color-coded)
- Retry Rate (%)

**Features**:
- Sortable columns
- Highlight best value (green background)
- Highlight worst value (red background)
- Export to CSV

**Interactivity**:
- Click row → Load that session in Session Analytics

**Layout**: Full width, variable height (one row per selected session)

---

## SECTION 5: Outlier & Anomaly Detection

### 5.1 Automated Outlier Detection Panel

**Objective**: Surface items requiring attention using statistical and pattern analysis

#### Algorithm A: Statistical Outliers (Performance)

**Method**: Items >3 standard deviations from mean extraction time

```python
SELECT
    person_name,
    duration_ms,
    AVG(duration_ms) OVER () as mean,
    STDEV(duration_ms) OVER () as stddev
FROM performance_metrics
WHERE operation = 'extraction'
HAVING duration_ms > (mean + 3 * stddev)
```

**Display**: Alert card "Performance Outliers"
- Count: `7 items` (red badge)
- List (expandable):
  - John Doe: `12,450ms` (4.2σ above mean)
  - Jane Smith: `10,230ms` (3.8σ above mean)
- Action: "Review All" button → Filter items table

---

#### Algorithm B: Error Patterns

**Method**: Group identical errors, flag if frequency >5

```python
SELECT
    error_message,
    COUNT(*) as frequency,
    GROUP_CONCAT(person_name, ', ') as affected_items
FROM batch_items
WHERE status = 'failed'
GROUP BY error_message
HAVING frequency > 5
```

**Display**: Alert card "Repeated Errors"
- Count: `2 patterns` (orange badge)
- List (expandable):
  - "TimeoutError: Page load exceeded 30s" (15 occurrences)
    - Suggested fix: "Increase timeout in settings"
    - Action: "Retry All" button
  - "Extraction failed: No cemetery found" (8 occurrences)
    - Suggested fix: "These may require manual review"
    - Action: "Mark for Manual Review" button

---

#### Algorithm C: Data Quality Issues

**Method**: Detect missing expected data fields

```python
# Missing cemetery but has burial event
SELECT COUNT(*) FROM batch_items bi
JOIN EventTable e ON ...
WHERE json_extract(bi.extracted_data, '$.cemeteryName') IS NULL
  AND e.EventType = 'Burial'
```

**Display**: Alert card "Data Quality Issues"
- **Missing cemetery names**: `12 items`
- **Orphaned media**: `4 images` (media without citation link)
- **Incomplete citations**: `6 items` (missing short footnote or bibliography)

---

#### Algorithm D: Retry Candidates

**Method**: Failed items with retry_count < max_retries (3)

```python
SELECT * FROM batch_items
WHERE status = 'failed'
  AND retry_count < 3
ORDER BY retry_count ASC
```

**Display**: Alert card "Retry Candidates"
- Count: `18 items` (green badge)
- Breakdown:
  - 0 retries: `12 items`
  - 1 retry: `5 items`
  - 2 retries: `1 item`
- Action: "Retry All" button (batch retry operation)

---

**Panel Layout**: Vertical stack of collapsible alert cards, each with:
- Header: Alert title + count badge
- Expand/collapse icon
- Severity color stripe (left border: red/orange/yellow/green)
- Action buttons in footer

**Overall Layout**: Full width, variable height (auto-stack)

---

### 5.2 Manual Investigation Tools

**Objective**: User-driven outlier hunting with custom filters

**Features**:

#### 5.2A Custom Filter Builder
- **Visual query builder**:
  - Field selector (dropdown): extraction_time, retry_count, status, etc.
  - Operator (dropdown): >, <, =, !=, LIKE, IN
  - Value input (text/number/dropdown)
  - AND/OR logic
  - Add/remove filter clauses

- **Example filters**:
  - `extraction_time > 5000 AND retry_count > 0`
  - `status = 'failed' AND error_message LIKE '%timeout%'`
  - `image_count = 0 AND cemetery_name IS NOT NULL`

**Visualization**: Form-based filter builder (similar to database query tools)

#### 5.2B Saved Filter Presets
- **Built-in presets**:
  - "Slow Extractions" (>5s)
  - "High Retry Items" (retry_count >= 2)
  - "Missing Images" (image_count = 0)
  - "Timeouts Only" (error LIKE '%timeout%')

- **Custom presets**:
  - User creates filter → "Save as Preset" button
  - Name preset: "My Custom Filter"
  - Preset appears in dropdown for quick access

**Storage**: Saved in user preferences (local storage or config file)

#### 5.2C Export Filtered Results
- **Button**: "Export Filtered Results" (enabled when filter active)
- **Format**: CSV with all columns + full error messages
- **Filename**: `findagrave_outliers_2025-11-19.csv`

**Layout**: Collapsible panel (accordion), full width

---

## SECTION 6: Administrative Tools

### 6.1 Batch Management

**Objective**: Control session lifecycle and state

**Actions**:

1. **Pause Active Session**
   - Button: "⏸ Pause" (only visible if session is active)
   - Behavior: Sets session status to 'suspended'
   - Confirmation: None (reversible)

2. **Resume Suspended Session**
   - Button: "▶ Resume" (only visible if session is suspended)
   - Behavior: Re-opens batch processing dialog, loads from checkpoint
   - Confirmation: None

3. **Delete Session**
   - Button: "🗑 Delete Session" (red, outline)
   - Confirmation dialog:
     - Title: "Delete session '{session_name}'?"
     - Warning: "This will permanently delete all items and metrics for this session."
     - Checkbox: "I understand this cannot be undone"
     - Buttons: Cancel / Delete (red, disabled until checkbox checked)
   - Behavior: Deletes from `batch_sessions`, cascades to `batch_items`, `batch_checkpoints`, `performance_metrics`

4. **Clear Completed Sessions**
   - Button: "🧹 Clear Completed" (orange, outline)
   - Confirmation: "Delete all completed sessions? ({count} sessions)"
   - Behavior: Deletes sessions with status = 'completed'
   - Keeps: Active, suspended, failed sessions

5. **Reset State DB**
   - Button: "⚠️ Reset State DB" (red, prominent)
   - Confirmation dialog:
     - Title: "RESET STATE DATABASE?"
     - Warning: "This will delete ALL batch state data (all sessions, items, metrics)."
     - Use case note: "Use this when you've restored RootsMagic from backup."
     - Checkbox: "I understand this is permanent and cannot be undone"
     - Buttons: Cancel / Reset Database (red, disabled until checkbox)
   - Behavior: Calls `state_repository.clear_all_sessions()`

**Layout**: Vertical button list in collapsible panel, icons + labels

---

### 6.2 Export & Reporting

**Objective**: Share insights and archive data

**Export Formats**:

#### 6.2A CSV Export
- **Session Summary CSV**:
  - Columns: session_name, date, total_items, completed, failed, avg_extraction_ms, error_rate
  - Filename: `findagrave_sessions_summary_{date}.csv`

- **Items Detail CSV**:
  - Columns: person_name, person_id, status, extraction_time, retry_count, error_message, memorial_url, family_links, image_count
  - Filename: `findagrave_items_{session_name}_{date}.csv`

- **Metrics CSV**:
  - Columns: session_id, operation, duration_ms, success, timestamp
  - Filename: `findagrave_metrics_{session_name}_{date}.csv`

**Button**: "📥 Export to CSV" with dropdown menu (Session Summary / Items Detail / Metrics)

#### 6.2B JSON Export
- **Full session data dump**:
  - Includes: session metadata, all items (with extracted_data), all metrics, checkpoints
  - Filename: `findagrave_session_{session_name}_{date}.json`
  - Format: Pretty-printed JSON (indent=2)

**Button**: "📦 Export to JSON"

**Use case**: Backup, sharing with collaborators, importing into analysis tools

#### 6.2C PDF Report (Future Enhancement)
- **Auto-generated summary report**:
  - Cover page: Session name, date range, summary stats
  - Page 2: Status distribution pie chart
  - Page 3: Processing timeline chart
  - Page 4: Error analysis
  - Page 5: Top 10 slowest items table
  - Page 6: Recommendations

**Button**: "📄 Generate PDF Report" (disabled in v1.0, shows "Coming Soon" tooltip)

#### 6.2D Scheduled Exports (Future Enhancement)
- **Email daily summary**:
  - Time: 7:00 AM daily
  - Recipients: User email(s)
  - Content: CSV attachment + summary stats in email body

**UI**: Settings panel with email input, schedule selector

**Layout**: Dropdown button with export format options

---

### 6.3 Settings & Preferences

**Objective**: Customize dashboard behavior and appearance

**Settings Categories**:

#### 6.3A Dashboard Settings
- **Auto-refresh interval**:
  - Options: Disabled / 5s / 10s / 30s / 60s
  - Default: 10s (when session is active)
  - Behavior: Polls state DB and updates dashboard

- **Default session selection**:
  - Options: Most recent / Last active / Ask me
  - Default: Most recent

- **Items per page**:
  - Options: 25 / 50 / 100
  - Default: 50
  - Applies to: Items table pagination

#### 6.3B Chart Settings
- **Color scheme**:
  - Options: Default / Colorblind-safe / High contrast / Grayscale
  - Default: Default
  - Applies to: All ECharts visualizations

- **Animation**:
  - Toggle: Enable/disable chart animations
  - Default: Enabled
  - Performance: Disabling improves performance on large datasets

#### 6.3C Notification Settings
- **Alert thresholds**:
  - Error rate alert: `> 5%` (slider: 0-20%)
  - Slow extraction alert: `> 5000ms` (slider: 1000-10000ms)
  - Retry count alert: `>= 3` (slider: 1-5)

- **Desktop notifications**:
  - Toggle: Enable/disable browser notifications
  - Triggers: Error threshold exceeded, batch complete

#### 6.3D Layout Preferences
- **Saved layouts**:
  - List of user-saved layouts
  - Actions: Load / Delete / Set as Default

- **Reset to default layout**:
  - Button: "Reset to Default"
  - Confirmation: "This will discard your current layout. Continue?"

**Layout**: Tabbed settings dialog, modal overlay

---

## Configurable Layout System

### Grid-Based Drag-and-Drop

**Implementation**: NiceGUI `ui.grid()` with JavaScript drag/drop handlers

**Features**:

1. **12-Column Responsive Grid**:
   - Each component = grid item with configurable column span (1-12)
   - Row height: Auto (content-based) or fixed (200px, 300px, 400px)

2. **Drag Handles**:
   - Every component card has drag handle icon (⋮⋮) in top-right corner
   - Cursor changes to grab hand on hover
   - Dragging shows ghost outline of component

3. **Drop Zones**:
   - Valid drop zones highlight with dashed blue border
   - Snap to grid (no sub-grid positioning)
   - Visual feedback: Green border on valid drop, red on invalid

4. **Layout Persistence**:
   - Save layout to local storage: `localStorage.setItem('dashboard_layout', JSON.stringify(layout))`
   - Load on dashboard init: `layout = JSON.parse(localStorage.getItem('dashboard_layout'))`
   - Fallback: Default layout if no saved layout exists

5. **Responsive Behavior**:
   - Desktop (>1200px): 12 columns
   - Tablet (768-1200px): 6 columns (components re-flow)
   - Mobile (<768px): 1 column (vertical stack)

**Layout Data Structure**:
```json
{
  "components": [
    {
      "id": "master_progress_card",
      "row": 0,
      "col": 0,
      "colSpan": 12,
      "rowSpan": 1
    },
    {
      "id": "status_distribution_chart",
      "row": 2,
      "col": 0,
      "colSpan": 4,
      "rowSpan": 2
    },
    ...
  ]
}
```

---

### Component Library (Add/Remove)

**Add Component Flow**:
1. User clicks "＋ Add Component" button (floating action button, bottom-right)
2. Opens component picker dialog (modal)
3. Shows categorized list of available components:
   - **Overview**: Master Progress, Active Sessions, Health Indicators
   - **Charts**: Status Distribution, Timeline, Retry Analysis, etc.
   - **Tables**: Items Table, Session Comparison
   - **Tools**: Export, Settings
4. Click component → Added to bottom of dashboard
5. User drags to desired position

**Remove Component Flow**:
1. Hover over component → "×" button appears in top-right (next to drag handle)
2. Click "×" → Component removed from dashboard (soft delete, can re-add)
3. Confirmation for destructive actions (e.g., "Remove Items Table?")

**Component State**:
- **Active**: Visible on dashboard
- **Inactive**: Not visible but can be added back
- **Disabled**: Not available (e.g., PDF Report in v1.0)

**Storage**: User's active components saved in layout JSON

---

### Layout Presets

**Built-in Presets**:

1. **Executive View** (High-level overview)
   - Components:
     - Master Progress Card (full width)
     - Active Sessions Summary
     - Health Indicators
     - Progress Over Time chart
     - Quality Metrics dashboard
   - Hidden: Items table, drill-down panels, error details

2. **Analyst View** (All charts and data)
   - Components: All available components enabled
   - Layout: Optimized for data exploration (charts prominent)

3. **Troubleshooting View** (Error-focused)
   - Components:
     - Health Indicators (top)
     - Error Analysis charts (prominent)
     - Outlier Detection panel (expanded)
     - Items Table (filtered to errors only)
     - Item Detail Panel (always open)
   - Hidden: Cumulative analytics, comparison tools

4. **Operator View** (Active batch monitoring)
   - Components:
     - Active Sessions (top, large)
     - Processing Timeline (real-time)
     - Items Table (current session only)
     - Batch Management tools (prominent)
   - Hidden: Historical analytics, comparison

**Preset Selector**:
- Dropdown in dashboard header: "Layout: [Executive ▼]"
- Click preset → Confirm switch (if current layout unsaved)
- Behavior: Loads preset layout, saves as current

**Custom Presets**:
- User customizes layout → "💾 Save Layout As..." button
- Dialog: "Name this layout: [______]"
- Saved preset appears in dropdown with (Custom) tag
- Actions: Load / Delete / Set as Default

**Default Preset**: Analyst View (shows everything, users can customize from there)

---

## Technical Requirements

### Performance Targets
- Dashboard load time: <2 seconds (with 1000 items)
- Chart render time: <500ms per chart
- Auto-refresh overhead: <100ms (no visible lag)
- Drag/drop responsiveness: <16ms (60 FPS)

### Browser Compatibility
- Primary: Chrome 90+, Firefox 88+, Safari 14+
- NiceGUI native mode: macOS-specific (PyWebView)

### Data Volume Handling
- Session items: Support up to 1000 items per session without pagination
- Total sessions: Support 50+ sessions without performance degradation
- Metrics records: Efficiently query up to 10,000 performance metrics

### Accessibility
- Keyboard navigation: Tab through components, Enter to activate
- Screen reader support: ARIA labels on all interactive elements
- Color contrast: WCAG AA compliant (4.5:1 minimum)

---

## Implementation Phases

### Phase 1: Core Dashboard (MVP)
- [ ] Section 1: Global Overview (all 3 components)
- [ ] Section 2: Session Analytics (selector + 2 basic charts)
- [ ] Section 3: Items Table (basic, no drill-down)
- [ ] Basic layout (fixed, no drag/drop)
- [ ] Auto-refresh (simple polling)

**Deliverable**: Functional dashboard with key metrics

---

### Phase 2: Advanced Visualizations
- [ ] Section 2: All performance charts (timeline, heatmap, etc.)
- [ ] Section 2: Error analysis charts
- [ ] Section 4: Cumulative analytics
- [ ] Chart interactivity (click to filter, zoom, etc.)

**Deliverable**: Rich visual analytics

---

### Phase 3: Drill-Down & Details
- [ ] Section 3: Item Detail Panel (slide-out)
- [ ] RootsMagic query integration (family links, citation details)
- [ ] Image thumbnails and lightbox
- [ ] Error detail views

**Deliverable**: Deep item inspection capabilities

---

### Phase 4: Outlier Detection
- [ ] Section 5: Automated outlier algorithms
- [ ] Section 5: Manual investigation tools
- [ ] Alert cards and notifications
- [ ] Suggested fixes and bulk actions

**Deliverable**: Proactive issue identification

---

### Phase 5: Configurability
- [ ] Drag-and-drop layout system
- [ ] Component library (add/remove)
- [ ] Layout presets (Executive, Analyst, etc.)
- [ ] Settings panel
- [ ] Layout persistence (local storage)

**Deliverable**: Fully customizable dashboard

---

### Phase 6: Export & Advanced Features
- [ ] CSV/JSON export
- [ ] PDF report generation
- [ ] Scheduled exports (email)
- [ ] Session comparison matrix
- [ ] Desktop notifications

**Deliverable**: Complete dashboard with all features

---

## Appendix

### Data Query Reference

**Key State DB Queries**:
```python
# Overall completion rate
SELECT
    SUM(completed_items) * 100.0 / SUM(total_items) as completion_rate
FROM batch_sessions

# Session performance metrics
SELECT operation, AVG(duration_ms), MAX(duration_ms), MIN(duration_ms)
FROM performance_metrics
WHERE session_id = ?
GROUP BY operation

# Error patterns
SELECT
    SUBSTR(error_message, 1, 50) as error_pattern,
    COUNT(*) as frequency
FROM batch_items
WHERE status = 'failed'
GROUP BY error_pattern
ORDER BY frequency DESC

# Outliers (>3σ)
WITH stats AS (
    SELECT
        AVG(duration_ms) as mean,
        STDEV(duration_ms) as stddev
    FROM performance_metrics
    WHERE operation = 'extraction'
)
SELECT * FROM performance_metrics
WHERE duration_ms > (SELECT mean + 3 * stddev FROM stats)
```

**RootsMagic Drill-Down Queries**:
```python
# Family links for person
SELECT f.FamilyID, f.FatherID, f.MotherID,
       father.Given || ' ' || father.Surname as father_name,
       mother.Given || ' ' || mother.Surname as mother_name,
       cl.CitationID IS NOT NULL as has_citation
FROM FamilyTable f
LEFT JOIN NameTable father ON f.FatherID = father.OwnerID AND father.IsPrimary = 1
LEFT JOIN NameTable mother ON f.MotherID = mother.OwnerID AND mother.IsPrimary = 1
LEFT JOIN CitationLinkTable cl ON f.FamilyID = cl.OwnerID AND cl.OwnerType = 1
WHERE f.FatherID = ? OR f.MotherID = ?

# Citation verification
SELECT c.CitationID, s.SourceID, s.Name
FROM CitationTable c
JOIN SourceTable s ON c.SourceID = s.SourceID
WHERE s.Name LIKE '%' || ? || '%'
```

---

### UX Patterns

**Visual Hierarchy**:
1. **Primary actions**: Large buttons, high contrast (green for positive actions)
2. **Secondary actions**: Outline buttons, medium size
3. **Destructive actions**: Red buttons, require confirmation
4. **Informational elements**: Muted colors, smaller text

**Color Coding**:
- **Green**: Success, complete, good performance
- **Yellow/Orange**: Warning, needs attention, moderate performance
- **Red**: Error, failed, poor performance
- **Gray**: Neutral, inactive, pending
- **Blue**: Information, links, selected state

**Tooltips**:
- Appear on hover after 500ms
- Max width: 300px
- Contain:
  - Metric definition (what it measures)
  - Calculation method (how it's computed)
  - Contextual help (what action to take)

**Loading States**:
- Skeleton screens for initial load (gray boxes matching component shapes)
- Spinner for auto-refresh (small, top-right of component)
- Progress bar for long operations (export, bulk retry)

---

### Future Enhancements

1. **AI-Powered Insights**:
   - Auto-generated recommendations: "Your error rate is 3× higher on weekends. Consider batch processing on weekdays."
   - Predictive completion dates using ML regression
   - Anomaly detection using isolation forests

2. **Real-Time Collaboration**:
   - Multi-user support: See who else is viewing dashboard
   - Shared annotations: Add notes to specific items (visible to team)
   - Activity feed: "John retried 5 failed items 2 hours ago"

3. **Mobile App**:
   - Simplified dashboard for iOS/Android
   - Push notifications for batch completion, errors
   - Quick actions: Pause/resume batch remotely

4. **Advanced Filtering**:
   - Natural language queries: "Show me items that failed more than twice yesterday"
   - Saved smart filters: Auto-update based on conditions (e.g., "Always show items with >3 retries")

5. **Integration with External Tools**:
   - Webhook notifications (Slack, Discord)
   - Export to Google Sheets (auto-sync)
   - Import batches from CSV

---

**Document Version History**:
- v1.0 (2025-11-19): Initial design specification
