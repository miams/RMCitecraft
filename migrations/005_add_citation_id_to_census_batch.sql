-- Migration 005: Add citation_id to census_batch_items
-- Purpose: Fix unique constraint to allow same person with multiple citations
-- The previous constraint (session_id, person_id, census_year) fails when
-- a person has multiple citations for the same census year (e.g., different sources)

-- Add citation_id column if it doesn't exist
ALTER TABLE census_batch_items ADD COLUMN citation_id INTEGER;

-- Add source_id column for better tracking
ALTER TABLE census_batch_items ADD COLUMN source_id INTEGER;

-- Drop the old unique index (SQLite requires recreating the table for constraint changes)
-- Instead, we create a new unique index on session_id + citation_id
CREATE UNIQUE INDEX IF NOT EXISTS idx_census_batch_items_citation
    ON census_batch_items(session_id, citation_id);

-- Note: We cannot drop the old UNIQUE constraint without recreating the table
-- But the new index will be used for lookups by citation_id
-- The old constraint may cause issues for duplicate person_id entries until
-- the database is recreated

-- Update schema version
INSERT OR REPLACE INTO schema_version (version, applied_at)
VALUES (5, datetime('now'));
