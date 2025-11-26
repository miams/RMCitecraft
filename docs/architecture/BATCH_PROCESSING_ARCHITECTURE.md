# Find a Grave Batch Processing Architecture

## Overview

The Find a Grave batch processing system is designed to handle network timeouts, browser crashes, and interruptions gracefully. It provides production-grade robustness through:

- **Crash Detection & Recovery**: Detects and recovers from browser/page crashes
- **Adaptive Timeouts**: Self-tunes based on network performance
- **Exponential Backoff**: Retries transient failures with increasing delays
- **State Persistence**: Saves progress to separate SQLite database
- **Resume Capability**: Continue interrupted batches from last checkpoint
- **Performance Metrics**: Tracks timing and success rates

> **Note**: For Census batch processing, see [Census Batch Processing Architecture](CENSUS_BATCH_PROCESSING_ARCHITECTURE.md).

## Architecture Components

### 1. State Database (`BatchStateRepository`)

**Purpose**: Persist batch processing state independently from RootsMagic database

**Location**: `~/.rmcitecraft/batch_state.db` (shared with Census batch processing)

**Tables** (Find a Grave specific):
- `batch_sessions`: Session metadata (status, progress, config)
- `batch_items`: Individual memorial processing state
- `batch_checkpoints`: Resume points for interrupted sessions

**Shared Tables**:
- `performance_metrics`: Operation timing and success rates (used by both Find a Grave and Census)
- `schema_version`: Migration tracking

> **See Also**: [Batch State Database Schema](../reference/BATCH_STATE_DATABASE_SCHEMA.md) for complete field-level documentation.

**Key Features**:
- Completely separate from RootsMagic database (no confusion)
- Atomic transactions coordinated with RootsMagic updates
- Tracks per-item status: queued → extracting → creating_citation → complete
- Records retry counts, errors, created IDs

### 2. Page Health Monitor

**Purpose**: Detect crashed or unresponsive browser pages

**Implementation**: `src/rmcitecraft/services/page_health_monitor.py`

**Detection Method**:
```python
# Test page responsiveness by executing simple JavaScript
result = await page.evaluate("() => 1 + 1")
# If this throws or times out, page is crashed
```

**Crash Indicators**:
- "target crashed"
- "page crashed"
- "execution context was destroyed"
- "protocol error"
- "session closed"

**Recovery Strategy**:
- Detect crash before processing next item
- Request fresh page from browser context
- Health check new page
- Continue processing

### 3. Adaptive Timeout Manager

**Purpose**: Dynamically adjust timeouts based on observed response times

**Implementation**: `src/rmcitecraft/services/adaptive_timeout.py`

**Algorithm**:
```python
# Rolling window of recent successful response times (default: 10)
timeout = mean(times) + 2 * stdev(times) + buffer

# Buffer is max(20% of calculated, 5 seconds)
# Clamped to [15s, 120s] range
```

**Example**:
- If recent loads: 8s, 10s, 12s, 14s, 16s
- Mean = 12s, StDev ≈ 3s
- Calculated = 12 + 2*3 = 18s
- Buffer = max(18*0.2, 5) = 5s
- Final timeout = 23s

**Benefits**:
- Adapts to slow networks (increases timeout)
- Adapts to fast networks (decreases timeout)
- Prevents premature timeouts on congested connections

### 4. Retry Strategy

**Purpose**: Handle transient failures with exponential backoff

**Implementation**: `src/rmcitecraft/services/retry_strategy.py`

**Retryable Errors**:
- Network timeouts
- Connection errors (refused, reset)
- Browser crashes (target/page crashed)
- DNS failures
- Protocol errors

**Non-Retryable Errors**:
- 404 Not Found
- Memorial does not exist
- Private memorial
- Forbidden/Unauthorized

**Backoff Schedule** (default config):
- Attempt 1: Immediate
- Attempt 2: Wait 2s
- Attempt 3: Wait 4s
- Attempt 4: Wait 8s
- Max: 3 retries (4 total attempts)

**Jitter**: ±20% randomness to prevent thundering herd

### 5. Atomic Transactions

**Purpose**: Ensure RootsMagic DB and state DB stay synchronized

**Implementation**: `src/rmcitecraft/database/connection.py:atomic_batch_operation()`

**Pattern**:
```python
with atomic_batch_operation(rm_db_path, state_db_path) as (rm_conn, state_conn, tracker):
    # Write to RootsMagic database
    rm_cursor = rm_conn.cursor()
    rm_cursor.execute("INSERT INTO CitationTable ...")
    citation_id = rm_cursor.lastrowid
    tracker['citation_id'] = citation_id

    # Write to state database
    state_cursor = state_conn.cursor()
    state_cursor.execute("UPDATE batch_items SET status='complete' ...")

    # Both commit together on success
    # Both rollback together on error
```

**Guarantees**:
- Either both databases update or neither does
- No orphaned citations without state tracking
- No incomplete state records

## Batch Processing Workflow

### Six-Phase Processing Loop

**PHASE 1: Page Health Check**
```python
# Before processing each item
health = await health_monitor.check_page_health(page)
if not health.is_healthy:
    recovered_page = await recovery_manager.attempt_recovery(page, automation)
    if not recovered_page:
        raise Exception("Failed to recover crashed page")
```

**PHASE 2: Duplicate Detection**
```python
# Multi-layer duplicate checking
duplicate_check = check_citation_exists_detailed(
    db_path, person_id, memorial_id, memorial_url
)
if duplicate_check['exists']:
    # Skip with detailed reason (formatted citation, memorial ID, or URL match)
    continue
```

**PHASE 3: Extraction with Retry & Adaptive Timeout**
```python
# Get current adaptive timeout
timeout = timeout_manager.get_current_timeout()

# Wrap extraction in retry logic
async def extract_with_timeout():
    return await automation.extract_memorial_data(url, timeout=timeout)

memorial_data = await retry_strategy.retry_async(extract_with_timeout)

# Record timing for adaptive adjustment
extraction_duration = time.time() - start_time
timeout_manager.record_response_time(extraction_duration, success=True)
```

**PHASE 4: Citation Formatting**
```python
# Store extracted data in state DB
state_repository.update_item_extraction(item_id, memorial_data)

# Format citations
citation = format_findagrave_citation(...)
```

**PHASE 5: Database Writes**
```python
with atomic_batch_operation(rm_db, state_db) as (rm_conn, state_conn, tracker):
    # Create source & citation
    result = create_findagrave_source_and_citation(rm_conn, ...)

    # Link to families
    link_citation_to_families(rm_conn, ...)

    # Create burial event
    burial_id = create_burial_event_and_link_citation(rm_conn, ...)

    # Update state DB
    state_cursor = state_conn.cursor()
    state_cursor.execute("UPDATE batch_items SET status='complete' ...")
```

**PHASE 6: Checkpoint & Metrics**
```python
# Mark item complete
state_repository.update_item_status(item_id, 'complete')

# Create checkpoint every N items (default: 1)
checkpoint_counter += 1
if checkpoint_counter >= checkpoint_frequency:
    state_repository.create_checkpoint(session_id, item_id, person_id)
    checkpoint_counter = 0

# Record performance metrics
state_repository.record_metric(
    operation='extraction',
    duration_ms=int(duration * 1000),
    success=True,
    session_id=session_id
)
```

## Configuration

### Environment Variables

Add to `.env` file:

```bash
# Find a Grave Batch Processing Settings

# Base timeout for page loads (seconds, default: 30)
FINDAGRAVE_BASE_TIMEOUT_SECONDS=30

# Enable adaptive timeout adjustment (default: True)
FINDAGRAVE_ENABLE_ADAPTIVE_TIMEOUT=True

# Number of recent requests for adaptive calculation (default: 10)
FINDAGRAVE_TIMEOUT_WINDOW_SIZE=10

# Maximum retry attempts for transient failures (default: 3)
FINDAGRAVE_MAX_RETRIES=3

# Base delay for exponential backoff (seconds, default: 2)
FINDAGRAVE_RETRY_BASE_DELAY_SECONDS=2

# Path to batch state database (default: ~/.rmcitecraft/batch_state.db)
FINDAGRAVE_STATE_DB_PATH=~/.rmcitecraft/batch_state.db

# Items processed between checkpoints (default: 1)
FINDAGRAVE_CHECKPOINT_FREQUENCY=1

# Enable automatic crash detection and recovery (default: True)
FINDAGRAVE_ENABLE_CRASH_RECOVERY=True
```

### Settings Access

```python
from rmcitecraft.config import get_config

config = get_config()
print(config.findagrave_base_timeout_seconds)  # 30
print(config.findagrave_max_retries)  # 3
```

## Using Resume Functionality

### User Workflow

1. **Start Batch Processing**
   - Click "Load Batch" to load people from RootsMagic database
   - Click "Process" to begin batch processing
   - System creates session in state DB

2. **Interruption Occurs**
   - Browser crash
   - Network failure
   - User stops processing (Ctrl+C)
   - System automatically saves state at each checkpoint

3. **Resume Session**
   - Click "Resume Session" button
   - See list of incomplete sessions with progress
   - Click session to resume
   - Batch continues from last checkpoint

### Resume Dialog Information

The resume dialog shows for each session:
- **Session ID**: Unique identifier (e.g., `batch_1732012345`)
- **Created**: Session creation timestamp
- **Status**: `running`, `paused`, or `queued`
- **Progress**: `15/20 complete`
- **Errors**: `2 errors` (if any)
- **Pending**: `3 pending`
- **Delete Button**: Red trash icon to delete individual session

### Session Management

**Delete Individual Session:**
1. Click "Resume Session" button
2. Click the red delete icon (🗑️) next to any session
3. Session and all associated data are permanently deleted
4. Dialog refreshes to show updated list

**Clear All Sessions:**
1. Click "Resume Session" button
2. Click "Clear All Sessions" (orange button at bottom)
3. Confirm deletion in warning dialog
4. All batch state data is permanently deleted

**When to Clear All Sessions:**
- After restoring RootsMagic database from backup
- State database person IDs no longer match RootsMagic database
- Testing workflow requires clean slate
- Accumulated many old/failed sessions

**What Gets Deleted:**
- Session records
- All batch items
- All checkpoints
- All performance metrics

**Important Notes:**
- Deletion is permanent (no undo)
- RootsMagic database is NOT affected
- State database automatically recreates on next batch
- Safe to delete `~/.rmcitecraft/batch_state.db` manually

### Behind the Scenes

```python
def resume_session(session_id):
    # 1. Load session from state DB
    session = state_repository.get_session(session_id)
    state_items = state_repository.get_session_items(session_id)

    # 2. Get person data from RootsMagic DB
    person_ids = [item['person_id'] for item in state_items]
    people = get_findagrave_people_by_ids(rm_db_path, person_ids)

    # 3. Reconstruct batch items with preserved state
    for state_item in state_items:
        if state_item['status'] == 'complete':
            # Skip completed items
            continue

        # Restore extracted data, created IDs, retry counts
        item = create_batch_item_from_state(state_item, person_data)
        batch_items.append(item)

    # 4. Continue processing from where we left off
    process_batch(batch_items)
```

## Performance Metrics

### Session Completion Summary

After session completes, comprehensive metrics are logged:

```
Batch session batch_1732012345 completed:
  Total: 20, Successful: 18, Failed: 2

  extraction: avg=3500ms, success_rate=90.0%
  citation_creation: avg=250ms, success_rate=100.0%
  image_download: avg=1200ms, success_rate=88.9%

Adaptive timeout: mean=3.2s, current=25s
```

### Metrics Tracked

**Per Session**:
- Total items processed
- Success/error counts
- Average duration by operation
- Success rates by operation

**Per Operation**:
- `extraction`: Memorial data extraction
- `citation_creation`: Citation/source creation in RootsMagic
- `image_download`: Photo downloads

**Adaptive Timeout**:
- Current timeout value
- Mean response time
- Success rate

## Error Handling

### Error Classification

**Retryable Errors** (automatic retry):
- Network timeouts
- Connection failures
- Browser crashes
- DNS failures
- Protocol errors

**Non-Retryable Errors** (fail immediately):
- Memorial does not exist (404)
- Private memorial
- Forbidden/Unauthorized access
- Invalid memorial ID

### Error Recording

All errors are:
1. Logged with full stack trace
2. Stored in state DB (`batch_items.error_message`)
3. Displayed in UI with clear message
4. Counted in session error metrics

### Duplicate Detection Layers

**Layer 1: Pre-filtering** (during batch load)
- Check for existing Find a Grave citations
- Exclude people who already have formatted citations

**Layer 2: Runtime checking** (during batch processing)
- Check formatted citation existence
- Check memorial ID in RefNumber field
- Check memorial URL in RefNumber field
- Returns detailed match information

## Troubleshooting

### Browser Crashes Frequently

**Symptoms**: Multiple consecutive "page crashed" errors

**Solutions**:
1. Check Chrome/Chromium version compatibility
2. Restart Playwright browser
3. Reduce batch size to lower memory usage
4. Check for Playwright updates

### Timeouts Still Occurring

**Symptoms**: Items timing out despite adaptive timeout

**Solutions**:
1. Increase base timeout: `FINDAGRAVE_BASE_TIMEOUT_SECONDS=45`
2. Increase max timeout cap in code (120s default)
3. Check network connection stability
4. Verify Find a Grave site is accessible

### Resume Not Working

**Symptoms**: Resume button shows no sessions or sessions won't resume

**Solutions**:
1. Check state database exists: `ls ~/.rmcitecraft/batch_state.db`
2. Verify session status: Sessions must be `running`, `paused`, or `queued`
3. Check person IDs still exist in RootsMagic database
4. Review logs for specific error messages

### Duplicate Citations Created

**Symptoms**: Same memorial cited multiple times

**Solutions**:
1. Verify pre-filtering is working (check logs for "excluded" count)
2. Check duplicate detection in Phase 2 (should see "Duplicate: ..." messages)
3. Ensure memorial ID extraction is correct
4. Review CitationTable.RefNumber format

## Architecture Decisions

### Why Separate State Database?

**Problem**: RootsMagic database should not track batch processing state

**Solution**: Completely separate SQLite database

**Benefits**:
- No schema modifications to RootsMagic database
- No confusion between genealogy data and batch state
- Can be safely deleted without affecting genealogy data
- Independent backup/restore of batch state

### Why Atomic Transactions?

**Problem**: Partial updates create inconsistent state

**Example Failure**:
```
1. Create citation in RootsMagic DB ✓
2. Update state DB to 'complete' ✗ (crash)
Result: Citation exists but state says 'in progress'
```

**Solution**: Coordinate transactions across both databases

**Result**: Either both succeed or both rollback (no orphans)

### Why Adaptive Timeout?

**Problem**: Fixed timeouts either too short (many failures) or too long (waste time)

**Solution**: Self-tune based on observed response times

**Benefits**:
- Fast networks: Lower timeout (fail fast)
- Slow networks: Higher timeout (succeed eventually)
- Network degrades: Automatically increases timeout
- Network improves: Automatically decreases timeout

### Why Exponential Backoff?

**Problem**: Immediate retry hammers failing service

**Solution**: Wait increasing amounts between retries

**Benefits**:
- Gives transient failures time to resolve
- Reduces load on failing service
- Jitter prevents thundering herd
- Respects rate limits

## Testing

### Unit Tests

**Location**: `tests/unit/`

**Coverage**:
- `test_adaptive_timeout.py`: 22 tests
- `test_retry_strategy.py`: 24 tests
- `test_batch_state_repository.py`: 24 tests

**Total**: 70 tests, 100% passing

**Run Tests**:
```bash
uv run pytest tests/unit/test_adaptive_timeout.py -v
uv run pytest tests/unit/test_retry_strategy.py -v
uv run pytest tests/unit/test_batch_state_repository.py -v
```

### Integration Tests

Integration tests for end-to-end crash recovery scenarios are planned but not yet implemented due to complexity of simulating browser crashes reliably.

## Future Enhancements

### Planned Improvements

1. **Parallel Processing**: Process multiple items concurrently
2. **Batch Prioritization**: Resume high-priority batches first
3. **Network Quality Detection**: Adjust retry strategy based on connection quality
4. **Automatic Retry Scheduling**: Re-queue failed items for later retry
5. **Session Cleanup**: Archive old completed sessions
6. **Performance Dashboards**: Visualize metrics over time

### Configuration Enhancements

1. **Per-Session Settings**: Override defaults for specific batches
2. **Retry Policies**: Customizable retry patterns
3. **Timeout Profiles**: Presets for different network conditions
4. **Alert Thresholds**: Notifications for high error rates

## References

### Key Files

**Implementation**:
- `src/rmcitecraft/database/batch_state_repository.py` - State persistence
- `src/rmcitecraft/services/page_health_monitor.py` - Crash detection
- `src/rmcitecraft/services/adaptive_timeout.py` - Dynamic timeouts
- `src/rmcitecraft/services/retry_strategy.py` - Exponential backoff
- `src/rmcitecraft/database/connection.py` - Atomic transactions
- `src/rmcitecraft/ui/tabs/findagrave_batch.py` - Batch processing UI

**Tests**:
- `tests/unit/test_batch_state_repository.py`
- `tests/unit/test_adaptive_timeout.py`
- `tests/unit/test_retry_strategy.py`

**Schema**:
- `migrations/001_create_batch_state_tables.sql`

### Related Documentation

- [Batch State Database Schema](../reference/BATCH_STATE_DATABASE_SCHEMA.md) - Complete schema reference
- [Census Batch Processing Architecture](CENSUS_BATCH_PROCESSING_ARCHITECTURE.md) - Census-specific workflow
- `CLAUDE.md` - Development guidance
- `AGENTS.md` - Machine-readable instructions
- `PRD.md` - Product requirements

## Maintenance

### Database Cleanup

State database grows over time. To clean old sessions:

```python
# Delete completed sessions older than 30 days
import sqlite3
from datetime import datetime, timedelta, timezone

conn = sqlite3.connect("~/.rmcitecraft/batch_state.db")
cursor = conn.cursor()

cutoff = datetime.now(timezone.utc) - timedelta(days=30)
cursor.execute("""
    DELETE FROM batch_sessions
    WHERE status = 'completed' AND completed_at < ?
""", (cutoff,))

conn.commit()
conn.close()
```

### Monitoring Health

Check system health with metrics:

```python
# Get recent session statistics
sessions = state_repository.get_resumable_sessions()
print(f"Active sessions: {len(sessions)}")

# Check timeout performance
stats = timeout_manager.get_statistics()
print(f"Success rate: {stats['success_rate']:.1%}")
print(f"Current timeout: {stats['current_timeout']}s")
```

## Support

For issues or questions:
- Check logs in `logs/` directory
- Review error messages in UI
- Examine state database with SQLite browser
- Report issues at: https://github.com/miams/RMCitecraft/issues

---

**Last Updated**: 2025-11-26
**Version**: 1.1.0
**Status**: Production
