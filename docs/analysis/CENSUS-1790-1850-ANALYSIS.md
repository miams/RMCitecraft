# Early Census Data Analysis (1790-1850)

**Date**: 2025-10-20
**Source**: `logs/pending_citations.json` - Records 12-18

## Overview

Analysis of extracted data from 1790-1850 US Federal Census records showing **dramatically different** data structure from modern census years. These early censuses recorded only **head of household names** with statistical tallies, not individual person records.

---

## Critical Historical Context

### 1790-1840: Head of Household Only

The first six US censuses (1790-1840) **did NOT record individual names** except for the head of household. Instead, they recorded:
- **Head of household name only**
- **Statistical tallies** by age/sex categories (e.g., "Free white males under 10", "Free white females 10-16", etc.)
- **Number of slaves** (pre-1865)

**Impact**: These censuses cannot provide detailed individual information like later censuses.

### 1850: First Modern Census

The **1850 census was revolutionary** - it was the first to:
- ✓ Record **every person's name** (not just head of household)
- ✓ Record **age, sex, birthplace** for each individual
- ✓ Record **occupation** for males over 15
- ✓ List persons **line by line**

**Impact**: 1850+ citations can reference specific individuals; 1790-1840 citations can only reference household heads.

---

## Data Analysis by Census Year

### 1850 Census (John Imes) - **First "Modern" Census**

```json
{
  "censusYear": null,  // ⚠️ NOT EXTRACTED
  "name": "John Imes",
  "sex": "Male",
  "age": "39",
  "birthYear": "1811",
  "birthplace": "Pennsylvania",
  "race": "White",
  "relationship": null,  // ❌ Not extracted
  "maritalStatus": null,  // ❌ Not collected in 1850
  "occupation": null,  // ❌ Not extracted (but was collected)
  "eventDate": "1850",
  "eventPlace": "Center Township, Greene, Pennsylvania, United States",
  "eventPlaceOriginal": "Centre, Greene, Pennsylvania, United States",
  "lineNumber": "37",  // ✓ Extracted
  "pageNumber": null,  // ❌ Not extracted
  "sheetNumber": null,
  "imageNumber": "565",
  "affiliatePublicationNumber": "M432"  // NARA microfilm
}
```

**Key Observations**:
- ✓ **First census with individual names**
- ✓ Has `lineNumber` ("37") - critical field
- ✓ Has `birthYear` ("1811")
- ✓ Has detailed birthplace
- ❌ `pageNumber` not extracted (should be present)
- ❌ `occupation` not extracted (but males 15+ had occupation recorded)
- ✓ NARA publication "M432" (1850 census microfilm)

---

### 1840 Census (Richard Jiams) - **Head of Household Only**

```json
{
  "censusYear": null,
  "name": "Richard Jiams",
  "sex": null,  // ❌ NO sex recorded (head of household only)
  "age": null,  // ❌ NO age recorded (only tally categories)
  "birthYear": null,
  "race": null,  // ❌ NO race for individuals
  "relationship": null,
  "maritalStatus": null,
  "occupation": null,
  "eventDate": "1840",
  "eventPlace": "Davidson, North Carolina, United States",
  "eventPlaceOriginal": null,
  "lineNumber": null,  // ❌ No individual line numbers (household listing)
  "pageNumber": "288",  // ✓ Page number present
  "sheetNumber": null,
  "imageNumber": "1215",
  "affiliatePublicationNumber": "M704"  // NARA microfilm
}
```

**Key Observations**:
- ⚠️ **Only head of household name recorded** - NO individual person data
- ❌ NO `sex`, `age`, `birthplace`, `relationship` for individuals
- ✓ Has `pageNumber` ("288")
- ❌ NO `lineNumber` (households not listed line-by-line)
- ✓ NARA publication "M704" (1840 census microfilm)

**Citation Impact**: 1840 citations reference the household, not a specific individual.

---

### 1830 Census (Richard Iiams) - **Head of Household Only**

```json
{
  "censusYear": null,
  "name": "Richard Iiams",
  "sex": null,  // ❌ NO individual data
  "age": null,
  "birthYear": null,
  "race": null,
  "relationship": null,
  "maritalStatus": null,
  "occupation": null,
  "eventDate": "1830",
  "eventPlace": "Davidson, Mecklenburg, North Carolina, United States",
  "eventPlaceOriginal": "Davidson, North Carolina, United States",
  "lineNumber": null,  // ❌ No line numbers
  "pageNumber": "246",  // ✓ Page number present
  "sheetNumber": null,
  "imageNumber": "493",
  "affiliatePublicationNumber": "M19"  // NARA microfilm
}
```

**Key Observations**:
- ⚠️ **Only head of household name**
- ✓ Has `pageNumber` ("246")
- ✓ NARA publication "M19" (1830 census microfilm)

---

### 1820 Census (John Jonas) - **Head of Household Only**

```json
{
  "censusYear": null,
  "name": "John Jonas",
  "sex": null,  // ❌ NO individual data
  "age": null,
  "birthYear": null,
  "race": null,
  "relationship": null,
  "maritalStatus": null,
  "occupation": null,
  "eventDate": "1820",
  "eventPlace": "Baltimore, Baltimore, Maryland, United States",
  "eventPlaceOriginal": "Baltimore Ward 3, Baltimore, Maryland, United States",
  "lineNumber": null,  // ❌ No line numbers
  "pageNumber": "136",  // ✓ Page number present
  "sheetNumber": null,
  "imageNumber": "78",
  "affiliatePublicationNumber": "M33"  // NARA microfilm
}
```

**Key Observations**:
- ⚠️ **Only head of household name**
- ✓ Has `pageNumber` ("136")
- ✓ Ward information in `eventPlaceOriginal` ("Baltimore Ward 3")
- ✓ NARA publication "M33" (1820 census microfilm)

---

### 1810 Census (P Ijames) - **Head of Household Only**

```json
{
  "censusYear": null,
  "name": "P Ijames",
  "sex": null,  // ❌ NO individual data
  "age": null,
  "birthYear": null,
  "race": null,
  "relationship": null,
  "maritalStatus": null,
  "occupation": null,
  "eventDate": "1810",
  "eventPlace": "Frederick, Maryland, United States",
  "eventPlaceOriginal": "Frederick, Maryland, United States",
  "lineNumber": null,  // ❌ No line numbers
  "pageNumber": "580",  // ✓ Page number present
  "sheetNumber": null,
  "imageNumber": "249",
  "affiliatePublicationNumber": "M252"  // NARA microfilm
}
```

**Key Observations**:
- ⚠️ **Only head of household name** (abbreviated: "P Ijames")
- ✓ Has `pageNumber` ("580")
- ✓ NARA publication "M252" (1810 census microfilm)

---

### 1800 Census (John Jeanes) - **Head of Household Only**

```json
{
  "censusYear": null,
  "name": "John Jeanes",
  "sex": null,  // ❌ NO individual data
  "age": null,
  "birthYear": null,
  "race": null,
  "relationship": null,
  "maritalStatus": null,
  "occupation": null,
  "eventDate": "1800",
  "eventPlace": "Anne Arundel, Maryland, United States",
  "eventPlaceOriginal": null,
  "lineNumber": null,  // ❌ No line numbers
  "pageNumber": "92",  // ✓ Page number present
  "sheetNumber": null,
  "imageNumber": "55",
  "affiliatePublicationNumber": "M32"  // NARA microfilm
}
```

**Key Observations**:
- ⚠️ **Only head of household name**
- ✓ Has `pageNumber` ("92")
- ✓ NARA publication "M32" (1800 census microfilm)

---

### 1790 Census (Plummer Iiams) - **First US Census**

```json
{
  "censusYear": null,
  "name": "Plummer Iiams",
  "sex": null,  // ❌ NO individual data
  "age": null,
  "birthYear": null,
  "race": null,
  "relationship": null,
  "maritalStatus": null,
  "occupation": null,
  "eventDate": "1790",
  "eventPlace": "Anne Arundel, Maryland, United States",
  "eventPlaceOriginal": null,
  "lineNumber": "508",  // ⚠️ Household number, not person line
  "pageNumber": "357",  // ✓ Page number present
  "sheetNumber": null,
  "imageNumber": "204",
  "affiliatePublicationNumber": "M637"  // NARA microfilm
}
```

**Key Observations**:
- ⚠️ **First US Census** (1790)
- ⚠️ **Only head of household name**
- ✓ Has `pageNumber` ("357")
- ⚠️ Has `lineNumber` ("508") - but this is **household number**, not person line number
- ✓ NARA publication "M637" (1790 census microfilm)

---

## Field Comparison: 1790-1850

| Field | 1790 | 1800 | 1810 | 1820 | 1830 | 1840 | 1850 | Notes |
|-------|------|------|------|------|------|------|------|-------|
| **censusYear** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | All need fallback |
| **name** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Head of household only (1790-1840) |
| **sex** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✓ | **First collected in 1850** |
| **age** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✓ | **First collected in 1850** |
| **birthYear** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✓ | Calculated from age (1850+) |
| **birthplace** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✓ | **First collected in 1850** |
| **race** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✓ | **First collected in 1850** |
| **relationship** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Not until 1880 |
| **maritalStatus** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Not until 1880 |
| **occupation** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Collected but not extracted |
| **eventDate** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Always present (just year) |
| **eventPlace** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Always present |
| **eventPlaceOriginal** | ❌ | ❌ | ✓ | ✓ | ✓ | ❌ | ✓ | Varies |
| **lineNumber** | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ✓ | 1790: household #; 1850+: person line |
| **pageNumber** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ❌ | **All use page number** |
| **sheetNumber** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Not until 1880 |
| **imageNumber** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Always present (digital) |
| **affiliatePublicationNumber** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | NARA microfilm |

---

## NARA Microfilm Publication Numbers (1790-1850)

| Census Year | NARA Publication | Name |
|-------------|------------------|------|
| 1790 | M637 | Heads of Families at the First Census |
| 1800 | M32 | Second Census of the United States |
| 1810 | M252 | Third Census of the United States |
| 1820 | M33 | Fourth Census of the United States |
| 1830 | M19 | Fifth Census of the United States |
| 1840 | M704 | Sixth Census of the United States |
| 1850 | M432 | Seventh Census of the United States |

**Note**: All early census titles emphasize "Heads of Families" (1790-1840) vs. individual enumeration (1850+).

---

## Citation Format Implications

### 1790-1840: Household Head Citations

**Format**:
```
[Head of Household Name], [Year] U.S. census, [County], [State],
page [page number]; NARA microfilm publication [number].
```

**Example** (1820):
```
John Jonas, 1820 U.S. census, Baltimore County, Maryland,
p. 136; NARA microfilm publication M33.
```

**Key Points**:
- ⚠️ **Cannot reference specific individuals** (only household head)
- ✓ Use page number (no line number)
- ✓ Include NARA microfilm publication
- ⚠️ Cannot state individual's age, sex, or birthplace (not recorded)

---

### 1850-1870: Individual Person Citations (Pre-ED)

**Format**:
```
[Person Name], [Age], [Year] U.S. census, [County], [State],
[Township], page [number], line [number]; NARA microfilm publication [number].
```

**Example** (1850):
```
John Imes, age 39, 1850 U.S. census, Greene County, Pennsylvania,
Center Township, line 37; NARA microfilm publication M432.
```

**Key Points**:
- ✓ **Can reference specific individuals** (first time!)
- ✓ Include age, birthplace (if citing from census)
- ✓ Use page number + line number
- ❌ NO Enumeration District (not used until 1880)

---

## Critical Issues Found

### 1. Page Number Not Extracted for 1850

**Impact**: HIGH - Page number is required field for 1850 citations

**Current Status**:
- 1850 record shows `pageNumber: null`
- But FamilySearch likely has page number (need to verify)

**Action Needed**: Check FamilySearch page for 1850 record to verify field availability.

---

### 2. Line Number Semantics Change

**Impact**: MEDIUM - Field meaning changes between census years

**1790**: `lineNumber: "508"` = **Household sequence number** (not individual line)
**1850+**: `lineNumber: "37"` = **Individual person line number**

**Citation Impact**:
- 1790-1840: Do NOT use line number in citations (household-based)
- 1850+: MUST use line number in citations (person-based)

---

### 3. No Individual Data Before 1850

**Impact**: CRITICAL - Changes entire citation approach

**1790-1840 Censuses**:
- ❌ NO individual names (except head of household)
- ❌ NO ages for individuals
- ❌ NO sex for individuals
- ❌ NO birthplaces
- ❌ NO occupations for individuals
- ✓ ONLY statistical tallies by category

**1850+ Censuses**:
- ✓ Every person named
- ✓ Age, sex, birthplace recorded
- ✓ Can cite specific individuals

**User Implication**: When user searches for ancestor in 1790-1840 census, they can ONLY find them if they were head of household. Children, spouses, other household members are **not named** - only counted in age/sex tallies.

---

## Complete Census Evolution Timeline

### Phase 1: Statistical Era (1790-1840)
- **Head of household name only**
- Statistical tallies by age/sex categories
- Page numbers only
- Cannot cite specific individuals (except household head)

### Phase 2: Individual Era Begins (1850-1870)
- **Every person named** (revolutionary change)
- Age, sex, birthplace recorded
- Page + line numbers
- Can cite specific individuals
- NO Enumeration Districts yet

### Phase 3: Enumeration District Era (1880-1940)
- Enumeration Districts introduced
- Sheet number + letter (instead of page)
- More detailed information (occupation, marital status, relationship)

### Phase 4: Modern Era (1950)
- Returns to page numbers (not sheets)
- Most detailed information (industry field added)
- ED still required

---

## Template Requirements by Era

### Era 1: 1790-1840 (Head of Household Only)
```python
required_fields = ['name', 'state', 'county', 'page_number']
optional_fields = ['town_ward']
citation_type = 'household'  # Not individual person
include_line_number = False  # No line numbers (or household sequence only)
include_ed = False
```

### Era 2: 1850-1870 (Individual, No ED)
```python
required_fields = ['name', 'age', 'state', 'county', 'town_ward', 'page_number', 'line_number']
optional_fields = ['birthplace', 'occupation']
citation_type = 'individual'  # Specific person
include_line_number = True
include_ed = False  # EDs not used yet
```

### Era 3: 1880-1940 (Individual, With ED, Sheet Numbers)
```python
required_fields = ['name', 'age', 'state', 'county', 'enumeration_district', 'sheet_number', 'line_number']
optional_fields = ['occupation', 'relationship', 'marital_status']
citation_type = 'individual'
include_line_number = True
include_ed = True
use_sheet = True  # Sheet + letter, not page
```

### Era 4: 1950 (Individual, With ED, Page Numbers)
```python
required_fields = ['name', 'age', 'state', 'county', 'enumeration_district', 'page_number', 'line_number']
optional_fields = ['occupation', 'industry', 'relationship', 'marital_status']
citation_type = 'individual'
include_line_number = True
include_ed = True
use_sheet = False  # Returns to page numbers
```

---

## Recommendations

### Immediate Actions

1. **Verify 1850 page number availability** - Check FamilySearch to confirm field exists
2. **Document household vs. individual citation formats** - Add to LLM prompts
3. **Add era-based validation** - Check that required fields exist for citation era

### User Communication

When extracting 1790-1840 census records, display warning:
```
⚠️ Note: 1790-1840 censuses list only heads of household.
Individual family members are not named in these census years.
```

### Template Layer Updates

```python
def get_census_era(year: int) -> str:
    if year <= 1840:
        return 'household_only'  # Can only cite household head
    elif year <= 1870:
        return 'individual_no_ed'  # Individual citations, no ED
    elif year <= 1940:
        return 'individual_with_ed_sheet'  # Individual with ED, use sheet
    else:
        return 'individual_with_ed_page'  # Individual with ED, use page
```

---

## Summary

The 1790-1850 period represents a dramatic evolution in US census methodology:

**1790-1840**: Head of household names only + statistical tallies
- ⚠️ Cannot cite specific individuals (only household heads)
- ✓ Use page numbers only
- ❌ No individual age, sex, or birthplace data

**1850**: Revolutionary change - first "modern" census
- ✓ **Every person named** for first time
- ✓ Age, sex, birthplace recorded
- ✓ Can cite specific individuals
- ✓ Use page + line numbers
- ❌ Still no Enumeration Districts

**1850 marks the dividing line** between household-based and individual-based census citations.

The browser extension correctly handles these early censuses by extracting only the fields that exist (name, page number, NARA publication). The LLM and template layers will need logic to generate appropriate citation formats based on census era.
