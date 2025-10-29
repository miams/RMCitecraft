# Census Image Management - Testing Guide

**Version**: 1.0
**Last Updated**: 2025-01-29

## Overview

This guide explains how to test the census image management system in its current state.

## Current Implementation Status

### ✅ Implemented (Ready to Test)
- Image processing service
- File watcher (monitors ~/Downloads)
- Automatic file renaming and organization
- Database integration (links images to citations and events)
- API endpoints

### ❌ Not Yet Implemented
- Browser extension (critical for automated workflow)
- Image status indicators in UI
- Image Manager tab
- Real-time progress notifications

## Manual Testing (Without Extension)

Since the browser extension doesn't exist yet, you can manually simulate the workflow:

### Test Scenario 1: Manual Image Download and Processing

**Prerequisites:**
1. RMCitecraft running (`uv run python -m rmcitecraft`)
2. At least one pending citation imported
3. A census image file ready to download

**Steps:**

1. **Start RMCitecraft**
   ```bash
   uv run python -m rmcitecraft
   ```

2. **Navigate to Citation Manager tab**

3. **Note the pending citation details:**
   - Person name: e.g., "Jesse Dorsey Iams"
   - Census year: e.g., 1930
   - Location: e.g., "Tulsa, Oklahoma"

4. **Click "Download Image" button**
   - This registers the image for processing
   - Command is queued for extension (but extension doesn't exist yet)

5. **Manually download census image from FamilySearch:**
   - Open the FamilySearch URL in your browser
   - Right-click the census image
   - "Save Image As..." → Save to **~/Downloads** folder
   - **Important**: Use the browser's default filename

6. **Watch the logs** (in terminal where RMCitecraft is running):
   ```
   File watcher detected: image.jpg
   Processing downloaded file: image.jpg
   Registered image for processing: img_123...
   Moving: ~/Downloads/image.jpg -> ~/Genealogy/RootsMagic/Files/Records - Census/1930 Federal/1930, Oklahoma, Tulsa - Iams, Jesse Dorsey.jpg
   Created media record: MediaID=42
   Linked media 42 to citation cit_456
   Successfully processed image
   ```

7. **Verify in file system:**
   ```bash
   ls -la ~/Genealogy/RootsMagic/Files/Records\ -\ Census/1930\ Federal/
   ```
   You should see: `1930, Oklahoma, Tulsa - Iams, Jesse Dorsey.jpg`

8. **Verify in RootsMagic database:**
   ```bash
   sqlite3 ~/Genealogy/RootsMagic/Iiams.rmtree "SELECT MediaID, MediaFile, Caption FROM MultimediaTable ORDER BY MediaID DESC LIMIT 5;"
   ```

### Test Scenario 2: Duplicate Detection

**Steps:**

1. Follow Test Scenario 1 to process an image

2. Download the **same census image** again to ~/Downloads

3. Watch the logs:
   ```
   Duplicate image detected: 1930, Oklahoma, Tulsa - Iams, Jesse Dorsey.jpg (existing MediaID=42)
   Linked existing media to new citation
   Deleted duplicate download
   ```

4. Verify only one file exists in census folder (no duplicates)

### Test Scenario 3: Multiple Images in Sequence

**Steps:**

1. Have 3 pending citations ready (same or different years)

2. Click "Download Image" for first citation

3. Manually download first census image to ~/Downloads

4. Wait for processing to complete (watch logs)

5. Click "Download Image" for second citation

6. Download second census image

7. Repeat for third

8. Verify all three images are:
   - Renamed correctly
   - In correct year folders
   - Linked in database

## API Testing (Without UI)

You can test the image processing system directly via API:

### 1. Register a Pending Image

```bash
curl -X POST http://localhost:8080/api/image/register \
  -H "Content-Type: application/json" \
  -d '{
    "image_id": "test_img_001",
    "citation_id": "cit_123",
    "year": 1930,
    "state": "Oklahoma",
    "county": "Tulsa",
    "surname": "Iams",
    "given_name": "Jesse Dorsey",
    "familysearch_url": "https://familysearch.org/ark:/61903/1:1:XXXX-XXX",
    "access_date": "2025-01-29"
  }'
```

### 2. Download Image Manually

Download a census image to ~/Downloads

### 3. Check Image Status

```bash
curl http://localhost:8080/api/image/test_img_001/status
```

**Expected Response:**
```json
{
  "image_id": "test_img_001",
  "status": "linked"
}
```

### 4. Get Active Images

```bash
curl http://localhost:8080/api/image/active
```

### 5. Get Failed Images

```bash
curl http://localhost:8080/api/image/failed
```

## Expected File Organization

After processing, census images should be organized as:

```
~/Genealogy/RootsMagic/Files/Records - Census/
├── 1790 Federal/
├── 1800 Federal/
├── ...
├── 1930 Federal/
│   └── 1930, Oklahoma, Tulsa - Iams, Jesse Dorsey.jpg
├── 1940 Federal/
│   └── 1940, Texas, Milam - Iiams, Frank W..jpg
└── 1950 Federal/
```

**Filename Format:** `YYYY, State, County - Surname, GivenName.ext`

## Database Verification

### Check MultimediaTable

```sql
SELECT
    MediaID,
    MediaPath,
    MediaFile,
    Caption,
    Date
FROM MultimediaTable
WHERE MediaPath LIKE '%Census%'
ORDER BY MediaID DESC
LIMIT 10;
```

### Check MediaLinkTable (Links to Citations)

```sql
SELECT
    ml.LinkID,
    ml.MediaID,
    ml.OwnerType,
    ml.OwnerID,
    m.MediaFile,
    c.CitationName
FROM MediaLinkTable ml
JOIN MultimediaTable m ON ml.MediaID = m.MediaID
LEFT JOIN CitationTable c ON ml.OwnerID = c.CitationID AND ml.OwnerType = 4
WHERE ml.OwnerType = 4  -- Citation links
ORDER BY ml.LinkID DESC
LIMIT 10;
```

### Check MediaLinkTable (Links to Events)

```sql
SELECT
    ml.LinkID,
    ml.MediaID,
    ml.OwnerType,
    ml.OwnerID,
    m.MediaFile,
    e.EventType
FROM MediaLinkTable ml
JOIN MultimediaTable m ON ml.MediaID = m.MediaID
LEFT JOIN EventTable e ON ml.OwnerID = e.EventID AND ml.OwnerType = 2
WHERE ml.OwnerType = 2  -- Event links
ORDER BY ml.LinkID DESC
LIMIT 10;
```

## Troubleshooting

### Issue: File watcher not detecting images

**Check logs for:**
```
File watcher started: monitoring /Users/yourname/Downloads
```

**If not started:**
- Verify `RM_MEDIA_ROOT_DIRECTORY` is set in .env
- Check ~/Downloads exists

**Manual verification:**
```bash
# In Python console
from pathlib import Path
print(Path.home() / "Downloads")
print((Path.home() / "Downloads").exists())
```

### Issue: Image not processing

**Check:**
1. Is file watcher running? (check logs at startup)
2. Is image file in ~/Downloads?
3. Is image a valid format? (JPG, PNG, PDF, TIFF)
4. Check logs for errors

**Common errors:**
- `No pending image found for: image.jpg` - Click "Download Image" button first
- `Invalid census year` - Citation data missing year field
- `Failed to move file` - Permission or disk space issue

### Issue: Duplicate not detected

**Verify:**
```bash
# Check if original file exists
ls -la ~/Genealogy/RootsMagic/Files/Records\ -\ Census/1930\ Federal/

# Check database for existing media
sqlite3 ~/Genealogy/RootsMagic/Iiams.rmtree \
  "SELECT MediaID, MediaFile FROM MultimediaTable WHERE MediaFile LIKE '%Iams%';"
```

### Issue: Wrong directory or filename

**Check citation data:**
- Year: Must be 1790-1950, divisible by 10
- State: Parsed from eventPlace (last comma-separated part)
- County: Parsed from eventPlace (second-to-last part)
- Name: Surname is last word, given name is rest

**Example:**
- eventPlace: "Tulsa, Oklahoma" → County="Tulsa", State="Oklahoma"
- name: "Jesse Dorsey Iams" → Given="Jesse Dorsey", Surname="Iams"

## Next Steps: Building the Browser Extension

To complete the automated workflow, a browser extension is needed with:

1. **Background script** that polls `/api/extension/commands` every 2 seconds
2. **Command handler** for `download_image` command:
   ```javascript
   if (command.type === 'download_image') {
       const { url } = command.data;
       // Navigate to FamilySearch page
       // Download census image
       // Confirm completion
   }
   ```
3. **Citation extractor** (already implemented in extension)

See: `docs/architecture/IMAGE-MANAGEMENT-ARCHITECTURE.md` for extension integration protocol.

## Performance Expectations

**File Detection:** < 2 seconds after download completes
**Processing:** < 1 second for typical 500KB image
**Database Operations:** < 500ms

## Known Limitations

1. **No UI feedback** - User doesn't see status after clicking "Download Image"
2. **Manual download required** - No browser extension yet
3. **No retry UI** - Failed images must be manually retried via API
4. **No Image Manager tab** - Can't browse processed images in UI

These will be addressed in Phase 3 (UI Enhancement) and Phase 4 (Smart Features).

## Success Criteria

A successful test shows:

✅ File watcher starts on application launch
✅ Clicking "Download Image" registers metadata
✅ Downloaded file detected in ~/Downloads
✅ File renamed with standardized format
✅ File moved to correct census year folder
✅ MultimediaTable record created
✅ MediaLinkTable entry links to citation
✅ MediaLinkTable entry links to event (if event_id provided)
✅ Duplicate detection works
✅ Multiple images process in sequence

---

**Document Version:** 1.0
**Phase:** 1 (Core Infrastructure) + 2 (UI Integration)
**Next Phase:** 3 (Image Manager UI) - See IMAGE-IMPLEMENTATION-PLAN.md
