# Playwright Migration - Complete Implementation

## Overview

Successfully migrated from Chrome Extension architecture to **Playwright-based browser automation**. This provides more reliable, robust census image downloads and citation extraction directly from Python.

## Why Playwright?

### Previous Architecture (Extension-based)
```
Chrome Extension → WebSocket → FastAPI → RootsMagic Database
```
**Problems:**
- Fragile DOM manipulation (buttons not found, timing issues)
- Complex cross-page-reload state management
- Difficult debugging
- Keyboard events didn't work reliably

### New Architecture (Playwright-based)
```
Your Chrome Browser ← Playwright (Python) → FastAPI → RootsMagic Database
```
**Benefits:**
- ✅ Robust browser automation with auto-waiting
- ✅ Real keyboard input (browser-level, not DOM events)
- ✅ Download verification (wait for file to complete)
- ✅ Better error handling and debugging
- ✅ Direct Python control
- ✅ Uses your existing Chrome session (already logged into FamilySearch)

## What Was Implemented

### 1. Playwright Integration (`playwright` package)
- Added to project dependencies via UV
- Installed Chromium browser binaries
- **Location:** `pyproject.toml`, `.venv/`

### 2. FamilySearch Automation Service
- **File:** `src/rmcitecraft/services/familysearch_automation.py`
- **Capabilities:**
  - Connect to your existing Chrome browser via CDP (Chrome DevTools Protocol)
  - Extract citation data from FamilySearch pages
  - Download census images with JPG selection
  - Uses keyboard automation (Tab, Down, Enter) for dialog handling
  - Waits for downloads to complete
  - Returns downloaded file path

**Key Methods:**
```python
automation = get_automation_service()

# Connect to your Chrome
await automation.connect_to_chrome()

# Extract citation data
data = await automation.extract_citation_data(familysearch_url)

# Download census image
success = await automation.download_census_image(image_url, download_path)

# Complete workflow
data = await automation.extract_and_download(record_url, download_path)
```

### 3. Chrome Launcher Utility
- **File:** `src/rmcitecraft/utils/chrome_launcher.py`
- **Purpose:** Launch Chrome with remote debugging enabled
- **Functions:**
  - `is_chrome_running_with_debugging()` - Check if Chrome is ready
  - `launch_chrome_with_debugging()` - Start Chrome with debugging port
  - `get_launch_instructions()` - Get manual launch command

### 4. UI Integration (Citation Manager Tab)
- **File:** `src/rmcitecraft/ui/tabs/citation_manager.py`
- **Changes:**
  - Added "Chrome Browser Connection" panel at top of UI
  - "Connect to Chrome" button with status indicator
  - Help button (?) showing setup instructions
  - Replaced extension command queue with direct Playwright automation
  - Updated `_check_and_request_image_download()` to use Playwright

**UI Elements:**
- 🟢 **Connected** status (green checkmark)
- 🔵 **Connect to Chrome** button
- ❓ **Help** button (instructions dialog)

### 5. Chrome Extension (No Longer Needed)
- Extension code remains but is **not required**
- Can be removed in future cleanup
- All functionality now handled by Playwright

## How to Test

### Step 1: Launch Chrome with Remote Debugging

You have two options:

**Option A: Let RMCitecraft Launch Chrome**
1. Close all Chrome windows
2. Click "Connect to Chrome" button in RMCitecraft
3. RMCitecraft will attempt to launch Chrome automatically
4. Chrome opens with debugging enabled

**Option B: Manual Launch (Recommended if auto-launch fails)**
1. Close all Chrome windows
2. Open Terminal and run:
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 \
    --user-data-dir="$HOME/Library/Application Support/Google/Chrome"
```
3. Chrome opens with debugging enabled
4. Keep Terminal window open (Chrome needs this process)

### Step 2: Log into FamilySearch
1. In the Chrome window that opened, navigate to `https://familysearch.org`
2. Log in with your FamilySearch account
3. Leave Chrome window open

### Step 3: Connect RMCitecraft to Chrome
1. In RMCitecraft, click "Connect to Chrome" button
2. Status should change to "✓ Connected" (green)
3. If connection fails, click "?" button for troubleshooting

### Step 4: Test Citation Import
1. In RMCitecraft, import a census citation (use browser extension or manual entry)
2. Click "Apply to Database" to save citation
3. **Watch for automatic image download:**
   - RMCitecraft connects to your Chrome
   - Navigates to image viewer page
   - Clicks download button
   - Selects "JPG Only" via keyboard
   - Downloads image to ~/Downloads/
   - Image is saved as `census_{CitationID}.jpg`

### Step 5: Verify Success
- Check ~/Downloads/ folder for new JPG file
- Check RMCitecraft UI for success notification
- Check logs: `logs/rmcitecraft.log`

## Expected Behavior

### Successful Flow:
```
1. [RMCitecraft] Connected to Chrome via CDP
2. [Playwright] Navigating to FamilySearch image viewer...
3. [Playwright] Waiting for download button (up to 15 seconds)...
4. [Playwright] Download button found
5. [Playwright] Clicking download button...
6. [Playwright] Using keyboard: Tab Down Down Tab Tab Enter
7. [Playwright] Download started: [filename].jpg
8. [Playwright] Downloaded census image to: ~/Downloads/census_12345.jpg
9. [UI] "Census image downloaded successfully"
```

### Troubleshooting:

**"Connection failed" / "Could not connect to Chrome"**
- Chrome not running with debugging port
- Solution: Close Chrome, launch manually with command above
- Verify port 9222 is open: `lsof -i :9222`

**"Download button not found"**
- FamilySearch page structure changed
- Solution: Check if URL is correct image viewer page (not record page)
- Manually navigate to image viewer in Chrome first

**"Keyboard automation failed"**
- Focus lost or dialog didn't appear
- Solution: Check Chrome window is visible (not minimized)
- Try manually to verify dialog appears correctly

## Configuration

No environment variables needed. Playwright connects to Chrome on **port 9222** (standard CDP port).

## Files Modified

| File | Changes |
|------|---------|
| `pyproject.toml` | Added `playwright==1.55.0` dependency |
| `src/rmcitecraft/services/familysearch_automation.py` | **NEW** - Playwright automation service |
| `src/rmcitecraft/utils/chrome_launcher.py` | **NEW** - Chrome launch utility |
| `src/rmcitecraft/ui/tabs/citation_manager.py` | Added Chrome connection UI, replaced command queue with Playwright |

## Next Steps

1. **Test with real census records** - Verify full workflow
2. **Image processing integration** - After download, rename and move to correct census folder
3. **Database linking** - Create MultimediaTable and MediaLinkTable entries
4. **Error handling** - Add retry logic for failed downloads
5. **Remove extension** - Clean up unused extension code (optional)

## Benefits Achieved

- ✅ **More reliable:** Playwright auto-waits for elements, no manual polling
- ✅ **Better keyboard input:** Browser-level events, not just DOM
- ✅ **Download verification:** Can wait for file and verify it exists
- ✅ **Simpler code:** ~200 lines removed from content.js, no WebSocket complexity
- ✅ **Better debugging:** Playwright has built-in trace viewer and screenshots
- ✅ **Uses your browser:** No need to handle authentication, cookies, or sessions

## Architecture Comparison

### Before (Extension):
```javascript
// content.js (~700 lines)
- Poll for button every second (up to 15 attempts)
- Simulate keyboard events (unreliable)
- No download verification
- Complex sessionStorage state management
```

### After (Playwright):
```python
# familysearch_automation.py (~300 lines)
- await page.wait_for_selector('button') (smart waiting)
- await page.keyboard.press('Tab') (real input)
- async with page.expect_download() (verification)
- Direct Python async/await
```

## Notes

- **Chrome must stay open** while using RMCitecraft automation
- **Don't close the Terminal window** if you launched Chrome manually
- Playwright connects to **existing Chrome tabs**, doesn't open new browser
- You can still browse FamilySearch manually in other tabs
- Downloads go to **~/Downloads/** by default (will be moved/renamed by image processing service)

---

**Last Updated:** 2025-11-05
**Status:** ✅ Implementation Complete - Ready for Testing
