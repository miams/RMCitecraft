---
priority: reference
topics: [census, citation, testing, ui, automation]
---

# Extension Debugging Guide

## Step-by-Step Debugging Process

### 1. Reload Extension (MANDATORY after any code changes)

```
1. Open chrome://extensions/
2. Find "RMCitecraft FamilySearch Assistant"
3. Click the circular refresh icon ⟳
4. Verify "Errors" button is not shown (no errors)
```

### 2. Check Content Script Is Loading

**On ANY FamilySearch Page:**

```
1. Navigate to: https://www.familysearch.org
2. Press F12 (or Cmd+Option+I on Mac)
3. Go to Console tab
4. Look for: [RMCitecraft Content] Content script loaded on: ...
```

**Expected Output:**
```
[RMCitecraft Content] Content script loaded on: https://www.familysearch.org/
[RMCitecraft Content] Content script initialized
```

**If you DON'T see these messages:**
- Extension wasn't reloaded properly → Go to step 1
- Page was loaded before extension → Close tab completely, open new one
- Content script has errors → Check extension errors page

### 3. Check Content Script on Census Page

**On a Census Record Page:**

Navigate to: `https://www.familysearch.org/ark:/61903/1:1:M6NQ-Z9F`

**Expected Console Output:**
```
[RMCitecraft Content] Content script loaded on: https://www.familysearch.org/ark:/61903/1:1:M6NQ-Z9F
[RMCitecraft Content] Content script initialized
[RMCitecraft Content] Census page detected
[RMCitecraft Content] Auto-send scheduled for 2 seconds
[RMCitecraft Content] Auto-extracting census data...
[RMCitecraft Content] Extracted census data: {familySearchUrl: "...", ...}
[RMCitecraft Content] Sending data to RMCitecraft...
[RMCitecraft Content] ✓ Data sent successfully
```

### 4. Check Popup Console

**To view popup logs:**

```
1. Click the extension icon to open popup
2. Right-click anywhere in the popup
3. Select "Inspect"
4. Go to Console tab in the new DevTools window
```

**Expected Output on Popup Open:**
```
[RMCitecraft Popup] Initializing popup...
[RMCitecraft Popup] Settings loaded: {rmcitecraftPort: 8080, autoActivateEnabled: true}
[RMCitecraft Popup] Activity log and stats loaded
[RMCitecraft Popup] Event listeners set up
[RMCitecraft Popup] Popup initialized successfully
```

### 5. Test Manual Send Button

**With Popup DevTools Open:**

```
1. Make sure you're on a FamilySearch census page
2. Click "Send to RMCitecraft" button in popup
3. Watch the console
```

**Expected Output:**
```
[RMCitecraft Popup] Send button clicked
[RMCitecraft Popup] Getting active tab...
[RMCitecraft Popup] Active tab: {id: 123, url: "https://www.familysearch.org/ark:/..."}
[RMCitecraft Popup] Tab URL: https://www.familysearch.org/ark:/...
[RMCitecraft Popup] Tab ID: 123
[RMCitecraft Popup] Sending EXTRACT_AND_SEND message to tab 123
[RMCitecraft Popup] Response from content script: {success: true}
[RMCitecraft Popup] Data sent successfully
```

**If You See This Error:**
```
[RMCitecraft Popup] sendMessage error: Error: Could not establish connection. Receiving end does not exist.
```

**This Means:** Content script is NOT loaded on that tab.

**Solutions:**
- Close the FamilySearch tab completely
- Open a NEW FamilySearch tab
- Make sure extension was reloaded (step 1)
- Check content script console (step 2)

### 6. Check Background Service Worker

**To view background script logs:**

```
1. Go to chrome://extensions/
2. Find "RMCitecraft FamilySearch Assistant"
3. Click "service worker" link (under "Inspect views")
4. DevTools will open with background script console
```

**Expected Output:**
```
[RMCitecraft Background] Background script initialized
[RMCitecraft Background] Starting health check...
[RMCitecraft Background] RMCitecraft is running (status: ok)
[RMCitecraft Background] Starting command polling...
```

### 7. Verify FamilySearch URL Pattern

**Content script only loads on pages matching:**
- `https://familysearch.org/*`
- `https://www.familysearch.org/*`

**Check your URL:**
```javascript
// In console, type:
window.location.href
```

Make sure it starts with `https://familysearch.org/` or `https://www.familysearch.org/`

### 8. Test Message Passing Manually

**In FamilySearch Page Console:**

```javascript
// Test if content script can receive messages
chrome.runtime.sendMessage({type: 'EXTRACT_AND_SEND'}, (response) => {
  console.log('Manual test response:', response);
});
```

**Expected:**
```
Manual test response: {success: true}
```

**Or (if not census page):**
```
Manual test response: {success: false, error: "Not a census record page"}
```

**If You Get:**
```
Uncaught Error: Extension context invalidated
```
**Solution:** Extension needs to be reloaded (step 1)

---

## Common Issues & Solutions

### Issue: "Could not establish connection"

**Cause:** Content script not loaded on target tab

**Solutions:**
1. Reload extension: `chrome://extensions/` → click ⟳
2. Close FamilySearch tab completely (not just refresh)
3. Open NEW FamilySearch tab
4. Check console for "[RMCitecraft Content] Content script loaded"

### Issue: No console messages at all

**Cause:** Content script not injecting

**Solutions:**
1. Check extension has no errors: `chrome://extensions/`
2. Verify manifest.json syntax is correct
3. Verify content.js file exists in extension folder
4. Reload extension

### Issue: Content script loads but doesn't detect census page

**Check Console For:**
```
[RMCitecraft Content] Not a census page, skipping auto-send
```

**Cause:** Page doesn't match census detection criteria

**Verify:**
- URL contains `/ark:/` or `/pal:/`
- Page has census data elements
- Try different census record URL

### Issue: Data sends but doesn't appear in RMCitecraft

**Check:**
1. RMCitecraft is running: `http://localhost:8080/api/health`
2. API endpoint is accessible: Open RMCitecraft → Citation Manager tab
3. Check RMCitecraft logs for received data
4. Verify pending citations section shows data

---

## Quick Diagnostic Checklist

Run through this checklist in order:

- [ ] Extension reloaded in `chrome://extensions/`
- [ ] No errors shown on extension card
- [ ] FamilySearch tab closed and reopened
- [ ] Console shows "[RMCitecraft Content] Content script loaded"
- [ ] On a census page with `/ark:/` in URL
- [ ] Console shows "[RMCitecraft Content] Census page detected"
- [ ] Popup opens without errors
- [ ] Popup console accessible via right-click → Inspect
- [ ] Send button click logs appear in popup console
- [ ] Response received from content script
- [ ] RMCitecraft is running on port 8080
- [ ] Green connection indicator in popup

If ALL checkboxes are checked and it still doesn't work, provide:
1. Full console output from FamilySearch page
2. Full console output from popup
3. The exact URL you're testing on
4. Screenshot of extension errors (if any)

---

## Testing URLs

### Working Census Record URLs:

```
# 1950 Census
https://www.familysearch.org/ark:/61903/1:1:6S59-C56T

# 1940 Census
https://www.familysearch.org/ark:/61903/1:1:K9CG-DP4

# 1930 Census
https://www.familysearch.org/ark:/61903/1:1:X7WP-Q7G

# 1920 Census
https://www.familysearch.org/ark:/61903/1:1:M6NQ-Z9F

# 1910 Census
https://www.familysearch.org/ark:/61903/1:1:M2C8-L8Y

# 1900 Census
https://www.familysearch.org/ark:/61903/1:1:MM6X-FGZ
```

---

## Log Output Reference

### Successful Flow:

**Content Script (FamilySearch Page Console):**
```
[RMCitecraft Content] Content script loaded on: https://www.familysearch.org/ark:/...
[RMCitecraft Content] Content script initialized
[RMCitecraft Content] Census page detected
[RMCitecraft Content] Auto-send scheduled for 2 seconds
[RMCitecraft Content] Auto-extracting census data...
[RMCitecraft Content] Extracted census data: {familySearchUrl: "...", censusYear: 1950, ...}
[RMCitecraft Content] Sending data to RMCitecraft...
[RMCitecraft Content] POST http://localhost:8080/api/citation/import
[RMCitecraft Content] ✓ Data sent successfully
[RMCitecraft Content] Response: {status: "success", citation_id: "import_..."}
```

**Popup (Popup DevTools Console):**
```
[RMCitecraft Popup] Initializing popup...
[RMCitecraft Popup] Settings loaded: {rmcitecraftPort: 8080, autoActivateEnabled: true}
[RMCitecraft Popup] Activity log and stats loaded
[RMCitecraft Popup] Event listeners set up
[RMCitecraft Popup] Popup initialized successfully
[RMCitecraft Popup] Send button clicked
[RMCitecraft Popup] Getting active tab...
[RMCitecraft Popup] Active tab: {id: 1234, url: "https://www.familysearch.org/ark:/..."}
[RMCitecraft Popup] Tab URL: https://www.familysearch.org/ark:/...
[RMCitecraft Popup] Tab ID: 1234
[RMCitecraft Popup] Sending EXTRACT_AND_SEND message to tab 1234
[RMCitecraft Popup] Response from content script: {success: true}
[RMCitecraft Popup] Data sent successfully
```

**Background (Service Worker Console):**
```
[RMCitecraft Background] Background script initialized
[RMCitecraft Background] Starting health check...
[RMCitecraft Background] Health check result: {status: "ok"}
[RMCitecraft Background] RMCitecraft is running
[RMCitecraft Background] Starting command polling...
[RMCitecraft Background] Polling for commands every 2000ms
```
