---
priority: reference
topics: [database, census, citation, batch, testing]
---

# Census Extraction 100-Entry Test Run Analysis

**Date:** 2025-12-05
**Status:** DRAFT - User has not yet reviewed or agreed to this analysis
**Analyst:** Claude Code session

---

## Overview

This document captures the analysis performed on the 100-entry census extraction test run. The backup data is stored in `./backup/100/` containing:
- `census.db` - Extracted census data
- `batch_state.db` - Batch processing state
- `rmcitecraft.log` - Application log

---

## Analysis Methodology

### 1. Database Comparison Approach

The analysis compared data across three sources:
1. **RootsMagic (`data/Iiams.rmtree`)** - Source of truth for expected persons
2. **census.db (`backup/100/census.db`)** - Extracted census data
3. **batch_state.db (`backup/100/batch_state.db`)** - Processing state

### 2. Key Queries Used

#### Finding expected RM persons from processed sources:
```sql
-- Get all persons (owners + witnesses) linked to processed sources
SELECT DISTINCT e.OwnerID as person_id, n.Given, n.Surname
FROM SourceTable s
JOIN CitationTable c ON s.SourceID = c.SourceID
JOIN CitationLinkTable cl ON c.CitationID = cl.CitationID AND cl.OwnerType = 2
JOIN EventTable e ON cl.OwnerID = e.EventID AND e.OwnerType = 0
JOIN NameTable n ON e.OwnerID = n.OwnerID AND n.IsPrimary = 1
WHERE s.SourceID IN (processed_source_ids)

-- Plus witnesses
SELECT DISTINCT w.PersonID, n.Given, n.Surname
FROM WitnessTable w
JOIN NameTable n ON w.PersonID = n.OwnerID AND n.IsPrimary = 1
WHERE w.EventID IN (event_ids_from_above)
```

#### Finding extracted persons in census.db:
```sql
SELECT DISTINCT rmtree_person_id FROM rmtree_link WHERE rmtree_person_id IS NOT NULL
```

#### Cross-referencing log for skipped persons:
```bash
grep "no RootsMagic match" backup/100/rmcitecraft.log | sed "s/.*Skipping '\([^']*\)'.*/\1/"
```

### 3. Temporary Files Created During Analysis

Located in `/tmp/`:
- `processed_citations.txt` - Source IDs that were processed (123 total)
- `rm_expected_persons.txt` - Expected RM persons (372 total)
- `rm_expected_ids.txt` - Just the RIN numbers
- `census_extracted_persons.txt` - Actually extracted RM person IDs (223 total)
- `missing_rm_ids.txt` - RM persons not in census.db (149 total)

---

## Key Findings

### Extraction Statistics

| Metric | Value | Notes |
|--------|-------|-------|
| Transcription sessions | 17 | All on Dec 5, 2025 |
| Sources processed | 123 | Via census_transcription_items |
| Items completed | 257 | Some sources have multiple persons |
| Census pages created | 106 | 1950 census only |
| Census persons in DB | 249 | All marked is_target_person=1 |
| RM persons linked | 223 | Via rmtree_link table |
| **Expected RM persons** | **372** | From RootsMagic source/event/witness chain |
| **Missing RM persons** | **149** | **40% extraction failure rate** |
| Persons skipped in log | 428 | "no RootsMagic match" messages |

### Critical Discovery: Name Matching Failures

The 428 "no RootsMagic match" skips include many persons who **ARE** in RootsMagic but failed name matching.

#### Category Breakdown of 149 Missing Persons

| Category | Count | Description |
|----------|-------|-------------|
| Found in log (extraction attempted) | 113 | Name matching failed |
| Married women (different surname) | 19 | Maiden vs married name |
| Family members not in log | 17 | Never attempted extraction |

### Root Cause Analysis: Name Matching Failures

#### 1. Middle Name/Initial Abbreviation Mismatch (~60+ cases)

**Example:**
- FamilySearch: "Guy L Ijams"
- RootsMagic: "Guy Lyndon Ijams"
- **Issue:** "L" doesn't match "Lyndon" - current code requires full name match

**Other examples:**
- "J" vs "John"
- "E" vs "Elizabeth"
- "W" vs "William"

#### 2. Married vs Maiden Name (~40+ cases)

**Example:**
- FamilySearch: "Imo E Ijams" (wife using husband's surname)
- RootsMagic: "Imo Mildred Hatfield" (maiden name stored)
- **Issue:** Surnames don't match, current married name logic only checks head's surname

**Other examples:**
- "Katherine T Lewis" (FS) vs "Catherine Harriet Ijams" (RM)
- "Elizabeth Mason Tayloe" (RM) - maiden name not matching FS married name

#### 3. Spelling Variations (~20+ cases)

**Example:**
- FamilySearch: "Katherine"
- RootsMagic: "Catherine"
- **Issue:** K/C spelling difference not handled

#### 4. Combined Issues (~15 cases)

Some persons have multiple issues:
- Different spelling AND married name
- Abbreviation AND married name

### Data Quality in census.db

| Field | Population Rate | Notes |
|-------|-----------------|-------|
| Full name | 249/249 (100%) | |
| Line number | 249/249 (100%) | SLS API working |
| FamilySearch ARK | 249/249 (100%) | |
| Age | 247/249 (99%) | 2 missing (Ward, Vacant) |
| Birthplace | 247/249 (99%) | |
| Relationship | 248/249 (99.6%) | |
| Occupation | 238/249 (96%) | Wives, elderly expected |

### Issues Found

1. **"Vacant" record extracted** - FamilySearch has "Vacant" entries for empty dwellings that were incorrectly treated as persons

2. **5 stuck test items** - "Test Person" entries from development stuck in "extracting" status

3. **Column naming confusion** - `rmtree_citation_id` in batch_state.db actually contains Source IDs, not Citation IDs

---

## Specific Missing Persons (Sample)

First 20 of 149 missing:

| RIN | Name | Likely Cause |
|-----|------|--------------|
| 137 | Samuel Francis Iiams | Name matching failure |
| 141 | Elon Alton Iiams | Not in log - never attempted |
| 145 | Ada Alice Jones | Name matching failure |
| 148 | Donald Eugene Iiams | Name matching failure |
| 642 | Elizabeth Mason Tayloe | Married name (maiden in RM) |
| 2083 | Lillie Beatrice Woods | Married name (maiden in RM) |
| 3087 | Noka Lee Hooper | Name matching failure |

Full list available in `/tmp/missing_rm_ids.txt` (generated during analysis).

---

## Suggested Next Steps

### Investigation

1. **Verify the 149 missing count** - Cross-reference with actual FamilySearch pages to confirm these persons exist on the census images

2. **Sample verification** - Manually check 5-10 specific missing persons to confirm root cause analysis:
   - RIN 193: Catherine Harriet Ijams - verify FS has "Katherine T Lewis"
   - RIN 2083: Lillie Beatrice Woods - verify married name issue
   - RIN 141: Elon Alton Iiams - verify why not in log at all

3. **Check the 17 "not in log" family members** - Determine if they should have been extracted via family table or if they're on different census pages

### Program Improvements (Proposed, Not Agreed)

1. **Enhance name matching for initials:**
   ```python
   # "Guy L" should match "Guy Lyndon" if L == Lyndon[0]
   def matches_with_initial(fs_name, rm_name):
       if len(fs_middle) == 1 and rm_middle.startswith(fs_middle):
           return True
   ```

2. **Expand married name matching:**
   - Current: Only checks if wife's FS surname matches head's surname
   - Proposed: Check all RM women's maiden names against FS married names
   - Consider checking spouse relationships in RootsMagic

3. **Add fuzzy first name matching:**
   - Handle K/C, Elisabeth/Elizabeth variations
   - Consider Soundex or similar phonetic matching

4. **Filter "Vacant" entries:**
   - Skip records where full_name == "Vacant"

5. **Fix column naming:**
   - Rename `rmtree_citation_id` to `rmtree_source_id` in batch_state.db schema

---

## Commands to Reproduce Analysis

```bash
# 1. Get processed source IDs
sqlite3 backup/100/batch_state.db \
  "SELECT DISTINCT rmtree_citation_id FROM census_transcription_items WHERE status = 'complete';" \
  > /tmp/processed_citations.txt

# 2. Get extracted RM person IDs
sqlite3 backup/100/census.db \
  "SELECT DISTINCT rmtree_person_id FROM rmtree_link WHERE rmtree_person_id IS NOT NULL;" \
  > /tmp/census_extracted_persons.txt

# 3. Find missing persons (requires Python with ICU extension)
# See methodology section for full query

# 4. Cross-reference with log
grep "no RootsMagic match" backup/100/rmcitecraft.log | wc -l
```

---

## Files Referenced

- `backup/100/census.db` - Test run extracted data
- `backup/100/batch_state.db` - Test run batch state
- `backup/100/rmcitecraft.log` - Test run log file
- `data/Iiams.rmtree` - RootsMagic database (source of truth)
- `src/rmcitecraft/services/familysearch_census_extractor.py` - Extraction code with name matching logic

---

## Status

**This analysis is DRAFT status.** The user has not yet reviewed or agreed to:
- The methodology used
- The conclusions drawn
- The proposed improvements

Next session should begin by reviewing this document and confirming/correcting the analysis before proceeding with any code changes.

---

*Generated: 2025-12-05 by Claude Code session*
