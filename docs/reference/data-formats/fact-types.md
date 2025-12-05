---
priority: reference
topics: [database, census, findagrave, testing, ui]
---

# RootsMagic 11: FactType Reference

**Document Version:** 1.0
**Last Updated:** 2025-01-08
**Related Tables:** FactTypeTable, EventTable
**Purpose:** Complete enumeration and categorization of built-in fact types

---

## Overview

RootsMagic 11 includes **65 built-in fact types** (FactTypeID < 1000) plus support for unlimited custom fact types (FactTypeID >= 1000). Fact types define the kinds of events and attributes that can be recorded for persons and families.

### Key Statistics

- **Built-in Fact Types:** 65
- **Person Fact Types:** 52 (80%)
- **Family Fact Types:** 13 (20%)
- **Custom Fact Types:** Varies by database (48 in sample database)

---

## Fact Type Properties

Each fact type has the following properties:

| Property | Description |
|----------|-------------|
| **FactTypeID** | Unique identifier (1-999 for built-in, >=1000 for custom) |
| **Name** | Full name of the fact type |
| **Abbrev** | Abbreviated form for display |
| **GedcomTag** | GEDCOM standard tag for export/import |
| **UseValue** | Whether Description/Value field is used (0/1) |
| **UseDate** | Whether Date field is used (0/1) |
| **UsePlaceUse** | Whether Place field is used (0/1) |
| **Sentence** | Template for generating narrative text |
| **OwnerType** | 0=Person event, 1=Family event |

---

## Complete Fact Type Enumeration

### Vital Events (6 types)

Events marking major life milestones: birth, death, and related ceremonies.

| ID | Name | Abbrev | GEDCOM | Owner | V/D/P | Description |
|----|------|--------|--------|-------|-------|-------------|
| 1 | Birth | Birth | BIRT | Person | 0/1/1 | Birth date and place |
| 2 | Death | Death | DEAT | Person | 1/1/1 | Death date, place, and cause |
| 3 | Christen | Chr | CHR | Person | 0/1/1 | Christening ceremony |
| 4 | Burial | Burial | BURI | Person | 0/1/1 | Burial date and location |
| 5 | Cremation | Cremation | CREM | Person | 0/1/1 | Cremation date and location |
| 503 | Stillborn | Stillborn | EVEN | Person | 0/1/1 | Stillborn birth |

**Notes:**
- Birth and Death are the most critical vital events
- Death.Value typically contains cause of death
- Burial/Cremation are separate from Death event

---

### Religious Events (9 types)

Religious ceremonies and ordinances.

| ID | Name | Abbrev | GEDCOM | Owner | V/D/P | Description |
|----|------|--------|--------|-------|-------|-------------|
| 6 | Adoption | Adoption | ADOP | Person | 0/1/1 | Adoption date and place |
| 7 | Baptism | Baptism | BAPM | Person | 0/1/1 | Baptism ceremony |
| 8 | Bar Mitzvah | Bar Mitzvah | BARM | Person | 0/1/1 | Jewish coming of age (male) |
| 9 | Bas Mitzvah | Bas Mitzvah | BASM | Person | 0/1/1 | Jewish coming of age (female) |
| 10 | Blessing | Blessing | BLES | Person | 0/1/1 | Religious blessing |
| 11 | Christen (adult) | Chr (adult) | CHRA | Person | 0/1/1 | Adult christening |
| 12 | Confirmation | Confirmation | CONF | Person | 0/1/1 | Confirmation ceremony |
| 13 | First communion | First comm | FCOM | Person | 0/1/1 | First communion |
| 14 | Ordination | Ordination | ORDN | Person | 0/1/1 | Religious ordination |

**Notes:**
- Adoption (6) is categorized here but may also be legal
- Gender-specific events: Bar Mitzvah (male), Bas Mitzvah (female)

---

### Migration (3 types)

Events related to geographic relocation and citizenship.

| ID | Name | Abbrev | GEDCOM | Owner | V/D/P | Description |
|----|------|--------|--------|-------|-------|-------------|
| 15 | Naturalization | Naturalization | NATU | Person | 0/1/1 | Citizenship naturalization |
| 16 | Emigration | Emigration | EMIG | Person | 0/1/1 | Departure from country |
| 17 | Immigration | Immigration | IMMI | Person | 0/1/1 | Arrival in new country |

**Notes:**
- Emigration = leaving a country
- Immigration = entering a country
- Both can have dates and places

---

### Life Events (3 types)

Regular life events and residence records.

| ID | Name | Abbrev | GEDCOM | Owner | V/D/P | Description |
|----|------|--------|--------|-------|-------|-------------|
| 18 | Census | Census | CENS | Person | 0/1/1 | Census enumeration |
| 29 | Residence | Residence | RESI | Person | 1/1/1 | Residence at a location |
| 311 | Census (family) | Census (fam) | CENS | Family | 0/1/1 | Family census record |

**Notes:**
- Census (18) is person-level, Census (311) is family-level
- Residence.Value can contain address details
- Census date typically the enumeration date, place the location

---

### Education & Career (5 types)

Educational achievements and professional activities.

| ID | Name | Abbrev | GEDCOM | Owner | V/D/P | Description |
|----|------|--------|--------|-------|-------|-------------|
| 21 | Graduation | Graduation | GRAD | Person | 0/1/1 | Graduation from institution |
| 22 | Retirement | Retirement | RETI | Person | 0/1/1 | Retirement date |
| 24 | Education | Education | EDUC | Person | 1/1/1 | Educational background |
| 26 | Occupation | Occupation | OCCU | Person | 1/1/1 | Profession or occupation |
| 500 | Degree | Degree | EVEN | Person | 1/1/1 | Academic degree earned |

**Notes:**
- Occupation.Value contains job title/description
- Education.Value contains school or institution name
- Degree.Value contains degree type (BA, MD, PhD, etc.)

---

### Military (1 type)

Military service events.

| ID | Name | Abbrev | GEDCOM | Owner | V/D/P | Description |
|----|------|--------|--------|-------|-------|-------------|
| 501 | Military | Military | EVEN | Person | 1/1/1 | Military service |

**Notes:**
- Value typically contains service branch, rank, or unit
- Custom fact types often used for specific wars/conflicts
- Sample database has custom types for WWI, WWII, Civil War

---

### Legal & Property (5 types)

Legal documents and property ownership.

| ID | Name | Abbrev | GEDCOM | Owner | V/D/P | Description |
|----|------|--------|--------|-------|-------|-------------|
| 19 | Probate | Probate | PROB | Person | 1/1/1 | Estate probate |
| 20 | Will | Will | WILL | Person | 1/1/1 | Will created/signed |
| 27 | Property | Property | PROP | Person | 1/1/1 | Property ownership |
| 36 | Caste | Caste | CAST | Person | 1/1/1 | Social caste |
| 37 | Title (Nobility) | Title | TITL | Person | 1/1/1 | Noble title |

**Notes:**
- Will.Value often contains document type (will, codicil, etc.)
- Property.Value contains property description or value
- Probate.Value may contain court or case information

---

### Identifiers (4 types)

Identification numbers and reference codes.

| ID | Name | Abbrev | GEDCOM | Owner | V/D/P | Description |
|----|------|--------|--------|-------|-------|-------------|
| 30 | Soc Sec No | SSN | SSN | Person | 1/0/0 | Social Security Number |
| 34 | Ancestral File Number | AFN | AFN | Person | 1/0/0 | LDS Ancestral File number |
| 35 | Reference No | Ref # | REFN | Person | 1/0/0 | User-defined reference |
| 901 | DNA test | DNA | _DNA | Person | 0/1/0 | DNA test information |

**Notes:**
- SSN, AFN, Ref# have no date or place (identifiers only)
- DNA test (901) has date but no place
- GEDCOM tag "_DNA" is non-standard (underscore prefix)

---

### LDS Ordinances (6 types)

Latter-day Saints (Mormon) religious ordinances.

| ID | Name | Abbrev | GEDCOM | Owner | V/D/P | Description |
|----|------|--------|--------|-------|-------|-------------|
| 31 | LDS Baptism | LDS Bapt | BAPL | Person | 0/1/1 | LDS baptism |
| 32 | LDS Endowment | LDS Endow | ENDL | Person | 0/1/1 | LDS endowment ceremony |
| 33 | LDS Seal to parents | LDS SealPar | SLGC | Person | 0/1/1 | Sealing to parents |
| 38 | LDS Confirmation | LDS Conf | CONL | Person | 0/1/1 | LDS confirmation |
| 39 | LDS Initiatory | LDS Init | WAC | Person | 0/1/1 | LDS initiatory ordinance |
| 309 | LDS Seal to spouse | LDS SealSp | SLGS | Family | 0/1/1 | Sealing to spouse |

**Notes:**
- Seal to spouse (309) is family-level, others are person-level
- LDS-specific religious ordinances
- May be performed posthumously (proxy ordinances)

---

### Family Events (10 types)

Events involving couples and family units.

| ID | Name | Abbrev | GEDCOM | Owner | V/D/P | Description |
|----|------|--------|--------|-------|-------|-------------|
| 300 | Marriage | Marriage | MARR | Family | 0/1/1 | Marriage ceremony |
| 301 | Annulment | Annulment | ANUL | Family | 0/1/1 | Marriage annulment |
| 302 | Divorce | Divorce | DIV | Family | 0/1/1 | Divorce decree |
| 303 | Divorce filed | Div. filed | DIVF | Family | 0/1/1 | Divorce filing |
| 304 | Engagement | Engagement | ENGA | Family | 0/1/1 | Engagement |
| 305 | Marriage Bann | Marr Bann | MARB | Family | 0/1/1 | Marriage banns published |
| 306 | Marriage Contract | Marr Contract | MARC | Family | 0/1/1 | Marriage contract signed |
| 307 | Marriage License | Marr Lic | MARL | Family | 0/1/1 | Marriage license issued |
| 308 | Marriage Settlement | Marr Settlement | MARS | Family | 0/1/1 | Marriage settlement |
| 310 | Residence (family) | Residence (fam) | RESI | Family | 1/1/1 | Family residence |

**Notes:**
- All family events have OwnerType = 1 (Family)
- Marriage sequence: Engagement → Bann → License → Marriage
- Divorce sequence: Filed → Decree
- Residence (310) is family-level vs. person-level Residence (29)

---

### Other (13 types)

Miscellaneous and general-purpose fact types.

| ID | Name | Abbrev | GEDCOM | Owner | V/D/P | Description |
|----|------|--------|--------|-------|-------|-------------|
| 23 | Description | Description | DSCR | Person | 1/1/1 | Physical description |
| 25 | Nationality | Nationality | NATI | Person | 1/1/1 | Nationality |
| 28 | Religion | Religion | RELI | Person | 1/1/1 | Religious affiliation |
| 502 | Mission | Mission | EVEN | Person | 1/1/1 | Mission service |
| 504 | Illness | Illness | EVEN | Person | 1/1/1 | Illness or health event |
| 505 | Living | Living | EVEN | Person | 0/1/1 | Living status marker |
| 507 | Election | Elected | EVEN | Person | 1/1/1 | Election to office |
| 508 | Excommunication | Excomm | EVEN | Person | 0/1/1 | Excommunication |
| 509 | Namesake | Namesake | EVEN | Person | 1/1/1 | Named after someone |
| 510 | Separation | Separation | EVEN | Family | 0/1/1 | Marital separation |
| 900 | Alternate name | Alt. Name | EVEN | Person | 0/1/0 | Alternate name |
| 902 | Association | Association | EVEN | Person | 1/1/1 | Personal association |
| 999 | Miscellaneous | Misc | EVEN | Person | 1/1/1 | General purpose fact |

**Notes:**
- Many use GEDCOM tag "EVEN" (generic event)
- Miscellaneous (999) is catch-all for undefined events
- Alternate name (900) has no place field

---

## Usage Frequency (Sample Database)

Based on the Iiams.rmtree database with 11,571 persons:

| Rank | ID | Fact Type | Count | % of Persons |
|------|-----|-----------|-------|--------------|
| 1 | 1 | Birth | 10,474 | 90.5% |
| 2 | 2 | Death | 7,882 | 68.1% |
| 3 | 300 | Marriage | 4,034 | 34.9% |
| 4 | 18 | Census | 3,923 | 33.9% |
| 5 | 30 | Soc Sec No | 936 | 8.1% |
| 6 | 26 | Occupation | 473 | 4.1% |
| 7 | 4 | Burial | 326 | 2.8% |
| 8 | 302 | Divorce | 247 | 2.1% |
| 9 | 29 | Residence | 110 | 1.0% |
| 10 | 27 | Property | 93 | 0.8% |

**Key Observations:**
- Birth (90.5%) and Death (68.1%) are most common
- Census records present for 34% of persons
- SSN recorded for recent individuals (8%)
- Most fact types used infrequently (<1%)

---

## Person vs Family Facts

### Person Facts (OwnerType = 0)

**Definition:** Events or attributes belonging to an individual person

**Storage:** EventTable with OwnerType=0, OwnerID=PersonID

**Examples:**
- Birth, Death, Burial
- Occupation, Education
- Census, Residence
- SSN, DNA test

**Count:** 52 built-in types

---

### Family Facts (OwnerType = 1)

**Definition:** Events or attributes belonging to a couple/family unit

**Storage:** EventTable with OwnerType=1, OwnerID=FamilyID

**Examples:**
- Marriage, Divorce, Engagement
- Marriage License, Bann, Contract
- Family Residence, Family Census
- Separation, Annulment

**Count:** 13 built-in types

**Note:** Family facts link to FamilyTable, which connects Father and Mother

---

## Field Usage Patterns

### V/D/P Notation

The "V/D/P" notation indicates which fields are used:
- **V** (UseValue): Description/Value field (0=not used, 1=used)
- **D** (UseDate): Date field (0=not used, 1=used)
- **P** (UsePlace): Place field (0=not used, 1=used)

### Common Patterns

**Pattern: 0/1/1** (Most common)
- Date and place, no description
- Examples: Birth, Baptism, Marriage, Burial
- Clean events with date/place only

**Pattern: 1/1/1**
- Date, place, AND description
- Examples: Death (cause), Occupation (job), Property (value)
- Rich events with additional detail

**Pattern: 1/0/0**
- Value only, no date/place
- Examples: SSN, AFN, Ref#
- Identifiers and reference numbers

**Pattern: 0/1/0**
- Date only (rare)
- Examples: DNA test
- Time-stamped but not location-specific

---

## GEDCOM Mappings

### Standard GEDCOM Tags

Most fact types map to standard GEDCOM 5.5.1 tags:

| GEDCOM Tag | RootsMagic Fact Types |
|------------|-----------------------|
| BIRT | Birth (1) |
| DEAT | Death (2) |
| MARR | Marriage (300) |
| DIV | Divorce (302) |
| CENS | Census (18), Census family (311) |
| OCCU | Occupation (26) |
| RESI | Residence (29), Residence family (310) |
| BURI | Burial (4) |
| BAPM | Baptism (7) |
| CONF | Confirmation (12) |

### Generic GEDCOM Tag (EVEN)

The tag **EVEN** (generic event) is used for:
- Custom events (500-999 range)
- Miscellaneous events without specific tags
- Examples: Degree (500), Military (501), Illness (504), Misc (999)

### Non-Standard Tags

- **_DNA** - DNA test (underscore prefix indicates vendor extension)
- **SSN** - Social Security Number (RootsMagic-specific)
- **WAC** - LDS Initiatory (LDS-specific)

---

## Custom Fact Types

### FactTypeID >= 1000

Users can create unlimited custom fact types with IDs starting at 1000.

**Sample Database Custom Types:**
- 1000: Obituary
- 1016: War Unit
- 1021: WWI Draft Registration
- 1022: News Article
- 1024: WWII Old Man's Draft
- 1025: WWII Primary Draft
- And 42 others...

**Custom types typically:**
- Have UseValue=1, UseDate=1, UsePlace=1 (full featured)
- Use GEDCOM tag "EVEN"
- Have custom sentence templates
- Are user-defined for specific research needs

---

## Querying Fact Types

### Get All Events for a Person

```sql
SELECT
    ft.Name as FactType,
    e.Date,
    e.Details,
    p.Name as Place
FROM EventTable e
JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
LEFT JOIN PlaceTable p ON e.PlaceID = p.PlaceID
WHERE e.OwnerType = 0  -- Person
  AND e.OwnerID = ?     -- PersonID
ORDER BY e.SortDate;
```

### Get All Family Events

```sql
SELECT
    ft.Name as FactType,
    e.Date,
    f.FatherID,
    f.MotherID
FROM EventTable e
JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
JOIN FamilyTable f ON e.OwnerID = f.FamilyID
WHERE e.OwnerType = 1  -- Family
  AND e.OwnerID = ?     -- FamilyID
ORDER BY e.SortDate;
```

### Get Vital Events Only

```sql
SELECT
    p.PersonID,
    n.Surname,
    n.Given,
    ft.Name,
    e.Date
FROM PersonTable p
JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
JOIN EventTable e ON p.PersonID = e.OwnerID
JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
WHERE e.EventType IN (1, 2, 3, 4, 5)  -- Birth, Death, Christen, Burial, Cremation
ORDER BY p.PersonID, e.SortDate;
```

### Count Events by Type

```sql
SELECT
    ft.FactTypeID,
    ft.Name,
    COUNT(*) as EventCount
FROM EventTable e
JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
GROUP BY ft.FactTypeID, ft.Name
ORDER BY EventCount DESC;
```

---

## Notes for AI Agents

1. **FactTypeID < 1000** = built-in types, **>= 1000** = custom user types

2. **OwnerType determines table join:**
   - 0 = Person → JOIN PersonTable
   - 1 = Family → JOIN FamilyTable

3. **UseValue/UseDate/UsePlace flags** indicate which fields are meaningful

4. **GEDCOM tag "EVEN"** is generic - check FactType name for specifics

5. **Vital events (1, 2, 300)** should be prioritized in biographies

6. **Family events** require both spouses for complete narrative

7. **LDS ordinances** (31-33, 38-39, 309) are religion-specific

8. **Identifiers** (30, 34, 35) have no dates - don't expect Date field

9. **Custom types vary by database** - query FactTypeTable for each database

10. **Sentence templates** (FactTypeTable.Sentence) define narrative generation

---

## Related Documentation

- **RM11_Schema_Reference.md** - FactTypeTable and EventTable schemas
- **RM11_Sentence_Templates.md** - Sentence template language for narratives
- **RM11_Date_Format.md** - Date field encoding
- **RM11_Data_Quality_Rules.md** - Validation rules for events

---

## Summary

RootsMagic provides **65 built-in fact types** organized into 11 functional categories:

1. **Vital Events** (6) - Birth, death, burial
2. **Religious Events** (9) - Baptism, confirmation, etc.
3. **Migration** (3) - Immigration, emigration, naturalization
4. **Life Events** (3) - Census, residence
5. **Education & Career** (5) - Occupation, graduation, degree
6. **Military** (1) - Military service
7. **Legal & Property** (5) - Will, probate, property
8. **Identifiers** (4) - SSN, reference numbers, DNA
9. **LDS Ordinances** (6) - Mormon religious ceremonies
10. **Family Events** (10) - Marriage, divorce, engagement
11. **Other** (13) - Miscellaneous and general purpose

The system supports **unlimited custom fact types** (ID >= 1000) for specialized research needs. Fact types define whether events are person-level or family-level, which fields are used (value/date/place), and how narratives are generated via sentence templates.

---

**End of Document**
