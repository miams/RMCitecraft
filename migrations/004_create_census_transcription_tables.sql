-- Migration 004: Create Census Transcription batch processing tables
-- Purpose: Track batch extraction of census data from FamilySearch into census.db
-- This is DIFFERENT from census_batch_* tables which track Citation Batch Processing
-- (updating existing RootsMagic citations). This tracks Transcription Processing
-- (extracting data from FamilySearch web pages into census.db for review).

-- =============================================================================
-- Census Transcription Sessions
-- =============================================================================
-- One session = one batch of citations to extract from FamilySearch
CREATE TABLE IF NOT EXISTS census_transcription_sessions (
    session_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    status TEXT DEFAULT 'queued' CHECK(status IN ('queued', 'running', 'paused', 'completed', 'failed')),
    total_items INTEGER DEFAULT 0,
    completed_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    skipped_count INTEGER DEFAULT 0,  -- Skipped due to duplicates
    edge_warning_count INTEGER DEFAULT 0,  -- Items needing page boundary review
    census_year INTEGER,  -- Filter: 1790-1950 or NULL for all years
    state_filter TEXT,  -- Optional state filter
    config_snapshot TEXT  -- JSON of settings used
);

-- =============================================================================
-- Census Transcription Items
-- =============================================================================
-- One item = one RootsMagic citation to process
CREATE TABLE IF NOT EXISTS census_transcription_items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES census_transcription_sessions(session_id) ON DELETE CASCADE,

    -- RootsMagic source data
    rmtree_citation_id INTEGER NOT NULL,
    rmtree_person_id INTEGER,  -- Head of household RIN (primary person on citation)
    person_name TEXT,
    census_year INTEGER NOT NULL,
    state TEXT,
    county TEXT,

    -- FamilySearch references
    familysearch_ark TEXT,  -- Person ARK from citation (1:1:XXXX format)
    image_ark TEXT,         -- Image ARK (3:1:XXXX format) - extracted during processing

    -- Processing state
    status TEXT DEFAULT 'queued' CHECK(status IN (
        'queued',      -- Waiting to be processed
        'extracting',  -- Currently extracting from FamilySearch
        'extracted',   -- Data extracted to census.db
        'complete',    -- Fully processed
        'error',       -- Failed with error
        'skipped'      -- Skipped (duplicate image, etc.)
    )),
    skip_reason TEXT,  -- Why item was skipped (if status='skipped')
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    last_attempt_at TEXT,

    -- Results (populated after extraction)
    census_db_person_id INTEGER,  -- Primary person ID in census.db
    census_db_page_id INTEGER,    -- Page ID in census.db
    household_extracted_count INTEGER DEFAULT 0,  -- Number of household members extracted
    extraction_method TEXT,  -- 'table_arks', 'sls_api', 'mixed'

    -- Edge detection flags (for page boundary warnings)
    line_number INTEGER,
    first_line_flag INTEGER DEFAULT 0,  -- 1 if person is on line 1
    last_line_flag INTEGER DEFAULT 0,   -- 1 if person is on last line for census year
    edge_warning_message TEXT,  -- Human-readable warning if applicable

    UNIQUE(session_id, rmtree_citation_id)
);

-- =============================================================================
-- Processed Census Images (Duplicate Prevention)
-- =============================================================================
-- Tracks which census images have been fully processed to avoid re-extraction
CREATE TABLE IF NOT EXISTS processed_census_images (
    image_ark TEXT PRIMARY KEY,      -- Image ARK (3:1:XXXX format)
    census_year INTEGER NOT NULL,
    state TEXT,
    county TEXT,
    enumeration_district TEXT,
    sheet_number TEXT,
    stamp_number TEXT,

    -- Processing info
    first_processed_at TEXT NOT NULL,
    last_processed_at TEXT,
    first_session_id TEXT,           -- Session that first processed this image
    total_persons_extracted INTEGER DEFAULT 0,

    -- Link to census.db
    census_db_page_id INTEGER        -- page_id in census.db census_page table
);

-- =============================================================================
-- Transcription Checkpoints (Resume Support)
-- =============================================================================
CREATE TABLE IF NOT EXISTS census_transcription_checkpoints (
    session_id TEXT PRIMARY KEY REFERENCES census_transcription_sessions(session_id) ON DELETE CASCADE,
    last_processed_item_id INTEGER,
    last_processed_citation_id INTEGER,
    checkpoint_at TEXT NOT NULL
);

-- =============================================================================
-- Indexes for Efficient Querying
-- =============================================================================

-- Session queries
CREATE INDEX IF NOT EXISTS idx_transcription_sessions_status
    ON census_transcription_sessions(status, created_at DESC);

-- Item queries by session and status
CREATE INDEX IF NOT EXISTS idx_transcription_items_session
    ON census_transcription_items(session_id, status);

-- Item queries by citation (for duplicate detection)
CREATE INDEX IF NOT EXISTS idx_transcription_items_citation
    ON census_transcription_items(rmtree_citation_id);

-- Item queries by image ARK (for grouping citations by page)
CREATE INDEX IF NOT EXISTS idx_transcription_items_image
    ON census_transcription_items(image_ark);

-- Edge warning queries
CREATE INDEX IF NOT EXISTS idx_transcription_items_edge
    ON census_transcription_items(session_id, first_line_flag, last_line_flag)
    WHERE first_line_flag = 1 OR last_line_flag = 1;

-- Processed images by year/location (for analytics)
CREATE INDEX IF NOT EXISTS idx_processed_images_location
    ON processed_census_images(census_year, state, county);

-- =============================================================================
-- Update schema version
-- =============================================================================
INSERT OR REPLACE INTO schema_version (version, applied_at)
VALUES (4, datetime('now'));
