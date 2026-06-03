---
priority: high
topics: [project-plan, draft-registration, automation]
status: planning
---

# Draft Registration Feature - Project Plan

**Start**: 2026-01-31 | **Target**: Phase 1 in 3-4 weeks

## Overview

Implement automated batch processing of draft registration records (WW2, WW1) in RMCitecraft UI: citation creation, image downloads, event management.

**Philosophy**: Iterative development - each phase delivers working functionality.

## Phase Breakdown

| Phase | Duration | Goal |
|-------|----------|------|
| **Phase 1: Core MVP** | Week 1-2 | Basic batch processing with RINs, citations from FamilySearch URLs |
| **Phase 2: Matching & Errors** | Week 3 | Robust person matching, comprehensive error handling |
| **Phase 3: Images & Polish** | Week 4 | Image downloads, production-ready UX |
| **Phase 4: Advanced** | Future | Enhanced automation, other record types |

---

## Phase 1: Core MVP (Week 1-2)

### Week 1: Backend Services

| Task | Duration | File | Key Methods |
|------|----------|------|-------------|
| **1.1: File Reader** | 2 days | `draft_file_reader.py` | `read_file()`, `validate_record()`, `preview()` |
| **1.2: Citation Builder** | 3 days | `draft_citation_builder.py` | `parse_familysearch_url()`, `build_source()`, `build_citation()` |
| **1.3: Database Writer** | 2 days | `draft_database_writer.py` | `create_or_find_source()`, `create_citation()`, `link_citation_to_person()` |
| **1.4: Batch Processor** | 2 days | `draft_batch_processor.py` | `process_batch()`, `process_record()`, `handle_error()` |

**File Reader** (`draft_file_reader.py`):
- Read CSV/XLSX with column mapping
- Validate required fields: `rin`, `given_name`, `surname`, `familysearch_citation`
- Handle missing/malformed data gracefully

**Citation Builder** (`draft_citation_builder.py`):
- Parse FamilySearch URLs for ARK, state, year, collection
- Generate Evidence Explained citations (footnote, short footnote, bibliography)
- XML entity encoding for BLOB storage
- Year-specific formatting (WW1 vs WW2)

**Citation Format** (WW2):
```
Footnote: 1942 U.S. draft registration, [County] County, [State],
[person name]; imaged, "[Collection Name]", FamilySearch (https://familysearch.org/ark:/...).

Short Footnote: 1942 U.S. draft reg., [County] Co., [State], [person name].

Bibliography: "[State], World War II Draft Registration Cards, 1940-1947."
Database with images. FamilySearch. http://FamilySearch.org.
```

**Database Writer** (`draft_database_writer.py`):
- Create SourceTable entries (free-form, TemplateID=0) with BLOB encoding
- Create CitationTable entries
- Link citations to persons (CitationLinkTable, OwnerType=0)
- Detect duplicate sources by title
- Detect duplicate citations by person + source
- Use transactions for atomicity

**Batch Processor** (`draft_batch_processor.py`):
- Process records sequentially
- Track success/warning/error counts
- Generate processing log
- Continue on errors (don't abort batch)

### Week 2: UI & Testing

| Task | Duration | Details |
|------|----------|---------|
| **1.5: UI Tab** | 3 days | File upload, preview (10 records), processing options, progress bar, results log |
| **1.6: Integration Testing** | 2 days | 50-record batch, duplicate detection, error scenarios |
| **1.7: Documentation** | 1 day | User guide, common errors, citation examples |

**UI Components** (`ui/tabs/draft_processing_tab.py`):
1. File upload (CSV/XLSX)
2. Preview table (first 10 records)
3. Processing options: "Create citations" (others disabled Phase 1)
4. Progress bar with status summary (processed/warnings/errors/pending)
5. Scrollable log with timestamps
6. Export error log to CSV

---

## Phase 2: Person Matching & Error Handling (Week 3)

| Task | Duration | Focus |
|------|----------|-------|
| **2.1: Person Matcher** | 2 days | RIN match (100%), name + birth year (95%), fuzzy name (70-90%) |
| **2.2: Manual Review UI** | 2 days | Side-by-side comparison, confidence scores, alternate matches |
| **2.3: Batch State** | 2 days | `~/.rmcitecraft/draft_batch_state.db`, pause/resume capability |
| **2.4: Error Handling** | 1 day | Categorized errors, suggested actions, retry mechanism |

**Person Matcher** (`draft_person_matcher.py`):
- Match by RIN (100% confidence)
- Fallback to name + birth year (exact: 95%, fuzzy: 70-90%)
- Handle aliases (search all NameTable entries)
- Return top 3 matches with confidence scores

**Manual Review Dialog** (`ui/components/match_review_dialog.py`):
- Show file record vs database match side-by-side
- Display confidence score and reason
- Show up to 5 potential matches
- Options: Accept, Choose Different, Skip, Manual Entry
- Keyboard shortcuts (Enter=accept, S=skip)

**Batch State** (`database/draft_batch_state_repository.py`):
```sql
-- ~/.rmcitecraft/draft_batch_state.db
CREATE TABLE batches (batch_id, filename, upload_date, status, config_json);
CREATE TABLE batch_records (record_id, batch_id, rin, status, match_confidence,
                            matched_rin, source_id, citation_id, error_message);
```

---

## Phase 3: Image Management & Polish (Week 4)

| Task | Duration | Focus |
|------|----------|-------|
| **3.1: Image Downloader** | 3 days | Chrome CDP, FamilySearch ARK URLs, organize by state/type |
| **3.2: Media Manager** | 2 days | MultimediaTable, MediaLinkTable (citation/person/event) |
| **3.3: Event Manager** | 2 days | Create draft events, link citations/media, detect duplicates |
| **3.4: UI Polish** | 2 days | Column mapping, pause/resume, batch history, multi-stage progress |

**Image Downloader** (`draft_image_downloader.py`):
- Connect to Chrome CDP (existing FamilySearch session)
- Navigate to ARK URL, extract high-res image
- Organize: `~/Genealogy/RootsMagic/Files/Records - Draft Registration/[State]/[Type]/`
- Filename: `Surname_Given_Year_State_Draft_RIN.jpg`
- Skip if exists, handle failures gracefully

**Media Manager** (`draft_media_manager.py`):
- Create MultimediaTable entry (MediaType=1, MediaPath, Caption)
- Link to Citation (MediaLinkTable, OwnerType=4)
- Link to Person (MediaLinkTable, OwnerType=0)
- Link to Event (MediaLinkTable, OwnerType=2)

**Event Manager** (`draft_event_manager.py`):
- Create/reuse "Draft Registration" fact type
- Create EventTable entry (OwnerType=0, Date, PlaceID, Details)
- Link citation (CitationLinkTable, OwnerType=2)
- Link media (MediaLinkTable, OwnerType=2)
- Detect duplicates (person + year)

---

## Phase 4: Advanced Features (Future)

- WW1 draft registration support
- Other record types (marriage, death, military service, birth certificates)
- GPT-4 assisted person matching
- Automatic record discovery on FamilySearch
- Batch rollback capability

---

## Project Schedule

```
Week 1: Backend (Tasks 1.1-1.4)
├─ Mon-Tue:   File Reader
├─ Wed-Fri:   Citation Builder
└─ Weekend:   Buffer

Week 2: UI & Testing (Tasks 1.5-1.7)
├─ Mon-Wed:   Database Writer + Batch Processor
├─ Thu-Sat:   Draft Processing UI
└─ Sun:       Integration Testing

Week 3: Matching & Errors (Tasks 2.1-2.4)
├─ Mon-Tue:   Person Matcher
├─ Wed-Thu:   Manual Review UI
├─ Fri:       Batch State
└─ Weekend:   Error Handling

Week 4: Images & Polish (Tasks 3.1-3.4)
├─ Mon-Wed:   Image Downloader
├─ Thu:       Media Manager
├─ Fri:       Event Manager
└─ Weekend:   UI Polish & Testing
```

## Milestones

- **M1**: Week 1 - Backend services functional
- **M2**: Week 2 - MVP usable for RIN-based batches
- **M3**: Week 3 - Robust matching and error handling
- **M4**: Week 4 - Full feature with images and events

## Risk Management

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| FamilySearch blocks automation | Medium | Use authenticated CDP, respect rate limits, manual fallback |
| Citation format complexity | Medium | Start with WW2 PA, iterate, user can manually edit |
| Person matching accuracy | Low | Conservative thresholds, manual review, show all fields |
| Database corruption | Low | Transactions, extensive testing, user backup reminder |
| Performance issues | Medium | Batch size warnings (>500), background processing, optimize queries |

## Success Criteria

**Phase 1 MVP**:
- Process 100 RIN-based records successfully
- Citations appear correctly in RootsMagic
- Zero database corruption
- < 5% error rate on well-formed data

**Phase 3 Complete**:
- Process 500+ records with images
- 90%+ automatic person matching accuracy
- < 10% error rate (including bad data)
- Time savings: 5 min/record → 30 sec/record

## Open Questions

1. **Fact Type**: Auto-create "Draft Registration" or require manual creation? → Recommend: Prompt on first use
2. **Image Download**: Enabled by default? → Recommend: Yes, with clear UI indication
3. **Duplicate Handling**: Skip, update, or ask? → Recommend: Skip with warning
4. **Place Management**: Auto-create or manual? → Recommend: Leave PlaceID=0 for Phase 1
5. **Batch Size**: Max limit? → Recommend: Warn at 500, limit at 2000
6. **Error Export**: CSV, Excel, JSON? → Recommend: CSV for Phase 1

## File Structure

```
src/rmcitecraft/
├── services/
│   ├── draft_file_reader.py              # Phase 1
│   ├── draft_citation_builder.py         # Phase 1
│   ├── draft_database_writer.py          # Phase 1
│   ├── draft_batch_processor.py          # Phase 1
│   ├── draft_person_matcher.py           # Phase 2
│   ├── draft_image_downloader.py         # Phase 3
│   ├── draft_media_manager.py            # Phase 3
│   └── draft_event_manager.py            # Phase 3
├── database/
│   └── draft_batch_state_repository.py   # Phase 2
├── ui/
│   ├── tabs/draft_processing_tab.py      # Phase 1
│   └── components/match_review_dialog.py # Phase 2
└── models/
    ├── draft_record.py                   # Phase 1
    ├── person_match.py                   # Phase 2
    └── batch_result.py                   # Phase 1
```

## Configuration Example

```python
DRAFT_PROCESSING_CONFIG = {
    'media_root_dir': Path('~/Genealogy/RootsMagic/Files'),
    'draft_media_subdir': 'Records - Draft Registration',
    'enable_image_download': True,
    'auto_create_events': True,
    'require_manual_review_threshold': 90,  # confidence %
    'max_concurrent_downloads': 3,
    'chrome_cdp_url': 'http://localhost:9222',
    'duplicate_source_action': 'reuse',
    'duplicate_citation_action': 'skip',
    'max_batch_size': 2000,
    'save_state_every_n_records': 10,
}
```
