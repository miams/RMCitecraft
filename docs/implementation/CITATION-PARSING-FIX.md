---
priority: reference
topics: [database, census, citation, testing, ui]
---

# Citation Parsing Fix - October 20, 2025

## Problem Report

User reported that citations 13345, 10018, 10252, 7940, and 8149 were not extracting FamilySearch URLs, even though the URLs were present in the database. Additionally, access dates needed to be formatted as "dd mmmm yyyy" (e.g., "3 January 2022") with no leading zero on single-digit days.

## Root Causes

### Issue 1: Year Pattern Not Matching "United States, Census" Format

**Citation 13345** had the format:
```
"United States, Census, 1950", , <i>FamilySearch</i> (https://...)
```

The existing pattern only matched:
- `"United States Census, 1940"` (no comma after "States")
- `"United States 1950 Census"` (year before "Census")

**Fix:** Updated `FS_YEAR_PATTERN` to handle optional comma after "United States":

```python
# Before:
FS_YEAR_PATTERN = re.compile(r"United States (?:Census,?\s*(\d{4})|(\d{4})\s+Census)", re.IGNORECASE)

# After:
FS_YEAR_PATTERN = re.compile(r"United States,?\s+(?:Census,?\s*(\d{4})|(\d{4})\s+Census)", re.IGNORECASE)
```

Now matches:
- `"United States Census, 1940"` ✅
- `"United States 1950 Census"` ✅
- `"United States, Census, 1950"` ✅ (NEW)

**Location:** `src/rmcitecraft/parsers/familysearch_parser.py:27`

### Issue 2: Wrong Parameter Used for Full Text in Detailed Format Parser

**Citations 10018, 10252, 7940, 8149** had URLs in the BLOB Footnote field, but the parser was using the wrong variable.

The `_parse_familysearch_format()` method at line 461 had:

```python
# WRONG - familysearch_entry is the context (SourceName), not the full citation
full_text = familysearch_entry if familysearch_entry else source_name
```

This caused the parser to extract URL/date from the SourceName (which doesn't have them) instead of from the full citation text.

**Fix:** Use `source_name` (which contains the full BLOB Footnote text) for URL/date extraction:

```python
# CORRECT - source_name contains the full citation text with URL
full_text = source_name
```

**Location:** `src/rmcitecraft/parsers/familysearch_parser.py:461-463`

### Issue 3: Access Date Format

User requirement: Access dates should be formatted as "dd mmmm yyyy" with:
- Day: Single digit for 1-9 (e.g., "3" not "03")
- Month: Fully spelled out (e.g., "January" not "Jan")
- Year: Four digits

**Formats to handle:**
- `"Tue Mar 19 21:29:33 UTC 2024"` (UTC timestamp)
- `"16 February 2020"` (day month year)
- `"accessed 12 January 2022"` (with "accessed" prefix)

**Fix:** Added `_format_access_date()` method to convert all date formats:

```python
def _format_access_date(self, date_str: str) -> str:
    """Convert various date formats to 'dd mmmm yyyy' format."""
    if not date_str:
        return ""

    # Remove 'accessed' prefix if present
    date_str = date_str.replace("accessed", "").strip()

    # Try different date formats
    date_formats = [
        "%a %b %d %H:%M:%S UTC %Y",  # "Tue Mar 19 21:29:33 UTC 2024"
        "%d %B %Y",                   # "16 February 2020"
        "%d %b %Y",                   # "16 Feb 2020"
    ]

    for fmt in date_formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            # Format as "d MMMM yyyy" (no leading zero on day)
            return dt.strftime("%-d %B %Y")
        except ValueError:
            continue

    # If no format matched, return original
    return date_str
```

Updated `_extract_access_date()` to call the formatting function:

```python
def _extract_access_date(self, text: str) -> str:
    """Extract and format access date."""
    match = self.ACCESS_DATE_PATTERN.search(text)
    if match:
        raw_date = match.group(1) or match.group(2) or ""
        return self._format_access_date(raw_date)  # Format the date
    return ""
```

**Location:** `src/rmcitecraft/parsers/familysearch_parser.py:299-341`

## Test Results

All 5 test citations now extract correctly:

| Citation | Year | Person | URL Extracted | Date Formatted |
|----------|------|--------|---------------|----------------|
| **13345** | 1950 | | ✅ Yes | ✅ 19 March 2024 |
| **10018** | 1940 | Ralph Craig | ✅ Yes | ✅ 16 February 2020 |
| **10252** | 1930 | William D Allbright | ✅ Yes | ✅ 12 January 2022 |
| **7940** | 1920 | Clinton W Allen | ✅ Yes | ✅ 14 December 2015 |
| **8149** | 1910 | William Allen | ✅ Yes | ✅ 20 October 2015 |

**Result:** 5/5 citations passed ✅

## Files Modified

1. **`src/rmcitecraft/parsers/familysearch_parser.py`**
   - Line 9: Added `from datetime import datetime` import
   - Line 27: Updated `FS_YEAR_PATTERN` to handle comma after "United States"
   - Lines 299-341: Added `_format_access_date()` method and updated `_extract_access_date()`
   - Lines 461-463: Fixed `full_text` assignment to use `source_name` instead of `familysearch_entry`

## Impact

**Before:**
- Citations with "United States, Census" format failed to parse
- Citations 10018, 10252, 7940, 8149 showed missing URLs (red error icon)
- Access dates had inconsistent formats (UTC timestamps, leading zeros)

**After:**
- All FamilySearch citation format variations now parse correctly
- URLs extract from all 5 test citations
- Access dates consistently formatted as "dd mmmm yyyy" (e.g., "3 January 2022")
- Fewer red error icons in Citation Manager (only truly missing URLs show red)

## Additional Notes

**Why the confusion with parameters?**

The parse function signature is:
```python
def parse(self, source_name: str, familysearch_entry: str, citation_id: int)
```

But the UI calls it like:
```python
parsed = parser.parse(parse_text, context_text, citation_id)
```

Where:
- `parse_text` = BLOB Footnote text (contains URL, full citation)
- `context_text` = SourceName (e.g., "Fed Census: 1940, Kansas...")

So the parameter names are misleading. In reality:
- `source_name` parameter = full citation text with URL
- `familysearch_entry` parameter = context/SourceName

The code was incorrectly assuming `familysearch_entry` had the full text.

## Documentation Status

✅ **Tested:** All 5 problem citations now parse correctly
✅ **Applied:** Changes are in the running application
✅ **Documented:** This file captures the fixes

---

**Status:** ✅ Complete
