---
priority: essential
topics: [troubleshooting, errors, support]
---

# Troubleshooting Guide

**For**: Users experiencing issues with RMCitecraft

## Quick Diagnostics

Run these commands to check your setup:

```bash
# Check Python version (need 3.11+)
python3 --version

# Check UV installation
uv --version

# Verify database connection
uv run python sqlite-extension/python_example.py

# Check if Chrome is running with debugging
lsof -i :9222
```

---

## Installation Issues

### "command not found: uv"

**Problem**: UV package manager not installed or not in PATH.

**Solution**:
```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Restart terminal or reload shell config
source ~/.zshrc  # or ~/.bashrc
```

### "No module named 'rmcitecraft'"

**Problem**: Dependencies not installed.

**Solution**:
```bash
cd /path/to/RMCitecraft
uv sync
```

### "Python version 3.x is not supported"

**Problem**: Python version too old.

**Solution**:
```bash
# Install Python 3.11+ via Homebrew
brew install python@3.11

# Verify
python3.11 --version
```

---

## Database Connection Issues

### "no such collation sequence: RMNOCASE"

**Problem**: ICU extension not loaded. RootsMagic databases require RMNOCASE collation.

**Cause**: Using raw `sqlite3.connect()` instead of RMCitecraft's connection function.

**Solution**: Always use the provided connection function:
```python
from rmcitecraft.database.connection import connect_rmtree
conn = connect_rmtree('path/to/database.rmtree')
```

**Verify ICU extension**:
```bash
uv run python sqlite-extension/python_example.py
```

### "attempt to write a readonly database"

**Problem**: Database opened in read-only mode (the default).

**Solution**: Explicitly enable write mode:
```python
conn = connect_rmtree('path/to/database.rmtree', read_only=False)
# Don't forget to commit!
conn.commit()
```

### "database is locked"

**Problem**: RootsMagic or another process has the database open.

**Solution**:
1. Close RootsMagic completely
2. Check for other processes: `lsof | grep .rmtree`
3. Restart RMCitecraft

### "unable to open database file"

**Problem**: Database path incorrect or file doesn't exist.

**Solution**:
1. Verify the path in your `.env` file:
   ```bash
   cat .env | grep RM_DATABASE_PATH
   ```
2. Check the file exists:
   ```bash
   ls -la "/path/to/your/database.rmtree"
   ```

---

## Chrome/FamilySearch Issues

### "Failed to connect to Chrome"

**Problem**: Chrome not running with remote debugging enabled.

**Solution**:
```bash
# Kill any existing Chrome instances
pkill -f "Google Chrome"

# Start with debugging enabled
~/start-chrome.sh
```

If you don't have the script, create it:
```bash
cat > ~/start-chrome.sh << 'EOF'
#!/bin/bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --no-first-run \
  --user-data-dir=~/.chrome-debug-profile
EOF
chmod +x ~/start-chrome.sh
```

### "Port 9222 already in use"

**Problem**: Another process using the debugging port.

**Solution**:
```bash
# Find what's using the port
lsof -i :9222

# Kill the process (replace PID with actual number)
kill -9 <PID>

# Restart Chrome
~/start-chrome.sh
```

### "FamilySearch login required"

**Problem**: Session expired in Chrome.

**Solution**:
1. Switch to the Chrome window started with `start-chrome.sh`
2. Navigate to [familysearch.org](https://www.familysearch.org)
3. Log in with your credentials
4. Return to RMCitecraft and retry

### "Page load timeout"

**Problem**: FamilySearch page taking too long to load.

**Possible Causes**:
- Slow internet connection
- FamilySearch experiencing high traffic
- Page doesn't exist (bad URL)

**Solution**:
1. Check your internet connection
2. Try opening the URL manually in Chrome
3. Wait and retry later if FamilySearch is slow
4. Verify the FamilySearch URL in the citation is valid

---

## Citation Processing Issues

### "No citations found for year XXXX"

**Problem**: No matching sources in database.

**Causes**:
- Source names don't match expected pattern
- Wrong database selected

**Solution**:
1. Check source naming in RootsMagic:
   - Should be: `Fed Census: 1930, Pennsylvania, Greene [...]`
   - Not: `1930 Census` or other formats
2. Verify database path in `.env`

### "Citation already complete"

**Problem**: Citation has all three forms (footnote, short footnote, bibliography) already populated.

**This is normal** - the citation doesn't need processing. Use the "Incomplete" filter to find citations that need work.

### "Missing ED number"

**Problem**: Enumeration District not extracted from FamilySearch.

**Solution**:
1. Look at the census image header (top right usually)
2. Click FamilySearch's "Information" button for metadata
3. Enter ED manually in the form

### "Short footnote same as footnote"

**Problem**: Citation marked incomplete because forms are identical.

**Cause**: Placeholder citation from FamilySearch hint wasn't processed.

**Solution**: Process the citation through RMCitecraft to generate proper differentiated forms.

---

## Image Issues

### "Image not downloading"

**Problem**: Census image won't download from FamilySearch.

**Solutions**:
1. Verify Chrome is connected (port 9222)
2. Check FamilySearch login status
3. Try manual download: right-click image → "Save Image As..."
4. Drag manually downloaded image into RMCitecraft

### "Image linked to wrong citation"

**Problem**: Image associated with incorrect person.

**Solution**:
1. In RootsMagic, unlink the image from the citation
2. Re-process the citation in RMCitecraft
3. Or manually link the correct image in RootsMagic

### "Media folder not found"

**Problem**: Configured media directory doesn't exist.

**Solution**:
1. Check `.env` setting:
   ```bash
   cat .env | grep RM_MEDIA_ROOT_DIRECTORY
   ```
2. Create directory if needed:
   ```bash
   mkdir -p ~/Genealogy/RootsMagic/Files
   ```

---

## Performance Issues

### "Processing very slow"

**Possible Causes**:
- Large database
- Slow network
- Many background applications

**Solutions**:
1. Close unnecessary applications
2. Process smaller batches (20-30 citations)
3. Check network speed

### "Memory error" or "Out of memory"

**Problem**: System running low on RAM.

**Solutions**:
1. Close other applications
2. Restart RMCitecraft
3. Process smaller batches

---

## Recovery

### "Batch processing interrupted"

**Problem**: RMCitecraft crashed or was closed during batch processing.

**Solution**: State is saved automatically:
1. Restart RMCitecraft
2. Go to Batch Processing tab
3. Click "Resume" to continue

State is stored in: `~/.rmcitecraft/batch_state.db`

### "Database corrupted"

**Problem**: RootsMagic database won't open or shows errors.

**Solution**:
1. **This is why you work on a copy!**
2. Delete the corrupted working copy
3. Make a fresh copy from your production database
4. Start over

### "Lost changes"

**Problem**: Changes not appearing in RootsMagic.

**Possible Causes**:
- Forgot to click "Save"
- Database opened in read-only mode
- Changes made to wrong database file

**Solution**:
1. Check the database path you're using
2. Re-process affected citations
3. Verify changes with SQLite browser

---

## Getting More Help

### Check Logs

```bash
# View recent log entries
tail -100 rmcitecraft.log

# Search for errors
grep -i error rmcitecraft.log
```

### Debug Mode

Enable verbose logging in `.env`:
```bash
LOG_LEVEL=DEBUG
```

### Report Issues

If you can't resolve the issue:

1. **Gather information**:
   - Python version: `python3 --version`
   - macOS version: `sw_vers`
   - Error message (exact text)
   - Steps to reproduce

2. **Check existing issues**: [GitHub Issues](https://github.com/miams/RMCitecraft/issues)

3. **Create new issue** with gathered information

---

## Common Error Messages Reference

| Error | Likely Cause | Quick Fix |
|-------|--------------|-----------|
| `RMNOCASE` | ICU not loaded | Use `connect_rmtree()` |
| `readonly database` | Write mode off | Add `read_only=False` |
| `database is locked` | RM still open | Close RootsMagic |
| `connection refused` | Chrome not running | Run `start-chrome.sh` |
| `login required` | FS session expired | Log into FamilySearch |
| `timeout` | Network/page issue | Retry or check connection |

---

**Document Version**: 1.0
**Last Updated**: 2025-12-30
