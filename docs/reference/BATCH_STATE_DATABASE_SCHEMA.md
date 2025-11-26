# Batch State Database Schema Reference

## Overview

RMCitecraft uses a single SQLite database (`~/.rmcitecraft/batch_state.db`) to track batch processing state for both **Find a Grave** and **Census** workflows. This database is completely separate from the RootsMagic database to:

- Avoid schema modifications to genealogy data
- Enable safe deletion without affecting research
- Support independent backup/restore of processing state
- Track progress across application restarts

## Database Location

| Platform | Path |
|----------|------|
| macOS/Linux | `~/.rmcitecraft/batch_state.db` |
| Windows | `%USERPROFILE%\.rmcitecraft\batch_state.db` |

## Schema Version

Current schema version: **3**

Migrations are applied automatically on first use:
- Migration 001: Find a Grave tables
- Migration 002: Census tables (adds to existing database)
- Migration 003: Schema improvements (backfills batch_type, adds indexes, adds export_status and familysearch_ark columns)

## Tables

### Find a Grave Tables

#### `batch_sessions`

Tracks Find a Grave batch processing sessions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `session_id` | TEXT | PRIMARY KEY | Unique identifier (e.g., `batch_1732012345`) |
| `created_at` | TIMESTAMP | NOT NULL | When session was created |
| `started_at` | TIMESTAMP | | When processing began |
| `completed_at` | TIMESTAMP | | When processing finished |
| `status` | TEXT | NOT NULL, CHECK | Session state (see Status Values) |
| `total_items` | INTEGER | NOT NULL, DEFAULT 0 | Total items in batch |
| `completed_count` | INTEGER | NOT NULL, DEFAULT 0 | Successfully processed items |
| `error_count` | INTEGER | NOT NULL, DEFAULT 0 | Failed items |
| `config_snapshot` | TEXT | | JSON of settings used for this session |

**Status Values:** `queued`, `running`, `paused`, `completed`, `failed`

#### `batch_items`

Tracks individual Find a Grave memorial processing state.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY | Auto-increment row ID |
| `session_id` | TEXT | NOT NULL, FK | References `batch_sessions` |
| `person_id` | INTEGER | NOT NULL | RootsMagic PersonID (RIN) |
| `memorial_id` | TEXT | NOT NULL | Find a Grave memorial ID |
| `memorial_url` | TEXT | | Full Find a Grave URL |
| `person_name` | TEXT | | Display name for UI |
| `status` | TEXT | NOT NULL, CHECK | Item state (see Status Values) |
| `retry_count` | INTEGER | NOT NULL, DEFAULT 0 | Number of retry attempts |
| `last_attempt_at` | TIMESTAMP | | Timestamp of last processing attempt |
| `error_message` | TEXT | | Error details if status='error' |
| `extracted_data` | TEXT | | JSON snapshot (see Extracted Data Format) |
| `created_citation_id` | INTEGER | | RootsMagic CitationID if created |
| `created_source_id` | INTEGER | | RootsMagic SourceID if created |
| `created_burial_event_id` | INTEGER | | RootsMagic EventID if created |
| `downloaded_image_paths` | TEXT | | JSON array of local image paths |
| `created_at` | TIMESTAMP | NOT NULL | When item was queued |
| `updated_at` | TIMESTAMP | NOT NULL | Last modification time |

**Unique Constraint:** `(session_id, person_id)`

**Status Values:** `queued`, `extracting`, `extracted`, `creating_citation`, `created_citation`, `downloading_images`, `complete`, `error`

#### `batch_checkpoints`

Tracks resume points for interrupted Find a Grave sessions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `session_id` | TEXT | PRIMARY KEY, FK | References `batch_sessions` |
| `last_processed_item_id` | INTEGER | | Last `batch_items.id` processed |
| `last_processed_person_id` | INTEGER | | Last RootsMagic PersonID processed |
| `checkpoint_at` | TIMESTAMP | NOT NULL | When checkpoint was created |

---

### Census Tables

#### `census_batch_sessions`

Tracks Census batch processing sessions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `session_id` | TEXT | PRIMARY KEY | Unique identifier (e.g., `census_1950_20251125`) |
| `created_at` | TIMESTAMP | NOT NULL | When session was created |
| `started_at` | TIMESTAMP | | When processing began |
| `completed_at` | TIMESTAMP | | When processing finished |
| `status` | TEXT | NOT NULL, CHECK | Session state (see Status Values) |
| `total_items` | INTEGER | NOT NULL, DEFAULT 0 | Total items in batch |
| `completed_count` | INTEGER | NOT NULL, DEFAULT 0 | Successfully processed items |
| `error_count` | INTEGER | NOT NULL, DEFAULT 0 | Failed items |
| `census_year` | INTEGER | | Census year filter (e.g., 1900, 1950) |
| `config_snapshot` | TEXT | | JSON of settings used |

**Status Values:** `queued`, `running`, `paused`, `completed`, `failed`

#### `census_batch_items`

Tracks individual census citation processing state.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY | Auto-increment row ID |
| `session_id` | TEXT | NOT NULL, FK | References `census_batch_sessions` |
| `person_id` | INTEGER | NOT NULL | RootsMagic PersonID (RIN) |
| `person_name` | TEXT | | Display name for UI |
| `census_year` | INTEGER | NOT NULL | Census year (1790-1950) |
| `state` | TEXT | | US state (e.g., "Ohio", "Texas") |
| `county` | TEXT | | County name |
| `status` | TEXT | NOT NULL, CHECK | Item state (see Status Values) |
| `retry_count` | INTEGER | NOT NULL, DEFAULT 0 | Number of retry attempts |
| `last_attempt_at` | TIMESTAMP | | Timestamp of last processing attempt |
| `error_message` | TEXT | | Error details if status='error' |
| `extracted_data` | TEXT | | JSON snapshot (see Extracted Data Format) |
| `created_citation_id` | INTEGER | | RootsMagic CitationID if updated |
| `created_source_id` | INTEGER | | RootsMagic SourceID if updated |
| `created_event_id` | INTEGER | | RootsMagic EventID for census |
| `downloaded_image_paths` | TEXT | | JSON array of local image paths |
| `export_status` | TEXT | DEFAULT 'pending', CHECK | Export state: `pending`, `exported`, `skipped`, `error` (added in v3) |
| `familysearch_ark` | TEXT | | FamilySearch ARK identifier (e.g., `61903/1:1:6JJZ-JB42`) (added in v3) |
| `created_at` | TIMESTAMP | NOT NULL | When item was queued |
| `updated_at` | TIMESTAMP | NOT NULL | Last modification time |

**Unique Constraint:** `(session_id, person_id, census_year)`

**Status Values:** `queued`, `extracting`, `extracted`, `creating_citation`, `created_citation`, `downloading_images`, `complete`, `error`

#### `census_batch_checkpoints`

Tracks resume points for interrupted Census sessions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `session_id` | TEXT | PRIMARY KEY, FK | References `census_batch_sessions` |
| `last_processed_item_id` | INTEGER | | Last `census_batch_items.id` processed |
| `last_processed_person_id` | INTEGER | | Last RootsMagic PersonID processed |
| `checkpoint_at` | TIMESTAMP | NOT NULL | When checkpoint was created |

---

### Shared Tables

#### `performance_metrics`

Tracks operation timing for both Find a Grave and Census processing.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY | Auto-increment row ID |
| `timestamp` | TIMESTAMP | NOT NULL | When operation occurred |
| `operation` | TEXT | NOT NULL, CHECK | Operation type (see values) |
| `duration_ms` | INTEGER | NOT NULL | Operation duration in milliseconds |
| `success` | BOOLEAN | NOT NULL | Whether operation succeeded |
| `session_id` | TEXT | FK | Associated session (nullable) |
| `batch_type` | TEXT | NOT NULL, CHECK | `findagrave` or `census` (always set, backfilled in v3) |

**Operation Values:** `page_load`, `extraction`, `citation_creation`, `image_download`

#### `schema_version`

Tracks applied migrations.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `version` | INTEGER | PRIMARY KEY | Migration version number |
| `applied_at` | TIMESTAMP | NOT NULL | When migration was applied |

---

## Extracted Data JSON Formats

### Find a Grave `extracted_data`

```json
{
  "memorial_id": "12345678",
  "name": "John Smith",
  "birth_date": "1 Jan 1900",
  "birth_location": "Springfield, Illinois",
  "death_date": "15 Mar 1975",
  "death_location": "Chicago, Illinois",
  "burial_date": "18 Mar 1975",
  "cemetery_name": "Oak Hill Cemetery",
  "cemetery_location": "Chicago, Cook County, Illinois, USA",
  "cemetery_id": "98765",
  "plot_info": "Section A, Lot 123",
  "bio": "Brief biography text...",
  "photos": [
    {
      "url": "https://images.findagrave.com/...",
      "caption": "Headstone",
      "is_primary": true
    }
  ],
  "family_links": [
    {
      "name": "Jane Smith",
      "relationship": "spouse",
      "memorial_id": "12345679"
    }
  ]
}
```

### Census `extracted_data`

```json
{
  "census_year": 1950,
  "state": "Ohio",
  "county": "Franklin",
  "city_town": "Columbus",
  "enumeration_district": "94-529",
  "sheet": null,
  "stamp": "5643",
  "line": "42",
  "dwelling_number": null,
  "family_number": "125",
  "household_head": "John W Iams",
  "relationship_to_head": "Head",
  "person_name": "John Winder Iams",
  "age": "45",
  "birthplace": "Ohio",
  "occupation": "Accountant",
  "familysearch_url": "https://www.familysearch.org/ark:/61903/1:1:...",
  "familysearch_image_url": "https://www.familysearch.org/ark:/61903/3:1:...",
  "access_date": "25 November 2025"
}
```

---

## Indexes

### Find a Grave Indexes

| Index Name | Table | Columns | Purpose |
|------------|-------|---------|---------|
| `idx_batch_items_session` | batch_items | (session_id, status) | Filter items by session and status |
| `idx_batch_items_person` | batch_items | (person_id) | Find items by RootsMagic PersonID |

### Census Indexes

| Index Name | Table | Columns | Purpose |
|------------|-------|---------|---------|
| `idx_census_batch_items_session` | census_batch_items | (session_id, status) | Filter items by session and status |
| `idx_census_batch_items_person` | census_batch_items | (person_id) | Find items by RootsMagic PersonID |
| `idx_census_batch_items_year` | census_batch_items | (census_year) | Filter by census year |
| `idx_census_batch_items_state` | census_batch_items | (state) | Filter by state |
| `idx_census_batch_items_county` | census_batch_items | (state, county) | Filter by state+county |
| `idx_census_batch_items_export` | census_batch_items | (session_id, export_status) | Filter for export queries (added in v3) |

### Shared Indexes

| Index Name | Table | Columns | Purpose |
|------------|-------|---------|---------|
| `idx_performance_metrics_batch_type` | performance_metrics | (batch_type, timestamp DESC) | Filter metrics by batch type (added in v3) |
| `idx_performance_metrics_session` | performance_metrics | (session_id, operation, timestamp) | Session performance analysis |
| `idx_performance_metrics_recent` | performance_metrics | (timestamp DESC) | Recent metrics lookup |

---

## Status State Machine

### Item Status Transitions

```
queued ──────────────────────────────────────────────────────┐
   │                                                         │
   ▼                                                         │
extracting ──────► error (retry if retryable)               │
   │                  │                                      │
   ▼                  │ (max retries exceeded)               │
extracted             ▼                                      │
   │              error (final)                              │
   ▼                                                         │
creating_citation ──► error ─────────────────────────────────┤
   │                                                         │
   ▼                                                         │
created_citation                                             │
   │                                                         │
   ▼                                                         │
downloading_images ──► error ────────────────────────────────┤
   │                                                         │
   ▼                                                         │
complete ◄───────────────────────────────────────────────────┘
```

### Session Status Transitions

```
queued ──► running ──► paused ──► running ──► completed
              │                       │
              ▼                       ▼
           failed                  failed
```

---

## Relationship to RootsMagic Database

### ID References

The batch state database stores RootsMagic IDs for cross-reference:

| Batch State Column | RootsMagic Table | Purpose |
|--------------------|------------------|---------|
| `person_id` | PersonTable.PersonID | Link to person being processed |
| `created_citation_id` | CitationTable.CitationID | Track created/updated citation |
| `created_source_id` | SourceTable.SourceID | Track created/updated source |
| `created_burial_event_id` | EventTable.EventID | Track created burial event |
| `created_event_id` | EventTable.EventID | Track census event |

### Important Notes

1. **IDs may become stale** if RootsMagic database is restored from backup
2. **Clear batch state** after restoring RootsMagic database to avoid orphaned references
3. **Atomic transactions** ensure both databases stay synchronized during processing

---

## Maintenance

### Clear All Data

```bash
rm ~/.rmcitecraft/batch_state.db
```

The database will be recreated automatically on next use.

### Query Examples

**Find incomplete sessions:**
```sql
SELECT session_id, status, total_items, completed_count
FROM census_batch_sessions
WHERE status IN ('running', 'paused', 'queued');
```

**Get error summary:**
```sql
SELECT error_message, COUNT(*) as count
FROM census_batch_items
WHERE status = 'error'
GROUP BY error_message
ORDER BY count DESC;
```

**Performance by operation:**
```sql
SELECT
    operation,
    batch_type,
    AVG(duration_ms) as avg_ms,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate
FROM performance_metrics
WHERE timestamp > datetime('now', '-7 days')
GROUP BY operation, batch_type;
```

---

## Related Documentation

- [Census Batch Processing Architecture](./CENSUS_BATCH_PROCESSING_ARCHITECTURE.md)
- [Find a Grave Batch Processing Architecture](../architecture/BATCH_PROCESSING_ARCHITECTURE.md)
- [RootsMagic Database Schema](./schema-reference.md)

---

**Last Updated:** 2025-11-26
**Schema Version:** 2
