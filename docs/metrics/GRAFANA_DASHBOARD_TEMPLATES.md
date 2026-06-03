# Grafana Dashboard Templates

Pre-configured Grafana dashboard JSON templates for RMCitecraft metrics. Import these directly into Grafana for instant visualization.

## Prerequisites

### SQLite Data Source Configuration

1. Install the **Grafana SQLite Datasource** plugin:
   ```bash
   grafana-cli plugins install frser-sqlite-datasource
   ```

2. Configure three data sources in Grafana:
   - **RootsMagic**: Points to `data/Iiams.rmtree`
   - **CensusDB**: Points to `~/.rmcitecraft/census.db`
   - **BatchStateDB**: Points to `~/.rmcitecraft/batch_state.db`

---

## Dashboard 1: Genealogy Overview

A high-level overview of your genealogy database health and content.

```json
{
  "annotations": {
    "list": []
  },
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "liveNow": false,
  "panels": [
    {
      "datasource": {
        "type": "frser-sqlite-datasource",
        "uid": "rootsmagic"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {"color": "#5794F2", "value": null}
            ]
          },
          "unit": "none"
        },
        "overrides": []
      },
      "gridPos": {"h": 4, "w": 4, "x": 0, "y": 0},
      "id": 1,
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "calcs": ["lastNotNull"],
          "fields": "",
          "values": false
        },
        "textMode": "auto"
      },
      "pluginVersion": "10.0.0",
      "targets": [
        {
          "queryText": "SELECT COUNT(*) as total_persons FROM PersonTable",
          "queryType": "table",
          "rawQueryText": "SELECT COUNT(*) as total_persons FROM PersonTable",
          "refId": "A"
        }
      ],
      "title": "Total Persons",
      "type": "stat"
    },
    {
      "datasource": {
        "type": "frser-sqlite-datasource",
        "uid": "rootsmagic"
      },
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [{"color": "#5794F2", "value": null}]
          }
        }
      },
      "gridPos": {"h": 4, "w": 4, "x": 4, "y": 0},
      "id": 2,
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false},
        "textMode": "auto"
      },
      "targets": [
        {
          "queryText": "SELECT COUNT(*) as total_events FROM EventTable",
          "refId": "A"
        }
      ],
      "title": "Total Events",
      "type": "stat"
    },
    {
      "datasource": {
        "type": "frser-sqlite-datasource",
        "uid": "rootsmagic"
      },
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [{"color": "#5794F2", "value": null}]
          }
        }
      },
      "gridPos": {"h": 4, "w": 4, "x": 8, "y": 0},
      "id": 3,
      "targets": [
        {
          "queryText": "SELECT COUNT(*) as total_sources FROM SourceTable",
          "refId": "A"
        }
      ],
      "title": "Total Sources",
      "type": "stat"
    },
    {
      "datasource": {
        "type": "frser-sqlite-datasource",
        "uid": "rootsmagic"
      },
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [{"color": "#5794F2", "value": null}]
          }
        }
      },
      "gridPos": {"h": 4, "w": 4, "x": 12, "y": 0},
      "id": 4,
      "targets": [
        {
          "queryText": "SELECT COUNT(*) as total_citations FROM CitationTable",
          "refId": "A"
        }
      ],
      "title": "Total Citations",
      "type": "stat"
    },
    {
      "datasource": {
        "type": "frser-sqlite-datasource",
        "uid": "rootsmagic"
      },
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [{"color": "#5794F2", "value": null}]
          }
        }
      },
      "gridPos": {"h": 4, "w": 4, "x": 16, "y": 0},
      "id": 5,
      "targets": [
        {
          "queryText": "SELECT COUNT(*) as total_families FROM FamilyTable",
          "refId": "A"
        }
      ],
      "title": "Total Families",
      "type": "stat"
    },
    {
      "datasource": {
        "type": "frser-sqlite-datasource",
        "uid": "rootsmagic"
      },
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [{"color": "#5794F2", "value": null}]
          }
        }
      },
      "gridPos": {"h": 4, "w": 4, "x": 20, "y": 0},
      "id": 6,
      "targets": [
        {
          "queryText": "SELECT COUNT(*) as total_media FROM MultimediaTable",
          "refId": "A"
        }
      ],
      "title": "Total Media",
      "type": "stat"
    },
    {
      "datasource": {
        "type": "frser-sqlite-datasource",
        "uid": "rootsmagic"
      },
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "bars",
            "fillOpacity": 80,
            "gradientMode": "none",
            "hideFrom": {"legend": false, "tooltip": false, "viz": false},
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {"type": "linear"},
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {"group": "A", "mode": "none"},
            "thresholdsStyle": {"mode": "off"}
          },
          "mappings": [],
          "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}]}
        }
      },
      "gridPos": {"h": 8, "w": 24, "x": 0, "y": 4},
      "id": 7,
      "options": {
        "legend": {"calcs": [], "displayMode": "list", "placement": "bottom", "showLegend": true},
        "tooltip": {"mode": "single", "sort": "none"}
      },
      "targets": [
        {
          "queryText": "SELECT CAST(SUBSTR(e.Date, 1, 4) AS INTEGER) as birth_year, COUNT(*) as count FROM EventTable e WHERE e.EventType = 1 AND e.Date != '' AND CAST(SUBSTR(e.Date, 1, 4) AS INTEGER) BETWEEN 1700 AND 2024 GROUP BY birth_year ORDER BY birth_year",
          "refId": "A"
        }
      ],
      "title": "Birth Year Distribution",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "frser-sqlite-datasource",
        "uid": "rootsmagic"
      },
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "custom": {"hideFrom": {"legend": false, "tooltip": false, "viz": false}},
          "mappings": []
        }
      },
      "gridPos": {"h": 6, "w": 8, "x": 0, "y": 12},
      "id": 8,
      "options": {
        "legend": {"displayMode": "list", "placement": "right", "showLegend": true},
        "pieType": "pie",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": true},
        "tooltip": {"mode": "single", "sort": "none"}
      },
      "targets": [
        {
          "queryText": "SELECT CASE WHEN Living = 1 THEN 'Living' ELSE 'Deceased' END as status, COUNT(*) as count FROM PersonTable GROUP BY Living",
          "refId": "A"
        }
      ],
      "title": "Living vs Deceased",
      "type": "piechart"
    },
    {
      "datasource": {
        "type": "frser-sqlite-datasource",
        "uid": "rootsmagic"
      },
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "custom": {"hideFrom": {"legend": false, "tooltip": false, "viz": false}},
          "mappings": []
        }
      },
      "gridPos": {"h": 6, "w": 8, "x": 8, "y": 12},
      "id": 9,
      "options": {
        "legend": {"displayMode": "list", "placement": "right", "showLegend": true},
        "pieType": "pie",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": true}
      },
      "targets": [
        {
          "queryText": "SELECT CASE Sex WHEN 0 THEN 'Male' WHEN 1 THEN 'Female' ELSE 'Unknown' END as gender, COUNT(*) as count FROM PersonTable GROUP BY Sex",
          "refId": "A"
        }
      ],
      "title": "Gender Distribution",
      "type": "piechart"
    },
    {
      "datasource": {
        "type": "frser-sqlite-datasource",
        "uid": "rootsmagic"
      },
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "max": 100,
          "min": 0,
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {"color": "#F2495C", "value": null},
              {"color": "#FADE2A", "value": 70},
              {"color": "#73BF69", "value": 90}
            ]
          },
          "unit": "percent"
        }
      },
      "gridPos": {"h": 6, "w": 8, "x": 16, "y": 12},
      "id": 10,
      "options": {
        "orientation": "auto",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false},
        "showThresholdLabels": false,
        "showThresholdMarkers": true
      },
      "targets": [
        {
          "queryText": "SELECT ROUND(100.0 * COUNT(DISTINCT e.OwnerID) / (SELECT COUNT(*) FROM PersonTable), 1) as pct_coverage FROM EventTable e WHERE e.EventType = 1 AND e.OwnerType = 0",
          "refId": "A"
        }
      ],
      "title": "Birth Event Coverage",
      "type": "gauge"
    }
  ],
  "refresh": "",
  "schemaVersion": 38,
  "style": "dark",
  "tags": ["genealogy", "rootsmagic"],
  "templating": {"list": []},
  "time": {"from": "now-6h", "to": "now"},
  "timepicker": {},
  "timezone": "",
  "title": "Genealogy Overview",
  "uid": "genealogy-overview",
  "version": 1,
  "weekStart": ""
}
```

---

## Dashboard 2: Data Quality

Monitor data quality issues and completeness.

```json
{
  "annotations": {"list": []},
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "panels": [
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "rootsmagic"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "max": 100,
          "min": 0,
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {"color": "#F2495C", "value": null},
              {"color": "#FADE2A", "value": 60},
              {"color": "#73BF69", "value": 80}
            ]
          },
          "unit": "percent"
        }
      },
      "gridPos": {"h": 6, "w": 6, "x": 0, "y": 0},
      "id": 1,
      "options": {
        "orientation": "auto",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false},
        "showThresholdLabels": false,
        "showThresholdMarkers": true
      },
      "targets": [
        {
          "queryText": "SELECT ROUND(((SELECT 100.0 * COUNT(DISTINCT OwnerID) / (SELECT COUNT(*) FROM PersonTable) FROM EventTable WHERE EventType = 1 AND Date != '' AND OwnerType = 0) + (SELECT 100.0 * COUNT(DISTINCT ChildID) / (SELECT COUNT(*) FROM PersonTable) FROM ChildTable) + (SELECT 100.0 * COUNT(DISTINCT OwnerID) / (SELECT COUNT(*) FROM PersonTable) FROM EventTable WHERE OwnerType = 0)) / 3, 1) as completeness_score",
          "refId": "A"
        }
      ],
      "title": "Data Completeness Score",
      "type": "gauge"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "rootsmagic"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "max": 100,
          "min": 0,
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {"color": "#F2495C", "value": null},
              {"color": "#FADE2A", "value": 50},
              {"color": "#73BF69", "value": 80}
            ]
          },
          "unit": "percent"
        }
      },
      "gridPos": {"h": 6, "w": 6, "x": 6, "y": 0},
      "id": 2,
      "options": {
        "orientation": "auto",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false},
        "showThresholdLabels": false,
        "showThresholdMarkers": true
      },
      "targets": [
        {
          "queryText": "SELECT ROUND(100.0 * SUM(CASE WHEN Quality != '' AND Quality IS NOT NULL AND Quality != '~~~' THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_with_quality FROM CitationTable",
          "refId": "A"
        }
      ],
      "title": "Citation Quality Coverage",
      "type": "gauge"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "rootsmagic"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "max": 100,
          "min": 0,
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {"color": "#F2495C", "value": null},
              {"color": "#FADE2A", "value": 50},
              {"color": "#73BF69", "value": 70}
            ]
          },
          "unit": "percent"
        }
      },
      "gridPos": {"h": 6, "w": 6, "x": 12, "y": 0},
      "id": 3,
      "targets": [
        {
          "queryText": "SELECT ROUND(100.0 * COUNT(DISTINCT cl.OwnerID) / (SELECT COUNT(*) FROM EventTable), 1) as pct_cited FROM CitationLinkTable cl WHERE cl.OwnerType = 2",
          "refId": "A"
        }
      ],
      "title": "Events with Citations",
      "type": "gauge"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "rootsmagic"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {"color": "#73BF69", "value": null},
              {"color": "#FADE2A", "value": 100},
              {"color": "#F2495C", "value": 500}
            ]
          }
        }
      },
      "gridPos": {"h": 6, "w": 6, "x": 18, "y": 0},
      "id": 4,
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false},
        "textMode": "auto"
      },
      "targets": [
        {
          "queryText": "SELECT COUNT(*) as missing_birth_date FROM PersonTable p WHERE NOT EXISTS (SELECT 1 FROM EventTable e WHERE e.OwnerID = p.PersonID AND e.OwnerType = 0 AND e.EventType = 1 AND e.Date != '')",
          "refId": "A"
        }
      ],
      "title": "Missing Birth Dates",
      "type": "stat"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "rootsmagic"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "custom": {"hideFrom": {"legend": false, "tooltip": false, "viz": false}},
          "mappings": []
        }
      },
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 6},
      "id": 5,
      "options": {
        "legend": {"displayMode": "table", "placement": "right", "showLegend": true},
        "pieType": "donut",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": true}
      },
      "targets": [
        {
          "queryText": "SELECT CASE WHEN Quality = '' OR Quality IS NULL THEN 'Unspecified' WHEN Quality = '~~~' THEN 'Unknown (~~~)' ELSE Quality END as quality_code, COUNT(*) as count FROM CitationTable GROUP BY quality_code ORDER BY count DESC",
          "refId": "A"
        }
      ],
      "title": "Citation Quality Code Distribution",
      "type": "piechart"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "rootsmagic"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "bars",
            "fillOpacity": 80,
            "gradientMode": "none",
            "hideFrom": {"legend": false, "tooltip": false, "viz": false},
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {"type": "linear"},
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {"group": "A", "mode": "none"},
            "thresholdsStyle": {"mode": "off"}
          },
          "mappings": [],
          "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}]}
        }
      },
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 6},
      "id": 6,
      "options": {
        "legend": {"calcs": [], "displayMode": "list", "placement": "bottom", "showLegend": true}
      },
      "targets": [
        {
          "queryText": "SELECT ft.Name as event_type, COUNT(*) as missing_place FROM EventTable e JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID WHERE e.PlaceID = 0 AND e.EventType IN (1, 2, 3, 4, 18, 300) GROUP BY e.EventType, ft.Name ORDER BY missing_place DESC",
          "refId": "A"
        }
      ],
      "title": "Events Missing Places",
      "type": "barchart"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "rootsmagic"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "custom": {
            "align": "auto",
            "cellOptions": {"type": "auto"},
            "inspect": false
          },
          "mappings": [],
          "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}]}
        }
      },
      "gridPos": {"h": 8, "w": 24, "x": 0, "y": 14},
      "id": 7,
      "options": {
        "cellHeight": "sm",
        "footer": {"countRows": false, "fields": "", "reducer": ["sum"], "show": false},
        "showHeader": true
      },
      "targets": [
        {
          "queryText": "SELECT n1.Surname, n1.Given, COUNT(*) as matches FROM NameTable n1 JOIN NameTable n2 ON n1.Surname = n2.Surname AND n1.Given = n2.Given AND n1.OwnerID < n2.OwnerID WHERE n1.IsPrimary = 1 AND n2.IsPrimary = 1 AND n1.Surname != '' GROUP BY n1.Surname, n1.Given HAVING COUNT(*) > 0 ORDER BY COUNT(*) DESC LIMIT 20",
          "refId": "A"
        }
      ],
      "title": "Potential Duplicate Persons",
      "type": "table"
    }
  ],
  "schemaVersion": 38,
  "style": "dark",
  "tags": ["genealogy", "data-quality"],
  "templating": {"list": []},
  "time": {"from": "now-6h", "to": "now"},
  "title": "Data Quality",
  "uid": "data-quality",
  "version": 1
}
```

---

## Dashboard 3: Census Analysis

Census-specific metrics and processing status.

```json
{
  "annotations": {"list": []},
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "panels": [
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "rootsmagic"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "bars",
            "fillOpacity": 80,
            "gradientMode": "none",
            "hideFrom": {"legend": false, "tooltip": false, "viz": false},
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {"type": "linear"},
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {"group": "A", "mode": "none"},
            "thresholdsStyle": {"mode": "off"}
          },
          "mappings": [],
          "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}]}
        }
      },
      "gridPos": {"h": 8, "w": 24, "x": 0, "y": 0},
      "id": 1,
      "options": {
        "legend": {"calcs": ["sum"], "displayMode": "table", "placement": "right", "showLegend": true}
      },
      "targets": [
        {
          "queryText": "SELECT CASE WHEN e.Date LIKE '179%' THEN '1790' WHEN e.Date LIKE '180%' THEN '1800' WHEN e.Date LIKE '181%' THEN '1810' WHEN e.Date LIKE '182%' THEN '1820' WHEN e.Date LIKE '183%' THEN '1830' WHEN e.Date LIKE '184%' THEN '1840' WHEN e.Date LIKE '185%' THEN '1850' WHEN e.Date LIKE '186%' THEN '1860' WHEN e.Date LIKE '187%' THEN '1870' WHEN e.Date LIKE '188%' THEN '1880' WHEN e.Date LIKE '189%' THEN '1890' WHEN e.Date LIKE '190%' THEN '1900' WHEN e.Date LIKE '191%' THEN '1910' WHEN e.Date LIKE '192%' THEN '1920' WHEN e.Date LIKE '193%' THEN '1930' WHEN e.Date LIKE '194%' THEN '1940' WHEN e.Date LIKE '195%' THEN '1950' ELSE 'Unknown' END as census_year, COUNT(*) as count FROM EventTable e WHERE e.EventType = 18 GROUP BY census_year ORDER BY census_year",
          "refId": "A"
        }
      ],
      "title": "Census Records by Year",
      "type": "barchart"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "rootsmagic"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "thresholds": {"mode": "absolute", "steps": [{"color": "#5794F2", "value": null}]}
        }
      },
      "gridPos": {"h": 4, "w": 6, "x": 0, "y": 8},
      "id": 2,
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false},
        "textMode": "auto"
      },
      "targets": [
        {
          "queryText": "SELECT COUNT(*) as total_census FROM EventTable WHERE EventType = 18",
          "refId": "A"
        }
      ],
      "title": "Total Census Events",
      "type": "stat"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "rootsmagic"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "max": 100,
          "min": 0,
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {"color": "#F2495C", "value": null},
              {"color": "#FADE2A", "value": 50},
              {"color": "#73BF69", "value": 80}
            ]
          },
          "unit": "percent"
        }
      },
      "gridPos": {"h": 4, "w": 6, "x": 6, "y": 8},
      "id": 3,
      "options": {
        "orientation": "auto",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false},
        "showThresholdLabels": false,
        "showThresholdMarkers": true
      },
      "targets": [
        {
          "queryText": "SELECT ROUND(100.0 * COUNT(DISTINCT COALESCE(e.OwnerID, w.PersonID)) / (SELECT COUNT(*) FROM PersonTable), 1) as pct_coverage FROM EventTable e LEFT JOIN WitnessTable w ON e.EventID = w.EventID WHERE e.EventType = 18 AND e.OwnerType = 0",
          "refId": "A"
        }
      ],
      "title": "Census Coverage",
      "type": "gauge"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "rootsmagic"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "max": 100,
          "min": 0,
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {"color": "#F2495C", "value": null},
              {"color": "#FADE2A", "value": 70},
              {"color": "#73BF69", "value": 90}
            ]
          },
          "unit": "percent"
        }
      },
      "gridPos": {"h": 4, "w": 6, "x": 12, "y": 8},
      "id": 4,
      "targets": [
        {
          "queryText": "SELECT ROUND(100.0 * COUNT(DISTINCT e.EventID) / NULLIF((SELECT COUNT(*) FROM EventTable WHERE EventType = 18), 0), 1) as pct_cited FROM EventTable e JOIN CitationLinkTable cl ON e.EventID = cl.OwnerID AND cl.OwnerType = 2 WHERE e.EventType = 18",
          "refId": "A"
        }
      ],
      "title": "Census Citation Coverage",
      "type": "gauge"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "rootsmagic"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "thresholds": {"mode": "absolute", "steps": [{"color": "#5794F2", "value": null}]}
        }
      },
      "gridPos": {"h": 4, "w": 6, "x": 18, "y": 8},
      "id": 5,
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false},
        "textMode": "auto"
      },
      "targets": [
        {
          "queryText": "SELECT COUNT(DISTINCT EventID) as events_with_witnesses FROM WitnessTable",
          "refId": "A"
        }
      ],
      "title": "Shared Census Events",
      "type": "stat"
    }
  ],
  "schemaVersion": 38,
  "style": "dark",
  "tags": ["genealogy", "census"],
  "templating": {"list": []},
  "time": {"from": "now-6h", "to": "now"},
  "title": "Census Analysis",
  "uid": "census-analysis",
  "version": 1
}
```

---

## Dashboard 4: Processing Performance

Track batch processing performance and status.

```json
{
  "annotations": {"list": []},
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "panels": [
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "batchstatedb"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "max": 100,
          "min": 0,
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {"color": "#F2495C", "value": null},
              {"color": "#FADE2A", "value": 80},
              {"color": "#73BF69", "value": 95}
            ]
          },
          "unit": "percent"
        }
      },
      "gridPos": {"h": 6, "w": 8, "x": 0, "y": 0},
      "id": 1,
      "options": {
        "orientation": "auto",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false},
        "showThresholdLabels": false,
        "showThresholdMarkers": true
      },
      "targets": [
        {
          "queryText": "SELECT ROUND(100.0 * SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as success_rate FROM census_batch_items",
          "refId": "A"
        }
      ],
      "title": "Processing Success Rate",
      "type": "gauge"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "batchstatedb"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "thresholds": {"mode": "absolute", "steps": [{"color": "#5794F2", "value": null}]}
        }
      },
      "gridPos": {"h": 3, "w": 4, "x": 8, "y": 0},
      "id": 2,
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false},
        "textMode": "auto"
      },
      "targets": [
        {
          "queryText": "SELECT COUNT(*) as total_sessions FROM census_batch_sessions",
          "refId": "A"
        }
      ],
      "title": "Total Sessions",
      "type": "stat"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "batchstatedb"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "thresholds": {"mode": "absolute", "steps": [{"color": "#73BF69", "value": null}]}
        }
      },
      "gridPos": {"h": 3, "w": 4, "x": 12, "y": 0},
      "id": 3,
      "targets": [
        {
          "queryText": "SELECT SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) as completed FROM census_batch_items",
          "refId": "A"
        }
      ],
      "title": "Items Completed",
      "type": "stat"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "batchstatedb"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "thresholds": {"mode": "absolute", "steps": [{"color": "#F2495C", "value": null}]}
        }
      },
      "gridPos": {"h": 3, "w": 4, "x": 16, "y": 0},
      "id": 4,
      "targets": [
        {
          "queryText": "SELECT SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors FROM census_batch_items",
          "refId": "A"
        }
      ],
      "title": "Items with Errors",
      "type": "stat"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "batchstatedb"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "thresholds": {"mode": "absolute", "steps": [{"color": "#FADE2A", "value": null}]}
        }
      },
      "gridPos": {"h": 3, "w": 4, "x": 20, "y": 0},
      "id": 5,
      "targets": [
        {
          "queryText": "SELECT SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending FROM census_batch_items",
          "refId": "A"
        }
      ],
      "title": "Items Pending",
      "type": "stat"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "batchstatedb"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "max": 100,
          "min": 0,
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {"color": "#F2495C", "value": null},
              {"color": "#FADE2A", "value": 70},
              {"color": "#73BF69", "value": 90}
            ]
          },
          "unit": "percent"
        }
      },
      "gridPos": {"h": 3, "w": 8, "x": 8, "y": 3},
      "id": 6,
      "options": {
        "orientation": "auto",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false},
        "showThresholdLabels": false,
        "showThresholdMarkers": true
      },
      "targets": [
        {
          "queryText": "SELECT ROUND(100.0 * SUM(CASE WHEN exported = 1 THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END), 0), 1) as export_rate FROM census_batch_items",
          "refId": "A"
        }
      ],
      "title": "Export Rate",
      "type": "gauge"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "batchstatedb"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "custom": {"hideFrom": {"legend": false, "tooltip": false, "viz": false}},
          "mappings": []
        }
      },
      "gridPos": {"h": 6, "w": 8, "x": 16, "y": 3},
      "id": 7,
      "options": {
        "legend": {"displayMode": "table", "placement": "right", "showLegend": true},
        "pieType": "donut",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": true}
      },
      "targets": [
        {
          "queryText": "SELECT status, COUNT(*) as count FROM census_batch_sessions GROUP BY status ORDER BY count DESC",
          "refId": "A"
        }
      ],
      "title": "Session Status Distribution",
      "type": "piechart"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "batchstatedb"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "bars",
            "fillOpacity": 80,
            "gradientMode": "none",
            "hideFrom": {"legend": false, "tooltip": false, "viz": false},
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {"type": "linear"},
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {"group": "A", "mode": "none"},
            "thresholdsStyle": {"mode": "off"}
          },
          "mappings": [],
          "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}]}
        }
      },
      "gridPos": {"h": 8, "w": 16, "x": 0, "y": 6},
      "id": 8,
      "options": {
        "legend": {"calcs": ["sum"], "displayMode": "table", "placement": "right", "showLegend": true}
      },
      "targets": [
        {
          "queryText": "SELECT DATE(completed_at) as process_date, COUNT(*) as items_processed FROM census_batch_items WHERE status = 'complete' GROUP BY process_date ORDER BY process_date DESC LIMIT 30",
          "refId": "A"
        }
      ],
      "title": "Daily Processing Volume",
      "type": "barchart"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "batchstatedb"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "custom": {
            "align": "auto",
            "cellOptions": {"type": "auto"},
            "inspect": false
          },
          "mappings": [],
          "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}]}
        }
      },
      "gridPos": {"h": 8, "w": 8, "x": 16, "y": 9},
      "id": 9,
      "options": {
        "cellHeight": "sm",
        "footer": {"countRows": false, "fields": "", "reducer": ["sum"], "show": false},
        "showHeader": true
      },
      "targets": [
        {
          "queryText": "SELECT COALESCE(error_message, 'Unknown') as error_type, COUNT(*) as count FROM census_batch_items WHERE status = 'error' GROUP BY error_message ORDER BY count DESC LIMIT 10",
          "refId": "A"
        }
      ],
      "title": "Error Types",
      "type": "table"
    }
  ],
  "schemaVersion": 38,
  "style": "dark",
  "tags": ["genealogy", "processing", "performance"],
  "templating": {"list": []},
  "time": {"from": "now-7d", "to": "now"},
  "title": "Processing Performance",
  "uid": "processing-performance",
  "version": 1
}
```

---

## Dashboard 5: Sources & Citations

Source and citation quality analysis.

```json
{
  "annotations": {"list": []},
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "panels": [
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "rootsmagic"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "thresholds": {"mode": "absolute", "steps": [{"color": "#5794F2", "value": null}]}
        }
      },
      "gridPos": {"h": 4, "w": 6, "x": 0, "y": 0},
      "id": 1,
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false},
        "textMode": "auto"
      },
      "targets": [
        {
          "queryText": "SELECT COUNT(*) as total_sources FROM SourceTable",
          "refId": "A"
        }
      ],
      "title": "Total Sources",
      "type": "stat"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "rootsmagic"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "thresholds": {"mode": "absolute", "steps": [{"color": "#5794F2", "value": null}]}
        }
      },
      "gridPos": {"h": 4, "w": 6, "x": 6, "y": 0},
      "id": 2,
      "targets": [
        {
          "queryText": "SELECT COUNT(*) as total_citations FROM CitationTable",
          "refId": "A"
        }
      ],
      "title": "Total Citations",
      "type": "stat"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "rootsmagic"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "thresholds": {"mode": "absolute", "steps": [{"color": "#F2495C", "value": null}]}
        }
      },
      "gridPos": {"h": 4, "w": 6, "x": 12, "y": 0},
      "id": 3,
      "targets": [
        {
          "queryText": "SELECT COUNT(*) as unused_sources FROM SourceTable s WHERE NOT EXISTS (SELECT 1 FROM CitationTable c WHERE c.SourceID = s.SourceID)",
          "refId": "A"
        }
      ],
      "title": "Unused Sources",
      "type": "stat"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "rootsmagic"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "thresholds": {"mode": "absolute", "steps": [{"color": "#73BF69", "value": null}]}
        }
      },
      "gridPos": {"h": 4, "w": 6, "x": 18, "y": 0},
      "id": 4,
      "targets": [
        {
          "queryText": "SELECT ROUND(AVG(citation_count), 2) as avg_citations FROM (SELECT s.SourceID, COUNT(c.CitationID) as citation_count FROM SourceTable s LEFT JOIN CitationTable c ON s.SourceID = c.SourceID GROUP BY s.SourceID)",
          "refId": "A"
        }
      ],
      "title": "Avg Citations/Source",
      "type": "stat"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "rootsmagic"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "custom": {"hideFrom": {"legend": false, "tooltip": false, "viz": false}},
          "mappings": []
        }
      },
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 4},
      "id": 5,
      "options": {
        "legend": {"displayMode": "table", "placement": "right", "showLegend": true},
        "pieType": "donut",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": true}
      },
      "targets": [
        {
          "queryText": "SELECT CASE WHEN TemplateID = 0 THEN 'Free-Form' ELSE 'Template' END as source_type, COUNT(*) as count FROM SourceTable GROUP BY source_type",
          "refId": "A"
        }
      ],
      "title": "Free-Form vs Template Sources",
      "type": "piechart"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "rootsmagic"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "bars",
            "fillOpacity": 80,
            "gradientMode": "none",
            "hideFrom": {"legend": false, "tooltip": false, "viz": false},
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {"type": "linear"},
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {"group": "A", "mode": "none"},
            "thresholdsStyle": {"mode": "off"}
          },
          "mappings": [],
          "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}]}
        }
      },
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 4},
      "id": 6,
      "options": {
        "legend": {"calcs": [], "displayMode": "list", "placement": "bottom", "showLegend": true}
      },
      "targets": [
        {
          "queryText": "SELECT CASE WHEN Name LIKE '%Census%' THEN 'Census' WHEN Name LIKE '%Birth%' THEN 'Vital - Birth' WHEN Name LIKE '%Death%' THEN 'Vital - Death' WHEN Name LIKE '%Marriage%' THEN 'Vital - Marriage' WHEN Name LIKE '%Grave%' OR Name LIKE '%Cemetery%' THEN 'Cemetery' WHEN Name LIKE '%Church%' OR Name LIKE '%Baptis%' THEN 'Church' WHEN Name LIKE '%Military%' OR Name LIKE '%War%' THEN 'Military' ELSE 'Other' END as source_type, COUNT(*) as count FROM SourceTable GROUP BY source_type ORDER BY count DESC",
          "refId": "A"
        }
      ],
      "title": "Source Types by Content",
      "type": "barchart"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "rootsmagic"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "custom": {"hideFrom": {"legend": false, "tooltip": false, "viz": false}},
          "mappings": []
        }
      },
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 12},
      "id": 7,
      "options": {
        "legend": {"displayMode": "table", "placement": "right", "showLegend": true},
        "pieType": "donut",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": true}
      },
      "targets": [
        {
          "queryText": "SELECT CASE cl.OwnerType WHEN 0 THEN 'Person' WHEN 1 THEN 'Family' WHEN 2 THEN 'Event' WHEN 7 THEN 'Name' ELSE 'Other' END as owner_type, COUNT(*) as link_count FROM CitationLinkTable cl GROUP BY cl.OwnerType ORDER BY link_count DESC",
          "refId": "A"
        }
      ],
      "title": "Citation Links by Owner Type",
      "type": "piechart"
    },
    {
      "datasource": {"type": "frser-sqlite-datasource", "uid": "rootsmagic"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "bars",
            "fillOpacity": 80,
            "gradientMode": "none",
            "hideFrom": {"legend": false, "tooltip": false, "viz": false},
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {"type": "linear"},
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {"group": "A", "mode": "none"},
            "thresholdsStyle": {"mode": "off"}
          },
          "mappings": [],
          "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}]}
        }
      },
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 12},
      "id": 8,
      "options": {
        "legend": {"calcs": [], "displayMode": "list", "placement": "bottom", "showLegend": true}
      },
      "targets": [
        {
          "queryText": "SELECT CASE WHEN citation_count = 0 THEN 'Unused (0)' WHEN citation_count = 1 THEN '1 citation' WHEN citation_count BETWEEN 2 AND 5 THEN '2-5 citations' WHEN citation_count BETWEEN 6 AND 20 THEN '6-20 citations' WHEN citation_count > 20 THEN '20+ citations' END as range_label, COUNT(*) as source_count FROM (SELECT s.SourceID, COUNT(c.CitationID) as citation_count FROM SourceTable s LEFT JOIN CitationTable c ON s.SourceID = c.SourceID GROUP BY s.SourceID) GROUP BY range_label ORDER BY MIN(citation_count)",
          "refId": "A"
        }
      ],
      "title": "Citations per Source Distribution",
      "type": "barchart"
    }
  ],
  "schemaVersion": 38,
  "style": "dark",
  "tags": ["genealogy", "sources", "citations"],
  "templating": {"list": []},
  "time": {"from": "now-6h", "to": "now"},
  "title": "Sources & Citations",
  "uid": "sources-citations",
  "version": 1
}
```

---

## Import Instructions

1. Open Grafana web interface
2. Navigate to **Dashboards** > **Import**
3. Copy one of the JSON blocks above
4. Paste into the "Import via panel json" text area
5. Click **Load**
6. Select appropriate data sources for each panel
7. Click **Import**

## Data Source UIDs

Update the `uid` values in the JSON to match your Grafana data source configuration:

| Placeholder | Your UID |
|-------------|----------|
| `rootsmagic` | (your RootsMagic data source UID) |
| `censusdb` | (your Census.db data source UID) |
| `batchstatedb` | (your batch_state.db data source UID) |

Find your data source UIDs at: **Configuration** > **Data Sources** > (select source) > check URL path.

---

*Generated: 2024-12-13*
