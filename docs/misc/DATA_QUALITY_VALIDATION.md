---
priority: archive
topics: [database, census, citation, batch, testing]
---

# Data Quality Validation for Census Citations

## Problem Identified

During batch processing of 1950 census entries (PersonIDs 11263, 4118, 7207), the FamilySearch extraction returned **incomplete data**:

```python
{
    'state': '',  # EMPTY!
    'county': '',  # EMPTY!
    'enumeration_district': '',  # EMPTY!
    'person_name': 'Verne D Adams',
    'familysearch_url': 'https://www.familysearch.org/ark:/61903/1:1:6XYT-2R3N',
}
```

**The system proceeded anyway**, creating invalid citations like:

```
1950 U.S. census,  County, , Verne D Adams; imaged, ...
                   ^^^^^^^^  <-- Missing state and county!
```

**Source names were not updated** (brackets remained empty):
```
Fed Census: 1950, Ohio, Stark [] Adams, Verne
                              ^^  <-- Should contain census details
```

## Solution: Automated Data Quality Checks

### New Validation Module

**File:** `src/rmcitecraft/validation/data_quality.py`

Provides comprehensive validation of extracted census data before database updates.

### Required Fields by Census Year

#### All Census Years (1790-1950)
- ✅ **State name**
- ✅ **County name**
- ✅ **Person name**
- ✅ **FamilySearch URL**

#### 1900-1950 Census
- ✅ **Enumeration District (ED)** - Critical for these years

#### 1850-1880 Census
- ✅ **Sheet number** - Recommended

### Validation Output

#### Failed Validation (Incomplete Data)
```
❌ Data quality validation FAILED
   3 critical errors
   Missing required fields: state, county, enumeration_district

❌ CRITICAL ERRORS:
  - Missing required field: State name (state)
  - Missing required field: County name (county)
  - Missing required field for 1950: Enumeration District (ED) (enumeration_district)

❌ SHOULD NOT PROCEED - Data quality check failed!
   Database update should be blocked until data is corrected.
```

#### Passed Validation (Complete Data)
```
✅ Data quality validation PASSED
   ℹ️  2 optional fields missing

✅ SAFE TO PROCEED with database update
```

## Integration into Workflow

### Updated Process Flow

```
1. Extract citation data from FamilySearch
   ↓
2. **VALIDATE data quality** ← NEW STEP
   ├─ If INVALID → Stop, log errors, skip entry
   └─ If VALID → Continue
   ↓
3. Update database/download image
```

### Code Integration Example

```python
from src.rmcitecraft.validation import validate_before_update

# After extraction
citation_data = await automation.extract_citation_data(familysearch_url)

# VALIDATE before proceeding
validation = validate_before_update(citation_data, census_year=1950)

if not validation:
    # Log validation errors
    print(validation.summary())
    for error in validation.errors:
        logger.error(f"Validation error: {error}")

    # STOP - do not update database
    log_entry['error'] = 'Data quality validation failed'
    log_entry['validation_errors'] = validation.errors
    return log_entry

# Safe to proceed - data is valid
metadata = ImageMetadata(...)
image_service.update_citation_fields_only(metadata)
```

## Why This Matters

### Data Integrity
- **Prevents incomplete citations** from polluting the database
- **Ensures Evidence Explained compliance** (complete citations required)
- **Maintains source name quality** (brackets must be filled)

### User Experience
- **Clear error messages** show exactly what's missing
- **Actionable feedback** helps user fix extraction issues
- **Audit trail** in logs shows why entries were skipped

### Database Quality
- **No blank fields** in formatted citations
- **Complete source names** with proper bracket content
- **Professional citations** meet genealogical standards

## Validation Rules

### Critical (Blocks Update)
1. State name must be present and > 2 characters
2. County name must be present and > 3 characters
3. Person name must be present and > 2 characters
4. FamilySearch URL must contain 'familysearch.org/ark:'
5. **For 1900-1950**: Enumeration District required
6. **For 1850-1880**: Sheet number recommended

### Warnings (Logged but Allowed)
- Optional fields missing (town/ward, line, family #)
- Short or unusual field values
- Non-standard formatting

## Testing Results

### Test 1: Incomplete Data (Current Problem)
```bash
python3 test_validation.py
```

**Input:**
```python
{'state': '', 'county': '', 'enumeration_district': '', ...}
```

**Result:** ❌ VALIDATION FAILED - 3 critical errors
**Action:** Database update BLOCKED

### Test 2: Complete Data
```python
{'state': 'Ohio', 'county': 'Stark', 'enumeration_district': '95-123', ...}
```

**Result:** ✅ VALIDATION PASSED
**Action:** Safe to proceed

## Impact on Current Codebase

### Files Modified

1. **New:** `src/rmcitecraft/validation/data_quality.py`
   - `CensusDataValidator` class
   - `ValidationResult` dataclass
   - `validate_before_update()` function

2. **New:** `src/rmcitecraft/validation/__init__.py`
   - Package initialization

3. **To Update:** `process_census_batch.py`
   - Add validation after extraction
   - Block database updates on validation failure
   - Log validation errors in Markdown report

4. **To Update:** `src/rmcitecraft/services/image_processing.py`
   - Add validation before `update_citation_fields_only()`
   - Return validation result in error messages

## Example Log Entry with Validation Errors

```markdown
## 1. ❌ Verne Dickey Adams

**Person ID:** 11263
**Citation ID:** 12255
**Event ID:** 33837

**Image Status:** ❌ Data quality validation failed
**Validation Errors:**
- Missing required field: State name (state)
- Missing required field: County name (county)
- Missing required field for 1950: Enumeration District (ED) (enumeration_district)

**Action Required:**
- Manually review FamilySearch page
- Verify extraction selectors are working
- Re-run after extraction issues are fixed

**FamilySearch URL:** [https://www.familysearch.org/ark:/61903/1:1:6XYT-2R3N](...)
```

## Root Cause Analysis

### Why Was State/County Missing?

Possible reasons:
1. **FamilySearch page selectors changed** - extraction logic needs updating
2. **Page not fully loaded** - need longer wait time
3. **Authentication issues** - FamilySearch requires sign-in
4. **Data not available on page** - some records lack location details

### Next Steps

1. ✅ **Add validation** - Implemented (this document)
2. 🔧 **Fix extraction** - Update FamilySearch selectors
3. 🔧 **Add fallback** - Parse location from SourceTable.Name if extraction fails
4. 🔧 **Improve logging** - Show exactly what was extracted vs expected

## Fallback Strategy

When extraction fails, parse from existing SourceTable.Name:

```python
# Source name format: "Fed Census: 1950, Ohio, Stark [] Adams, Verne"
def parse_location_from_source_name(source_name: str) -> tuple[str, str]:
    """Parse state and county from source name as fallback."""
    import re
    match = re.search(r'(\d{4}),\s*([^,]+),\s*([^\[\]]+)', source_name)
    if match:
        year, state, county = match.groups()
        return state.strip(), county.strip()
    return '', ''
```

This provides a safety net when FamilySearch extraction fails.

## Conclusion

**Data quality validation** is now a required step in the census processing workflow. It ensures:

✅ No incomplete data in database
✅ Clear error messages for debugging
✅ Professional-quality citations
✅ Audit trail in logs

**Next Action:** Integrate validation into `process_census_batch.py` and update batch processing workflow.
