---
priority: archive
topics: [database, census, citation, batch, testing]
---

# Census Batch E2E Test with Image Downloads

## Overview

The `test_census_batch_with_downloads.py` E2E test verifies the complete census batch processing workflow including:
- Census batch creation with real FamilySearch URLs
- Actual image downloads using browser automation
- Dashboard analytics validation
- Image file verification

## Prerequisites

### 1. Chrome with Remote Debugging

The test requires Chrome to be running with remote debugging enabled:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 \
    --user-data-dir="$HOME/Library/Application Support/Google/Chrome-RMCitecraft"
```

**Why separate user data directory?**
- Keeps test Chrome instance isolated from your regular Chrome
- Allows you to be logged into FamilySearch without affecting your main browser session

### 2. FamilySearch Login

Once Chrome is running:
1. Navigate to https://www.familysearch.org
2. Log in with your FamilySearch account
3. Keep Chrome open while running tests

### 3. Test Data

The test uses real FamilySearch URLs defined in `conftest.py`:
- 1900 Census record (Ohio, Noble County)
- 1940 Census record (Texas, Milam County)

You can update these URLs to use your own census records.

## Running the Test

### Run with Chrome Available

```bash
# Terminal 1: Start Chrome with remote debugging
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 \
    --user-data-dir="$HOME/Library/Application Support/Google/Chrome-RMCitecraft"

# Terminal 2: Run the test
uv run pytest tests/e2e/test_census_batch_with_downloads.py -v -s
```

### Test Will Skip If:
- Chrome is not running with remote debugging (port 9222)
- Not logged into FamilySearch
- Test data URLs are inaccessible

## What the Test Does

### Phase 1: Create Census Batch
- Creates a test batch session
- Adds 2 census records with real FamilySearch URLs
- Initializes batch state in database

### Phase 2: Download Census Images
- Uses Playwright automation to navigate to FamilySearch
- Downloads actual census images for each record
- Saves images to temporary directory
- Updates item status (complete/error)

### Phase 3: Validate Downloaded Files
- Verifies files exist
- Checks file size (> 10KB)
- Validates JPG format (magic bytes)

### Phase 4: Validate Dashboard Analytics
- Checks status distribution (complete vs error)
- Validates year distribution (1900, 1940)
- Validates state distribution (Ohio, Texas)

### Phase 5: Validate Session Metadata
- Verifies session status is "completed"
- Checks item counts match
- Validates timestamps

## Expected Output

```
================================================================================
E2E TEST: Census Batch with Real Image Downloads
================================================================================

================================================================================
PHASE 1: Create Census Batch
================================================================================
Created item 1: Ella Ijams (1900 Ohio)
Created item 2: Test Person (1940 Texas)

================================================================================
PHASE 2: Download Census Images
================================================================================

--- Processing Ella Ijams (1900) ---
Downloading from: https://www.familysearch.org/ark:/61903/3:1:S3HT-DC17-RCM
Destination: /tmp/pytest.../1900, Ohio, Noble - Ella Ijams.jpg
✓ Downloaded: 125678 bytes
✓ Valid JPG file

--- Processing Test Person (1940) ---
Downloading from: https://www.familysearch.org/ark:/61903/3:1:3QS7-L9MT-RHHD
Destination: /tmp/pytest.../1940, Texas, Milam - Test Person.jpg
✓ Downloaded: 156234 bytes
✓ Valid JPG file

================================================================================
PHASE 3: Validate Downloaded Files
================================================================================
Total files downloaded: 2
✓ Verified: 1900, Ohio, Noble - Ella Ijams.jpg (125678 bytes)
✓ Verified: 1940, Texas, Milam - Test Person.jpg (156234 bytes)

================================================================================
PHASE 4: Validate Dashboard Analytics
================================================================================
Status distribution: {'complete': 2}
Year distribution: {1900: 1, 1940: 1}
State distribution: {'Ohio': 1, 'Texas': 1}
✓ Completed: 2/2
✓ Errors: 0/2
✓ Year 1900: 1 record(s)
✓ Year 1940: 1 record(s)

================================================================================
PHASE 5: Validate Session Metadata
================================================================================
✓ Session status: completed
✓ Total items: 2
✓ Completed count: 2
✓ Error count: 0

================================================================================
TEST SUMMARY - Census Batch with Downloads
================================================================================
✓ Records processed: 2
✓ Images downloaded: 2
✓ Completed: 2
✓ Errors: 0
✓ Analytics validated
================================================================================
ALL VALIDATIONS PASSED ✓
================================================================================
```

## Troubleshooting

### Test Skipped: Chrome Not Running

```
SKIPPED - Chrome not running with remote debugging
```

**Solution**: Start Chrome with the command shown in Prerequisites section.

### Test Skipped: Not Logged Into FamilySearch

```
SKIPPED - FamilySearch login required
```

**Solution**:
1. Open Chrome (with remote debugging)
2. Navigate to https://www.familysearch.org
3. Log in
4. Re-run test

### Download Failed

If downloads fail but Chrome is connected:
1. Check that FamilySearch URLs in `conftest.py` are accessible
2. Verify you have access to those specific census records
3. Check for network connectivity issues

### Slow Download Times

Census images can be large (100KB - 1MB+). Expect:
- 5-10 seconds per image download
- Total test time: 30-60 seconds for 2 images

## Integration with CI/CD

This test requires interactive Chrome session and cannot run in headless CI/CD environments. Mark as:
- `@pytest.mark.e2e` - End-to-end test
- `@pytest.mark.slow` - Slow-running test
- Skip in CI: Use `@pytest.mark.skipif(os.getenv("CI"), reason="Requires interactive Chrome")`

## Related Tests

- `test_census_analytics.py` - Census analytics without downloads (faster, no Chrome required)
- `test_image_download.py` - Standalone image download tests
- `test_citation_extraction.py` - Citation extraction tests
- `test_complete_workflow.py` - Complete citation workflow tests
