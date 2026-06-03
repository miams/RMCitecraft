# RootsMagic Query Patterns

Common SQL patterns for genealogical research.

## Person Queries

### Find person by RIN
```sql
SELECT p.PersonID, n.Given, n.Surname, p.Sex,
       (SELECT e.Date FROM EventTable e
        WHERE e.OwnerID = p.PersonID AND e.EventType = 1) as Birth,
       (SELECT e.Date FROM EventTable e
        WHERE e.OwnerID = p.PersonID AND e.EventType = 2) as Death
FROM PersonTable p
JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
WHERE p.PersonID = ?
```

### Search by surname with variants
```sql
SELECT p.PersonID as RIN, n.Given, n.Surname
FROM PersonTable p
JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
WHERE n.Surname LIKE '%Iiams%'
   OR n.Surname LIKE '%Ijams%'
   OR n.Surname LIKE '%Iams%'
   OR n.Surname LIKE '%Imes%'
ORDER BY n.Surname, n.Given
```

### Find persons by birth year range
```sql
SELECT p.PersonID, n.Given, n.Surname, e.Date as Birth
FROM PersonTable p
JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
JOIN EventTable e ON e.OwnerID = p.PersonID AND e.EventType = 1
WHERE SUBSTR(e.Date, 4, 4) BETWEEN '1730' AND '1750'
ORDER BY e.Date
```

### Find persons by birthplace
```sql
SELECT p.PersonID, n.Given, n.Surname, pl.Name as Birthplace
FROM PersonTable p
JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
JOIN EventTable e ON e.OwnerID = p.PersonID AND e.EventType = 1
JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
WHERE pl.Name LIKE '%Anne Arundel%'
ORDER BY n.Surname
```

## Family Queries

### Get parents of a person
```sql
SELECT
    f.FatherID,
    (SELECT n.Given || ' ' || n.Surname FROM NameTable n
     WHERE n.OwnerID = f.FatherID AND n.IsPrimary = 1) as Father,
    f.MotherID,
    (SELECT n.Given || ' ' || n.Surname FROM NameTable n
     WHERE n.OwnerID = f.MotherID AND n.IsPrimary = 1) as Mother
FROM ChildTable c
JOIN FamilyTable f ON c.FamilyID = f.FamilyID
WHERE c.ChildID = ?
```

### Get all children of a person
```sql
SELECT
    c.ChildID,
    n.Given,
    n.Surname,
    p.Sex,
    (SELECT e.Date FROM EventTable e
     WHERE e.OwnerID = c.ChildID AND e.EventType = 1) as Birth
FROM FamilyTable f
JOIN ChildTable c ON c.FamilyID = f.FamilyID
JOIN PersonTable p ON p.PersonID = c.ChildID
JOIN NameTable n ON n.OwnerID = c.ChildID AND n.IsPrimary = 1
WHERE f.FatherID = ? OR f.MotherID = ?
ORDER BY Birth
```

### Get siblings of a person
```sql
SELECT
    c2.ChildID as SiblingRIN,
    n.Given,
    n.Surname,
    (SELECT e.Date FROM EventTable e
     WHERE e.OwnerID = c2.ChildID AND e.EventType = 1) as Birth
FROM ChildTable c1
JOIN ChildTable c2 ON c1.FamilyID = c2.FamilyID
JOIN NameTable n ON n.OwnerID = c2.ChildID AND n.IsPrimary = 1
WHERE c1.ChildID = ? AND c2.ChildID != ?
ORDER BY Birth
```

### Get spouses of a person
```sql
SELECT
    CASE WHEN f.FatherID = ? THEN f.MotherID ELSE f.FatherID END as SpouseID,
    (SELECT n.Given || ' ' || n.Surname FROM NameTable n
     WHERE n.OwnerID = CASE WHEN f.FatherID = ? THEN f.MotherID ELSE f.FatherID END
     AND n.IsPrimary = 1) as SpouseName,
    (SELECT e.Date FROM EventTable e
     WHERE e.OwnerID = f.FamilyID AND e.OwnerType = 1 AND e.EventType = 300) as MarriageDate
FROM FamilyTable f
WHERE f.FatherID = ? OR f.MotherID = ?
```

### Get marriage details
```sql
SELECT
    f.FamilyID,
    e.Date as MarriageDate,
    pl.Name as MarriagePlace,
    (SELECT n.Given || ' ' || n.Surname FROM NameTable n
     WHERE n.OwnerID = f.FatherID AND n.IsPrimary = 1) as Husband,
    (SELECT n.Given || ' ' || n.Surname FROM NameTable n
     WHERE n.OwnerID = f.MotherID AND n.IsPrimary = 1) as Wife
FROM FamilyTable f
LEFT JOIN EventTable e ON e.OwnerID = f.FamilyID
    AND e.OwnerType = 1 AND e.EventType = 300
LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
WHERE f.FatherID = ? OR f.MotherID = ?
```

## Census Queries

### Find census events for a person
```sql
SELECT
    e.EventID,
    e.Date,
    pl.Name as Place,
    s.Name as Source
FROM EventTable e
LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
LEFT JOIN CitationLinkTable cl ON cl.OwnerID = e.EventID AND cl.OwnerType = 2
LEFT JOIN CitationTable c ON c.CitationID = cl.CitationID
LEFT JOIN SourceTable s ON s.SourceID = c.SourceID
WHERE e.OwnerID = ? AND e.OwnerType = 0 AND e.EventType = 18
ORDER BY e.Date
```

### Find 1790 census sources
```sql
SELECT SourceID, Name, Comments
FROM SourceTable
WHERE Name LIKE '%1790%' AND Name LIKE '%Census%'
ORDER BY Name
```

## Source Queries

### Get sources linked to a person
```sql
SELECT DISTINCT s.SourceID, s.Name
FROM SourceTable s
JOIN CitationTable c ON c.SourceID = s.SourceID
JOIN CitationLinkTable cl ON cl.CitationID = c.CitationID
WHERE (cl.OwnerType = 0 AND cl.OwnerID = ?)  -- Person
   OR (cl.OwnerType = 2 AND cl.OwnerID IN   -- Events
       (SELECT EventID FROM EventTable WHERE OwnerID = ? AND OwnerType = 0))
ORDER BY s.Name
```

### Read free-form source fields (BLOB)
```python
# For TemplateID=0, citation data is in SourceTable.Fields BLOB
cursor.execute("""
    SELECT CAST(Fields AS TEXT) FROM SourceTable WHERE SourceID = ?
""", (source_id,))
fields_xml = cursor.fetchone()[0]

# Parse XML to get Footnote, ShortFootnote, Bibliography
import xml.etree.ElementTree as ET
root = ET.fromstring(fields_xml)
footnote = root.find('.//Field[Name="Footnote"]/Value').text
```

### Update source comments (for GPS)
```python
cursor.execute("""
    UPDATE SourceTable SET Comments = ? WHERE SourceID = ?
""", (gps_html, source_id))
conn.commit()
```

## Census.db Queries

### Find all census records for a surname
```sql
SELECT cp.person_id, cp.full_name, pg.census_year, pg.state, pg.county,
       cp.line_number, rl.rmtree_person_id as RIN
FROM census_person cp
JOIN census_page pg ON cp.page_id = pg.page_id
LEFT JOIN rmtree_link rl ON cp.person_id = rl.census_person_id
WHERE cp.surname LIKE '%Iiams%'
ORDER BY pg.census_year, pg.state
```

### Get household tallies (1790-1840)
```sql
SELECT
    cp.full_name,
    pg.census_year,
    MAX(CASE WHEN cpf.field_name = 'free_white_males_16_plus'
        THEN cpf.field_value END) as M16_plus,
    MAX(CASE WHEN cpf.field_name = 'free_white_males_under_16'
        THEN cpf.field_value END) as M_under_16,
    MAX(CASE WHEN cpf.field_name = 'free_white_females'
        THEN cpf.field_value END) as Females,
    MAX(CASE WHEN cpf.field_name = 'slaves'
        THEN cpf.field_value END) as Slaves
FROM census_person cp
JOIN census_page pg ON cp.page_id = pg.page_id
LEFT JOIN census_person_field cpf ON cp.person_id = cpf.person_id
WHERE pg.census_year <= 1840
GROUP BY cp.person_id
ORDER BY pg.census_year
```

### Find unlinked census records
```sql
SELECT cp.person_id, cp.full_name, pg.census_year, pg.county
FROM census_person cp
JOIN census_page pg ON cp.page_id = pg.page_id
LEFT JOIN rmtree_link rl ON cp.person_id = rl.census_person_id
WHERE rl.link_id IS NULL
ORDER BY pg.census_year, cp.surname
```

### Create rmtree_link
```sql
INSERT INTO rmtree_link
(census_person_id, rmtree_person_id, rmtree_citation_id,
 match_confidence, match_method, linked_at)
VALUES (?, ?, ?, ?, 'manual_analysis', datetime('now'))
```

## Utility Functions

### Parse RootsMagic date to year
```python
def parse_year(date_str):
    """Extract year from RootsMagic date format."""
    if date_str and len(date_str) >= 7:
        return date_str[3:7]
    return None
```

### Calculate age at date
```python
def age_at_date(birth_date, target_year):
    """Calculate age at a given year."""
    birth_year = parse_year(birth_date)
    if birth_year and birth_year.isdigit():
        return target_year - int(birth_year)
    return None
```

### Format person display
```python
def format_person(rin, given, surname, birth_year, sex):
    """Format person for display."""
    sex_str = 'M' if sex == 0 else 'F' if sex == 1 else '?'
    return f"RIN {rin}: {given} {surname} ({sex_str}) b.{birth_year or '?'}"
```
