# Quick Start Guide - Citation Manager UI

## Running the Application

### Option 1: Using the Entry Point (Recommended)

After running `uv sync` once, you can use the `rmcitecraft` command:

**Browser Mode (default):**
```bash
uv run rmcitecraft
```

**Native Mode (macOS Window):**
```bash
RMCITECRAFT_NATIVE=true uv run rmcitecraft
```

### Option 2: Direct Python Execution

**Browser Mode:**
```bash
uv run python -m rmcitecraft
```

**Native Mode:**
```bash
RMCITECRAFT_NATIVE=true uv run python -m rmcitecraft
```

### Mode Comparison

**Browser Mode (default):**
- Opens in your default web browser at http://localhost:8080
- Hot reload enabled (code changes automatically refresh)
- Good for development and testing

**Native Mode:**
- Opens as a native macOS window
- Better user experience for end users
- No browser UI elements (cleaner interface)

## Using the Citation Manager

### Step 1: Navigate to Citation Manager

1. Launch the application
2. Click on the **"Citation Manager"** tab in the top navigation

### Step 2: Select a Census Year

1. In the left panel, click the **"Census Year"** dropdown
2. Select a year (e.g., "1900 US Census")
3. Citations will load automatically

**Available Years:**
- 1790, 1800, 1810, 1820, 1830, 1840
- 1850, 1860, 1870, 1880, 1890
- 1900, 1910, 1920, 1930, 1940, 1950

### Step 3: Browse Citations

The left panel shows all citations for the selected year:

- **Green checkmark (✓)**: Citation already formatted
- **Blue circle (●)**: Citation complete and ready to format
- **Amber warning (⚠)**: Citation incomplete (missing fields)

Click on any citation to view details.

### Step 4: View Citation Details

The right panel shows three sections:

**1. Current Citation (Database)**
- Source Name from RootsMagic
- FamilySearch Entry text
- Existing Footnote (if any)

**2. Parsed Data**
- All extracted citation fields
- Missing fields shown in red: "(not found)"

**3. Generated Citation** (if complete)
- Full Footnote (Evidence Explained format)
- Short Footnote (abbreviated)
- Bibliography (bibliography format)
- Action buttons (Copy, Update)

### Step 5: Batch Selection

To select multiple citations:

1. Check the checkbox on each citation you want to select
2. Or click **"Select All"** to select all citations
3. Status label shows: "X of Y citations selected"

## Keyboard Shortcuts

- **Tab**: Navigate between UI elements
- **Space**: Toggle checkboxes
- **Enter**: Activate buttons
- **Cmd+Q** (Native mode): Quit application
- **Cmd+W** (Browser mode): Close tab

## Troubleshooting

### Database Connection Error

If you see "Database connection failed":

1. Check that `.env` file exists
2. Verify `RM_DATABASE_PATH` points to your `.rmtree` file
3. Ensure SQLite ICU extension is in `sqlite-extension/icu.dylib`

### No Citations Load

If the citation list is empty:

1. Check that the selected census year exists in your database
2. Verify Source Names follow pattern: `Fed Census: YYYY, State, County...`
3. Check logs: `logs/rmcitecraft.log`

### UI Doesn't Start

If the application doesn't launch:

1. Ensure UV virtual environment is active:
   ```bash
   source .venv/bin/activate
   ```

2. Install/update dependencies:
   ```bash
   uv sync
   ```

3. Check for port conflicts (default: 8080):
   ```bash
   lsof -i :8080
   ```

### Parsing Errors

If citations show "(not found)" for all fields:

- This is expected for some citations (e.g., 1790 with "[missing]" notation)
- Week 4 will add manual data entry for these cases
- Check logs for parsing errors: `logs/rmcitecraft.log`

## Testing the UI

Run the automated test suite:

```bash
uv run python test_ui_citation_manager.py
```

Expected output:
```
All Citation Manager tests passed! ✓
- Test 1: Citation Manager Initialization ✓
- Test 2: Citation Loading ✓
- Test 3: Person Name Extraction ✓
- Test 4: Batch Selection State ✓
```

## What Works in Week 3

✅ **Fully Functional:**
- Tab navigation
- Census year selection
- Citation loading from database
- Citation list display with status icons
- Citation detail view (3 sections)
- Parsed data display
- Generated citation formatting
- Batch selection (checkboxes + "Select All")
- Missing field detection

🔲 **Coming in Week 4:**
- "Copy Footnote" button implementation
- "Update Database" button implementation
- Missing data entry form
- Side-by-side browser integration
- Batch processing workflow
- Progress indicators
- Undo/redo support

## Configuration

### Environment Variables

Edit `.env` file to configure:

```bash
# Database
RM_DATABASE_PATH=data/Iiams.rmtree

# UI Mode
RMCITECRAFT_NATIVE=true  # or false for browser mode

# Logging
LOG_LEVEL=INFO
```

### Window Size (Native Mode)

Currently uses NiceGUI defaults. Week 4 will add:
- Custom window size
- Window positioning
- Split-screen mode (app + browser)

## Support

- **Documentation**: See docs/archive/WEEK3-SUMMARY.md for technical details
- **Issues**: Check logs in `logs/` directory
- **Database Schema**: See `docs/reference/schema-reference.md`

## Next Steps

After testing the UI, Week 4 will add:
1. Database write operations
2. Missing data entry form
3. Batch processing
4. Browser integration for viewing FamilySearch pages
5. Copy to clipboard functionality

---

**Last Updated:** 2025-10-20
**Version:** Week 3 - Citation Manager UI
