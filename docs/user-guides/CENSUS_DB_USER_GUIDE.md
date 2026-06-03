# Census.db User Guide

A visual guide to understanding and using the Census Extraction Database for genealogical research.

---

## What is Census.db?

Census.db is a **structured data repository** that extends RootsMagic's capabilities for census research. While RootsMagic stores citations as free-form text, census.db stores the actual transcribed data in searchable, queryable fields.

[DIAGRAM: Two-panel comparison showing RootsMagic on the left with a citation displayed as a block of formatted text reading "1790 U.S. census, Anne Arundel County, Maryland, page 368, line 24, John Iiams..." versus census.db on the right showing the same information broken into labeled fields: census_year=1790, state=Maryland, county=Anne Arundel, page_number=368, line_number=24, full_name=John Iiams, with each field in its own box. An arrow between them shows "Structured vs. Unstructured" with the caption "RootsMagic stores what you cite; census.db stores what you extracted."]

### Why Two Databases?

| RootsMagic (.rmtree) | Census.db |
|---------------------|-----------|
| Stores **citations** (text references) | Stores **transcriptions** (actual data) |
| One person per citation | Entire households together |
| Free-form text | Structured, searchable fields |
| Cannot query "all farmers in 1850" | Can query any field combination |
| No edit history | Tracks all changes |

---

## The Big Picture: How Everything Connects

[DIAGRAM: A comprehensive system architecture diagram showing three main components arranged horizontally. On the left is a large rounded rectangle labeled "RootsMagic Database (.rmtree)" containing stacked boxes for PersonTable, EventTable, CitationTable, and SourceTable. In the center is a cylinder shape labeled "Census.db" containing stacked boxes for census_person, census_page, census_person_field, and rmtree_link. On the right is a cloud shape labeled "FamilySearch" with document icons inside.

Arrows connect these components:
1. A bidirectional arrow labeled "rmtree_link table" connects RootsMagic's PersonTable to census.db's census_person
2. Another arrow labeled "SourceID reference" connects SourceTable to rmtree_link
3. An arrow labeled "Playwright Extraction" goes from FamilySearch cloud into census.db
4. A dashed arrow labeled "Citation ARK URLs" connects CitationTable to FamilySearch

Below the main diagram, a caption reads: "Census.db sits between your genealogy software and online sources, storing the detailed data that RootsMagic cannot hold in structured form."]

---

## Database Location

```
~/.rmcitecraft/census.db     (macOS/Linux)
%USERPROFILE%\.rmcitecraft\census.db     (Windows)
```

You can open this database with any SQLite browser (DB Browser for SQLite, DBeaver, etc.) to explore and query directly.

---

## Core Tables: A Visual Tour

Census.db contains 12 tables organized into four functional groups:

[DIAGRAM: A hierarchical organization chart with four main branches, each a different color:

**Branch 1 (Blue): "Extraction Tracking"**
- extraction_batch (stores when and how data was extracted)

**Branch 2 (Green): "Census Data"**
- census_page (the physical page: year, state, county, ED, sheet)
  - census_person (each person on the page: name, age, occupation)
    - census_person_field (extra fields via key-value pairs)
    - census_relationship (connections to other persons)

**Branch 3 (Orange): "RootsMagic Integration"**
- rmtree_link (the bridge: connects census_person to RIN and SourceID)

**Branch 4 (Purple): "Quality & History"**
- field_quality (confidence scores, verification status)
- field_history (version control for edits)
- match_attempt (algorithm performance tracking)
- extraction_gap (missing data documentation)
- gap_pattern (recurring problem catalog)

The diagram shows parent-child relationships with connecting lines, and each table box includes 2-3 example columns to give a sense of what it stores.]

---

## Table 1: census_page — The Census Page

Every census record lives on a physical page. This table stores page-level metadata shared by everyone enumerated on that page.

[DIAGRAM: A representation of a census page document (like a form) on the left side, with labeled callout lines pointing to a database table on the right. The census form shows header information at the top (State, County, Township, ED number, Sheet number, Enumeration date, Enumerator name) and a grid of lines below. Each piece of header information has an arrow pointing to the corresponding column in the census_page table:

census_page table columns shown:
- page_id (auto-generated)
- census_year → "1790, 1800, ... 1950"
- state → "Maryland"
- county → "Anne Arundel"
- township_city → "South River"
- enumeration_district → "95" (1880+)
- sheet_number → "3B" (1880-1940)
- page_number → "368" (1790-1870, 1950)
- stamp_number → for 1950 terminology
- enumeration_date → "August 2, 1790"
- enumerator_name → "John Smith"
- familysearch_image_url → link to actual image

Caption: "One census_page record represents one physical page of the census. All persons enumerated on that page share these location details."]

### Key Insight: Page vs. Sheet vs. Stamp

Different census years use different terminology:

| Census Years | Location Identifier | Column Used |
|--------------|---------------------|-------------|
| 1790-1870 | Page number | `page_number` |
| 1880-1940 | Sheet number (A/B sides) | `sheet_number`, `sheet_letter` |
| 1950 | Stamp number | `stamp_number` |

---

## Table 2: census_person — The Individual

Each person enumerated gets one record. This table stores the "core" fields present in most census years.

[DIAGRAM: A visual representation of a census form line showing a single row of handwritten-style text: "24 | John Iiams | Head | M | W | 34 | Farmer | Maryland". Below this, arrows point down to a database record representation showing the census_person table with columns:

- person_id: 2491
- page_id: 532 (links to census_page)
- line_number: 24
- full_name: "John Iiams"
- given_name: "John"
- surname: "Iiams"
- relationship_to_head: "Head"
- sex: "M"
- race: "W"
- age: 34
- marital_status: "M"
- birthplace: "Maryland"
- occupation: "Farmer"
- familysearch_ark: (URL)
- is_target_person: 1 (was this the person you searched for?)

Caption: "Each line on the census form becomes one census_person record. The page_id links back to the page metadata."]

### 1790-1840 Census: A Special Case

Early censuses (1790-1840) only named the **head of household** and counted everyone else in age/sex categories. For these years:

[DIAGRAM: A representation of a 1790 census entry showing a single row with columns: "Name of Head | Free White Males 16+ | Free White Males <16 | Free White Females | Other Free | Slaves". The example shows: "John Iiams | 2 | 1 | 1 | 0 | 0"

Below this, the diagram shows how this maps to census.db:
- One census_person record (for John Iiams, the head)
- Multiple census_person_field records storing the tallies:
  - field_name: "free_white_males_16_plus", field_value: "2"
  - field_name: "free_white_males_under_16", field_value: "1"
  - field_name: "free_white_females", field_value: "1"
  - field_name: "slaves", field_value: "0"
  - field_name: "total_household", field_value: "4"

Caption: "For 1790-1840, census_person holds the head of household, while census_person_field stores the tally columns as key-value pairs."]

---

## Table 3: census_person_field — The EAV Pattern

Census forms changed every decade. Rather than 200+ columns, census.db uses the **Entity-Attribute-Value (EAV)** pattern: store each field as a row with a name and value.

[DIAGRAM: A side-by-side comparison. On the left, a traditional wide table approach labeled "BAD: One Column Per Field" shows a table with 50+ columns stretching horizontally, most empty, with column headers like "income_1950", "weeks_worked_1940", "veteran_ww2", etc. Many cells show "NULL".

On the right, the EAV approach labeled "GOOD: Key-Value Pairs" shows a narrow table with just 4 columns: field_id, person_id, field_name, field_value. Multiple rows show:
- 1, 2491, "income", "4500"
- 2, 2491, "weeks_worked", "52"
- 3, 2491, "veteran_ww2", "Yes"

Caption: "EAV pattern: Instead of 200 columns (mostly empty), store only the fields that have values. Each field becomes a row."]

### Common Field Names by Census Era

| Era | Common Fields Stored |
|-----|---------------------|
| **1790-1840** | free_white_males_16_plus, free_white_males_under_16, free_white_females, slaves, other_free_persons, total_household |
| **1850-1870** | real_estate_value, personal_estate_value, attended_school, cannot_read_write |
| **1880-1930** | months_unemployed, parents_birthplace, citizenship_status, year_immigrated |
| **1940-1950** | income, weeks_worked, hours_worked, grade_completed, veteran_ww2 |

---

## Table 4: rmtree_link — The Bridge to RootsMagic

This is the **most critical table** for integration. It connects census.db records to RootsMagic persons and sources.

[DIAGRAM: A bridge illustration showing two landmasses. On the left landmass labeled "Census.db", there's a census_person record with person_id=2491 and full_name="John Iiams". On the right landmass labeled "RootsMagic", there are two records: PersonTable with PersonID=11803 (RIN) and SourceTable with SourceID=2665.

The bridge between them is labeled "rmtree_link" and shows the connecting data:
- link_id: 47
- census_person_id: 2491 → (arrow to census_person)
- rmtree_person_id: 11803 → (arrow to PersonTable, labeled "The RIN!")
- rmtree_citation_id: 2665 → (arrow to SourceTable)
- match_confidence: 0.95
- match_method: "source_sync"
- linked_at: "2026-01-07T16:43:00"

Caption: "rmtree_link is the bridge. It says 'Census person #2491 is RIN 11803 in RootsMagic, documented by Source #2665.'"]

### Match Methods Explained

| match_method | Meaning |
|--------------|---------|
| `url_match` | Matched via FamilySearch ARK URL in citation |
| `auto_fuzzy_v2` | Automatic name matching algorithm |
| `source_sync` | Synced from RootsMagic source linkage |
| `manual_gps` | Manual link with GPS documentation |
| `user_confirmed` | User verified a suggested match |
| `user_rejected` | User explicitly said "not this person" |

---

## The Complete Data Flow

[DIAGRAM: A flowchart showing data movement through the system, reading left to right:

**Stage 1: "Source"**
Cloud icon labeled "FamilySearch" or "Ancestry" containing census images and transcriptions.

**Arrow labeled "Playwright Automation"** →

**Stage 2: "Extract"**
Cylinder labeled "census.db" with data flowing into three boxes inside:
- census_page (location metadata)
- census_person (person details)
- census_person_field (extended fields)

**Arrow labeled "rmtree_link"** ↔

**Stage 3: "Integrate"**
Box labeled "RootsMagic" containing:
- PersonTable (RIN)
- SourceTable (citation)
- EventTable (census event)

**Arrow labeled "Citation"** →

**Stage 4: "Output"**
Document icon labeled "Evidence Explained Citation" showing formatted footnote text.

Below the flowchart, a timeline shows the typical workflow:
1. "Search FamilySearch for ancestor"
2. "Extract census page with Playwright"
3. "Data stored in census.db"
4. "Link to RootsMagic person (RIN)"
5. "Generate formatted citation"

Caption: "Data flows from online sources through census.db to RootsMagic. The rmtree_link maintains the connection."]

---

## Use Case 1: Tracking a Family Across Decades (1790-1860)

This replicates the **90-60 Census Workbook** functionality: stack census records to see family changes over time.

[DIAGRAM: A vertical timeline visualization showing the Iiams household across multiple census years. Each census year is a horizontal band:

**1790 Band (top):**
Box showing "John Iiams (Head)" with tally boxes: "2 M16+ | 1 M<16 | 1 F | Total: 4"

**1800 Band:**
Box showing "John Iiams (Head)" with tally boxes: "3 M16+ | 2 M<16 | 3 F | Total: 8"
Yellow highlight on the increased numbers with annotation "Family grew"

**1810 Band:**
Box showing "John Iiams (Head)" with tally boxes: "2 M16+ | 0 M<16 | 2 F | Total: 4"
Yellow highlight with annotation "Children left home?"

**1820 Band:**
Box showing "Mary Iiams (Head)" with annotation "Widow - John died"

**1830-1840 Bands:** (similar pattern)

**1850 Band (wider, showing individuals):**
Individual boxes for each person now named:
"Mary Iiams, 70, Head" | "William Iiams, 45, Son" | "Sarah Iiams, 40, Daughter"

Caption: "Stacking census records vertically reveals family changes: births, deaths, marriages, children leaving home. This is the core function of the 90-60 Census Workbook, now in database form."]

### SQL Query for Family Timeline

```sql
-- Get all census records for Iiams family in Maryland, ordered by year
SELECT
    pg.census_year,
    cp.full_name,
    cp.relationship_to_head,
    cp.age,
    MAX(CASE WHEN cpf.field_name = 'free_white_males_16_plus' THEN cpf.field_value END) as M16_plus,
    MAX(CASE WHEN cpf.field_name = 'free_white_males_under_16' THEN cpf.field_value END) as M_under_16,
    MAX(CASE WHEN cpf.field_name = 'free_white_females' THEN cpf.field_value END) as Females,
    MAX(CASE WHEN cpf.field_name = 'total_household' THEN cpf.field_value END) as Total
FROM census_person cp
JOIN census_page pg ON cp.page_id = pg.page_id
LEFT JOIN census_person_field cpf ON cp.person_id = cpf.person_id
WHERE cp.surname LIKE '%Iiams%'
  AND pg.state = 'Maryland'
  AND pg.census_year BETWEEN 1790 AND 1860
GROUP BY cp.person_id
ORDER BY pg.census_year, cp.line_number;
```

---

## Use Case 2: Identifying Unnamed Family Members

Before 1850, only household heads were named. Census.db helps you **deduce who the unnamed people were**.

[DIAGRAM: A detective-style investigation board with strings connecting clues:

**Central Question Box:** "Who are the '2 males 16+' in John Iiams' 1790 household?"

**Clue 1 (left):**
1790 Census record showing "John Iiams, Head, 2 M16+, 1 M<16, 1 F"
Arrow pointing to: "John himself is 1 of the 2 adult males"

**Clue 2 (top):**
RootsMagic data showing "John Iiams (RIN 11803), born 1756"
"His brother Plummer born 1748 - also an adult!"

**Clue 3 (right):**
1791 Will document showing "Elizabeth Selman, housekeeper"
Arrow: "Explains the 1 female!"

**Clue 4 (bottom):**
List of John's known children with birth years:
"Son James, born 1775 = 15 years old in 1790 = under 16 ✓"

**Conclusion Box:**
"Probable household composition:
- John Iiams (Head, 34) - M 16+
- Brother Plummer (42) - M 16+
- Son James (15) - M under 16
- Elizabeth Selman (housekeeper) - Female"

Caption: "Census.db stores the tallies. You use RootsMagic family data to deduce identities. The rmtree_link connects your conclusions."]

---

## Use Case 3: Complete Household Extraction

When you extract a census record, get **everyone on the page**, not just your target ancestor.

[DIAGRAM: A representation of a census page showing multiple household entries:

**Page 368, Anne Arundel County, Maryland, 1790**

Line 11: Charity Iiams (widow) — 1 female
Line 12: Josephus Waters — 1 M16+, 3 M<16, 4 F, 4 slaves
Line 13: John Elder — 3 M16+, 1 M<16, 1 F, 1 slave
Line 14: Thomas Iiams — 2 M16+, 3 M<16, 2 F
Line 15: Penelopes Iiams — 1 female
...
Line 24: John Iiams — 2 M16+, 1 M<16, 1 F

All entries are shown as rows in a database table visualization, with arrows showing:
- All share the same page_id (pointing to census_page record)
- Each has its own person_id (pointing to individual census_person records)
- Nearby families might be relatives! (annotation highlighting Charity, Thomas, Penelopes, and John Iiams clustered together)

Caption: "Neighbors on census pages are often relatives. Census.db stores entire pages, letting you discover family clusters."]

---

## Use Case 4: Linking Census to RootsMagic with GPS Documentation

For ambiguous matches, document your reasoning in the Source Comments field.

[DIAGRAM: A workflow showing the GPS (Genealogical Proof Standard) documentation process:

**Step 1: "Ambiguous Census Record"**
Census record box: "John Iram, 1790, Anne Arundel, 1 M16+, 1 F, 4 slaves"
Question marks around it: "Which John is this?"

**Step 2: "Gather Evidence"**
Multiple evidence boxes connected by lines:
- "Will of John Ijams (1791): names housekeeper Elizabeth Selman"
- "Will mentions slaves: Sifo, Nan"
- "Father Plummer on same 1790 census, p.357"
- "Died 1791 - explains why no 1800 census"

**Step 3: "Document in Source Comments"**
RootsMagic Source dialog mockup showing Comments field with formatted GPS text:
"<b>Genealogical Proof Statement</b>
<u>Conclusion:</u> This record is John Iiams (1756-1791)...
<u>Evidence:</u> 1. Will names housekeeper... 2. Father on same census..."

**Step 4: "Create rmtree_link"**
Database record showing:
census_person_id: 2493 → rmtree_person_id: 1315
match_method: "manual_gps"
match_confidence: 0.95

Caption: "For difficult identifications, document your reasoning. The GPS goes in RootsMagic's Source Comments; the link goes in rmtree_link."]

---

## Use Case 5: Syncing Sources with Census.db

When you create new Source records in RootsMagic, sync them to census.db.

[DIAGRAM: A synchronization workflow showing bidirectional data flow:

**Left Panel: "RootsMagic Sources"**
List of source records:
- SourceID 2665: "1790, Anne Arundel, p.368, line 24, John Iiams" → RIN 11803
- SourceID 12524: "1790, Anne Arundel, p.380, line 12, John Iiams" → RIN 11804
- SourceID 12525: "1790, Anne Arundel, p.395, line 4, John Iiams" → RIN 1315

**Center: Sync Process**
Arrows showing data flow with Python code snippet:
```python
# Sync script creates/updates rmtree_link
cursor.execute('''
    INSERT INTO rmtree_link
    (census_person_id, rmtree_person_id, rmtree_citation_id)
    VALUES (?, ?, ?)
''', (2491, 11803, 2665))
```

**Right Panel: "census.db rmtree_link table"**
Table showing the synchronized links:
| census_person_id | rmtree_person_id | rmtree_citation_id |
| 2491 | 11803 | 2665 |
| 2492 | 11804 | 12524 |
| 2493 | 1315 | 12525 |

Caption: "Keep census.db in sync with RootsMagic. When you link a Source to a RIN, update rmtree_link to maintain the connection."]

---

## Use Case 6: Quality Tracking and Verification

Track transcription confidence and human verification status.

[DIAGRAM: A quality dashboard visualization showing:

**Top Section: "Confidence Scores"**
A horizontal bar chart showing records by confidence level:
- Green bar (0.9-1.0): "High confidence - 450 records"
- Yellow bar (0.7-0.9): "Medium confidence - 120 records"
- Red bar (< 0.7): "Needs review - 35 records"

**Middle Section: "Verification Pipeline"**
A Kanban-style board with columns:
- "Extracted" (150 cards)
- "AI Suggested" (45 cards)
- "Human Verified" (400 cards)
- "Corrected" (12 cards)

**Bottom Section: "field_quality Table Example"**
Table showing:
| person_id | field_name | confidence_score | source_legibility | human_verified |
| 2491 | occupation | 0.65 | faded | 0 |
| 2491 | age | 0.95 | clear | 1 |

Caption: "field_quality tracks how confident we are in each transcription. Low-confidence fields need human review."]

---

## How census.db Replaces the 90-60 Census Workbook

The 90-60 Census Workbook is a Google Sheets tool for 1790-1860 census research. Census.db provides the same functionality in database form, with additional benefits:

[DIAGRAM: A feature comparison matrix with two columns:

**90-60 Census Workbook (Spreadsheet)**
- Manual data entry ❌
- 10 million cell limit ❌
- Cannot link to genealogy software ❌
- Filter/sort with scripts ⚠️
- Color-coded categories ✓
- Household stacking view ✓
- Birth year range calculation ✓

**Census.db (Database)**
- Automated extraction from FamilySearch ✓
- Unlimited records ✓
- Direct link to RootsMagic RINs ✓
- SQL queries for any analysis ✓
- Query by any combination of fields ✓
- Household stacking via queries ✓
- Birth year calculation via queries ✓
- Version history for all edits ✓
- Quality/verification tracking ✓
- API for custom applications ✓

An arrow at the bottom shows "Migration Path: Export workbook → Import to census.db"

Caption: "Census.db does everything the spreadsheet does, plus links to RootsMagic, tracks quality, and scales to any size."]

### Mapping 90-60 Workbook Fields to Census.db

| 90-60 Workbook Field | Census.db Location |
|---------------------|-------------------|
| Census Year | census_page.census_year |
| Page/Image Number | census_page.page_number |
| Head of Household | census_person.full_name |
| Community | census_page.township_city |
| County/Parish | census_page.county |
| State | census_page.state |
| Free White Males 16+ | census_person_field (field_name='free_white_males_16_plus') |
| Free White Males <16 | census_person_field (field_name='free_white_males_under_16') |
| Free White Females | census_person_field (field_name='free_white_females') |
| Free Colored Persons | census_person_field (field_name='other_free_persons') |
| Slaves | census_person_field (field_name='slaves') |
| Comments | SourceTable.Comments (in RootsMagic) |
| User Field 1 | census_person_field (custom field_name) |
| User Field 2 | census_person_field (custom field_name) |

---

## Quick Reference: Common Queries

### Find all persons with a surname
```sql
SELECT cp.*, pg.census_year, pg.state, pg.county
FROM census_person cp
JOIN census_page pg ON cp.page_id = pg.page_id
WHERE cp.surname LIKE '%Iiams%'
ORDER BY pg.census_year;
```

### Get household tallies for 1790-1840 records
```sql
SELECT
    cp.full_name,
    pg.census_year,
    pg.county,
    MAX(CASE WHEN cpf.field_name = 'free_white_males_16_plus' THEN cpf.field_value END) as M16_plus,
    MAX(CASE WHEN cpf.field_name = 'free_white_males_under_16' THEN cpf.field_value END) as M_under_16,
    MAX(CASE WHEN cpf.field_name = 'free_white_females' THEN cpf.field_value END) as Females,
    MAX(CASE WHEN cpf.field_name = 'slaves' THEN cpf.field_value END) as Slaves
FROM census_person cp
JOIN census_page pg ON cp.page_id = pg.page_id
LEFT JOIN census_person_field cpf ON cp.person_id = cpf.person_id
WHERE pg.census_year <= 1840
GROUP BY cp.person_id
ORDER BY pg.census_year;
```

### Find census records linked to a RootsMagic person
```sql
SELECT
    cp.full_name,
    pg.census_year,
    pg.state,
    pg.county,
    rl.match_confidence,
    rl.match_method
FROM census_person cp
JOIN census_page pg ON cp.page_id = pg.page_id
JOIN rmtree_link rl ON cp.person_id = rl.census_person_id
WHERE rl.rmtree_person_id = 1315  -- Your RIN here
ORDER BY pg.census_year;
```

### Find unlinked census records
```sql
SELECT cp.*, pg.census_year, pg.county
FROM census_person cp
JOIN census_page pg ON cp.page_id = pg.page_id
LEFT JOIN rmtree_link rl ON cp.person_id = rl.census_person_id
WHERE rl.link_id IS NULL
ORDER BY pg.census_year, cp.surname;
```

### Get extraction statistics
```sql
SELECT
    pg.census_year,
    pg.state,
    COUNT(DISTINCT pg.page_id) as pages,
    COUNT(cp.person_id) as persons,
    COUNT(rl.link_id) as linked
FROM census_page pg
LEFT JOIN census_person cp ON pg.page_id = cp.page_id
LEFT JOIN rmtree_link rl ON cp.person_id = rl.census_person_id
GROUP BY pg.census_year, pg.state
ORDER BY pg.census_year, pg.state;
```

---

## The rmtree_link in Detail

This table deserves special attention because it's the **key to integration**.

[DIAGRAM: An expanded entity-relationship diagram focusing on rmtree_link:

**Center: rmtree_link table (enlarged)**
Showing all columns:
- link_id (PK)
- census_person_id (FK) ───→ census_person.person_id
- rmtree_person_id ─────────→ RootsMagic.PersonTable.PersonID (RIN)
- rmtree_citation_id ───────→ RootsMagic.SourceTable.SourceID
- rmtree_event_id ──────────→ RootsMagic.EventTable.EventID (optional)
- rmtree_database ──────────→ Path to .rmtree file
- match_confidence ─────────→ 0.0 to 1.0 (how sure are we?)
- match_method ─────────────→ How was this link created?
- linked_at ────────────────→ When was this link created?

**Surrounding context boxes:**

**Top-left: "One Census Record"**
census_person record showing person_id, full_name, age

**Top-right: "One RIN"**
RootsMagic PersonTable record showing PersonID, name

**Bottom-left: "One Source"**
RootsMagic SourceTable showing SourceID, citation text

**Bottom-right: "Usage Examples"**
- "Find all census records for RIN 1315"
- "Find which RIN is linked to census person 2493"
- "Find all records linked via manual GPS"

Caption: "rmtree_link connects one census_person to one RIN and one Source. You can have multiple census records linked to the same RIN (one per census year)."]

---

## Summary: What Goes Where

[DIAGRAM: A decision tree / flowchart for data storage:

**Question 1: "What kind of data is it?"**

Branch A: "Citation text (footnote, bibliography)"
→ Store in: **RootsMagic SourceTable.Fields**
→ Format: Evidence Explained style

Branch B: "Transcribed census data (names, ages, occupations)"
→ Store in: **census.db census_person + census_person_field**
→ Format: Structured fields

Branch C: "Analytical notes (GPS, research conclusions)"
→ Store in: **RootsMagic SourceTable.Comments**
→ Format: HTML (bold, italic, underline)

Branch D: "The link between census record and RIN"
→ Store in: **census.db rmtree_link**
→ Format: Foreign key references

Branch E: "Edit history and quality scores"
→ Store in: **census.db field_history, field_quality**
→ Format: Audit trail

Caption: "Each type of data has its proper home. Census.db holds structured data; RootsMagic holds citations and conclusions."]

---

## Next Steps

1. **Explore the database**: Open `~/.rmcitecraft/census.db` in DB Browser for SQLite
2. **Run sample queries**: Try the queries in this guide
3. **Extract a census page**: Use Playwright to add data
4. **Create rmtree_links**: Connect census records to your RootsMagic RINs
5. **Document with GPS**: Add proof statements for ambiguous matches

---

## Related Documentation

- [Census Extraction Database Schema Reference](../reference/CENSUS_EXTRACTION_DATABASE_SCHEMA.md) — Complete technical schema
- [Census Batch Processing Architecture](../architecture/CENSUS_BATCH_PROCESSING_ARCHITECTURE.md) — Automated extraction workflow
- [Database Patterns](../reference/DATABASE_PATTERNS.md) — SQL patterns for RootsMagic

---

*Last Updated: January 2026*
