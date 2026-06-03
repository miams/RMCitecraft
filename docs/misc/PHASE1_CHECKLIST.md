# Phase 1 Implementation Checklist

## Objective
Set up plugin infrastructure and validate existing data sources for genealogy analytics.

**Status**: Ready to Begin
**Expected Duration**: 1-2 hours
**Prerequisites**: Docker installed and running

---

## Pre-Flight Checks

### ✓ Files Created
- [x] `docker-compose.yml` - Updated with all required plugins
- [x] `validation_queries.sql` - Validation queries for each chart type
- [x] `dashboards/phase1_validation.json` - Test dashboard
- [x] `GRAFANA_SQL_PATTERNS.md` - SQL query pattern documentation
- [x] `prepare_grafana_db.py` - Updated with indexes and views

### ✓ Plugin List
The following plugins will be auto-installed on Grafana startup:
- [x] `frser-sqlite-datasource` - SQLite datasource (existing)
- [x] `netsage-sankey-panel` - Sankey diagrams
- [x] `esnet-chord-panel` - Chord diagrams
- [x] `esnet-arcdiagram-panel` - Arc diagrams
- [x] `marcusolsson-treemap-panel` - Treemap hierarchical charts
- [x] `esnet-networkmap-panel` - Network graphs
- [x] `equansdatahub-tree-panel` - Tree/Dendrogram charts

---

## Step-by-Step Implementation

### Step 1: Prepare the Database

**What**: Create a Grafana-compatible copy of your RootsMagic database

**Commands**:
```bash
cd metrics
uv run python prepare_grafana_db.py
```

**Expected Output**:
```
Preparing Grafana database...
Connected to source: ../data/Iiams.rmtree
Created destination: data/rootsmagic_clean.db
Processing table: PersonTable...
  -> Copied 2847 rows.
Processing table: NameTable...
  -> Copied 5694 rows.
...

Adding performance indexes...
  -> Added 11 performance indexes

Creating performance views...
  -> Created person_summary view
  -> Created family_connections view
  -> Created citation_quality view
  -> Created 3 performance views

============================================================
✓ Database ready for Grafana!
============================================================
Location: data/rootsmagic_clean.db

Next steps:
  1. Start Grafana: docker-compose up -d
  2. Open http://localhost:3000
  3. Navigate to Phase 1 Validation dashboard
  4. Run validation queries to test data quality
```

**Validation**:
- [ ] Script completed without errors
- [ ] File `data/rootsmagic_clean.db` exists
- [ ] File size is similar to source database

**Troubleshooting**:
- If "Error connecting to source": Check that `../data/Iiams.rmtree` exists
- If "ICU extension not found": Check `../sqlite-extension/icu.dylib` exists
- If "Permission denied": Run `chmod +x prepare_grafana_db.py`

---

### Step 2: Start Docker

**What**: Launch Docker Desktop and start Grafana container

**Commands**:
```bash
# If Docker Desktop is not running, start it first
open -a Docker

# Wait for Docker to start (check menu bar icon)
# Then start Grafana
cd metrics
docker-compose up -d
```

**Expected Output**:
```
[+] Running 1/1
 ✔ Container rmcitecraft-grafana  Started
```

**Validation**:
- [ ] Docker Desktop is running (icon in menu bar)
- [ ] Container `rmcitecraft-grafana` shows as "Running"
- [ ] No error messages in output

**Check Container Status**:
```bash
docker ps
```

Should show:
```
CONTAINER ID   IMAGE                       STATUS          PORTS
abc123def456   grafana/grafana-oss:latest  Up 10 seconds   0.0.0.0:3000->3000/tcp
```

**Troubleshooting**:
- If container exits immediately: Check logs with `docker logs rmcitecraft-grafana`
- If port 3000 is busy: Stop other services using port 3000
- If plugin download fails: Check internet connection

---

### Step 3: Verify Plugin Installation

**What**: Check that all required plugins installed successfully

**Commands**:
```bash
# View Grafana logs to see plugin installation
docker logs rmcitecraft-grafana | grep -i plugin

# Or check inside container
docker exec rmcitecraft-grafana grafana-cli plugins ls
```

**Expected Output**:
```
frser-sqlite-datasource @ 3.x.x
netsage-sankey-panel @ 1.x.x
esnet-chord-panel @ 1.x.x
esnet-arcdiagram-panel @ 1.x.x
marcusolsson-treemap-panel @ 1.x.x
esnet-networkmap-panel @ 1.x.x
equansdatahub-tree-panel @ 1.x.x
```

**Validation**:
- [ ] All 7 plugins listed
- [ ] No "failed to install" errors in logs

**Troubleshooting**:
- If plugins failed: Restart container with `docker-compose restart`
- If still failing: Check `GF_INSTALL_PLUGINS` in docker-compose.yml
- Manual install (fallback): Use Grafana UI → Administration → Plugins

---

### Step 4: Access Grafana UI

**What**: Open Grafana in your web browser

**Steps**:
1. Open browser to: http://localhost:3000
2. You should see the Grafana home page (no login required - anonymous access is enabled)
3. If prompted for login:
   - Username: `admin`
   - Password: `admin`
   - (You can skip changing the password)

**Validation**:
- [ ] Grafana UI loads without errors
- [ ] Left sidebar shows menu items (Dashboards, Explore, etc.)
- [ ] No error banners at top of page

**Troubleshooting**:
- If page doesn't load: Check container is running (`docker ps`)
- If "502 Bad Gateway": Wait 30 seconds and refresh (Grafana is still starting)
- If login page shows: Use admin/admin

---

### Step 5: Verify Data Sources

**What**: Confirm the three SQLite data sources are connected

**Steps**:
1. In Grafana, navigate to: **Administration** (gear icon) → **Data sources**
2. You should see three data sources:
   - **RootsMagic** (frser-sqlite-datasource)
   - **CensusDB** (frser-sqlite-datasource)
   - **BatchStateDB** (frser-sqlite-datasource)
3. Click on **RootsMagic** data source
4. Scroll down and click **Test** button

**Expected Result**:
```
✓ Data source is working
```

**Validation**:
- [ ] All three data sources show green checkmark
- [ ] Test button returns "Data source is working"
- [ ] No "database locked" errors

**Troubleshooting**:
- If data source not found: Check `provisioning/datasources/datasources.yml`
- If "database locked": Stop any other processes accessing the database
- If path error: Check that `./data/rootsmagic_clean.db` exists

---

### Step 6: Open Phase 1 Validation Dashboard

**What**: Load the pre-built test dashboard to validate all chart types

**Steps**:
1. In Grafana, navigate to: **Dashboards** (four squares icon) → **Browse**
2. Find dashboard: **Phase 1 - Chart Validation Dashboard**
3. Click to open

**Expected Result**:
Dashboard loads with 7+ panels:
- Data Quality Metrics (table)
- TEST: Heatmap - Birth Seasonality
- TEST: Bubble Map - Geographic Distribution
- TEST: Sankey - Migration Flows
- TEST: Chord - Surname Intermarriage
- TEST: Treemap - Citation Coverage
- TEST: Arc Diagram - Lifespan Overlaps

**Validation**:
- [ ] Dashboard loads without errors
- [ ] All panels show data (not "No data")
- [ ] No red error messages in panels

**Troubleshooting**:
- If dashboard not found: Check `dashboards/phase1_validation.json` exists
- If "No data": Check data sources are connected
- If plugin error: Verify plugin installation (Step 3)

---

### Step 7: Run Data Quality Checks

**What**: Validate your database has sufficient data for each chart type

**Steps**:
1. In the Phase 1 Validation Dashboard, find the **Data Quality Metrics** panel (top)
2. Review the coverage percentages:

**Expected Thresholds**:
| Metric | Good | Acceptable | Needs Work |
|--------|------|------------|------------|
| Date Coverage | >80% | >50% | <50% |
| Coordinate Coverage | >30% | >10% | <10% |
| Citation Coverage | >60% | >40% | <40% |
| Name Coverage | >95% | >90% | <90% |
| Family Relationship Coverage | >70% | >50% | <50% |

**Validation**:
- [ ] Date Coverage: ___% (Record your value)
- [ ] Coordinate Coverage: ___% (Record your value)
- [ ] Citation Coverage: ___% (Record your value)
- [ ] Name Coverage: ___% (Record your value)

**Action Items**:
- If Date Coverage <50%: Many charts will have gaps
- If Coordinate Coverage <10%: Maps will be sparse
- If Citation Coverage <40%: Treemap will have limited depth
- If Name Coverage <90%: Network graphs may be incomplete

**Note**: Don't worry if some metrics are low - charts will still work, just with less data.

---

### Step 8: Test Each Chart Type

**What**: Click through each test panel and verify it renders correctly

**Checklist**:
Go through each panel in the dashboard and verify:

#### ✓ Heatmap - Birth Seasonality
- [ ] Displays color grid (decades on one axis, months on other)
- [ ] Colors vary based on birth counts
- [ ] Tooltip shows decade, month, and count on hover
- **Data**: If empty, your database may not have birth dates with month precision

#### ✓ Bubble Map - Geographic Distribution
- [ ] Map loads with base layer (OpenStreetMap)
- [ ] Circles appear at locations with coordinates
- [ ] Circle size varies based on person count
- [ ] Tooltip shows location name and count
- **Data**: If empty, run geocoding to add coordinates to PlaceTable

#### ✓ Sankey - Migration Flows
- [ ] Shows flowing connections between place names
- [ ] Flow width varies based on person count
- [ ] Tooltip shows source → target and count
- **Data**: Requires birth and death places that differ

#### ✓ Chord - Surname Intermarriage
- [ ] Shows circular layout with surname segments
- [ ] Arcs connect surnames that intermarried
- [ ] Arc thickness varies based on marriage count
- **Data**: Requires families with different father/mother surnames

#### ✓ Treemap - Citation Coverage
- [ ] Shows nested rectangles
- [ ] Top level shows citation types
- [ ] Second level shows record categories
- [ ] Rectangle size varies based on citation count
- **Data**: Requires sources with citations

#### ✓ Arc Diagram - Lifespan Overlaps
- [ ] Shows people arranged on a line/axis
- [ ] Arcs connect people whose lives overlapped
- [ ] Tooltip shows names and overlap years
- **Data**: Requires birth and death dates

**Troubleshooting by Chart Type**:

| Chart Shows | Likely Cause | Solution |
|-------------|--------------|----------|
| "No data" | Missing data in database | Check corresponding data quality metric |
| "Plugin error" | Plugin not installed | Restart Grafana, check plugin list |
| "Query error" | SQL syntax issue | Check Grafana logs for details |
| Blank/white panel | Loading timeout | Refresh page, check query performance |
| Partial data | LIMIT clause | Expected - queries limited to 50-100 rows |

---

### Step 9: Run Manual Validation Queries

**What**: Test queries directly in Grafana's SQL editor

**Steps**:
1. Navigate to: **Explore** (compass icon in left sidebar)
2. Select data source: **RootsMagic**
3. Paste queries from `validation_queries.sql`
4. Click **Run query**

**Test These Key Queries**:

#### Query 1: Person Count
```sql
SELECT COUNT(*) as total_persons FROM PersonTable;
```
**Expected**: Your actual person count (e.g., 2847)

#### Query 2: Heatmap Data Format
```sql
SELECT
  strftime('%Y', e.Date) as decade,
  CAST(strftime('%m', e.Date) AS INTEGER) as month,
  COUNT(*) as birth_count
FROM EventTable e
WHERE e.EventType = 1 AND e.Date IS NOT NULL
GROUP BY decade, month
LIMIT 10;
```
**Expected**: 3 columns (decade, month, birth_count) with 10 rows

#### Query 3: Network Graph Nodes
```sql
SELECT
  p.PersonID as id,
  n.Given || ' ' || n.Surname as title,
  n.Surname as mainStat
FROM PersonTable p
JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
LIMIT 10;
```
**Expected**: 3 columns (id, title, mainStat) with 10 rows

**Validation**:
- [ ] All queries return data without errors
- [ ] Column names match expected format
- [ ] Data types are correct (text vs. number)

---

### Step 10: Document Your Findings

**What**: Record baseline metrics and any issues discovered

**Create**: `metrics/PHASE1_RESULTS.md`

**Template**:
```markdown
# Phase 1 Validation Results

**Date**: 2026-01-25
**Database**: Iiams.rmtree
**Grafana Version**: [Check in UI: Gear → Server settings → Version]

## Data Quality Metrics
- Date Coverage: ___%
- Coordinate Coverage: ___%
- Citation Coverage: ___%
- Name Coverage: ___%
- Family Relationship Coverage: ___%

## Chart Validation Results
- [x] Heatmap: Working / Partial data / Not working
- [x] Bubble Map: Working / Partial data / Not working
- [x] Sankey: Working / Partial data / Not working
- [x] Chord: Working / Partial data / Not working
- [x] Treemap: Working / Partial data / Not working
- [x] Arc Diagram: Working / Partial data / Not working

## Issues Discovered
1. [Example] Heatmap shows no data before 1850 - birth dates missing
2. [Example] Bubble Map only shows 5 locations - need geocoding
3. [Example] Sankey empty - everyone died in birthplace

## Action Items for Phase 2
1. [ ] Geocode PlaceTable for better map coverage
2. [ ] Improve date precision for heatmap accuracy
3. [ ] Add more residence events for migration analysis

## Plugin Status
- frser-sqlite-datasource: ✓ Installed
- netsage-sankey-panel: ✓ Installed
- esnet-chord-panel: ✓ Installed
- esnet-arcdiagram-panel: ✓ Installed
- marcusolsson-treemap-panel: ✓ Installed
- esnet-networkmap-panel: ✓ Installed
- equansdatahub-tree-panel: ✓ Installed

## Next Steps
Ready to proceed to Phase 2: Simple Charts implementation
```

---

## Phase 1 Complete! 🎉

### Success Criteria Met
- [ ] Grafana running and accessible
- [ ] All 7 plugins installed successfully
- [ ] Three data sources connected and tested
- [ ] Phase 1 Validation Dashboard loads
- [ ] Data quality metrics recorded
- [ ] At least 4 out of 6 chart types showing data
- [ ] Validation queries run successfully
- [ ] Results documented

### What You've Accomplished
✓ Infrastructure setup complete
✓ Plugin ecosystem validated
✓ Data quality baseline established
✓ SQL patterns documented
✓ Performance optimizations applied

### Ready for Phase 2?
If you met the success criteria, you're ready to proceed to **Phase 2: Simple Charts**.

Phase 2 will focus on:
- Building production-quality heatmaps
- Creating geographic distribution maps
- Implementing citation coverage treemaps
- Adding dashboard variables for filtering
- Creating reusable panel templates

---

## Quick Reference Commands

### Start Grafana
```bash
cd metrics
docker-compose up -d
```

### View Logs
```bash
docker logs -f rmcitecraft-grafana
```

### Stop Grafana
```bash
cd metrics
docker-compose down
```

### Restart After Changes
```bash
cd metrics
docker-compose restart
```

### Rebuild Database
```bash
cd metrics
uv run python prepare_grafana_db.py
```

### Check Plugin Status
```bash
docker exec rmcitecraft-grafana grafana-cli plugins ls
```

### Access Shell Inside Container
```bash
docker exec -it rmcitecraft-grafana /bin/bash
```

---

## Troubleshooting Reference

### Issue: Plugins Won't Install
**Symptoms**: Error in logs about plugin download
**Solutions**:
1. Check internet connection
2. Try restarting Docker: `docker-compose restart`
3. Manual install via UI: Administration → Plugins → Search
4. Check Docker Hub rate limits (wait and retry)

### Issue: Database Locked
**Symptoms**: "database is locked" error
**Solutions**:
1. Close RootsMagic application
2. Stop any running scripts accessing database
3. Restart Grafana: `docker-compose restart`

### Issue: No Data in Panels
**Symptoms**: All panels show "No data"
**Solutions**:
1. Check data source connection: Administration → Data sources → Test
2. Verify database file exists: `ls -la metrics/data/rootsmagic_clean.db`
3. Run validation queries in Explore to diagnose
4. Check for SQL errors in panel edit mode

### Issue: Container Won't Start
**Symptoms**: `docker ps` shows no container
**Solutions**:
1. Check logs: `docker logs rmcitecraft-grafana`
2. Verify port 3000 is available: `lsof -i :3000`
3. Check docker-compose.yml syntax
4. Try removing and recreating: `docker-compose down && docker-compose up -d`

### Issue: Performance is Slow
**Symptoms**: Queries take >5 seconds
**Solutions**:
1. Verify indexes were created (check prepare_grafana_db.py output)
2. Add LIMIT clauses to queries
3. Use views for complex queries
4. Check database size isn't excessive

---

## Support Resources

- **Grafana Documentation**: https://grafana.com/docs/grafana/latest/
- **SQLite Plugin Docs**: https://github.com/fr-ser/grafana-sqlite-datasource
- **Plugin Catalog**: http://localhost:3000/plugins
- **Community Forum**: https://community.grafana.com/

---

*Phase 1 Checklist Version: 1.0*
*Last Updated: 2026-01-25*
