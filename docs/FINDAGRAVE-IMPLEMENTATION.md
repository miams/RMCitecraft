# Find a Grave Batch Processing - Implementation Summary

## ✅ Completed Components

### 1. Core Services

**`src/rmcitecraft/services/findagrave_automation.py`**
- Browser automation via Playwright (connects to Chrome CDP)
- Extracts memorial data from Find a Grave pages
- Detects maiden names from HTML italics
- Downloads photos with metadata extraction

**`src/rmcitecraft/services/findagrave_formatter.py`**
- Evidence Explained citation formatting
- Source name generation: `"Find a Grave: Surname, GivenName (MaidenName) (YYYY-YYYY) RIN PersonID"`
- Image filename generation: `"Surname, GivenName (MaidenName) (YYYY-YYYY).jpg"`

**`src/rmcitecraft/services/findagrave_batch.py`**
- Batch processing controller with state management
- Status tracking: QUEUED → EXTRACTING → NEEDS_REVIEW → COMPLETE/ERROR
- Session management with progress tracking

### 2. Database Integration

**`src/rmcitecraft/database/findagrave_queries.py`**
- Queries URLTable for Find a Grave URLs (Name='Find a Grave')
- Filters out people who already have formatted citations
- Detects Evidence Explained format citations
- **Database stats**: 5,376 people with Find a Grave URLs

### 3. User Interface

**`src/rmcitecraft/ui/tabs/findagrave_batch.py`**
- Separate tab accessible from main navigation
- Two-panel layout: Queue (40%) + Details (60%)
- Batch loading with configurable size and offset
- Individual item extraction and photo downloads
- Status icons and color-coded queue items

**Main Application Integration**
- Added "Find a Grave" navigation button to header
- Tab switching between Census Batch, Find a Grave, and Citation Manager

### 4. Database Export (✅ Implemented)

**`src/rmcitecraft/database/findagrave_queries.py`** - Database write functions
- `create_findagrave_source_and_citation()` - Creates Source and Citation records
- `_build_source_fields_xml()` - Formats SourceTable.Fields BLOB (XML)
- `_build_citation_fields_xml()` - Formats CitationTable.Fields BLOB (XML)
- Properly stores citations in SourceTable.Fields for TemplateID=0 (free-form sources)
- Handles transactions with commit/rollback
- Returns created SourceID and CitationID

### 5. Test Suite (27 tests - all passing ✅)

**Unit Tests**
- `tests/unit/test_findagrave_formatter.py` (10 tests)
- `tests/unit/test_findagrave_queries.py` (11 tests - includes XML formatting tests)

**End-to-End Tests**
- `tests/test_findagrave_e2e.py` (6 tests)
- Validates against Ruth Eleanor's actual database citation

## 📁 Directory Structure for Images

Per requirements:
- **Person photos**: `~/Genealogy/RootsMagic/Files/Pictures - People`
  - Photo type: "Person"
  - Filename: `"Surname, GivenName (MaidenName) (YYYY-YYYY).jpg"`
- **Grave photos**: `~/Genealogy/RootsMagic/Files/Pictures - Cemetaries`
  - Photo type: "Grave"
  - Filename: `"Surname, GivenName (MaidenName) (YYYY-YYYY).jpg"` (with counter for multiples)
- **Family photos**: `~/Genealogy/RootsMagic/Files/Pictures - People` (TBD)
  - Photo type: "Family"
- **Other photos**: `~/Genealogy/RootsMagic/Files/Pictures - Other`
  - Photo type: "Other" or undefined

## 🔄 Workflow (Current Implementation)

1. **Load Batch** → Query database for people with Find a Grave URLs
2. **Select Person** → View memorial info and extracted data
3. **Extract Data** → Browser automation retrieves memorial details
4. **Format Citations** → Generate Evidence Explained format
5. **Save to Database** → Write Source and Citation records (TemplateID=0)
6. **Download Photos** → Save to appropriate directory with generated filename
7. **Mark Complete** → Status updates to COMPLETE with SourceID/CitationID

## 🚧 Needs Iteration (Complex Citation Linking)

### Issue #1: Burial Event Creation

**Requirement**: Create Burial event with Place location from Find a Grave
- **Place**: City, County, State (general location)
- **Place Details**: Specific cemetery name
- **Citation**: Link to this Burial event

**Implementation Needed**:
```python
# Create Burial event if doesn't exist
burial_event_id = create_burial_event(
    person_id=item.person_id,
    place=item.cemetery_location,  # "Amwell Township, Washington County, Pennsylvania"
    place_details=item.cemetery_name,  # "North Ten Mile Baptist Cemetery"
    death_year=item.death_year,
)

# Link citation to Burial event
link_citation_to_event(
    citation_id=citation_id,
    event_id=burial_event_id,
    event_type=BURIAL_EVENT_TYPE,
)
```

### Issue #2: Birth/Death Event Citations

**Requirement**: If birth/death dates exist in Find a Grave, those events may already have citations in RootsMagic

**Questions to Resolve**:
1. Should we check if Birth/Death events already exist?
2. If they exist with citations, should we add Find a Grave as a secondary citation?
3. If they exist without citations, should we add Find a Grave citation?
4. What's the priority order for citations? (Census vs Find a Grave)

**Implementation Needed**:
```python
# Check existing events
birth_event = find_event(person_id, EVENT_TYPE_BIRTH)
death_event = find_event(person_id, EVENT_TYPE_DEATH)

# Determine if Find a Grave citation should be added
# Option 1: Add as secondary citation if primary exists
# Option 2: Only add if no citation exists
# Option 3: User decides via UI checkbox
```

### Issue #3: Family Member Citations

**Requirement**: If spouse/family members are in Find a Grave, they should have citations too

**Complexity**:
- Find a Grave shows family relationships (spouse, parents, children)
- Each family member may have their own memorial
- Need to determine which relationships to process automatically

**Questions to Resolve**:
1. Should we automatically process family members?
2. How deep should the relationship tree go? (spouse only? parents/children? siblings?)
3. Should user select which family members to process?

**Implementation Needed**:
```python
# Extract family members from memorial page
family_members = extract_family_members(memorial_data)

# For each family member with a memorial:
for member in family_members:
    if member.memorial_url:
        # Option 1: Add to batch queue automatically
        # Option 2: Show in UI for user selection
        # Option 3: Create separate "family processing" workflow
```

## 📋 Recommended Iteration Plan

### Phase 1: Basic Burial Event Creation (Next Step)
1. Detect if Burial event exists for person
2. If not, create Burial event with cemetery info
3. Link Find a Grave citation to Burial event
4. Test with 5-10 people from database

### Phase 2: Birth/Death Event Decision Logic
1. Add UI toggle: "Link to Birth/Death events if they exist"
2. Check if events exist and have citations
3. User reviews before linking
4. Test with people who have existing Birth/Death events

### Phase 3: Family Member Processing
1. Extract family member info from memorial page
2. Show in UI as "Related Memorials" section
3. User selects which family members to process
4. Add selected family members to batch queue

### Phase 4: Advanced Features
1. Handle cenotaphs (no burial location)
2. Handle multiple burial locations
3. Handle cremation vs burial
4. Handle memorial-only entries (no grave)

## 🧪 Testing Status

**Database Query**: ✅ Working
- Found 5,376 people with Find a Grave URLs
- Correctly excludes Ruth Eleanor (Person ID 1095) who already has citation

**Citation Formatting**: ✅ Working
- Matches database format for Ruth Eleanor
- Source name follows pattern
- Image filename follows pattern

**Database Export**: ✅ Implemented
- Creates Source records (TemplateID=0)
- Creates Citation records
- Writes formatted citations to SourceTable.Fields BLOB (XML)
- All 27 tests passing

**UI**: ✅ Implemented
- Separate tab accessible from navigation
- Two-column layout with strict positioning: "Memorial Queue" (left 35%) + "Person Detail" (right 65%)
- Queue displays: PersonID, name, dates, memorial ID
- **Batch loading with offset support**: configurable size and offset for pagination
- **Checkbox selection**: properly cleared after processing (no accumulation)
- **Summary updates**: header stats refresh after each processing run
- Citations displayed without accordion (direct view with separators)
- Photo display with descriptions/captions when available
- Photo download capability via browser automation
- Real-time progress updates via logging (no notification errors)
- Status tracking (QUEUED → EXTRACTING → COMPLETE)

**Automation**: ✅ Implemented
- Browser automation via Playwright CDP
- Extract memorial data (person, cemetery, photos, contributor)
- **Photo downloads via browser context**:
  - Uses `context.request.get()` to maintain authentication/cookies
  - Fixed timeout issue (was using `page.expect_download()` which doesn't work for images)
  - Logs download size for verification
- Photo deduplication by ID
- Metadata extraction improvements:
  - **Contributor**: Full name + user ID from profile link (e.g., "Bill LaBach (46539089)")
  - **Photo Type**: Extracted from paragraph text containing "Photo type:"
  - **Photo Description**: Multi-strategy extraction:
    - Searches for `.photo-description`, `.photo-caption` elements
    - Fallback: scans all text elements, filters out metadata
    - Captures meaningful text (2+ words, skips "Added by", "Photo type")
    - Examples: "Mary Una Imes with Daughter Elizabeth", "World War I Draft Registration Cards, 1917-1918 for Geo Washington Akin"
  - **Added Date**: Extracted from "Added by" section
- **Filename handling**:
  - **All photos**: `Surname, GivenName (MaidenName) (YYYY-YYYY).jpg` (includes maiden name for females)
  - **When surname is empty**: Queries spouse's surname via FamilyTable, uses bracket notation: `[Laubach], Agnes (1648-1727).jpg`
  - **Multiple Grave photos**: Auto-increments counter if file exists: `_1.jpg`, `_2.jpg`, etc.
- **Photo directory routing by type**:
  - **Person** → `~/Genealogy/RootsMagic/Files/Pictures - People`
  - **Grave** → `~/Genealogy/RootsMagic/Files/Pictures - Cemetaries`
  - **Family** → `~/Genealogy/RootsMagic/Files/Pictures - People` (TBD: may choose not to download)
  - **Other** → `~/Genealogy/RootsMagic/Files/Pictures - Other`
  - **Undefined** → `~/Genealogy/RootsMagic/Files/Pictures - Other` (TBD: may use AI to categorize)

## 🎯 Next Steps

1. **Test end-to-end workflow** with real Chrome session and Find a Grave pages
2. **Implement Burial event creation** in database module
3. **Create citation → event linking** logic
4. **Test with 5-10 people** from database
5. **Iterate on complex cases** (birth/death events, family members)

## 📝 User Decisions Needed

1. **Burial Event Creation**:
   - Always create if doesn't exist? ✓
   - Overwrite existing burial location? (needs clarification)

2. **Birth/Death Events**:
   - Link Find a Grave as secondary citation? (needs clarification)
   - Only if no existing citations? (needs clarification)

3. **Family Members**:
   - Automatic processing? (needs clarification)
   - User selection required? (needs clarification)

---

**Status**: Core functionality complete (database export ✅). Ready for end-to-end testing and iterative refinement on complex workflows (burial events, birth/death event linking, family members).

**Test Coverage**: 27 tests passing (10 formatter + 11 database queries + 6 e2e)
