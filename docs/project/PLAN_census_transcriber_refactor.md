# Census Transcription Batch Processing Enhancement Plan

## Overview

Transform the census transcription system from single-item UI-driven extraction to robust batch processing with:
1. **Primary extraction method**: Person page table ARKs (family members with relationships)
2. **Secondary extraction method**: SLS API (fallback for complete page coverage)
3. **Duplicate prevention**: Track processed census images to avoid re-processing
4. **Edge detection**: Notify operator when families span page boundaries
5. **Batch UI**: Multi-select queue with progress tracking (similar to Find a Grave)

---

## Phase 1: Extract Family Member ARKs from Person Page Table

### Current State
The person page table on FamilySearch already extracts:
- Core fields: Name, Line Number, Age, Relationship to Head, etc.
- Household member links via DOM: `a[href*="/ark:/61903/1:1:"]`

### Enhancement Required
The person page table on FamilySearch displays family relationships with names AND clickable links. For example, when viewing a person's record, you see:
```
Household Members (in this household)
Father: William C James  [link to ARK]
Mother: Mary E James     [link to ARK]
Wife:   Ella M James     [link to ARK]
```

**New Method**: `_extract_family_member_arks_from_table()`
```python
async def _extract_family_member_arks_from_table(
    self, page: Page
) -> list[dict[str, str]]:
    """
    Extract family member ARKs from person page table.

    The FamilySearch person page displays "Household Members" section
    with relationship labels and linked ARKs.

    Returns:
        List of dicts with keys: name, ark, relationship
        e.g., [{'name': 'Mary E James', 'ark': '1:1:XXXX', 'relationship': 'Wife'}]
    """
```

### Implementation Notes
- Parse table rows with relationship labels (Father, Mother, Wife, Son, etc.)
- Extract both name AND ARK URL from links
- This gives us NAMED family members (unlike SLS API which returns ARKs only)
- Use as PRIMARY extraction method when filtering to RootsMagic persons

---

## Phase 2: Census Transcription Batch State Schema

### New Tables (in `batch_state.db`)

Migration `003_create_census_transcription_tables.sql`:

```sql
-- Census Transcription Sessions (different from census_batch_sessions)
-- census_batch_sessions is for Citation Batch Processing (updating existing citations)
-- This is for Transcription Processing (extracting data from FamilySearch into census.db)
CREATE TABLE IF NOT EXISTS census_transcription_sessions (
    session_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    status TEXT DEFAULT 'queued',  -- queued, running, paused, completed, failed
    total_items INTEGER DEFAULT 0,
    completed_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    skipped_count INTEGER DEFAULT 0,
    census_year INTEGER,  -- Filter: 1790-1950 or NULL for all
    config_snapshot TEXT  -- JSON
);

-- Census Transcription Items (one per RootsMagic citation to process)
CREATE TABLE IF NOT EXISTS census_transcription_items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES census_transcription_sessions(session_id),

    -- RootsMagic source data
    rmtree_citation_id INTEGER NOT NULL,
    rmtree_person_id INTEGER,  -- Head of household RIN
    person_name TEXT,
    census_year INTEGER NOT NULL,
    state TEXT,
    county TEXT,

    -- FamilySearch references
    familysearch_ark TEXT,  -- Person ARK from citation
    image_ark TEXT,         -- Image ARK (3:1:XXXX format)

    -- Processing state
    status TEXT DEFAULT 'queued',
    -- Status values: queued, extracting, extracted, complete, error, skipped
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    last_attempt_at TEXT,

    -- Results
    census_db_person_id INTEGER,  -- ID in census.db after extraction
    census_db_page_id INTEGER,    -- ID in census.db
    household_extracted_count INTEGER DEFAULT 0,

    -- Edge detection flags
    first_line_flag INTEGER DEFAULT 0,  -- Person on line 1
    last_line_flag INTEGER DEFAULT 0,   -- Person on last line (30/40)

    UNIQUE(session_id, rmtree_citation_id)
);

-- Processed Census Images (for duplicate prevention)
CREATE TABLE IF NOT EXISTS processed_census_images (
    image_ark TEXT PRIMARY KEY,      -- Image ARK (3:1:XXXX format)
    census_year INTEGER NOT NULL,
    state TEXT,
    county TEXT,
    enumeration_district TEXT,
    sheet_number TEXT,

    -- Processing info
    first_processed_at TEXT NOT NULL,
    last_processed_at TEXT,
    session_id TEXT,                 -- Session that first processed this
    total_persons_extracted INTEGER DEFAULT 0,

    -- Page info for duplicate detection
    census_db_page_id INTEGER        -- Link to census.db census_page
);

-- Transcription checkpoints
CREATE TABLE IF NOT EXISTS census_transcription_checkpoints (
    session_id TEXT PRIMARY KEY REFERENCES census_transcription_sessions(session_id),
    last_processed_item_id INTEGER,
    last_processed_citation_id INTEGER,
    checkpoint_at TEXT NOT NULL
);

-- Index for duplicate checking
CREATE INDEX IF NOT EXISTS idx_processed_images_year_state
ON processed_census_images(census_year, state, county);
```

---

## Phase 3: Duplicate Prevention System

### Image-Level Duplicate Prevention

**Problem**: Multiple RootsMagic persons may share the same census page. Without tracking, we'd re-extract the same image multiple times.

**Solution**: Track processed images by Image ARK (3:1:XXXX format).

```python
class CensusTranscriptionRepository:
    """Repository for census transcription batch state."""

    def is_image_already_processed(self, image_ark: str) -> bool:
        """Check if an image has already been processed."""

    def mark_image_processed(
        self,
        image_ark: str,
        census_year: int,
        state: str,
        county: str,
        ed: str,
        sheet: str,
        census_db_page_id: int,
        person_count: int,
        session_id: str
    ) -> None:
        """Mark an image as processed to prevent duplicates."""

    def get_processed_image_info(self, image_ark: str) -> dict | None:
        """Get info about a previously processed image."""
```

### Person-Level Duplicate Prevention

Use existing `normalize_ark_url()` and `repository.get_person_by_ark()` in census.db.

### Queue Filtering

When building the transcription queue:
1. Query RootsMagic citations with FamilySearch ARKs
2. For each citation, check if the Image ARK has been processed
3. Skip citations for already-processed images (show count in UI)
4. Include option to "Re-process" for manual override

---

## Phase 4: Edge Detection for Page Boundaries

### Problem
Census families can span page boundaries:
- Family starts on line 1 → may have started on previous page
- Family ends on last line (30 for 1950, 40 for 1940) → may continue on next page

### Detection Logic

```python
# Line limits by census year
LINE_LIMITS = {
    1950: 30,  # 30 lines per sheet
    1940: 40,  # 40 lines per sheet
    1930: 100, # 100 lines per sheet
    1920: 100,
    # etc.
}

def detect_edge_conditions(
    line_number: int,
    census_year: int,
    relationship_to_head: str,
) -> dict[str, bool]:
    """
    Detect if a person may span page boundaries.

    Returns:
        {
            'first_line_warning': True/False,
            'last_line_warning': True/False,
            'warning_message': str or None
        }
    """
    max_line = LINE_LIMITS.get(census_year, 40)

    first_line_warning = (line_number == 1)
    last_line_warning = (line_number >= max_line - 2)  # Within 2 of last line

    message = None
    if first_line_warning and relationship_to_head not in ('Head', 'head'):
        message = f"Line 1: {relationship_to_head} may have family on previous page"
    elif last_line_warning:
        message = f"Line {line_number}/{max_line}: Family may continue on next page"

    return {
        'first_line_warning': first_line_warning,
        'last_line_warning': last_line_warning,
        'warning_message': message,
    }
```

### UI Notifications

- **In-progress indicator**: Yellow warning badge on items with edge flags
- **Summary report**: List all items needing manual page boundary review
- **Log output**: Clear message for each edge case detected

---

## Phase 5: Batch Processing Service

### CensusTranscriptionBatchService

```python
class CensusTranscriptionBatchService:
    """Orchestrates census transcription batch processing."""

    def __init__(
        self,
        extractor: FamilySearchCensusExtractor,
        state_repo: CensusTranscriptionRepository,
        rm_db_path: str,
    ):
        self.extractor = extractor
        self.state_repo = state_repo
        self.rm_db_path = rm_db_path

    async def build_transcription_queue(
        self,
        census_year: int | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """
        Build queue of citations to transcribe.

        1. Query RootsMagic for census citations with FamilySearch ARKs
        2. Filter out citations for already-processed images
        3. Group by image ARK (multiple citations may share an image)
        4. Return sorted queue
        """

    async def process_batch(
        self,
        session_id: str,
        on_progress: Callable[[int, int, str], None] | None = None,
        on_edge_warning: Callable[[str, dict], None] | None = None,
    ) -> BatchResult:
        """
        Process all items in a session.

        For each item:
        1. Check if image already processed → skip with link to existing data
        2. Navigate to person ARK
        3. Extract family member ARKs from person page table (PRIMARY)
        4. Filter to RootsMagic persons using fuzzy name matching
        5. Extract data for matched persons
        6. Fallback to SLS API for any missed persons (SECONDARY)
        7. Detect edge conditions and flag for review
        8. Mark image as processed
        9. Record metrics and checkpoint
        """

    async def _extract_with_family_priority(
        self,
        ark_url: str,
        census_year: int,
        rm_persons: list[RMPersonData],
    ) -> ExtractionResult:
        """
        Extract using family table ARKs as primary method.

        1. Navigate to person ARK page
        2. Extract family member ARKs from table (names + ARKs + relationships)
        3. Match against rm_persons using fuzzy name matching
        4. Extract data for matched family members
        5. If any rm_persons not found, fallback to SLS API
        """
```

---

## Phase 6: Updated UI for Batch Operations

### New Tab: "Census Transcription"

Replace current single-import dialog with batch processing tab:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Census Transcription                                               │
├─────────────────────────────────────────────────────────────────────┤
│  [Year: 1950 ▼]  [State: All ▼]  [Load Queue]  [Resume Session ▼]  │
├─────────────────────────────────────────────────────────────────────┤
│  Queue: 45 citations | Skipped: 12 (already processed) | Errors: 0  │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ □  R Lynn Ijams       1950  Franklin Co., IL    ED 94-123      │ │
│  │ ⚠  Mary E James       1950  Franklin Co., IL    ED 94-123  [L1]│ │
│  │ □  John W Iams        1950  Noble Co., OH       ED 67-45       │ │
│  │ ...                                                             │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  [Select All]  [Deselect All]  [Process Selected (3)]              │
├─────────────────────────────────────────────────────────────────────┤
│  Progress: ████████░░░░░░░░ 8/45 (17.8%)                           │
│  Current: Extracting Mary E James...                                │
│  Warnings: 2 items need page boundary review                        │
└─────────────────────────────────────────────────────────────────────┘
```

### UI Components

1. **Filter Controls**
   - Census year dropdown (1790-1950)
   - State filter
   - Show/hide already processed toggle

2. **Queue Table**
   - Checkbox for multi-select
   - Person name, year, location, ED
   - Status icons (queued, processing, complete, error)
   - Edge warning badges ([L1], [L30])

3. **Action Buttons**
   - Load Queue: Build queue from RootsMagic
   - Process Selected: Start batch for selected items
   - Resume Session: Show incomplete sessions dialog
   - Clear Queue: Reset current queue

4. **Progress Section**
   - Progress bar with item count
   - Current item being processed
   - Edge warnings summary
   - Error summary with retry option

5. **Summary Panel** (on completion)
   - Total extracted
   - Skipped (duplicates)
   - Edge warnings requiring review
   - Errors needing attention

---

## Implementation Order

### Week 1: Foundation
1. Create migration `003_create_census_transcription_tables.sql`
2. Implement `CensusTranscriptionRepository` with session/item CRUD
3. Add `_extract_family_member_arks_from_table()` method
4. Write unit tests for new repository

### Week 2: Duplicate Prevention & Edge Detection
5. Implement image-level duplicate tracking
6. Add edge detection logic with census-year-specific line limits
7. Update `extract_from_ark()` to return edge flags
8. Write tests for duplicate prevention and edge detection

### Week 3: Batch Service
9. Implement `CensusTranscriptionBatchService`
10. Add primary (table ARKs) + secondary (SLS API) extraction logic
11. Integrate with existing retry strategy and adaptive timeout
12. Write integration tests

### Week 4: UI
13. Create new Census Transcription tab
14. Implement queue building and filtering
15. Add progress tracking and edge warning display
16. Add session resume functionality

---

## Files to Create/Modify

### New Files
- `migrations/003_create_census_transcription_tables.sql`
- `src/rmcitecraft/database/census_transcription_repository.py`
- `src/rmcitecraft/services/census_transcription_batch.py`
- `src/rmcitecraft/ui/tabs/census_transcription.py`
- `tests/unit/test_census_transcription_repository.py`
- `tests/integration/test_census_transcription_batch.py`

### Modified Files
- `src/rmcitecraft/services/familysearch_census_extractor.py`
  - Add `_extract_family_member_arks_from_table()`
  - Add edge detection to `extract_from_ark()`
- `src/rmcitecraft/ui/tabs/census_extraction_viewer.py`
  - Convert to batch mode (or create separate tab)
- `src/rmcitecraft/main.py`
  - Add new tab to navigation

---

## Success Criteria

1. **Family ARK Extraction**: Successfully extract family member ARKs from person page table with relationship labels
2. **Duplicate Prevention**: No census image is processed twice (tracked by Image ARK)
3. **Edge Detection**: All line 1 and last-line entries are flagged with clear warnings
4. **Batch Processing**: Process multiple citations in a single session with checkpoint/resume
5. **Performance**: Process 10+ citations per minute with proper throttling
6. **UI**: Clear queue display with progress, warnings, and error handling

---

## Risk Mitigation

1. **FamilySearch Rate Limiting**: Use existing adaptive timeout and retry logic
2. **Page Structure Changes**: Abstract DOM selectors for easy updates
3. **Large Queue Sizes**: Implement pagination and lazy loading
4. **Browser Crashes**: Leverage existing crash recovery from Find a Grave
5. **Network Failures**: Checkpoint after each successful extraction

---

## Implementation Status

### Completed (2025-12-03)

1. **Migration 004**: `migrations/004_create_census_transcription_tables.sql`
   - `census_transcription_sessions` table
   - `census_transcription_items` table
   - `processed_census_images` table (duplicate prevention)
   - `census_transcription_checkpoints` table

2. **CensusTranscriptionRepository**: `src/rmcitecraft/database/census_transcription_repository.py`
   - Session CRUD operations
   - Item CRUD operations with bulk insert
   - Duplicate prevention via `is_image_processed()` / `mark_image_processed()`
   - Checkpoint operations for resume support
   - Analytics queries (summary, status distribution)
   - 22 unit tests passing

3. **Family Member ARK Extraction**: `_extract_family_member_arks_from_table()` in `familysearch_census_extractor.py`
   - Extracts names, ARKs, and relationships from person page table
   - Scans relationship labels (Father, Mother, Wife, Son, etc.)
   - Also checks "Household Members" section outside tables

4. **Edge Detection**: `src/rmcitecraft/services/census_edge_detection.py`
   - `detect_edge_conditions()` for first/last line warnings
   - Census-year-specific line limits (30 for 1950, 40 for 1940, etc.)
   - Relationship-aware warnings (non-head on line 1)
   - 18 unit tests passing

5. **Batch Service**: `src/rmcitecraft/services/census_transcription_batch.py`
   - `CensusTranscriptionBatchService` orchestration class
   - `build_transcription_queue()` from RootsMagic citations
   - `create_session_from_queue()` for session creation
   - `process_batch()` with progress callbacks and edge warnings
   - `resume_session()` for crash recovery

### Remaining

6. **Census Transcription UI Tab**: Batch operations interface
   - Queue display with multi-select
   - Progress tracking
   - Edge warning display
   - Session resume dialog

---

*Last Updated: 2025-12-03*
*Status: Implementation in Progress*
