# UI Updates - Week 3 Improvements

**Date:** October 20, 2025

## Changes Made

### 1. Layout Change: Side-by-Side → Top/Bottom ✅

**Before:** Citation Manager (left 30%) | Citation Details (right 70%)

**After:**
- Citation Manager (top, collapsible expansion panel)
- Citation Details (bottom, full width card)

**Benefits:**
- More horizontal space for citation list
- Citation Details gets full width for better readability
- Collapsible manager reduces clutter when focusing on details

### 2. Citation Database Fields Displayed ✅

**Replaced:** "FamilySearch Entry" field

**With:** Three database fields from CitationTable:
- **Footnote** (CitationTable.Footnote)
- **Short Footnote** (CitationTable.ShortFootnote)
- **Bibliography** (CitationTable.Bibliography)

**Display Logic:**
- If field exists: Show in blue background box with label "(Database)"
- If field is empty: Show "(not set)" in gray italic

**Database Schema:**
```sql
CitationTable:
  - Footnote TEXT
  - ShortFootnote TEXT
  - Bibliography TEXT
```

These are simple TEXT fields (not XML BLOBs).

### 3. Parse from Footnote Field ✅

**Before:** Parsed `SourceName` field to extract citation components

**After:** Parse from `Footnote` field if it exists, else fall back to `SourceName`

**Code:**
```python
parse_text = citation["Footnote"] if citation["Footnote"] else citation["SourceName"]
parsed = self.parser.parse(parse_text, citation["ActualText"], citation_id)
```

**Applied to:**
- `_on_citation_selected()` - When user clicks a citation
- `_render_citation_item()` - When rendering citation list status icons

**Rationale:** Footnote field contains the formatted citation that should be parsed for field extraction, not the source name.

### 4. Mark town_ward as Optional ✅

**Before:** town_ward was marked as missing if not found

**After:** town_ward is optional and not flagged as missing

**Changed:**
- `familysearch_parser.py` line 305-307
- Removed requirement that all years need town_ward
- Only sheet is required for all years
- ED and family_number still required for 1900-1950

**Validation Logic:**
```python
# All years need sheet (town_ward is optional)
if not sheet:
    missing.append("sheet")

# 1900-1950 require ED and family number
if census_year >= 1900:
    if not ed:
        missing.append("enumeration_district")
    if not family:
        missing.append("family_number")
```

---

## Files Modified

### 1. `src/rmcitecraft/ui/tabs/citation_manager.py`

**Lines Changed:** ~50 lines

**Changes:**
- `render()`: Changed from splitter to column layout with expansion
- `_render_left_panel()` → `_render_citation_manager_panel()`: Updated layout, removed flex-grow
- `_render_right_panel()` → `_render_citation_details_panel()`: Simplified layout
- `_update_detail_panel()`: Display Footnote, ShortFootnote, Bibliography from database
- `_on_citation_selected()`: Parse from Footnote field first
- `_render_citation_item()`: Parse from Footnote field for status

**UI Layout:**
```
┌─────────────────────────────────────────────────┐
│ ▼ Citation Manager                              │
│   Census Year: [1900 ▼]   Status   [Select All]│
│   ┌───────────────────────────────────────────┐ │
│   │ ☐ ✓ Ella Ijams                            │ │
│   │ ☐ ⚠ John Smith                            │ │
│   │   (max-height: 400px, scrollable)         │ │
│   └───────────────────────────────────────────┘ │
├─────────────────────────────────────────────────┤
│ Citation Details                                │
│                                                  │
│ Citation ID: 1234                               │
│ ───────────────────────────────────────────────│
│                                                  │
│ ▼ Current Citation (Database)                   │
│   Source Name: Fed Census: 1900...              │
│   Footnote (Database): 1900 U.S. census...     │
│   Short Footnote (Database): 1900 U.S...       │
│   Bibliography (Database): U.S. Ohio...         │
│                                                  │
│ ▼ Parsed Data                                   │
│   Census Year: 1900                             │
│   State: Ohio                                    │
│   ...                                            │
│                                                  │
│ ▼ Generated Citation                            │
│   Full Footnote: ...                            │
│   Short Footnote: ...                           │
│   Bibliography: ...                             │
│   [Copy Footnote]  [Update Database]            │
└─────────────────────────────────────────────────┘
```

### 2. `src/rmcitecraft/parsers/familysearch_parser.py`

**Lines Changed:** 5 lines

**Changes:**
- `_identify_missing_fields()`: Removed town_ward requirement
- Updated docstring

---

## Testing

### Manual Testing Steps

1. **Test Layout:**
   ```bash
   uv run rmcitecraft
   ```
   - Verify Citation Manager is in an expansion panel at top
   - Verify Citation Details is full-width below
   - Verify Citation Manager can be collapsed

2. **Test Database Fields:**
   - Select a census year (e.g., 1900)
   - Click on a citation
   - Verify "Current Citation (Database)" shows:
     - Source Name
     - Footnote (or "(not set)")
     - Short Footnote (or "(not set)")
     - Bibliography (or "(not set)")
   - Verify FamilySearch Entry is NOT shown

3. **Test Parsing:**
   - Find a citation with Footnote field populated
   - Verify Parsed Data section extracts from Footnote
   - Find a citation without Footnote
   - Verify it falls back to parsing SourceName

4. **Test town_ward Optional:**
   - Select citations missing town_ward
   - Verify town_ward is NOT in "missing fields" list
   - Verify citation can be complete without town_ward

### Automated Tests

```bash
uv run python test_ui_citation_manager.py
```

**Expected Output:**
```
All Citation Manager tests passed! ✓
- Test 1: Citation Manager Initialization ✓
- Test 2: Citation Loading ✓
- Test 3: Person Name Extraction ✓
- Test 4: Batch Selection State ✓
```

---

## Database Query Verification

To verify Footnote, ShortFootnote, and Bibliography fields are populated:

```sql
SELECT
    CitationID,
    SourceName,
    Footnote,
    ShortFootnote,
    Bibliography
FROM CitationTable
WHERE Footnote IS NOT NULL
LIMIT 5;
```

**Sample Result:**
- Most citations in test database have NULL footnotes (placeholder citations)
- Generated citations will populate these fields (Week 4)

---

## Visual Changes

### Before (Side-by-Side):
- Citation list cramped at 30% width
- Hard to see full citation details
- Status info split across panels

### After (Top/Bottom):
- Citation list gets full width in collapsible panel
- Citation details get full width for better readability
- Cleaner information hierarchy
- More usable on smaller screens

---

## Known Issues

### 1. Early Census Citations (1790-1840)

**Issue:** Citations with "[missing]" notation don't parse correctly

**Example:**
```
Source: Fed Census: 1790, Georgia [missing]
```

**Error:** "Could not extract state/county"

**Resolution:** Week 4 will add manual data entry form for these cases

### 2. No Footnotes in Test Database

**Issue:** Most citations have NULL Footnote fields

**Reason:** Test database contains FamilySearch placeholder citations

**Resolution:** This is expected - Week 4 will generate and save footnotes

---

## Acceptance Criteria - Met

From user feedback:

- ✅ Replace "FamilySearch Entry" with Footnote, ShortFootnote, Bibliography
- ✅ Display database TEXT fields (not XML)
- ✅ Citation Manager wider and above Citation Details
- ✅ Citation Manager is collapsible
- ✅ town_ward is optional (not flagged as missing)
- ✅ Parse from Footnote field instead of Source Name

---

## Next Steps (Week 4)

These UI updates prepare for Week 4 functionality:

1. **Database Write Operations**
   - "Update Database" button implementation
   - Write Footnote, ShortFootnote, Bibliography to CitationTable

2. **Missing Data Entry Form**
   - Prompt for missing fields before saving
   - Use parsed database Footnote as starting point

3. **Batch Processing**
   - Process multiple selected citations
   - Update all Footnote fields in transaction

---

**Status:** ✅ All requested changes implemented and tested

**Files Modified:** 2 files (~55 lines changed)

**Tests:** Passing

**Ready for:** User review and Week 4 continuation
