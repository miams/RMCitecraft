---
priority: reference
topics: [database, census, citation, batch, testing]
---

# Testing Image Download - Step by Step

## What Was Fixed

1. **Extension now finds ANY FamilySearch tab** (not just the active one)
   - You can switch to RMCitecraft window after opening FamilySearch
   - Extension will find the FamilySearch tab in the background

2. **Better error reporting**
   - Failed downloads now show in the Error Panel (bug button)
   - Click the 🐛 button in bottom-right to see details

3. **Command checking every 2 seconds**
   - Download commands are delivered within 2 seconds

## How to Test

### Step 1: Setup
1. **Reload the extension** in Chrome:
   - Go to `chrome://extensions/`
   - Find "RMCitecraft FamilySearch Assistant"
   - Click the reload icon (↻)

2. **Restart RMCitecraft**:
   ```bash
   rmcitecraft restart
   ```

### Step 2: Open FamilySearch Page
1. Open a FamilySearch census **record page** in Chrome:
   - Example: `https://www.familysearch.org/ark:/61903/1:1:ML83-PVK`
   - (The page with person details, not the image viewer)

2. The extension should **automatically send** the citation data
   - Check extension popup: "Sent Today" should increment

### Step 3: Process Citation in RMCitecraft
1. Switch to RMCitecraft window
2. You should see a **new pending citation** at the top
3. Click **"Review & Apply"** button
4. In the dialog:
   - Check the generated citations look correct
   - Click **"Apply to Database"**

### Step 4: Image Download (Automatic)
Within 2 seconds, the extension should:
1. Receive the download command
2. Find the FamilySearch tab (even if it's not active)
3. Click the download button
4. Image downloads to ~/Downloads

**What to watch:**
- Extension console: `[RMCitecraft] Found FamilySearch tab: ...`
- Chrome downloads: Image file appears
- RMCitecraft logs: Image processing starts

### Step 5: Check for Errors
If something goes wrong:
1. Look for the **🐛 bug button** in bottom-right corner of RMCitecraft
2. If there's a badge, click it to see error details
3. Click "Copy" to copy the error for debugging

## Expected Results

### Success Indicators
✅ Citation appears in RMCitecraft pending list
✅ "Apply to Database" succeeds
✅ "Image missing - download requested" notification
✅ Extension console shows: "Found FamilySearch tab"
✅ Image downloads to ~/Downloads folder
✅ RMCitecraft processes and renames image
✅ Image appears in RootsMagic linked to citation

### Common Issues

**Issue**: "No FamilySearch tabs found"
- **Fix**: Keep the FamilySearch page open (any tab, doesn't need to be active)
- **Check**: Make sure you didn't close the FamilySearch tab

**Issue**: "Failed to communicate with FamilySearch tab"
- **Fix**: Reload the FamilySearch page
- **Reason**: Content script may not be loaded

**Issue**: Image doesn't download
- **Check Extension Console**:
  1. Go to `chrome://extensions/`
  2. Click "service worker" under RMCitecraft extension
  3. Look for error messages

**Issue**: Image downloads but isn't processed
- **Check App Logs**:
  ```bash
  tail -f logs/rmcitecraft.log | grep -i image
  ```
- **Verify**: `WATCH_FOLDER` in `.env` points to ~/Downloads

## Troubleshooting Commands

```bash
# Check if RMCitecraft is running
rmcitecraft status

# View last 50 lines of logs
tail -50 logs/rmcitecraft.log

# Watch logs in real-time
tail -f logs/rmcitecraft.log

# Restart everything
rmcitecraft restart
# Then reload extension in Chrome
```

## What the Logs Should Show

### RMCitecraft Logs (Success)
```
INFO - Citation 9763 missing image, requesting download...
INFO - Queued download_image command [ID]
DEBUG - WebSocket received: check_commands
DEBUG - Returning 1 pending command(s)
DEBUG - WebSocket received: command_response
INFO - Command completed: download_image
INFO - New file detected: census-image.jpg
INFO - Processing image for census...
INFO - Image moved to: 1910 Federal/...
```

### Extension Console (Success)
```
[RMCitecraft] Received command: { type: 'download_image', ... }
[RMCitecraft] Found FamilySearch tab: 123 https://familysearch.org/...
[RMCitecraft Content] Attempting to download census image...
[RMCitecraft Content] On image viewer page - looking for download button...
[RMCitecraft Content] Found download button with data-testid, clicking...
```

## Notes

- **FamilySearch tab can be in any window** - extension will find it
- **Tab doesn't need to be active** - can be in background
- **Multiple FamilySearch tabs**: Extension uses most recently accessed
- **Image viewer page**: If you're already on the image viewer page (ark:/61903/3:1:...), that's perfect!

## Report Issues

If it still doesn't work, provide:
1. Screenshot of error from bug button (🐛)
2. Extension console logs
3. RMCitecraft logs (last 100 lines)
4. FamilySearch URL you were on
