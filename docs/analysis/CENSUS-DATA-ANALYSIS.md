# Census Data Structure Analysis

**Date**: 2025-10-20
**Source**: `logs/pending_citations.json` - Real extracted data from 6 census years

## Overview

This document analyzes the actual data structure and field variations across US Federal Census records (1900-1950) as extracted from FamilySearch by the browser extension.

## Data by Census Year

### 1950 Census (Eldon Iams)
```json
{
  "censusYear": null,  // ⚠️ NOT EXTRACTED
  "name": "Eldon Iams",
  "sex": "Male",
  "age": "33 years",
  "birthYear": "1917",
  "birthplace": "Minnesota",
  "race": "W",
  "relationship": "Head",
  "maritalStatus": "Married",
  "occupation": "Farmer",
  "industry": "Farm",
  "eventDate": "3 April 1950",
  "eventPlace": "Lura Township, Faribault, Minnesota, United States",
  "eventPlaceOriginal": "Lura, Faribault, Minnesota",
  "enumerationDistrict": "22-27",
  "lineNumber": "7",
  "pageNumber": "71",
  "imageNumber": "18"
}
```

**Unique to 1950**:
- ✓ `occupation` + `industry` fields
- ✓ `birthYear` field (estimated)
- ✓ `pageNumber` instead of sheet
- ✓ Age includes "years" suffix

**Missing**:
- ❌ `enumerationDistrict` is formatted as "22-27" (should extract as district 22-27)
- ❌ `censusYear` not being extracted

---

### 1940 Census (Glen H James)
```json
{
  "censusYear": null,  // ⚠️ NOT EXTRACTED
  "name": "Glen H James",
  "sex": "Male",
  "age": "40",
  "birthplace": "Missouri",
  "race": "White",
  "relationship": "Head",
  "maritalStatus": "Married",
  "eventDate": "1940",
  "eventPlace": "Mill Spring Township, Wayne, Wayne, Missouri, United States",
  "eventPlaceOriginal": "Mill Spring Township, Wayne, Wayne, Missouri, United States",
  "lineNumber": "45",
  "sheetNumber": "14",
  "imageNumber": "744"
}
```

**Unique to 1940**:
- ✓ `sheetNumber` (no sheet letter in this record)
- ✓ `eventDate` is just year "1940"
- ✓ Age is numeric only (no "years" suffix)
- ✓ Race is full word "White" (not abbreviation)

**Key Observation**:
- ⚠️ **Enumeration District Number field format**: "112-9 Mill Spring Township, Granite Bend, Mill Spring, Leeper"
  - Combines ED number ("112-9") with location descriptions
  - Extension now extracts these separately:
    - `enumerationDistrict`: "112-9"
    - `enumerationDistrictLocation`: "Mill Spring Township, Granite Bend, Mill Spring, Leeper"

**Missing**:
- ❌ No `occupation` or `industry` (not collected in 1940)
- ❌ No `birthYear` (not in this record)
- ❌ `censusYear` not extracted (now fixed with fallback)

---

### 1930 Census (George B Iams)
```json
{
  "censusYear": null,  // ⚠️ NOT EXTRACTED
  "name": "George B Iams",
  "sex": "Male",
  "age": "64 years",
  "birthYear": "1866",
  "birthplace": "Pennsylvania",
  "race": "White",
  "relationship": "Head",
  "maritalStatus": "Married",
  "eventDate": "1930",
  "eventPlace": "Jefferson, Greene, Pennsylvania, United States",
  "eventPlaceOriginal": "Jefferson, Greene, Pennsylvania, United States",
  "eventType": "Census",
  "lineNumber": "15",
  "sheetNumber": "13",
  "sheetLetter": "A",
  "imageNumber": "98",
  "affiliatePublicationNumber": "T626"
}
```

**Unique to 1930**:
- ✓ `sheetNumber` + `sheetLetter` (e.g., "13A")
- ✓ `eventType` field ("Census")
- ✓ `affiliatePublicationNumber` (NARA microfilm: "T626")
- ✓ Has `birthYear` field

**Missing**:
- ❌ `enumerationDistrict` not extracted
- ❌ `censusYear` not extracted

---

### 1920 Census (James Iams)
```json
{
  "censusYear": null,  // ⚠️ NOT EXTRACTED
  "name": "James Iams",
  "sex": "Male",
  "age": "54 years",
  "birthYear": "1866",
  "birthplace": "Pennsylvania",
  "race": "White",
  "relationship": "Head",
  "maritalStatus": "Married",
  "eventDate": "1920",
  "eventPlace": "Clay Center, Clay, Kansas, United States",
  "eventPlaceOriginal": "Clay Center, ED 4, Clay, Kansas, United States",
  "eventType": "Census",
  "lineNumber": "71",
  "sheetNumber": "12",
  "sheetLetter": "B",
  "imageNumber": "204",
  "affiliatePublicationNumber": "T625"
}
```

**Key Observations**:
- ⚠️ `eventPlaceOriginal` contains ED (Enumeration District) info: "ED 4"
- ✓ NARA microfilm: "T625"
- ✓ Sheet format: "12B"

**Missing**:
- ❌ `enumerationDistrict` not extracted (but visible in `eventPlaceOriginal`)
- ❌ `censusYear` not extracted

---

### 1910 Census (Levi W Iams)
```json
{
  "censusYear": null,  // ⚠️ NOT EXTRACTED
  "name": "Levi W Iams",
  "sex": "Male",
  "age": "28",
  "birthYear": "1882",
  "birthplace": "Pennsylvania",
  "race": "White",
  "relationship": "Head",
  "maritalStatus": "Married",
  "eventDate": "1910",
  "eventPlace": "South Franklin, Washington, Pennsylvania, United States",
  "eventPlaceOriginal": "South Franklin, 233, Washington, Pennsylvania, United States",
  "eventType": "Census",
  "sheetNumber": "2",
  "sheetLetter": "B",
  "imageNumber": "387",
  "affiliatePublicationNumber": "T624"
}
```

**Key Observations**:
- ⚠️ `eventPlaceOriginal` contains ED number "233" (but not labeled as "ED")
- ✓ NARA microfilm: "T624"
- ❌ NO `lineNumber` extracted

**Missing**:
- ❌ `lineNumber` not extracted (critical field!)
- ❌ `enumerationDistrict` not extracted (but visible in `eventPlaceOriginal`)
- ❌ `censusYear` not extracted

---

### 1900 Census (Dennis Iams)
```json
{
  "censusYear": null,  // ⚠️ NOT EXTRACTED
  "name": "Dennis Iams",
  "sex": "Male",
  "age": "43 years",
  "birthplace": "Pennsylvania",
  "race": "White",
  "relationship": "Head",
  "maritalStatus": "Married",
  "eventDate": "1900",
  "eventPlace": "Richhill Township, Greene, Pennsylvania, United States",
  "eventPlaceOriginal": "Richhill Township (south side), ED 98, Greene, Pennsylvania, United States",
  "eventType": "Census",
  "lineNumber": "93",
  "sheetNumber": "1",
  "sheetLetter": "B",
  "imageNumber": "77",
  "affiliatePublicationNumber": "T623"
}
```

**Key Observations**:
- ⚠️ `eventPlaceOriginal` contains ED: "ED 98"
- ✓ NARA microfilm: "T623"
- ✓ Sheet format: "1B"

**Missing**:
- ❌ `birthYear` not extracted (not available in 1900 census)
- ❌ `enumerationDistrict` not extracted (but visible in `eventPlaceOriginal`: "ED 98")
- ❌ `censusYear` not extracted

---

## Field Comparison Matrix

| Field | 1900 | 1910 | 1920 | 1930 | 1940 | 1950 | Notes |
|-------|------|------|------|------|------|------|-------|
| **censusYear** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | **CRITICAL: Not being extracted** |
| **name** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Always present |
| **sex** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Always present |
| **age** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Format varies (with/without "years") |
| **birthYear** | ❌ | ✓ | ✓ | ✓ | ❌ | ✓ | Not in 1900, 1940 |
| **birthplace** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Always present |
| **race** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Format varies (abbrev vs full) |
| **relationship** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Always present |
| **maritalStatus** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Always present |
| **occupation** | ❌ | ❌ | ❌ | ❌ | ❌ | ✓ | **Only 1950** |
| **industry** | ❌ | ❌ | ❌ | ❌ | ❌ | ✓ | **Only 1950** |
| **eventDate** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Format varies (year vs full date) |
| **eventPlace** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Always present |
| **eventPlaceOriginal** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Often contains ED info |
| **eventType** | ✓ | ✓ | ✓ | ✓ | ❌ | ❌ | Only pre-1940 |
| **enumerationDistrict** | ❌ | ❌ | ❌ | ❌ | ❌ | ✓ | **Inconsistent extraction** |
| **lineNumber** | ✓ | ❌ | ✓ | ✓ | ✓ | ✓ | **1910 missing!** |
| **pageNumber** | ❌ | ❌ | ❌ | ❌ | ❌ | ✓ | **Only 1950** |
| **sheetNumber** | ✓ | ✓ | ✓ | ✓ | ✓ | ❌ | Pre-1950 only |
| **sheetLetter** | ✓ | ✓ | ✓ | ✓ | ❌ | ❌ | Pre-1940 only |
| **imageNumber** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Always present |
| **affiliatePublicationNumber** | ✓ | ✓ | ✓ | ✓ | ❌ | ❌ | NARA film (pre-1940) |

---

## Critical Issues

### 1. Census Year Not Being Extracted
**Impact**: HIGH - Required for all citation templates

The `censusYear` field is `null` in ALL records, but `eventDate` contains the year.

**Problem**: The `extractCensusYear()` function is not finding the year in the page.

**Solution**: ✅ **FIXED** - Added fallback logic to parse year from `eventDate` field.

---

### 2. Enumeration District Inconsistent
**Impact**: HIGH - Required for 1880-1950 citations

- 1950: ✓ Extracted as "22-27"
- 1940: ⚠️ Extracted as combined field "112-9 Mill Spring Township, Granite Bend, Mill Spring, Leeper"
- 1930: ❌ Not extracted (may not be in table)
- 1920: ❌ Not extracted (but in `eventPlaceOriginal`: "ED 4")
- 1910: ❌ Not extracted (but in `eventPlaceOriginal`: "233")
- 1900: ❌ Not extracted (but in `eventPlaceOriginal`: "ED 98")

**Problem**:
- 1940: Field "Enumeration District Number" contains ED + location: "112-9 Mill Spring Township..."
- 1920-1900: ED embedded in `eventPlaceOriginal` field
- Sometimes just a number without "ED" prefix

**Solution**: ✅ **FIXED**
1. Added cleanup logic to parse ED number from 1940 combined format
2. Saves location portion as `enumerationDistrictLocation` (new field)
3. Added regex fallback parsing of `eventPlaceOriginal` for other years

---

### 3. Line Number Missing for 1910
**Impact**: HIGH - Required field for all citations

The 1910 record (Levi W Iams) has NO `lineNumber` extracted.

**Possible Causes**:
- FamilySearch doesn't have line number for this record
- Line number labeled differently ("Line" vs "Line Number")
- Extraction selector not matching

**Solution**: Need to verify the actual FamilySearch page to confirm field availability.

---

### 4. Age Format Variations
**Impact**: LOW - Easy to normalize

- 1950: "33 years"
- 1940: "40"
- 1930: "64 years"
- 1920: "54 years"
- 1910: "28"
- 1900: "43 years"

**Pattern**: Inconsistent inclusion of " years" suffix

**Solution**: Strip " years" suffix during normalization.

---

### 5. Race Format Variations
**Impact**: LOW - Easy to normalize

- 1950: "W" (abbreviation)
- All others: "White" (full word)

**Solution**: Normalize to single-letter codes during LLM extraction.

---

### 6. Sheet vs Page Number
**Impact**: MEDIUM - Required for proper citation format

**1900-1940**: Use `sheetNumber` + `sheetLetter` (e.g., "13A", "1B")
**1950**: Use `pageNumber` (e.g., "71")

**Solution**: Template logic should check census year:
```python
if census_year >= 1950:
    use pageNumber
else:
    use sheetNumber + sheetLetter
```

---

## Data Normalization Strategy

### Phase 1: Browser Extension Improvements

1. **Fix `censusYear` extraction**:
   - Update `extractCensusYear()` to search page heading
   - Add fallback: parse from `eventDate` field
   - Ensure all records have `censusYear` populated

2. **Fix `enumerationDistrict` extraction**:
   - Keep current table-based extraction
   - Add fallback: regex parse from `eventPlaceOriginal`
   - Pattern: `/\bED\s+(\d+[-\d]*)\b/i` or `/,\s+(\d+),/`

3. **Investigate 1910 line number issue**:
   - Check FamilySearch page for actual field availability
   - Add alternate label checks if needed

### Phase 2: LLM Extraction Layer

The LLM should normalize extracted data:

1. **Parse `censusYear` from `eventDate` if missing**:
   ```python
   if not census_year and event_date:
       year_match = re.search(r'\b(17|18|19|20)\d{2}\b', event_date)
       census_year = int(year_match.group(0)) if year_match else None
   ```

2. **Parse `enumerationDistrict` from `eventPlaceOriginal` if missing**:
   ```python
   if not enumeration_district and event_place_original:
       ed_match = re.search(r'\bED\s+(\d+[-\d]*)\b', event_place_original, re.I)
       enumeration_district = ed_match.group(1) if ed_match else None
   ```

3. **Normalize age** (strip " years" suffix):
   ```python
   if age and age.endswith(' years'):
       age = age.replace(' years', '').strip()
   ```

4. **Normalize race** (convert to single-letter codes):
   ```python
   race_map = {
       'White': 'W',
       'Black': 'B',
       'Mulatto': 'Mu',
       'Chinese': 'Ch',
       'Japanese': 'Jp',
       'Indian': 'In',
   }
   race = race_map.get(race, race)
   ```

5. **Combine sheet + letter**:
   ```python
   if sheet_number and sheet_letter:
       sheet = f"{sheet_number}{sheet_letter}"
   else:
       sheet = sheet_number
   ```

### Phase 3: Citation Template Layer

Templates should handle year-specific field requirements:

```python
# 1900-1940: Use sheet number + letter
if 1900 <= census_year <= 1940:
    required_fields = ['sheet_number', 'enumeration_district', 'line_number']
    sheet_format = f"{sheet_number}{sheet_letter or ''}"

# 1950: Use page number
elif census_year == 1950:
    required_fields = ['page_number', 'enumeration_district', 'line_number']
```

---

## NARA Microfilm Publication Numbers

The `affiliatePublicationNumber` field contains NARA microfilm series:

| Year | Publication | Notes |
|------|-------------|-------|
| 1900 | T623 | Available in records |
| 1910 | T624 | Available in records |
| 1920 | T625 | Available in records |
| 1930 | T626 | Available in records |
| 1940 | (none) | Not in FamilySearch data |
| 1950 | (none) | Not yet released by NARA |

**Use Case**: Reference note layer of Evidence Explained citations.

---

## Recommendations

### Immediate Actions (Browser Extension)

1. ✅ **Fix `censusYear` extraction** - Add fallback to parse from `eventDate`
2. ✅ **Fix `enumerationDistrict` extraction** - Add regex fallback for `eventPlaceOriginal`
3. ⚠️ **Investigate 1910 line number** - May need to check actual FamilySearch page

### Medium-Term (LLM Layer)

4. **Add data normalization in LLM extraction prompt**:
   - Parse census year from event date
   - Parse ED from event place original
   - Normalize age, race, sheet format
   - Flag missing required fields by census year

### Long-Term (Template Layer)

5. **Year-specific template logic**:
   - Check census year to determine required fields
   - Use sheet vs page number appropriately
   - Include NARA publication numbers when available

---

## Next Steps

1. **Update browser extension** (`content.js`):
   - Fix `extractCensusYear()` function
   - Add ED regex fallback
   - Test with all 6 census years

2. **Update LLM extraction prompts** (`src/rmcitecraft/llm/prompts/`):
   - Add normalization instructions
   - Add field requirement logic by year
   - Add regex patterns for ED extraction

3. **Update citation templates** (`src/rmcitecraft/citations/templates/`):
   - Add year-specific field checks
   - Implement sheet vs page logic
   - Add NARA publication numbers

4. **Test with real data**:
   - Re-extract all 6 citations with fixed extension
   - Verify all fields populate correctly
   - Test LLM extraction and normalization
   - Generate citations for all years
