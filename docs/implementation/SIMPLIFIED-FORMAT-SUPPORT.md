# Simplified FamilySearch Format Support

**Date:** October 20, 2025

## Overview

Added parser support for **simplified FamilySearch citation format** - a minimal format that FamilySearch currently uses which lacks detailed census information.

## Problem

Citation ID 10859 demonstrates the simplified format:

**SourceFields BLOB contains:**
```
"United States Census, 1940", , <i>FamilySearch</i> (https://www.familysearch.org/ark:/61903/1:1:K98H-Z4N : Tue Oct 03 04:25:40 UTC 2023), Entry for Herbert E Ijans and Nelle S Ijans, 1940.
```

**SourceName contains:**
```
Fed Census: 1940, California, San Bernardino [] Ijams, Herbert E.
```

This format is "quite lacking in details" (user's words) and represents how FamilySearch currently sends citation information.

### What's Missing from Simplified Format:

❌ Enumeration District (ED)
❌ Sheet number
❌ Family number
❌ Dwelling number
❌ Town/Ward information
❌ "citing" section with census details

### What's Available:

✅ Census year
✅ Person name(s) - from "Entry for" pattern
✅ FamilySearch URL
✅ Access date
✅ State/County - from RM SourceName

## Solution

### 1. Format Detection

Parser now detects three formats:

1. **SourceName format**: `Fed Census: 1900, Ohio, Noble [citing...] Person`
2. **Detailed FamilySearch format**: `"United States Census, 1940," database with images, FamilySearch (URL), Person, Town, County, State, United States; citing...`
3. **Simplified FamilySearch format** (NEW): `"United States Census, 1940", , FamilySearch (URL), Entry for Person Names, 1940.`

Detection logic:
```python
# Detect FamilySearch format by year pattern
is_familysearch_format = FS_YEAR_PATTERN.search(source_name) is not None

if is_familysearch_format:
    # Try to parse location hierarchy
    if location_hierarchy_found:
        return _parse_familysearch_format()  # Detailed format
    else:
        return _parse_simplified_familysearch_format()  # Simplified format
else:
    return _parse_sourcename_format()  # Legacy format
```

### 2. New Pattern

Added pattern to extract person names from "Entry for" text:

```python
# Pattern for simplified FamilySearch format: "Entry for Person Name(s), Year"
ENTRY_FOR_PATTERN = re.compile(r"Entry for (.+?),\s*\d{4}\s*\.", re.IGNORECASE)
```

**Examples:**
- `"Entry for Herbert E Ijans and Nelle S Ijans, 1940."` → `"Herbert E Ijans"`
- `"Entry for John Smith, 1930."` → `"John Smith"`

Handles multiple names by taking the first person mentioned.

### 3. Enhanced Access Date Pattern

Updated to handle both formats:

**Before:**
```python
ACCESS_DATE_PATTERN = re.compile(r"accessed (\d{1,2} \w+ \d{4})", re.IGNORECASE)
```

**After:**
```python
# Matches both formats:
# "accessed DD MMM YYYY" (detailed format)
# ": DDD MMM DD HH:MM:SS UTC YYYY" (simplified format)
ACCESS_DATE_PATTERN = re.compile(
    r"(?:accessed\s+)?(\d{1,2} \w+ \d{4})|:\s+([A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d{1,2}\s+[\d:]{8}\s+UTC\s+\d{4})",
    re.IGNORECASE,
)
```

### 4. Simplified Parser Method

Created `_parse_simplified_familysearch_format()`:

**Extraction Logic:**
```python
def _parse_simplified_familysearch_format(...):
    # Citation text (BLOB) contains: year, URL, date, person names
    citation_text = source_name

    # RM SourceName contains: state, county
    rm_source_name = familysearch_entry

    # Extract person names from "Entry for" pattern
    entry_match = ENTRY_FOR_PATTERN.search(citation_text)
    # Handle: "Herbert E Ijans and Nelle S Ijans" → "Herbert E Ijans"

    # Extract state/county from RM SourceName
    # "Fed Census: 1940, California, San Bernardino [] Person"

    # Extract URL and date from citation text
    url = _extract_url(citation_text)
    access_date = _extract_access_date(citation_text)

    # Mark missing fields
    missing_fields = ["enumeration_district", "sheet", "family_number"]
    is_complete = False  # Simplified format is never complete
```

### 5. UI Integration

Updated `citation_manager.py` to pass SourceName as context:

```python
# Priority for parsing: Footnote > Source.Footnote > Free Form > SourceName
parse_text = citation["Footnote"] or source_footnote or freeform_text or source_name

# Pass SourceName as second parameter for state/county extraction
context_text = citation["ActualText"] if citation["ActualText"] else source_name

parsed = self.parser.parse(parse_text, context_text, citation_id)
```

This allows the simplified parser to:
- Get citation text (with URL/date) from first parameter
- Get SourceName (with state/county) from second parameter

## Test Results

### Input:

**Citation Text (from SourceFields BLOB):**
```
"United States Census, 1940", , <i>FamilySearch</i> (https://www.familysearch.org/ark:/61903/1:1:K98H-Z4N : Tue Oct 03 04:25:40 UTC 2023), Entry for Herbert E Ijans and Nelle S Ijans, 1940.
```

**RM SourceName (context):**
```
Fed Census: 1940, California, San Bernardino [] Ijams, Herbert E.
```

### Output:

```
Census Year:           1940 ✓
State:                 California ✓
County:                San Bernardino ✓
Person Name:           Herbert E Ijans ✓
Given Name:            Herbert E ✓
Surname:               Ijans ✓
FamilySearch URL:      https://www.familysearch.org/ark:/61903/1:1:K98H-Z4N ✓
Access Date:           Tue Oct 03 04:25:40 UTC 2023 ✓

Missing Fields:        ['enumeration_district', 'sheet', 'family_number']
Is Complete:           False
```

## Format Comparison

| Field | SourceName Format | Detailed FS Format | Simplified FS Format |
|-------|-------------------|--------------------|-----------------------|
| **Year** | ✓ `Fed Census: 1900` | ✓ `United States Census, 1940` | ✓ `United States Census, 1940` |
| **State** | ✓ `Ohio` | ✓ `Arizona` | ✓ (from SourceName) |
| **County** | ✓ `Noble` | ✓ `Graham` | ✓ (from SourceName) |
| **Town/Ward** | - | ✓ `Safford, District 1` | ❌ Not available |
| **Person** | ✓ `Ijams, Ella` | ✓ `Sheldon L Ijams` | ✓ `Herbert E Ijans` |
| **ED** | ✓ (from [citing...]) | ✓ `5-1B` | ❌ Not available |
| **Sheet** | ✓ (from [citing...]) | ✓ `7B` | ❌ Not available |
| **Family** | ✓ (from [citing...]) | ✓ `190` | ❌ Not available |
| **URL** | - | ✓ | ✓ |
| **Access Date** | - | ✓ | ✓ |

## Files Modified

### `src/rmcitecraft/parsers/familysearch_parser.py`

**Added:**
- `ENTRY_FOR_PATTERN` - Extract person names from "Entry for..." text
- `_parse_simplified_familysearch_format()` - New parser method (~110 lines)

**Modified:**
- `ACCESS_DATE_PATTERN` - Handle both date formats
- `_extract_access_date()` - Return whichever group matched
- `_parse_familysearch_format()` - Fall back to simplified parser when location hierarchy not found

**Lines Changed:** ~120 lines

### `src/rmcitecraft/ui/tabs/citation_manager.py`

**Modified:**
- `_on_citation_selected()` - Pass SourceName as context for simplified format
- `_render_citation_item()` - Pass SourceName as context for simplified format

**Lines Changed:** ~10 lines

## Known Limitations

### 1. Incomplete Citations

Simplified format citations will **always** be marked as incomplete:
- Missing: ED, sheet, family number
- Cannot generate complete *Evidence Explained* citations
- User must manually enter missing data

### 2. Multiple Person Names

Pattern extracts only the first person:
- `"Entry for John Smith and Mary Smith"` → `"John Smith"`
- Spouse/household members are ignored

### 3. No Citation Details

No "citing" section means:
- No NARA publication number
- No FHL microfilm number
- No page/sheet reference
- No image quality indicators

### 4. State/County Dependency

Simplified parser **requires** RM SourceName for state/county:
- If SourceName doesn't follow `Fed Census: YYYY, State, County` format
- State/county will be missing
- Citations will have additional missing fields

## Future Enhancements

### Option 1: User Data Entry Form (Week 4 Task 2)
- Show form for missing fields
- Pre-fill with parsed data
- User manually enters ED, sheet, family from FamilySearch page
- "Open FamilySearch" button to view source while entering data

### Option 2: Browser Extension (Future)
- Auto-extract from FamilySearch page
- Fill missing fields automatically
- No manual data entry required

### Option 3: LLM Enhancement (Future)
- Use LLM to extract from free-form text
- Handle variations in simplified format
- Infer missing data from context
- But still limited by what FamilySearch provides

## User Impact

### What Works:
✅ Parser no longer crashes on simplified format
✅ Extracts all available data (year, state, county, person, URL, date)
✅ Clearly indicates missing fields
✅ Can generate partial citations
✅ User can see which fields need manual entry

### What's Needed:
⚠️ User must manually complete citations
⚠️ Cannot generate full *Evidence Explained* format
⚠️ Week 4 Task 2 (missing data form) becomes critical

## Summary

✅ **Simplified FamilySearch format now fully supported**

The parser now handles three distinct citation formats:
1. **SourceName** (legacy)
2. **Detailed FamilySearch** (full census details)
3. **Simplified FamilySearch** (minimal details) - NEW

**For Citation ID 10859:**
- Before: Parser error, no extraction
- After: Extracts 8 fields, identifies 3 missing fields

**Next Priority:** Implement Week 4 Task 2 (missing data input form) to allow users to complete simplified format citations.

---

**Documentation:** This file documents the simplified format support added on October 20, 2025.
