# Draft Registration Image Download

Guide for downloading draft registration images from FamilySearch and AncestryLibrary.com.

## Overview

RMCitecraft can now download draft registration card images from both:
- **FamilySearch** - Free, accessible anywhere
- **AncestryLibrary.com** - Available when connected to library WiFi

The automation downloads both sides of the draft card (front and back) and combines them into a single horizontal image with proper trimming of black borders.

## Prerequisites

### 1. Chrome with Remote Debugging

Start Chrome with remote debugging enabled **before** running RMCitecraft:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 \
    --no-first-run \
    --user-data-dir=~/.chrome-debug-profile
```

**Important:**
- Use a separate user data directory (`~/.chrome-debug-profile`) to avoid conflicts with your main Chrome profile
- Keep this Chrome window open while using RMCitecraft
- Log into FamilySearch or AncestryLibrary in this Chrome window

### 2. ImageMagick

Image combining requires ImageMagick (`convert` command):

```bash
# Check if installed
which convert

# Install via Homebrew (macOS)
brew install imagemagick
```

## Workflow

### Step 1: Import Draft Registration Citations

1. Prepare a CSV/XLSX file with draft registration data:
   - Required columns: `RIN`, `Given`, `Surname`, `FamilySearch_Citation`
   - `FamilySearch_Citation` can contain **either** a FamilySearch URL **or** AncestryLibrary URL

Example CSV:
```csv
RIN,Given,Surname,State,FamilySearch_Citation
123,Charles,Birdell,Ohio,https://www.ancestrylibrary.com/search/collections/2238/records/199636392
456,John,Smith,Ohio,https://www.familysearch.org/ark:/61903/1:1:K6PP-VBL
```

2. Use the **Draft Registration Processing** tab in RMCitecraft
3. Upload your CSV/XLSX file
4. Configure processing options:
   - ✅ Skip duplicates (recommended)
   - ✅ Validate persons (recommended)
5. Click **Process Records**

**What happens:**
- Creates Source and Citation records in RootsMagic
- For AncestryLibrary URLs: Creates placeholder citation with URL stored
- For FamilySearch URLs: Parses metadata and creates formatted citation
- Links citations to persons by RIN

### Step 2: Download Images

After citations are created, download the images:

```bash
# Download all draft registration images
python scripts/download_draft_images.py

# Download for specific person
python scripts/download_draft_images.py --person-id 123

# Preview what would be downloaded
python scripts/download_draft_images.py --dry-run

# Specify output directory
python scripts/download_draft_images.py --output-dir ~/Desktop/draft_images
```

**Default output directory:**
```
~/Genealogy/RootsMagic/Files/Records - Draft/
```

**What happens:**
1. Queries database for draft registration citations with URLs
2. Connects to Chrome via CDP (port 9222)
3. For each AncestryLibrary citation:
   - Navigates to the record page
   - Clicks image thumbnail to open viewer
   - Downloads front of card (image 1)
   - Clicks "Next" button
   - Downloads back of card (image 2)
   - Trims black borders from both images (25% fuzz)
   - Combines horizontally with left image centered vertically
   - Saves as: `draft_reg_{CitationID}_{PersonName}.jpg`

## Image Combining Details

### Process

1. **Trim black borders** - Removes scan borders from both images (25% fuzz tolerance)
2. **Vertical centering** - Extends shorter image (usually front of card) to height of taller image (back of card)
3. **Horizontal append** - Places front on left, back on right
4. **Final trim** - Removes any outer black borders from combined result

### Example Result

```
┌──────────────────────┬──────────────────┐
│                      │                  │
│                      │  REGISTRAR'S     │
│  REGISTRATION CARD   │  REPORT          │
│  (Front - Horizontal)│  (Back-Vertical) │
│                      │                  │
└──────────────────────┴──────────────────┘
```

The front of the card is centered vertically to align nicely with the taller back.

## Troubleshooting

### Error: "Failed to connect to Chrome"

**Solution:**
1. Ensure Chrome is running with remote debugging:
   ```bash
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
       --remote-debugging-port=9222 \
       --no-first-run \
       --user-data-dir=~/.chrome-debug-profile
   ```
2. Check if port 9222 is accessible:
   ```bash
   curl http://localhost:9222/json
   ```

### Error: "ImageMagick command failed"

**Solution:**
Install ImageMagick:
```bash
brew install imagemagick
```

### AncestryLibrary: Login Required

**Solution:**
1. In the Chrome window (with remote debugging), navigate to ancestrylibrary.com
2. Log in with your library credentials
3. Re-run the download script

### Images Not Downloading

**Checklist:**
- ✅ Chrome is running with CDP on port 9222
- ✅ Logged into AncestryLibrary or FamilySearch in that Chrome window
- ✅ For AncestryLibrary: Connected to library WiFi
- ✅ Citations exist in database with valid URLs
- ✅ ImageMagick installed

## Code Changes Summary

### New Files

1. **`src/rmcitecraft/services/ancestrylibrary_automation.py`**
   - Playwright automation for AncestryLibrary.com
   - Downloads both images (front and back)
   - Combines images with proper trimming

2. **`scripts/download_draft_images.py`**
   - CLI script to download images for existing citations
   - Supports both FamilySearch and AncestryLibrary
   - Automatic file organization

### Modified Files

1. **`src/rmcitecraft/services/draft_batch_processor.py`**
   - Removed skip logic for AncestryLibrary URLs
   - Added conditional processing for AncestryLibrary vs FamilySearch
   - Creates placeholder citations for AncestryLibrary (populated after download)

2. **`src/rmcitecraft/services/draft_database_writer.py`**
   - Added `check_duplicate_source_by_url()` method
   - Enables duplicate detection for AncestryLibrary citations by URL

## Future Enhancements

- [ ] FamilySearch image download automation
- [ ] Auto-download during citation import (optional)
- [ ] UI button to trigger downloads for selected persons
- [ ] Batch download with progress tracking
- [ ] Citation metadata update after AncestryLibrary download

## References

- [Playwright Documentation](https://playwright.dev/python/)
- [ImageMagick Convert Command](https://imagemagick.org/script/convert.php)
- [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/)
