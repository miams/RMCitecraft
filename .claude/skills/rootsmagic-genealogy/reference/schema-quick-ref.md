# RootsMagic Database Schema Quick Reference

## Core Tables

### PersonTable
Primary table for individuals.

| Column | Type | Description |
|--------|------|-------------|
| PersonID | INTEGER | Primary key (RIN) |
| UniqueID | TEXT | UUID for syncing |
| Sex | INTEGER | 0=Male, 1=Female, 2=Unknown |
| ParentID | INTEGER | Link to parents' FamilyID |
| SpouseID | INTEGER | Link to primary spouse's FamilyID |
| Color | INTEGER | User-defined color coding |
| Note | BLOB | Person notes (HTML) |
| Living | INTEGER | 0=Deceased, 1=Living |

### NameTable
Names for each person (supports alternate names).

| Column | Type | Description |
|--------|------|-------------|
| NameID | INTEGER | Primary key |
| OwnerID | INTEGER | → PersonTable.PersonID |
| Surname | TEXT | Last name (RMNOCASE collation) |
| Given | TEXT | First/middle names (RMNOCASE) |
| Prefix | TEXT | Dr., Rev., etc. |
| Suffix | TEXT | Jr., III, etc. |
| Nickname | TEXT | Nicknames |
| IsPrimary | INTEGER | 1=Primary name, 0=Alternate |
| NameType | INTEGER | Name type code |
| SortDate | BIGINT | For sorting |

### FamilyTable
Marriage/partnership records.

| Column | Type | Description |
|--------|------|-------------|
| FamilyID | INTEGER | Primary key |
| FatherID | INTEGER | → PersonTable.PersonID (husband) |
| MotherID | INTEGER | → PersonTable.PersonID (wife) |
| ChildID | INTEGER | Deprecated, use ChildTable |
| HusbOrder | INTEGER | Marriage order for husband |
| WifeOrder | INTEGER | Marriage order for wife |
| Note | BLOB | Family notes (HTML) |

### ChildTable
Parent-child relationships.

| Column | Type | Description |
|--------|------|-------------|
| RecID | INTEGER | Primary key |
| ChildID | INTEGER | → PersonTable.PersonID |
| FamilyID | INTEGER | → FamilyTable.FamilyID |
| RelFather | INTEGER | Relationship to father (0=Birth, 1=Adopted, etc.) |
| RelMother | INTEGER | Relationship to mother |
| ChildOrder | INTEGER | Birth order |

### EventTable
Life events (births, deaths, marriages, census, etc.).

| Column | Type | Description |
|--------|------|-------------|
| EventID | INTEGER | Primary key |
| OwnerType | INTEGER | **0=Person, 1=Family** |
| OwnerID | INTEGER | → PersonID or FamilyID (based on OwnerType) |
| EventType | INTEGER | See Event Type codes below |
| Date | TEXT | RootsMagic date format |
| PlaceID | INTEGER | → PlaceTable.PlaceID |
| SiteID | INTEGER | → PlaceTable (specific site) |
| Note | BLOB | Event notes (HTML) |
| SortDate | BIGINT | For chronological sorting |

**Critical:** For OwnerType=1 (Family events like marriage), OwnerID is a FamilyID, not PersonID!

### SourceTable
Source records.

| Column | Type | Description |
|--------|------|-------------|
| SourceID | INTEGER | Primary key |
| Name | TEXT | Source name/title |
| TemplateID | INTEGER | 0=Free-form, >0=Template-based |
| Fields | BLOB | XML with Footnote/ShortFootnote/Bibliography |
| Comments | TEXT | Researcher notes (store GPS here) |
| RefNumber | TEXT | User reference number |

### CitationTable
Links sources to events/persons.

| Column | Type | Description |
|--------|------|-------------|
| CitationID | INTEGER | Primary key |
| SourceID | INTEGER | → SourceTable.SourceID |
| CitationName | TEXT | Citation identifier |
| Fields | BLOB | Citation-specific data (XML) |
| Comments | TEXT | Citation notes |
| ActualText | TEXT | Actual text quoted |

### PlaceTable
Location records.

| Column | Type | Description |
|--------|------|-------------|
| PlaceID | INTEGER | Primary key |
| Name | TEXT | Full place name |
| Reverse | TEXT | Reversed for sorting (County, State) |
| Latitude | REAL | GPS latitude |
| Longitude | REAL | GPS longitude |

### MediaTable
Media file references.

| Column | Type | Description |
|--------|------|-------------|
| MediaID | INTEGER | Primary key |
| MediaPath | TEXT | File path (may have `?/` or `?\` prefix) |
| MediaType | INTEGER | File type |
| Caption | TEXT | Description |

## Event Type Codes

| Code | Event |
|------|-------|
| 1 | Birth |
| 2 | Death |
| 3 | Burial |
| 4 | Cremation |
| 5 | Baptism |
| 7 | Residence |
| 18 | Census |
| 19 | Occupation |
| 300 | Marriage |
| 301 | Divorce |
| 302 | Annulment |

## RootsMagic Date Format

Dates are stored as strings with this format:
```
D.+YYYYMMDD..+00000000..
```

| Position | Content |
|----------|---------|
| 0-1 | "D." prefix |
| 2 | Modifier (+, -, ~, etc.) |
| 3-6 | Year (4 digits) |
| 7-8 | Month (01-12) |
| 9-10 | Day (01-31) |

**Parsing year:**
```python
birth_year = date_string[3:7] if date_string and len(date_string) >= 7 else None
```

## Census.db Schema (Sidecar Database)

### census_page
| Column | Type | Description |
|--------|------|-------------|
| page_id | INTEGER | Primary key |
| census_year | INTEGER | 1790, 1800, etc. |
| state | TEXT | State name |
| county | TEXT | County name |
| township_city | TEXT | Township or city |
| enumeration_district | TEXT | ED (1880+) |
| page_number | TEXT | Page number |
| sheet_number | TEXT | Sheet number (1880-1940) |

### census_person
| Column | Type | Description |
|--------|------|-------------|
| person_id | INTEGER | Primary key |
| page_id | INTEGER | → census_page |
| line_number | INTEGER | Line on page |
| full_name | TEXT | Full name |
| given_name | TEXT | First name |
| surname | TEXT | Last name |
| relationship_to_head | TEXT | Head, Wife, Son, etc. |
| sex | TEXT | M/F |
| age | INTEGER | Age at census |
| occupation | TEXT | Occupation |

### census_person_field (EAV Pattern)
| Column | Type | Description |
|--------|------|-------------|
| field_id | INTEGER | Primary key |
| person_id | INTEGER | → census_person |
| field_name | TEXT | Field name (e.g., "slaves") |
| field_value | TEXT | Field value |

### rmtree_link (Bridge Table)
| Column | Type | Description |
|--------|------|-------------|
| link_id | INTEGER | Primary key |
| census_person_id | INTEGER | → census_person |
| rmtree_person_id | INTEGER | → RootsMagic PersonID (RIN) |
| rmtree_citation_id | INTEGER | → RootsMagic SourceID |
| match_confidence | REAL | 0.0-1.0 |
| match_method | TEXT | How match was made |
| linked_at | TEXT | ISO timestamp |

## RMNOCASE Collation

Many text columns use RMNOCASE collation for case-insensitive sorting.

**Never use raw sqlite3** - it cannot load the ICU extension required for RMNOCASE.

```python
# CORRECT
from rmcitecraft.database.connection import connect_rmtree
conn = connect_rmtree('data/Iiams.rmtree')

# WRONG - will fail on RMNOCASE columns
import sqlite3
conn = sqlite3.connect('data/Iiams.rmtree')
```
