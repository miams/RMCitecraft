-- Migration 001: Create batch state tracking tables
-- Purpose: Track Find a Grave batch processing sessions for resume capability
-- Separate database from RootsMagic to avoid confusion

-- Batch sessions table
CREATE TABLE IF NOT EXISTS batch_sessions (
    session_id TEXT PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'paused', 'completed', 'failed')),
    total_items INTEGER NOT NULL DEFAULT 0,
    completed_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    config_snapshot TEXT  -- JSON of settings used
);

-- Individual batch items tracking
CREATE TABLE IF NOT EXISTS batch_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES batch_sessions(session_id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL,
    memorial_id TEXT NOT NULL,
    memorial_url TEXT,
    person_name TEXT,
    status TEXT NOT NULL CHECK(status IN (
        'queued', 'extracting', 'extracted', 'creating_citation',
        'created_citation', 'downloading_images', 'complete', 'error'
    )),
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMP,
    error_message TEXT,
    extracted_data TEXT,  -- JSON snapshot of FindAGraveData
    created_citation_id INTEGER,
    created_source_id INTEGER,
    created_burial_event_id INTEGER,
    downloaded_image_paths TEXT,  -- JSON array of paths
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    UNIQUE(session_id, person_id)
);

-- Checkpoint tracking for efficient resume
CREATE TABLE IF NOT EXISTS batch_checkpoints (
    session_id TEXT PRIMARY KEY REFERENCES batch_sessions(session_id) ON DELETE CASCADE,
    last_processed_item_id INTEGER,
    last_processed_person_id INTEGER,
    checkpoint_at TIMESTAMP NOT NULL
);

-- Performance metrics for adaptive timeout
CREATE TABLE IF NOT EXISTS performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP NOT NULL,
    operation TEXT NOT NULL CHECK(operation IN (
        'page_load', 'extraction', 'citation_creation', 'image_download'
    )),
    duration_ms INTEGER NOT NULL,
    success BOOLEAN NOT NULL,
    session_id TEXT REFERENCES batch_sessions(session_id) ON DELETE SET NULL
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_batch_items_session
    ON batch_items(session_id, status);

CREATE INDEX IF NOT EXISTS idx_batch_items_person
    ON batch_items(person_id);

CREATE INDEX IF NOT EXISTS idx_performance_metrics_session
    ON performance_metrics(session_id, operation, timestamp);

CREATE INDEX IF NOT EXISTS idx_performance_metrics_recent
    ON performance_metrics(timestamp DESC);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL
);

INSERT OR REPLACE INTO schema_version (version, applied_at)
VALUES (1, datetime('now'));
