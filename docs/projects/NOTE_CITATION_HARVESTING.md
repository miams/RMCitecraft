---
priority: medium
topics: [citations, notes, automation, evidence-explained]
status: discovery
---

# Note Citation Harvesting Project

**Status**: Discovery / Requirements Gathering

## Objective

Harvest citation information from notes fields and generate proper Evidence Explained citations with free-form format (TemplateID=0).

## Scope

**Current State**: Many genealogical sources stored as informal notes rather than proper citations.

**Goal**: Identify notes with source information (URLs, references), categorize by type, create proper Evidence Explained citations, migrate from notes to citation structure.

## Volume Analysis

| Location | Count | Status |
|----------|-------|--------|
| Person notes with URLs | 888 | Identified |
| Event notes with URLs | 6,178 | Identified |
| **Total** | **7,066** | **Target** |

### URL Distribution

| Domain | Count | % |
|--------|-------|---|
| FamilySearch | 3,367 | 47.6% |
| Newspapers.com | 2,220 | 31.4% |
| Ancestry.com | 677 | 9.6% |
| Other | ~800 | 11.3% |

### Priority: Events Without Citations

Events with URL notes but NO linked citations (prime targets):

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

**Citation Status**:
- Events with URLs that HAVE citations: 2,477
- Events with URLs WITHOUT citations: 3,701 (**primary target**)

## Top FamilySearch Collections

| Collection | Count |
|------------|-------|
| U.S. Social Security NUMIDENT | 166 |
| U.S. Social Security Death Index | 108 |
| U.S. Public Records, 1970-2009 | 101 |
| Ohio, County Marriages, 1789-1994 | 98 |
| Pennsylvania, County Marriages, 1885-1950 | 87 |
| U.S. WWII Draft Registration Cards, 1942 | 55 |
| Ohio, Deaths, 1908-1953 | 49 |
| North Carolina, County Marriages, 1762-1979 | 49 |

**Total Unique Collections**: ~50+

## Common Note Patterns

### Pattern 1: Well-Formatted FamilySearch Citation
```
"Pennsylvania, County Marriages, 1885-1950," index and images, <i>FamilySearch</i>
(https://familysearch.org/pal:/MM9.1.1/VFQ9-J71 : accessed 06 Oct 2013),
James B Iams and Ruth Jones, 1941.
```
Already Evidence Explained format.

### Pattern 2: FamilySearch with Citing Info
```
"California Birth Index, 1905-1995," database, <i>FamilySearch</i>
(https://familysearch.org/ark:/61903/1:1:VLDB-6KS : 27 November 2014),
Robert Ijams, 07 Mar 1920; citing Los Angeles, California, United States,
Department of Health Services, Vital Statistics Department, Sacramento.
```
Includes original source citation.

### Pattern 3: Ancestry Source Information
```
Source Information
Ancestry.com. <i>Pennsylvania, U.S., Marriages, 1852-1968</i> [database on-line].
Lehi, UT, USA: Ancestry.com Operations, Inc., 2016.

Original data: <i>Marriage Records</i>. <i>Pennsylvania Marriages.</i>
Various County Register of Wills Offices, Pennsylvania.

https://www.ancestry.com/discoveryui-content/view/902116152%3A61381
```
Structured with source info, original data, URL.

### Pattern 4: Newspapers.com Citation
```
Source Citation
The Bristol Daily Courier; Publication Date: 15/ Apr/ 1964;
Publication Place: Bristol, Pennsylvania, USA;
URL: https://www.newspapers.com/image/53107874/...
```

### Pattern 5: Raw Note with URL
```
http://wc.rootsweb.ancestry.com/cgi-bin/igm.cgi?op=GET&db=raykohler&id=I29652
DEATH NOTICE:
HOWARD IMES
[transcription]
(Juniata Sentinel & Republican - August 22, 1917)
```

## Technical Approach

### Phase 1: Parser Development

**Parsers**:
1. **FamilySearchParser** - Parse FamilySearch-formatted citations
2. **AncestryParser** - Parse Ancestry source information blocks
3. **NewspapersComParser** - Parse Newspapers.com citations
4. **GenericURLParser** - Extract URLs and context

### Phase 2: Source Matching/Creation

1. Check if source exists (by collection name + year)
2. Create new free-form source if needed (TemplateID=0)
3. Reuse existing sources

### Phase 3: Citation Generation

**Evidence Explained Format** (4th ed., p. 423 - Emphasis on database):

**Structure**:
- **Layer 1 (Source)**: Database collection
- **Specific Item Block (Citation)**: Person names, dates, record details
- **Location Layer**: "citing..." original source info

**Example**:
```
Footnote:
"Ohio, County Marriages, 1789-2013," database with images, FamilySearch
(https://familysearch.org/ark:/61903/1:1:X8Z9-S3F : 10 December 2017),
William W. Iiams and Angela Hilbrant, 11 Dec 1887; citing Marriage,
Shelby, Ohio, United States, Franklin County Genealogical & Historical Society.

Short Footnote:
"Ohio, County Marriages," FamilySearch, William W. Iiams and Angela Hilbrant, 1887.

Bibliography:
"Ohio, County Marriages, 1789-2013." Database with images. FamilySearch.
http://FamilySearch.org.
```

### Phase 4: Image Download (Optional)

1. Connect to Chrome CDP (pre-authenticated FamilySearch)
2. Navigate to ARK URL from note
3. Download record image(s)
4. Save to `~/Genealogy/RootsMagic/Files/Records - Marriage Certificates/`
5. Create MediaTable record and link to Citation

### Phase 5: Note Cleanup

1. Optionally preserve original note as research note
2. Remove citation text from event notes after migration
3. Keep person notes as-is (reference only)

## Source Naming Standards

### Current Issues (Marriage Records Example)

**29 existing sources** with inconsistencies:
- 10 use templates (not free-form)
- 15 missing provider suffix
- 7 have quotes in source name
- 6 include person names (should be in citation only)
- Multiple typos: "Viirginia", "Counter" (should be "County")

### Recommended Standard

**Format**: `Marriage Records: [State], [Collection] - [Groom Surname], [Groom Given] & [Bride Surname], [Bride Given], [Year]`

**Rules**:
1. Always free-form (TemplateID=0)
2. One Source per marriage record (enables unique Footnote)
3. State first (geographic sorting)
4. No redundant state prefix in collection name
5. Surnames before given names
6. Marriage year at end
7. No quotes in source name
8. Full state names (not abbreviations)

**Examples**:
```
Marriage Records: North Carolina, County Marriages 1762-1979 - Ijams, William & Hanes, Caty, 1812
Marriage Records: Ohio, County Marriages 1789-2013 - Iiams, William & Hilbrant, Angela, 1887
Marriage Records: Pennsylvania, County Marriages 1885-1950 - Iams, James & Jones, Ruth, 1941
```

## FamilySearch Marriage Analysis

### Priority by Domain (Uncited Events)

| Domain | Count | % | Notes |
|--------|-------|---|-------|
| **FamilySearch** | **2,505** | **68%** | **Priority target** |
| Ancestry | 462 | 12% | Paywalled |
| Newspapers.com | 136 | 4% | Most already cited |
| State archives | ~80 | 2% | Various |
| Other | ~520 | 14% | Misc |

### FamilySearch Marriage Breakdown (1,040 uncited)

| Collection Type | Count | % |
|-----------------|-------|---|
| State, County Marriages | 586 | 56% |
| State Marriages (statewide) | 317 | 30% |
| State Marriage Index | 83 | 8% |
| Marriage Certificates | 15 | 1.5% |
| Vital Record Indexes | 12 | 1% |
| Other | 27 | 3% |

### Top States (Uncited Marriage Events)

| State | Count |
|-------|-------|
| Ohio | 201 |
| Pennsylvania | 106 |
| North Carolina | 86 |
| Indiana | 75 |
| Iowa | 60 |
| California | 44 |
| Missouri | 41 |

**Unique Collections**: 137 unique FamilySearch collections, ~11 match existing sources, **~126 new sources to create**

## Implementation Plan

### Phase 1: Prototype CLI (2-3 days)
- Build FamilySearch marriage note parser
- Test extraction on 10 Ohio County Marriages
- Implement source name standardization
- Define Evidence Explained templates

### Phase 2: Source Migration (1 week)
- Fix 10 templated sources → free-form
- Fix typos, remove person names from source names
- Add provider suffix where missing
- Remove quotes from collection names

### Phase 3: Batch Processing (1-2 weeks)
- Process FamilySearch marriages (highest priority)
- Create ~126 new sources
- Generate 1,040 citations
- Link to events (CitationLinkTable)

### Phase 4: Expansion (future)
- Ancestry marriages (paywalled, lower priority)
- Birth/death records
- Other event types
- Image downloads (optional)

## Questions to Resolve

### Decided
1. **URL patterns?** - FamilySearch ark URLs (2,388), Newspapers.com (2,220), Ancestry (677)
2. **Most common types?** - FamilySearch vital records, Social Security, newspapers

### Open
1. **One source per collection or per record?** → Recommend: One source per record (enables unique Footnote)
2. **Handle notes with existing citations?** → Skip, verify, or flag for review?
3. **Preserve original note text?** → Keep as research note, append to citation, or discard?
4. **Priority order?** → Start with FamilySearch marriages (1,040 uncited events)
5. **Auto-process or review batches?** → Review first 10 of each type, then batch process

## File Paths

| Record Type | Image Storage |
|-------------|---------------|
| Census | `~/Genealogy/RootsMagic/Files/Records - Census/` |
| Marriage | `~/Genealogy/RootsMagic/Files/Records - Marriage Certificates/` |

**Note**: Marriage image organization not yet fully consistent.

## Reference Materials

**Evidence Explained 4th Edition**: User has physical copy.

**Process**: When uncertain about Evidence Explained formatting, ask user to reference the book.

**Key Areas**:
- Footnote format for online database citations
- Short footnote abbreviations
- Bibliography format for digital collections
- State vital records patterns
- Layered citations (derivative vs original source)

## Progress Log

- **2026-01-01**: Project initiated, discovery phase
- **2026-01-01**: Database analysis complete:
  - 7,066 notes with URLs
  - 3,701 events without citations (priority)
  - 50+ unique FamilySearch collections
  - 5 common note patterns documented
  - Technical architecture proposed
  - Source naming standard defined
