# Note Citation Harvesting Project

## Objective
Harvest citation information from notes fields in the RootsMagic database and generate proper Evidence Explained citations with free-form style.

## Status
**Phase**: Discovery / Requirements Gathering

## Overview
Many genealogical sources are currently stored as informal notes rather than proper citations. This project aims to:
1. Identify notes containing source information (URLs, source references)
2. Categorize by source type (FamilySearch, Ancestry, state vital records, etc.)
3. Create citation templates for common source types
4. Generate proper Evidence Explained citations
5. Migrate data from notes to proper citation structure

## Target Note Locations
- Person notes (PersonTable.Note)
- Birth event notes
- Death event notes
- Other event notes with URLs

## Source Types to Support
- FamilySearch collections
- Ancestry.com collections
- Newspapers.com
- State vital records (e.g., "California Births")
- Other online sources

---

## Discovery Findings

### Database Analysis (2026-01-01)

#### Volume Summary
| Location | Count |
|----------|-------|
| Person notes with URLs | 888 |
| Event notes with URLs | 6,178 |
| **Total notes to process** | **7,066** |

#### URL Domain Distribution
| Domain | Count |
|--------|-------|
| FamilySearch | 3,367 |
| Newspapers.com | 2,220 |
| Ancestry.com | 677 |
| Other | ~800 |

#### Event Types Without Citations (Highest Priority)
Events that have URL notes but NO linked citations - prime candidates for harvesting:

| Event Type | Count |
|------------|-------|
| Marriage | 1,374 |
| Death | 887 |
| Birth | 689 |
| Obituary | 268 |
| Divorce | 96 |
| War Veteran | 59 |
| News | 54 |
| WWII Draft | 51 |
| WWI Draft | 20 |
| **Total** | **3,701** |

#### Citation Status
- Events with URL notes that HAVE citations: 2,477
- Events with URL notes WITHOUT citations: 3,701 (target)

### FamilySearch Collection Analysis

Most frequently referenced FamilySearch collections in notes:

| Collection | Count |
|------------|-------|
| United States, Social Security Numerical Identification Files (NUMIDENT) | 166 |
| United States Social Security Death Index | 108 |
| United States Public Records, 1970-2009 | 101 |
| Ohio, County Marriages, 1789-1994 | 98 |
| Pennsylvania, County Marriages, 1885-1950 | 87 |
| United States World War II Draft Registration Cards, 1942 | 55 |
| Ohio, Deaths, 1908-1953 | 49 |
| North Carolina, County Marriages, 1762-1979 | 49 |
| Iowa, County Marriages, 1838-1934 | 46 |
| Texas Birth Index, 1903-1997 | 42 |
| Ohio, Marriages, 1800-1958 | 40 |
| Ohio, County Births, 1841-2003 | 39 |
| California Death Index, 1940-1997 | 38 |
| California Birth Index, 1905-1995 | 38 |

### Common Note Patterns

#### Pattern 1: Well-Formatted FamilySearch Citation
```
"Pennsylvania, County Marriages, 1885-1950," index and images, <i>FamilySearch</i>
(https://familysearch.org/pal:/MM9.1.1/VFQ9-J71 : accessed 06 Oct 2013),
James B Iams and Ruth Jones, 1941.
```
- Already in Evidence Explained format
- Contains: collection name, record type, publisher, URL, access date, subject details

#### Pattern 2: FamilySearch Citation with Citing Info
```
"California Birth Index, 1905-1995," database, <i>FamilySearch</i>
(https://familysearch.org/ark:/61903/1:1:VLDB-6KS : 27 November 2014),
Robert Ijams, 07 Mar 1920; citing Los Angeles, California, United States,
Department of Health Services, Vital Statistics Department, Sacramento.
```
- Includes original source citation

#### Pattern 3: Ancestry Source Information
```
Source Information
Ancestry.com. <i>Pennsylvania, U.S., Marriages, 1852-1968</i> [database on-line].
Lehi, UT, USA: Ancestry.com Operations, Inc., 2016.

Original data: <i>Marriage Records</i>. <i>Pennsylvania Marriages.</i>
Various County Register of Wills Offices, Pennsylvania.

https://www.ancestry.com/discoveryui-content/view/902116152%3A61381
```
- Structured with source info, original data, and URL

#### Pattern 4: Newspapers.com Citation
```
Source Citation
The Bristol Daily Courier; Publication Date: 15/ Apr/ 1964;
Publication Place: Bristol, Pennsylvania, USA;
URL: https://www.newspapers.com/image/53107874/...
```
- Contains publication name, date, place, and URL

#### Pattern 5: Raw Note with URL
```
http://wc.rootsweb.ancestry.com/cgi-bin/igm.cgi?op=GET&db=raykohler&id=I29652
DEATH NOTICE:
HOWARD IMES
[transcription of death notice]
(Juniata Sentinel & Republican - August 22, 1917)
```
- URL plus transcribed content with source reference

---

## Technical Approach

### Proposed Architecture

#### Phase 1: Parser Development
Create parsers for each source pattern:
1. **FamilySearchParser** - Parse FamilySearch-formatted citations
2. **AncestryParser** - Parse Ancestry source information blocks
3. **NewspapersComParser** - Parse Newspapers.com citations
4. **GenericURLParser** - Extract URLs and surrounding context

#### Phase 2: Source Matching/Creation
1. Check if source already exists (by collection name + year)
2. Create new free-form source if needed
3. Use TemplateID=0 (free-form) for all generated sources

#### Phase 3: Citation Generation
1. Generate Evidence Explained format citations
2. Create Footnote, Short Footnote, Bibliography forms
3. Link citations to events (CitationLinkTable)

#### Phase 4: Note Cleanup
1. Optionally preserve original note as research note
2. Remove citation text from event notes after migration
3. Keep person notes as-is (reference only)

### Database Operations

#### Source Creation
```sql
-- Free-form source (TemplateID=0)
INSERT INTO SourceTable (Name, TemplateID, Fields)
VALUES ('Birth Records: California Birth Index, 1905-1995 - FamilySearch', 0, [BLOB])
```

#### Citation Linking
```sql
-- Link citation to event
INSERT INTO CitationLinkTable (OwnerType, OwnerID, CitationID, Quality, ...)
VALUES (2, [EventID], [CitationID], 'PDO', ...)
```

---

## Questions to Resolve

### Already Answered
1. **What URL patterns exist in notes?**
   - FamilySearch ark URLs (2,388), Newspapers.com URLs (2,220), Ancestry URLs (677)

2. **What are the most common source types?**
   - FamilySearch vital records (births, deaths, marriages)
   - Social Security files (SSDI, NUMIDENT)
   - Newspapers.com clippings
   - Ancestry record collections

### Still Need to Decide
1. **Should we create one source per collection, or per record?**
   - Recommendation: One source per collection, multiple citations

2. **How to handle notes that already have citations?**
   - Skip? Verify? Flag for review?

3. **Should the original note text be preserved?**
   - Options: Keep as research note, append to citation, discard

4. **Priority order for processing?**
   - Suggestion: Start with events WITHOUT citations (3,701 records)

5. **Should we auto-process or require user review per batch?**
   - Consider: Review first 10 of each type, then batch process

---

## Progress Log
- **2026-01-01**: Project initiated, beginning discovery phase
- **2026-01-01**: Completed initial database analysis:
  - Identified 7,066 total notes with URLs
  - Found 3,701 events without citations (priority targets)
  - Analyzed top FamilySearch collections (50+ unique collections)
  - Documented 5 common note patterns
  - Proposed technical architecture

---

## Next Steps
1. Build prototype parser for FamilySearch formatted citations (most common, well-structured)
2. Test extraction on sample of 10-20 notes
3. Define Evidence Explained citation templates for each source type
4. Decide on user review workflow
