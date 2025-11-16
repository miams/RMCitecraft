# End-to-End (E2E) Tests for FamilySearch Automation

## Overview

These tests verify the complete Playwright-based automation workflow for FamilySearch census citation extraction and image downloads. They run against **real FamilySearch pages** with **real browser automation**.

## Test Coverage

### 1. Chrome Connection Tests (`test_chrome_connection.py`)
- ✅ Connect to Chrome via CDP (Chrome DevTools Protocol)
- ✅ Verify browser contexts and pages
- ✅ Create and manage multiple tabs
- ✅ Disconnect and reconnect
- ✅ Verify Chrome version and debugging status

### 2. Citation Extraction Tests (`test_citation_extraction.py`)
- ✅ Extract citation data from 1900 census records
- ✅ Extract citation data from 1940 census records
- ✅ Find image viewer URLs
- ✅ Handle page loading and timing
- ✅ Process multiple records sequentially
- ✅ Handle invalid URLs gracefully
- ✅ Verify FamilySearch entry text extraction

### 3. Image Download Tests (`test_image_download.py`)
- ✅ Download census images from 1900 records
- ✅ Download census images from 1940 records
- ✅ Verify JPG format selection (not PDF)
- ✅ Test keyboard automation (Tab, Down, Enter)
- ✅ Download multiple images sequentially
- ✅ Handle file overwrites
- ✅ Verify download completion and file validity
- ✅ Test performance and timing

### 4. Complete Workflow Tests (`test_complete_workflow.py`)
- ✅ Full workflow: extract + download (1900 census)
- ✅ Full workflow: extract + download (1940 census)
- ✅ Batch processing multiple records
- ✅ Verify all required fields extracted
- ✅ Image quality verification
- ✅ Error handling and recovery
- ✅ Real-world user workflow simulation

## Prerequisites

### 1. Chrome with Remote Debugging

Chrome must be running with remote debugging enabled on port 9222:

```bash
# Close all Chrome windows first
pkill -9 "Google Chrome"

# Launch Chrome with debugging
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 \
    --user-data-dir="$HOME/Library/Application Support/Google/Chrome"
```

**Keep this Terminal window open** - Chrome needs the process running.

### 2. FamilySearch Authentication

1. In the Chrome window that opened, navigate to `https://familysearch.org`
2. **Log in manually** with your FamilySearch credentials
3. Leave Chrome window open during tests

### 3. Test URLs Configuration

Edit `conftest.py` and update `TEST_URLS` dictionary with real census record URLs you have access to:

```python
TEST_URLS = {
    "1900_census_record": "https://www.familysearch.org/ark:/61903/1:1:YOUR-RECORD",
    "1900_census_image_viewer": "https://www.familysearch.org/ark:/61903/3:1:YOUR-IMAGE",
    "1940_census_record": "https://www.familysearch.org/ark:/61903/1:1:YOUR-RECORD",
    "1940_census_image_viewer": "https://www.familysearch.org/ark:/61903/3:1:YOUR-IMAGE",
}
```

**How to find URLs:**
- Browse to a census record on FamilySearch
- Copy the URL from address bar (record page)
- Click on the census image, copy that URL (image viewer page)

## Running Tests

### Install Dependencies

```bash
# Install test dependencies
uv sync --dev
```

### Run All E2E Tests

```bash
# Run all E2E tests
uv run pytest tests/e2e/ -v

# Run with detailed output
uv run pytest tests/e2e/ -vv -s

# Run only E2E tests marked with @pytest.mark.e2e
uv run pytest -m e2e -v
```

### Run Specific Test Files

```bash
# Run only Chrome connection tests
uv run pytest tests/e2e/test_chrome_connection.py -v

# Run only citation extraction tests
uv run pytest tests/e2e/test_citation_extraction.py -v

# Run only image download tests
uv run pytest tests/e2e/test_image_download.py -v

# Run only complete workflow tests
uv run pytest tests/e2e/test_complete_workflow.py -v
```

### Run Specific Tests

```bash
# Run a specific test by name
uv run pytest tests/e2e/test_citation_extraction.py::test_extract_citation_from_1900_census -v

# Run tests matching pattern
uv run pytest tests/e2e/ -k "1900_census" -v

# Run tests matching multiple patterns
uv run pytest tests/e2e/ -k "download or extract" -v
```

### Run with Coverage

```bash
# Run with coverage report
uv run pytest tests/e2e/ --cov=src/rmcitecraft/services/familysearch_automation --cov-report=html

# View coverage report
open htmlcov/index.html
```

## Test Output

### Successful Test Run

```
tests/e2e/test_chrome_connection.py::test_chrome_connection_succeeds PASSED
tests/e2e/test_citation_extraction.py::test_extract_citation_from_1900_census PASSED
tests/e2e/test_image_download.py::test_download_1900_census_image PASSED
tests/e2e/test_complete_workflow.py::test_complete_workflow_1900_census PASSED

=== 40 passed in 120.45s ===
```

### Expected Timing

- Chrome connection tests: ~5 seconds
- Citation extraction tests: ~30 seconds
- Image download tests: ~60 seconds (actual downloads)
- Complete workflow tests: ~90 seconds

**Total runtime:** ~3-4 minutes for all E2E tests

## Troubleshooting

### "Chrome not running with remote debugging"

**Problem:** Tests are skipped with message about Chrome not available.

**Solution:**
```bash
# Verify Chrome is running
lsof -i :9222

# Should show Chrome process on port 9222
# If not, launch Chrome with debugging command above
```

### "Connection refused" or "Could not connect"

**Problem:** Tests fail with connection errors.

**Solution:**
1. Close all Chrome windows
2. Restart Chrome with debugging command
3. Wait 5 seconds for Chrome to fully start
4. Run tests again

### "Authentication required" or "401 Unauthorized"

**Problem:** Tests fail because not logged into FamilySearch.

**Solution:**
1. Open Chrome (already running with debugging)
2. Navigate to `https://familysearch.org`
3. Log in manually
4. Leave window open
5. Run tests again

### "Element not found" or "Timeout"

**Problem:** Download button not found, page didn't load.

**Solution:**
1. Verify your `TEST_URLS` are correct and accessible
2. Manually navigate to URL in Chrome to verify page loads
3. Check if FamilySearch changed page structure
4. Increase timeout in test if network is slow

### Tests are slow

**Problem:** Tests take longer than expected.

**Reasons:**
- Network latency to FamilySearch
- Large image downloads (5-10MB per image)
- Chrome page rendering time
- This is normal for E2E tests

**Improvement:**
```bash
# Run specific fast tests
uv run pytest tests/e2e/test_chrome_connection.py -v  # ~5s

# Skip slow download tests
uv run pytest tests/e2e/ -m "not slow" -v
```

### Downloaded images not cleaned up

**Problem:** Temp directories have leftover test images.

**Solution:**
Tests use `cleanup_downloads` fixture which auto-deletes files. If tests crash, manually clean:

```bash
# Check temp directory
ls -lh /tmp/pytest-of-$USER/

# Clean old pytest temp directories
rm -rf /tmp/pytest-of-$USER/pytest-*
```

## Test Data

### What Gets Downloaded

During test runs, real census images are downloaded to temporary directories:
- File format: JPG (not PDF)
- File size: 100KB - 5MB
- Automatically cleaned up after each test

### Test URLs

Update `conftest.py` with your own census records. Suggested test records:
- **1900 census:** Any household member
- **1940 census:** Any household member
- **Both with images:** Required for download tests

### Privacy

Tests use **your FamilySearch account** and access **records you have permission to view**. No data is shared or logged externally.

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e:
    runs-on: macos-latest

    steps:
      - uses: actions/checkout@v3

      - name: Install dependencies
        run: uv sync --dev

      - name: Launch Chrome with debugging
        run: |
          /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
            --remote-debugging-port=9222 \
            --user-data-dir=$HOME/chrome-profile \
            --headless &
          sleep 5

      - name: Run E2E tests
        run: uv run pytest tests/e2e/ -v
        env:
          FAMILYSEARCH_USER: ${{ secrets.FAMILYSEARCH_USER }}
          FAMILYSEARCH_PASS: ${{ secrets.FAMILYSEARCH_PASS }}
```

**Note:** CI/CD requires automated login (not implemented yet). For now, run tests locally.

## Test Development

### Adding New Tests

1. Create new test file: `tests/e2e/test_my_feature.py`
2. Import fixtures from `conftest.py`
3. Mark tests with `@pytest.mark.e2e` and `@pytest.mark.asyncio`
4. Use `automation_service` fixture for browser automation
5. Use `cleanup_downloads` fixture for file operations

Example:

```python
import pytest

pytestmark = pytest.mark.e2e

@pytest.mark.asyncio
async def test_my_feature(automation_service, test_urls, cleanup_downloads):
    # Your test code here
    citation_data = await automation_service.extract_citation_data(
        test_urls["1900_census_record"]
    )
    assert citation_data is not None
```

### Test Best Practices

1. **Use real data:** Don't mock FamilySearch - test against real site
2. **Clean up:** Use `cleanup_downloads` fixture for temp files
3. **Be specific:** Assert exact expected behavior
4. **Log output:** Use `logger.info()` to document test progress
5. **Handle errors:** Test should pass OR skip (not crash)

### Debugging Tests

```bash
# Run with pytest debugger
uv run pytest tests/e2e/test_citation_extraction.py::test_extract_citation_from_1900_census --pdb

# Run with verbose logging
uv run pytest tests/e2e/ -vv -s --log-cli-level=DEBUG

# Capture screenshots on failure (requires pytest-playwright)
uv run pytest tests/e2e/ --screenshot=on --video=retain-on-failure
```

## Performance Benchmarks

Target performance for complete workflow:
- **Citation extraction:** < 10 seconds
- **Image download:** < 20 seconds
- **Complete workflow:** < 30 seconds

Tests will fail if significantly slower (timeout).

## Dependencies

- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `pytest-playwright` - Playwright integration
- `playwright` - Browser automation
- `loguru` - Logging

## Known Issues

1. **FamilySearch rate limiting:** Too many rapid requests may trigger rate limit. Add delays between tests if needed.

2. **Page structure changes:** If FamilySearch updates their page structure, tests may fail. Update selectors in `familysearch_automation.py`.

3. **Network timeouts:** Slow networks may cause timeouts. Increase timeout values in test if needed.

4. **Chrome versions:** Tests require Chrome 90+ with CDP support. Update Chrome if tests fail with version errors.

## Support

- **Tests failing?** Check troubleshooting section above
- **Need help?** Review test logs with `-vv -s` flags
- **Found a bug?** Check if FamilySearch page structure changed

---

**Last Updated:** 2025-11-05
**Test Count:** 40+ E2E tests
**Coverage:** Chrome connection, citation extraction, image download, complete workflow
