---
priority: essential
topics: [census, citation, batch, testing, ui]
---

# E2E Testing Quick Start Guide

## What We Built

Comprehensive automated end-to-end tests for the Playwright-based FamilySearch automation. Tests verify real browser interactions, citation extraction, and image downloads.

**Test Coverage:**
- ✅ 40+ automated tests
- ✅ Chrome browser connection
- ✅ Citation data extraction
- ✅ Census image downloads
- ✅ Complete workflows
- ✅ Error handling
- ✅ Performance benchmarks

## Quick Start (3 Steps)

### Step 1: Launch Chrome with Debugging

```bash
# Close all Chrome windows first
pkill -9 "Google Chrome"

# Launch Chrome with remote debugging
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 \
    --user-data-dir="$HOME/Library/Application Support/Google/Chrome"
```

**Keep this Terminal window open!**

### Step 2: Log into FamilySearch

1. In the Chrome window, go to `https://familysearch.org`
2. Log in with your credentials
3. Leave Chrome open

### Step 3: Run Tests

```bash
# Easy way - use the helper script
./scripts/run_e2e_tests.sh

# Or run directly with pytest
uv run pytest tests/e2e/ -v
```

## Test Suites

Run specific test suites:

```bash
# Connection tests only (~5 seconds)
./scripts/run_e2e_tests.sh --connection

# Citation extraction tests (~30 seconds)
./scripts/run_e2e_tests.sh --extraction

# Image download tests (~60 seconds, downloads real images)
./scripts/run_e2e_tests.sh --download

# Complete workflow tests (~90 seconds)
./scripts/run_e2e_tests.sh --workflow

# All tests (~3-4 minutes)
./scripts/run_e2e_tests.sh --all
```

## Before First Run

### Update Test URLs

Edit `tests/e2e/conftest.py` with your own census record URLs:

```python
TEST_URLS = {
    "1900_census_record": "https://www.familysearch.org/ark:/61903/1:1:YOUR-RECORD",
    "1900_census_image_viewer": "https://www.familysearch.org/ark:/61903/3:1:YOUR-IMAGE",
    "1940_census_record": "https://www.familysearch.org/ark:/61903/1:1:YOUR-RECORD",
    "1940_census_image_viewer": "https://www.familysearch.org/ark:/61903/3:1:YOUR-IMAGE",
}
```

**How to get URLs:**
1. Browse to any census record on FamilySearch
2. Copy URL from address bar → use as `census_record`
3. Click on census image
4. Copy that URL → use as `census_image_viewer`

You need 2 pairs of URLs (1900 and 1940) for full test coverage.

## What Tests Do

### Chrome Connection Tests (Fast)
```bash
./scripts/run_e2e_tests.sh --connection
```
- Connects to Chrome via CDP
- Verifies browser contexts
- Tests tab management
- **No FamilySearch access needed** ✓

### Citation Extraction Tests
```bash
./scripts/run_e2e_tests.sh --extraction
```
- Navigates to FamilySearch census pages
- Extracts person name, date, place
- Finds image viewer URLs
- Tests multiple records
- **Requires FamilySearch login** ⚠️

### Image Download Tests
```bash
./scripts/run_e2e_tests.sh --download
```
- Downloads real census images
- Verifies JPG format (not PDF)
- Tests keyboard automation
- Validates file size and quality
- **Downloads ~10-50MB during test** 📥
- **Requires FamilySearch login** ⚠️

### Complete Workflow Tests
```bash
./scripts/run_e2e_tests.sh --workflow
```
- Full end-to-end simulation
- Extract → Download → Verify
- Batch processing multiple records
- Performance benchmarks
- **Most comprehensive** 🎯
- **Requires FamilySearch login** ⚠️

## Test Output Example

```
tests/e2e/test_chrome_connection.py::test_chrome_connection_succeeds PASSED
tests/e2e/test_chrome_connection.py::test_chrome_has_pages PASSED
tests/e2e/test_citation_extraction.py::test_extract_citation_from_1900_census PASSED
tests/e2e/test_image_download.py::test_download_1900_census_image PASSED
tests/e2e/test_complete_workflow.py::test_complete_workflow_1900_census PASSED

=== 40 passed in 185.42s ===

✓ All tests passed!
```

## Troubleshooting

### Tests Skip with "Chrome not running"

**Problem:**
```
SKIPPED [1] conftest.py:95: Chrome not running with remote debugging
```

**Solution:**
```bash
# Check if Chrome is running with debugging
lsof -i :9222

# Should show Chrome process
# If not, launch Chrome with command from Step 1
```

### Tests Fail with "Authentication required"

**Problem:** Tests fail accessing FamilySearch pages

**Solution:**
1. Open your Chrome (already running with debugging)
2. Navigate to `https://familysearch.org`
3. Log in manually
4. Leave window open
5. Run tests again

### Tests Fail with "Element not found"

**Problem:** Download button or page elements not found

**Solution:**
1. Verify your `TEST_URLS` in `conftest.py` are correct
2. Manually open one URL in Chrome to verify it works
3. Check if FamilySearch changed their page structure
4. See detailed README: `tests/e2e/README.md`

## Advanced Usage

### Run with Coverage Report

```bash
./scripts/run_e2e_tests.sh --coverage

# View coverage
open htmlcov/index.html
```

### Run Specific Test

```bash
uv run pytest tests/e2e/test_citation_extraction.py::test_extract_citation_from_1900_census -vv
```

### Run with Extra Logging

```bash
uv run pytest tests/e2e/ -vv -s --log-cli-level=DEBUG
```

### Run Tests Matching Pattern

```bash
# Run all tests with "1900" in name
uv run pytest tests/e2e/ -k "1900" -v

# Run all download tests
uv run pytest tests/e2e/ -k "download" -v
```

## Files Created

```
tests/e2e/
├── __init__.py                    # Package marker
├── conftest.py                    # Shared fixtures and config
├── test_chrome_connection.py      # 10+ connection tests
├── test_citation_extraction.py    # 12+ extraction tests
├── test_image_download.py         # 15+ download tests
├── test_complete_workflow.py      # 13+ workflow tests
└── README.md                      # Detailed documentation

scripts/
└── run_e2e_tests.sh              # Test runner helper script

pytest.ini                         # Pytest configuration
docs/
└── E2E-TESTING-QUICKSTART.md     # This file
```

## Performance

**Expected timing:**
- Connection tests: ~5 seconds ⚡
- Extraction tests: ~30 seconds
- Download tests: ~60 seconds 📥
- Workflow tests: ~90 seconds
- **Full suite: ~3-4 minutes** ⏱️

## Best Practices

1. **Update TEST_URLS** with records you have access to
2. **Keep Chrome open** during test runs
3. **Stay logged in** to FamilySearch
4. **Run connection tests first** to verify setup
5. **Run full suite** before committing changes

## CI/CD Note

These tests currently require manual authentication. For CI/CD:
- Tests will skip if Chrome not available
- Consider using test FamilySearch account
- Or mock FamilySearch responses for CI

## Next Steps

After tests pass:
1. ✅ Playwright automation is working
2. ✅ Citation extraction is reliable
3. ✅ Image downloads complete successfully
4. 🚀 Ready to integrate with RMCitecraft UI
5. 🚀 Ready for real-world usage

## Support

- **Full documentation:** `tests/e2e/README.md`
- **Test code:** `tests/e2e/*.py`
- **Helper script:** `scripts/run_e2e_tests.sh`

---

**Questions?** Read the detailed README: `tests/e2e/README.md`

**Ready to test?** Run: `./scripts/run_e2e_tests.sh`
