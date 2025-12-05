---
priority: reference
topics: [database, census, citation, batch, testing]
---

# Census Image Download Workflow

## Overview

RMCitecraft automates census image downloads from FamilySearch using a multi-strategy approach that handles different page types and structures.

## FamilySearch URL Structure

### Census Record Pages
- **URL Pattern**: `https://www.familysearch.org/ark:/61903/1:1:XXXXX`
- **Purpose**: Displays person information and census data
- **Content**: Tables with person details, event information, etc.

### Image Viewer Pages
- **URL Pattern**: `https://www.familysearch.org/ark:/61903/3:1:XXXXX`
- **Purpose**: Displays the actual census image with download controls
- **Content**: Image viewer with zoom, adjust, download buttons

## Automated Download Strategy

### Strategy 1: Navigation (Record Page → Image Viewer)
If on a census record page (ark:/61903/1:1:...):
1. Search for links to image viewer pages (ark:/61903/3:1:...)
2. Navigate to the image viewer page
3. Proceed to Strategy 2

### Strategy 2: Click Download Button (Image Viewer Page)
If on image viewer page (ark:/61903/3:1:...):
1. **Primary**: Look for `button[data-testid="download-image-button"]`
2. **Fallback**: Try `button[aria-label="Download"]`
3. Click the button to trigger download
4. Browser downloads image to default Downloads folder

### Strategy 3: Direct Image URL (Last Resort)
If download button not found:
1. Search for image elements on page
2. Extract image URL
3. Use Chrome Downloads API to download directly

## Testing the Workflow

### From Census Record Page
```
1. Open: https://www.familysearch.org/ark:/61903/1:1:6FSK-61C7
2. RMCitecraft sends "Send to RMCitecraft" (citation data extracted)
3. Click "Apply to Database" in RMCitecraft
4. Extension receives download_image command
5. Extension navigates to image viewer page
6. Extension clicks download button
7. Image downloads to ~/Downloads
8. RMCitecraft watches Downloads folder
9. Image is renamed and moved to census folder
10. Database records created linking image to citation
```

### From Image Viewer Page
```
1. Open: https://www.familysearch.org/ark:/61903/3:1:3QHN-GQHW-P7SW
2. Extension already on image viewer page
3. Extension finds and clicks download button immediately
4. Rest of workflow continues as above
```

## Key Extension Updates (content.js)

### New Download Logic
- **Page Detection**: Identifies record page vs. image viewer page by URL pattern
- **Smart Navigation**: Automatically navigates to image viewer if on record page
- **Reliable Button Selector**: Uses FamilySearch's `data-testid="download-image-button"`
- **Fallback Mechanisms**: Multiple strategies if primary method fails

### Debug Output
Extension logs helpful debug information:
```javascript
[RMCitecraft Content] Attempting to download census image...
[RMCitecraft Content] Current page type: { isImageViewerPage: true, isRecordPage: false, url: "..." }
[RMCitecraft Content] On image viewer page - looking for download button...
[RMCitecraft Content] Found download button with data-testid, clicking...
```

## Configuration Requirements

### Environment Variables (.env)
```bash
# Where browser downloads images
WATCH_FOLDER=/Users/yourusername/Downloads

# Where census images are organized
RM_MEDIA_ROOT_DIRECTORY=/Users/yourusername/Genealogy/RootsMagic/Files/Records - Census/

# RootsMagic database path
RM_DATABASE_PATH=/path/to/database.rmtree
```

### Census Folder Structure
```
Records - Census/
├── 1790 Federal/
├── 1800 Federal/
├── ...
├── 1940 Federal/
├── 1950 Federal/
└── 1850 Federal Slave Schedule/
```

## Troubleshooting

### Image Not Downloading
1. **Check URL**: Ensure you're on a FamilySearch page (contains `ark:/61903/`)
2. **Check Tab**: FamilySearch tab must be active (focused)
3. **Check Console**: Open Chrome DevTools → Console → Filter by "[RMCitecraft]"
4. **Manual Test**: Try clicking the download button manually on the image viewer page

### Image Not Processing
1. **Check Logs**: `tail -f logs/rmcitecraft.log`
2. **Verify Watch Folder**: Ensure `WATCH_FOLDER` matches browser downloads location
3. **Check Permissions**: Ensure RMCitecraft has read/write access to folders
4. **Verify Image Watcher**: Look for "Image watcher started" in logs

### Extension Errors
1. **Reload Extension**: Chrome → Extensions → Reload
2. **Check Permissions**: Extension needs download permissions
3. **Verify Connection**: Extension popup should show "Connected"
4. **Check Background Script**: Chrome → Extensions → Service Worker → Console

## Expected Behavior

### Success Indicators
- ✅ Extension popup shows "Image downloaded" notification
- ✅ Image appears in Downloads folder
- ✅ RMCitecraft log shows "Processing image for census..."
- ✅ Image moves to correct census year folder with proper name
- ✅ Database records created in MultimediaTable and MediaLinkTable
- ✅ RootsMagic shows linked image for the citation

### Timing
- **Citation extraction**: Instant (on page load)
- **Image download request**: After "Apply to Database" clicked
- **Download initiation**: 1-2 seconds
- **Browser download**: 2-5 seconds (depends on image size)
- **Image processing**: 1-2 seconds
- **Total time**: ~5-10 seconds from "Apply to Database" to linked image

## Future Enhancements

- [ ] Batch image downloads for multiple citations
- [ ] Image quality selection (high-res vs. thumbnail)
- [ ] Retry logic for failed downloads
- [ ] Progress indicator in RMCitecraft UI
- [ ] Support for other FamilySearch record types (vital records, etc.)
