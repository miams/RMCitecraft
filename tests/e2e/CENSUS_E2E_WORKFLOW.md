# Census Image Download E2E Test Workflow

## Issue Summary

The census image download E2E tests encounter a Playwright navigation hang when trying to programmatically navigate to FamilySearch image viewer pages. This appears to be a compatibility issue between Playwright's `launch_persistent_context()` and FamilySearch's authentication flow on macOS.

**When it works**: Chrome is already on the image viewer page (test found in previous session logs)
**When it hangs**: Tests try to navigate from one page to another using `page.goto()` or `page.evaluate()`

## Workaround: Manual Chrome Launch

To run the census download tests successfully:

### Step 1: Manually Launch Chrome

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/chrome-debug-profile" \
  --disable-blink-features=AutomationControlled
```

### Step 2: Manually Navigate to Image Viewer

In the Chrome window that opens:

1. Go to https://www.familysearch.org
2. Sign in if needed (session persists in profile)
3. Navigate to the census image viewer URL:
   `https://www.familysearch.org/ark:/61903/3:1:S3HT-DC17-RCM`
4. Wait for the image viewer to fully load

###Step 3: Run E2E Tests

With Chrome still open and on the image viewer page:

```bash
uv run pytest tests/e2e/test_census_batch_with_downloads.py -v -s
```

The test will:
- Detect the existing Chrome instance (via CDP port 9222)
- Find the image viewer tab already open
- Skip navigation (since already on correct page)
- Proceed with download automation

## Why This Works

From the session logs, we can see that when Chrome is **already on the image viewer page**, the test:

```
Found existing FamilySearch tab: https://www.familysearch.org/ark:/61903/3:1:S3HT-DC17-RCM?lang=en&i=5
Already on image viewer page: https://www.familysearch.org/ark:/61903/3:1:S3HT-DC17-RCM?lang=en&i=5
Waiting for download button...
```

This bypasses the problematic navigation code entirely.

## Failed Approaches

The following navigation strategies all hung indefinitely:

1. ✗ `page.goto()` with various `wait_until` parameters (domcontentloaded, commit, load)
2. ✗ JavaScript navigation via `page.evaluate("window.location.href = '...'")`
3. ✗ Shorter timeouts (still hung before timeout triggered)
4. ✗ CDP connection vs launch_persistent_context (both hung)

The common thread: **any programmatic navigation** after authentication hangs.

## Root Cause Hypothesis

The issue appears related to:
- Playwright's interaction with FamilySearch's authentication state
- macOS-specific Chrome profile handling
- Connection instability between Python/Playwright and Chrome process

Previous test runs showed EPIPE (broken pipe) errors, indicating the Python-Chrome connection was severing during/after navigation attempts.

## Long-term Solutions to Investigate

1. **Selenium WebDriver**: Try alternative browser automation library
2. **Different Playwright strategy**: Use separate browser profile per test
3. **Mock/Stub navigation**: Skip actual browser automation for E2E tests
4. **FamilySearch API**: If available, download images via API instead
5. **Headless Chrome**: Test if headless mode behaves differently
6. **Playwright version**: Try different Playwright versions

## Related Files

- `src/rmcitecraft/services/familysearch_automation.py` - Automation service with navigation code
- `tests/e2e/test_census_batch_with_downloads.py` - E2E test that downloads census images
- `tests/e2e/conftest.py` - Test fixtures for Chrome connection
- `/tmp/census_batch_final.log` - Previous successful test run showing "Already on image viewer page"

## Test Logs Location

Failed test logs:
- `/tmp/census_launch_persistent.log` - First launch attempt (hung at navigation)
- `/tmp/census_test_commit_strategy.log` - "commit" wait strategy (still hung)
- `/tmp/census_test_js_navigation.log` - JavaScript navigation attempt (still hung)
- `/tmp/census_batch_final.log` - Previous successful run (showed EPIPE error eventually)

## Success Criteria

The test passes when:
1. Chrome remains running (no EPIPE/connection loss)
2. Image viewer page loads completely
3. Download button is found and clicked
4. Census image downloads to specified path
5. Downloaded file is valid JPG (magic bytes check passes)
6. Database state correctly tracks download
7. Chrome remains open after test (for subsequent runs)
