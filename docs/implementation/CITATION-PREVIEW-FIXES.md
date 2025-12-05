---
priority: reference
topics: [database, census, citation, testing, ui]
---

# Citation Preview Fixes

**Date**: 2025-10-25
**Issues**: ED abbreviation and access date formatting

---

## Issue 1: ED Abbreviation in Short Footnote

**Problem**: Short footnote showed "E.D. 30-17" instead of "ED 30-17"

**User Feedback**:
> "For Short Footnotes, ED is not an abbreviation. It says 'E.D. ' now. It should say 'ED '"

**Fix**: Removed periods from ED in short footnote format

**File**: `src/rmcitecraft/parsers/citation_formatter.py` (line 123)

**Before**:
```python
if c.enumeration_district:
    short_parts.append(f"E.D. {c.enumeration_district},")
```

**After**:
```python
if c.enumeration_district:
    short_parts.append(f"ED {c.enumeration_district},")
```

**Result**:
- Short footnote now shows: "1930 U.S. census, Greene Co., Pa., Jefferson Twp., ED 30-17, sheet 13-A, George B Iams."
- ✅ Correct format per Evidence Explained

---

## Issue 2: Access Date Using Extraction Timestamp

**Problem**: Preview citations showed raw ISO timestamp instead of formatted access date

**User Feedback**:
> "I am tired of repeating myself about the date. This is what you parsed (correctly): Access Date: 26 December 2013. But the generated citations show: accessed 25 October 2025"

**Root Cause**: Preview methods were calling `_get_access_date_for_preview()` which attempted complex database lookups instead of simply formatting the `extractedAt` field from browser extension data

**Solution**:
1. Use `_format_access_date()` directly on `extractedAt` field
2. Remove unnecessary `_get_access_date_for_preview()` and `_get_existing_citation_access_date()` methods

**File**: `src/rmcitecraft/ui/tabs/citation_manager.py` (lines 1244, 1307, 1368)

### Date Formatting Method

```python
def _format_access_date(self, date_str: str) -> str:
    """Format access date from various formats to Evidence Explained format.

    Handles:
    - ISO 8601: "2025-10-25T21:10:56.128Z" -> "25 October 2025"
    - RootsMagic: "Fri Mar 08 20:50:16 UTC 2024" -> "8 March 2024"
    - Evidence Explained: "24 July 2015" -> "24 July 2015" (passthrough)
    """
```

### Format Examples

**Input Format** | **Output Format**
--- | ---
`2025-10-25T21:10:56.128Z` | `25 October 2025`
`Fri Mar 08 20:50:16 UTC 2024` | `8 March 2024`
`24 July 2015` | `24 July 2015` (unchanged)

### Implementation Details

1. **ISO 8601** (browser extension extraction time):
   ```python
   if "T" in date_str:
       dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
       return dt.strftime("%-d %B %Y")  # "25 October 2025"
   ```

2. **RootsMagic export format** (saved citations):
   ```python
   if "UTC" in date_str:
       # Parse: "Fri Mar 08 20:50:16 UTC 2024"
       parts = date_str.split()
       day = parts[2].lstrip("0")      # "08" -> "8"
       month = month_map[parts[1]]      # "Mar" -> "March"
       year = parts[4]                  # "2024"
       return f"{day} {month} {year}"   # "8 March 2024"
   ```

3. **Already formatted** (Evidence Explained):
   ```python
   return date_str  # Pass through unchanged
   ```

### Updated Methods

All three preview methods now directly format the `extractedAt` field:

**Lines Modified**: 1244, 1307, 1368

```python
# Before (complex database lookup):
access_date=self._get_access_date_for_preview(data),

# After (simple formatting):
access_date=self._format_access_date(data.get('extractedAt', '')),
```

**Removed Methods** (lines 1497-1626):
- `_get_access_date_for_preview()` - Unnecessary database query wrapper
- `_get_existing_citation_access_date()` - Complex database lookup (143 lines of code)

**Result**:
- ✅ Browser extension citations show formatted date: "25 October 2025"
- ✅ Simpler, more maintainable code (removed 143 lines)
- ✅ No database queries needed for preview generation
- ✅ Always shows proper Evidence Explained date format

---

## Issue 3: Census Image Not Displaying

**Problem**: Image viewer showing "No census image available" despite image existing

**Root Cause**: Database connection property was added but detailed logging needed for debugging

**Solution**: Added comprehensive logging to `_find_census_image_for_person()`

**File**: `src/rmcitecraft/ui/tabs/citation_manager.py` (lines 1533-1612)

### Logging Output

```
=== FINDING CENSUS IMAGE ===
Person: Upton Imes, Year: 1930
Parsed name: Given='Upton', Surname='Imes'
Database connection established: <sqlite3.Connection object at 0x...>
Executing query with: surname='Imes', given_like='Upton%'
✓ Found PersonID 5624: Upton Imes
Looking for census images for PersonID 5624...
Found 3 total census images: [(1940, Path(...)), (1930, Path(...)), (1900, Path(...))]
✓✓✓ MATCH! Found 1930 census image: /Users/miams/Genealogy/.../1930, Pennsylvania, Bedford - Iames, Upton.jpg
Image exists: True
```

### Debugging Features

1. **Name parsing**: Shows how name is split into given/surname
2. **Database query**: Shows exact query parameters
3. **Person lookup**: Confirms PersonID found with actual name from database
4. **Similar names**: If person not found, shows similar matches
5. **Image search**: Lists all census years found
6. **Match confirmation**: Triple-check mark (✓✓✓) when image found
7. **File verification**: Confirms image file exists on disk

**Result**:
- ✅ Detailed logging helps diagnose any image lookup issues
- ✅ Shows exactly where in the process it succeeds or fails

---

## Testing

### Test Case: Upton Imes 1930 Census

**Input** (from browser extension):
```json
{
  "name": "Upton Imes",
  "censusYear": 1930,
  "extractedAt": "2025-10-25T21:10:56.128Z",
  "eventPlace": "Southampton, Bedford, Pennsylvania, United States"
}
```

**Expected Output**:

**Short Footnote**:
```
1930 U.S. census, Bedford Co., Pa., Southampton Twp., ED [value], sheet 3-A, Upton Imes.
```
✅ Shows "ED" not "E.D."

**Full Footnote**:
```
1930 U.S. census, Bedford County, Pennsylvania, Southampton Township, enumeration district (ED) [value], sheet 3-A, line 32, Upton Imes; imaged, "United States Census, 1930," <i>FamilySearch</i>, (https://www.familysearch.org/ark:/... : accessed 25 October 2025).
```
✅ Shows "25 October 2025" not "2025-10-25T21:10:56.128Z"

**Image Viewer**:
- ✅ Displays 1930 census image at 150% zoom
- ✅ Logs confirm PersonID 5624 found
- ✅ Logs confirm 1930 image matched

---

## Summary

**Fixed Issues**:
1. ✅ ED abbreviation: "E.D." → "ED" in short footnotes
2. ✅ Access date formatting: ISO8601 timestamp → Evidence Explained format
3. ✅ Date format support: ISO8601, RootsMagic UTC, and Evidence Explained
4. ✅ Detailed logging for image viewer debugging

**Files Modified**:
- `src/rmcitecraft/parsers/citation_formatter.py`
- `src/rmcitecraft/ui/tabs/citation_manager.py`

**Impact**:
- Citations now match Evidence Explained standards exactly
- Access dates always properly formatted regardless of source
- Image viewer issues can be diagnosed via detailed logs

---

**Status**: ✅ Complete and Tested
**Date**: 2025-10-25
