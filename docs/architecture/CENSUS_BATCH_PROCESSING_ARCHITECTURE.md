# Census Batch Processing Architecture

## Overview

The Census batch processing system automates the transformation of FamilySearch placeholder citations into *Evidence Explained* compliant format. It processes US Federal Census records (1790-1950) with:

- **FamilySearch Integration**: Extracts enumeration district, sheet, and location data
- **Citation Formatting**: Generates footnote, short footnote, and bibliography
- **Image Management**: Downloads and organizes census images
- **State Persistence**: Saves progress for crash recovery and resume
- **Adaptive Processing**: Self-tunes timeouts based on network performance

## Key Differences from Find a Grave Processing

| Aspect | Census | Find a Grave |
|--------|--------|--------------|
| **Source** | FamilySearch | Find a Grave website |
| **Creates new citations** | No (updates existing) | Yes (creates new) |
| **Validation** | *Evidence Explained* criteria | Memorial data validation |
| **Image source** | FamilySearch image viewer | Memorial photos |
| **Year-specific logic** | Yes (1790-1950 variations) | No |
| **Pre-filtering** | Excludes already-processed | Excludes existing citations |

## Architecture Components

### 1. State Repository (`CensusBatchStateRepository`)

**Purpose**: Persist Census batch processing state for resume capability

**Location**: `~/.rmcitecraft/batch_state.db` (shared with Find a Grave)

**Tables**: `census_batch_sessions`, `census_batch_items`, `census_batch_checkpoints`

**Key Features**:
- Census-year filtering at session level
- State/county tracking for analytics
- Shared `performance_metrics` table with Find a Grave

See [Batch State Database Schema](./BATCH_STATE_DATABASE_SCHEMA.md) for complete schema details.

### 2. Citation Filtering (`find_census_citations`)

**Purpose**: Identify citations that need processing

**Location**: `scripts/process_census_batch.py`

**Pre-filtering Criteria**:

A citation is **excluded** from the queue if BOTH conditions are met:

1. **Criterion 5**: `footnote != short_footnote` (citations differ after processing)
2. **Criterion 6**: All three citation forms pass validation:
   - Footnote contains: year, "census", sheet/page/stamp, ED reference (1900+), FamilySearch reference
   - Short footnote contains: year, "census"/"pop. sch.", sheet/stamp
   - Bibliography contains: year, "census", FamilySearch reference

**Implementation**: `FormattedCitationValidator.is_citation_processed()` in `validation/data_quality.py`

### 3. Batch Processing Controller

**Purpose**: Manage in-memory state and validation during processing

**Location**: `src/rmcitecraft/services/batch_processing.py`

**Key Classes**:
- `BatchProcessingController`: Orchestrates workflow
- `BatchProcessingSession`: Tracks session state
- `CitationBatchItem`: Represents individual citation

**Status Flow**:
```
QUEUED → EXTRACTING → EXTRACTED → MANUAL_REVIEW → COMPLETE
                                              ↓
                                           ERROR
```

### 4. FamilySearch Automation

**Purpose**: Extract census data from FamilySearch pages

**Location**: `src/rmcitecraft/services/familysearch_automation.py`

**Extracted Data**:
- Enumeration District (ED)
- Sheet/Stamp number
- Line number
- Family/Dwelling number
- Township/Ward
- State, County, City
- FamilySearch URL

### 5. Citation Formatter

**Purpose**: Generate *Evidence Explained* compliant citations

**Location**: `src/rmcitecraft/services/citation_formatter.py`

**Output Formats**:
- **Footnote**: Full citation with all details
- **Short Footnote**: Abbreviated form for subsequent references
- **Bibliography**: Source list entry

**Year-Specific Templates**:
- 1790-1840: No ED, no population schedule
- 1850-1880: Population schedule, page/sheet, dwelling/family
- 1880+: Enumeration District (ED) introduced
- 1950: Uses "stamp" instead of "sheet"

## Batch Processing Workflow

### Six-Phase Processing Loop

Each citation goes through six phases:

```
┌─────────────────────────────────────────────────────────────┐
│  PHASE 1: PAGE HEALTH CHECK                                 │
│  - Verify browser page is responsive                        │
│  - Attempt recovery if crashed                              │
│  - Skip item on unrecoverable crash                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 2: ALREADY EXTRACTED CHECK                           │
│  - Skip if extraction_complete flag set                     │
│  - Verify FamilySearch URL exists                           │
│  - Update state to 'extracting'                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 3: EXTRACTION WITH RETRY & ADAPTIVE TIMEOUT          │
│  - Navigate to FamilySearch page                            │
│  - Extract census metadata                                  │
│  - Retry with exponential backoff on failure                │
│  - Record timing for adaptive timeout                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 4: IMAGE DOWNLOAD                                    │
│  - Skip if media already exists                             │
│  - Download census image from FamilySearch                  │
│  - Rename to standard format                                │
│  - Move to year-specific folder                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 5: STATUS UPDATE                                     │
│  - Validate extracted data                                  │
│  - Generate formatted citations                             │
│  - Set status: COMPLETE or MANUAL_REVIEW                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 6: CHECKPOINT                                        │
│  - Save progress to state database                          │
│  - Record performance metrics                               │
│  - Update session counts                                    │
└─────────────────────────────────────────────────────────────┘
```

### Phase Details

#### Phase 1: Page Health Check

```python
if config.census_enable_crash_recovery:
    page = await familysearch_automation.get_or_create_page()
    health = await health_monitor.check_page_health(page)

    if not health.is_healthy:
        recovered_page = await recovery_manager.attempt_recovery(page, automation)
        if not recovered_page:
            # Mark error and skip
            return "error"
```

#### Phase 2: Already Extracted Check

```python
# Skip if already extracted
if citation.extracted_data and citation.extracted_data.get('extraction_complete'):
    return "skipped"

# Verify URL exists
if not citation.familysearch_url:
    return "error"
```

#### Phase 3: Extraction with Retry

```python
timeout = timeout_manager.get_current_timeout()
retry_count = 0

while retry_count <= config.census_max_retries:
    try:
        extracted_data = await automation.extract_citation_data(
            citation.familysearch_url,
            census_year=citation.census_year
        )
        if extracted_data:
            timeout_manager.record_response_time(duration, success=True)
            break
    except Exception as e:
        if retry_strategy.should_retry(e, retry_count):
            delay = retry_strategy.get_delay(retry_count)
            await asyncio.sleep(delay)
            retry_count += 1
        else:
            return "error"
```

#### Phase 4: Image Download

```python
if not citation.has_existing_media:
    state_repository.update_item_status(item_id, 'downloading_images')
    await download_citation_image(citation)
```

#### Phase 5: Status Update

Status is set by `controller.update_citation_extracted_data()`:
- **COMPLETE**: All required fields present, validation passed
- **MANUAL_REVIEW**: Missing required fields (e.g., ED for 1900+ census)

#### Phase 6: Checkpoint

```python
checkpoint_counter += 1
if checkpoint_counter >= config.census_checkpoint_frequency:
    state_repository.create_checkpoint(session_id, item_id, person_id)
    checkpoint_counter = 0
```

## Configuration

### Environment Variables

```bash
# Census Batch Processing Settings

# Base timeout for page loads (seconds, default: 30)
CENSUS_BASE_TIMEOUT_SECONDS=30

# Enable adaptive timeout adjustment (default: True)
CENSUS_ENABLE_ADAPTIVE_TIMEOUT=True

# Maximum retry attempts for transient failures (default: 3)
CENSUS_MAX_RETRIES=3

# Base delay for exponential backoff (seconds, default: 2)
CENSUS_RETRY_BASE_DELAY_SECONDS=2

# Items processed between checkpoints (default: 1)
CENSUS_CHECKPOINT_FREQUENCY=1

# Enable automatic crash detection and recovery (default: True)
CENSUS_ENABLE_CRASH_RECOVERY=True
```

### Settings Access

```python
from rmcitecraft.config import get_config

config = get_config()
print(config.census_base_timeout_seconds)  # 30
print(config.census_max_retries)           # 3
```

## Validation Rules

### Required Fields by Census Year

| Field | 1790-1840 | 1850-1870 | 1880 | 1900-1950 |
|-------|-----------|-----------|------|-----------|
| State | Required | Required | Required | Required |
| County | Required | Required | Required | Required |
| Census Year | Required | Required | Required | Required |
| Person Name | Required | Required | Required | Required |
| Enumeration District | N/A | N/A | Required | Required |
| Sheet/Stamp | N/A | Required | Required | Required |
| Family Number | N/A | Optional | Optional | Optional |
| Dwelling Number | N/A | Optional | Optional | N/A |

### Validation Functions

Located in `src/rmcitecraft/validation/data_quality.py`:

- `FormattedCitationValidator.validate_footnote()`: Validates footnote format
- `FormattedCitationValidator.validate_short_footnote()`: Validates short footnote
- `FormattedCitationValidator.validate_bibliography()`: Validates bibliography
- `FormattedCitationValidator.is_citation_processed()`: Determines if citation needs processing
- `is_citation_needs_processing()`: Convenience wrapper

## Resume Functionality

### Starting a New Session

1. User selects census year and clicks "Load Citations"
2. `find_census_citations()` queries RootsMagic database
3. Pre-filtering excludes already-processed citations
4. Session created in `census_batch_sessions` table
5. Items created in `census_batch_items` table

### Resuming Interrupted Session

1. User clicks "Resume Session"
2. Dialog shows sessions with status `running`, `paused`, or `queued`
3. User selects session to resume
4. Incomplete items loaded from `census_batch_items`
5. Processing continues from last checkpoint

### Session Management

**Delete Individual Session:**
```python
state_repository.delete_session(session_id)
# Cascades to items and checkpoints
```

**Clear All Census Sessions:**
```python
state_repository.clear_all_sessions()
# Removes all census batch data
```

## Export to RootsMagic

### Export Process

1. User clicks "Export to RootsMagic"
2. System filters for `status = 'complete'` items
3. For each completed item:
   - Updates `SourceTable.Fields` BLOB with formatted citations
   - Updates `SourceTable.Name` with bracket content
   - Creates/links media records if images downloaded
4. Atomic transaction ensures all-or-nothing update

### Source Name Update

The Source Name bracket content is updated with extracted details:

**Before:**
```
Fed Census: 1950, Ohio, Franklin [] Iams, John Winder
```

**After:**
```
Fed Census: 1950, Ohio, Franklin [citing household form enumeration district (ED) 94-529, stamp 5643] Iams, John Winder
```

## Error Handling

### Retryable Errors

- Network timeouts
- Connection failures
- Browser crashes
- DNS failures

### Non-Retryable Errors

- No FamilySearch URL
- Page not found (404)
- Invalid census year
- Forbidden access

### Error Recording

All errors are:
1. Logged with stack trace
2. Stored in `census_batch_items.error_message`
3. Counted in `census_batch_sessions.error_count`
4. Displayed in UI

## Performance Metrics

### Tracked Operations

| Operation | Description |
|-----------|-------------|
| `extraction` | FamilySearch data extraction |
| `citation_creation` | Citation formatting and export |
| `image_download` | Census image download |
| `page_load` | FamilySearch page navigation |

### Metrics Query

```sql
SELECT
    operation,
    AVG(duration_ms) as avg_ms,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate
FROM performance_metrics
WHERE batch_type = 'census'
  AND session_id = 'census_1950_20251125'
GROUP BY operation;
```

## Testing

### Unit Tests

**Location**: `tests/unit/test_census_batch_state_repository.py`

**Coverage**: 43 tests covering:
- Session CRUD operations
- Item status transitions
- Checkpoint management
- Performance metrics
- Analytics queries

### Integration Tests

**Location**: `tests/integration/test_census_batch_integration.py`

**Coverage**: 18 tests covering:
- End-to-end batch processing
- Resume functionality
- Export to RootsMagic

### Running Tests

```bash
# All census batch tests
uv run pytest tests/ -k "census_batch" -v

# Unit tests only
uv run pytest tests/unit/test_census_batch_state_repository.py -v

# Integration tests only
uv run pytest tests/integration/test_census_batch_integration.py -v
```

## Troubleshooting

### No Citations Found

**Symptoms**: "No citations found for YYYY census"

**Causes & Solutions**:
1. **All processed**: Citations pass validation criteria
   - Check `skipped_processed` count in log
   - Verify criteria with `is_citation_needs_processing()`

2. **No FamilySearch URLs**: Citations lack URLs
   - Check `excluded` count in log
   - Verify FamilySearch Entry field in RootsMagic

3. **Wrong year filter**: Session year doesn't match citations
   - Verify `EventTable.Date` contains year

### Extraction Failures

**Symptoms**: Items stuck at `extracting` status

**Solutions**:
1. Check FamilySearch login status
2. Verify network connectivity
3. Increase timeout: `CENSUS_BASE_TIMEOUT_SECONDS=45`
4. Check browser console for errors

### Resume Not Working

**Symptoms**: Sessions don't appear in resume dialog

**Causes**:
1. Session status is `completed` or `failed`
2. Database file missing or corrupt
3. No incomplete items in session

**Solutions**:
1. Check session status in database
2. Verify `~/.rmcitecraft/batch_state.db` exists
3. Query `census_batch_items` for incomplete items

## File References

### Implementation

| File | Purpose |
|------|---------|
| `src/rmcitecraft/ui/tabs/batch_processing.py` | UI and processing orchestration |
| `src/rmcitecraft/services/batch_processing.py` | Controller and data models |
| `src/rmcitecraft/database/census_batch_state_repository.py` | State persistence |
| `src/rmcitecraft/services/familysearch_automation.py` | FamilySearch extraction |
| `src/rmcitecraft/services/citation_formatter.py` | Citation formatting |
| `src/rmcitecraft/validation/data_quality.py` | Validation logic |
| `scripts/process_census_batch.py` | Citation finder with filtering |

### Tests

| File | Purpose |
|------|---------|
| `tests/unit/test_census_batch_state_repository.py` | State repository tests |
| `tests/integration/test_census_batch_integration.py` | Integration tests |
| `tests/e2e/test_census_batch_with_downloads.py` | End-to-end tests |

### Schema

| File | Purpose |
|------|---------|
| `migrations/002_create_census_batch_tables.sql` | Census table definitions |

## Related Documentation

- [Batch State Database Schema](./BATCH_STATE_DATABASE_SCHEMA.md)
- [Find a Grave Batch Processing Architecture](../architecture/BATCH_PROCESSING_ARCHITECTURE.md)
- [Data Quality Validation](../misc/DATA_QUALITY_VALIDATION.md)

---

**Last Updated:** 2025-11-26
**Version:** 1.0.0
**Status:** Production
