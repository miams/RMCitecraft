# Citation Formatter Corrections for 1930 Census

**Date**: 2025-10-25
**Reference**: Mills, Elizabeth Shown. *Evidence Explained: Citing History Sources from Artifacts to Cyberspace: 4th Edition* (p. 253).

---

## Issues Found in UI-Generated Citation

The UI was generating:
```
1930 U.S. census, Greene County, Pennsylvania, population schedule, Jefferson, enumeration district (ED) 17, sheet 13A, family 281, George B Iams; imaged, "1930 United States Federal Census," FamilySearch (https://familysearch.org/ark:/61903/1:1:XH3Z-4J8 : accessed 7 November 2020).
```

## Corrections Applied

### 1. Removed "population schedule" for 1910-1940

**User Insight**:
> "In the Census from 1910-1940, only the population schedules have survived, thereby eliminating the need for citations to specify which schedule is being cited."

**Change**:
- **1910-1940**: Omit "population schedule" (redundant)
- **1900, 1950**: Include "population schedule" (multiple schedule types existed)

**Code** (`src/rmcitecraft/parsers/citation_formatter.py:60-63`):
```python
# 1910-1940: Omit "population schedule" (only schedules that survived)
# 1900 and 1950: Include "population schedule" if multiple schedule types exist
if c.census_year in [1900, 1950]:
    footnote_parts.append("population schedule,")
```

### 2. Changed Collection Title Format

**Old**: `"1930 United States Federal Census,"`
**New**: `"United States Census, 1930,"`

**Applies to**: Footnote only (bibliography uses different format)

**Code** (`src/rmcitecraft/parsers/citation_formatter.py:80-85`):
```python
# Add FamilySearch citation - correct format per Evidence Explained
# Collection title format: "United States Census, YYYY" (not "YYYY United States Federal Census")
footnote_parts.append(
    f'imaged, "United States Census, {c.census_year}," '
    f"<i>FamilySearch</i>, ({c.familysearch_url} : accessed {c.access_date})."
)
```

### 3. Added Line Number Support

**Issue**: `ParsedCitation` model was missing `line` field
**Fix**: Added `line: Optional[str] = None` to model

**Code** (`src/rmcitecraft/models/citation.py:24`):
```python
sheet: Optional[str] = None
line: Optional[str] = None  # Added
family_number: Optional[str] = None
```

**Formatter** (`src/rmcitecraft/parsers/citation_formatter.py:74-76`):
```python
# Line number (not family number) per Evidence Explained
if c.line:
    footnote_parts.append(f"line {c.line},")
```

### 4. Removed Family Number from Citation

**Issue**: Family number was being included in footnote
**Fix**: Removed `family_number` from footnote template (line number is used instead)

**Note**: Family number is still extracted and stored (may be used for internal tracking), but not included in Evidence Explained citations for 1900+.

---

## Expected Output (1930 Census)

### Footnote
```
1930 U.S. census, Greene County, Pennsylvania, Jefferson Township, enumeration district (ED) 30-17, sheet 13-A, line 15, George B Iams; imaged, "United States Census, 1930," <i>FamilySearch</i>, (https://www.familysearch.org/ark:/61903/1:1:XH3Z-4J8 : accessed 7 November 2020).
```

**Key Elements**:
- ✅ No "population schedule" (1910-1940)
- ✅ Township designation included ("Jefferson Township")
- ✅ Line number included ("line 15")
- ✅ NO family number
- ✅ Collection title: "United States Census, 1930"
- ✅ Comma before parenthesis: `, (`

### Short Footnote
```
1930 U.S. census, Greene Co., Pa., pop. sch., Jefferson, E.D. 30-17, sheet 13-A, George B Iams.
```

**Key Elements**:
- ✅ State abbreviated ("Pa.")
- ✅ "pop. sch." abbreviation
- ✅ "E.D." abbreviation
- ✅ No line number in short form
- ✅ No italics, no URL

### Bibliography
```
U.S. Pennsylvania. Greene County. 1930 U.S Census. Imaged. "1930 United States Federal Census". <i>FamilySearch</i> https://www.familysearch.org/ark:/61903/1:1:XH3Z-4J8 : 2020.
```

**Key Elements**:
- ✅ No "Population Schedule." for 1910-1940
- ✅ Collection title different from footnote: "1930 United States Federal Census"
- ✅ Access year only (not full date)

---

## Bibliography Format Differences

Evidence Explained uses **different collection title formats** for footnotes vs. bibliography:

| Citation Type | Collection Title Format |
|--------------|------------------------|
| **Footnote** | "United States Census, YYYY" |
| **Bibliography** | "YYYY United States Federal Census" |

This is intentional per Evidence Explained style guidelines.

---

## Files Modified

1. **`src/rmcitecraft/parsers/citation_formatter.py`**
   - Lines 39-141: Updated `_format_1900_1950()` method
   - Added comments citing Evidence Explained 4th ed., p. 253
   - Conditional logic for "population schedule" based on census year
   - Collection title format corrected
   - Line number support added

2. **`src/rmcitecraft/models/citation.py`**
   - Line 24: Added `line` field to `ParsedCitation` model
   - Line 69: Added `line` field to `CitationExtraction` model

---

## Testing

Run the citation formatter unit tests to verify:

```bash
uv run pytest tests/unit/test_citation_formatter.py -v
```

Expected results:
- ✅ 1930 census footnote matches Evidence Explained format
- ✅ No "population schedule" for years 1910-1940
- ✅ "population schedule" included for 1900 and 1950
- ✅ Line number appears when available
- ✅ Family number excluded from citations

---

## Additional Census Years

The same logic applies to other census years in the 1900-1950 range:

| Year | Pop. Schedule? | Line Number? | Notes |
|------|----------------|--------------|-------|
| 1900 | ✅ Yes | ✅ Preferred | Multiple schedule types |
| 1910 | ❌ No | ✅ Preferred | Only pop. schedules survived |
| 1920 | ❌ No | ✅ Preferred | Only pop. schedules survived |
| 1930 | ❌ No | ✅ Preferred | Only pop. schedules survived |
| 1940 | ❌ No | ✅ Preferred | Only pop. schedules survived |
| 1950 | ✅ Yes | ✅ Preferred | Multiple schedule types |

**Line number**: Always include when available (Evidence Explained preferred element for precise location).

---

**Last Updated**: 2025-10-25
**Status**: Corrections applied to `src/rmcitecraft/parsers/citation_formatter.py`
