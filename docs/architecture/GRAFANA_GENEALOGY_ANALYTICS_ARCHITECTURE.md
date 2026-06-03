# Grafana Genealogy Analytics Architecture

## Executive Summary

This document analyzes the feasibility of implementing 10 advanced chart types for genealogy analytics using Grafana, evaluates the existing Grafana setup, and provides a phased implementation plan.

**Verdict**: 8 out of 10 recommended chart types can be implemented in Grafana (6 excellent, 2 good, 2 requires workarounds).

---

## Current Grafana Setup

### Infrastructure
- **Platform**: Grafana OSS (latest) via Docker Compose
- **SQLite Plugin**: frser-sqlite-datasource (installed)
- **Location**: `./metrics/` directory
- **Port**: 3000 (localhost:3000)

### Data Sources
1. **RootsMagic** (`rootsmagic_clean.db`) - Main genealogy database (RMNOCASE collation stripped)
2. **CensusDB** (`census.db`) - Census extraction data (EAV pattern)
3. **BatchStateDB** (`batch_state.db`) - Processing state tracking

### Current Visualizations in Use
- Stat panels (counts, metrics)
- Gauge charts (progress, quality scores)
- Bar charts (categorical comparisons)
- Pie charts (distributions)
- Geomap (geographic markers - already working!)
- Time series (temporal trends)
- Tables (detailed listings)

### Database Preparation Process
The `prepare_grafana_db.py` script:
- Copies RootsMagic database
- Strips RMNOCASE collation (Grafana doesn't support ICU extension)
- Creates Grafana-compatible schema
- Sets proper permissions for Docker container

---

## Chart Type Feasibility Analysis

### ✅ Excellent Support (Native or Proven Plugins)

#### 1. **Heatmap** - Temporal Event Patterns
- **Status**: ✅ Built-in (native Grafana visualization)
- **Complexity**: LOW
- **Use Case**: Birth seasonality, census coverage matrix, research completeness
- **Data Format**: 3 columns (x_axis, y_axis, value)
- **SQL Example**:
```sql
SELECT
  strftime('%Y', BirthDate) as decade,
  CAST(strftime('%m', BirthDate) AS INTEGER) as month,
  COUNT(*) as birth_count
FROM EventTable
WHERE EventType = 1  -- Birth events
GROUP BY decade, month
```

#### 2. **Bubble Map** - Geographic Distribution
- **Status**: ✅ Built-in Geomap (already in use!)
- **Complexity**: LOW
- **Use Case**: Ancestral hotspots, cemetery locations, immigration ports
- **Data Format**: latitude, longitude, value (bubble size), label
- **SQL Example**:
```sql
SELECT
  p.Latitude,
  p.Longitude,
  COUNT(DISTINCT e.OwnerID) as ancestor_count,
  p.PlaceName as location
FROM PlaceTable p
JOIN EventTable e ON e.PlaceID = p.PlaceID
WHERE p.Latitude IS NOT NULL
GROUP BY p.PlaceID
```

#### 3. **Treemap** - Source Citation Coverage
- **Status**: ✅ Plugin available ([marcusolsson-treemap-panel](https://grafana.com/grafana/plugins/marcusolsson-treemap-panel/))
- **Complexity**: MEDIUM
- **Use Case**: Citation coverage by branch, record type distribution
- **Data Format**: hierarchical path, value
- **SQL Example**:
```sql
SELECT
  st.Name || ' > ' || ct.CitationType as hierarchy,
  COUNT(*) as citation_count
FROM SourceTable st
JOIN CitationTable ct ON ct.SourceID = st.SourceID
GROUP BY st.SourceID, ct.CitationType
```

#### 4. **Sankey Diagram** - Migration Flow
- **Status**: ✅ Plugin available ([netsage-sankey-panel](https://grafana.com/grafana/plugins/netsage-sankey-panel/))
- **Complexity**: MEDIUM
- **Use Case**: Multi-generational migration, occupational evolution, religious transitions
- **Data Format**: source, target, value
- **SQL Example**:
```sql
-- Migration from birthplace to death place by generation
SELECT
  birth_place.PlaceName as source,
  death_place.PlaceName as target,
  COUNT(*) as flow_count
FROM PersonTable p
JOIN EventTable birth ON birth.OwnerID = p.PersonID AND birth.EventType = 1
JOIN EventTable death ON death.OwnerID = p.PersonID AND death.EventType = 2
JOIN PlaceTable birth_place ON birth.PlaceID = birth_place.PlaceID
JOIN PlaceTable death_place ON death.PlaceID = death_place.PlaceID
WHERE birth_place.PlaceID != death_place.PlaceID
GROUP BY birth_place.PlaceName, death_place.PlaceName
HAVING flow_count > 2
```

#### 5. **Chord Diagram** - Inter-Family Marriage Patterns
- **Status**: ✅ Plugin available ([esnet-chord-panel](https://grafana.com/grafana/plugins/esnet-chord-panel/))
- **Complexity**: MEDIUM
- **Use Case**: Surname intermarriage frequency, community endogamy
- **Data Format**: source, target, value (requires 2 data fields + metric)
- **SQL Example**:
```sql
-- Surname intermarriage matrix
SELECT
  father_name.Surname as source,
  mother_name.Surname as target,
  COUNT(*) as marriage_count
FROM FamilyTable f
JOIN NameTable father_name ON father_name.OwnerID = f.FatherID AND father_name.IsPrimary = 1
JOIN NameTable mother_name ON mother_name.OwnerID = f.MotherID AND mother_name.IsPrimary = 1
WHERE father_name.Surname != mother_name.Surname
GROUP BY father_name.Surname, mother_name.Surname
HAVING marriage_count >= 2
ORDER BY marriage_count DESC
```

#### 6. **Arc Diagram** - Lifespan Overlaps
- **Status**: ✅ Plugin available ([esnet-arcdiagram-panel](https://grafana.com/grafana/plugins/esnet-arcdiagram-panel/))
- **Complexity**: MEDIUM-HIGH
- **Use Case**: Generational overlap, who could have known whom, oral history chains
- **Data Format**: source, destination, optional weight, optional cluster fields
- **SQL Example**:
```sql
-- People who overlapped in life (birth before death of elder)
WITH lifespans AS (
  SELECT
    p.PersonID,
    n.Given || ' ' || n.Surname as full_name,
    birth.Date as birth_date,
    death.Date as death_date
  FROM PersonTable p
  JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
  LEFT JOIN EventTable birth ON birth.OwnerID = p.PersonID AND birth.EventType = 1
  LEFT JOIN EventTable death ON death.OwnerID = p.PersonID AND death.EventType = 2
  WHERE birth.Date IS NOT NULL
)
SELECT
  elder.full_name as source,
  younger.full_name as target,
  (julianday(elder.death_date) - julianday(younger.birth_date)) / 365.25 as overlap_years
FROM lifespans elder
JOIN lifespans younger ON younger.birth_date < elder.death_date
WHERE elder.birth_date < younger.birth_date
  AND elder.death_date IS NOT NULL
  AND overlap_years > 5
ORDER BY overlap_years DESC
LIMIT 100
```

### ⚠️ Good Support (Requires Adaptation)

#### 7. **Network Chart** - Family Relationship Web
- **Status**: ⚠️ Built-in Node Graph (requires edge data) + [esnet-networkmap-panel](https://grafana.com/grafana/plugins/esnet-networkmap-panel/)
- **Complexity**: HIGH
- **Use Case**: Intermarriage networks, DNA match clusters, witness relationships
- **Challenge**: Requires nodes + edges format; may need JSON transformation
- **Data Format**: Separate queries for nodes and edges
- **SQL Examples**:
```sql
-- NODES query
SELECT
  p.PersonID as id,
  n.Given || ' ' || n.Surname as title,
  n.Surname as mainStat,
  n.Surname as arc__family  -- for clustering
FROM PersonTable p
JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
LIMIT 500

-- EDGES query
SELECT
  f.FatherID || '--' || f.MotherID as id,
  f.FatherID as source,
  f.MotherID as target,
  'marriage' as mainStat
FROM FamilyTable f
WHERE f.FatherID IS NOT NULL AND f.MotherID IS NOT NULL
```

#### 8. **Dendrogram** - Enhanced Pedigree View
- **Status**: ⚠️ Plugins available ([equansdatahub-tree-panel](https://grafana.com/grafana/plugins/equansdatahub-tree-panel/), [pgillich-tree-panel](https://grafana.com/grafana/plugins/pgilglich-tree-panel/))
- **Complexity**: HIGH
- **Use Case**: Interactive pedigree, descendant charts, surname lineage
- **Challenge**: Requires hierarchical data format (Node ID, Parent ID, Node Label)
- **Data Format**: id, parent_id, label
- **SQL Example**:
```sql
-- Pedigree chart (ancestors of person 1)
WITH RECURSIVE ancestors AS (
  -- Start with the person of interest
  SELECT
    1 as PersonID,
    NULL as ParentID,
    (SELECT Given || ' ' || Surname FROM NameTable WHERE OwnerID = 1 AND IsPrimary = 1) as full_name,
    0 as generation

  UNION ALL

  -- Recursively get parents
  SELECT
    CASE
      WHEN anc.generation % 2 = 0 THEN f.FatherID
      ELSE f.MotherID
    END as PersonID,
    anc.PersonID as ParentID,
    (SELECT Given || ' ' || Surname FROM NameTable n
     WHERE n.OwnerID = CASE WHEN anc.generation % 2 = 0 THEN f.FatherID ELSE f.MotherID END
     AND n.IsPrimary = 1) as full_name,
    anc.generation + 1 as generation
  FROM ancestors anc
  JOIN FamilyTable f ON f.FamilyID = (SELECT FatherID FROM PersonTable WHERE PersonID = anc.PersonID)
  WHERE generation < 5
)
SELECT PersonID as id, ParentID as parent_id, full_name as label
FROM ancestors
WHERE PersonID IS NOT NULL
```

### ❌ Not Available (Workarounds Required)

#### 9. **Circular Packing** - Nested Family Structure
- **Status**: ❌ No Grafana plugin available
- **Complexity**: N/A
- **Alternative**: Use Treemap panel (similar hierarchical visualization with rectangles instead of circles)
- **Recommendation**: Implement in separate React app if critical

#### 10. **Ridgeline Chart** - Generational Distribution Comparison
- **Status**: ❌ No Grafana plugin available
- **Complexity**: N/A
- **Alternative**: Use multiple overlapping histograms or density plots
- **Recommendation**: Implement in separate React app if critical

---

## Implementation Architecture

### Phase 1: Foundation (Week 1)
**Objective**: Set up plugin infrastructure and validate existing data sources

**Tasks**:
1. Install required plugins via Grafana Plugin Catalog (not CLI, per 2026 changes)
2. Create test dashboard for plugin validation
3. Document SQL query patterns for each chart type
4. Create data transformation utilities for complex formats

**Plugin Installation** (via Grafana UI: Administration → Plugins → Search):
```bash
# Note: As of Feb 2026, install via Grafana UI Plugin Catalog, not CLI

# Required plugins:
# - netsage-sankey-panel (Sankey diagrams)
# - marcusolsson-treemap-panel (Treemaps)
# - esnet-chord-panel (Chord diagrams)
# - esnet-arcdiagram-panel (Arc diagrams)
# - esnet-networkmap-panel (Network graphs)
# - equansdatahub-tree-panel (Tree/Dendrogram)
```

**Validation Queries**:
```sql
-- Test heatmap data format
SELECT 'test' as x, 'test' as y, 1 as value

-- Test Sankey data format
SELECT 'source' as source, 'target' as target, 10 as value

-- Test node graph format
SELECT 1 as id, 'Node 1' as title, 'group1' as mainStat
```

**Deliverables**:
- Updated `docker-compose.yml` with plugin list in GF_INSTALL_PLUGINS
- Test dashboard: `genealogy_analytics_test.json`
- Documentation: `GRAFANA_SQL_PATTERNS.md`

### Phase 2: Simple Charts (Week 2)
**Objective**: Implement charts with straightforward SQL queries

**Charts to implement**:
1. ✅ **Heatmap**: Birth Seasonality Matrix
   - Dashboard: `temporal_patterns.json`
   - Panel: "Birth Patterns by Month and Decade"
   - SQL: Group births by strftime('%Y') and strftime('%m')

2. ✅ **Bubble Map**: Ancestral Hotspots
   - Dashboard: `geographic_distribution.json`
   - Panel: "Ancestor Distribution Map"
   - SQL: PlaceTable coordinates with COUNT(PersonID) as bubble size
   - Note: Geomap already working in current setup!

3. ✅ **Treemap**: Citation Coverage
   - Dashboard: `research_quality.json`
   - Panel: "Citation Coverage by Record Type"
   - SQL: Hierarchical path from SourceTable + CitationTable

**Testing**:
- Verify data loads correctly for each chart
- Test with surname filter variable: `$surname`
- Validate tooltips show meaningful information
- Test export functionality

**Deliverables**:
- 3 new dashboards with documented panels
- SQL query library for each chart type
- Screenshots for documentation

### Phase 3: Flow Charts (Week 3)
**Objective**: Implement Sankey, Chord, and Arc diagrams

**Charts to implement**:
4. ✅ **Sankey**: Migration Patterns
   - Dashboard: `migration_analysis.json`
   - Panel: "Multi-Generational Migration Flows"
   - SQL: Birth place → residence → death place chains
   - Variables: generation filter, minimum flow threshold

5. ✅ **Chord**: Surname Intermarriage
   - Dashboard: `family_connections.json`
   - Panel: "Surname Marriage Network"
   - SQL: FamilyTable joined with father/mother surnames
   - Filter: Minimum 2 marriages between surname pairs

6. ✅ **Arc**: Lifespan Overlaps
   - Dashboard: `temporal_relationships.json`
   - Panel: "Who Could Have Known Whom"
   - SQL: Lifespan overlap calculation with julianday()
   - Interactive: Click person to highlight connections

**Complexity Considerations**:
- Sankey requires careful flow aggregation (avoid duplicate paths)
- Chord needs symmetric matrix preparation
- Arc diagram benefits from date quality validation

**Deliverables**:
- 3 flow-based dashboards
- Data quality report: "Flow Chart Data Gaps"
- User guide: "Interpreting Flow Visualizations"

### Phase 4: Network & Tree Charts (Week 4)
**Objective**: Implement complex relationship visualizations

**Charts to implement**:
7. ⚠️ **Network Graph**: Family Relationship Web
   - Dashboard: `relationship_network.json`
   - Panel: "Family Intermarriage Network"
   - Challenge: Requires TWO queries (nodes + edges)
   - Solution: Use transformation or create VIEW in database
   - SQL Pattern:
     ```sql
     -- Create view for network data
     CREATE VIEW family_network_nodes AS ...
     CREATE VIEW family_network_edges AS ...
     ```

8. ⚠️ **Dendrogram**: Interactive Pedigree
   - Dashboard: `pedigree_explorer.json`
   - Panel: "5-Generation Ancestor Tree"
   - Challenge: Recursive CTE for ancestor traversal
   - Variables: Root person selector
   - Limit: 5 generations (performance constraint)

**Technical Challenges**:
- Node Graph plugin expects specific JSON structure
- May need to use Grafana transformations (e.g., "Prepare time series" → "Graph")
- Consider creating materialized views for performance

**Deliverables**:
- 2 relationship dashboards
- Database views for network data
- Performance optimization guide

### Phase 5: Advanced Features (Week 5+)
**Objective**: Polish, interactivity, and integration

**Enhancements**:
1. **Dashboard Variables**:
   - Surname filter (dropdown)
   - Generation range (slider)
   - Date range filter
   - Minimum connection threshold

2. **Cross-Dashboard Linking**:
   - Click person in network → open pedigree dashboard
   - Click location in map → show migration flows from that location
   - Click surname in chord → filter all dashboards by that surname

3. **Data Quality Integration**:
   - Show data completeness overlays
   - Highlight unreliable date estimates
   - Badge for verified vs. unverified connections

4. **Export & Sharing**:
   - Snapshot generation for reports
   - PDF export with annotations
   - Public dashboard (anonymous access) for family sharing

**Monitoring & Maintenance**:
- Query performance monitoring
- Dashboard usage analytics
- Regular data refresh from RootsMagic working copy

**Deliverables**:
- Master dashboard: `genealogy_analytics_hub.json`
- User guide: "Grafana Analytics for Genealogists"
- Video walkthrough (screen recording)

---

## Database Optimization

### Recommended Views for Performance

```sql
-- Pre-computed person summary
CREATE VIEW person_summary AS
SELECT
  p.PersonID,
  n.Given || ' ' || n.Surname as full_name,
  n.Surname,
  birth.Date as birth_date,
  death.Date as death_date,
  birth_place.PlaceName as birth_place,
  death_place.PlaceName as death_place,
  CAST((julianday(death.Date) - julianday(birth.Date)) / 365.25 AS INTEGER) as lifespan_years
FROM PersonTable p
JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
LEFT JOIN EventTable birth ON birth.OwnerID = p.PersonID AND birth.EventType = 1
LEFT JOIN EventTable death ON death.OwnerID = p.PersonID AND death.EventType = 2
LEFT JOIN PlaceTable birth_place ON birth.PlaceID = birth_place.PlaceID
LEFT JOIN PlaceTable death_place ON death.PlaceID = death_place.PlaceID;

-- Pre-computed family connections
CREATE VIEW family_connections AS
SELECT
  f.FamilyID,
  f.FatherID,
  f.MotherID,
  father_name.Given || ' ' || father_name.Surname as father_name,
  father_name.Surname as father_surname,
  mother_name.Given || ' ' || mother_name.Surname as mother_name,
  mother_name.Surname as mother_surname,
  marriage.Date as marriage_date,
  marriage_place.PlaceName as marriage_place
FROM FamilyTable f
LEFT JOIN NameTable father_name ON father_name.OwnerID = f.FatherID AND father_name.IsPrimary = 1
LEFT JOIN NameTable mother_name ON mother_name.OwnerID = f.MotherID AND mother_name.IsPrimary = 1
LEFT JOIN EventTable marriage ON marriage.OwnerID = f.FamilyID AND marriage.EventType = 300 AND marriage.OwnerType = 1
LEFT JOIN PlaceTable marriage_place ON marriage.PlaceID = marriage_place.PlaceID;

-- Pre-computed citation quality
CREATE VIEW citation_quality AS
SELECT
  st.SourceID,
  st.Name as source_name,
  COUNT(DISTINCT ct.CitationID) as citation_count,
  COUNT(DISTINCT ml.MediaID) as media_count,
  CASE
    WHEN st.TemplateID = 0 THEN 'Free-Form'
    ELSE 'Template-Based'
  END as citation_type
FROM SourceTable st
LEFT JOIN CitationTable ct ON ct.SourceID = st.SourceID
LEFT JOIN MediaLinkTable ml ON ml.OwnerID = st.SourceID AND ml.OwnerType = 3
GROUP BY st.SourceID;
```

### Indexes for Query Performance

```sql
-- Add to prepare_grafana_db.py after table creation
CREATE INDEX IF NOT EXISTS idx_event_ownerid ON EventTable(OwnerID);
CREATE INDEX IF NOT EXISTS idx_event_type ON EventTable(EventType);
CREATE INDEX IF NOT EXISTS idx_event_placeid ON EventTable(PlaceID);
CREATE INDEX IF NOT EXISTS idx_name_ownerid ON NameTable(OwnerID);
CREATE INDEX IF NOT EXISTS idx_name_isprimary ON NameTable(IsPrimary);
CREATE INDEX IF NOT EXISTS idx_place_coords ON PlaceTable(Latitude, Longitude);
CREATE INDEX IF NOT EXISTS idx_citation_sourceid ON CitationTable(SourceID);
CREATE INDEX IF NOT EXISTS idx_family_father ON FamilyTable(FatherID);
CREATE INDEX IF NOT EXISTS idx_family_mother ON FamilyTable(MotherID);
```

---

## Alternative: React Graph Gallery Integration

### When to Use React Instead of Grafana

**Use React Graph Gallery** if you need:
- Circular Packing (no Grafana plugin)
- Ridgeline Charts (no Grafana plugin)
- Highly customized interactivity (click → drill-down → filter → animate)
- Embedded analytics in RMCitecraft UI
- Real-time updates during batch processing

### Hybrid Architecture Option

**Approach**: Embed Grafana dashboards in RMCitecraft NiceGUI interface using iframes

**Benefits**:
- Best of both worlds: Grafana's SQL queries + React's custom charts
- Unified user experience (no separate Grafana login)
- RMCitecraft can pass context variables (surname, PersonID) to Grafana
- Maintain all genealogy tools in one interface

**Implementation**:
```python
# In src/rmcitecraft/ui/tabs/analytics_tab.py

from nicegui import ui

class AnalyticsTab:
    def __init__(self, parent_container):
        with parent_container:
            ui.label("Genealogy Analytics").classes('text-2xl font-bold')

            with ui.tabs() as tabs:
                tab_overview = ui.tab('Overview')
                tab_migration = ui.tab('Migration')
                tab_network = ui.tab('Networks')
                tab_custom = ui.tab('Custom Charts')

            with ui.tab_panels(tabs, value=tab_overview):
                with ui.tab_panel(tab_overview):
                    # Embed Grafana dashboard
                    ui.html('''
                        <iframe
                            src="http://localhost:3000/d/genealogy-overview?orgId=1&kiosk"
                            width="100%"
                            height="800px"
                            frameborder="0">
                        </iframe>
                    ''')

                with ui.tab_panel(tab_custom):
                    # React Graph Gallery charts (circular packing, ridgeline)
                    self.render_custom_charts()

    def render_custom_charts(self):
        # Use NiceGUI + JavaScript to render React components
        # Or use Plotly (Python library) for interactive charts
        import plotly.graph_objects as go

        fig = go.Figure()
        # ... build custom chart
        ui.plotly(fig)
```

**Configuration**:
```yaml
# docker-compose.yml - enable embedding
environment:
  - GF_SECURITY_ALLOW_EMBEDDING=true
  - GF_AUTH_ANONYMOUS_ENABLED=true
  - GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer  # Read-only for embedded views
```

---

## Cost-Benefit Analysis

### Grafana-Only Approach

**Pros**:
- ✅ 8 out of 10 charts fully supported
- ✅ Existing infrastructure (already running)
- ✅ SQL-based (no data export required)
- ✅ Real-time queries on live data
- ✅ Built-in authentication, sharing, snapshots
- ✅ Low maintenance (Docker Compose)

**Cons**:
- ❌ Missing 2 chart types (circular packing, ridgeline)
- ❌ Plugin ecosystem less mature than React
- ❌ Complex data transformations in SQL
- ❌ Separate UI from RMCitecraft main app

**Estimated Effort**: 4-5 weeks

---

### React Graph Gallery Approach

**Pros**:
- ✅ All 10 chart types available
- ✅ Highly customizable interactions
- ✅ Modern, beautiful defaults
- ✅ Can embed in RMCitecraft UI
- ✅ Direct database access (no API needed)

**Cons**:
- ❌ Requires building 10 separate components
- ❌ Data fetching layer (Python → JSON → React)
- ❌ State management complexity
- ❌ Higher maintenance burden
- ❌ No built-in dashboard framework

**Estimated Effort**: 8-10 weeks

---

### Recommended: Hybrid Approach

**Architecture**:
1. **Grafana for 8 core charts** (Sankey, Chord, Arc, Network, Dendrogram, Treemap, Heatmap, Bubble Map)
2. **Plotly (Python) for 2 missing charts** (Circular Packing, Ridgeline) embedded in NiceGUI
3. **Grafana iframes** in RMCitecraft analytics tab for unified UX

**Benefits**:
- ✅ All 10 chart types covered
- ✅ Leverage existing Grafana work
- ✅ Minimal React development (use Plotly instead)
- ✅ Unified user experience
- ✅ Fast implementation (5-6 weeks)

**Implementation Priority**:
1. Phase 1-4: Build 8 Grafana charts (4 weeks)
2. Phase 5: Add Plotly charts to RMCitecraft UI (1 week)
3. Phase 6: Embed Grafana dashboards in NiceGUI (1 week)

---

## Quick Start Commands

```bash
# Start Grafana
cd metrics
docker-compose up -d

# Prepare database (after updating RootsMagic data)
uv run python prepare_grafana_db.py

# Access Grafana
open http://localhost:3000

# Install plugins (via UI after Feb 2026)
# Navigate to: Administration → Plugins and data → Plugins
# Search and install:
# - Sankey Panel (netsage-sankey-panel)
# - Chord Panel (esnet-chord-panel)
# - Arc Diagram (esnet-arcdiagram-panel)
# - Treemap (marcusolsson-treemap-panel)
# - Network Map (esnet-networkmap-panel)
# - Interactive Tree (equansdatahub-tree-panel)

# View logs
docker logs -f rmcitecraft-grafana

# Restart after plugin install
docker-compose restart
```

---

## Data Quality Considerations

### Chart-Specific Data Requirements

| Chart | Required Data | Data Quality Impact | Mitigation |
|-------|--------------|---------------------|------------|
| Heatmap | Date precision (month/year) | Missing months → gaps | Group by quarter if needed |
| Bubble Map | Latitude/Longitude | Missing coords → no display | Geocode PlaceTable offline |
| Treemap | Hierarchical structure | Flat data → single level | Create synthetic hierarchy |
| Sankey | Source→Target pairs | Self-loops → visual clutter | Filter WHERE source != target |
| Chord | Symmetric relationships | One-way data → asymmetric | Handle in SQL with UNION |
| Arc | Date ranges (birth/death) | Missing dates → no overlap | Estimate dates if quality flag set |
| Network | Person IDs + relationships | Orphan nodes → disconnected | Filter by connection count |
| Dendrogram | Parent-child links | Missing parents → truncated tree | Show "Unknown" placeholders |

### Pre-Visualization Data Validation

Add to `prepare_grafana_db.py`:

```python
def validate_chart_data(conn):
    """Run data quality checks before dashboard use."""
    cursor = conn.cursor()

    # Check 1: Date coverage for temporal charts
    cursor.execute("""
        SELECT
            COUNT(*) as total_events,
            COUNT(Date) as events_with_dates,
            ROUND(100.0 * COUNT(Date) / COUNT(*), 1) as date_coverage_pct
        FROM EventTable
    """)
    print("Date Coverage:", cursor.fetchone())

    # Check 2: Geographic coverage for maps
    cursor.execute("""
        SELECT
            COUNT(*) as total_places,
            COUNT(Latitude) as places_with_coords,
            ROUND(100.0 * COUNT(Latitude) / COUNT(*), 1) as coord_coverage_pct
        FROM PlaceTable
    """)
    print("Coordinate Coverage:", cursor.fetchone())

    # Check 3: Citation coverage for treemaps
    cursor.execute("""
        SELECT
            COUNT(*) as total_sources,
            COUNT(DISTINCT ct.SourceID) as sources_with_citations,
            ROUND(100.0 * COUNT(DISTINCT ct.SourceID) / COUNT(*), 1) as citation_coverage_pct
        FROM SourceTable st
        LEFT JOIN CitationTable ct ON ct.SourceID = st.SourceID
    """)
    print("Citation Coverage:", cursor.fetchone())
```

---

## Security & Privacy

### Grafana Configuration for Family Sharing

**Scenario**: Share analytics dashboards with extended family while protecting sensitive data.

**Approach 1: Anonymous Read-Only Access** (current setup)
```yaml
# docker-compose.yml
environment:
  - GF_AUTH_ANONYMOUS_ENABLED=true
  - GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer  # Read-only
```

**Approach 2: User Authentication**
```yaml
# For named user access
environment:
  - GF_AUTH_ANONYMOUS_ENABLED=false
  - GF_SECURITY_ADMIN_USER=admin
  - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}  # Use .env
```

**Data Filtering**:
```sql
-- Add privacy filters to queries
WHERE p.Living = 0  -- Exclude living people

-- Or use date-based filter (100-year rule)
WHERE (julianday('now') - julianday(birth.Date)) / 365.25 > 100
```

**Network Security**:
- Run Grafana on localhost only (no external port exposure)
- Use Tailscale/VPN for remote family access
- Export static snapshots for sharing (no live database access)

---

## Monitoring & Maintenance

### Dashboard Health Checks

```bash
# Check if Grafana is running
docker ps | grep rmcitecraft-grafana

# Verify database accessibility
docker exec rmcitecraft-grafana \
  sqlite3 /var/lib/grafana/data/rootsmagic_clean.db "SELECT COUNT(*) FROM PersonTable"

# Check plugin status
docker exec rmcitecraft-grafana \
  grafana-cli plugins ls

# Monitor query performance
# (Add to Grafana provisioning)
```

### Refresh Cadence

| Data Source | Refresh Frequency | Method | Notes |
|-------------|------------------|--------|-------|
| RootsMagic DB | Weekly | Manual `prepare_grafana_db.py` | After batch processing |
| CensusDB | Daily | Auto-copy on startup | If using census transcription |
| BatchStateDB | Real-time | Volume mount | Live processing state |

### Backup Strategy

```bash
# Backup dashboards
cp -r ./metrics/dashboards ./metrics/dashboards.backup.$(date +%Y%m%d)

# Backup data
cp ./metrics/data/rootsmagic_clean.db ./metrics/data/rootsmagic_clean.db.backup

# Version control dashboards
git add metrics/dashboards/*.json
git commit -m "Update genealogy analytics dashboards"
```

---

## Next Steps

1. **Immediate (Today)**:
   - [ ] Start Grafana: `cd metrics && docker-compose up -d`
   - [ ] Access UI: http://localhost:3000
   - [ ] Review current dashboards

2. **Week 1**:
   - [ ] Install required plugins via Grafana UI
   - [ ] Create test dashboard with sample queries
   - [ ] Validate plugin compatibility

3. **Week 2-5**:
   - [ ] Follow phased implementation plan
   - [ ] Document SQL patterns
   - [ ] Create user guides

4. **Optional**:
   - [ ] Evaluate Plotly for missing charts
   - [ ] Design NiceGUI analytics tab
   - [ ] Embed Grafana dashboards in main UI

---

## References

**Grafana Plugins**:
- [Sankey Panel](https://grafana.com/grafana/plugins/netsage-sankey-panel/)
- [Chord Panel](https://grafana.com/grafana/plugins/esnet-chord-panel/)
- [Arc Diagram](https://grafana.com/grafana/plugins/esnet-arcdiagram-panel/)
- [Treemap Panel](https://grafana.com/grafana/plugins/marcusolsson-treemap-panel/)
- [Network Map](https://grafana.com/grafana/plugins/esnet-networkmap-panel/)
- [Interactive Tree Panel](https://grafana.com/grafana/plugins/equansdatahub-tree-panel/)

**Grafana Documentation**:
- [Visualizations Overview](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/)
- [Node Graph](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/node-graph/)
- [Heatmap](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/heatmap/)
- [Geomap](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/geomap/)

**Community Examples**:
- [Energy Flow Sankey with PostgreSQL](https://community.grafana.com/t/energy-flow-diagram-using-sankey-panel-with-data-from-postgresql/112711)
- [15 Grafana Visualizations You Didn't Know About](https://crashlaker.medium.com/15-grafana-vis-you-probably-didnt-know-was-possible-with-these-3-plugins-4a43f6de75f6)

---

*Document Version: 1.0*
*Last Updated: 2026-01-25*
*Author: Claude Sonnet 4.5*
