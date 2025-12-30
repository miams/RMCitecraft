---
priority: essential
topics: [citation, evidence-explained, formatting, reference]
---

# RMCitecraft Citation Style Guide

**For**: Users who want to understand how RMCitecraft formats census citations

## Overview

RMCitecraft formats census citations following *Evidence Explained* by Elizabeth Shown Mills, with specific implementation choices documented here. Understanding these conventions helps you:

- Know what to expect from generated citations
- Identify if your existing citations are compatible
- Make informed decisions about manual corrections

---

## The Three Citation Forms

Every census record generates three citation forms:

| Form | Purpose | Example Length |
|------|---------|----------------|
| **Footnote** | First reference in a document | Full detail |
| **Short Footnote** | Subsequent references | Abbreviated |
| **Bibliography** | Source list entry | Hierarchical format |

---

## Citation Format by Census Era

### Era 1: 1790-1840 (Household Schedules)

These early censuses only recorded the head of household by name.

**Footnote Format:**
```
1820 U.S. census, Baltimore County, Maryland, page 136, John Jonas;
imaged, "United States, Census, 1820," FamilySearch
(https://familysearch.org/ark:/... : accessed 25 December 2025).
```

**Short Footnote:**
```
1820 U.S. census, Baltimore Co., Md., p. 136, John Jonas.
```

**Key Elements:**
- Year, County, State order
- Page number (no sheet/ED in this era)
- Person name (head of household only)
- FamilySearch citation with URL and access date

---

### Era 2: 1850-1870 (Individual Enumeration, No ED)

The 1850 census revolutionized data collection by listing every person.

#### 1850 Census Format

**Footnote:**
```
1850 U.S. census, Greene County, Pennsylvania, population schedule,
Center Township, page 45 (penned), dwelling 123, family 124, line 37,
John Imes; imaged, "United States, Census, 1850," FamilySearch
(https://familysearch.org/ark:/... : accessed 25 December 2025).
```

**Short Footnote:**
```
1850 U.S. census, Greene Co., Pa., pop. sch., Center Twp., p. 45 (penned),
dwelling 123, family 124, line 37, John Imes.
```

**Key Elements:**
- "population schedule" appears in footnote (distinguishes from slave/mortality schedules)
- Page number marked "(penned)" - these were handwritten page numbers
- Dwelling and family numbers included when available
- Locality (township) appears after "population schedule"

#### 1860 Census Format

**Special Note:** FamilySearch does not index line numbers for 1860. RMCitecraft uses family number instead.

**Footnote:**
```
1860 U.S. census, Davie County, North Carolina, population schedule,
Mocksville, page 45, family 123, George W Ijams; imaged,
"United States, Census, 1860," FamilySearch
(https://familysearch.org/ark:/... : accessed 25 December 2025).
```

**Short Footnote:**
```
1860 U.S. census, Davie Co., N.C., pop. sch., Mocksville, page 45,
family 123, George W Ijams.
```

#### 1870 Census Format

**Footnote:**
```
1870 U.S. census, Jefferson County, Kansas, population schedule,
page 224, line 15, John W Yams; imaged, "United States, Census, 1870,"
FamilySearch (https://familysearch.org/ark:/... : accessed 25 December 2025).
```

---

### Era 3: 1880-1940 (Enumeration Districts)

The 1880 census introduced Enumeration Districts (ED) for urban areas.

#### 1880 Census Format

**Footnote:**
```
1880 U.S. census, Jefferson County, Kansas, population schedule,
Sarcoxie Township, enumeration district (ED) 113, page 224 (stamped),
line 15, John W Yams; imaged, "United States, Census, 1880," FamilySearch
(https://familysearch.org/ark:/... : accessed 25 December 2025).
```

**Short Footnote:**
```
1880 U.S. census, Jefferson Co., Kans., pop. sch., Sarcoxie Twp.,
E.D. 113, page 224 (stamped), line 15, John W Yams.
```

**Key Changes in 1880:**
- Enumeration District (ED) now required
- "page (stamped)" - NARA stamped page numbers on microfilm
- "sheet" terminology begins (sheet 224A, 224B)

#### 1900-1940 Census Format

**Footnote (1930 Example):**
```
1930 U.S. census, Greene County, Pennsylvania, Jefferson Township,
enumeration district (ED) 30-17, sheet 13-A, line 15, George B Iams;
imaged, "United States, Census, 1930," FamilySearch
(https://familysearch.org/ark:/... : accessed 25 December 2025).
```

**Short Footnote (1930 Example):**
```
1930 U.S. census, Greene Co., Pa., Jefferson Twp., E.D. 30-17,
sheet 13-A, line 15, George B Iams.
```

**Note on 1910-1940:** The short footnote omits "pop. sch." because only population schedules survive for these years. There's no ambiguity to resolve.

---

### Era 4: 1950 Census

The 1950 census returned to page numbering and introduced new terminology.

**Footnote:**
```
1950 U.S. census, Stark County, Ohio, Canton, enumeration district (ED) 76-123,
stamp 15, line 42, Verne D Adams; imaged, "United States Census, 1950,"
FamilySearch (https://familysearch.org/ark:/... : accessed 25 December 2025).
```

**Short Footnote:**
```
1950 U.S. census, Stark Co., Oh., pop. sch., Canton, E.D. 76-123,
stamp 15, line 42, Verne D Adams.
```

**Key Changes:**
- Uses "stamp" instead of "sheet" (NARA stamped numbers)
- "pop. sch." returns in short footnote (distinguishes from sample forms)

---

## Special Schedule Types

### Slave Schedules (1850, 1860)

Slave schedules list enslaved persons by owner, with age, sex, and color but no names.

**Footnote:**
```
1860 U.S. census, Tishomingo County, Mississippi, slave schedule,
page 21, line 40, column 1 and line 1, column 2, Burgess Ijams, "owner";
imaged, "United States, Census (Slave Schedule), 1860," FamilySearch
(https://familysearch.org/ark:/... : accessed 25 December 2025).
```

**Short Footnote:**
```
1860 U.S. census, Tishomingo Co., Miss., slave sch., page 21,
line 40, column 1 and line 1, column 2, Burgess Ijams, "owner."
```

**Key Elements:**
- "slave schedule" instead of "population schedule"
- Column number (1 or 2) identifies which column on the form
- Owner name followed by "owner" in quotes
- FamilySearch title includes "(Slave Schedule)"

### Mortality Schedules (1850-1880)

Mortality schedules list persons who died in the 12 months preceding enumeration.

**Footnote:**
```
1850 U.S. census, Warren County, New Jersey, mortality schedule,
page 2, line 2, Daniel Shannon; imaged, "United States, Census
(Mortality Schedule), 1850," FamilySearch
(https://familysearch.org/ark:/... : accessed 25 December 2025).
```

**Short Footnote:**
```
1850 U.S. census, Warren Co., N.J., mort. sch., page 2, line 2,
Daniel Shannon.
```

---

## Abbreviations Used

### State Abbreviations

RMCitecraft uses standard two-letter postal abbreviations in short footnotes:

| State | Abbreviation | State | Abbreviation |
|-------|--------------|-------|--------------|
| Alabama | Ala. | Montana | Mont. |
| Arizona | Ariz. | Nebraska | Nebr. |
| Arkansas | Ark. | Nevada | Nev. |
| California | Calif. | New Hampshire | N.H. |
| Colorado | Colo. | New Jersey | N.J. |
| Connecticut | Conn. | New Mexico | N.Mex. |
| Delaware | Del. | New York | N.Y. |
| Florida | Fla. | North Carolina | N.C. |
| Georgia | Ga. | North Dakota | N.Dak. |
| Idaho | Idaho | Ohio | Oh. |
| Illinois | Ill. | Oklahoma | Okla. |
| Indiana | Ind. | Oregon | Oreg. |
| Iowa | Iowa | Pennsylvania | Pa. |
| Kansas | Kans. | Rhode Island | R.I. |
| Kentucky | Ky. | South Carolina | S.C. |
| Louisiana | La. | South Dakota | S.Dak. |
| Maine | Maine | Tennessee | Tenn. |
| Maryland | Md. | Texas | Tex. |
| Massachusetts | Mass. | Utah | Utah |
| Michigan | Mich. | Vermont | Vt. |
| Minnesota | Minn. | Virginia | Va. |
| Mississippi | Miss. | Washington | Wash. |
| Missouri | Mo. | West Virginia | W.Va. |
| | | Wisconsin | Wis. |
| | | Wyoming | Wyo. |

### Other Abbreviations

| Full Form | Short Footnote |
|-----------|----------------|
| County | Co. |
| Township | Twp. |
| population schedule | pop. sch. |
| slave schedule | slave sch. |
| mortality schedule | mort. sch. |
| enumeration district | E.D. |
| page | p. |

**Note on Township Abbreviation:**
- Named townships use "Twp." (e.g., "Jefferson Twp.")
- Numbered townships keep full spelling (e.g., "Township 4 Range 6")

---

## Bibliography Format

Bibliography entries use a hierarchical format organized by jurisdiction:

```
U.S. [State]. [County] County. [Year] U.S Census. [Schedule Type].
Imaged. "[FamilySearch Collection Title]." FamilySearch [URL] : [Year].
```

**Example:**
```
U.S. Pennsylvania. Greene County. 1930 U.S Census. Population Schedule.
Imaged. "United States Census, 1930." FamilySearch
https://familysearch.org/ark:/61903/1:1:XH3Z-4J8 : 2025.
```

---

## Source Name Format

RMCitecraft expects sources to be named in this format:

```
Fed Census: YYYY, State, County [citing details] Surname, GivenName
```

**Examples:**
```
Fed Census: 1930, Pennsylvania, Greene [citing ED 30-17, sheet 13-A] Iams, George B
Fed Census: 1950, Ohio, Stark [] Adams, Verne
Fed Census Slave Schedule: 1860, Mississippi, Tishomingo [page 21] Ijams, Burgess
Fed Census Mortality Schedule: 1850, New Jersey, Warren [line 2] Shannon, Daniel
```

**Key Points:**
- Citations created from FamilySearch hints in RootsMagic follow this format
- Empty brackets `[]` indicate details not yet filled in
- Special schedules have different prefixes

---

## Design Decisions

### Why These Specific Formats?

1. **County before State**: Follows *Evidence Explained* recommendation for U.S. census citations

2. **"enumeration district (ED)" spelled out in footnote**: Provides clarity on first reference; abbreviated to "E.D." in short footnote

3. **Sheet vs Page vs Stamp**: Uses terminology matching the original records:
   - Pre-1880: "page" (handwritten or printed page numbers)
   - 1880-1940: "sheet" (sheet 1A, 1B, 2A, 2B format)
   - 1950: "stamp" (NARA stamped numbers)

4. **"(penned)" for 1850/1870**: Indicates handwritten page numbers to distinguish from later stamped numbers

5. **"(stamped)" for 1880**: Indicates NARA-applied page numbers on microfilm

6. **Omitting "pop. sch." for 1910-1940**: Only population schedules survive for these years, so the distinction is unnecessary

7. **Including "pop. sch." for 1950**: Distinguishes from sample questionnaires used in some areas

---

## Validation Rules

RMCitecraft validates citations against these rules:

| Rule | Description |
|------|-------------|
| Census year | Must be valid decennial year (1790-1950, no 1890) |
| State | Must be present and valid |
| County | Must be present |
| ED required | For 1880-1950 censuses |
| Sheet/Stamp | Required for 1880-1950 |
| Distinct forms | Footnote must differ from short footnote |

---

## Compatibility Notes

### Working with Existing Citations

RMCitecraft can process citations that:
- Follow the "Fed Census:" source name pattern
- Have a FamilySearch URL in the citation data
- Are "free-form" citations (TemplateID = 0)

### Citations That May Not Match

If your existing citations don't match these formats:
- They won't appear in the "Incomplete" filter
- Manual formatting may be needed
- Consider reformatting to match for batch processing benefits

---

## References

- Mills, Elizabeth Shown. *Evidence Explained: Citing History Sources from Artifacts to Cyberspace*. 3rd ed. Baltimore: Genealogical Publishing Company, 2015.
- National Archives. "Census Records." https://www.archives.gov/research/census
- FamilySearch. "United States Census" collections. https://familysearch.org

---

**Document Version**: 1.0
**Last Updated**: 2025-12-30
