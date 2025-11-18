# RootsMagic 11: Query Performance Patterns

**Document Version:** 1.0
**Last Updated:** 2025-01-08
**Purpose:** Optimized SQL query patterns for common genealogical operations

---

## Overview

This document provides efficient, tested SQL query patterns for common RootsMagic database operations. All queries use proper indexes and JOIN strategies for optimal performance.

### Database Requirements

**RMNOCASE Collation:**
All queries require the ICU extension for RMNOCASE collation support.

```python
import sqlite3

conn = sqlite3.connect('data/Iiams.rmtree')
conn.enable_load_extension(True)
conn.load_extension('./sqlite-extension/icu.dylib')
conn.execute("SELECT icu_load_collation('en_US@colStrength=primary;caseLevel=off;normalization=on','RMNOCASE')")
conn.enable_load_extension(False)
```

---

## Person Queries

### Pattern 1: Get Person with Primary Name

```sql
SELECT
    p.PersonID,
    n.Surname,
    n.Given,
    n.Prefix,
    n.Suffix,
    n.BirthYear,
    n.DeathYear,
    p.Sex
FROM PersonTable p
JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
WHERE p.PersonID = ?;
```

**Indexes Used:** PersonTable(PersonID), NameTable(OwnerID, IsPrimary)

---

### Pattern 2: Search by Name

```sql
-- Exact surname match
SELECT
    p.PersonID,
    n.Surname,
    n.Given,
    n.BirthYear,
    n.DeathYear
FROM PersonTable p
JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
WHERE n.Surname = ?
ORDER BY n.Surname, n.Given;

-- Phonetic surname match (Metaphone)
SELECT
    p.PersonID,
    n.Surname,
    n.Given,
    n.BirthYear,
    n.DeathYear
FROM PersonTable p
JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
WHERE n.SurnameMP = ?
ORDER BY n.Surname, n.Given;
```

**Indexes Used:** NameTable(Surname), NameTable(SurnameMP)

---

### Pattern 3: Get Person's Parents

```sql
SELECT
    father.PersonID as FatherID,
    fn.Surname as FatherSurname,
    fn.Given as FatherGiven,
    mother.PersonID as MotherID,
    mn.Surname as MotherSurname,
    mn.Given as MotherGiven
FROM PersonTable p
LEFT JOIN ChildTable ct ON p.PersonID = ct.ChildID
LEFT JOIN FamilyTable f ON ct.FamilyID = f.FamilyID
LEFT JOIN PersonTable father ON f.FatherID = father.PersonID
LEFT JOIN NameTable fn ON father.PersonID = fn.OwnerID AND fn.IsPrimary = 1
LEFT JOIN PersonTable mother ON f.MotherID = mother.PersonID
LEFT JOIN NameTable mn ON mother.PersonID = mn.OwnerID AND mn.IsPrimary = 1
WHERE p.PersonID = ?
LIMIT 1;
```

**Note:** LIMIT 1 because multiple families are rare but possible

---

### Pattern 4: Get Person's Children

```sql
SELECT
    child.PersonID,
    cn.Surname,
    cn.Given,
    cn.BirthYear,
    cn.DeathYear,
    child.Sex
FROM PersonTable p
JOIN FamilyTable f ON p.PersonID = f.FatherID OR p.PersonID = f.MotherID
JOIN ChildTable ct ON f.FamilyID = ct.FamilyID
JOIN PersonTable child ON ct.ChildID = child.PersonID
JOIN NameTable cn ON child.PersonID = cn.OwnerID AND cn.IsPrimary = 1
WHERE p.PersonID = ?
ORDER BY cn.BirthYear, cn.Surname, cn.Given;
```

---

## Event Queries

### Pattern 5: Get All Events for Person (Timeline)

```sql
SELECT
    e.EventID,
    ft.Name as EventType,
    ft.FactTypeID,
    e.Date,
    e.SortDate,
    e.Details,
    pl.Name as Place,
    e.IsPrivate,
    e.Proof
FROM EventTable e
JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
WHERE e.OwnerType = 0
  AND e.OwnerID = ?
ORDER BY e.SortDate, ft.FactTypeID;
```

**Indexes Used:** EventTable(OwnerID, OwnerType), idxOwnerDate

---

### Pattern 6: Get Vital Events Only

```sql
SELECT
    e.EventID,
    ft.Name as EventType,
    e.Date,
    e.Details,
    pl.Name as Place
FROM EventTable e
JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
WHERE e.OwnerType = 0
  AND e.OwnerID = ?
  AND e.EventType IN (1, 2, 3, 4, 300)  -- Birth, Death, Christen, Burial, Marriage
ORDER BY e.SortDate;
```

---

## Family Queries

### Pattern 7: Get Person's Spouses

```sql
SELECT
    spouse.PersonID,
    sn.Surname,
    sn.Given,
    sn.BirthYear,
    sn.DeathYear,
    f.FamilyID,
    marriage.Date as MarriageDate
FROM PersonTable p
JOIN FamilyTable f ON (
    (p.PersonID = f.FatherID AND spouse.PersonID = f.MotherID) OR
    (p.PersonID = f.MotherID AND spouse.PersonID = f.FatherID)
)
JOIN PersonTable spouse ON (
    spouse.PersonID = f.FatherID OR spouse.PersonID = f.MotherID
) AND spouse.PersonID != p.PersonID
JOIN NameTable sn ON spouse.PersonID = sn.OwnerID AND sn.IsPrimary = 1
LEFT JOIN EventTable marriage ON f.FamilyID = marriage.OwnerID AND marriage.EventType = 300
WHERE p.PersonID = ?
ORDER BY marriage.SortDate;
```

---

## Ancestor Queries

### Pattern 8: Get Direct Ancestors (Recursive, 10 Generations)

```sql
WITH RECURSIVE ancestors(PersonID, Generation, Relationship) AS (
    -- Base case: starting person
    SELECT PersonID, 0 as Generation, 'Self' as Relationship
    FROM PersonTable
    WHERE PersonID = ?

    UNION ALL

    -- Recursive case: parents
    SELECT
        CASE
            WHEN f.FatherID IS NOT NULL THEN f.FatherID
            ELSE f.MotherID
        END as PersonID,
        a.Generation + 1,
        CASE
            WHEN f.FatherID IS NOT NULL AND f.MotherID IS NOT NULL THEN
                CASE WHEN f.FatherID = CASE WHEN f.FatherID IS NOT NULL THEN f.FatherID ELSE f.MotherID END
                    THEN 'Father' ELSE 'Mother' END
            WHEN f.FatherID IS NOT NULL THEN 'Father'
            ELSE 'Mother'
        END
    FROM ancestors a
    JOIN ChildTable ct ON a.PersonID = ct.ChildID
    JOIN FamilyTable f ON ct.FamilyID = f.FamilyID
    WHERE a.Generation < 10
      AND (f.FatherID IS NOT NULL OR f.MotherID IS NOT NULL)
)
SELECT DISTINCT
    a.PersonID,
    n.Surname,
    n.Given,
    n.BirthYear,
    n.DeathYear,
    a.Generation,
    a.Relationship
FROM ancestors a
JOIN NameTable n ON a.PersonID = n.OwnerID AND n.IsPrimary = 1
WHERE a.Generation > 0  -- Exclude self
ORDER BY a.Generation, n.Surname, n.Given;
```

---

### Pattern 9: Get Ancestors with Spouses

```sql
-- Simplified version: Parents and grandparents with spouses
SELECT
    p.PersonID,
    n.Surname,
    n.Given,
    n.BirthYear,
    n.DeathYear,
    'Parent' as Relationship
FROM PersonTable root
JOIN ChildTable ct1 ON root.PersonID = ct1.ChildID
JOIN FamilyTable f1 ON ct1.FamilyID = f1.FamilyID
JOIN PersonTable p ON (p.PersonID = f1.FatherID OR p.PersonID = f1.MotherID)
JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
WHERE root.PersonID = ?

UNION

SELECT
    p.PersonID,
    n.Surname,
    n.Given,
    n.BirthYear,
    n.DeathYear,
    'Grandparent' as Relationship
FROM PersonTable root
JOIN ChildTable ct1 ON root.PersonID = ct1.ChildID
JOIN FamilyTable f1 ON ct1.FamilyID = f1.FamilyID
JOIN PersonTable parent ON (parent.PersonID = f1.FatherID OR parent.PersonID = f1.MotherID)
JOIN ChildTable ct2 ON parent.PersonID = ct2.ChildID
JOIN FamilyTable f2 ON ct2.FamilyID = f2.FamilyID
JOIN PersonTable p ON (p.PersonID = f2.FatherID OR p.PersonID = f2.MotherID)
JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
WHERE root.PersonID = ?

ORDER BY Relationship, Surname, Given;
```

---

## Descendant Queries

### Pattern 10: Get All Descendants (Recursive)

```sql
WITH RECURSIVE descendants(PersonID, Generation) AS (
    -- Base case
    SELECT PersonID, 0 as Generation
    FROM PersonTable
    WHERE PersonID = ?

    UNION ALL

    -- Recursive case: children
    SELECT
        ct.ChildID,
        d.Generation + 1
    FROM descendants d
    JOIN FamilyTable f ON d.PersonID = f.FatherID OR d.PersonID = f.MotherID
    JOIN ChildTable ct ON f.FamilyID = ct.FamilyID
    WHERE d.Generation < 10
)
SELECT
    d.PersonID,
    n.Surname,
    n.Given,
    n.BirthYear,
    n.DeathYear,
    d.Generation
FROM descendants d
JOIN NameTable n ON d.PersonID = n.OwnerID AND n.IsPrimary = 1
WHERE d.Generation > 0
ORDER BY d.Generation, n.Surname, n.Given;
```

---

## Source and Citation Queries

### Pattern 11: Get Citations for Event

```sql
SELECT
    c.CitationID,
    c.CitationName,
    s.SourceID,
    s.Name as SourceName,
    s.TemplateID
FROM CitationLinkTable cl
JOIN CitationTable c ON cl.CitationID = c.CitationID
JOIN SourceTable s ON c.SourceID = s.SourceID
WHERE cl.OwnerType = 2  -- Event
  AND cl.OwnerID = ?    -- EventID
ORDER BY cl.LinkID;
```

---

### Pattern 12: Get Unsourced Events

```sql
SELECT
    e.EventID,
    ft.Name as EventType,
    p.PersonID,
    n.Surname,
    n.Given,
    e.Date,
    pl.Name as Place
FROM EventTable e
JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
JOIN PersonTable p ON e.OwnerID = p.PersonID
JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
LEFT JOIN CitationLinkTable cl ON e.EventID = cl.OwnerID AND cl.OwnerType = 2
WHERE e.OwnerType = 0
  AND e.EventType IN (1, 2, 300)  -- Birth, Death, Marriage
  AND cl.LinkID IS NULL
ORDER BY n.Surname, n.Given, e.SortDate;
```

---

## Place Queries

### Pattern 13: Find Places by State/County

```sql
-- All places in Maryland
SELECT PlaceID, Name
FROM PlaceTable
WHERE Name LIKE '%Maryland, United States'
ORDER BY Name;

-- All places in Baltimore County
SELECT PlaceID, Name
FROM PlaceTable
WHERE Name LIKE '%Baltimore, Maryland, United States'
ORDER BY Name;
```

**Index Used:** Full table scan (consider name prefix for optimization)

---

## Data Quality Queries

### Pattern 14: Find People with Missing Vital Events

```sql
-- People missing birth events
SELECT
    p.PersonID,
    n.Surname,
    n.Given,
    n.BirthYear
FROM PersonTable p
JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
LEFT JOIN EventTable birth ON p.PersonID = birth.OwnerID AND birth.EventType = 1
WHERE birth.EventID IS NULL
  AND n.BirthYear IS NOT NULL  -- Should have birth info
ORDER BY n.Surname, n.Given
LIMIT 100;
```

---

### Pattern 15: Find Logical Inconsistencies

```sql
-- Death before birth
SELECT
    p.PersonID,
    n.Surname,
    n.Given,
    birth.Date as BirthDate,
    birth.SortDate as BirthSort,
    death.Date as DeathDate,
    death.SortDate as DeathSort
FROM PersonTable p
JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
JOIN EventTable birth ON p.PersonID = birth.OwnerID AND birth.EventType = 1
JOIN EventTable death ON p.PersonID = death.OwnerID AND death.EventType = 2
WHERE birth.SortDate != 9223372036854775807
  AND death.SortDate != 9223372036854775807
  AND death.SortDate < birth.SortDate;
```

---

## Performance Tips

### Tip 1: Use Indexes

**Always filter on indexed fields:**
- PersonTable: PersonID (PK)
- NameTable: OwnerID, IsPrimary, Surname, SurnameMP
- EventTable: OwnerID + OwnerType (idxOwnerID)
- EventTable: OwnerID + SortDate (idxOwnerDate)

### Tip 2: Avoid SELECT *

**Good:**
```sql
SELECT PersonID, Surname, Given FROM NameTable...
```

**Bad:**
```sql
SELECT * FROM NameTable...
```

### Tip 3: Use LEFT JOIN for Optional Data

```sql
-- Place may not exist for all events
LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
```

### Tip 4: Limit Large Result Sets

```sql
-- Add LIMIT for exploration queries
SELECT ... FROM ... LIMIT 100;
```

### Tip 5: Use EXPLAIN QUERY PLAN

```sql
EXPLAIN QUERY PLAN
SELECT ...;
```

Check that indexes are being used properly.

---

## Python Helper Functions

### Connection Helper

```python
def connect_rmtree(db_path):
    """Connect to RootsMagic database with RMNOCASE support."""
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    conn.load_extension('./sqlite-extension/icu.dylib')
    conn.execute("SELECT icu_load_collation('en_US@colStrength=primary;caseLevel=off;normalization=on','RMNOCASE')")
    conn.enable_load_extension(False)

    return conn
```

### Query Wrapper

```python
def query_person_timeline(person_id, db_path):
    """Get all events for a person."""
    conn = connect_rmtree(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            e.EventID,
            ft.Name as EventType,
            e.Date,
            e.SortDate,
            e.Details,
            pl.Name as Place
        FROM EventTable e
        JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
        LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
        WHERE e.OwnerType = 0
          AND e.OwnerID = ?
        ORDER BY e.SortDate
    """, (person_id,))

    events = cursor.fetchall()
    conn.close()

    return events
```

---

## Related Documentation

- **RM11_Schema_Reference.md** - Table structures and indexes
- **RM11_Data_Quality_Rules.md** - Validation queries
- **RM11_Timeline_Construction.md** - Timeline generation queries
- **sqlite-extension/python_example.py** - RMNOCASE setup

---

## Summary

Key query patterns for RootsMagic databases:

1. **Always use RMNOCASE collation** - Required for proper string comparisons
2. **JOIN NameTable with IsPrimary=1** - Get primary names
3. **Use indexed fields** - PersonID, OwnerID, OwnerType, SortDate
4. **Recursive CTEs for ancestors/descendants** - Efficient family tree traversal
5. **LEFT JOIN for optional data** - Places, citations may not exist
6. **Filter on OwnerType** - Critical for polymorphic tables (EventTable, etc.)
7. **Order by SortDate** - Chronological event ordering
8. **Limit result sets** - For exploration and testing
9. **Check indexes with EXPLAIN** - Verify query optimization

These patterns provide a foundation for building efficient AI agents that analyze RootsMagic databases.

---

**End of Document**
