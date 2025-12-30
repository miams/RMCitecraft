---
priority: essential
topics: [user-guide, census, batch-processing]
---

# Census Batch Workflow Guide

**For**: Users processing multiple census citations at once
**Time to Complete**: Varies by batch size

## Overview

RMCitecraft's batch processing allows you to format multiple census citations in a single session. This guide covers the complete workflow from selecting citations to exporting formatted results.

---

## Before You Begin

### Prerequisites

1. **Chrome running with remote debugging** - `~/start-chrome.sh`
2. **Logged into FamilySearch** in that Chrome session
3. **RMCitecraft running** - `uv run python src/rmcitecraft/main.py`
4. **Working database copy** - Never process your production database directly

### Understanding Citation States

| State | Meaning | Action Needed |
|-------|---------|---------------|
| **Incomplete** | Has FamilySearch URL but missing formatted fields | Process with RMCitecraft |
| **Complete** | All three citation forms present and different | None - already formatted |
| **No URL** | Citation lacks FamilySearch link | Add URL manually first |

---

## Step 1: Select Census Year

### In the Batch Processing Tab

1. Open RMCitecraft
2. Navigate to **Batch Processing** tab
3. Select a census year from the dropdown (e.g., "1930")

### What Appears

The system queries your RootsMagic database for citations matching:
- `Fed Census: YYYY, ...` (population schedules)
- `Fed Census Slave Schedule: YYYY, ...` (1850-1860)
- `Fed Census Mortality Schedule: YYYY, ...` (1850-1880)

---

## Step 2: Filter Citations

### Filter Options

| Filter | Shows |
|--------|-------|
| **All** | Every citation for the selected year |
| **Incomplete** | Citations needing processing |
| **Complete** | Already formatted citations |
| **No Media** | Citations without linked images |

### Recommended Approach

Start with **Incomplete** filter to focus on citations needing work.

---

## Step 3: Start Batch Processing

### Click "Start Batch"

RMCitecraft begins processing each citation:

1. **Extracts FamilySearch URL** from citation data
2. **Opens page in Chrome** via Playwright automation
3. **Extracts census data** (person, location, ED, sheet, line)
4. **Downloads census image** automatically
5. **Presents data for review**

### Progress Display

```
Processing: 3 of 47 citations
Current: George B Iams (1930, Greene County, PA)
Status: Extracting data...

[Pause] [Skip] [Stop]
```

---

## Step 4: Review Each Citation

### The Review Dialog

For each citation, a dialog shows:

**Left Panel - Citation Data:**
- Person name
- Census year
- State and County
- Township/City
- Enumeration District (ED)
- Sheet/Page number
- Line number
- Family number

**Right Panel - Census Image:**
- Displays at 275% zoom (readable text)
- Pan and zoom controls
- Line numbers visible for verification

### Fill Missing Fields

Some fields may be empty if FamilySearch didn't index them:

| Field | How to Find on Image |
|-------|---------------------|
| ED | Top right of census page header |
| Sheet | Top center (e.g., "Sheet 13-A") |
| Line | Left margin numbers (1-50 per page) |
| Family | "Family No." column |
| Dwelling | "Dwelling No." column |

### Verify Extracted Data

Compare extracted data against the image:
- Person name spelling
- Line number accuracy
- ED number format (varies by year)

---

## Step 5: Save or Skip

### Save Citation

Click **Save** to:
- Generate formatted footnote, short footnote, and bibliography
- Write to RootsMagic database
- Link census image to citation
- Mark citation as complete

### Skip Citation

Click **Skip** to:
- Move to next citation without saving
- Citation remains in "Incomplete" state
- Can process later

### Stop Batch

Click **Stop** to:
- End batch processing
- Progress is saved automatically
- Resume later from where you left off

---

## Citation Format Output

### What Gets Generated

**Footnote (full reference):**
```
1930 U.S. census, Greene County, Pennsylvania, Jefferson Township,
enumeration district (ED) 30-17, sheet 13-A, line 15, George B Iams;
imaged, "United States Census, 1930," FamilySearch
(https://familysearch.org/ark:/61903/1:1:XH3Z-4J8 : accessed 30 December 2025).
```

**Short Footnote (subsequent references):**
```
1930 U.S. census, Greene Co., Pa., Jefferson Twp., E.D. 30-17,
sheet 13-A, line 15, George B Iams.
```

**Bibliography (source list):**
```
U.S. Pennsylvania. Greene County. 1930 U.S Census. Population Schedule.
Imaged. "United States Census, 1930." FamilySearch
https://familysearch.org/ark:/61903/1:1:XH3Z-4J8 : 2025.
```

---

## Year-Specific Notes

### 1790-1840 (Household Schedules)

- Only head of household listed by name
- No enumeration districts
- Simple format: year, county, state, page, person name

### 1850-1870 (Pre-ED Era)

- Individual names listed
- No enumeration districts yet
- Uses page numbers (penned)
- 1850/1870: Includes dwelling/family numbers, line
- 1860: Uses family number instead of line (not indexed by FamilySearch)

### 1880 (ED Introduction)

- First census with Enumeration Districts
- Uses page numbers (stamped by NARA)
- Format: ED, page (stamped), line

### 1900-1940 (Sheet Era)

- Uses sheet numbers (1A, 1B, 2A, 2B format)
- ED required
- Family number included
- 1910-1940: "pop. sch." omitted in short footnote (only population schedules survive)

### 1950 (Stamp Era)

- Uses "stamp" instead of "sheet"
- ED required
- "pop. sch." returns in short footnote (distinguishes from sample forms)
- Some areas used household forms (different format)

---

## Handling Special Cases

### Slave Schedules (1850, 1860)

Source names begin with `Fed Census Slave Schedule:`

- Lists enslaved persons by owner
- Owner name appears with "owner" designation
- Column numbers (1 or 2) identify position on form

### Mortality Schedules (1850-1880)

Source names begin with `Fed Census Mortality Schedule:`

- Lists persons who died in preceding 12 months
- Simpler format (no ED for 1850-1870)

### Missing ED Numbers

For 1880-1950, ED is required. If not shown on FamilySearch page:

1. Click the **Information** button on FamilySearch image viewer
2. Look for "Enumeration District" in the metadata
3. Or check the top-right corner of the census form

### Household Forms (1950)

Some 1950 census areas (Ohio, Michigan) used household forms instead of standard forms:

- No sheet numbers - uses stamp and image number
- Format notes "household form" in citation
- Example: `stamp 366, image 372 of 441`

---

## Batch Recovery

### If RMCitecraft Crashes

State is automatically saved to `~/.rmcitecraft/batch_state.db`:

1. Restart RMCitecraft
2. Go to Batch Processing tab
3. Click "Resume" to continue from last position

### If Chrome Disconnects

1. Restart Chrome with `~/start-chrome.sh`
2. Log into FamilySearch
3. Click "Retry" in RMCitecraft

---

## Best Practices

### 1. Process by Year

Work through one census year at a time for consistency.

### 2. Batch Size

Process 20-50 citations per session to avoid fatigue.

### 3. Verify First Few

Carefully check the first 5-10 citations of each year to ensure formatting is correct.

### 4. Regular Saves

Don't accumulate too many processed citations before backing up your database.

### 5. Keep Notes

If you encounter unusual records, note them for later review.

---

## Troubleshooting

### "No citations found for year"

- Check that source names follow the pattern: `Fed Census: YYYY, State, County [...]`
- Verify the database path in your `.env` file

### "Chrome connection failed"

- Ensure Chrome is running with `--remote-debugging-port=9222`
- Check that no other application is using port 9222

### "FamilySearch page not loading"

- Verify you're logged into FamilySearch in the Chrome session
- Check your internet connection
- FamilySearch may be experiencing issues - try again later

### "ED field empty"

- Not all FamilySearch pages show ED prominently
- Click the Information button on the image viewer
- Or check the census form header

---

## Next Steps

- **[Image Workflow](IMAGE-WORKFLOW.md)** - Managing census images
- **[Citation Style Guide](../reference/CITATION-STYLE-GUIDE.md)** - Formatting conventions
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions

---

**Document Version**: 1.0
**Last Updated**: 2025-12-30
