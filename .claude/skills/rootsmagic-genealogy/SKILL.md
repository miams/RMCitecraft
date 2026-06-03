---
name: rootsmagic-genealogy
description: >
  Query and analyze RootsMagic genealogy database (.rmtree files).
  Search for persons by name, date, or place. Explore family relationships
  (parents, children, spouses, siblings). Match census records to RIN candidates.
  Generate GPS (Genealogical Proof Statement) documentation. Format citations
  per Evidence Explained standards. Query census.db sidecar database for
  structured census data. Use when user asks about ancestors, family trees,
  census records, genealogical research, RINs, person identification, or
  RootsMagic database queries.
allowed-tools:
  - Read
  - Grep
  - Bash(uv:*, python:*)
  - Glob
---

# RootsMagic Genealogy Skill

Query, analyze, and document genealogical research in RootsMagic databases.

## Critical: Database Safety Rules

1. **Always use `connect_rmtree()`** - Never use raw `sqlite3.connect()`
2. **Default to read-only** - Pass `read_only=False` only when writing
3. **Never use sqlite3 CLI** - It cannot load the ICU extension
4. **Get user approval before writes** - All database modifications require consent

```python
from rmcitecraft.database.connection import connect_rmtree

# Read operations (default)
conn = connect_rmtree('data/Iiams.rmtree')

# Write operations - explicit
conn = connect_rmtree('data/Iiams.rmtree', read_only=False)
conn.commit()  # Don't forget!
conn.close()
```

## Database Locations

| Database | Path | Purpose |
|----------|------|---------|
| RootsMagic | `data/Iiams.rmtree` | Main genealogy database |
| Census.db | `~/.rmcitecraft/census.db` | Structured census extractions |
| Batch State | `~/.rmcitecraft/batch_state.db` | Processing state |

## Core Operations

### 1. Person Search

Find persons by name with surname variant support.

```python
uv run python3 << 'EOF'
from rmcitecraft.database.connection import connect_rmtree

conn = connect_rmtree('data/Iiams.rmtree')
cursor = conn.cursor()

# Search by surname (supports LIKE patterns)
cursor.execute("""
    SELECT p.PersonID as RIN, n.Given, n.Surname, p.Sex,
           (SELECT e.Date FROM EventTable e
            WHERE e.OwnerID = p.PersonID AND e.EventType = 1) as BirthDate,
           (SELECT pl.Name FROM EventTable e
            LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
            WHERE e.OwnerID = p.PersonID AND e.EventType = 1) as BirthPlace
    FROM PersonTable p
    JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
    WHERE n.Surname LIKE '%Iiams%'
    ORDER BY n.Surname, BirthDate
""")

for row in cursor.fetchall():
    rin, given, surname, sex, birth, place = row
    birth_yr = birth[3:7] if birth and len(birth) >= 7 else '?'
    sex_str = 'M' if sex == 0 else 'F' if sex == 1 else '?'
    print(f"RIN {rin}: {given} {surname} ({sex_str}) b.{birth_yr} - {place or 'Unknown'}")

conn.close()
EOF
```

**Surname variants to search:** Iiams, Ijams, Iams, Imes, Iames, Ijames, Iiames

### 2. Family Relationships

Get complete family context for a RIN.

```python
uv run python3 << 'EOF'
from rmcitecraft.database.connection import connect_rmtree

RIN = 1561  # Change this

conn = connect_rmtree('data/Iiams.rmtree')
cursor = conn.cursor()

# Basic info
cursor.execute("""
    SELECT n.Given, n.Surname,
           (SELECT e.Date FROM EventTable e WHERE e.OwnerID = ? AND e.EventType = 1) as Birth,
           (SELECT e.Date FROM EventTable e WHERE e.OwnerID = ? AND e.EventType = 2) as Death
    FROM NameTable n
    WHERE n.OwnerID = ? AND n.IsPrimary = 1
""", (RIN, RIN, RIN))
row = cursor.fetchone()
if row:
    print(f"RIN {RIN}: {row[0]} {row[1]}")
    print(f"Birth: {row[2][3:7] if row[2] else '?'}")
    print(f"Death: {row[3][3:7] if row[3] else '?'}")

# Parents
cursor.execute("""
    SELECT
        (SELECT n.Given || ' ' || n.Surname FROM NameTable n
         WHERE n.OwnerID = f.FatherID AND n.IsPrimary = 1) as Father,
        f.FatherID,
        (SELECT n.Given || ' ' || n.Surname FROM NameTable n
         WHERE n.OwnerID = f.MotherID AND n.IsPrimary = 1) as Mother,
        f.MotherID
    FROM ChildTable c
    JOIN FamilyTable f ON c.FamilyID = f.FamilyID
    WHERE c.ChildID = ?
""", (RIN,))
parents = cursor.fetchone()
if parents:
    print(f"\nParents:")
    print(f"  Father: {parents[0]} (RIN {parents[1]})")
    print(f"  Mother: {parents[2]} (RIN {parents[3]})")

# Spouses
cursor.execute("""
    SELECT
        CASE WHEN f.FatherID = ? THEN f.MotherID ELSE f.FatherID END as SpouseID,
        (SELECT n.Given || ' ' || n.Surname FROM NameTable n
         WHERE n.OwnerID = CASE WHEN f.FatherID = ? THEN f.MotherID ELSE f.FatherID END
         AND n.IsPrimary = 1) as SpouseName,
        (SELECT e.Date FROM EventTable e
         WHERE e.OwnerID = f.FamilyID AND e.OwnerType = 1 AND e.EventType = 300) as MarrDate
    FROM FamilyTable f
    WHERE f.FatherID = ? OR f.MotherID = ?
""", (RIN, RIN, RIN, RIN))
spouses = cursor.fetchall()
if spouses:
    print(f"\nSpouses:")
    for sp in spouses:
        marr_yr = sp[2][3:7] if sp[2] and len(sp[2]) >= 7 else '?'
        print(f"  {sp[1]} (RIN {sp[0]}) m.{marr_yr}")

# Children
cursor.execute("""
    SELECT c.ChildID, n.Given, n.Surname, p.Sex,
           (SELECT e.Date FROM EventTable e WHERE e.OwnerID = c.ChildID AND e.EventType = 1) as Birth
    FROM FamilyTable f
    JOIN ChildTable c ON c.FamilyID = f.FamilyID
    JOIN PersonTable p ON p.PersonID = c.ChildID
    JOIN NameTable n ON n.OwnerID = c.ChildID AND n.IsPrimary = 1
    WHERE f.FatherID = ? OR f.MotherID = ?
    ORDER BY Birth
""", (RIN, RIN))
children = cursor.fetchall()
if children:
    print(f"\nChildren ({len(children)}):")
    for ch in children:
        birth_yr = ch[4][3:7] if ch[4] and len(ch[4]) >= 7 else '?'
        sex_str = 'M' if ch[3] == 0 else 'F' if ch[3] == 1 else '?'
        print(f"  {ch[1]} {ch[2]} (RIN {ch[0]}, {sex_str}) b.{birth_yr}")

conn.close()
EOF
```

### 3. Census Record Matching

Find RIN candidates for a census record based on:
- Name similarity
- Birth year range (calculated from census age)
- Geographic proximity
- Household composition

See `scripts/census_match.py` for the full matching algorithm.

### 4. GPS Documentation

Generate Genealogical Proof Statements for RootsMagic Comments fields.

**Supported HTML formatting:** `<b>bold</b>`, `<u>underline</u>`, `<i>italic</i>`

```python
gps_template = """<b>Genealogical Proof Statement</b>

<u>Conclusion:</u> [State the identification clearly]

<u>Evidence:</u>

1. <b>[Primary source type]:</b> [Description and what it proves]

2. <b>[Supporting source]:</b> [Description and relevance]

3. <b>[Additional evidence]:</b> [Corroborating details]

<u>Limitations:</u> [Any caveats, gaps, or uncertainties]

<i>Analysis completed [Month Year].</i>"""
```

**Storage locations:**
- Source-level GPS: `SourceTable.Comments`
- Person-level notes: `PersonTable.Note`

### 5. Census.db Integration

Query structured census data from the sidecar database.

```python
import sqlite3

census_conn = sqlite3.connect('/Users/miams/.rmcitecraft/census.db')
cursor = census_conn.cursor()

# Find census records for a surname
cursor.execute("""
    SELECT cp.person_id, cp.full_name, pg.census_year, pg.state, pg.county,
           rl.rmtree_person_id as RIN
    FROM census_person cp
    JOIN census_page pg ON cp.page_id = pg.page_id
    LEFT JOIN rmtree_link rl ON cp.person_id = rl.census_person_id
    WHERE cp.surname LIKE '%Iiams%'
    ORDER BY pg.census_year
""")

# Create rmtree_link (connect census record to RIN)
cursor.execute("""
    INSERT INTO rmtree_link
    (census_person_id, rmtree_person_id, rmtree_citation_id,
     match_confidence, match_method, linked_at)
    VALUES (?, ?, ?, ?, 'manual_analysis', datetime('now'))
""", (census_person_id, rin, source_id, confidence))
census_conn.commit()
```

## Database Schema Quick Reference

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| PersonTable | People | PersonID (RIN), Sex, Note |
| NameTable | Names | OwnerID→PersonID, Given, Surname, IsPrimary |
| FamilyTable | Marriages | FamilyID, FatherID, MotherID |
| ChildTable | Parent-child links | ChildID, FamilyID |
| EventTable | Life events | OwnerID, OwnerType, EventType, Date, PlaceID |
| SourceTable | Sources | SourceID, Name, Comments, Fields (BLOB) |
| PlaceTable | Places | PlaceID, Name |

**Event Types:** 1=Birth, 2=Death, 300=Marriage, 18=Census

**OwnerType in EventTable:** 0=Person, 1=Family

**Date format:** `D.+YYYYMMDD..+00000000..` (year at positions 3-7)

## Evidence Explained Citation Standards

### Footnote Format (1900-1950)
```
1900 U.S. census, Noble County, Ohio, population schedule, Olive Township,
enumeration district (ED) 95, sheet 3B, family 57, Ella Ijams; imaged,
"1900 United States Federal Census," FamilySearch (https://familysearch.org/ark:/...).
```

### Short Footnote
```
1900 U.S. census, Noble Co., Oh., pop. sch., Olive Township, E.D. 95, sheet 3B, Ella Ijams.
```

### Census Year Variations

| Years | Key Elements |
|-------|--------------|
| 1790-1840 | Head of household only, tally columns |
| 1850-1870 | All names, no ED, dwelling/family numbers |
| 1880+ | ED introduced, sheet numbers |
| 1950 | Uses "stamp" instead of "sheet" |

## Detailed Reference

For complete documentation, see:
- `reference/schema-quick-ref.md` - Full table schemas
- `reference/query-patterns.md` - Advanced SQL patterns
- `docs/reference/DATABASE_PATTERNS.md` - Project database guide
- `docs/reference/CENSUS_EXTRACTION_DATABASE_SCHEMA.md` - Census.db schema

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/person_search.py` | Search persons with filters |
| `scripts/family_tree.py` | Generate family relationships |
| `scripts/census_match.py` | Match census records to RINs |
