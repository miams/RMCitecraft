-- Phase 1 Validation Queries for Grafana Genealogy Analytics
-- These queries test data format compatibility with each chart type
-- Run these in Grafana to validate your setup before creating production dashboards

-- =============================================================================
-- 1. HEATMAP VALIDATION - Birth Seasonality
-- =============================================================================
-- Expected format: x (text), y (text), value (number)
-- Tests: Date extraction, grouping, aggregation

SELECT
  strftime('%Y', e.Date) as decade,
  CAST(strftime('%m', e.Date) AS INTEGER) as month,
  COUNT(*) as birth_count
FROM EventTable e
WHERE e.EventType = 1  -- Birth events
  AND e.Date IS NOT NULL
  AND e.Date != ''
GROUP BY decade, month
ORDER BY decade, month
LIMIT 100;

-- Expected result: ~12 rows per decade showing month distribution


-- =============================================================================
-- 2. BUBBLE MAP VALIDATION - Geographic Distribution
-- =============================================================================
-- Expected format: latitude, longitude, value (bubble size), label
-- Tests: Coordinate data, place name extraction

SELECT
  p.Latitude,
  p.Longitude,
  COUNT(DISTINCT e.OwnerID) as person_count,
  p.PlaceName as location,
  'circle' as geohash  -- Dummy field for Grafana geomap
FROM PlaceTable p
JOIN EventTable e ON e.PlaceID = p.PlaceID
WHERE p.Latitude IS NOT NULL
  AND p.Longitude IS NOT NULL
  AND p.Latitude != 0
  AND p.Longitude != 0
GROUP BY p.PlaceID
HAVING person_count > 0
ORDER BY person_count DESC
LIMIT 50;

-- Expected result: Top 50 locations with coordinates and person counts


-- =============================================================================
-- 3. TREEMAP VALIDATION - Citation Coverage
-- =============================================================================
-- Expected format: hierarchical path (text), value (number)
-- Tests: Hierarchical string concatenation, citation counts

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
    ELSE 'Other Records'
  END as hierarchy,
  COUNT(DISTINCT ct.CitationID) as citation_count
FROM SourceTable st
LEFT JOIN CitationTable ct ON ct.SourceID = st.SourceID
GROUP BY hierarchy
HAVING citation_count > 0
ORDER BY citation_count DESC;

-- Expected result: Hierarchical categories with citation counts


-- =============================================================================
-- 4. SANKEY VALIDATION - Migration Flows
-- =============================================================================
-- Expected format: source (text), target (text), value (number)
-- Tests: Place linking across events, flow aggregation

WITH person_places AS (
  SELECT
    p.PersonID,
    birth_place.PlaceName as birth_place,
    death_place.PlaceName as death_place
  FROM PersonTable p
  LEFT JOIN EventTable birth ON birth.OwnerID = p.PersonID AND birth.EventType = 1
  LEFT JOIN EventTable death ON death.OwnerID = p.PersonID AND death.EventType = 2
  LEFT JOIN PlaceTable birth_place ON birth.PlaceID = birth_place.PlaceID
  LEFT JOIN PlaceTable death_place ON death.PlaceID = death_place.PlaceID
  WHERE birth_place.PlaceName IS NOT NULL
    AND death_place.PlaceName IS NOT NULL
    AND birth_place.PlaceName != death_place.PlaceName
)
SELECT
  birth_place as source,
  death_place as target,
  COUNT(*) as flow_count
FROM person_places
GROUP BY birth_place, death_place
HAVING flow_count >= 2  -- Minimum flow threshold
ORDER BY flow_count DESC
LIMIT 50;

-- Expected result: Top migration paths with person counts


-- =============================================================================
-- 5. CHORD VALIDATION - Surname Intermarriage
-- =============================================================================
-- Expected format: source (text), target (text), value (number)
-- Tests: Surname extraction from family table, symmetric relationships

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
LIMIT 30;

-- Expected result: Surname pairs with marriage frequency


-- =============================================================================
-- 6. ARC DIAGRAM VALIDATION - Lifespan Overlaps
-- =============================================================================
-- Expected format: source (text), target (text), value (optional weight)
-- Tests: Date arithmetic, overlap calculation

WITH lifespans AS (
  SELECT
    p.PersonID,
    n.Given || ' ' || n.Surname as full_name,
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
LIMIT 50;

-- Expected result: Person pairs with years of life overlap


-- =============================================================================
-- 7. NETWORK GRAPH VALIDATION - Family Relationships
-- =============================================================================
-- NOTE: Network graphs require TWO separate queries (nodes + edges)

-- NODES QUERY
SELECT
  p.PersonID as id,
  n.Given || ' ' || n.Surname as title,
  n.Surname as mainStat,
  n.Surname as arc__family,  -- For color clustering
  'person' as detail__type
FROM PersonTable p
JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
WHERE p.PersonID IN (
  -- Only include people with relationships
  SELECT DISTINCT FatherID FROM FamilyTable WHERE FatherID IS NOT NULL
  UNION
  SELECT DISTINCT MotherID FROM FamilyTable WHERE MotherID IS NOT NULL
)
LIMIT 100;

-- EDGES QUERY (run separately or use UNION)
SELECT
  f.FamilyID || '-marriage' as id,
  f.FatherID as source,
  f.MotherID as target,
  'marriage' as mainStat
FROM FamilyTable f
WHERE f.FatherID IS NOT NULL
  AND f.MotherID IS NOT NULL
  AND f.FatherID IN (SELECT id FROM (
    -- Match PersonIDs from nodes query
    SELECT p.PersonID as id
    FROM PersonTable p
    JOIN NameTable n ON n.OwnerID = p.PersonID
    LIMIT 100
  ))
LIMIT 50;

-- Expected result: Nodes with IDs and edges connecting them


-- =============================================================================
-- 8. DENDROGRAM/TREE VALIDATION - Pedigree Chart
-- =============================================================================
-- Expected format: id (number), parent_id (number), label (text)
-- Tests: Recursive CTE for ancestor traversal

WITH RECURSIVE ancestors AS (
  -- Anchor: Start with person 1 (or any root person)
  SELECT
    1 as PersonID,
    NULL as ParentID,
    (SELECT n.Given || ' ' || n.Surname
     FROM NameTable n
     WHERE n.OwnerID = 1 AND n.IsPrimary = 1) as label,
    0 as generation,
    'root' as parent_type

  UNION ALL

  -- Recursive: Get father
  SELECT
    child_fam.FatherID as PersonID,
    anc.PersonID as ParentID,
    (SELECT n.Given || ' ' || n.Surname
     FROM NameTable n
     WHERE n.OwnerID = child_fam.FatherID AND n.IsPrimary = 1) as label,
    anc.generation + 1 as generation,
    'father' as parent_type
  FROM ancestors anc
  JOIN ChildTable ct ON ct.ChildID = anc.PersonID
  JOIN FamilyTable child_fam ON child_fam.FamilyID = ct.FamilyID
  WHERE anc.generation < 4  -- Limit to 4 generations
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
    'mother' as parent_type
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
  parent_type
FROM ancestors
WHERE PersonID IS NOT NULL
ORDER BY generation, PersonID;

-- Expected result: Hierarchical tree structure with parent-child relationships


-- =============================================================================
-- DATA QUALITY CHECKS
-- =============================================================================

-- Check 1: Date Coverage for Temporal Charts
SELECT
  'Date Coverage' as metric,
  COUNT(*) as total_events,
  COUNT(Date) as events_with_dates,
  ROUND(100.0 * COUNT(Date) / COUNT(*), 1) as coverage_percentage
FROM EventTable;

-- Check 2: Coordinate Coverage for Maps
SELECT
  'Coordinate Coverage' as metric,
  COUNT(*) as total_places,
  COUNT(Latitude) as places_with_coords,
  ROUND(100.0 * COUNT(Latitude) / COUNT(*), 1) as coverage_percentage
FROM PlaceTable;

-- Check 3: Citation Coverage for Treemaps
SELECT
  'Citation Coverage' as metric,
  COUNT(*) as total_sources,
  COUNT(DISTINCT ct.SourceID) as sources_with_citations,
  ROUND(100.0 * COUNT(DISTINCT ct.SourceID) / COUNT(*), 1) as coverage_percentage
FROM SourceTable st
LEFT JOIN CitationTable ct ON ct.SourceID = st.SourceID;

-- Check 4: Family Relationship Coverage for Network/Chord
SELECT
  'Family Relationship Coverage' as metric,
  COUNT(*) as total_families,
  COUNT(FatherID) as families_with_father,
  COUNT(MotherID) as families_with_mother,
  ROUND(100.0 * COUNT(CASE WHEN FatherID IS NOT NULL AND MotherID IS NOT NULL THEN 1 END) / COUNT(*), 1) as complete_percentage
FROM FamilyTable;

-- Check 5: Name Coverage for All Charts
SELECT
  'Name Coverage' as metric,
  COUNT(DISTINCT p.PersonID) as total_persons,
  COUNT(DISTINCT n.OwnerID) as persons_with_names,
  ROUND(100.0 * COUNT(DISTINCT n.OwnerID) / COUNT(DISTINCT p.PersonID), 1) as coverage_percentage
FROM PersonTable p
LEFT JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1;


-- =============================================================================
-- QUICK REFERENCE: Chart Type → Data Format Mapping
-- =============================================================================

/*
CHART TYPE          | COLUMNS NEEDED                | NOTES
--------------------|-------------------------------|--------------------------------
Heatmap             | x, y, value                   | x,y are text; value is number
Bubble Map          | latitude, longitude, value    | Use Geomap visualization
Treemap             | hierarchy, value              | hierarchy uses " > " separator
Sankey              | source, target, value         | source != target
Chord               | source, target, value         | Can be symmetric
Arc Diagram         | source, target, [value]       | Value optional for weighting
Network (Nodes)     | id, title, mainStat           | mainStat for clustering/color
Network (Edges)     | id, source, target            | source/target match node ids
Dendrogram/Tree     | id, parent_id, label          | parent_id NULL for root

All charts support additional columns for tooltips and filtering.
*/
