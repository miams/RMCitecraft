# Grafana Genealogy Analytics

Interactive analytics dashboards for RootsMagic genealogy data using Grafana.

## Quick Start

```bash
# 1. Prepare the database
uv run python prepare_grafana_db.py

# 2. Start Grafana
docker-compose up -d

# 3. Open in browser
open http://localhost:3000

# 4. Navigate to "Phase 1 - Chart Validation Dashboard"
```

## What's Included

### 📊 Chart Types (8 of 10 implemented in Grafana)

| Chart | Status | Use Case |
|-------|--------|----------|
| **Heatmap** | ✅ Built-in | Birth seasonality, research completeness |
| **Bubble Map** | ✅ Built-in | Geographic distribution of ancestors |
| **Treemap** | ✅ Plugin | Citation coverage by record type |
| **Sankey** | ✅ Plugin | Multi-generational migration flows |
| **Chord** | ✅ Plugin | Surname intermarriage patterns |
| **Arc Diagram** | ✅ Plugin | Lifespan overlaps (who knew whom) |
| **Network Graph** | ⚠️ Plugin | Family relationship web |
| **Dendrogram** | ⚠️ Plugin | Interactive pedigree/descendant trees |
| **Circular Packing** | ❌ N/A | Use Plotly instead |
| **Ridgeline** | ❌ N/A | Use Plotly instead |

### 🗂️ Directory Structure

```
metrics/
├── docker-compose.yml              # Grafana container config + plugins
├── prepare_grafana_db.py           # Database preparation script
├── validation_queries.sql          # Test queries for each chart type
├── GRAFANA_SQL_PATTERNS.md         # SQL query pattern documentation
├── PHASE1_CHECKLIST.md             # Implementation guide
├── README.md                       # This file
│
├── data/                           # SQLite databases (Docker volume)
│   ├── rootsmagic_clean.db        # Main genealogy database
│   ├── census.db                  # Census extraction data
│   └── batch_state.db             # Processing state
│
├── dashboards/                     # Dashboard JSON files
│   ├── phase1_validation.json     # Test dashboard (Phase 1)
│   ├── genealogy_overview.json    # Main overview (existing)
│   ├── data_quality.json          # Data quality metrics (existing)
│   ├── census_analysis.json       # Census analysis (existing)
│   ├── sources_citations.json     # Citation tracking (existing)
│   └── processing_performance.json # Batch processing stats (existing)
│
└── provisioning/                   # Grafana auto-configuration
    ├── datasources/
    │   └── datasources.yml        # SQLite datasource config
    └── dashboards/
        └── dashboards.yml         # Dashboard auto-load config
```

### 📚 Documentation

| Document | Purpose |
|----------|---------|
| **PHASE1_CHECKLIST.md** | Step-by-step setup and validation guide |
| **GRAFANA_SQL_PATTERNS.md** | SQL query patterns for all chart types |
| **validation_queries.sql** | Test queries to validate data format |
| **../docs/architecture/GRAFANA_GENEALOGY_ANALYTICS_ARCHITECTURE.md** | Complete architecture & implementation plan |

## Architecture

### Data Flow

```
RootsMagic Database (Iiams.rmtree)
         ↓
prepare_grafana_db.py (strips RMNOCASE, adds indexes/views)
         ↓
rootsmagic_clean.db (Grafana-compatible)
         ↓
Grafana (SQLite plugin) ← Dashboards (JSON)
         ↓
Interactive Charts (Browser)
```

### Performance Optimizations

The `prepare_grafana_db.py` script automatically:
- **Strips RMNOCASE collation** (Grafana doesn't support ICU extension)
- **Adds 11 performance indexes** (EventTable, NameTable, PlaceTable, etc.)
- **Creates 3 materialized views** (person_summary, family_connections, citation_quality)
- **Validates data quality** (date coverage, coordinate coverage, etc.)

### Plugins Installed

```yaml
# Auto-installed via GF_INSTALL_PLUGINS environment variable
- frser-sqlite-datasource          # SQLite datasource
- netsage-sankey-panel             # Sankey diagrams
- esnet-chord-panel                # Chord diagrams
- esnet-arcdiagram-panel           # Arc diagrams
- marcusolsson-treemap-panel       # Treemap hierarchical charts
- esnet-networkmap-panel           # Network graphs
- equansdatahub-tree-panel         # Tree/Dendrogram charts
```

## Implementation Phases

### ✅ Phase 0: Existing Setup (Complete)
- Grafana container running
- SQLite datasource configured
- 5 basic dashboards (overview, data quality, census, citations, performance)
- Geomap working with PlaceTable coordinates

### 🔄 Phase 1: Foundation (Current)
**Duration**: 1-2 hours
**Deliverables**:
- [x] Updated docker-compose.yml with all plugins
- [x] Database preparation script with indexes/views
- [x] Validation queries for all chart types
- [x] Test dashboard (phase1_validation.json)
- [x] SQL pattern documentation

**To Complete Phase 1**: Follow **PHASE1_CHECKLIST.md**

### 📅 Phase 2: Simple Charts (Week 2)
**Charts**: Heatmap, Bubble Map, Treemap
**Focus**: Birth seasonality, geographic hotspots, citation coverage
**Deliverables**: 3 new production dashboards

### 📅 Phase 3: Flow Charts (Week 3)
**Charts**: Sankey, Chord, Arc
**Focus**: Migration patterns, surname networks, lifespan overlaps
**Deliverables**: 3 flow-based dashboards

### 📅 Phase 4: Network & Tree Charts (Week 4)
**Charts**: Network Graph, Dendrogram
**Focus**: Family relationships, interactive pedigrees
**Deliverables**: 2 relationship dashboards

### 📅 Phase 5: Advanced Features (Week 5+)
**Focus**: Dashboard variables, cross-linking, data quality integration
**Deliverables**: Master analytics hub, user guide

## Data Sources

### RootsMagic (rootsmagic_clean.db)
- **Tables**: PersonTable, NameTable, EventTable, FamilyTable, PlaceTable, SourceTable, CitationTable, MediaTable, etc.
- **Update Frequency**: Manual (run `prepare_grafana_db.py` after RootsMagic changes)
- **Size**: ~50-100 MB (varies by database)

### CensusDB (census.db)
- **Purpose**: Census extraction data (EAV pattern)
- **Update Frequency**: Automatic (volume mount)
- **Source**: `~/.rmcitecraft/census.db`

### BatchStateDB (batch_state.db)
- **Purpose**: Batch processing state tracking
- **Update Frequency**: Real-time (volume mount)
- **Source**: `~/.rmcitecraft/batch_state.db`

## Common Tasks

### Rebuild Database After RootsMagic Changes
```bash
cd metrics
uv run python prepare_grafana_db.py
# No need to restart Grafana - changes are immediate
```

### View Grafana Logs
```bash
docker logs -f rmcitecraft-grafana
```

### Restart Grafana
```bash
cd metrics
docker-compose restart
```

### Install New Plugin
```bash
# Option 1: Via UI (recommended for 2026+)
# Navigate to: Administration → Plugins → Search

# Option 2: Via docker-compose.yml
# Add plugin to GF_INSTALL_PLUGINS, then:
docker-compose down
docker-compose up -d
```

### Export Dashboard
1. Open dashboard in Grafana
2. Click ⚙️ (Settings) → JSON Model
3. Copy JSON
4. Save to `dashboards/<name>.json`
5. Commit to git

### Import Dashboard
```bash
# Place JSON file in dashboards/ directory
# Grafana auto-loads on startup (provisioning/dashboards/dashboards.yml)
# OR import via UI: Dashboards → Import → Upload JSON
```

### Access Grafana Shell
```bash
docker exec -it rmcitecraft-grafana /bin/bash
```

### Check Database Size
```bash
ls -lh metrics/data/*.db
```

### Validate SQL Query
```bash
# Test query directly in SQLite
docker exec rmcitecraft-grafana \
  sqlite3 /var/lib/grafana/data/rootsmagic_clean.db \
  "SELECT COUNT(*) FROM PersonTable"
```

## Data Quality Tips

### Improve Map Coverage
Add coordinates to PlaceTable:
1. Export places: `SELECT DISTINCT PlaceName FROM PlaceTable WHERE Latitude IS NULL`
2. Geocode using external service (Google Maps API, OpenCage, etc.)
3. Update RootsMagic database with coordinates
4. Rebuild Grafana database

### Improve Date Precision
Many charts benefit from month/day precision:
- Check: `SELECT Date FROM EventTable WHERE Date LIKE '%-%'`
- Add month/day to vague dates (e.g., "1850" → "1850-06-15" estimated)

### Add Missing Relationships
Network graphs require complete FamilyTable:
- Check: `SELECT COUNT(*) FROM FamilyTable WHERE FatherID IS NULL OR MotherID IS NULL`
- Add missing parents in RootsMagic
- Rebuild database

## Troubleshooting

### "No data" in charts
1. Check data source connection: Administration → Data sources → Test
2. Run validation queries in Explore
3. Check data quality metrics in Phase 1 dashboard
4. Review `validation_queries.sql` for expected data format

### "Plugin error"
1. Verify plugin installation: `docker exec rmcitecraft-grafana grafana-cli plugins ls`
2. Restart Grafana: `docker-compose restart`
3. Check logs: `docker logs rmcitecraft-grafana | grep -i plugin`

### "Database locked"
1. Close RootsMagic application
2. Stop any running Python scripts
3. Restart Grafana: `docker-compose restart`

### Slow queries
1. Verify indexes: Check `prepare_grafana_db.py` output
2. Add LIMIT clauses: `LIMIT 100`
3. Use views: `FROM person_summary` instead of complex JOINs
4. Check database size: `ls -lh data/*.db`

### Container won't start
1. Check logs: `docker logs rmcitecraft-grafana`
2. Verify port 3000 available: `lsof -i :3000`
3. Check docker-compose.yml syntax
4. Rebuild: `docker-compose down && docker-compose up -d`

## Security & Privacy

### Current Setup (Development)
- **Anonymous access**: Enabled (no login required)
- **Role**: Admin (full access)
- **Network**: localhost only (not exposed to internet)

### Production Setup (Family Sharing)
To share dashboards with family:

**Option 1: Read-Only Anonymous Access**
```yaml
# In docker-compose.yml
environment:
  - GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer  # Change from Admin
```

**Option 2: Named Users**
```yaml
# In docker-compose.yml
environment:
  - GF_AUTH_ANONYMOUS_ENABLED=false
  - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
```

**Privacy Filters**:
Add to queries to exclude living people:
```sql
WHERE p.Living = 0
-- OR use 100-year rule
WHERE (julianday('now') - julianday(birth.Date)) / 365.25 > 100
```

**Network Security**:
- Keep on localhost (no external exposure)
- Use VPN/Tailscale for remote family access
- Export static snapshots for sharing (no live database)

## Performance Benchmarks

### Expected Query Times (on typical genealogy database ~3000 people)
- Simple aggregations: <100ms
- Heatmaps: <200ms
- Maps: <500ms (coordinate lookups)
- Sankey flows: <1s (complex joins)
- Chord diagrams: <1s
- Network graphs: <2s (large result sets)
- Dendrograms (recursive): <3s

### Database Size Limits
- Optimal: <100 MB
- Good: 100-500 MB
- Slow: >500 MB (consider materialized views)

## Next Steps

1. **Complete Phase 1**: Follow **PHASE1_CHECKLIST.md**
2. **Document Results**: Create `PHASE1_RESULTS.md` with your findings
3. **Prioritize Charts**: Based on your data quality, pick Phase 2 charts
4. **Start Building**: Follow architecture document for Phase 2+

## Resources

- **Architecture Doc**: `../docs/architecture/GRAFANA_GENEALOGY_ANALYTICS_ARCHITECTURE.md`
- **SQL Patterns**: `GRAFANA_SQL_PATTERNS.md`
- **Phase 1 Guide**: `PHASE1_CHECKLIST.md`
- **Grafana Docs**: https://grafana.com/docs/grafana/latest/
- **SQLite Plugin**: https://github.com/fr-ser/grafana-sqlite-datasource
- **Plugin Catalog**: http://localhost:3000/plugins

---

**Version**: 1.0
**Last Updated**: 2026-01-25
**Status**: Phase 1 Ready to Begin
