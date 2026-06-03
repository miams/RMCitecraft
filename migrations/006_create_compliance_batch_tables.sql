-- Migration 006: Create compliance batch tracking tables
-- Created: 2026-01-23
-- Purpose: Track citation compliance fixes and proposals for audit trail

-- Compliance batch sessions
CREATE TABLE IF NOT EXISTS compliance_sessions (
    id INTEGER PRIMARY KEY,
    session_id TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'active',  -- 'active', 'completed', 'cancelled'
    description TEXT,
    source_type_filter TEXT,
    issue_type_filter TEXT,
    total_sources INTEGER DEFAULT 0,
    sources_fixed INTEGER DEFAULT 0,
    sources_skipped INTEGER DEFAULT 0,
    sources_errored INTEGER DEFAULT 0
);

-- Individual compliance batch items (one per source per session)
CREATE TABLE IF NOT EXISTS compliance_batch_items (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    source_id INTEGER NOT NULL,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    issue_type TEXT NOT NULL,  -- 'P1_DOUBLE_SPACES', 'P2_MISSING_PERIOD', etc.
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'approved', 'applied', 'rejected', 'error'

    -- Original values
    original_footnote TEXT,
    original_short_footnote TEXT,
    original_bibliography TEXT,

    -- Proposed values
    proposed_footnote TEXT,
    proposed_short_footnote TEXT,
    proposed_bibliography TEXT,

    -- Transformation metadata
    confidence_score REAL,
    transformation_notes TEXT,  -- JSON array of notes

    -- Audit trail
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    applied_at TIMESTAMP,
    error_message TEXT,
    review_notes TEXT,

    UNIQUE(session_id, source_id),
    FOREIGN KEY (session_id) REFERENCES compliance_sessions(session_id)
);

-- Index for efficient queries
CREATE INDEX IF NOT EXISTS idx_compliance_items_session ON compliance_batch_items(session_id);
CREATE INDEX IF NOT EXISTS idx_compliance_items_status ON compliance_batch_items(status);
CREATE INDEX IF NOT EXISTS idx_compliance_items_source_type ON compliance_batch_items(source_type);
CREATE INDEX IF NOT EXISTS idx_compliance_items_issue_type ON compliance_batch_items(issue_type);

-- Compliance fix history (for rollback capability)
CREATE TABLE IF NOT EXISTS compliance_fix_history (
    id INTEGER PRIMARY KEY,
    batch_item_id INTEGER NOT NULL,
    source_id INTEGER NOT NULL,
    field_name TEXT NOT NULL,  -- 'Footnote', 'ShortFootnote', 'Bibliography'
    old_value TEXT,
    new_value TEXT,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rolled_back_at TIMESTAMP,
    FOREIGN KEY (batch_item_id) REFERENCES compliance_batch_items(id)
);

CREATE INDEX IF NOT EXISTS idx_fix_history_source ON compliance_fix_history(source_id);
CREATE INDEX IF NOT EXISTS idx_fix_history_batch_item ON compliance_fix_history(batch_item_id);

-- Compliance analysis snapshots (for tracking progress over time)
CREATE TABLE IF NOT EXISTS compliance_snapshots (
    id INTEGER PRIMARY KEY,
    snapshot_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_sources INTEGER NOT NULL,
    compliant_sources INTEGER NOT NULL,
    sources_with_issues INTEGER NOT NULL,
    p1_double_spaces INTEGER DEFAULT 0,
    p2_missing_period INTEGER DEFAULT 0,
    p3_fn_equals_sf INTEGER DEFAULT 0,
    p4_fn_equals_bib INTEGER DEFAULT 0,
    p5_missing_access_date INTEGER DEFAULT 0,
    p6_empty_citations INTEGER DEFAULT 0,
    details_json TEXT  -- Full breakdown by source type
);
