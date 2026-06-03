# RootsMagic Query Cookbook

Common SQL patterns for genealogical research.

## Person Queries

### Find Person by Name

```sql
-- Basic name search with surname pattern
SELECT p.PersonID as RIN, n.Given, n.Surname, p.Sex,
       (SELECT e.Date FROM EventTable e
        WHERE e.OwnerID = p.PersonID AND e.EventType = 1) as BirthDate
FROM PersonTable p
JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
WHERE n.Surname LIKE '%Smith%' COLLATE RMNOCASE
ORDER BY n.Surname, n.Given;
```

### Find Person with Birth/Death Details

```sql
SELECT p.PersonID as RIN, n.Given, n.Surname,
       birth.Date as BirthDate, birth_place.Name as BirthPlace,
       death.Date as DeathDate, death_place.Name as DeathPlace
FROM PersonTable p
JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
LEFT JOIN EventTable birth ON birth.OwnerID = p.PersonID
          AND birth.OwnerType = 0 AND birth.EventType = 1
LEFT JOIN PlaceTable birth_place ON birth.PlaceID = birth_place.PlaceID
LEFT JOIN EventTable death ON death.OwnerID = p.PersonID
          AND death.OwnerType = 0 AND death.EventType = 2
LEFT JOIN PlaceTable death_place ON death.PlaceID = death_place.PlaceID
WHERE n.Surname = 'Smith' COLLATE RMNOCASE
  AND n.Given = 'John' COLLATE RMNOCASE;
```

### Find People Born in Year Range

```sql
SELECT p.PersonID as RIN, n.Given, n.Surname, n.BirthYear
FROM PersonTable p
JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
WHERE n.BirthYear BETWEEN 1850 AND 1860
ORDER BY n.BirthYear, n.Surname;
```

## Family Relationship Queries

### Get Person's Parents

```sql
SELECT
    p.PersonID as ChildRIN,
    n.Given || ' ' || n.Surname as ChildName,
    f.FatherID,
    nf.Given || ' ' || nf.Surname as FatherName,
    f.MotherID,
    nm.Given || ' ' || nm.Surname as MotherName
FROM PersonTable p
JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
JOIN ChildTable c ON c.ChildID = p.PersonID
JOIN FamilyTable f ON c.FamilyID = f.FamilyID
LEFT JOIN NameTable nf ON nf.OwnerID = f.FatherID AND nf.IsPrimary = 1
LEFT JOIN NameTable nm ON nm.OwnerID = f.MotherID AND nm.IsPrimary = 1
WHERE p.PersonID = 1561;  -- Replace with target RIN
```

### Get Person's Spouses

```sql
SELECT
    CASE WHEN f.FatherID = ? THEN f.MotherID ELSE f.FatherID END as SpouseRIN,
    (SELECT n.Given || ' ' || n.Surname FROM NameTable n
     WHERE n.OwnerID = CASE WHEN f.FatherID = ? THEN f.MotherID ELSE f.FatherID END
     AND n.IsPrimary = 1) as SpouseName,
    (SELECT e.Date FROM EventTable e
     WHERE e.OwnerID = f.FamilyID AND e.OwnerType = 1 AND e.EventType = 300) as MarriageDate,
    (SELECT pl.Name FROM EventTable e
     LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
     WHERE e.OwnerID = f.FamilyID AND e.OwnerType = 1 AND e.EventType = 300) as MarriagePlace
FROM FamilyTable f
WHERE f.FatherID = ? OR f.MotherID = ?;
-- Use same PersonID for all ? placeholders
```

### Get Person's Children

```sql
SELECT c.ChildID as RIN, n.Given, n.Surname, p.Sex,
       (SELECT e.Date FROM EventTable e
        WHERE e.OwnerID = c.ChildID AND e.EventType = 1) as BirthDate,
       c.RelFather, c.RelMother, c.ChildOrder
FROM FamilyTable f
JOIN ChildTable c ON c.FamilyID = f.FamilyID
JOIN PersonTable p ON p.PersonID = c.ChildID
JOIN NameTable n ON n.OwnerID = c.ChildID AND n.IsPrimary = 1
WHERE f.FatherID = 1561 OR f.MotherID = 1561  -- Replace with parent RIN
ORDER BY c.ChildOrder;
```

### Get All Siblings

```sql
-- Get siblings (same parents)
SELECT DISTINCT s.ChildID as SiblingRIN, n.Given, n.Surname
FROM ChildTable c
JOIN ChildTable s ON c.FamilyID = s.FamilyID
JOIN NameTable n ON n.OwnerID = s.ChildID AND n.IsPrimary = 1
WHERE c.ChildID = 1561  -- Replace with target RIN
  AND s.ChildID != 1561  -- Exclude self
ORDER BY n.Surname, n.Given;
```

## Census Queries

### Find All Census Records for Person

**Critical:** Census events may be owned OR witnessed. Must check both.

```sql
-- Owned census events
SELECT e.EventID, e.Date, pl.Name as Place,
       s.SourceID, s.Name as SourceName, c.CitationID
FROM EventTable e
LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
LEFT JOIN CitationLinkTable cl ON cl.OwnerID = e.EventID AND cl.OwnerType = 2
LEFT JOIN CitationTable c ON c.CitationID = cl.CitationID
LEFT JOIN SourceTable s ON s.SourceID = c.SourceID
WHERE e.OwnerID = 1561  -- Replace with target RIN
  AND e.OwnerType = 0
  AND e.EventType = 18

UNION

-- Witnessed census events
SELECT e.EventID, e.Date, pl.Name as Place,
       s.SourceID, s.Name as SourceName, c.CitationID
FROM WitnessTable w
JOIN EventTable e ON e.EventID = w.EventID
LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
LEFT JOIN CitationLinkTable cl ON cl.OwnerID = e.EventID AND cl.OwnerType = 2
LEFT JOIN CitationTable c ON c.CitationID = cl.CitationID
LEFT JOIN SourceTable s ON s.SourceID = c.SourceID
WHERE w.PersonID = 1561  -- Replace with target RIN
  AND e.EventType = 18
ORDER BY Date;
```

### Find People in Same Census Household

```sql
-- Get all people in same census event (household)
SELECT
    CASE WHEN e.OwnerType = 0 THEN e.OwnerID ELSE NULL END as HeadRIN,
    w.PersonID as WitnessRIN,
    COALESCE(n.Given || ' ' || n.Surname, w.Given || ' ' || w.Surname) as Name,
    w.Role
FROM EventTable e
LEFT JOIN WitnessTable w ON w.EventID = e.EventID
LEFT JOIN NameTable n ON n.OwnerID = w.PersonID AND n.IsPrimary = 1
WHERE e.EventID = 12345  -- Replace with EventID
ORDER BY w.WitnessID;
```

## Source and Citation Queries

### Get All Citations for Event

```sql
SELECT c.CitationID, c.CitationName, s.Name as SourceName,
       s.TemplateID, st.Name as TemplateName
FROM CitationLinkTable cl
JOIN CitationTable c ON cl.CitationID = c.CitationID
JOIN SourceTable s ON c.SourceID = s.SourceID
LEFT JOIN SourceTemplateTable st ON s.TemplateID = st.TemplateID
WHERE cl.OwnerType = 2  -- Event
  AND cl.OwnerID = 12345;  -- Replace with EventID
```

### Find Free-Form Census Citations

```sql
-- Free-form sources have TemplateID=0
SELECT s.SourceID, s.Name,
       CAST(s.Fields AS TEXT) as FieldsXML,
       c.CitationID, c.CitationName
FROM SourceTable s
LEFT JOIN CitationTable c ON c.SourceID = s.SourceID
WHERE s.TemplateID = 0
  AND s.Name LIKE '%census%' COLLATE RMNOCASE
ORDER BY s.Name;
```

### Extract Footnote from Free-Form Source

```python
import xml.etree.ElementTree as ET
import sqlite3
from rmcitecraft.database.connection import connect_rmtree

conn = connect_rmtree('data/Iiams.rmtree')
cursor = conn.cursor()

# Get source with TemplateID=0
cursor.execute("""
    SELECT SourceID, CAST(Fields AS TEXT) as FieldsXML
    FROM SourceTable
    WHERE SourceID = ? AND TemplateID = 0
""", (source_id,))

source_id, fields_xml = cursor.fetchone()
if fields_xml:
    root = ET.fromstring(fields_xml)
    footnote = root.find('.//Field[Name="Footnote"]/Value')
    if footnote is not None:
        print(footnote.text)
```

## Media Queries

### Find Primary Photo for Person

```sql
SELECT m.MediaID, m.MediaFile, m.MediaPath, m.Caption
FROM MediaLinkTable ml
JOIN MultimediaTable m ON ml.MediaID = m.MediaID
WHERE ml.OwnerType = 0  -- Person
  AND ml.OwnerID = 1561  -- Replace with target RIN
  AND ml.IsPrimary = 1
LIMIT 1;
```

### Find All Media for Event

```sql
SELECT m.MediaID, m.MediaFile, m.MediaPath, m.Caption,
       m.MediaType, ml.SortOrder
FROM MediaLinkTable ml
JOIN MultimediaTable m ON ml.MediaID = m.MediaID
WHERE ml.OwnerType = 2  -- Event
  AND ml.OwnerID = 12345  -- Replace with EventID
ORDER BY ml.SortOrder;
```

## Place Queries

### Find All Events in Place

```sql
SELECT p.Name as Place, e.EventID, e.EventType, e.Date,
       ft.Name as FactType,
       n.Given || ' ' || n.Surname as PersonName
FROM PlaceTable p
JOIN EventTable e ON e.PlaceID = p.PlaceID
JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
LEFT JOIN NameTable n ON n.OwnerID = e.OwnerID AND n.IsPrimary = 1
WHERE p.Name LIKE '%Noble County, Ohio%' COLLATE RMNOCASE
ORDER BY e.Date;
```

## Advanced Patterns

### Count Events by Type for Person

```sql
SELECT ft.Name as EventType, COUNT(*) as Count
FROM EventTable e
JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
WHERE e.OwnerID = 1561 AND e.OwnerType = 0
GROUP BY e.EventType, ft.Name
ORDER BY Count DESC;
```

### Find People Without Census Records

```sql
SELECT p.PersonID as RIN, n.Given, n.Surname, n.BirthYear
FROM PersonTable p
JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
WHERE NOT EXISTS (
    SELECT 1 FROM EventTable e
    WHERE e.OwnerID = p.PersonID AND e.OwnerType = 0 AND e.EventType = 18
)
AND NOT EXISTS (
    SELECT 1 FROM WitnessTable w
    JOIN EventTable e ON e.EventID = w.EventID
    WHERE w.PersonID = p.PersonID AND e.EventType = 18
)
AND n.BirthYear IS NOT NULL
AND n.BirthYear < 1950
ORDER BY n.BirthYear DESC;
```

### Timeline of All Events for Person

```sql
SELECT
    e.Date,
    ft.Name as EventType,
    e.Details,
    pl.Name as Place,
    COUNT(cl.CitationID) as CitationCount
FROM EventTable e
JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
LEFT JOIN CitationLinkTable cl ON cl.OwnerID = e.EventID AND cl.OwnerType = 2
WHERE e.OwnerID = 1561 AND e.OwnerType = 0
GROUP BY e.EventID
ORDER BY e.SortDate;
```

## Important Notes

1. **Always use RMNOCASE collation** for text comparisons on Surname, Given, Name fields
2. **Check both EventTable and WitnessTable** for census records
3. **Use read_only=True** (default) unless you need to modify data
4. **Extract year from Date field** with `date_string[3:7]`
5. **Marriage events use OwnerType=1** (Family), not 0 (Person)
6. **Free-form sources store citations in BLOB** fields, not TEXT fields
7. **MediaPath uses symbols:** ? = Media folder, ~ = home, * = database folder
