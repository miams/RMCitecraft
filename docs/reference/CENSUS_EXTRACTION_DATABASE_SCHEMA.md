---
priority: essential
topics: [database, census, citation, batch, testing]
---

# Census Extraction Database Schema Reference

## Overview

The Census Extraction Database (`~/.rmcitecraft/census.db`) stores detailed census transcription data extracted from FamilySearch using Playwright browser automation. This database is **separate from both** the RootsMagic database and the batch state database to:

- Store comprehensive census data beyond what RootsMagic citations capture
- Support all census years (1790-1950) with varying field sets via EAV pattern
- Enable data quality tracking and human verification workflows
- Provide cross-database linking for research correlation
- Support future AI transcription from census images

### Key Differences from Batch State Database

| Database | Purpose | Data Lifetime |
|----------|---------|---------------|
| `batch_state.db` | Track processing workflow state | Ephemeral - safe to delete |
| `census.db` | Store extracted census transcriptions | Persistent research data |

## Database Location

| Platform | Path |
|----------|------|
| macOS/Linux | `~/.rmcitecraft/census.db` |
| Windows | `%USERPROFILE%\.rmcitecraft\census.db` |

## Schema Version

Current schema version: **3**

The schema is auto-created on first use by `CensusExtractionRepository`.

**Version History:**
- v1: Initial schema with extraction, page, person, field, quality tables
- v2: Added `field_history` table for version control of field edits
- v3: Added `match_attempt`, `extraction_gap`, and `gap_pattern` tables for extraction analytics

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                census.db                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐     │
│  │ extraction_batch │────►│   census_page    │◄────│  match_attempt   │     │
│  │  (session info)  │     │ (page metadata)  │     │ (match tracking) │     │
│  └────────┬─────────┘     └────────┬─────────┘     └──────────────────┘     │
│           │                        │                                         │
│           │                        │ 1:N                                     │
│           │                        ▼                                         │
│           │              ┌──────────────────┐                               │
│           │              │  census_person   │◄───┐                          │
│           │              │ (core fields)    │    │                          │
│           │              └────────┬─────────┘    │                          │
│           │                       │              │                          │
│           │      ┌────────────────┼──────────────┼───────┐                  │
│           │      │                │              │       │                  │
│           │      ▼                ▼              ▼       │                  │
│           │  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐│
│           │  │census_person_field│ │census_relationship│ │   rmtree_link   ││
│           │  │    (EAV store)    │ │(family connections)│ │(RootsMagic IDs) ││
│           │  └──────────────────┘ └──────────────────┘ └──────────────────┘│
│           │          │                                                       │
│           │          ▼                                                       │
│           │  ┌──────────────────┐       ┌──────────────────┐                │
│           │  │  field_quality   │       │  field_history   │                │
│           │  │(optional QA data)│       │(version control) │                │
│           │  └──────────────────┘       └──────────────────┘                │
│           │                                                                  │
│           │  ┌──────────────────┐       ┌──────────────────┐                │
│           └─►│  extraction_gap  │──────►│   gap_pattern    │                │
│              │ (missing data)   │       │ (pattern catalog)│                │
│              └──────────────────┘       └──────────────────┘                │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Tables

### `extraction_batch`

Tracks extraction sessions (one per FamilySearch browsing session).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `batch_id` | INTEGER | PRIMARY KEY | Auto-increment batch ID |
| `started_at` | TEXT | NOT NULL | ISO timestamp when extraction started |
| `completed_at` | TEXT | | ISO timestamp when extraction finished |
| `source` | TEXT | NOT NULL | Data source: `familysearch`, `ancestry`, `ai_transcription` |
| `extractor_version` | TEXT | NOT NULL | Version of extraction code used |
| `notes` | TEXT | | User-provided notes about this batch |

---

### `census_page`

Census page-level metadata shared by all persons on the same page.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `page_id` | INTEGER | PRIMARY KEY | Auto-increment page ID |
| `batch_id` | INTEGER | FK | References `extraction_batch` |
| `census_year` | INTEGER | NOT NULL | Census year (1790-1950) |
| `state` | TEXT | NOT NULL | US state name |
| `county` | TEXT | NOT NULL | County name |
| `township_city` | TEXT | | Township or city name |
| `enumeration_district` | TEXT | | ED number (1880+) |
| `supervisor_district` | TEXT | | Supervisor district |
| `sheet_number` | TEXT | | Sheet number (1880-1940) |
| `sheet_letter` | TEXT | | Sheet side: `A` or `B` |
| `page_number` | TEXT | | Page number (1790-1870, 1950) |
| `stamp_number` | TEXT | | Stamp number (1950 terminology) |
| `enumeration_date` | TEXT | | Date of enumeration |
| `enumerator_name` | TEXT | | Name of census enumerator |
| `familysearch_film` | TEXT | | FamilySearch film number |
| `familysearch_image_url` | TEXT | | URL to census image |
| `extracted_at` | TEXT | NOT NULL | ISO timestamp of extraction |

**Indexes:**
- `idx_census_page_year` on `(census_year)` - Filter by year
- `idx_census_page_location` on `(state, county)` - Geographic queries
- `idx_census_page_ed` on `(enumeration_district)` - ED lookup

---

### `census_person`

Core person fields present in most census years (1790-1950).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `person_id` | INTEGER | PRIMARY KEY | Auto-increment person ID |
| `page_id` | INTEGER | NOT NULL, FK | References `census_page` |
| `line_number` | INTEGER | | Line number on census form |
| `dwelling_number` | INTEGER | | Dwelling number |
| `family_number` | INTEGER | | Family number |
| `household_id` | TEXT | | FamilySearch household ID |
| `full_name` | TEXT | NOT NULL | Complete name as transcribed |
| `given_name` | TEXT | | First/middle names |
| `surname` | TEXT | | Family name |
| `name_suffix` | TEXT | | Jr, Sr, II, III, etc. |
| `relationship_to_head` | TEXT | | Relationship to household head |
| `sex` | TEXT | | M or F |
| `race` | TEXT | | Race/color as recorded |
| `age` | INTEGER | | Age in years |
| `age_months` | INTEGER | | Age in months (infants) |
| `marital_status` | TEXT | | Single, Married, Widowed, Divorced |
| `birthplace` | TEXT | | State/country of birth |
| `birthplace_father` | TEXT | | Father's birthplace |
| `birthplace_mother` | TEXT | | Mother's birthplace |
| `occupation` | TEXT | | Occupation (1850+) |
| `industry` | TEXT | | Industry/employer |
| `worker_class` | TEXT | | P=Private, G=Government, O=Own |
| `familysearch_ark` | TEXT | | FamilySearch ARK URL |
| `familysearch_person_id` | TEXT | | FamilySearch internal ID |
| `extracted_at` | TEXT | NOT NULL | ISO timestamp of extraction |
| `is_target_person` | INTEGER | | 1 if specifically searched for |

**Indexes:**
- `idx_census_person_page` on `(page_id)` - Find all persons on page
- `idx_census_person_name` on `(surname, given_name)` - Name search
- `idx_census_person_ark` on `(familysearch_ark)` - Deduplication lookup
- `idx_census_person_line` on `(page_id, line_number)` - Ordered listing

---

### `census_person_field`

Year-specific fields using Entity-Attribute-Value (EAV) pattern. This allows storing census-year-specific fields (e.g., 1950 income, 1940 social security) without schema changes.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `field_id` | INTEGER | PRIMARY KEY | Auto-increment field ID |
| `person_id` | INTEGER | NOT NULL, FK | References `census_person` |
| `field_name` | TEXT | NOT NULL | Normalized field name (see Field Names) |
| `field_value` | TEXT | | Field value as string |
| `field_type` | TEXT | | Type hint: `string`, `integer`, `boolean` |
| `familysearch_label` | TEXT | | Original label from FamilySearch |

**Indexes:**
- `idx_person_field_person` on `(person_id)` - Get all fields for person
- `idx_person_field_name` on `(field_name)` - Query by field type

**Common Extended Fields:**

| Field Name | Census Years | Description |
|------------|--------------|-------------|
| `birth_year` | All | Calculated/estimated birth year |
| `event_date` | All | Census enumeration date |
| `event_place` | All | Full event location string |
| `income` | 1940, 1950 | Income amount |
| `weeks_worked` | 1940, 1950 | Weeks worked last year |
| `hours_worked` | 1940, 1950 | Hours worked last week |
| `same_house_1949` | 1950 | Lived in same house in 1949 |
| `veteran` | 1910-1950 | Veteran status |
| `veteran_ww1` | 1930-1950 | WWI veteran |
| `veteran_ww2` | 1950 | WWII veteran |
| `attended_school` | 1850-1950 | School attendance |
| `grade_completed` | 1940, 1950 | Highest grade completed |
| `citizenship_status` | 1900-1950 | Naturalization status |
| `children_born` | 1900-1950 | Number of children (women) |

---

### `census_relationship`

Relationships between census persons (e.g., spouse, children on same page).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `relationship_id` | INTEGER | PRIMARY KEY | Auto-increment ID |
| `person_id` | INTEGER | NOT NULL, FK | The person |
| `related_person_id` | INTEGER | FK | Related person (if in database) |
| `related_person_name` | TEXT | | Name if not in database |
| `relationship_type` | TEXT | NOT NULL | spouse, child, parent, sibling |

**Index:**
- `idx_relationship_person` on `(person_id)` - Find relationships

---

### `rmtree_link`

Links between census extractions and RootsMagic database records.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `link_id` | INTEGER | PRIMARY KEY | Auto-increment ID |
| `census_person_id` | INTEGER | NOT NULL, FK | References `census_person` |
| `rmtree_person_id` | INTEGER | | RootsMagic PersonID (RIN) |
| `rmtree_citation_id` | INTEGER | | RootsMagic CitationID |
| `rmtree_event_id` | INTEGER | | RootsMagic EventID |
| `rmtree_database` | TEXT | | Path to .rmtree file |
| `match_confidence` | REAL | | 0.0-1.0 confidence score |
| `match_method` | TEXT | | How match was determined |
| `linked_at` | TEXT | NOT NULL | ISO timestamp of linking |

**Match Methods:**
- `url_match` - Matched via FamilySearch ARK URL in citation (most common)
- `auto_fuzzy_v2` - Automatic fuzzy name matching using Hungarian algorithm
- `migration_from_validation` - Migrated from legacy batch validation
- `manual_link` - User manually linked records from suggestions
- `user_confirmed` - User confirmed a suggested match
- `user_rejected` - User explicitly rejected the person (not in family tree)
- `not_in_rmtree` - Confirmed person does not exist in RootsMagic database
- `manual_correction` - User manually corrected or updated the RIN
- `unlinked_orphan` - Link previously existed but RIN removed
- `name_match` (legacy) - Matched by name and census year

**Indexes:**
- `idx_rmtree_link_census` on `(census_person_id)` - Find links for extraction
- `idx_rmtree_link_rmtree` on `(rmtree_person_id)` - Find extractions for RM person
- `idx_rmtree_link_citation` on `(rmtree_citation_id)` - Find by citation

---

### `field_quality`

Optional per-field quality assessment for transcription verification.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `quality_id` | INTEGER | PRIMARY KEY | Auto-increment ID |
| `person_field_id` | INTEGER | FK | Links to EAV field (optional) |
| `person_id` | INTEGER | FK | Links to person (for core fields) |
| `field_name` | TEXT | NOT NULL | Field being assessed |
| `confidence_score` | REAL | | 0.0-1.0 transcription confidence |
| `source_legibility` | TEXT | | clear, faded, damaged, illegible |
| `transcription_note` | TEXT | | Notes about interpretation |
| `ai_confidence` | REAL | | AI model confidence (if AI-transcribed) |
| `human_verified` | INTEGER | | 1 if human verified |
| `verified_by` | TEXT | | Who verified |
| `verified_at` | TEXT | | When verified |

**Indexes:**
- `idx_field_quality_person` on `(person_id)` - Quality by person
- `idx_field_quality_field` on `(person_field_id)` - Quality by field

---

### `field_history`

Version control for field edits. Tracks the original FamilySearch-extracted value and all subsequent manual edits with timestamps.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `history_id` | INTEGER | PRIMARY KEY | Auto-increment ID |
| `person_id` | INTEGER | NOT NULL, FK | References `census_person` |
| `field_name` | TEXT | NOT NULL | Name of the field being tracked |
| `field_value` | TEXT | | The value at this version |
| `field_source` | TEXT | NOT NULL | Source: `familysearch`, `manual_edit`, `ai_transcription` |
| `is_original` | INTEGER | | 1 if this is the original imported value |
| `created_at` | TEXT | NOT NULL | ISO timestamp when this version was created |
| `created_by` | TEXT | | User who made the edit (blank for system imports) |

**Indexes:**
- `idx_field_history_person` on `(person_id)` - Get all history for person
- `idx_field_history_field` on `(person_id, field_name)` - Get history for specific field

**Field Sources:**
- `familysearch` - Original value extracted from FamilySearch
- `manual_edit` - User manually edited the value
- `ai_transcription` - AI transcription from census image

**Usage Pattern:**

When a field is edited:
1. If no history exists for the field, create an "original" entry with `is_original=1`
2. Create a new entry with the new value and `is_original=0`

This allows retrieving the original FamilySearch value at any time, even after multiple edits.

---

### `schema_version`

Tracks schema version for migrations.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `version` | INTEGER | PRIMARY KEY | Schema version number |
| `applied_at` | TEXT | NOT NULL | When version was applied |

---

### `match_attempt`

Records each attempt to match FamilySearch persons to RootsMagic during batch processing. Used for analytics and debugging match algorithm performance.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `attempt_id` | INTEGER | PRIMARY KEY | Auto-increment ID |
| `batch_id` | INTEGER | FK | References `extraction_batch` |
| `page_id` | INTEGER | FK | References `census_page` |
| `source_id` | INTEGER | | RootsMagic SourceID being processed |
| `fs_full_name` | TEXT | NOT NULL | FamilySearch full name |
| `fs_given_name` | TEXT | | FamilySearch given name |
| `fs_surname` | TEXT | | FamilySearch surname |
| `fs_ark` | TEXT | | FamilySearch ARK URL |
| `fs_line_number` | INTEGER | | Line number on census form |
| `fs_relationship` | TEXT | | Relationship to household head |
| `fs_age` | TEXT | | Age as recorded |
| `fs_birthplace` | TEXT | | Birthplace |
| `fs_household_head_name` | TEXT | | Name of household head |
| `match_status` | TEXT | NOT NULL | `matched`, `skipped`, `review_needed` |
| `matched_rm_person_id` | INTEGER | | RootsMagic PersonID if matched |
| `matched_census_person_id` | INTEGER | FK | References `census_person` if matched |
| `skip_reason` | TEXT | | Why skipped (e.g., `no_rin_candidates`, `below_threshold`) |
| `best_candidate_rm_id` | INTEGER | | Best candidate RIN even if not matched |
| `best_candidate_name` | TEXT | | Name of best candidate |
| `best_candidate_score` | REAL | | Score of best candidate (0.0-1.0) |
| `best_match_method` | TEXT | | How best candidate was found |
| `candidates_json` | TEXT | | JSON array of all candidates considered |
| `attempted_at` | TEXT | NOT NULL | ISO timestamp of attempt |

**Match Status Values:**
- `matched` - Successfully matched to RootsMagic person
- `skipped` - Skipped due to skip_reason (e.g., no candidates, low confidence)
- `review_needed` - Multiple candidates or ambiguous match; needs manual review

**Indexes:**
- `idx_match_attempt_status` on `(match_status)` - Filter by result
- `idx_match_attempt_source` on `(source_id)` - Find attempts by source
- `idx_match_attempt_fs_ark` on `(fs_ark)` - Lookup by ARK
- `idx_match_attempt_batch` on `(batch_id)` - Find attempts by batch
- `idx_match_attempt_skip_reason` on `(skip_reason)` - Analyze skip patterns

---

### `extraction_gap`

Tracks missing data, failed matches, and data quality issues detected during extraction. Used to identify systematic problems and prioritize improvements.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `gap_id` | INTEGER | PRIMARY KEY | Auto-increment ID |
| `batch_id` | INTEGER | FK | References `extraction_batch` |
| `source_id` | INTEGER | | RootsMagic SourceID |
| `gap_type` | TEXT | NOT NULL | `missing_person`, `missing_field`, `match_failure` |
| `gap_category` | TEXT | | Category: `married_name`, `ocr_error`, `middle_name`, `fs_data_missing` |
| `severity` | TEXT | | `high`, `medium`, `low` |
| `expected_rm_person_id` | INTEGER | | Expected RootsMagic PersonID |
| `expected_rm_name` | TEXT | | Expected name from RootsMagic |
| `expected_field_name` | TEXT | | Expected field name |
| `expected_field_value` | TEXT | | Expected field value |
| `actual_fs_name` | TEXT | | Actual FamilySearch name |
| `actual_fs_ark` | TEXT | | Actual FamilySearch ARK |
| `actual_census_person_id` | INTEGER | FK | References `census_person` |
| `actual_field_value` | TEXT | | Actual field value found |
| `root_cause` | TEXT | | Identified root cause |
| `root_cause_pattern` | TEXT | | Pattern identifier (links to `gap_pattern`) |
| `fs_data_verified` | INTEGER | | 1 if manually verified against FamilySearch |
| `fs_data_exists` | INTEGER | | NULL=unknown, 0=doesn't exist, 1=exists |
| `resolution_status` | TEXT | | `open`, `in_progress`, `resolved`, `wont_fix` |
| `resolution_notes` | TEXT | | Notes about resolution |
| `resolved_at` | TEXT | | ISO timestamp when resolved |
| `detected_at` | TEXT | NOT NULL | ISO timestamp when detected |
| `updated_at` | TEXT | NOT NULL | ISO timestamp of last update |

**Gap Types:**
- `missing_person` - Expected person not found in extraction
- `missing_field` - Field value missing or empty
- `match_failure` - Match algorithm failed to find correct match

**Gap Categories:**
- `married_name` - Name mismatch due to married name
- `ocr_error` - FamilySearch OCR/transcription error
- `middle_name` - Middle name mismatch (e.g., "John W" vs "John William")
- `fs_data_missing` - Data missing from FamilySearch transcription

**Indexes:**
- `idx_extraction_gap_type` on `(gap_type)` - Filter by gap type
- `idx_extraction_gap_category` on `(gap_category)` - Filter by category
- `idx_extraction_gap_source` on `(source_id)` - Find gaps by source
- `idx_extraction_gap_status` on `(resolution_status)` - Find open gaps
- `idx_extraction_gap_pattern` on `(root_cause_pattern)` - Group by pattern
- `idx_extraction_gap_severity` on `(severity)` - Prioritize by severity

---

### `gap_pattern`

Catalog of identified gap patterns for systematic analysis and fix prioritization.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `pattern_id` | INTEGER | PRIMARY KEY | Auto-increment ID |
| `pattern_name` | TEXT | NOT NULL, UNIQUE | Pattern identifier |
| `pattern_description` | TEXT | | Human-readable description |
| `match_criteria_json` | TEXT | | JSON criteria for auto-detecting this pattern |
| `affected_count` | INTEGER | | Number of gaps matching this pattern |
| `affected_sources` | INTEGER | | Number of unique sources affected |
| `affected_batches` | INTEGER | | Number of batches affected |
| `suggested_fix` | TEXT | | Recommended fix approach |
| `fix_complexity` | TEXT | | `trivial`, `easy`, `medium`, `hard`, `complex` |
| `status` | TEXT | | `identified`, `analyzing`, `fix_planned`, `fix_implemented`, `verified` |
| `created_at` | TEXT | NOT NULL | ISO timestamp when pattern identified |
| `updated_at` | TEXT | NOT NULL | ISO timestamp of last update |

**Indexes:**
- `idx_gap_pattern_status` on `(status)` - Filter by fix status
- `idx_gap_pattern_complexity` on `(fix_complexity)` - Prioritize by complexity

---

## Features and Capabilities

### 1. Multi-Source Extraction

Supports multiple data sources with provenance tracking:

```python
from rmcitecraft.database.census_extraction_db import get_census_repository

repo = get_census_repository()
batch_id = repo.create_batch(source="familysearch", notes="1950 Ohio extraction")
```

### 2. Household Extraction

Extracts all persons on a census page, maintaining household relationships:

```python
# Get all persons in same household
persons = repo.get_persons_on_page(page_id=42)
for person in persons:
    print(f"{person.line_number}: {person.full_name} - {person.relationship_to_head}")
```

### 3. Flexible Field Storage (EAV)

Store any census-year-specific fields without schema changes:

```python
# Store 1950-specific fields
repo.insert_person_fields_bulk(person_id, {
    "income": "4500",
    "weeks_worked": "52",
    "veteran_ww2": True,
    "same_house_1949": "Yes"
})

# Retrieve all extended fields
fields = repo.get_person_fields(person_id)
print(f"Income: ${fields.get('income')}")
```

### 4. RootsMagic Integration

Link census extractions to RootsMagic records:

```python
from rmcitecraft.database.census_extraction_db import RMTreeLink

link = RMTreeLink(
    census_person_id=42,
    rmtree_person_id=2776,  # RIN in RootsMagic
    rmtree_citation_id=10370,
    rmtree_database="data/Iiams.rmtree",
    match_confidence=1.0,
    match_method="url_match"
)
repo.insert_rmtree_link(link)
```

### 5. Deduplication

Prevent duplicate extractions via ARK URL normalization:

```python
# Check if already extracted
existing = repo.get_person_by_ark("https://www.familysearch.org/ark:/61903/1:1:6XKG-DP65")
if existing:
    print(f"Already have {existing.full_name}")
```

### 6. Quality Tracking

Track transcription confidence and human verification:

```python
from rmcitecraft.database.census_extraction_db import FieldQuality

quality = FieldQuality(
    person_id=42,
    field_name="occupation",
    confidence_score=0.85,
    source_legibility="faded",
    transcription_note="Abbreviated as 'Asst Mgr'"
)
repo.insert_field_quality(quality)
```

---

## Sample Queries

### Basic Queries

**Find all persons with surname "Ijams" in 1950 census:**
```sql
SELECT cp.*, pg.state, pg.county
FROM census_person cp
JOIN census_page pg ON cp.page_id = pg.page_id
WHERE cp.surname = 'Ijams' AND pg.census_year = 1950;
```

**Get extraction statistics:**
```sql
SELECT
    pg.census_year,
    COUNT(DISTINCT pg.page_id) as pages,
    COUNT(cp.person_id) as persons
FROM census_page pg
LEFT JOIN census_person cp ON pg.page_id = cp.page_id
GROUP BY pg.census_year
ORDER BY pg.census_year;
```

**Find households with multiple persons:**
```sql
SELECT
    pg.page_id,
    pg.state,
    pg.county,
    pg.enumeration_district,
    COUNT(*) as household_size
FROM census_person cp
JOIN census_page pg ON cp.page_id = pg.page_id
GROUP BY pg.page_id
HAVING household_size > 1
ORDER BY household_size DESC
LIMIT 20;
```

### EAV Field Queries

**Find all veterans in 1950 census:**
```sql
SELECT cp.full_name, cp.age, pg.state, pg.county
FROM census_person cp
JOIN census_page pg ON cp.page_id = pg.page_id
JOIN census_person_field cpf ON cp.person_id = cpf.person_id
WHERE pg.census_year = 1950
  AND cpf.field_name = 'veteran'
  AND cpf.field_value IN ('Yes', '1', 'Y');
```

**Pivot extended fields for a person:**
```sql
SELECT
    cp.full_name,
    MAX(CASE WHEN cpf.field_name = 'income' THEN cpf.field_value END) as income,
    MAX(CASE WHEN cpf.field_name = 'weeks_worked' THEN cpf.field_value END) as weeks_worked,
    MAX(CASE WHEN cpf.field_name = 'veteran_ww2' THEN cpf.field_value END) as ww2_vet
FROM census_person cp
LEFT JOIN census_person_field cpf ON cp.person_id = cpf.person_id
WHERE cp.person_id = 42
GROUP BY cp.person_id;
```

---

## Cross-Database Queries with RootsMagic

These queries require **attaching** both databases. Use with caution - the RootsMagic database requires the ICU extension for RMNOCASE collation.

### Setup: Attach Both Databases

```sql
-- In sqlite3 CLI or Python
ATTACH DATABASE '/path/to/Iiams.rmtree' AS rm;
ATTACH DATABASE '~/.rmcitecraft/census.db' AS census;
```

### Find Census Extractions for RootsMagic Person

```sql
-- Find all census extractions linked to a RootsMagic person
SELECT
    cp.full_name,
    pg.census_year,
    pg.state,
    pg.county,
    cp.age,
    cp.occupation,
    rl.match_confidence,
    rl.match_method
FROM census.census_person cp
JOIN census.census_page pg ON cp.page_id = pg.page_id
JOIN census.rmtree_link rl ON cp.person_id = rl.census_person_id
WHERE rl.rmtree_person_id = 2776  -- RIN in RootsMagic
ORDER BY pg.census_year;
```

### Compare Census Data with RootsMagic Events

```sql
-- Match census extractions to RootsMagic census events
SELECT
    -- RootsMagic data
    rm.NameTable.Surname || ', ' || rm.NameTable.Given as rm_name,
    rm.EventTable.Date as rm_date,
    rm.PlaceTable.Name as rm_place,
    -- Census extraction data
    cp.full_name as census_name,
    pg.census_year,
    cp.age as census_age,
    pg.state || ', ' || pg.county as census_location
FROM census.rmtree_link rl
JOIN census.census_person cp ON rl.census_person_id = cp.person_id
JOIN census.census_page pg ON cp.page_id = pg.page_id
JOIN rm.PersonTable ON rl.rmtree_person_id = rm.PersonTable.PersonID
JOIN rm.NameTable ON rm.PersonTable.PersonID = rm.NameTable.OwnerID AND rm.NameTable.IsPrimary = 1
LEFT JOIN rm.EventTable ON rl.rmtree_event_id = rm.EventTable.EventID
LEFT JOIN rm.PlaceTable ON rm.EventTable.PlaceID = rm.PlaceTable.PlaceID
WHERE rl.rmtree_person_id = 2776;
```

### Find Unlinked Census Extractions

```sql
-- Find census persons not yet linked to RootsMagic
SELECT
    cp.full_name,
    pg.census_year,
    pg.state,
    pg.county,
    cp.familysearch_ark
FROM census.census_person cp
JOIN census.census_page pg ON cp.page_id = pg.page_id
LEFT JOIN census.rmtree_link rl ON cp.person_id = rl.census_person_id
WHERE rl.link_id IS NULL
ORDER BY pg.census_year, cp.surname;
```

### Verify Citation ARK URLs Match

```sql
-- Cross-check FamilySearch ARKs in citations vs extractions
SELECT
    rm.CitationTable.CitationID,
    rm.SourceTable.Name as source_name,
    census.census_person.full_name,
    census.census_person.familysearch_ark
FROM rm.CitationTable
JOIN rm.SourceTable ON rm.CitationTable.SourceID = rm.SourceTable.SourceID
LEFT JOIN census.rmtree_link ON rm.CitationTable.CitationID = census.rmtree_link.rmtree_citation_id
LEFT JOIN census.census_person ON census.rmtree_link.census_person_id = census.census_person.person_id
WHERE rm.SourceTable.Name LIKE '%Census%'
  AND census.census_person.person_id IS NOT NULL;
```

---

## Recommended Use Cases

### 1. Census Citation Enhancement

Extract full transcription data to supplement RootsMagic free-form citations:

```python
# Extract data from FamilySearch
result = await extractor.extract_from_ark(
    ark_url="https://www.familysearch.org/ark:/61903/1:1:6XKG-DP65",
    census_year=1950,
    rmtree_citation_id=10370,
    rmtree_person_id=2776
)

# Query stored data for citation improvement
fields = repo.get_person_fields(result.person_id)
print(f"Occupation: {fields.get('occupation')}")
print(f"Income: ${fields.get('income')}")
```

### 2. Household Research

Extract complete households for family group analysis:

```python
# Get all persons on same census page
persons = repo.get_persons_on_page(page_id)
for person in persons:
    fields = repo.get_person_fields(person.person_id)
    print(f"{person.relationship_to_head}: {person.full_name}, age {person.age}")
    if fields.get('occupation'):
        print(f"  Occupation: {fields['occupation']}")
```

### 3. Data Quality Verification

Track which extractions need human review:

```python
# Find fields with low confidence
with repo._connect() as conn:
    low_quality = conn.execute("""
        SELECT cp.full_name, fq.field_name, fq.confidence_score, fq.transcription_note
        FROM field_quality fq
        JOIN census_person cp ON fq.person_id = cp.person_id
        WHERE fq.confidence_score < 0.7
          AND fq.human_verified = 0
        ORDER BY fq.confidence_score
    """).fetchall()
```

### 4. Migration Analysis

Track geographic movement across census years:

```python
# Find all census records for a surname across years
results = repo.search_persons(surname="Ijams")
for person in results:
    page = repo.get_page_by_id(person.page_id)
    print(f"{page.census_year}: {person.full_name} in {page.county}, {page.state}")
```

---

## Maintenance

### Clear All Data

```bash
rm ~/.rmcitecraft/census.db
```

The database will be recreated on next use.

### Backup

```bash
cp ~/.rmcitecraft/census.db ~/.rmcitecraft/census.db.backup
```

### Vacuum (Reclaim Space)

```bash
sqlite3 ~/.rmcitecraft/census.db "VACUUM;"
```

---

## Python API Reference

```python
from rmcitecraft.database.census_extraction_db import (
    CensusExtractionRepository,
    CensusPage,
    CensusPerson,
    RMTreeLink,
    FieldQuality,
    FieldHistory,
    get_census_repository,
    CENSUS_DB_PATH,
)

# Get singleton repository
repo = get_census_repository()

# Or create with custom path
repo = CensusExtractionRepository(db_path=Path("/custom/path.db"))

# Key methods
repo.create_batch(source, notes) -> int
repo.insert_page(CensusPage) -> int
repo.insert_person(CensusPerson) -> int
repo.insert_person_fields_bulk(person_id, fields_dict, labels_dict)
repo.insert_rmtree_link(RMTreeLink) -> int
repo.insert_field_quality(FieldQuality) -> int
repo.get_person_by_ark(ark_url) -> CensusPerson | None
repo.get_persons_on_page(page_id) -> list[CensusPerson]
repo.get_person_fields(person_id) -> dict[str, Any]
repo.search_persons(surname, given_name, census_year, state, county) -> list[CensusPerson]
repo.get_extraction_stats() -> dict[str, Any]

# Field history (version control) methods
repo.insert_field_history(person_id, field_name, field_value, field_source, is_original, created_by) -> int
repo.get_field_history(person_id, field_name=None) -> list[FieldHistory]
repo.get_original_field_value(person_id, field_name) -> str | None
repo.record_field_change(person_id, field_name, old_value, new_value, source, created_by) -> None
```

---

## Census Year YAML Schemas

The `src/rmcitecraft/schemas/census/` directory contains YAML schema definitions for each US Federal Census year (1790-1950). These schemas define:

1. **Form structure** - Physical layout of census forms
2. **Column definitions** - Fields collected in that census year
3. **Valid values** - Enumerated values for coded fields
4. **Historical context** - Era-specific features and research tips

### Schema Files

| File | Census Year | Key Features |
|------|-------------|--------------|
| `1790.yaml` - `1840.yaml` | 1790-1840 | Statistical tallies only; heads of household named |
| `1850.yaml` | 1850 | First census to name all persons; no ED |
| `1860.yaml` | 1860 | Personal estate value added |
| `1870.yaml` | 1870 | Post-Civil War; citizenship questions |
| `1880.yaml` | 1880 | Enumeration districts (ED) introduced |
| `1900.yaml` | 1900 | Birth month/year recorded (unique census) |
| `1910.yaml` | 1910 | Civil War veteran questions |
| `1920.yaml` | 1920 | Year of naturalization |
| `1930.yaml` | 1930 | Radio ownership, veteran questions |
| `1940.yaml` | 1940 | Social Security; supplemental sampling |
| `1950.yaml` | 1950 | Last publicly available census |

### Schema Structure

Each YAML file follows this structure:

```yaml
year: 1950
era: "individual_with_ed_sheet"  # Classification for form structure
nara_publication: "T6"           # NARA microfilm publication number

form_structure:
  lines_per_side: 30             # Lines per page/sheet side
  sides: ["A", "B"]              # Sheet sides (or null for pages)
  supplemental_lines: [14, 29]   # Sample lines (1940, 1950)
  uses_page: false               # Uses page numbers
  uses_sheet: true               # Uses sheet numbers
  uses_stamp: true               # Uses stamp numbers (1950)

columns:
  - name: line_number
    data_type: integer
    description: "Line number on census form"
    required: false
    is_metadata: true

  - name: name
    column_number: 1
    data_type: string
    description: "Name of person"
    required: true

  - name: sex
    column_number: 3
    data_type: string
    description: "M=Male, F=Female"
    valid_values: ["M", "F"]
    required: true

abbreviations:
  "do": "same as above"
  '"': "ditto - same as above"

instructions: |
  Historical context and reading tips...
```

### Era Classifications

| Era | Census Years | Characteristics |
|-----|--------------|-----------------|
| `head_of_household` | 1790-1840 | Only head named; statistical tallies |
| `individual_no_ed` | 1850-1870 | All persons named; no enumeration districts |
| `individual_with_ed` | 1880 | Enumeration districts introduced |
| `individual_with_ed_sheet` | 1900-1950 | Sheets with A/B sides; ED required |

### Using Schemas Programmatically

```python
import yaml
from pathlib import Path

# Load schema for a census year
schema_path = Path("src/rmcitecraft/schemas/census/1950.yaml")
with open(schema_path) as f:
    schema = yaml.safe_load(f)

# Get form structure
lines_per_side = schema["form_structure"]["lines_per_side"]
uses_sheet = schema["form_structure"]["uses_sheet"]

# Get required columns
required_cols = [
    col["name"] for col in schema["columns"]
    if col.get("required", False)
]

# Get valid values for a field
sex_values = next(
    col["valid_values"]
    for col in schema["columns"]
    if col["name"] == "sex"
)
```

---

## Integration with RootsMagic

The census.db database is designed to complement RootsMagic databases, providing enhanced census research capabilities that RootsMagic citations alone cannot offer.

### Value Proposition

| Capability | RootsMagic Only | RootsMagic + census.db |
|------------|-----------------|------------------------|
| **Citation text** | Free-form footnote/bibliography | Structured data + formatted citation |
| **Household context** | Single person cited | All household members stored |
| **Field granularity** | Embedded in citation text | Individual searchable fields |
| **Multi-census analysis** | Manual comparison | Query across census years |
| **Data quality tracking** | None | Confidence scores, verification status |
| **Edit history** | Lost | Original + all changes preserved |
| **Match diagnostics** | None | Algorithm performance analytics |

### Primary Use Cases

#### 1. Census Citation Enhancement

Extract full transcription data to supplement RootsMagic free-form citations:

```python
# After extracting a census page
person = repo.get_person_by_ark(ark_url)
fields = repo.get_person_fields(person.person_id)

# Build enhanced citation footnote
footnote = f"{page.census_year} U.S. census, {page.county}, {page.state}, "
footnote += f"E.D. {page.enumeration_district}, sheet {page.sheet_number}, "
footnote += f"line {person.line_number}, {person.full_name}"
if fields.get("occupation"):
    footnote += f", {fields['occupation']}"
```

#### 2. Household Research

Analyze complete households for family group reconstruction:

```python
# Get all persons on same census page
household = repo.get_persons_on_page(page_id)

print(f"Household of {household[0].full_name}:")
for person in household:
    rel = person.relationship_to_head or "Head"
    print(f"  {rel}: {person.full_name}, age {person.age}")
```

#### 3. Cross-Census Migration Tracking

Track family movement across census years:

```python
# Find all census records for a surname
results = repo.search_persons(surname="Ijams")
by_year = {}
for p in results:
    page = repo.get_page_by_id(p.page_id)
    by_year.setdefault(page.census_year, []).append((p, page))

for year in sorted(by_year.keys()):
    print(f"\n{year} Census:")
    for person, page in by_year[year]:
        print(f"  {person.full_name} in {page.county}, {page.state}")
```

#### 4. Data Quality Verification

Identify and track transcription issues:

```python
# Find fields with low confidence needing review
with repo._connect() as conn:
    issues = conn.execute("""
        SELECT cp.full_name, fq.field_name,
               fq.confidence_score, fq.transcription_note
        FROM field_quality fq
        JOIN census_person cp ON fq.person_id = cp.person_id
        WHERE fq.confidence_score < 0.7
          AND fq.human_verified = 0
        ORDER BY fq.confidence_score
    """).fetchall()
```

#### 5. RootsMagic Person Matching

Find census extractions for RootsMagic persons:

```python
# Get all census extractions linked to a specific RIN
rin = 2776  # RootsMagic PersonID
with repo._connect() as conn:
    extractions = conn.execute("""
        SELECT cp.*, pg.census_year, pg.state, pg.county
        FROM census_person cp
        JOIN census_page pg ON cp.page_id = pg.page_id
        JOIN rmtree_link rl ON cp.person_id = rl.census_person_id
        WHERE rl.rmtree_person_id = ?
        ORDER BY pg.census_year
    """, (rin,)).fetchall()
```

### Cross-Database Query Examples

When both databases are attached:

```sql
-- Attach databases
ATTACH DATABASE 'data/Iiams.rmtree' AS rm;
ATTACH DATABASE '~/.rmcitecraft/census.db' AS census;

-- Find persons in RootsMagic missing census extractions
SELECT rm.NameTable.Surname, rm.NameTable.Given, rm.PersonTable.PersonID
FROM rm.PersonTable
JOIN rm.NameTable ON rm.PersonTable.PersonID = rm.NameTable.OwnerID
  AND rm.NameTable.IsPrimary = 1
LEFT JOIN census.rmtree_link ON rm.PersonTable.PersonID = census.rmtree_link.rmtree_person_id
WHERE census.rmtree_link.link_id IS NULL
  AND rm.PersonTable.PersonID IN (
      -- Persons with census events
      SELECT DISTINCT OwnerID FROM rm.EventTable WHERE EventType = 18
  );
```

---

## Related Documentation

- [Census Batch Processing Architecture](../architecture/CENSUS_BATCH_PROCESSING_ARCHITECTURE.md)
- [Batch State Database Schema](./BATCH_STATE_DATABASE_SCHEMA.md)
- [RootsMagic Schema Reference](./schema-reference.md)
- [Database Patterns](./DATABASE_PATTERNS.md)

---

**Last Updated:** 2025-12-11
**Schema Version:** 3
