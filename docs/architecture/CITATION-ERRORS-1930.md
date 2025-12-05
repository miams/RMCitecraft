---
priority: reference
topics: [database, census, citation, testing, ui]
---

# 1930 Census Citation Errors - Analysis

**Test Case**: George B Iams, 1930 U.S. Census, Greene County, Pennsylvania, Jefferson Township

## Source Data

**CitationID**: 9816
**PersonID**: 3447
**EventID**: 24124
**SourceID**: 3099

**RM Source Name**:
```
Fed Census: 1930, Pennsylvania, Greene [citing enumeration district (ED) ED 17, sheet 13A, line 15] Iams, George B.
```

**FamilySearch Citation (CitationTable.Fields "Page" field)**:
```
"United States Census, 1930," database with images, FamilySearch (https://familysearch.org/ark:/61903/1:1:XH3Z-4J8 : accessed 7 November 2020), George B Iams, Jefferson, Greene, Pennsylvania, United States; citing enumeration district (ED) ED 17, sheet 13A, line 15, family 281, NARA microfilm publication T626 (Washington D.C.: National Archives and Records Administration, 2002), roll 2044; FHL microfilm 2,341,778.
```

**Event Place (PlaceTable.Name)**:
```
Jefferson Township, Greene, Pennsylvania, United States
```

## Generated Footnote (Incorrect)

```
None U.S. census, Jefferson, Greene, Pennsylvania, United States, sheet 13, George B Iams; imaged, FamilySearch (https://www.familysearch.org/ark:/61903/1:1:XH3Z-4J8?lang=en)
```

## Correct Evidence Explained Footnote

```
1930 U.S. census, Greene County, Pennsylvania, Jefferson Township, enumeration district (ED) 30-17, sheet 13-A, line 15, George B Iams; imaged, "United States Census, 1930," <i>FamilySearch</i>, (https://www.familysearch.org/ark:/61903/1:1:XH3Z-4J8 : accessed 7 November 2020).
```

---

## 14 Errors Identified

### Error 1: Missing Census Year
**Generated**: `None U.S. census`
**Correct**: `1930 U.S. census`
**Source**: Year must be extracted from FamilySearch citation or RM Source Name

### Error 2: Wrong Geographic Order
**Generated**: `Jefferson, Greene, Pennsylvania, United States`
**Correct**: `Greene County, Pennsylvania, Jefferson Township`
**Source**: Parse PlaceTable.Name and reorder per Evidence Explained format

### Error 3: Missing "County" Designation
**Generated**: `Greene`
**Correct**: `Greene County`
**Source**: Add "County" suffix to county name from PlaceTable

### Error 4: Missing Place Type Designation
**Generated**: `Jefferson`
**Correct**: `Jefferson Township`
**Source**: Extract place type from PlaceTable.Name (Township/City/Village/etc.)

### Error 5: Missing Enumeration District (ED)
**Generated**: Not included
**Correct**: `enumeration district (ED) 30-17`
**Source**: Extract from FamilySearch citation "citing" clause
**Note**: RM Source shows "ED 17" (incomplete), actual is "30-17"

### Error 6: Incomplete Sheet Number
**Generated**: `sheet 13`
**Correct**: `sheet 13-A`
**Source**: Extract from FamilySearch citation, preserve suffix (A/B)

### Error 7: Missing Line Number
**Generated**: Not included
**Correct**: `line 15`
**Source**: Extract from FamilySearch citation "citing" clause

### Error 8: Wrong Citation Element Order
**Generated**: Location before person name
**Correct**: County, State, Township, ED, sheet, line, THEN person name
**Evidence Explained Order**: Geographic (county/state/locality), enumeration details (ED/sheet/line), person name

### Error 9: Missing Collection Title
**Generated**: No collection title after "imaged,"
**Correct**: `"United States Census, 1930,"`
**Format**: Always `"United States Census, [YEAR],"`

### Error 10: Missing Italics on FamilySearch
**Generated**: `FamilySearch`
**Correct**: `<i>FamilySearch</i>`
**Note**: Use HTML `<i>` tags for italics in RootsMagic

### Error 11: Missing Comma Before URL Parenthesis
**Generated**: `FamilySearch (`
**Correct**: `<i>FamilySearch</i>, (`
**Format**: Comma after italicized source name, before URL parenthesis

### Error 12: URL Includes Query Parameter
**Generated**: `https://www.familysearch.org/ark:/61903/1:1:XH3Z-4J8?lang=en`
**Correct**: `https://www.familysearch.org/ark:/61903/1:1:XH3Z-4J8`
**Fix**: Strip query parameters (`?lang=en`)

### Error 13: Missing Access Date with Colon Separator
**Generated**: No access date
**Correct**: ` : accessed 7 November 2020`
**Source**: Extract from FamilySearch citation
**Format**: Space-colon-space before "accessed", date in "D Month YYYY" format

### Error 14: Removed "United States" from Location
**Generated**: Includes "United States"
**Correct**: Omit "United States" (not needed in Evidence Explained format for 1930 census)
**Note**: Only include County, State, and local subdivision

---

## Additional Notes from User

1. **Enumeration District Issue**: RM Source shows "ED 17" but correct is "30-17". User retrieved full ED from census image. UI should prompt if ED is missing or flag suspiciously short EDs.

2. **Place Type Source**: "Jefferson Township" designation comes from EventTable → PlaceTable.Name field. Must parse to extract both locality name and type.

3. **Access Date**: Must always match date in FamilySearch citation, not today's date.

4. **NARA/FHL Microfilm**: Ignore these fields (not included in Evidence Explained format for 1930+).

5. **Family Number**: FamilySearch citation includes "family 281" but this is not included in Evidence Explained format.

---

## Data Extraction Requirements

### From FamilySearch Citation (CitationTable.Fields "Page")
- Census year (1930)
- Person name (George B Iams)
- Enumeration district (ED 17 - incomplete, needs user correction)
- Sheet number with suffix (13A → 13-A)
- Line number (15)
- Family number (281 - ignore for output)
- FamilySearch URL (strip query params)
- Access date (7 November 2020)
- NARA publication (ignore)
- FHL microfilm (ignore)

### From PlaceTable.Name (via EventTable)
- Full place string: "Jefferson Township, Greene, Pennsylvania, United States"
- Parse into: [Locality + Type], [County], [State], [Country]
- Extract: "Jefferson Township" (locality), "Greene" (county), "Pennsylvania" (state)
- Discard: "United States"

### From RM Source Name
- Fallback for year if not in FamilySearch citation
- Fallback for ED if not in FamilySearch citation (but may be incomplete)

---

## LLM Extraction Model (Pydantic)

```python
from pydantic import BaseModel, Field, validator

class CensusExtraction(BaseModel):
    year: int = Field(ge=1790, le=1950, description="Census year")
    state: str = Field(min_length=2, description="US state")
    county: str = Field(min_length=1, description="County name")
    locality: str | None = Field(None, description="Township/City/Village name")
    locality_type: str | None = Field(None, description="Township/City/Village/etc.")
    enumeration_district: str | None = Field(None, description="ED number (may be incomplete)")
    sheet: str = Field(description="Sheet number with suffix (e.g., 13-A)")
    line: str | None = Field(None, description="Line number")
    family_number: str | None = Field(None, description="Family number (not used in output)")
    person_name: str = Field(description="Person's name as it appears in census")
    familysearch_url: str = Field(description="FamilySearch ARK URL (no query params)")
    access_date: str = Field(description="Access date in 'D Month YYYY' format")
    nara_publication: str | None = Field(None, description="NARA publication (ignored)")
    fhl_microfilm: str | None = Field(None, description="FHL microfilm (ignored)")
    missing_fields: list[str] = Field(default_factory=list, description="Required fields that couldn't be extracted")

    @validator('year')
    def validate_census_year(cls, v):
        """Census years are every 10 years: 1790, 1800, ..., 1950"""
        if v % 10 != 0:
            raise ValueError(f"Invalid census year: {v}")
        return v

    @validator('familysearch_url')
    def strip_query_params(cls, v):
        """Remove query parameters from URL"""
        if '?' in v:
            return v.split('?')[0]
        return v
```

---

## Template Rendering Logic (1930 Census)

### Footnote Template
```
{year} U.S. census, {county} County, {state}, {locality} {locality_type}, enumeration district (ED) {ed}, sheet {sheet}, line {line}, {person_name}; imaged, "United States Census, {year}," <i>FamilySearch</i>, ({url} : accessed {access_date}).
```

### Missing Data Handling
- If ED missing or incomplete: Prompt user with FamilySearch page open
- If locality_type missing: Use locality name only (no prompt)
- If line missing: Omit "line X," from template

---

**Last Updated**: 2025-10-25
**Status**: Ready for implementation
