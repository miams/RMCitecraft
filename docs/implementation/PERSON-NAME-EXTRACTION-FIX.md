---
priority: reference
topics: [census, citation, testing, ui, automation]
---

# Person Name Extraction Fix - October 20, 2025

## Problem Report

User reported that person names were not being extracted from many citations. Two specific examples were provided:
- **Citation 9304**: Should extract "John Ijmes"
- **Citation 10643**: Should extract person name from "Entry for Wilbur L Gibson and Lela R Gibson"

## Root Causes

Both citations were routed to the simplified format parser (because they lack full location hierarchy), but the parser wasn't handling all the different minimal format variations.

### Issue 1: Minimal Format Not Recognized

**Citation 9304** has the format:
```
...(URL : date), John Ijmes, 1880; citing enumeration district...
```

This is a **minimal format** where:
- Person name appears directly after `), `
- Followed by year and semicolon
- Has "citing" details but no location hierarchy

The simplified parser only looked for "Entry for" pattern and didn't have fallback logic for names that appear directly after the closing parenthesis.

**Fix:** Added fallback pattern to extract person name from minimal format:

```python
else:
    # Try minimal format: "), Person Name, Year; citing"
    # Pattern: after "), " extract text until comma or semicolon
    import re
    minimal_pattern = re.search(r'\),\s*([^,;]+?)(?:,\s*\d{4}\s*;|,|;)', citation_text)
    if minimal_pattern:
        person_name = minimal_pattern.group(1).strip()
```

This pattern matches text after `), ` and stops at:
- Comma followed by year and semicolon (e.g., ", 1880;")
- Any comma or semicolon

**Location:** `src/rmcitecraft/parsers/familysearch_parser.py:575-581`

### Issue 2: Entry For Pattern Didn't Match Full Date Format

**Citation 10643** has the format:
```
...(URL : date), Entry for Wilbur L Gibson and Lela R Gibson, 10 April 1950.
```

The existing pattern was:
```python
ENTRY_FOR_PATTERN = re.compile(r"Entry for (.+?),\s*\d{4}\s*\.", re.IGNORECASE)
```

This expected just a year (`\d{4}`) but the actual format includes the full date "10 April 1950".

**Fix:** Updated pattern to handle both formats:

```python
# Before:
ENTRY_FOR_PATTERN = re.compile(r"Entry for (.+?),\s*\d{4}\s*\.", re.IGNORECASE)

# After: Handles both "Entry for Name, 1940." and "Entry for Name, 10 April 1950."
ENTRY_FOR_PATTERN = re.compile(r"Entry for (.+?),\s*(?:\d{1,2}\s+\w+\s+)?\d{4}\s*\.", re.IGNORECASE)
```

The optional group `(?:\d{1,2}\s+\w+\s+)?` matches "10 April " when present.

**Location:** `src/rmcitecraft/parsers/familysearch_parser.py:73`

## Format Variations Now Supported

The simplified format parser now handles three variations:

### 1. Entry For Format (1950 style)
```
"...), Entry for Wilbur L Gibson and Lela R Gibson, 10 April 1950."
```
- Uses "Entry for" prefix
- May include full date (DD Month YYYY) or just year
- Extracts first person when multiple names present

### 2. Minimal Format (older years)
```
"...), John Ijmes, 1880; citing enumeration district..."
```
- Person name directly after `), `
- Followed by year and semicolon
- No "Entry for" prefix

### 3. Simplified Format (already supported)
```
"...), Entry for Name, 1940."
```
- "Entry for" with just year
- No location details

## Test Results

| Citation | Format | Expected | Result | Status |
|----------|--------|----------|--------|--------|
| **9304** | Minimal | "John Ijmes" | "John Ijmes" | ✅ PASS |
| **10643** | Entry For (full date) | "Wilbur L Gibson" | "Wilbur L Gibson" | ✅ PASS |

Both citations now extract person names correctly, including proper given/surname splitting:
- Citation 9304: Given="John", Surname="Ijmes"
- Citation 10643: Given="Wilbur L", Surname="Gibson"

## Files Modified

**`src/rmcitecraft/parsers/familysearch_parser.py`:**

1. **Line 73:** Updated `ENTRY_FOR_PATTERN` to handle full date format
   ```python
   ENTRY_FOR_PATTERN = re.compile(r"Entry for (.+?),\s*(?:\d{1,2}\s+\w+\s+)?\d{4}\s*\.", re.IGNORECASE)
   ```

2. **Lines 575-581:** Added minimal format fallback pattern
   ```python
   else:
       # Try minimal format: "), Person Name, Year; citing"
       minimal_pattern = re.search(r'\),\s*([^,;]+?)(?:,\s*\d{4}\s*;|,|;)', citation_text)
       if minimal_pattern:
           person_name = minimal_pattern.group(1).strip()
   ```

3. **Lines 583-592:** Refactored name splitting logic to work with both patterns

## Impact

**Before:**
- Citations with minimal format showed empty person names
- "Entry for" citations with full dates failed to match pattern
- Many citations displayed with no person name in UI

**After:**
- Person names extract from minimal format (e.g., Citation 9304)
- "Entry for" pattern handles both year-only and full date formats
- More citations show person names in Citation Manager

## Known Limitations

The user mentioned: "It is frequently wrong, but that's a separate issue."

This suggests there are other person name extraction issues beyond these two patterns. However, those would require additional investigation with specific examples. The current fixes address the two reported citation formats.

### Potential Future Issues:

1. **Household member names**: Citations like "John Smith in household of Mary Smith" may extract wrong name
2. **Name variations**: Nicknames, Jr./Sr. suffixes, hyphenated names
3. **Multiple people**: Pattern takes first person when multiple names present (intentional)
4. **Location hierarchy formats**: Some detailed citations may still fail if location format is unusual

These would need to be addressed as specific cases are reported.

## Documentation Status

✅ **Tested:** Both reported citations now extract correctly
✅ **Applied:** Changes are in the running application
✅ **Documented:** This file captures the fixes

---

**Status:** ✅ Complete

**Note:** User should report additional specific citation IDs where person names are incorrect for further investigation.
