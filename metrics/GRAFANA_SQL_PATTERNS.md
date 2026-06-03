# Grafana SQL Patterns for Genealogy Analytics

A comprehensive guide to SQL query patterns for each chart type in the genealogy analytics dashboards.

## Table of Contents
- [Quick Reference](#quick-reference)
- [Heatmap Patterns](#heatmap-patterns)
- [Bubble Map Patterns](#bubble-map-patterns)
- [Treemap Patterns](#treemap-patterns)
- [Sankey Patterns](#sankey-patterns)
- [Chord Patterns](#chord-patterns)
- [Arc Diagram Patterns](#arc-diagram-patterns)
- [Network Graph Patterns](#network-graph-patterns)
- [Dendrogram Patterns](#dendrogram-patterns)
- [Common Filters](#common-filters)
- [Performance Tips](#performance-tips)

---

## Quick Reference

| Chart Type | Required Columns | Example Use Case |
|------------|------------------|------------------|
| Heatmap | x (text), y (text), value (number) | Birth seasonality by decade/month |
| Bubble Map | latitude, longitude, value, label | Ancestral location hotspots |
| Treemap | hierarchy (text), value (number) | Citation coverage hierarchy |
| Sankey | source (text), target (text), value (number) | Migration flows |
| Chord | source (text), target (text), value (number) | Surname intermarriage |
| Arc Diagram | source (text), target (text), [value] | Lifespan overlaps |
| Network (Nodes) | id, title, mainStat | Family relationship nodes |
| Network (Edges) | id, source, target | Family relationship edges |
| Dendrogram | id, parent_id, label | Pedigree/descendant tree |

---

## Heatmap Patterns

### Pattern 1: Birth Seasonality Matrix

**Use Case**: Show birth patterns across months and decades

```sql
SELECT
  strftime('%Y', e.Date) as decade,
  CAST(strftime('%m', e.Date) AS INTEGER) as month,
  COUNT(*) as birth_count
FROM EventTable e
WHERE e.EventType = 1  -- Birth events
  AND e.Date IS NOT NULL
  AND e.Date != ''
GROUP BY decade, month
ORDER BY decade, month;
```

**Visualization Settings**:
- X-axis: decade
- Y-axis: month
- Color: birth_count

### Pattern 2: Research Completeness Matrix

**Use Case**: Show data quality across generations and field types

```sql
WITH generations AS (
  SELECT
    p.PersonID,
    -- Estimate generation based on birth year
    CASE
      WHEN CAST(strftime('%Y', birth.Date) AS INTEGER) < 1800 THEN 'Pre-1800'
      WHEN CAST(strftime('%Y', birth.Date) AS INTEGER) < 1850 THEN '1800-1849'
      WHEN CAST(strftime('%Y', birth.Date) AS INTEGER) < 1900 THEN '1850-1899'
      WHEN CAST(strftime('%Y', birth.Date) AS INTEGER) < 1950 THEN '1900-1949'
      ELSE '1950+'
    END as generation,
    CASE WHEN birth.Date IS NOT NULL THEN 1 ELSE 0 END as has_birth,
    CASE WHEN death.Date IS NOT NULL THEN 1 ELSE 0 END as has_death,
    CASE WHEN EXISTS (SELECT 1 FROM ChildTable WHERE ChildID = p.PersonID) THEN 1 ELSE 0 END as has_parents
  FROM PersonTable p
  LEFT JOIN EventTable birth ON birth.OwnerID = p.PersonID AND birth.EventType = 1
  LEFT JOIN EventTable death ON death.OwnerID = p.PersonID AND death.EventType = 2
)
SELECT
  generation as decade,
  'Birth Date' as field_type,
  ROUND(AVG(has_birth) * 100, 1) as completeness_pct
FROM generations
WHERE generation IS NOT NULL
GROUP BY generation
UNION ALL
SELECT
  generation as decade,
  'Death Date' as field_type,
  ROUND(AVG(has_death) * 100, 1) as completeness_pct
FROM generations
WHERE generation IS NOT NULL
GROUP BY generation
UNION ALL
SELECT
  generation as decade,
  'Parents' as field_type,
  ROUND(AVG(has_parents) * 100, 1) as completeness_pct
FROM generations
WHERE generation IS NOT NULL
GROUP BY generation
ORDER BY decade, field_type;
```

### Pattern 3: Census Coverage Matrix

**Use Case**: Show census year coverage by family branch

```sql
SELECT
  CASE
    WHEN n.Surname IN ('Iiams', 'Ijams', 'Iam') THEN 'Iiams'
    -- Add other surname variations
    ELSE n.Surname
  END as family_branch,
  CASE
    WHEN e.Date LIKE '1850%' THEN '1850'
    WHEN e.Date LIKE '1860%' THEN '1860'
    WHEN e.Date LIKE '1870%' THEN '1870'
    WHEN e.Date LIKE '1880%' THEN '1880'
    WHEN e.Date LIKE '1900%' THEN '1900'
    WHEN e.Date LIKE '1910%' THEN '1910'
    WHEN e.Date LIKE '1920%' THEN '1920'
    WHEN e.Date LIKE '1930%' THEN '1930'
    WHEN e.Date LIKE '1940%' THEN '1940'
    WHEN e.Date LIKE '1950%' THEN '1950'
  END as census_year,
  COUNT(DISTINCT p.PersonID) as person_count
FROM PersonTable p
JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
JOIN EventTable e ON e.OwnerID = p.PersonID
JOIN SourceTable s ON s.SourceID IN (
  SELECT SourceID FROM CitationTable WHERE CitationID = e.CitationID
)
WHERE s.Name LIKE '%Census%'
  AND census_year IS NOT NULL
GROUP BY family_branch, census_year
ORDER BY family_branch, census_year;
```

---

## Bubble Map Patterns

### Pattern 1: Ancestral Location Hotspots

**Use Case**: Show where ancestors lived with bubble size = person count

```sql
SELECT
  p.Latitude,
  p.Longitude,
  COUNT(DISTINCT e.OwnerID) as person_count,
  p.PlaceName as location,
  -- Additional fields for tooltip
  GROUP_CONCAT(DISTINCT st.Name, ', ') as place_type
FROM PlaceTable p
JOIN EventTable e ON e.PlaceID = p.PlaceID
LEFT JOIN SourceTable st ON st.SourceID IN (
  SELECT SourceID FROM CitationTable WHERE CitationID = e.CitationID
)
WHERE p.Latitude IS NOT NULL
  AND p.Longitude IS NOT NULL
  AND p.Latitude != 0
  AND p.Longitude != 0
GROUP BY p.PlaceID
HAVING person_count > 0
ORDER BY person_count DESC
LIMIT 100;
```

**Geomap Settings**:
- Location Mode: Coords
- Latitude: Latitude column
- Longitude: Longitude column
- Size: person_count (2-15 range)
- Color: person_count threshold

### Pattern 2: Cemetery Locations

**Use Case**: Map cemeteries with burial count

```sql
SELECT
  p.Latitude,
  p.Longitude,
  COUNT(DISTINCT e.OwnerID) as burial_count,
  p.PlaceName as cemetery_name
FROM PlaceTable p
JOIN EventTable e ON e.PlaceID = p.PlaceID
WHERE e.EventType = 6  -- Burial events
  AND p.Latitude IS NOT NULL
  AND p.Longitude IS NOT NULL
GROUP BY p.PlaceID
HAVING burial_count > 0
ORDER BY burial_count DESC;
```

### Pattern 3: Immigration Entry Points

**Use Case**: Map ports of entry with arrival counts

```sql
SELECT
  p.Latitude,
  p.Longitude,
  COUNT(DISTINCT e.OwnerID) as arrival_count,
  p.PlaceName as port_name,
  MIN(e.Date) as first_arrival,
  MAX(e.Date) as last_arrival
FROM PlaceTable p
JOIN EventTable e ON e.PlaceID = p.PlaceID
WHERE e.EventType = 42  -- Immigration events
  AND p.Latitude IS NOT NULL
  AND p.Longitude IS NOT NULL
GROUP BY p.PlaceID
HAVING arrival_count > 0
ORDER BY arrival_count DESC;
```

---

## Treemap Patterns

### Pattern 1: Citation Coverage by Record Type

**Use Case**: Hierarchical view of citation distribution

```sql
SELECT
  CASE
    WHEN st.TemplateID = 0 THEN 'Free-Form Citations'
    ELSE 'Template-Based Citations'
  END || ' > ' ||
  CASE
    WHEN st.Name LIKE '%Census%' THEN 'Census Records'
    WHEN st.Name LIKE '%Birth%' OR st.Name LIKE '%Marriage%' OR st.Name LIKE '%Death%' THEN 'Vital Records'
    WHEN st.Name LIKE '%Church%' THEN 'Church Records'
    WHEN st.Name LIKE '%Cemetery%' OR st.Name LIKE '%Grave%' THEN 'Cemetery Records'
    WHEN st.Name LIKE '%Military%' THEN 'Military Records'
    WHEN st.Name LIKE '%Land%' OR st.Name LIKE '%Deed%' THEN 'Land Records'
    ELSE 'Other Records'
  END as hierarchy,
  COUNT(DISTINCT ct.CitationID) as citation_count
FROM SourceTable st
LEFT JOIN CitationTable ct ON ct.SourceID = st.SourceID
GROUP BY hierarchy
HAVING citation_count > 0
ORDER BY citation_count DESC;
```

**Note**: Hierarchy delimiter is ` > ` (space-greater-space)

### Pattern 2: Media Coverage by Type and Century

**Use Case**: Show media distribution across time periods

```sql
SELECT
  CASE
    WHEN m.MediaType = 0 THEN 'Photos'
    WHEN m.MediaType = 1 THEN 'Documents'
    WHEN m.MediaType = 2 THEN 'Audio'
    WHEN m.MediaType = 3 THEN 'Video'
    ELSE 'Other Media'
  END || ' > ' ||
  CASE
    WHEN CAST(strftime('%Y', m.Date) AS INTEGER) < 1800 THEN 'Pre-1800'
    WHEN CAST(strftime('%Y', m.Date) AS INTEGER) < 1900 THEN '1800s'
    WHEN CAST(strftime('%Y', m.Date) AS INTEGER) < 2000 THEN '1900s'
    ELSE '2000s'
  END as hierarchy,
  COUNT(*) as media_count
FROM MediaTable m
WHERE m.Date IS NOT NULL
GROUP BY hierarchy
ORDER BY media_count DESC;
```

### Pattern 3: Family Branch Size

**Use Case**: Compare descendant counts by surname

```sql
SELECT
  'All Families > ' || n.Surname as hierarchy,
  COUNT(DISTINCT p.PersonID) as person_count
FROM PersonTable p
JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
WHERE n.Surname IS NOT NULL
GROUP BY n.Surname
HAVING person_count >= 5
ORDER BY person_count DESC;
```

---

## Sankey Patterns

### Pattern 1: Multi-Stage Migration

**Use Case**: Track movement from birth → residence → death

```sql
WITH person_places AS (
  SELECT
    p.PersonID,
    birth_place.PlaceName as birth_place,
    residence_place.PlaceName as residence_place,
    death_place.PlaceName as death_place
  FROM PersonTable p
  LEFT JOIN EventTable birth ON birth.OwnerID = p.PersonID AND birth.EventType = 1
  LEFT JOIN EventTable residence ON residence.OwnerID = p.PersonID AND residence.EventType = 4
  LEFT JOIN EventTable death ON death.OwnerID = p.PersonID AND death.EventType = 2
  LEFT JOIN PlaceTable birth_place ON birth.PlaceID = birth_place.PlaceID
  LEFT JOIN PlaceTable residence_place ON residence.PlaceID = residence_place.PlaceID
  LEFT JOIN PlaceTable death_place ON death.PlaceID = death_place.PlaceID
)
-- Birth to Residence flows
SELECT
  birth_place as source,
  residence_place as target,
  COUNT(*) as flow_count
FROM person_places
WHERE birth_place IS NOT NULL
  AND residence_place IS NOT NULL
  AND birth_place != residence_place
GROUP BY birth_place, residence_place
HAVING flow_count >= 2

UNION ALL

-- Residence to Death flows
SELECT
  residence_place as source,
  death_place as target,
  COUNT(*) as flow_count
FROM person_places
WHERE residence_place IS NOT NULL
  AND death_place IS NOT NULL
  AND residence_place != death_place
GROUP BY residence_place, death_place
HAVING flow_count >= 2

ORDER BY flow_count DESC
LIMIT 100;
```

### Pattern 2: Occupational Evolution

**Use Case**: Track career progression across generations

```sql
WITH occupation_pairs AS (
  SELECT
    p.PersonID,
    father.Occupation as parent_occupation,
    p.Occupation as person_occupation
  FROM PersonTable p
  JOIN ChildTable ct ON ct.ChildID = p.PersonID
  JOIN FamilyTable f ON f.FamilyID = ct.FamilyID
  JOIN PersonTable father ON father.PersonID = f.FatherID
  WHERE father.Occupation IS NOT NULL
    AND p.Occupation IS NOT NULL
    AND father.Occupation != p.Occupation
)
SELECT
  parent_occupation as source,
  person_occupation as target,
  COUNT(*) as transition_count
FROM occupation_pairs
GROUP BY parent_occupation, person_occupation
HAVING transition_count >= 2
ORDER BY transition_count DESC;
```

### Pattern 3: Religious Affiliation Transitions

**Use Case**: Track religious transitions across generations

```sql
SELECT
  parent_church.Name as source,
  person_church.Name as target,
  COUNT(*) as transition_count
FROM PersonTable p
JOIN ChildTable ct ON ct.ChildID = p.PersonID
JOIN FamilyTable f ON f.FamilyID = ct.FamilyID
JOIN PersonTable parent ON parent.PersonID = f.FatherID
-- Join to church membership events
JOIN EventTable parent_event ON parent_event.OwnerID = parent.PersonID AND parent_event.EventType = 16
JOIN EventTable person_event ON person_event.OwnerID = p.PersonID AND person_event.EventType = 16
JOIN PlaceTable parent_church ON parent_church.PlaceID = parent_event.PlaceID
JOIN PlaceTable person_church ON person_church.PlaceID = person_event.PlaceID
WHERE parent_church.Name != person_church.Name
GROUP BY parent_church.Name, person_church.Name
HAVING transition_count >= 2
ORDER BY transition_count DESC;
```

---

## Chord Patterns

### Pattern 1: Surname Intermarriage Network

**Use Case**: Show which family names intermarried most frequently

```sql
SELECT
  father_name.Surname as source,
  mother_name.Surname as target,
  COUNT(*) as marriage_count
FROM FamilyTable f
JOIN NameTable father_name ON father_name.OwnerID = f.FatherID AND father_name.IsPrimary = 1
JOIN NameTable mother_name ON mother_name.OwnerID = f.MotherID AND mother_name.IsPrimary = 1
WHERE father_name.Surname IS NOT NULL
  AND mother_name.Surname IS NOT NULL
  AND father_name.Surname != mother_name.Surname
  AND f.FatherID IS NOT NULL
  AND f.MotherID IS NOT NULL
GROUP BY father_name.Surname, mother_name.Surname
HAVING marriage_count >= 2
ORDER BY marriage_count DESC
LIMIT 50;
```

**Note**: For symmetric chord diagram, include both directions:

```sql
-- Add UNION ALL with source/target swapped if needed
UNION ALL
SELECT
  mother_name.Surname as source,
  father_name.Surname as target,
  COUNT(*) as marriage_count
FROM FamilyTable f
...
```

### Pattern 2: Geographic Marriage Exchanges

**Use Case**: Show which locations exchanged marriage partners

```sql
SELECT
  groom_place.PlaceName as source,
  bride_place.PlaceName as target,
  COUNT(*) as marriage_count
FROM FamilyTable f
JOIN PersonTable father ON father.PersonID = f.FatherID
JOIN PersonTable mother ON mother.PersonID = f.MotherID
-- Get birth places as proxy for origin location
JOIN EventTable father_birth ON father_birth.OwnerID = father.PersonID AND father_birth.EventType = 1
JOIN EventTable mother_birth ON mother_birth.OwnerID = mother.PersonID AND mother_birth.EventType = 1
JOIN PlaceTable groom_place ON groom_place.PlaceID = father_birth.PlaceID
JOIN PlaceTable bride_place ON bride_place.PlaceID = mother_birth.PlaceID
WHERE groom_place.PlaceName != bride_place.PlaceName
GROUP BY groom_place.PlaceName, bride_place.PlaceName
HAVING marriage_count >= 2
ORDER BY marriage_count DESC;
```

### Pattern 3: Religious Group Interconnections

**Use Case**: Show marriages between different religious communities

```sql
SELECT
  father_church.Name as source,
  mother_church.Name as target,
  COUNT(*) as marriage_count
FROM FamilyTable f
-- Get church affiliations for both spouses
JOIN EventTable father_church_event ON father_church_event.OwnerID = f.FatherID AND father_church_event.EventType = 16
JOIN EventTable mother_church_event ON mother_church_event.OwnerID = f.MotherID AND mother_church_event.EventType = 16
JOIN PlaceTable father_church ON father_church.PlaceID = father_church_event.PlaceID
JOIN PlaceTable mother_church ON mother_church.PlaceID = mother_church_event.PlaceID
WHERE father_church.Name != mother_church.Name
GROUP BY father_church.Name, mother_church.Name
HAVING marriage_count >= 1
ORDER BY marriage_count DESC;
```

---

## Arc Diagram Patterns

### Pattern 1: Lifespan Overlaps (Who Could Have Known Whom)

**Use Case**: Show which ancestors' lives overlapped

```sql
WITH lifespans AS (
  SELECT
    p.PersonID,
    n.Given || ' ' || n.Surname as full_name,
    n.Surname,
    birth.Date as birth_date,
    death.Date as death_date,
    CAST((julianday(death.Date) - julianday(birth.Date)) / 365.25 AS INTEGER) as age
  FROM PersonTable p
  JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
  LEFT JOIN EventTable birth ON birth.OwnerID = p.PersonID AND birth.EventType = 1
  LEFT JOIN EventTable death ON death.OwnerID = p.PersonID AND death.EventType = 2
  WHERE birth.Date IS NOT NULL
    AND birth.Date != ''
)
SELECT
  elder.full_name as source,
  younger.full_name as target,
  CAST((julianday(elder.death_date) - julianday(younger.birth_date)) / 365.25 AS INTEGER) as overlap_years
FROM lifespans elder
JOIN lifespans younger ON younger.birth_date < elder.death_date
WHERE elder.birth_date < younger.birth_date
  AND elder.death_date IS NOT NULL
  AND elder.death_date != ''
  AND overlap_years > 10  -- Meaningful overlap threshold
ORDER BY overlap_years DESC
LIMIT 100;
```

### Pattern 2: Same-Location Contemporaries

**Use Case**: Show people who lived in the same place at the same time

```sql
WITH residences AS (
  SELECT
    p.PersonID,
    n.Given || ' ' || n.Surname as full_name,
    pl.PlaceName,
    e.Date,
    e.SortDate
  FROM PersonTable p
  JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
  JOIN EventTable e ON e.OwnerID = p.PersonID AND e.EventType = 4  -- Residence
  JOIN PlaceTable pl ON pl.PlaceID = e.PlaceID
  WHERE e.Date IS NOT NULL
)
SELECT
  r1.full_name as source,
  r2.full_name as target,
  ABS(r1.SortDate - r2.SortDate) / 365 as years_apart
FROM residences r1
JOIN residences r2 ON r1.PlaceName = r2.PlaceName
  AND r1.PersonID < r2.PersonID  -- Avoid duplicates
  AND ABS(r1.SortDate - r2.SortDate) / 365 <= 5  -- Within 5 years
ORDER BY years_apart
LIMIT 100;
```

### Pattern 3: Witness Relationships Timeline

**Use Case**: Show who witnessed whose life events

```sql
SELECT
  principal.Given || ' ' || principal.Surname as source,
  witness.Given || ' ' || witness.Surname as target,
  e.Date as event_date,
  et.Name as event_type
FROM WitnessTable w
JOIN EventTable e ON e.EventID = w.EventID
JOIN PersonTable p1 ON p1.PersonID = e.OwnerID
JOIN PersonTable p2 ON p2.PersonID = w.WitnessID
JOIN NameTable principal ON principal.OwnerID = p1.PersonID AND principal.IsPrimary = 1
JOIN NameTable witness ON witness.OwnerID = p2.PersonID AND witness.IsPrimary = 1
JOIN EventTypeTable et ON et.EventType = e.EventType
WHERE e.Date IS NOT NULL
ORDER BY e.SortDate
LIMIT 100;
```

---

## Network Graph Patterns

Network graphs require TWO separate queries (or a VIEW with UNION).

### Pattern 1: Family Intermarriage Network

**NODES Query**:
```sql
SELECT
  p.PersonID as id,
  n.Given || ' ' || n.Surname as title,
  n.Surname as mainStat,
  n.Surname as arc__family,  -- For color clustering
  'person' as detail__type,
  CAST((julianday('now') - julianday(birth.Date)) / 365.25 AS INTEGER) as detail__age
FROM PersonTable p
JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
LEFT JOIN EventTable birth ON birth.OwnerID = p.PersonID AND birth.EventType = 1
WHERE p.PersonID IN (
  -- Only include people with relationships
  SELECT DISTINCT FatherID FROM FamilyTable WHERE FatherID IS NOT NULL
  UNION
  SELECT DISTINCT MotherID FROM FamilyTable WHERE MotherID IS NOT NULL
)
LIMIT 200;
```

**EDGES Query**:
```sql
SELECT
  'marriage-' || f.FamilyID as id,
  f.FatherID as source,
  f.MotherID as target,
  'marriage' as mainStat,
  marriage.Date as detail__date
FROM FamilyTable f
LEFT JOIN EventTable marriage ON marriage.OwnerID = f.FamilyID AND marriage.EventType = 300 AND marriage.OwnerType = 1
WHERE f.FatherID IS NOT NULL
  AND f.MotherID IS NOT NULL
  AND f.FatherID IN (SELECT id FROM (...nodes query...))
  AND f.MotherID IN (SELECT id FROM (...nodes query...))
LIMIT 200;
```

**Alternative**: Create a VIEW combining both:

```sql
CREATE VIEW family_network AS
-- Nodes
SELECT
  'node' as type,
  CAST(p.PersonID AS TEXT) as id,
  n.Given || ' ' || n.Surname as title,
  n.Surname as group_name,
  NULL as source,
  NULL as target
FROM PersonTable p
JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
WHERE p.PersonID IN (
  SELECT DISTINCT FatherID FROM FamilyTable WHERE FatherID IS NOT NULL
  UNION
  SELECT DISTINCT MotherID FROM FamilyTable WHERE MotherID IS NOT NULL
)

UNION ALL

-- Edges
SELECT
  'edge' as type,
  'marriage-' || f.FamilyID as id,
  'marriage' as title,
  NULL as group_name,
  CAST(f.FatherID AS TEXT) as source,
  CAST(f.MotherID AS TEXT) as target
FROM FamilyTable f
WHERE f.FatherID IS NOT NULL
  AND f.MotherID IS NOT NULL;
```

---

## Dendrogram Patterns

### Pattern 1: Pedigree Chart (Ancestors)

**Use Case**: Show 4-5 generation pedigree tree

```sql
WITH RECURSIVE ancestors AS (
  -- Anchor: Start with person of interest (PersonID = 1)
  SELECT
    1 as PersonID,
    NULL as ParentID,
    (SELECT n.Given || ' ' || n.Surname
     FROM NameTable n
     WHERE n.OwnerID = 1 AND n.IsPrimary = 1) as label,
    0 as generation,
    'root' as lineage

  UNION ALL

  -- Recursive: Get father
  SELECT
    child_fam.FatherID as PersonID,
    anc.PersonID as ParentID,
    (SELECT n.Given || ' ' || n.Surname
     FROM NameTable n
     WHERE n.OwnerID = child_fam.FatherID AND n.IsPrimary = 1) as label,
    anc.generation + 1 as generation,
    anc.lineage || ' → Father' as lineage
  FROM ancestors anc
  JOIN ChildTable ct ON ct.ChildID = anc.PersonID
  JOIN FamilyTable child_fam ON child_fam.FamilyID = ct.FamilyID
  WHERE anc.generation < 4
    AND child_fam.FatherID IS NOT NULL

  UNION ALL

  -- Recursive: Get mother
  SELECT
    child_fam.MotherID as PersonID,
    anc.PersonID as ParentID,
    (SELECT n.Given || ' ' || n.Surname
     FROM NameTable n
     WHERE n.OwnerID = child_fam.MotherID AND n.IsPrimary = 1) as label,
    anc.generation + 1 as generation,
    anc.lineage || ' → Mother' as lineage
  FROM ancestors anc
  JOIN ChildTable ct ON ct.ChildID = anc.PersonID
  JOIN FamilyTable child_fam ON child_fam.FamilyID = ct.FamilyID
  WHERE anc.generation < 4
    AND child_fam.MotherID IS NOT NULL
)
SELECT
  PersonID as id,
  ParentID as parent_id,
  label,
  generation,
  lineage
FROM ancestors
WHERE PersonID IS NOT NULL
ORDER BY generation, PersonID;
```

### Pattern 2: Descendant Chart

**Use Case**: Show all descendants of an ancestor

```sql
WITH RECURSIVE descendants AS (
  -- Anchor: Start with ancestor (PersonID = 100)
  SELECT
    100 as PersonID,
    NULL as ParentID,
    (SELECT n.Given || ' ' || n.Surname
     FROM NameTable n
     WHERE n.OwnerID = 100 AND n.IsPrimary = 1) as label,
    0 as generation

  UNION ALL

  -- Recursive: Get children
  SELECT
    ct.ChildID as PersonID,
    desc.PersonID as ParentID,
    (SELECT n.Given || ' ' || n.Surname
     FROM NameTable n
     WHERE n.OwnerID = ct.ChildID AND n.IsPrimary = 1) as label,
    desc.generation + 1 as generation
  FROM descendants desc
  JOIN FamilyTable f ON (f.FatherID = desc.PersonID OR f.MotherID = desc.PersonID)
  JOIN ChildTable ct ON ct.FamilyID = f.FamilyID
  WHERE desc.generation < 5
)
SELECT
  PersonID as id,
  ParentID as parent_id,
  label,
  generation
FROM descendants
WHERE PersonID IS NOT NULL
ORDER BY generation, PersonID;
```

---

## Common Filters

### Surname Filter (Dashboard Variable)

Add to WHERE clause:
```sql
WHERE ('$surname' = 'All' OR n.Surname = '$surname')
```

### Living Person Filter (Privacy)

Add to WHERE clause:
```sql
WHERE p.Living = 0
-- OR use date-based filter (100-year rule)
WHERE (julianday('now') - julianday(birth.Date)) / 365.25 > 100
```

### Date Range Filter

Add to WHERE clause:
```sql
WHERE e.SortDate BETWEEN
  julianday('$start_date') AND julianday('$end_date')
```

### Generation Filter

Add to WHERE clause (requires generation calculation):
```sql
WHERE generation BETWEEN $min_gen AND $max_gen
```

### Data Quality Filter

Add to WHERE clause:
```sql
WHERE e.Date IS NOT NULL
  AND e.Date != ''
  AND LENGTH(e.Date) >= 4  -- At least a year
```

---

## Performance Tips

### 1. Use Indexes

Add to `prepare_grafana_db.py`:

```python
cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_ownerid ON EventTable(OwnerID)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_type ON EventTable(EventType)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_placeid ON EventTable(PlaceID)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_name_ownerid ON NameTable(OwnerID)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_name_isprimary ON NameTable(IsPrimary)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_place_coords ON PlaceTable(Latitude, Longitude)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_citation_sourceid ON CitationTable(SourceID)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_family_father ON FamilyTable(FatherID)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_family_mother ON FamilyTable(MotherID)")
```

### 2. Create Views for Complex Queries

```sql
CREATE VIEW person_summary AS
SELECT
  p.PersonID,
  n.Given || ' ' || n.Surname as full_name,
  n.Surname,
  birth.Date as birth_date,
  death.Date as death_date,
  birth_place.PlaceName as birth_place,
  death_place.PlaceName as death_place
FROM PersonTable p
JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
LEFT JOIN EventTable birth ON birth.OwnerID = p.PersonID AND birth.EventType = 1
LEFT JOIN EventTable death ON death.OwnerID = p.PersonID AND death.EventType = 2
LEFT JOIN PlaceTable birth_place ON birth.PlaceID = birth_place.PlaceID
LEFT JOIN PlaceTable death_place ON death.PlaceID = death_place.PlaceID;
```

### 3. Limit Result Sets

Always use LIMIT for large datasets:
```sql
LIMIT 100  -- Or use dashboard variable: LIMIT $max_results
```

### 4. Filter Early

Apply WHERE clauses before JOINs when possible:
```sql
-- Good
FROM (SELECT * FROM PersonTable WHERE Living = 0) p

-- Less efficient
FROM PersonTable p
WHERE p.Living = 0
```

### 5. Avoid N+1 Queries

Use JOINs instead of subqueries in SELECT:
```sql
-- Good
SELECT p.PersonID, n.Surname
FROM PersonTable p
JOIN NameTable n ON n.OwnerID = p.PersonID

-- Less efficient
SELECT
  p.PersonID,
  (SELECT Surname FROM NameTable WHERE OwnerID = p.PersonID) as surname
FROM PersonTable p
```

---

## Troubleshooting

### Common Issues

**Issue**: "no such collation sequence: RMNOCASE"
- **Cause**: Using raw SQLite database instead of cleaned version
- **Fix**: Use `prepare_grafana_db.py` to create Grafana-compatible database

**Issue**: Empty results for date-based queries
- **Cause**: Date format inconsistencies
- **Fix**: Add `AND e.Date != ''` to filters

**Issue**: Duplicate rows in results
- **Cause**: Multiple name records or events
- **Fix**: Use `DISTINCT` or add `IsPrimary = 1` filter

**Issue**: Slow query performance
- **Cause**: Missing indexes, large result sets
- **Fix**: Add indexes, use LIMIT, create views

**Issue**: Plugin not showing data
- **Cause**: Incorrect column names or data format
- **Fix**: Validate with `validation_queries.sql` first

---

## Next Steps

1. Run validation queries in Grafana SQL editor
2. Create test dashboard with sample panels
3. Adjust queries based on your data quality
4. Create production dashboards (Phase 2+)
5. Add dashboard variables for interactivity

---

*Document Version: 1.0*
*Last Updated: 2026-01-25*
