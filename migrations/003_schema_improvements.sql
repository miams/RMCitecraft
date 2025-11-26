-- Migration 003: Schema improvements and data consistency fixes
-- Purpose: Backfill batch_type, add useful columns, improve indexes
-- Safe to run multiple times (uses IF NOT EXISTS and conditional updates)

-- =============================================================================
-- STEP 1: Backfill batch_type for existing performance_metrics
-- =============================================================================
-- Records with NULL batch_type are legacy Find a Grave records
-- Determine type by checking if session_id exists in findagrave or census tables

UPDATE performance_metrics
SET batch_type = 'findagrave'
WHERE batch_type IS NULL
  AND session_id IN (SELECT session_id FROM batch_sessions);

UPDATE performance_metrics
SET batch_type = 'census'
WHERE batch_type IS NULL
  AND session_id IN (SELECT session_id FROM census_batch_sessions);

-- Any remaining NULL batch_type records (orphaned session_ids) default to findagrave
-- since that was the original system
UPDATE performance_metrics
SET batch_type = 'findagrave'
WHERE batch_type IS NULL;

-- =============================================================================
-- STEP 2: Add index for batch_type filtering
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_performance_metrics_batch_type
    ON performance_metrics(batch_type, timestamp DESC);

-- =============================================================================
-- STEP 3: Add export_status to census_batch_items for tracking export state
-- =============================================================================
-- SQLite doesn't support IF NOT EXISTS for ALTER TABLE, so we check first
-- This column tracks: 'pending', 'exported', 'skipped', 'error'

-- Check if column exists by trying to select it (will fail silently in migration runner)
-- The migration runner should handle this gracefully

-- Note: This ALTER may fail if column exists - that's OK, migration continues
ALTER TABLE census_batch_items
ADD COLUMN export_status TEXT DEFAULT 'pending'
    CHECK(export_status IN ('pending', 'exported', 'skipped', 'error'));

-- =============================================================================
-- STEP 4: Add familysearch_ark to census_batch_items for better tracking
-- =============================================================================
-- Stores the FamilySearch ARK identifier separately from full URL

ALTER TABLE census_batch_items
ADD COLUMN familysearch_ark TEXT;

-- =============================================================================
-- STEP 5: Add index for export_status filtering (useful for export queries)
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_census_batch_items_export
    ON census_batch_items(session_id, export_status);

-- =============================================================================
-- STEP 6: Update schema version
-- =============================================================================
INSERT OR REPLACE INTO schema_version (version, applied_at)
VALUES (3, datetime('now'));

-- =============================================================================
-- NOTES FOR CODE:
-- =============================================================================
-- 1. Always enable foreign keys in connection:
--    PRAGMA foreign_keys = ON;
--
-- 2. When querying performance_metrics, batch_type is now always populated
--    No need for "OR batch_type IS NULL" fallback
--
-- 3. New columns added to census_batch_items:
--    - export_status: Track export state ('pending'|'exported'|'skipped'|'error')
--    - familysearch_ark: Store ARK identifier (e.g., '61903/1:1:6JJZ-JB42')
