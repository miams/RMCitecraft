-- Migration 002: Create Census batch state tracking tables
-- Purpose: Track Census batch processing sessions with census-specific metadata
-- Separate from Find a Grave batches for domain-specific analytics

-- Census batch sessions table
CREATE TABLE IF NOT EXISTS census_batch_sessions (
    session_id TEXT PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'paused', 'completed', 'failed')),
    total_items INTEGER NOT NULL DEFAULT 0,
    completed_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    census_year INTEGER,  -- Census year filter applied (e.g., 1900)
    config_snapshot TEXT  -- JSON of settings used
);

-- Individual census batch items tracking
CREATE TABLE IF NOT EXISTS census_batch_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES census_batch_sessions(session_id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL,
    person_name TEXT,
    census_year INTEGER NOT NULL,  -- 1790-1950
    state TEXT,  -- US state abbreviation (e.g., "OH", "TX")
    county TEXT,  -- County name
    citation_id INTEGER,  -- RootsMagic CitationID (for unique tracking)
    source_id INTEGER,  -- RootsMagic SourceID
    status TEXT NOT NULL CHECK(status IN (
        'queued', 'extracting', 'extracted', 'creating_citation',
        'created_citation', 'downloading_images', 'complete', 'error'
    )),
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMP,
    error_message TEXT,
    extracted_data TEXT,  -- JSON snapshot of census data
    created_citation_id INTEGER,
    created_source_id INTEGER,
    created_event_id INTEGER,  -- Census event ID
    downloaded_image_paths TEXT,  -- JSON array of paths
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

-- Checkpoint tracking for efficient resume
CREATE TABLE IF NOT EXISTS census_batch_checkpoints (
    session_id TEXT PRIMARY KEY REFERENCES census_batch_sessions(session_id) ON DELETE CASCADE,
    last_processed_item_id INTEGER,
    last_processed_person_id INTEGER,
    checkpoint_at TIMESTAMP NOT NULL
);

-- Add batch_type column to performance_metrics for distinguishing batch types
ALTER TABLE performance_metrics
ADD COLUMN batch_type TEXT CHECK(batch_type IN ('findagrave', 'census'));

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_census_batch_items_session
    ON census_batch_items(session_id, status);

CREATE INDEX IF NOT EXISTS idx_census_batch_items_person
    ON census_batch_items(person_id);

CREATE INDEX IF NOT EXISTS idx_census_batch_items_year
    ON census_batch_items(census_year);

CREATE INDEX IF NOT EXISTS idx_census_batch_items_state
    ON census_batch_items(state);

CREATE INDEX IF NOT EXISTS idx_census_batch_items_county
    ON census_batch_items(state, county);

CREATE INDEX IF NOT EXISTS idx_census_batch_items_citation
    ON census_batch_items(session_id, citation_id);

-- Update schema version
INSERT OR REPLACE INTO schema_version (version, applied_at)
VALUES (2, datetime('now'));
