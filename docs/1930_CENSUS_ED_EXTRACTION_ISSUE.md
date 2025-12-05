---
priority: reference
topics: [database, census, citation, batch, testing]
---

# 1930 Census Enumeration District (ED) Extraction Issue

## Problem Summary

All 6 tested 1930 census entries failed validation with the error:
```
Missing required field for 1930: Enumeration District (ED) (enumeration_district)
```

**Date Tested**: November 6, 2025
**Log File**: `docs/misc/census_batch_1930_20251106_170705.md`

## Root Cause Analysis

### 1. Citation Data Status

The 1930 census citations in the database have:

- **SourceTable.Fields** (TemplateID=0): Contains placeholder FamilySearch formatting
  - Example: `"United States Census, 1930", database with images, <i>FamilySearch</i> (https://www.familysearch.org/ark:/61903/1:1:X4CT-WY9 : Thu Sep 21 20:37:15 UTC 2023), Entry for Henry Arnold and Catherine Arnold, 1930.`
  - This format includes the FamilySearch URL but no census details (ED, sheet, line, etc.)

- **CitationTable.ActualText**: Empty
  - No raw FamilySearch entry text saved
  - Cannot extract census details from citation text

- **CitationTable.RefNumber**: Empty
  - FamilySearch URL only exists in the formatted footnote text

- **CitationTable.Fields**: Contains empty "Page" field
  - `<Field><Name>Page</Name><Value /></Field>`

### 2. FamilySearch Page Extraction

The batch processing script successfully:

1. ✅ Extracted FamilySearch URLs from SourceTable.Fields footnotes using regex
2. ✅ Visited the FamilySearch pages via Playwright automation
3. ✅ Extracted state and county from event place
4. ❌ **Failed to extract Enumeration District** from page table fields

The JavaScript scraper in `familysearch_automation.py` looks for ED in table labels matching:
- `label.includes('enumeration')`
- `label === 'ed'`
- `label === 'e.d.'`

**Hypothesis**: 1930 FamilySearch pages either:
- Don't display ED in labeled table rows
- Use different label text that doesn't match our patterns
- Store ED in a different page element (not in data tables)
- Require viewing the actual census image to see ED

### 3. Data Flow Comparison

**1940 Census (Working)**:
- ActualText field populated with detailed FamilySearch citation
- RefNumber field has FamilySearch URL
- Page tables contain ED, sheet, line fields
- Extraction succeeds → validation passes → citations formatted

**1930 Census (Failing)**:
- ActualText field empty (no raw citation)
- RefNumber field empty
- Only formatted footnote contains FamilySearch URL
- Page tables don't expose ED
- Extraction returns empty ED → validation fails

## Tested Entries

All failed with same error:

| Person | Citation ID | Location | URL |
|--------|------------|----------|-----|
| Henry Arnold | 10622 | Shelby, Ohio | https://www.familysearch.org/ark:/61903/1:1:X4CT-WY9 |
| Charles Colvin Bowser | 10897 | Blair, Pennsylvania | https://www.familysearch.org/ark:/61903/1:1:XH83-DN9 |
| Louisa Lonita Clark | 10754 | Forsyth, North Carolina | https://www.familysearch.org/ark:/61903/1:1:X3SB-M39 |
| Rosa Jane Daugherty | 12426 | Macon, Illinois | https://www.familysearch.org/ark:/61903/1:1:XSBY-NGH |
| Julia E. Depoy | 11029 | Whitley, Indiana | https://www.familysearch.org/ark:/61903/1:1:X418-WQH |
| Bertha M. Detterline | 10916 | Montgomery, Pennsylvania | https://www.familysearch.org/ark:/61903/1:1:XHZQ-KWJ |

## Proposed Solutions

### Option 1: Manual Entry via Batch Processing UI (Recommended)

**Status**: UI design completed in `docs/architecture/BATCH_PROCESSING_UI_DESIGN.md`

**Approach**:
1. Batch processing extracts all available fields from FamilySearch pages
2. Validation identifies missing required fields (ED, sheet, line)
3. UI presents missing fields form + FamilySearch image viewer side-by-side
4. User views census image and manually enters visible ED
5. System generates proper Evidence Explained citations with complete data

**Advantages**:
- Works for all census years and edge cases
- Handles any missing data scenario
- User verifies data accuracy by viewing original image
- Supports efficient keyboard-first workflow for 100s-1000s of entries

**Timeline**:
- Phase 1 (Core Batch UI): Weeks 1-2
- Phase 2 (Missing Data Form): Week 3
- Phase 3 (Image Viewer Integration): Week 4

### Option 2: Enhanced FamilySearch Page Scraping

**Approach**:
1. Manually visit one of the 1930 URLs to inspect page structure
2. Identify where ED is displayed (if at all)
3. Add new selectors/patterns to `familysearch_automation.py`
4. Test extraction on 1930 pages

**Investigation Steps**:
```python
# Visit: https://www.familysearch.org/ark:/61903/1:1:X4CT-WY9
# Check:
# - Page source HTML structure
# - Data table labels and values
# - Metadata in JavaScript objects
# - Image metadata/annotations
# - Different page sections/tabs
```

**Limitations**:
- May not work if ED not exposed in page data
- Requires maintenance as FamilySearch updates page structure
- Doesn't solve problem if ED only visible on census image

### Option 3: Relaxed Validation for Existing Citations

**Approach**:
- Make ED optional for citations that already exist in database
- Keep ED required for new citations being created
- Add flag to distinguish "legacy citations" vs "new citations"

**Implementation**:
```python
# In validation/census_data.py
def validate_census_data(data: dict, census_year: int, is_legacy: bool = False) -> ValidationResult:
    # ... existing validation ...

    # Relax ED requirement for legacy citations
    if is_legacy and census_year in range(1900, 1951):
        required_fields.remove('enumeration_district')  # Make optional
```

**Advantages**:
- Allows processing of existing citations without manual data entry
- Still enforces quality standards for new citations
- Simple code change

**Disadvantages**:
- Results in citations with incomplete data
- Not Evidence Explained compliant without ED
- User may prefer to complete the data properly

### Option 4: Hybrid Approach

**Approach**:
1. Try enhanced scraping (Option 2) first
2. If extraction still fails, mark fields as "requires manual entry"
3. Use batch UI (Option 1) for manual data entry
4. Track which citations have complete vs incomplete data

**Advantages**:
- Maximizes automated extraction
- Falls back to manual entry when needed
- Maintains data quality standards
- Provides clear audit trail

## Recommendation

**Proceed with Option 1 (Manual Entry via Batch UI)** as the primary solution because:

1. **Already designed**: Comprehensive UI spec completed in `docs/architecture/BATCH_PROCESSING_UI_DESIGN.md`
2. **Handles all edge cases**: Not limited to 1930 census or ED extraction
3. **Better data quality**: User verifies data by viewing original images
4. **Scalable**: Designed for efficient processing of 100s-1000s of entries
5. **Evidence Explained compliant**: Results in complete, accurate citations

**Additionally investigate Option 2** as a quick test:
- Visit one 1930 FamilySearch URL manually
- Inspect page structure for ED location
- If found, add enhanced selectors
- This could reduce manual entry workload

## Next Steps

1. **Manual Investigation** (30 minutes)
   - Visit https://www.familysearch.org/ark:/61903/1:1:X4CT-WY9
   - Inspect page HTML for ED location
   - Document findings

2. **If ED found on page** → Implement enhanced scraping
   - Update `familysearch_automation.py` selectors
   - Test on all 6 failed entries
   - Document new patterns

3. **If ED not on page or still failing** → Proceed with Batch UI implementation
   - Start Phase 1: Core three-panel layout
   - Implement missing fields detection
   - Build data entry form with keyboard shortcuts
   - Integrate FamilySearch image viewer

4. **Update validation logic** (regardless of approach)
   - Track which fields were auto-extracted vs manually entered
   - Add audit trail for data sources
   - Provide clear feedback on data completeness

## Related Documentation

- Batch UI Design: `docs/architecture/BATCH_PROCESSING_UI_DESIGN.md`
- FamilySearch Automation: `src/rmcitecraft/services/familysearch_automation.py`
- Validation Module: `src/rmcitecraft/validation/census_data.py`
- 1930 Test Log: `docs/misc/census_batch_1930_20251106_170705.md`

---

**Last Updated**: November 6, 2025
**Status**: Investigation and solution design phase
