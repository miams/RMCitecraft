# Pre-1900 Census Data Analysis (1860-1880)

**Date**: 2025-10-20
**Source**: `logs/pending_citations.json` - Records 9, 10, 11

## Overview

Analysis of extracted data from 1860, 1870, and 1880 US Federal Census records showing significant field differences from later census years.

---

## 1880 Census (John W. Yams)

```json
{
  "censusYear": null,  // ⚠️ NOT EXTRACTED (should parse from eventDate: "1880")
  "name": "John W. Yams",
  "sex": "Male",
  "age": "33",
  "birthYear": "1847",
  "birthplace": "Ohio, United States",
  "race": "White",
  "relationship": "Self",  // ⚠️ Unusual value (not "Head")
  "maritalStatus": "Married",
  "occupation": "Farmer",
  "industry": null,
  "eventDate": "1880",
  "eventPlace": "Oskaloosa, Jefferson, Kansas, United States",
  "eventPlaceOriginal": "Oskaloosa, ED 113, Jefferson, KS, United States",
  "eventType": "Census",
  "enumerationDistrict": null,  // ⚠️ Should parse from eventPlaceOriginal: "ED 113"
  "lineNumber": null,  // ❌ MISSING - Critical field!
  "pageNumber": null,
  "sheetNumber": "224",
  "sheetLetter": "A",
  "familyNumber": null,
  "dwellingNumber": null,
  "imageNumber": "454",
  "affiliatePublicationNumber": "T9"  // NARA microfilm for 1880 census
}
```

### Key Observations

**Present**:
- ✓ Has `occupation` ("Farmer") - Occupation collected in 1880
- ✓ Has `birthYear` ("1847")
- ✓ Has `sheetNumber` + `sheetLetter` ("224A")
- ✓ Has NARA publication number "T9" (1880 census microfilm)

**Unique to 1880**:
- ⚠️ `relationship`: "Self" (instead of "Head")
- ✓ ED in `eventPlaceOriginal`: "ED 113"
- ✓ State abbreviation in place: "KS" (instead of full name)

**Missing**:
- ❌ `lineNumber` - **CRITICAL FIELD MISSING**
- ❌ `enumerationDistrict` not extracted (but in `eventPlaceOriginal`)
- ❌ `censusYear` not extracted

**Impact**: 1880 was the **first census to use Enumeration Districts**, making ED a required field for 1880-1950 citations.

---

## 1870 Census (T H Ojams)

```json
{
  "censusYear": null,  // ⚠️ NOT EXTRACTED
  "name": "T H Ojams",
  "sex": "Male",
  "age": "28 years",
  "birthYear": "1842",
  "birthplace": "Ohio",
  "race": "White",
  "relationship": "Head",
  "maritalStatus": null,  // ❌ MISSING
  "occupation": null,  // ❌ MISSING
  "industry": null,
  "eventDate": "1870",
  "eventPlace": "Hartford City, Blackford, Indiana, United States",
  "eventPlaceOriginal": null,  // ❌ NO ORIGINAL PLACE
  "eventType": "Census",
  "enumerationDistrict": null,  // ✓ Correct - ED not used in 1870
  "lineNumber": "5",
  "pageNumber": "9",  // ⚠️ Uses PAGE NUMBER (not sheet!)
  "sheetNumber": null,
  "sheetLetter": null,
  "familyNumber": null,
  "dwellingNumber": null,
  "imageNumber": "133",
  "affiliatePublicationNumber": "M593"  // NARA microfilm for 1870 census
}
```

### Key Observations

**Present**:
- ✓ Has `lineNumber` ("5")
- ✓ Has `pageNumber` ("9") - **Uses page number, NOT sheet number!**
- ✓ Has `birthYear` ("1842")
- ✓ Has NARA publication number "M593" (1870 census microfilm)

**Unique to 1870**:
- ⚠️ **Uses `pageNumber` instead of `sheetNumber`** (like 1950, not 1880-1940)
- ✓ No `eventPlaceOriginal` field
- ✓ No `enumerationDistrict` (EDs not used until 1880)

**Missing**:
- ❌ `maritalStatus` not extracted (may not be in table)
- ❌ `occupation` not extracted (but occupation was collected in 1870)
- ❌ `censusYear` not extracted

**Impact**: 1870 citation format will be closer to 1850-1860 format (page number, no ED).

---

## 1860 Census (Hugh Imes)

```json
{
  "censusYear": null,  // ⚠️ NOT EXTRACTED
  "name": "Hugh Imes",
  "sex": "Male",
  "age": "42",
  "birthYear": "1818",
  "birthplace": "Maryland",
  "race": "White",
  "relationship": null,  // ❌ MISSING
  "maritalStatus": null,  // ❌ MISSING (not collected in 1860)
  "occupation": null,  // ❌ MISSING
  "industry": null,
  "eventDate": "1860",
  "eventPlace": "Dallas Township, Harrison, Missouri, United States",
  "eventPlaceOriginal": null,  // ❌ NO ORIGINAL PLACE
  "eventType": "Census",
  "enumerationDistrict": null,  // ✓ Correct - ED not used in 1860
  "lineNumber": null,  // ❌ MISSING - Critical field!
  "pageNumber": "162",
  "sheetNumber": null,
  "sheetLetter": null,
  "familyNumber": null,
  "dwellingNumber": null,
  "imageNumber": "167",
  "affiliatePublicationNumber": "M653"  // NARA microfilm for 1860 census
}
```

### Key Observations

**Present**:
- ✓ Has `pageNumber` ("162")
- ✓ Has `birthYear` ("1818")
- ✓ Has NARA publication number "M653" (1860 census microfilm)

**Unique to 1860**:
- ✓ Uses `pageNumber` (not sheet)
- ✓ No `enumerationDistrict` (not used until 1880)
- ✓ No `eventPlaceOriginal` field

**Missing**:
- ❌ `relationship` not extracted (may not be in FamilySearch table)
- ❌ `maritalStatus` not extracted (not collected in 1860 census)
- ❌ `occupation` not extracted (but occupation was collected in 1860)
- ❌ `lineNumber` not extracted - **CRITICAL FIELD MISSING**
- ❌ `censusYear` not extracted

**Impact**: 1860 and earlier censuses are simpler - just page number, line number, person name.

---

## Field Comparison: 1860-1880

| Field | 1860 | 1870 | 1880 | Notes |
|-------|------|------|------|-------|
| **censusYear** | ❌ | ❌ | ❌ | All need fallback parsing |
| **name** | ✓ | ✓ | ✓ | Always present |
| **sex** | ✓ | ✓ | ✓ | Always present |
| **age** | ✓ | ✓ | ✓ | Always present |
| **birthYear** | ✓ | ✓ | ✓ | Available in all three |
| **birthplace** | ✓ | ✓ | ✓ | Always present |
| **race** | ✓ | ✓ | ✓ | Always present |
| **relationship** | ❌ | ✓ | ✓ | Not in 1860? |
| **maritalStatus** | ❌ | ❌ | ✓ | Not collected until 1880 |
| **occupation** | ❌ | ❌ | ✓ | Collected but not extracted |
| **industry** | ❌ | ❌ | ❌ | Not until 1950 |
| **eventDate** | ✓ | ✓ | ✓ | Just year |
| **eventPlace** | ✓ | ✓ | ✓ | Always present |
| **eventPlaceOriginal** | ❌ | ❌ | ✓ | Contains ED in 1880 |
| **eventType** | ✓ | ✓ | ✓ | "Census" |
| **enumerationDistrict** | ❌ | ❌ | ❌ | EDs started in 1880, not extracted |
| **lineNumber** | ❌ | ✓ | ❌ | **Inconsistent extraction** |
| **pageNumber** | ✓ | ✓ | ❌ | **Pre-1880 uses page, not sheet** |
| **sheetNumber** | ❌ | ❌ | ✓ | **1880+ uses sheet number** |
| **sheetLetter** | ❌ | ❌ | ✓ | **1880+ uses sheet letter** |
| **familyNumber** | ❌ | ❌ | ❌ | Not in any record |
| **dwellingNumber** | ❌ | ❌ | ❌ | Not in any record |
| **imageNumber** | ✓ | ✓ | ✓ | Always present |
| **affiliatePublicationNumber** | ✓ | ✓ | ✓ | NARA microfilm numbers |

---

## Critical Differences: Pre-1880 vs 1880+

### Page Number vs Sheet Number

**1850-1870**: Use `pageNumber` field
- 1860: Page 162
- 1870: Page 9

**1880-1940**: Use `sheetNumber` + `sheetLetter`
- 1880: Sheet 224A
- 1900: Sheet 1B
- 1930: Sheet 13A

**1950**: Use `pageNumber` again
- 1950: Page 71

### Enumeration Districts

**1850-1870**: NO Enumeration Districts
- Citations use: State, County, Township/City, Page, Line

**1880-1950**: Enumeration Districts required
- Citations use: State, County, ED, Sheet/Page, Line

### NARA Microfilm Publication Numbers

| Census Year | NARA Publication | Name |
|-------------|------------------|------|
| 1860 | M653 | Eighth Census of the United States |
| 1870 | M593 | Ninth Census of the United States |
| 1880 | T9 | Tenth Census of the United States |
| 1900 | T623 | Twelfth Census of the United States |
| 1910 | T624 | Thirteenth Census of the United States |
| 1920 | T625 | Fourteenth Census of the United States |
| 1930 | T626 | Fifteenth Census of the United States |
| 1940 | (none) | Not available in FamilySearch data |
| 1950 | (none) | Not yet released by NARA |

---

## Issues Found

### 1. Line Number Inconsistently Extracted

**Impact**: CRITICAL - Required field for all census citations

- ✓ **1870**: Line Number extracted ("5")
- ❌ **1880**: Line Number NOT extracted
- ❌ **1860**: Line Number NOT extracted

**Possible Causes**:
1. FamilySearch may not have line number for these specific records
2. Field labeled differently in earlier census years
3. Extraction selector not matching

**Action Needed**: Check actual FamilySearch pages to verify field availability.

---

### 2. Enumeration District Not Extracted for 1880

**Impact**: HIGH - Required for 1880-1950 citations

The 1880 census introduced Enumeration Districts, making ED a required field.

**Current Status**:
- ✓ ED is in `eventPlaceOriginal`: "Oskaloosa, **ED 113**, Jefferson, KS, United States"
- ❌ Not extracted by current logic

**Fix**: The fallback regex should already handle this, but it's not being extracted.

**Expected Result**:
```json
{
  "enumerationDistrict": "113"
}
```

---

### 3. Occupation Not Extracted

**Impact**: MEDIUM - Occupation collected in 1860, 1870, 1880 but not extracted

Occupation was collected starting in 1850 census, but not being extracted for:
- ❌ 1860 (should be present)
- ❌ 1870 (should be present)
- ✓ 1880 ("Farmer" extracted successfully)

**Possible Causes**:
1. FamilySearch may not include occupation in table for earlier years
2. Field labeled differently ("Profession" instead of "Occupation"?)

---

### 4. Relationship to Head of Household

**Impact**: MEDIUM - Helps identify correct person in household

- ❌ **1860**: Not extracted
- ✓ **1870**: "Head" extracted
- ✓ **1880**: "Self" extracted (unusual value)

**Note**: 1880 uses "Self" instead of "Head" - both mean the same thing (household head).

---

## Citation Template Requirements by Era

### 1850-1870 Format
```
State, County, Township/City, Page Number, Line Number
No Enumeration District
No Sheet Number
```

**Example** (1870):
```
Indiana, Blackford County, Hartford City, page 9, line 5
```

### 1880-1940 Format
```
State, County, Enumeration District, Sheet Number + Letter, Line Number
```

**Example** (1880):
```
Kansas, Jefferson County, ED 113, sheet 224A, line [?]
```

### 1950 Format
```
State, County, Enumeration District, Page Number, Line Number
```

**Example** (1950):
```
Minnesota, Faribault County, ED 22-27, page 71, line 7
```

---

## Recommendations

### Immediate Actions

1. **Verify Line Number Availability**:
   - Check FamilySearch pages for 1860 and 1880 records
   - Determine if line numbers are available but not extracted
   - Add alternate label checks if needed

2. **Test 1880 ED Extraction**:
   - The fallback regex should extract "113" from "ED 113"
   - Re-run extraction to verify it's working
   - If still failing, debug regex pattern

3. **Update Documentation**:
   - Add pre-1880 census year requirements to design docs
   - Document page vs sheet number usage by year
   - Update citation template requirements

### Template Layer Updates Needed

```python
# Determine reference format based on census year
if census_year <= 1870:
    # Pre-1880: Use page number, no ED
    required_fields = ['state', 'county', 'town_ward', 'page_number', 'line_number']
    use_page = True
    require_ed = False
elif 1880 <= census_year <= 1940:
    # 1880-1940: Use sheet + letter, require ED
    required_fields = ['state', 'county', 'enumeration_district', 'sheet_number', 'line_number']
    use_page = False
    require_ed = True
elif census_year == 1950:
    # 1950: Use page number, require ED
    required_fields = ['state', 'county', 'enumeration_district', 'page_number', 'line_number']
    use_page = True
    require_ed = True
```

---

## Next Steps

1. ✅ **Document pre-1880 field differences** (this document)
2. ⚠️ **Test 1880 ED extraction** - Verify fallback regex is working
3. ⚠️ **Investigate line number issues** - Check FamilySearch pages for 1860, 1880
4. 📝 **Update citation templates** - Add pre-1880 logic
5. 📝 **Update LLM prompts** - Add instructions for pre-1880 format variations

---

## Summary

Pre-1880 census records have significant structural differences:

**Page vs Sheet**:
- 1860-1870: Page number
- 1880-1940: Sheet number + letter
- 1950: Page number (returns to earlier format)

**Enumeration Districts**:
- 1860-1870: No EDs
- 1880-1950: EDs required

**Line Number**:
- Inconsistently extracted (needs investigation)

**NARA Microfilm**:
- All years have `affiliatePublicationNumber` field
- Can be used in reference note layer of citations

The browser extension handles most variations correctly, but **line number extraction** needs investigation for 1860 and 1880 records.
