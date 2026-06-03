# RMCitecraft Grafana Metrics Catalog

A comprehensive catalog of 110+ genealogy, research, and data quality metrics for Grafana dashboards.

## Data Sources

| Database | Path | Description |
|----------|------|-------------|
| RootsMagic | `data/Iiams.rmtree` | Primary genealogy database |
| Census DB | `~/.rmcitecraft/census.db` | Census extraction data (EAV pattern) |
| Batch State | `~/.rmcitecraft/batch_state.db` | Processing workflow state |

## Color Coding Standards

| Condition | Hex Color | Usage |
|-----------|-----------|-------|
| Complete/Good | `#73BF69` | Success states, high coverage |
| Partial/Warning | `#FADE2A` | Moderate coverage, needs attention |
| Missing/Error | `#F2495C` | Failures, missing data |
| In Progress | `#5794F2` | Active processing |
| Neutral/Info | `#8AB8FF` | Informational metrics |

## OwnerType Reference

Many RootsMagic tables use polymorphic foreign keys via `OwnerType`:

| Value | Entity |
|-------|--------|
| 0 | Person |
| 1 | Family |
| 2 | Event |
| 3 | Source |
| 4 | Citation |
| 5 | Place |
| 6 | Task |
| 7 | Name |

---

# Category A: Population & Demographics

## A01: Total Persons
**Description**: Total number of individuals in the database
**Visualization**: Stat panel (large number)
**Color**: Blue (`#5794F2`)
**Drill-down**: Link to person list table

```sql
SELECT COUNT(*) as total_persons
FROM PersonTable
```

---

## A02: Living vs Deceased Distribution
**Description**: Breakdown of living versus deceased individuals
**Visualization**: Pie chart
**Colors**: Living=Green, Deceased=Gray
**Drill-down**: Filter person list by living status

```sql
SELECT
  CASE WHEN Living = 1 THEN 'Living' ELSE 'Deceased' END as status,
  COUNT(*) as count
FROM PersonTable
GROUP BY Living
```

---

## A03: Gender Distribution
**Description**: Male/Female/Unknown breakdown
**Visualization**: Pie chart
**Colors**: Male=Blue, Female=Pink, Unknown=Gray
**Drill-down**: Filter by gender

```sql
SELECT
  CASE Sex
    WHEN 0 THEN 'Male'
    WHEN 1 THEN 'Female'
    ELSE 'Unknown'
  END as gender,
  COUNT(*) as count
FROM PersonTable
GROUP BY Sex
```

---

## A04: Birth Year Distribution
**Description**: Histogram of birth years showing generational patterns
**Visualization**: Bar chart (time series)
**Color**: Blue gradient by density
**Drill-down**: Click year to see persons born that year

```sql
SELECT
  CAST(SUBSTR(e.Date, 1, 4) AS INTEGER) as birth_year,
  COUNT(*) as count
FROM EventTable e
WHERE e.EventType = 1  -- Birth
  AND e.Date != ''
  AND CAST(SUBSTR(e.Date, 1, 4) AS INTEGER) BETWEEN 1700 AND 2024
GROUP BY birth_year
ORDER BY birth_year
```

---

## A05: Death Year Distribution
**Description**: Histogram of death years
**Visualization**: Bar chart (time series)
**Color**: Gray gradient
**Drill-down**: Click year to see persons who died that year

```sql
SELECT
  CAST(SUBSTR(e.Date, 1, 4) AS INTEGER) as death_year,
  COUNT(*) as count
FROM EventTable e
WHERE e.EventType = 2  -- Death
  AND e.Date != ''
  AND CAST(SUBSTR(e.Date, 1, 4) AS INTEGER) BETWEEN 1700 AND 2024
GROUP BY death_year
ORDER BY death_year
```

---

## A06: Birth Decade Heatmap
**Description**: Births aggregated by decade for trend analysis
**Visualization**: Heatmap
**Color**: Green gradient (more births = darker)
**Drill-down**: Decade detail

```sql
SELECT
  (CAST(SUBSTR(e.Date, 1, 4) AS INTEGER) / 10) * 10 as decade,
  COUNT(*) as count
FROM EventTable e
WHERE e.EventType = 1
  AND e.Date != ''
  AND CAST(SUBSTR(e.Date, 1, 4) AS INTEGER) BETWEEN 1700 AND 2020
GROUP BY decade
ORDER BY decade
```

---

## A07: Age at Death Statistics
**Description**: Average, median, min, max age at death
**Visualization**: Stat panels (4 values)
**Color**: Blue
**Drill-down**: Distribution histogram

```sql
WITH ages AS (
  SELECT
    p.PersonID,
    CAST(SUBSTR(d.Date, 1, 4) AS INTEGER) - CAST(SUBSTR(b.Date, 1, 4) AS INTEGER) as age_at_death
  FROM PersonTable p
  JOIN EventTable b ON p.PersonID = b.OwnerID AND b.OwnerType = 0 AND b.EventType = 1
  JOIN EventTable d ON p.PersonID = d.OwnerID AND d.OwnerType = 0 AND d.EventType = 2
  WHERE b.Date != '' AND d.Date != ''
    AND CAST(SUBSTR(b.Date, 1, 4) AS INTEGER) > 1700
    AND CAST(SUBSTR(d.Date, 1, 4) AS INTEGER) > 1700
)
SELECT
  ROUND(AVG(age_at_death), 1) as avg_age,
  MIN(age_at_death) as min_age,
  MAX(age_at_death) as max_age,
  COUNT(*) as sample_size
FROM ages
WHERE age_at_death BETWEEN 0 AND 120
```

---

## A08: Age at Death Distribution
**Description**: Histogram of ages at death
**Visualization**: Bar chart
**Color**: Gray gradient
**Drill-down**: Click age range for person list

```sql
WITH ages AS (
  SELECT
    CAST(SUBSTR(d.Date, 1, 4) AS INTEGER) - CAST(SUBSTR(b.Date, 1, 4) AS INTEGER) as age
  FROM PersonTable p
  JOIN EventTable b ON p.PersonID = b.OwnerID AND b.OwnerType = 0 AND b.EventType = 1
  JOIN EventTable d ON p.PersonID = d.OwnerID AND d.OwnerType = 0 AND d.EventType = 2
  WHERE b.Date != '' AND d.Date != ''
)
SELECT
  CASE
    WHEN age < 1 THEN 'Infant (<1)'
    WHEN age BETWEEN 1 AND 5 THEN 'Child (1-5)'
    WHEN age BETWEEN 6 AND 17 THEN 'Youth (6-17)'
    WHEN age BETWEEN 18 AND 40 THEN 'Adult (18-40)'
    WHEN age BETWEEN 41 AND 65 THEN 'Middle Age (41-65)'
    WHEN age BETWEEN 66 AND 80 THEN 'Senior (66-80)'
    WHEN age > 80 THEN 'Elderly (80+)'
    ELSE 'Unknown'
  END as age_group,
  COUNT(*) as count
FROM ages
WHERE age BETWEEN 0 AND 120
GROUP BY age_group
ORDER BY MIN(age)
```

---

## A09: Lifespan Trends by Birth Decade
**Description**: Average lifespan evolution over generations
**Visualization**: Line chart
**Color**: Green line
**Drill-down**: Decade detail

```sql
WITH lifespans AS (
  SELECT
    (CAST(SUBSTR(b.Date, 1, 4) AS INTEGER) / 10) * 10 as birth_decade,
    CAST(SUBSTR(d.Date, 1, 4) AS INTEGER) - CAST(SUBSTR(b.Date, 1, 4) AS INTEGER) as lifespan
  FROM PersonTable p
  JOIN EventTable b ON p.PersonID = b.OwnerID AND b.OwnerType = 0 AND b.EventType = 1
  JOIN EventTable d ON p.PersonID = d.OwnerID AND d.OwnerType = 0 AND d.EventType = 2
  WHERE b.Date != '' AND d.Date != ''
)
SELECT
  birth_decade,
  ROUND(AVG(lifespan), 1) as avg_lifespan,
  COUNT(*) as sample_size
FROM lifespans
WHERE lifespan BETWEEN 0 AND 120
  AND birth_decade BETWEEN 1700 AND 1950
GROUP BY birth_decade
HAVING COUNT(*) >= 5
ORDER BY birth_decade
```

---

## A10: Top 20 Surnames
**Description**: Most common surnames in database
**Visualization**: Horizontal bar chart
**Color**: Blue bars
**Drill-down**: Click surname for person list

```sql
SELECT
  n.Surname as surname,
  COUNT(*) as count
FROM NameTable n
WHERE n.IsPrimary = 1
  AND n.Surname != ''
GROUP BY n.Surname
ORDER BY count DESC
LIMIT 20
```

---

## A11: Surname Distribution by Century
**Description**: How surname frequency changes over time
**Visualization**: Stacked bar chart
**Color**: Different color per top surname
**Drill-down**: Century/surname detail

```sql
SELECT
  n.Surname,
  (CAST(SUBSTR(e.Date, 1, 4) AS INTEGER) / 100) * 100 as century,
  COUNT(*) as count
FROM NameTable n
JOIN PersonTable p ON n.OwnerID = p.PersonID
LEFT JOIN EventTable e ON p.PersonID = e.OwnerID AND e.OwnerType = 0 AND e.EventType = 1
WHERE n.IsPrimary = 1
  AND n.Surname IN (SELECT Surname FROM NameTable WHERE IsPrimary = 1 GROUP BY Surname ORDER BY COUNT(*) DESC LIMIT 10)
GROUP BY n.Surname, century
ORDER BY century, count DESC
```

---

## A12: Given Name Frequency (Male)
**Description**: Most popular male given names
**Visualization**: Word cloud or bar chart
**Color**: Blue
**Drill-down**: Name detail

```sql
SELECT
  n.Given as given_name,
  COUNT(*) as count
FROM NameTable n
JOIN PersonTable p ON n.OwnerID = p.PersonID
WHERE n.IsPrimary = 1
  AND p.Sex = 0
  AND n.Given != ''
GROUP BY n.Given
ORDER BY count DESC
LIMIT 20
```

---

## A13: Given Name Frequency (Female)
**Description**: Most popular female given names
**Visualization**: Word cloud or bar chart
**Color**: Pink
**Drill-down**: Name detail

```sql
SELECT
  n.Given as given_name,
  COUNT(*) as count
FROM NameTable n
JOIN PersonTable p ON n.OwnerID = p.PersonID
WHERE n.IsPrimary = 1
  AND p.Sex = 1
  AND n.Given != ''
GROUP BY n.Given
ORDER BY count DESC
LIMIT 20
```

---

## A14: Birthplace Geography (Top States)
**Description**: Most common birth states/regions
**Visualization**: Choropleth map or bar chart
**Color**: Blue gradient
**Drill-down**: State detail

```sql
SELECT
  pl.Name as birthplace,
  COUNT(*) as count
FROM EventTable e
JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
WHERE e.EventType = 1
  AND pl.Name != ''
GROUP BY pl.Name
ORDER BY count DESC
LIMIT 20
```

---

## A15: Immigration Indicators
**Description**: Persons with birthplace outside USA
**Visualization**: Stat panel + pie chart
**Color**: Orange
**Drill-down**: Immigrant list

```sql
SELECT
  CASE
    WHEN pl.Name LIKE '%Germany%' OR pl.Name LIKE '%German%' THEN 'Germany'
    WHEN pl.Name LIKE '%Ireland%' OR pl.Name LIKE '%Irish%' THEN 'Ireland'
    WHEN pl.Name LIKE '%England%' OR pl.Name LIKE '%English%' THEN 'England'
    WHEN pl.Name LIKE '%Scotland%' OR pl.Name LIKE '%Scottish%' THEN 'Scotland'
    WHEN pl.Name LIKE '%Wales%' OR pl.Name LIKE '%Welsh%' THEN 'Wales'
    WHEN pl.Name NOT LIKE '%USA%' AND pl.Name NOT LIKE '%United States%'
         AND pl.Name NOT LIKE '%Ohio%' AND pl.Name NOT LIKE '%Pennsylvania%'
         AND pl.Name NOT LIKE '%Virginia%' AND pl.Name NOT LIKE '%Kentucky%'
         AND pl.Name NOT LIKE '%Indiana%' AND pl.Name NOT LIKE '%Illinois%'
         THEN 'Other Foreign'
    ELSE 'USA'
  END as origin,
  COUNT(*) as count
FROM EventTable e
JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
WHERE e.EventType = 1
  AND pl.Name != ''
GROUP BY origin
ORDER BY count DESC
```

---

## A16: Persons per Generation
**Description**: Count by estimated generation (25-year spans)
**Visualization**: Bar chart
**Color**: Gradient by age
**Drill-down**: Generation member list

```sql
SELECT
  CASE
    WHEN CAST(SUBSTR(e.Date, 1, 4) AS INTEGER) < 1750 THEN 'Pre-1750'
    ELSE CAST((CAST(SUBSTR(e.Date, 1, 4) AS INTEGER) / 25) * 25 AS TEXT) || 's'
  END as generation,
  COUNT(*) as count
FROM EventTable e
WHERE e.EventType = 1
  AND e.Date != ''
GROUP BY generation
ORDER BY MIN(CAST(SUBSTR(e.Date, 1, 4) AS INTEGER))
```

---

## A17: Alternate Names Count
**Description**: Persons with multiple name records (maiden names, aliases)
**Visualization**: Stat panel
**Color**: Purple
**Drill-down**: Person list with alternates

```sql
SELECT
  CASE
    WHEN name_count = 1 THEN '1 name'
    WHEN name_count = 2 THEN '2 names'
    WHEN name_count >= 3 THEN '3+ names'
  END as category,
  COUNT(*) as person_count
FROM (
  SELECT OwnerID, COUNT(*) as name_count
  FROM NameTable
  GROUP BY OwnerID
)
GROUP BY category
```

---

## A18: Nickname Usage
**Description**: Persons with recorded nicknames
**Visualization**: Stat panel with percentage
**Color**: Teal
**Drill-down**: Nickname list

```sql
SELECT
  SUM(CASE WHEN Nickname != '' THEN 1 ELSE 0 END) as with_nickname,
  SUM(CASE WHEN Nickname = '' OR Nickname IS NULL THEN 1 ELSE 0 END) as without_nickname,
  ROUND(100.0 * SUM(CASE WHEN Nickname != '' THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_with_nickname
FROM NameTable
WHERE IsPrimary = 1
```

---

# Category B: Event Coverage

## B01: Total Events
**Description**: Total event records in database
**Visualization**: Stat panel
**Color**: Blue
**Drill-down**: Event type breakdown

```sql
SELECT COUNT(*) as total_events
FROM EventTable
```

---

## B02: Events by Type
**Description**: Distribution of event types
**Visualization**: Horizontal bar chart
**Color**: Different color per type
**Drill-down**: Event list by type

```sql
SELECT
  ft.Name as event_type,
  COUNT(*) as count
FROM EventTable e
JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
GROUP BY e.EventType, ft.Name
ORDER BY count DESC
```

---

## B03: Birth Event Coverage
**Description**: Percentage of persons with birth events
**Visualization**: Gauge (0-100%)
**Colors**: >90%=Green, 70-90%=Yellow, <70%=Red
**Drill-down**: Persons missing births

```sql
SELECT
  COUNT(DISTINCT e.OwnerID) as with_birth,
  (SELECT COUNT(*) FROM PersonTable) as total_persons,
  ROUND(100.0 * COUNT(DISTINCT e.OwnerID) / (SELECT COUNT(*) FROM PersonTable), 1) as pct_coverage
FROM EventTable e
WHERE e.EventType = 1
  AND e.OwnerType = 0
```

---

## B04: Death Event Coverage (Deceased Only)
**Description**: Percentage of deceased persons with death events
**Visualization**: Gauge (0-100%)
**Colors**: >80%=Green, 50-80%=Yellow, <50%=Red
**Drill-down**: Deceased missing death events

```sql
SELECT
  COUNT(DISTINCT e.OwnerID) as with_death,
  (SELECT COUNT(*) FROM PersonTable WHERE Living = 0) as deceased_persons,
  ROUND(100.0 * COUNT(DISTINCT e.OwnerID) /
    NULLIF((SELECT COUNT(*) FROM PersonTable WHERE Living = 0), 0), 1) as pct_coverage
FROM EventTable e
JOIN PersonTable p ON e.OwnerID = p.PersonID AND e.OwnerType = 0
WHERE e.EventType = 2
  AND p.Living = 0
```

---

## B05: Census Coverage
**Description**: Percentage of persons with at least one census event
**Visualization**: Gauge
**Colors**: Threshold-based
**Drill-down**: Persons without census

```sql
SELECT
  COUNT(DISTINCT COALESCE(e.OwnerID, w.PersonID)) as with_census,
  (SELECT COUNT(*) FROM PersonTable) as total_persons,
  ROUND(100.0 * COUNT(DISTINCT COALESCE(e.OwnerID, w.PersonID)) /
    (SELECT COUNT(*) FROM PersonTable), 1) as pct_coverage
FROM EventTable e
LEFT JOIN WitnessTable w ON e.EventID = w.EventID
WHERE e.EventType = 18
  AND e.OwnerType = 0
```

---

## B06: Marriage Event Count
**Description**: Total marriage events
**Visualization**: Stat panel
**Color**: Pink
**Drill-down**: Marriage list

```sql
SELECT COUNT(*) as marriage_count
FROM EventTable
WHERE EventType = 300  -- Marriage (check actual EventType)
```

---

## B07: Events with Dates
**Description**: Percentage of events with date information
**Visualization**: Gauge
**Colors**: >95%=Green, 80-95%=Yellow, <80%=Red
**Drill-down**: Events missing dates

```sql
SELECT
  SUM(CASE WHEN Date != '' AND Date IS NOT NULL THEN 1 ELSE 0 END) as with_date,
  COUNT(*) as total,
  ROUND(100.0 * SUM(CASE WHEN Date != '' AND Date IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_with_date
FROM EventTable
```

---

## B08: Events with Places
**Description**: Percentage of events with place information
**Visualization**: Gauge
**Colors**: Threshold-based
**Drill-down**: Events missing places

```sql
SELECT
  SUM(CASE WHEN PlaceID > 0 THEN 1 ELSE 0 END) as with_place,
  COUNT(*) as total,
  ROUND(100.0 * SUM(CASE WHEN PlaceID > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_with_place
FROM EventTable
```

---

## B09: Events per Person Statistics
**Description**: Average, min, max events per person
**Visualization**: Stat panels
**Color**: Blue
**Drill-down**: Distribution histogram

```sql
WITH person_events AS (
  SELECT OwnerID, COUNT(*) as event_count
  FROM EventTable
  WHERE OwnerType = 0
  GROUP BY OwnerID
)
SELECT
  ROUND(AVG(event_count), 1) as avg_events,
  MIN(event_count) as min_events,
  MAX(event_count) as max_events
FROM person_events
```

---

## B10: Events per Person Distribution
**Description**: Histogram of events per person
**Visualization**: Bar chart
**Color**: Blue gradient
**Drill-down**: Person list by event count

```sql
WITH person_events AS (
  SELECT OwnerID, COUNT(*) as event_count
  FROM EventTable
  WHERE OwnerType = 0
  GROUP BY OwnerID
)
SELECT
  CASE
    WHEN event_count = 1 THEN '1'
    WHEN event_count BETWEEN 2 AND 5 THEN '2-5'
    WHEN event_count BETWEEN 6 AND 10 THEN '6-10'
    WHEN event_count BETWEEN 11 AND 20 THEN '11-20'
    WHEN event_count > 20 THEN '20+'
  END as event_range,
  COUNT(*) as person_count
FROM person_events
GROUP BY event_range
ORDER BY MIN(event_count)
```

---

## B11: Shared Facts (Witnesses)
**Description**: Events shared via WitnessTable
**Visualization**: Stat panel
**Color**: Purple
**Drill-down**: Shared event list

```sql
SELECT
  COUNT(DISTINCT EventID) as events_with_witnesses,
  COUNT(*) as total_witness_records,
  (SELECT COUNT(*) FROM EventTable) as total_events,
  ROUND(100.0 * COUNT(DISTINCT EventID) / (SELECT COUNT(*) FROM EventTable), 1) as pct_shared
FROM WitnessTable
```

---

## B12: Census Events by Year
**Description**: Distribution of census records by census year
**Visualization**: Bar chart
**Color**: Blue bars
**Drill-down**: Census list by year

```sql
SELECT
  CASE
    WHEN e.Date LIKE '179%' THEN '1790'
    WHEN e.Date LIKE '180%' THEN '1800'
    WHEN e.Date LIKE '181%' THEN '1810'
    WHEN e.Date LIKE '182%' THEN '1820'
    WHEN e.Date LIKE '183%' THEN '1830'
    WHEN e.Date LIKE '184%' THEN '1840'
    WHEN e.Date LIKE '185%' THEN '1850'
    WHEN e.Date LIKE '186%' THEN '1860'
    WHEN e.Date LIKE '187%' THEN '1870'
    WHEN e.Date LIKE '188%' THEN '1880'
    WHEN e.Date LIKE '189%' THEN '1890'
    WHEN e.Date LIKE '190%' THEN '1900'
    WHEN e.Date LIKE '191%' THEN '1910'
    WHEN e.Date LIKE '192%' THEN '1920'
    WHEN e.Date LIKE '193%' THEN '1930'
    WHEN e.Date LIKE '194%' THEN '1940'
    WHEN e.Date LIKE '195%' THEN '1950'
    ELSE 'Unknown'
  END as census_year,
  COUNT(*) as count
FROM EventTable e
WHERE e.EventType = 18
GROUP BY census_year
ORDER BY census_year
```

---

## B13: Burial Event Coverage
**Description**: Deceased persons with burial events
**Visualization**: Gauge
**Colors**: Threshold-based
**Drill-down**: Deceased without burial

```sql
SELECT
  COUNT(DISTINCT e.OwnerID) as with_burial,
  (SELECT COUNT(*) FROM PersonTable WHERE Living = 0) as deceased,
  ROUND(100.0 * COUNT(DISTINCT e.OwnerID) /
    NULLIF((SELECT COUNT(*) FROM PersonTable WHERE Living = 0), 0), 1) as pct_coverage
FROM EventTable e
WHERE e.EventType = 4  -- Burial
  AND e.OwnerType = 0
```

---

## B14: Events by Decade
**Description**: Event volume over time
**Visualization**: Area chart
**Color**: Blue fill
**Drill-down**: Decade detail

```sql
SELECT
  (CAST(SUBSTR(Date, 1, 4) AS INTEGER) / 10) * 10 as decade,
  COUNT(*) as event_count
FROM EventTable
WHERE Date != ''
  AND CAST(SUBSTR(Date, 1, 4) AS INTEGER) BETWEEN 1700 AND 2020
GROUP BY decade
ORDER BY decade
```

---

## B15: Events with Notes
**Description**: Events containing note/detail text
**Visualization**: Stat panel with percentage
**Color**: Teal
**Drill-down**: Events with notes

```sql
SELECT
  SUM(CASE WHEN Note != '' THEN 1 ELSE 0 END) as with_notes,
  COUNT(*) as total,
  ROUND(100.0 * SUM(CASE WHEN Note != '' THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_with_notes
FROM EventTable
```

---

## B16: Custom Event Types
**Description**: Non-standard event types in use
**Visualization**: Table
**Color**: Orange highlights
**Drill-down**: Custom event list

```sql
SELECT
  ft.Name as event_type,
  ft.FactTypeID,
  COUNT(e.EventID) as usage_count
FROM FactTypeTable ft
LEFT JOIN EventTable e ON ft.FactTypeID = e.EventType
WHERE ft.FactTypeID > 100  -- Custom types typically have higher IDs
GROUP BY ft.FactTypeID, ft.Name
ORDER BY usage_count DESC
```

---

# Category C: Census Data

## C01: Total Census Extractions
**Description**: Total census page extractions in census.db
**Visualization**: Stat panel
**Color**: Blue
**Drill-down**: Extraction list

```sql
-- Census.db
SELECT COUNT(*) as total_extractions
FROM census_page
```

---

## C02: Census Pages by Year
**Description**: Extracted pages per census year
**Visualization**: Bar chart
**Color**: Blue bars
**Drill-down**: Year detail

```sql
-- Census.db
SELECT
  census_year,
  COUNT(*) as page_count
FROM census_page
GROUP BY census_year
ORDER BY census_year
```

---

## C03: Persons Extracted per Page
**Description**: Average household size from extractions
**Visualization**: Stat panels (avg, min, max)
**Color**: Green
**Drill-down**: Page detail

```sql
-- Census.db
SELECT
  ROUND(AVG(person_count), 1) as avg_persons,
  MIN(person_count) as min_persons,
  MAX(person_count) as max_persons
FROM (
  SELECT page_id, COUNT(*) as person_count
  FROM census_person
  GROUP BY page_id
)
```

---

## C04: Line Number Coverage
**Description**: Distribution of line numbers (1-50 for census sheets)
**Visualization**: Heatmap
**Color**: Green gradient
**Drill-down**: Line detail

```sql
-- Census.db
SELECT
  cpf.field_value as line_number,
  COUNT(*) as count
FROM census_person_field cpf
WHERE cpf.field_name = 'line_number'
GROUP BY cpf.field_value
ORDER BY CAST(cpf.field_value AS INTEGER)
```

---

## C05: Family Number Distribution
**Description**: Extracted family numbers
**Visualization**: Histogram
**Color**: Purple
**Drill-down**: Family detail

```sql
-- Census.db
SELECT
  cpf.field_value as family_number,
  COUNT(*) as count
FROM census_person_field cpf
WHERE cpf.field_name = 'family_number'
GROUP BY cpf.field_value
ORDER BY CAST(cpf.field_value AS INTEGER)
LIMIT 50
```

---

## C06: Extraction Completeness
**Description**: Pages with all required fields extracted
**Visualization**: Gauge
**Colors**: >90%=Green, <90%=Yellow
**Drill-down**: Incomplete pages

```sql
-- Census.db
WITH page_fields AS (
  SELECT
    cp.page_id,
    SUM(CASE WHEN cpf.field_name = 'enumeration_district' AND cpf.field_value != '' THEN 1 ELSE 0 END) as has_ed,
    SUM(CASE WHEN cpf.field_name = 'sheet_number' AND cpf.field_value != '' THEN 1 ELSE 0 END) as has_sheet,
    SUM(CASE WHEN cpf.field_name = 'line_number' AND cpf.field_value != '' THEN 1 ELSE 0 END) as has_line
  FROM census_person cp
  LEFT JOIN census_person_field cpf ON cp.person_id = cpf.person_id
  GROUP BY cp.page_id
)
SELECT
  SUM(CASE WHEN has_ed > 0 AND has_sheet > 0 AND has_line > 0 THEN 1 ELSE 0 END) as complete_pages,
  COUNT(*) as total_pages,
  ROUND(100.0 * SUM(CASE WHEN has_ed > 0 AND has_sheet > 0 AND has_line > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_complete
FROM page_fields
```

---

## C07: State/County Distribution
**Description**: Census records by location
**Visualization**: Treemap or bar chart
**Color**: Blue gradient
**Drill-down**: Location detail

```sql
-- Census.db
SELECT
  cp.state,
  cp.county,
  COUNT(*) as count
FROM census_page cp
WHERE cp.state != ''
GROUP BY cp.state, cp.county
ORDER BY count DESC
LIMIT 20
```

---

## C08: Enumeration Districts Processed
**Description**: Unique EDs in extractions
**Visualization**: Stat panel
**Color**: Teal
**Drill-down**: ED list

```sql
-- Census.db
SELECT COUNT(DISTINCT cpf.field_value) as unique_eds
FROM census_person_field cpf
WHERE cpf.field_name = 'enumeration_district'
  AND cpf.field_value != ''
```

---

## C09: Match Confidence Distribution
**Description**: RootsMagic match confidence scores
**Visualization**: Histogram
**Colors**: >0.8=Green, 0.5-0.8=Yellow, <0.5=Red
**Drill-down**: Match detail

```sql
-- Census.db
SELECT
  CASE
    WHEN match_score >= 0.9 THEN 'Excellent (90%+)'
    WHEN match_score >= 0.8 THEN 'Good (80-89%)'
    WHEN match_score >= 0.7 THEN 'Fair (70-79%)'
    WHEN match_score >= 0.5 THEN 'Low (50-69%)'
    ELSE 'Poor (<50%)'
  END as confidence_level,
  COUNT(*) as count
FROM census_person
WHERE match_score IS NOT NULL
GROUP BY confidence_level
ORDER BY MIN(match_score) DESC
```

---

## C10: Unmatched Census Persons
**Description**: Extracted persons without RootsMagic match
**Visualization**: Stat panel
**Color**: Red (warning)
**Drill-down**: Unmatched list

```sql
-- Census.db
SELECT
  SUM(CASE WHEN rin IS NULL OR rin = 0 THEN 1 ELSE 0 END) as unmatched,
  SUM(CASE WHEN rin IS NOT NULL AND rin > 0 THEN 1 ELSE 0 END) as matched,
  COUNT(*) as total
FROM census_person
```

---

## C11: Census Year Coverage Matrix
**Description**: Which persons appear in which census years
**Visualization**: Heatmap matrix
**Color**: Green=present, Gray=absent
**Drill-down**: Person census history

```sql
SELECT
  CASE
    WHEN e.Date LIKE '185%' THEN '1850'
    WHEN e.Date LIKE '186%' THEN '1860'
    WHEN e.Date LIKE '187%' THEN '1870'
    WHEN e.Date LIKE '188%' THEN '1880'
    WHEN e.Date LIKE '190%' THEN '1900'
    WHEN e.Date LIKE '191%' THEN '1910'
    WHEN e.Date LIKE '192%' THEN '1920'
    WHEN e.Date LIKE '193%' THEN '1930'
    WHEN e.Date LIKE '194%' THEN '1940'
  END as census_year,
  COUNT(DISTINCT COALESCE(e.OwnerID, w.PersonID)) as person_count
FROM EventTable e
LEFT JOIN WitnessTable w ON e.EventID = w.EventID
WHERE e.EventType = 18
GROUP BY census_year
ORDER BY census_year
```

---

## C12: Head of Household Count
**Description**: Census records where person is head
**Visualization**: Stat panel
**Color**: Blue
**Drill-down**: Head list

```sql
-- Census.db
SELECT COUNT(*) as head_count
FROM census_person_field
WHERE field_name = 'relationship'
  AND (field_value LIKE '%Head%' OR field_value LIKE '%Self%')
```

---

## C13: Relationship Types Distribution
**Description**: Census relationship types extracted
**Visualization**: Pie chart
**Color**: Different per relationship
**Drill-down**: Relationship list

```sql
-- Census.db
SELECT
  field_value as relationship,
  COUNT(*) as count
FROM census_person_field
WHERE field_name = 'relationship'
  AND field_value != ''
GROUP BY field_value
ORDER BY count DESC
LIMIT 15
```

---

## C14: Occupation Frequency
**Description**: Most common occupations extracted
**Visualization**: Word cloud or bar chart
**Color**: Blue
**Drill-down**: Occupation detail

```sql
-- Census.db
SELECT
  field_value as occupation,
  COUNT(*) as count
FROM census_person_field
WHERE field_name = 'occupation'
  AND field_value != ''
  AND field_value NOT IN ('None', 'N/A', '-', '')
GROUP BY field_value
ORDER BY count DESC
LIMIT 20
```

---

## C15: Birthplace Extraction Rate
**Description**: Census persons with birthplace extracted
**Visualization**: Gauge
**Colors**: Threshold-based
**Drill-down**: Missing birthplace list

```sql
-- Census.db
SELECT
  SUM(CASE WHEN cpf.field_value != '' THEN 1 ELSE 0 END) as with_birthplace,
  COUNT(DISTINCT cp.person_id) as total_persons,
  ROUND(100.0 * SUM(CASE WHEN cpf.field_value != '' THEN 1 ELSE 0 END) /
    NULLIF(COUNT(DISTINCT cp.person_id), 0), 1) as pct_with_birthplace
FROM census_person cp
LEFT JOIN census_person_field cpf ON cp.person_id = cpf.person_id
  AND cpf.field_name = 'birthplace'
```

---

## C16: Age Extraction Accuracy
**Description**: Extracted ages vs calculated ages
**Visualization**: Scatter plot
**Color**: Points colored by error magnitude
**Drill-down**: Age mismatch list

```sql
-- Requires joining census.db to RootsMagic
-- This is a conceptual query for UI implementation
SELECT
  cp.person_id,
  cpf.field_value as extracted_age,
  cp.rin,
  cpg.census_year
FROM census_person cp
JOIN census_person_field cpf ON cp.person_id = cpf.person_id
JOIN census_page cpg ON cp.page_id = cpg.page_id
WHERE cpf.field_name = 'age'
  AND cp.rin IS NOT NULL
```

---

## C17: Dwelling Number Gaps
**Description**: Missing dwelling numbers in sequence
**Visualization**: Table with gaps highlighted
**Color**: Red for gaps
**Drill-down**: Gap detail

```sql
-- Census.db
SELECT
  cpg.page_id,
  cpg.census_year,
  GROUP_CONCAT(DISTINCT cpf.field_value) as dwelling_numbers
FROM census_page cpg
JOIN census_person cp ON cpg.page_id = cp.page_id
JOIN census_person_field cpf ON cp.person_id = cpf.person_id
WHERE cpf.field_name = 'dwelling_number'
GROUP BY cpg.page_id, cpg.census_year
```

---

## C18: Multi-Page Households
**Description**: Households spanning multiple census pages
**Visualization**: Stat panel
**Color**: Orange (attention)
**Drill-down**: Multi-page list

```sql
-- Census.db
SELECT COUNT(*) as multi_page_households
FROM (
  SELECT cpf.field_value as family_num
  FROM census_person_field cpf
  JOIN census_person cp ON cpf.person_id = cp.person_id
  WHERE cpf.field_name = 'family_number'
  GROUP BY cpf.field_value
  HAVING COUNT(DISTINCT cp.page_id) > 1
)
```

---

## C19: Census Extraction Rate Over Time
**Description**: Extractions per day/week
**Visualization**: Time series
**Color**: Blue line
**Drill-down**: Daily detail

```sql
-- Census.db
SELECT
  DATE(created_at) as extraction_date,
  COUNT(*) as extractions
FROM census_page
GROUP BY DATE(created_at)
ORDER BY extraction_date
```

---

## C20: Field Completeness by Census Year
**Description**: Which fields are populated per census year
**Visualization**: Heatmap
**Color**: Green=populated, Red=missing
**Drill-down**: Year/field detail

```sql
-- Census.db
SELECT
  cpg.census_year,
  cpf.field_name,
  COUNT(*) as populated_count,
  (SELECT COUNT(DISTINCT person_id) FROM census_person cp2
   JOIN census_page cpg2 ON cp2.page_id = cpg2.page_id
   WHERE cpg2.census_year = cpg.census_year) as total_persons,
  ROUND(100.0 * COUNT(*) /
    NULLIF((SELECT COUNT(DISTINCT person_id) FROM census_person cp2
            JOIN census_page cpg2 ON cp2.page_id = cpg2.page_id
            WHERE cpg2.census_year = cpg.census_year), 0), 1) as pct_populated
FROM census_person_field cpf
JOIN census_person cp ON cpf.person_id = cp.person_id
JOIN census_page cpg ON cp.page_id = cpg.page_id
WHERE cpf.field_value != ''
GROUP BY cpg.census_year, cpf.field_name
ORDER BY cpg.census_year, field_name
```

---

## C21: FamilySearch URLs Captured
**Description**: Pages with valid FamilySearch ARK URLs
**Visualization**: Gauge
**Colors**: >95%=Green
**Drill-down**: Missing URL list

```sql
-- Census.db
SELECT
  SUM(CASE WHEN familysearch_url LIKE '%familysearch.org%' THEN 1 ELSE 0 END) as with_url,
  COUNT(*) as total,
  ROUND(100.0 * SUM(CASE WHEN familysearch_url LIKE '%familysearch.org%' THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_with_url
FROM census_page
```

---

## C22: Image ARKs Captured
**Description**: Pages with image viewer ARKs
**Visualization**: Gauge
**Colors**: Threshold-based
**Drill-down**: Missing image URL list

```sql
-- Census.db
SELECT
  SUM(CASE WHEN image_ark != '' AND image_ark IS NOT NULL THEN 1 ELSE 0 END) as with_image_ark,
  COUNT(*) as total,
  ROUND(100.0 * SUM(CASE WHEN image_ark != '' AND image_ark IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_with_image
FROM census_page
```

---

# Category D: Source & Citation Quality

## D01: Total Sources
**Description**: Total source records
**Visualization**: Stat panel
**Color**: Blue
**Drill-down**: Source list

```sql
SELECT COUNT(*) as total_sources
FROM SourceTable
```

---

## D02: Total Citations
**Description**: Total citation records
**Visualization**: Stat panel
**Color**: Blue
**Drill-down**: Citation list

```sql
SELECT COUNT(*) as total_citations
FROM CitationTable
```

---

## D03: Citations per Source Distribution
**Description**: How many citations reference each source
**Visualization**: Histogram
**Color**: Blue gradient
**Drill-down**: Source detail

```sql
SELECT
  CASE
    WHEN citation_count = 0 THEN 'Unused (0)'
    WHEN citation_count = 1 THEN '1 citation'
    WHEN citation_count BETWEEN 2 AND 5 THEN '2-5 citations'
    WHEN citation_count BETWEEN 6 AND 20 THEN '6-20 citations'
    WHEN citation_count > 20 THEN '20+ citations'
  END as range,
  COUNT(*) as source_count
FROM (
  SELECT s.SourceID, COUNT(c.CitationID) as citation_count
  FROM SourceTable s
  LEFT JOIN CitationTable c ON s.SourceID = c.SourceID
  GROUP BY s.SourceID
)
GROUP BY range
ORDER BY MIN(citation_count)
```

---

## D04: Unused Sources
**Description**: Sources with zero citations
**Visualization**: Stat panel (warning)
**Color**: Orange
**Drill-down**: Unused source list

```sql
SELECT COUNT(*) as unused_sources
FROM SourceTable s
WHERE NOT EXISTS (
  SELECT 1 FROM CitationTable c WHERE c.SourceID = s.SourceID
)
```

---

## D05: Evidence Explained Quality Codes
**Description**: Distribution of 3-character quality codes
**Visualization**: Pie chart
**Colors**: PDO=DarkGreen, PDX=Green, SDX=Yellow, ~~~=Red
**Drill-down**: Quality code detail

```sql
SELECT
  CASE
    WHEN Quality = '' OR Quality IS NULL THEN 'Unspecified'
    WHEN Quality = '~~~' THEN 'Unknown (~~~)'
    ELSE Quality
  END as quality_code,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM CitationTable), 1) as percentage
FROM CitationTable
GROUP BY quality_code
ORDER BY count DESC
```

---

## D06: Quality Code Coverage
**Description**: Citations with vs without quality codes
**Visualization**: Gauge
**Colors**: >80%=Green, <80%=Yellow
**Drill-down**: Missing quality list

```sql
SELECT
  SUM(CASE WHEN Quality != '' AND Quality IS NOT NULL AND Quality != '~~~' THEN 1 ELSE 0 END) as with_quality,
  COUNT(*) as total,
  ROUND(100.0 * SUM(CASE WHEN Quality != '' AND Quality IS NOT NULL AND Quality != '~~~' THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_with_quality
FROM CitationTable
```

---

## D07: Free-Form vs Template Sources
**Description**: Sources using templates vs free-form
**Visualization**: Pie chart
**Colors**: Free-form=Blue, Template=Green
**Drill-down**: Source type list

```sql
SELECT
  CASE WHEN TemplateID = 0 THEN 'Free-Form' ELSE 'Template' END as source_type,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM SourceTable), 1) as percentage
FROM SourceTable
GROUP BY source_type
```

---

## D08: Top Source Templates
**Description**: Most used source templates
**Visualization**: Bar chart
**Color**: Green bars
**Drill-down**: Template usage

```sql
SELECT
  st.Name as template_name,
  COUNT(s.SourceID) as usage_count
FROM SourceTable s
JOIN SourceTemplateTable st ON s.TemplateID = st.TemplateID
WHERE s.TemplateID > 0
GROUP BY s.TemplateID, st.Name
ORDER BY usage_count DESC
LIMIT 15
```

---

## D09: Sources by Repository
**Description**: Sources grouped by repository
**Visualization**: Bar chart
**Color**: Blue bars
**Drill-down**: Repository detail

```sql
SELECT
  COALESCE(r.Name, 'No Repository') as repository,
  COUNT(s.SourceID) as source_count
FROM SourceTable s
LEFT JOIN RepositoryTable r ON s.RepositoryID = r.RepositoryID
GROUP BY r.Name
ORDER BY source_count DESC
```

---

## D10: Repository Coverage
**Description**: Sources assigned to repositories
**Visualization**: Gauge
**Colors**: Threshold-based
**Drill-down**: Sources without repository

```sql
SELECT
  SUM(CASE WHEN RepositoryID > 0 THEN 1 ELSE 0 END) as with_repository,
  COUNT(*) as total,
  ROUND(100.0 * SUM(CASE WHEN RepositoryID > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_with_repository
FROM SourceTable
```

---

## D11: Citation Links by Owner Type
**Description**: What entities citations are attached to
**Visualization**: Pie chart
**Color**: Different per type
**Drill-down**: Link detail

```sql
SELECT
  CASE cl.OwnerType
    WHEN 0 THEN 'Person'
    WHEN 1 THEN 'Family'
    WHEN 2 THEN 'Event'
    WHEN 7 THEN 'Name'
    ELSE 'Other'
  END as owner_type,
  COUNT(*) as link_count
FROM CitationLinkTable cl
GROUP BY cl.OwnerType
ORDER BY link_count DESC
```

---

## D12: Events with Citations
**Description**: Percentage of events with source citations
**Visualization**: Gauge
**Colors**: >70%=Green, 50-70%=Yellow, <50%=Red
**Drill-down**: Uncited events

```sql
SELECT
  COUNT(DISTINCT cl.OwnerID) as events_with_citations,
  (SELECT COUNT(*) FROM EventTable) as total_events,
  ROUND(100.0 * COUNT(DISTINCT cl.OwnerID) / (SELECT COUNT(*) FROM EventTable), 1) as pct_cited
FROM CitationLinkTable cl
WHERE cl.OwnerType = 2
```

---

## D13: Average Citations per Event
**Description**: Citation density for events
**Visualization**: Stat panel
**Color**: Blue
**Drill-down**: Event citation counts

```sql
SELECT
  ROUND(AVG(citation_count), 2) as avg_citations_per_event
FROM (
  SELECT e.EventID, COUNT(cl.CitationID) as citation_count
  FROM EventTable e
  LEFT JOIN CitationLinkTable cl ON e.EventID = cl.OwnerID AND cl.OwnerType = 2
  GROUP BY e.EventID
)
```

---

## D14: Source Name Word Cloud Data
**Description**: Common words in source titles
**Visualization**: Word cloud
**Color**: Blue gradient
**Drill-down**: Source search

```sql
SELECT
  s.Name as source_name,
  LENGTH(s.Name) as name_length
FROM SourceTable s
WHERE s.Name != ''
ORDER BY name_length DESC
LIMIT 100
```

---

## D15: Census Source Coverage
**Description**: Census events with proper citations
**Visualization**: Gauge
**Colors**: >90%=Green
**Drill-down**: Uncited census events

```sql
SELECT
  COUNT(DISTINCT e.EventID) as census_with_citation,
  (SELECT COUNT(*) FROM EventTable WHERE EventType = 18) as total_census,
  ROUND(100.0 * COUNT(DISTINCT e.EventID) /
    NULLIF((SELECT COUNT(*) FROM EventTable WHERE EventType = 18), 0), 1) as pct_cited
FROM EventTable e
JOIN CitationLinkTable cl ON e.EventID = cl.OwnerID AND cl.OwnerType = 2
WHERE e.EventType = 18
```

---

## D16: Duplicate Source Detection
**Description**: Potential duplicate sources (similar names)
**Visualization**: Table
**Color**: Orange highlights
**Drill-down**: Merge candidates

```sql
SELECT
  s1.Name as source1,
  s2.Name as source2,
  s1.SourceID as id1,
  s2.SourceID as id2
FROM SourceTable s1
JOIN SourceTable s2 ON s1.SourceID < s2.SourceID
WHERE s1.Name = s2.Name
  OR (LENGTH(s1.Name) > 20 AND s1.Name LIKE s2.Name || '%')
LIMIT 20
```

---

## D17: Citation Age Distribution
**Description**: When citations were added (by UTCModDate)
**Visualization**: Time series
**Color**: Blue line
**Drill-down**: Date detail

```sql
SELECT
  DATE(UTCModDate / 1000, 'unixepoch') as mod_date,
  COUNT(*) as citations_modified
FROM CitationTable
WHERE UTCModDate > 0
GROUP BY mod_date
ORDER BY mod_date DESC
LIMIT 90
```

---

## D18: Source Types by Content
**Description**: Inferred source types from names
**Visualization**: Pie chart
**Color**: Different per type
**Drill-down**: Type list

```sql
SELECT
  CASE
    WHEN Name LIKE '%Census%' THEN 'Census'
    WHEN Name LIKE '%Birth%' THEN 'Vital - Birth'
    WHEN Name LIKE '%Death%' THEN 'Vital - Death'
    WHEN Name LIKE '%Marriage%' THEN 'Vital - Marriage'
    WHEN Name LIKE '%Grave%' OR Name LIKE '%Cemetery%' THEN 'Cemetery'
    WHEN Name LIKE '%Church%' OR Name LIKE '%Baptis%' THEN 'Church'
    WHEN Name LIKE '%Military%' OR Name LIKE '%War%' THEN 'Military'
    WHEN Name LIKE '%Newspaper%' THEN 'Newspaper'
    WHEN Name LIKE '%Will%' OR Name LIKE '%Probate%' THEN 'Probate'
    ELSE 'Other'
  END as source_type,
  COUNT(*) as count
FROM SourceTable
GROUP BY source_type
ORDER BY count DESC
```

---

## D19: Citation Detail Completeness
**Description**: Citations with detail text
**Visualization**: Gauge
**Colors**: Threshold-based
**Drill-down**: Incomplete citations

```sql
SELECT
  SUM(CASE WHEN CitationName != '' THEN 1 ELSE 0 END) as with_detail,
  COUNT(*) as total,
  ROUND(100.0 * SUM(CASE WHEN CitationName != '' THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_with_detail
FROM CitationTable
```

---

## D20: Sources Added by Month
**Description**: Source creation trend
**Visualization**: Bar chart
**Color**: Green bars
**Drill-down**: Monthly detail

```sql
SELECT
  strftime('%Y-%m', DATE(UTCModDate / 1000, 'unixepoch')) as month,
  COUNT(*) as sources_added
FROM SourceTable
WHERE UTCModDate > 0
GROUP BY month
ORDER BY month DESC
LIMIT 24
```

---

## D21: Multi-Repository Sources
**Description**: Sources linked to multiple repositories
**Visualization**: Stat panel
**Color**: Purple
**Drill-down**: Multi-repo sources

```sql
-- Note: RootsMagic typically has one repo per source
-- This checks for sources that might need multiple repos
SELECT COUNT(*) as sources_needing_review
FROM SourceTable
WHERE RepositoryID = 0
  AND (Name LIKE '%FamilySearch%' OR Name LIKE '%Ancestry%' OR Name LIKE '%Archives%')
```

---

## D22: Citation Quality by Source Type
**Description**: Quality code distribution per source category
**Visualization**: Stacked bar chart
**Color**: Quality-based colors
**Drill-down**: Type/quality detail

```sql
SELECT
  CASE
    WHEN s.Name LIKE '%Census%' THEN 'Census'
    WHEN s.Name LIKE '%Birth%' OR s.Name LIKE '%Death%' OR s.Name LIKE '%Marriage%' THEN 'Vital'
    WHEN s.Name LIKE '%Grave%' OR s.Name LIKE '%Cemetery%' THEN 'Cemetery'
    ELSE 'Other'
  END as source_category,
  CASE
    WHEN c.Quality IN ('PDO', 'PDX') THEN 'Primary'
    WHEN c.Quality IN ('SDO', 'SDX') THEN 'Secondary'
    WHEN c.Quality = '~~~' OR c.Quality = '' THEN 'Unspecified'
    ELSE 'Other'
  END as quality_level,
  COUNT(*) as count
FROM CitationTable c
JOIN SourceTable s ON c.SourceID = s.SourceID
GROUP BY source_category, quality_level
ORDER BY source_category, count DESC
```

---

# Category E: Media & Documentation

## E01: Total Media Files
**Description**: Total multimedia records
**Visualization**: Stat panel
**Color**: Blue
**Drill-down**: Media list

```sql
SELECT COUNT(*) as total_media
FROM MultimediaTable
```

---

## E02: Media by Type
**Description**: Distribution of media file types
**Visualization**: Pie chart
**Color**: Different per type
**Drill-down**: Type list

```sql
SELECT
  CASE
    WHEN MediaPath LIKE '%.jpg' OR MediaPath LIKE '%.jpeg' THEN 'JPEG'
    WHEN MediaPath LIKE '%.png' THEN 'PNG'
    WHEN MediaPath LIKE '%.gif' THEN 'GIF'
    WHEN MediaPath LIKE '%.pdf' THEN 'PDF'
    WHEN MediaPath LIKE '%.tif' OR MediaPath LIKE '%.tiff' THEN 'TIFF'
    WHEN MediaPath LIKE '%.doc%' THEN 'Word'
    ELSE 'Other'
  END as media_type,
  COUNT(*) as count
FROM MultimediaTable
GROUP BY media_type
ORDER BY count DESC
```

---

## E03: Media Links by Owner Type
**Description**: What entities media is attached to
**Visualization**: Pie chart
**Color**: Different per type
**Drill-down**: Link detail

```sql
SELECT
  CASE OwnerType
    WHEN 0 THEN 'Person'
    WHEN 1 THEN 'Family'
    WHEN 2 THEN 'Event'
    WHEN 3 THEN 'Source'
    WHEN 4 THEN 'Citation'
    WHEN 5 THEN 'Place'
    ELSE 'Other'
  END as owner_type,
  COUNT(*) as link_count
FROM MediaLinkTable
GROUP BY OwnerType
ORDER BY link_count DESC
```

---

## E04: Persons with Photos
**Description**: Percentage of persons with at least one photo
**Visualization**: Gauge
**Colors**: Threshold-based
**Drill-down**: Persons without photos

```sql
SELECT
  COUNT(DISTINCT ml.OwnerID) as persons_with_media,
  (SELECT COUNT(*) FROM PersonTable) as total_persons,
  ROUND(100.0 * COUNT(DISTINCT ml.OwnerID) / (SELECT COUNT(*) FROM PersonTable), 1) as pct_with_media
FROM MediaLinkTable ml
WHERE ml.OwnerType = 0
```

---

## E05: Orphaned Media
**Description**: Media files not linked to any entity
**Visualization**: Stat panel (warning)
**Color**: Orange
**Drill-down**: Orphaned file list

```sql
SELECT COUNT(*) as orphaned_media
FROM MultimediaTable m
WHERE NOT EXISTS (
  SELECT 1 FROM MediaLinkTable ml WHERE ml.MediaID = m.MediaID
)
```

---

## E06: Media per Person Distribution
**Description**: How many media files per person
**Visualization**: Histogram
**Color**: Blue gradient
**Drill-down**: Person media counts

```sql
SELECT
  CASE
    WHEN media_count = 0 THEN '0'
    WHEN media_count = 1 THEN '1'
    WHEN media_count BETWEEN 2 AND 5 THEN '2-5'
    WHEN media_count BETWEEN 6 AND 10 THEN '6-10'
    WHEN media_count > 10 THEN '10+'
  END as range,
  COUNT(*) as person_count
FROM (
  SELECT p.PersonID, COUNT(ml.MediaID) as media_count
  FROM PersonTable p
  LEFT JOIN MediaLinkTable ml ON p.PersonID = ml.OwnerID AND ml.OwnerType = 0
  GROUP BY p.PersonID
)
GROUP BY range
ORDER BY MIN(media_count)
```

---

## E07: Census Images Linked
**Description**: Census events with image attachments
**Visualization**: Gauge
**Colors**: Threshold-based
**Drill-down**: Census without images

```sql
SELECT
  COUNT(DISTINCT e.EventID) as census_with_images,
  (SELECT COUNT(*) FROM EventTable WHERE EventType = 18) as total_census,
  ROUND(100.0 * COUNT(DISTINCT e.EventID) /
    NULLIF((SELECT COUNT(*) FROM EventTable WHERE EventType = 18), 0), 1) as pct_with_images
FROM EventTable e
JOIN MediaLinkTable ml ON e.EventID = ml.OwnerID AND ml.OwnerType = 2
WHERE e.EventType = 18
```

---

## E08: Primary vs Secondary Media
**Description**: Media marked as primary for entities
**Visualization**: Pie chart
**Colors**: Primary=Green, Secondary=Gray
**Drill-down**: Primary media list

```sql
SELECT
  CASE WHEN IsPrimary = 1 THEN 'Primary' ELSE 'Secondary' END as priority,
  COUNT(*) as count
FROM MediaLinkTable
GROUP BY IsPrimary
```

---

## E09: Media Caption Coverage
**Description**: Media with descriptions/captions
**Visualization**: Gauge
**Colors**: Threshold-based
**Drill-down**: Media without captions

```sql
SELECT
  SUM(CASE WHEN Caption != '' THEN 1 ELSE 0 END) as with_caption,
  COUNT(*) as total,
  ROUND(100.0 * SUM(CASE WHEN Caption != '' THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_with_caption
FROM MultimediaTable
```

---

## E10: Media by Folder/Path
**Description**: Media organization by directory
**Visualization**: Treemap
**Color**: Blue gradient
**Drill-down**: Folder contents

```sql
SELECT
  SUBSTR(MediaPath, 1, INSTR(MediaPath || '/', '/') - 1) as folder,
  COUNT(*) as file_count
FROM MultimediaTable
WHERE MediaPath != ''
GROUP BY folder
ORDER BY file_count DESC
LIMIT 15
```

---

## E11: Missing Media Files
**Description**: Media records pointing to nonexistent files
**Visualization**: Stat panel (error)
**Color**: Red
**Drill-down**: Missing file list

```sql
-- Note: This requires filesystem access; showing records that might be missing
SELECT COUNT(*) as potentially_missing
FROM MultimediaTable
WHERE MediaPath LIKE '?%'  -- Relative paths starting with ?
  OR MediaPath = ''
```

---

## E12: Media Added Over Time
**Description**: Media additions trend
**Visualization**: Time series
**Color**: Blue line
**Drill-down**: Date detail

```sql
SELECT
  DATE(UTCModDate / 1000, 'unixepoch') as add_date,
  COUNT(*) as media_added
FROM MultimediaTable
WHERE UTCModDate > 0
GROUP BY add_date
ORDER BY add_date DESC
LIMIT 90
```

---

# Category F: Family Structure

## F01: Total Families
**Description**: Total family unit records
**Visualization**: Stat panel
**Color**: Blue
**Drill-down**: Family list

```sql
SELECT COUNT(*) as total_families
FROM FamilyTable
```

---

## F02: Marriage Status Distribution
**Description**: Families by marriage status
**Visualization**: Pie chart
**Colors**: Married=Green, Unknown=Gray
**Drill-down**: Status list

```sql
SELECT
  CASE
    WHEN FatherID > 0 AND MotherID > 0 THEN 'Both Parents'
    WHEN FatherID > 0 THEN 'Father Only'
    WHEN MotherID > 0 THEN 'Mother Only'
    ELSE 'Unknown'
  END as structure,
  COUNT(*) as count
FROM FamilyTable
GROUP BY structure
```

---

## F03: Children per Family Distribution
**Description**: Number of children in family units
**Visualization**: Histogram
**Color**: Green gradient
**Drill-down**: Family detail

```sql
SELECT
  CASE
    WHEN child_count = 0 THEN '0 children'
    WHEN child_count = 1 THEN '1 child'
    WHEN child_count BETWEEN 2 AND 4 THEN '2-4 children'
    WHEN child_count BETWEEN 5 AND 8 THEN '5-8 children'
    WHEN child_count > 8 THEN '9+ children'
  END as range,
  COUNT(*) as family_count
FROM (
  SELECT f.FamilyID, COUNT(c.ChildID) as child_count
  FROM FamilyTable f
  LEFT JOIN ChildTable c ON f.FamilyID = c.FamilyID
  GROUP BY f.FamilyID
)
GROUP BY range
ORDER BY MIN(child_count)
```

---

## F04: Average Children per Family
**Description**: Mean number of children
**Visualization**: Stat panel
**Color**: Green
**Drill-down**: Distribution

```sql
SELECT
  ROUND(AVG(child_count), 2) as avg_children
FROM (
  SELECT f.FamilyID, COUNT(c.ChildID) as child_count
  FROM FamilyTable f
  LEFT JOIN ChildTable c ON f.FamilyID = c.FamilyID
  GROUP BY f.FamilyID
)
```

---

## F05: Multiple Marriages
**Description**: Persons married more than once
**Visualization**: Bar chart
**Color**: Purple bars
**Drill-down**: Multi-marriage list

```sql
SELECT
  CASE
    WHEN marriage_count = 1 THEN '1 marriage'
    WHEN marriage_count = 2 THEN '2 marriages'
    WHEN marriage_count = 3 THEN '3 marriages'
    WHEN marriage_count >= 4 THEN '4+ marriages'
  END as category,
  COUNT(*) as person_count
FROM (
  SELECT FatherID as PersonID, COUNT(*) as marriage_count
  FROM FamilyTable
  WHERE FatherID > 0
  GROUP BY FatherID
  UNION ALL
  SELECT MotherID as PersonID, COUNT(*) as marriage_count
  FROM FamilyTable
  WHERE MotherID > 0
  GROUP BY MotherID
)
WHERE marriage_count > 1
GROUP BY category
ORDER BY MIN(marriage_count)
```

---

## F06: Parentage Completeness
**Description**: Persons with both parents identified
**Visualization**: Gauge
**Colors**: >70%=Green, <70%=Yellow
**Drill-down**: Missing parent list

```sql
SELECT
  SUM(CASE WHEN f.FatherID > 0 AND f.MotherID > 0 THEN 1 ELSE 0 END) as both_parents,
  COUNT(DISTINCT c.ChildID) as total_children,
  ROUND(100.0 * SUM(CASE WHEN f.FatherID > 0 AND f.MotherID > 0 THEN 1 ELSE 0 END) /
    NULLIF(COUNT(DISTINCT c.ChildID), 0), 1) as pct_both_parents
FROM ChildTable c
JOIN FamilyTable f ON c.FamilyID = f.FamilyID
```

---

## F07: Generational Depth
**Description**: Maximum ancestor generations traced
**Visualization**: Stat panel
**Color**: Blue
**Drill-down**: Deepest lines

```sql
-- Simplified: count persons with grandparents
WITH parents AS (
  SELECT c.ChildID, f.FatherID, f.MotherID
  FROM ChildTable c
  JOIN FamilyTable f ON c.FamilyID = f.FamilyID
)
SELECT
  SUM(CASE WHEN p2.FatherID > 0 OR p2.MotherID > 0 THEN 1 ELSE 0 END) as has_grandparents,
  COUNT(*) as total_with_parents
FROM parents p1
LEFT JOIN parents p2 ON p1.FatherID = p2.ChildID OR p1.MotherID = p2.ChildID
WHERE p1.FatherID > 0 OR p1.MotherID > 0
```

---

## F08: Sibling Groups
**Description**: Families with multiple children
**Visualization**: Stat panel
**Color**: Green
**Drill-down**: Sibling list

```sql
SELECT COUNT(*) as families_with_siblings
FROM (
  SELECT FamilyID, COUNT(*) as child_count
  FROM ChildTable
  GROUP BY FamilyID
  HAVING COUNT(*) > 1
)
```

---

## F09: Half-Sibling Relationships
**Description**: Persons sharing one parent
**Visualization**: Stat panel
**Color**: Orange
**Drill-down**: Half-sibling list

```sql
SELECT COUNT(DISTINCT c1.ChildID) as persons_with_half_siblings
FROM ChildTable c1
JOIN FamilyTable f1 ON c1.FamilyID = f1.FamilyID
JOIN FamilyTable f2 ON (f1.FatherID = f2.FatherID AND f1.MotherID != f2.MotherID)
               OR (f1.MotherID = f2.MotherID AND f1.FatherID != f2.FatherID)
JOIN ChildTable c2 ON f2.FamilyID = c2.FamilyID
WHERE c1.ChildID != c2.ChildID
```

---

## F10: Childless Families
**Description**: Family units with no children recorded
**Visualization**: Stat panel
**Color**: Gray
**Drill-down**: Childless family list

```sql
SELECT COUNT(*) as childless_families
FROM FamilyTable f
WHERE NOT EXISTS (
  SELECT 1 FROM ChildTable c WHERE c.FamilyID = f.FamilyID
)
```

---

## F11: Birth Order Distribution
**Description**: Child order within families
**Visualization**: Bar chart
**Color**: Green bars
**Drill-down**: Birth order detail

```sql
SELECT
  CASE
    WHEN RelOrder = 0 THEN 'Unknown/First'
    WHEN RelOrder BETWEEN 1 AND 3 THEN '1st-3rd'
    WHEN RelOrder BETWEEN 4 AND 6 THEN '4th-6th'
    WHEN RelOrder > 6 THEN '7th+'
  END as birth_order,
  COUNT(*) as count
FROM ChildTable
GROUP BY birth_order
ORDER BY MIN(RelOrder)
```

---

# Category G: Data Quality & Gaps

## G01: Persons Missing Birth Dates
**Description**: Persons without birth date recorded
**Visualization**: Stat panel (warning)
**Color**: Orange
**Drill-down**: Missing birth list

```sql
SELECT
  COUNT(*) as missing_birth_date
FROM PersonTable p
WHERE NOT EXISTS (
  SELECT 1 FROM EventTable e
  WHERE e.OwnerID = p.PersonID
    AND e.OwnerType = 0
    AND e.EventType = 1
    AND e.Date != ''
)
```

---

## G02: Deceased Missing Death Dates
**Description**: Deceased persons without death date
**Visualization**: Stat panel (warning)
**Color**: Orange
**Drill-down**: Missing death list

```sql
SELECT
  COUNT(*) as deceased_missing_death
FROM PersonTable p
WHERE p.Living = 0
  AND NOT EXISTS (
    SELECT 1 FROM EventTable e
    WHERE e.OwnerID = p.PersonID
      AND e.OwnerType = 0
      AND e.EventType = 2
      AND e.Date != ''
  )
```

---

## G03: Events Missing Places
**Description**: Events that should have places but don't
**Visualization**: Stat panel
**Color**: Yellow
**Drill-down**: Placeless events

```sql
SELECT
  ft.Name as event_type,
  COUNT(*) as missing_place
FROM EventTable e
JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
WHERE e.PlaceID = 0
  AND e.EventType IN (1, 2, 3, 4, 18, 300)  -- Birth, Death, Baptism, Burial, Census, Marriage
GROUP BY e.EventType, ft.Name
ORDER BY missing_place DESC
```

---

## G04: Names Without Surnames
**Description**: Name records missing surname
**Visualization**: Stat panel (warning)
**Color**: Orange
**Drill-down**: Missing surname list

```sql
SELECT COUNT(*) as missing_surname
FROM NameTable
WHERE IsPrimary = 1
  AND (Surname = '' OR Surname IS NULL)
```

---

## G05: Names Without Given Names
**Description**: Name records missing given name
**Visualization**: Stat panel (warning)
**Color**: Orange
**Drill-down**: Missing given name list

```sql
SELECT COUNT(*) as missing_given
FROM NameTable
WHERE IsPrimary = 1
  AND (Given = '' OR Given IS NULL)
```

---

## G06: Duplicate Name Detection
**Description**: Potential duplicate persons
**Visualization**: Table
**Color**: Red highlights
**Drill-down**: Merge review

```sql
SELECT
  n1.Surname,
  n1.Given,
  COUNT(*) as matches
FROM NameTable n1
JOIN NameTable n2 ON n1.Surname = n2.Surname
  AND n1.Given = n2.Given
  AND n1.OwnerID < n2.OwnerID
WHERE n1.IsPrimary = 1 AND n2.IsPrimary = 1
  AND n1.Surname != ''
GROUP BY n1.Surname, n1.Given
HAVING COUNT(*) > 0
ORDER BY COUNT(*) DESC
LIMIT 20
```

---

## G07: Living Persons Without Privacy Flag
**Description**: Living persons possibly exposed
**Visualization**: Stat panel (error)
**Color**: Red
**Drill-down**: Privacy review

```sql
SELECT COUNT(*) as living_without_privacy
FROM PersonTable
WHERE Living = 1
-- Note: RootsMagic may handle privacy differently; adjust as needed
```

---

## G08: Impossible Dates
**Description**: Dates that are logically impossible
**Visualization**: Table
**Color**: Red
**Drill-down**: Date error list

```sql
-- Death before birth
SELECT
  'Death before birth' as issue,
  COUNT(*) as count
FROM EventTable b
JOIN EventTable d ON b.OwnerID = d.OwnerID AND b.OwnerType = d.OwnerType
WHERE b.EventType = 1 AND d.EventType = 2
  AND b.Date != '' AND d.Date != ''
  AND CAST(SUBSTR(d.Date, 1, 4) AS INTEGER) < CAST(SUBSTR(b.Date, 1, 4) AS INTEGER)
```

---

## G09: Very Old Living Persons
**Description**: Living flag set for unlikely ages
**Visualization**: Table (warning)
**Color**: Orange
**Drill-down**: Review list

```sql
SELECT
  p.PersonID,
  n.Given || ' ' || n.Surname as name,
  SUBSTR(e.Date, 1, 4) as birth_year,
  2024 - CAST(SUBSTR(e.Date, 1, 4) AS INTEGER) as age
FROM PersonTable p
JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
JOIN EventTable e ON p.PersonID = e.OwnerID AND e.OwnerType = 0 AND e.EventType = 1
WHERE p.Living = 1
  AND e.Date != ''
  AND CAST(SUBSTR(e.Date, 1, 4) AS INTEGER) < 1920
ORDER BY CAST(SUBSTR(e.Date, 1, 4) AS INTEGER)
```

---

## G10: Incomplete Census Records
**Description**: Census missing key data points
**Visualization**: Table
**Color**: Yellow
**Drill-down**: Incomplete list

```sql
SELECT
  COUNT(*) as incomplete_census
FROM EventTable e
WHERE e.EventType = 18
  AND (e.Date = '' OR e.PlaceID = 0)
```

---

## G11: Uncited Vital Events
**Description**: Birth/Death/Marriage without citations
**Visualization**: Gauge
**Colors**: <30% uncited=Green
**Drill-down**: Uncited vital list

```sql
SELECT
  ft.Name as event_type,
  COUNT(*) as uncited_count
FROM EventTable e
JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
WHERE e.EventType IN (1, 2, 300)
  AND NOT EXISTS (
    SELECT 1 FROM CitationLinkTable cl
    WHERE cl.OwnerID = e.EventID AND cl.OwnerType = 2
  )
GROUP BY e.EventType, ft.Name
ORDER BY uncited_count DESC
```

---

## G12: Places Without Coordinates
**Description**: Places missing GPS coordinates
**Visualization**: Gauge
**Colors**: Threshold-based
**Drill-down**: Places to geocode

```sql
SELECT
  SUM(CASE WHEN Latitude = 0 AND Longitude = 0 THEN 1 ELSE 0 END) as no_coordinates,
  COUNT(*) as total_places,
  ROUND(100.0 * SUM(CASE WHEN Latitude = 0 AND Longitude = 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_missing
FROM PlaceTable
WHERE Name != ''
```

---

## G13: Data Completeness Score
**Description**: Overall completeness percentage
**Visualization**: Gauge (large)
**Colors**: >80%=Green, 60-80%=Yellow, <60%=Red
**Drill-down**: Completeness breakdown

```sql
SELECT
  ROUND(
    (
      -- Has birth date
      (SELECT 100.0 * COUNT(DISTINCT OwnerID) / (SELECT COUNT(*) FROM PersonTable)
       FROM EventTable WHERE EventType = 1 AND Date != '' AND OwnerType = 0)
      +
      -- Has at least one parent
      (SELECT 100.0 * COUNT(DISTINCT ChildID) / (SELECT COUNT(*) FROM PersonTable)
       FROM ChildTable)
      +
      -- Has at least one event
      (SELECT 100.0 * COUNT(DISTINCT OwnerID) / (SELECT COUNT(*) FROM PersonTable)
       FROM EventTable WHERE OwnerType = 0)
    ) / 3
  , 1) as completeness_score
```

---

## G14: Stale Data Detection
**Description**: Records not modified recently
**Visualization**: Time series
**Color**: Gray for old
**Drill-down**: Stale record list

```sql
SELECT
  CASE
    WHEN DATE(UTCModDate / 1000, 'unixepoch') > DATE('now', '-30 days') THEN 'Last 30 days'
    WHEN DATE(UTCModDate / 1000, 'unixepoch') > DATE('now', '-90 days') THEN '30-90 days'
    WHEN DATE(UTCModDate / 1000, 'unixepoch') > DATE('now', '-365 days') THEN '90-365 days'
    ELSE 'Over 1 year'
  END as age_category,
  COUNT(*) as count
FROM PersonTable
WHERE UTCModDate > 0
GROUP BY age_category
```

---

## G15: Research Notes Coverage
**Description**: Persons with research notes attached
**Visualization**: Gauge
**Colors**: Threshold-based
**Drill-down**: Persons without notes

```sql
SELECT
  SUM(CASE WHEN Note != '' THEN 1 ELSE 0 END) as with_notes,
  COUNT(*) as total,
  ROUND(100.0 * SUM(CASE WHEN Note != '' THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_with_notes
FROM PersonTable
```

---

# Category H: Processing Performance

## H01: Total Batch Sessions
**Description**: Number of processing sessions run
**Visualization**: Stat panel
**Color**: Blue
**Drill-down**: Session list

```sql
-- batch_state.db
SELECT COUNT(*) as total_sessions
FROM census_batch_sessions
```

---

## H02: Session Status Distribution
**Description**: Completed vs in-progress vs failed sessions
**Visualization**: Pie chart
**Colors**: Completed=Green, In-Progress=Blue, Failed=Red
**Drill-down**: Status list

```sql
-- batch_state.db
SELECT
  status,
  COUNT(*) as count
FROM census_batch_sessions
GROUP BY status
ORDER BY count DESC
```

---

## H03: Items Processed per Session
**Description**: Average items per batch session
**Visualization**: Stat panel
**Color**: Green
**Drill-down**: Session detail

```sql
-- batch_state.db
SELECT
  ROUND(AVG(item_count), 1) as avg_items_per_session
FROM (
  SELECT session_id, COUNT(*) as item_count
  FROM census_batch_items
  GROUP BY session_id
)
```

---

## H04: Processing Success Rate
**Description**: Percentage of items successfully processed
**Visualization**: Gauge
**Colors**: >95%=Green, 80-95%=Yellow, <80%=Red
**Drill-down**: Failed items

```sql
-- batch_state.db
SELECT
  SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) as completed,
  SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors,
  COUNT(*) as total,
  ROUND(100.0 * SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as success_rate
FROM census_batch_items
```

---

## H05: Error Types Distribution
**Description**: Types of processing errors encountered
**Visualization**: Pie chart
**Colors**: Different per error type
**Drill-down**: Error list

```sql
-- batch_state.db
SELECT
  COALESCE(error_message, 'Unknown') as error_type,
  COUNT(*) as count
FROM census_batch_items
WHERE status = 'error'
GROUP BY error_message
ORDER BY count DESC
LIMIT 10
```

---

## H06: Processing Time per Item
**Description**: Average time to process each item
**Visualization**: Stat panel + histogram
**Color**: Blue
**Drill-down**: Slow items

```sql
-- batch_state.db (if timing data available)
SELECT
  ROUND(AVG(
    (julianday(completed_at) - julianday(started_at)) * 24 * 60 * 60
  ), 2) as avg_seconds_per_item
FROM census_batch_items
WHERE completed_at IS NOT NULL AND started_at IS NOT NULL
```

---

## H07: Session Duration Trend
**Description**: How long sessions take over time
**Visualization**: Line chart
**Color**: Blue line
**Drill-down**: Session timing detail

```sql
-- batch_state.db
SELECT
  DATE(created_at) as session_date,
  ROUND(AVG(
    (julianday(updated_at) - julianday(created_at)) * 24 * 60
  ), 1) as avg_duration_minutes
FROM census_batch_sessions
WHERE updated_at IS NOT NULL
GROUP BY session_date
ORDER BY session_date DESC
LIMIT 30
```

---

## H08: Retry Success Rate
**Description**: Items that succeeded on retry
**Visualization**: Gauge
**Colors**: High=Green
**Drill-down**: Retry list

```sql
-- batch_state.db
SELECT
  SUM(CASE WHEN retry_count > 0 AND status = 'complete' THEN 1 ELSE 0 END) as retry_success,
  SUM(CASE WHEN retry_count > 0 THEN 1 ELSE 0 END) as total_retried,
  ROUND(100.0 * SUM(CASE WHEN retry_count > 0 AND status = 'complete' THEN 1 ELSE 0 END) /
    NULLIF(SUM(CASE WHEN retry_count > 0 THEN 1 ELSE 0 END), 0), 1) as retry_success_rate
FROM census_batch_items
```

---

## H09: Export Completion Rate
**Description**: Items exported to RootsMagic
**Visualization**: Gauge
**Colors**: >90%=Green
**Drill-down**: Not exported list

```sql
-- batch_state.db
SELECT
  SUM(CASE WHEN exported = 1 THEN 1 ELSE 0 END) as exported,
  SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) as completed,
  ROUND(100.0 * SUM(CASE WHEN exported = 1 THEN 1 ELSE 0 END) /
    NULLIF(SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END), 0), 1) as export_rate
FROM census_batch_items
```

---

## H10: Daily Processing Volume
**Description**: Items processed per day
**Visualization**: Bar chart
**Color**: Blue bars
**Drill-down**: Daily detail

```sql
-- batch_state.db
SELECT
  DATE(completed_at) as process_date,
  COUNT(*) as items_processed
FROM census_batch_items
WHERE status = 'complete'
GROUP BY process_date
ORDER BY process_date DESC
LIMIT 30
```

---

## H11: Peak Processing Hours
**Description**: When most processing occurs
**Visualization**: Heatmap
**Color**: Green gradient
**Drill-down**: Hour detail

```sql
-- batch_state.db
SELECT
  strftime('%H', created_at) as hour,
  COUNT(*) as session_count
FROM census_batch_sessions
GROUP BY hour
ORDER BY hour
```

---

## H12: Census Year Processing Distribution
**Description**: Which census years have been processed
**Visualization**: Bar chart
**Color**: Blue bars
**Drill-down**: Year detail

```sql
-- batch_state.db
SELECT
  census_year,
  COUNT(*) as items_processed
FROM census_batch_items
GROUP BY census_year
ORDER BY census_year
```

---

## H13: Checkpoint Recovery Rate
**Description**: Sessions recovered from checkpoints
**Visualization**: Stat panel
**Color**: Green
**Drill-down**: Recovery list

```sql
-- batch_state.db
SELECT
  SUM(CASE WHEN checkpoint_data IS NOT NULL AND checkpoint_data != '' THEN 1 ELSE 0 END) as with_checkpoint,
  COUNT(*) as total
FROM census_batch_items
```

---

## H14: Processing Throughput Over Time
**Description**: Items per hour trend
**Visualization**: Area chart
**Color**: Green fill
**Drill-down**: Throughput detail

```sql
-- batch_state.db
SELECT
  DATE(completed_at) as date,
  COUNT(*) * 1.0 /
    NULLIF(MAX(julianday(completed_at)) - MIN(julianday(completed_at)), 0) / 24 as items_per_hour
FROM census_batch_items
WHERE status = 'complete'
GROUP BY DATE(completed_at)
HAVING COUNT(*) > 5
ORDER BY date DESC
LIMIT 30
```

---

# Appendix: Dashboard Layout Recommendations

## Overview Dashboard
```
+------------------+------------------+------------------+
|   Total Persons  |  Total Events    | Total Citations  |
|      (A01)       |     (B01)        |     (D02)        |
+------------------+------------------+------------------+
|          Birth Year Distribution (A04)                 |
|          [Bar Chart - full width]                      |
+------------------+------------------+------------------+
|  Living/Deceased |  Gender Dist.    |  Birth Coverage  |
|      (A02)       |     (A03)        |     (B03)        |
+------------------+------------------+------------------+
|          Census Records by Year (B12)                  |
|          [Bar Chart - full width]                      |
+--------------------------------------------------------+
```

## Data Quality Dashboard
```
+------------------+------------------+------------------+
| Data Complete %  | Citation Quality | Missing Births   |
|      (G13)       |     (D06)        |     (G01)        |
+------------------+------------------+------------------+
|    Quality Code Distribution (D05)   |  Uncited Events  |
|    [Pie Chart]                       |     (G11)        |
+--------------------------------------+------------------+
|          Events Missing Places (G03)                   |
|          [Table]                                       |
+--------------------------------------------------------+
```

## Processing Dashboard
```
+------------------+------------------+------------------+
|  Success Rate    |  Items Today     | Active Sessions  |
|      (H04)       |     (H10)        |     (H02)        |
+------------------+------------------+------------------+
|          Processing Throughput (H14)                   |
|          [Line Chart - full width]                     |
+------------------+------------------+------------------+
|    Error Types   |  Retry Success   | Export Rate      |
|      (H05)       |     (H08)        |     (H09)        |
+------------------+------------------+------------------+
```

---

# Quick Reference: Metric IDs

| Category | ID Range | Count |
|----------|----------|-------|
| A: Population & Demographics | A01-A18 | 18 |
| B: Event Coverage | B01-B16 | 16 |
| C: Census Data | C01-C22 | 22 |
| D: Source & Citation Quality | D01-D22 | 22 |
| E: Media & Documentation | E01-E12 | 12 |
| F: Family Structure | F01-F11 | 11 |
| G: Data Quality & Gaps | G01-G15 | 15 |
| H: Processing Performance | H01-H14 | 14 |
| **Total** | | **130** |

---

*Generated: 2024-12-13*
