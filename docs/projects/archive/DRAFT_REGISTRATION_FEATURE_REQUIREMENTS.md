---
priority: high
topics: [ui, draft-registration, automation, citation, media]
status: planning
---

# Draft Registration Processing Feature Requirements

**Version**: 1.0
**Date**: 2026-01-31

## Overview

Add batch processing to RMCitecraft UI for draft registration records (WW2, WW1): automatically create Evidence Explained citations, download images, create events, and link to RootsMagic database.

## User Stories

**Primary**: Upload a spreadsheet of draft registrations from FamilySearch and have RMCitecraft automatically create citations, download images, and attach them to the correct people in the database.

**Key Workflows**:
1. Upload CSV/XLSX file with draft data
2. Auto-match records to people by RIN or name
3. Create formatted citations per Evidence Explained
4. Download registration card images from FamilySearch/Ancestry
5. Create draft registration events (optional)
6. Handle errors and duplicates gracefully

## Functional Requirements

### FR1: File Input

| Requirement | Details |
|-------------|---------|
| **Formats** | CSV, XLSX |
| **Expected Columns** | `rin`, `given_name`, `surname`, `birth_year`, `death_year`, `familysearch_citation`, `registration_date`, `state`, `county`, `notes` |
| **Column Mapping** | Flexible interface for non-standard headers |
| **Validation** | Validate required fields before processing |
| **Preview** | Show first 10-20 records before starting |

### FR2: Person Matching

| Match Type | Confidence | Method |
|------------|-----------|---------|
| RIN (exact) | 100% | Direct PersonID lookup |
| Name + birth year (exact) | 95% | Given + Surname + exact birth year |
| Name + birth year (fuzzy) | 70-90% | Fuzzy name match + birth year ±1 |
| Name only | 50-70% | Fuzzy name match |

**Manual Review**: Prompt user for matches < 90% confidence
**Fallbacks**: Skip unmatched, create new person (future)

### FR3: Citation Creation

**Format** (Evidence Explained):
```
Footnote:
1942 U.S. draft registration, [County] County, [State],
[person name]; imaged, "[Collection Name]", FamilySearch (https://familysearch.org/ark:/...).

Short Footnote:
1942 U.S. draft reg., [County] Co., [State], [person name].

Bibliography:
"[State], World War II Draft Registration Cards, 1940-1947." Database with images.
FamilySearch. http://FamilySearch.org.
```

**Features**:
- Parse FamilySearch URLs for ARK identifiers
- Auto-detect WW1 vs WW2 based on year
- State-specific formatting variations
- Source deduplication by collection name
- Citation deduplication by person + source

**⚠️ Existing Source Remediation**:
~253 records have existing sources with placeholder/incomplete citations that need updating with properly formatted Evidence Explained text.

### FR4: Image Download

**Sources**:
| Source | Method | Details |
|--------|--------|---------|
| **FamilySearch 1:1** (Person ARKs) | Browser automation | Navigate to person page → "View Original Document" → download dialog (JPG) → handle single/dual cards |
| **FamilySearch 3:1** (Image ARKs) | Browser automation | Direct image viewer → CMD-S keyboard shortcut → download TWO images (front + back) → combine with ImageMagick |
| **AncestryLibrary** | Browser automation | Record detail → Tool menu download → TWO images → combine with ImageMagick |

**⚠️ Ancestry URL Discovery** (NEW - 2026-02-06):
- For FamilySearch-only records, automatically search AncestryLibrary by name + birth year
- Prefer collections: "U.S., World War II Draft Cards Young Men, 1940-1947" and "U.S., World War II Draft Registration Cards, 1942"
- ~80% success rate based on testing
- Store discovered URLs for future use

**File Naming**: `surname, givenname (birth-death).jpg`
- Query RootsMagic by RIN for names and dates
- Fallbacks: omit missing dates, append `_2` for duplicates

**Storage**: `/Users/miams/Genealogy/RootsMagic/Files/Records - Military/WW II - Draft Registration/`
- Single directory, no state-based subdirectories

**Media Linking**:
- MultimediaTable entry (MediaType=1, MediaFile, MediaPath, Caption)
- Link to Citation (MediaLinkTable, OwnerType=4)
- Link to Person (MediaLinkTable, OwnerType=0)
- Link to Event if created (MediaLinkTable, OwnerType=2)

**Duplicate Detection**: Check by filename, skip/overwrite/rename

### FR5: Event Creation (Optional)

**Event Data**:
- EventType: Draft Registration (check if exists or create)
- OwnerType: 0 (Person), OwnerID: PersonID
- Date: Registration date (if known)
- PlaceID: Match or create place
- Details: Serial number, registration info
- IsPrimary: 0

**Linking**:
- Citation → Event (CitationLinkTable, OwnerType=2)
- Media → Event (MediaLinkTable, OwnerType=2)

**Duplicate Detection**: Check for existing draft event for same person + year

### FR6: User Interface

**Layout**:
1. **File Upload** - Choose CSV/XLSX
2. **Column Mapping** - Map non-standard headers (if needed)
3. **Preview & Configure** - Show record count, enable/disable: citations, images, events
4. **Process** - Progress bar, status summary (processed/warnings/errors/pending)
5. **Results & Log** - Scrollable log with timestamps, export errors

**Manual Review Dialog** (confidence < 90%):
- Show file record vs database match side-by-side
- Display confidence score and reason
- Show alternate matches
- Options: Accept, Choose Different, Skip, Manual Entry

### FR7: Batch State Management

**State Database**: `~/.rmcitecraft/draft_batch_state.db`

**Tables**:
- `batches`: Track batch metadata, status
- `batch_records`: Per-record status (pending/processing/completed/failed/skipped), matched RIN, created IDs, errors

**Features**:
- Save state every N records
- Resume from last processed
- Batch history view

### FR8: Logging & Error Handling

**Error Categories**:
- Data validation errors (missing fields, invalid data)
- Person matching errors (no match, ambiguous)
- Download errors (FamilySearch/Ancestry)
- Database write errors

**Error Actions**:
- Log with context and suggested action
- Mark record as failed
- Continue processing remaining records
- Export failed records to CSV for retry

## Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| **Performance** | 100 records < 5 min (excluding images), images ~5-10 sec each |
| **Reliability** | Resume from crash, retry downloads (3 attempts) |
| **Usability** | Clear progress, helpful errors, keyboard shortcuts |
| **Data Integrity** | Never overwrite without confirmation, detect duplicates, validate before writes |
| **Extensibility** | Support other draft types (WW1, Vietnam), other record types (marriage, death) |

## Technical Architecture

**Services**:
- `draft_file_reader.py` - Parse CSV/XLSX, validate, column mapping
- `draft_person_matcher.py` - Match to PersonTable, fuzzy matching, confidence scores
- `draft_citation_builder.py` - Parse FamilySearch URLs, format Evidence Explained citations
- `draft_image_downloader.py` - Chrome CDP, navigate, extract, download
- `draft_event_manager.py` - Create/link events, handle duplicates
- `draft_batch_processor.py` - Orchestrate workflow, state management, error handling

**UI**:
- `ui/tabs/draft_processing_tab.py` - Main interface
- `ui/components/match_review_dialog.py` - Manual review

**Database**:
- `database/draft_batch_state_repository.py` - Batch state CRUD

**Batch State Schema** (`~/.rmcitecraft/draft_batch_state.db`):
```sql
CREATE TABLE batches (
    batch_id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    upload_date TEXT NOT NULL,
    total_records INTEGER,
    processed_records INTEGER,
    status TEXT, -- 'pending', 'processing', 'completed', 'paused', 'failed'
    config_json TEXT
);

CREATE TABLE batch_records (
    record_id INTEGER PRIMARY KEY,
    batch_id INTEGER,
    row_number INTEGER,
    rin INTEGER,
    status TEXT,
    match_confidence REAL,
    matched_rin INTEGER,
    source_id INTEGER,
    citation_id INTEGER,
    event_id INTEGER,
    media_id INTEGER,
    error_message TEXT,
    processed_date TEXT,
    FOREIGN KEY (batch_id) REFERENCES batches(batch_id)
);
```

## Dependencies

**Existing**: `database/connection.py`, `services/familysearch_automation.py`, `utils/rm_date.py`, `validation/data_quality.py`

**New**: `openpyxl`, `fuzzywuzzy` or `rapidfuzz`, `pandas` (optional)

**External**: Chrome with remote debugging, FamilySearch account, internet connection

## Configuration

```python
DRAFT_SETTINGS = {
    'media_root': '~/Genealogy/RootsMagic/Files/Records - Draft Registration',
    'auto_create_events': True,
    'auto_download_images': True,
    'require_manual_review_threshold': 90,  # confidence %
    'max_concurrent_downloads': 3,
    'chrome_cdp_url': 'http://localhost:9222',
    'default_fact_type_name': 'Draft Registration',
    'duplicate_handling': 'skip',  # 'skip', 'update', 'ask'
}
```

## Success Metrics

- **Time Savings**: 5 min/record → 30 sec/record
- **Accuracy**: 95%+ automatic matching
- **Adoption**: 500+ registrations processed in 3 months
- **Reliability**: < 5% error rate

## Future Enhancements

**Phase 2**:
- Other record types (marriage, death, military)
- OCR text extraction
- Automatic place standardization
- Citation conflict resolution

**Phase 3**:
- AI-assisted matching (GPT-4)
- Automatic record discovery
- Citation quality scoring
- FamilySearch API integration (if available)

## Open Questions

1. **Fact Type**: Auto-create "Draft Registration" or require manual creation?
2. **Place Matching**: Auto-create places or manual selection?
3. **Image Format**: JPEG, PNG, or PDF? What resolution?
4. **Citation Templates**: Allow user customization?
5. **Batch Size**: Maximum batch size? (Suggest warn at 500, limit at 2000)
6. **Network Failures**: Retry attempts for downloads? (Suggest 3)
7. **Duplicate Strategy**: Default for duplicate sources/citations/events? (Suggest skip with warning)

## References

- Evidence Explained (3rd ed.) - Elizabeth Shown Mills
- RootsMagic Schema Reference - `docs/reference/schema-reference.md`
- FamilySearch ARK URL format
- WW2 Draft Registration Cards - FamilySearch collection docs
