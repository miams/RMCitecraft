# Frontend Design & Testing Reference

Detailed patterns and techniques for the `frontend-design` skill.

**See also**: `SKILL.md` for core principles and workflow.

---

## Table of Contents

- [Playwright Testing Patterns](#playwright-testing-patterns)
- [Advanced Browser Automation](#advanced-browser-automation)
- [Debugging Techniques](#debugging-techniques)
- [Performance Profiling](#performance-profiling)
- [Visual Regression Testing](#visual-regression-testing)

---

## Playwright Testing Patterns

### Comprehensive Diagnostic Capture

```python
class ComprehensiveDiagnostics:
    """Capture all browser events for analysis."""

    def __init__(self, page):
        self.console = []
        self.errors = []
        self.requests = []
        self.responses = []

        # Capture browser events
        page.on('console', lambda m: self.console.append(m))
        page.on('pageerror', lambda e: self.errors.append(e))
        page.on('request', lambda r: self.requests.append(r))
        page.on('response', lambda r: self.responses.append(r))

    async def export_report(self, page):
        """Generate comprehensive diagnostic report."""
        return {
            'console_logs': [f"{m.type}: {m.text}" for m in self.console],
            'errors': [str(e) for e in self.errors],
            'network_failed': [r.url for r in self.requests if r.failure],
            'screenshot': await page.screenshot(),
            'html_snapshot': await page.content()
        }
```

### Bisecting Component Failures

```python
async def bisect_failure():
    """Binary search to find failing component."""
    components = ['header', 'nav', 'content', 'charts', 'table', 'footer']

    for comp in components:
        # Enable only this component
        enable_component(comp)

        # Test
        result = await test_page()

        if not result.passed:
            print(f'❌ {comp} caused failure')
            await page.screenshot(path=f'failure_{comp}.png')
            return comp
        else:
            print(f'✅ {comp} works')

    return None  # All components work
```

### Wait Strategies

```python
# Pattern 1: Wait for element to appear
await page.wait_for_selector('.dashboard-loaded', timeout=10000)

# Pattern 2: Wait for function to return true
await page.wait_for_function('() => window.appReady === true', timeout=5000)

# Pattern 3: Wait for network request
await page.wait_for_response('**/api/data', timeout=8000)

# Pattern 4: Wait with retry logic
async def wait_with_retry(selector, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            await page.wait_for_selector(selector, timeout=5000)
            return True
        except TimeoutError:
            if attempt == max_attempts - 1:
                await page.screenshot(path=f'timeout_{selector}.png')
                raise
            await page.reload()
```

### Network State Validation

```python
async def validate_network_state():
    """Ensure all critical requests succeeded."""
    responses = []

    page.on('response', lambda r: responses.append(r))

    # Perform actions
    await page.click('button')

    # Validate responses
    for response in responses:
        if response.status >= 400:
            print(f'❌ Failed: {response.url} ({response.status})')
        else:
            print(f'✅ Success: {response.url}')
```

---

## Advanced Browser Automation

### Video Recording

```python
async def test_with_video():
    """Record test session as video."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # Enable video recording
        context = await browser.new_context(
            record_video_dir='./test_videos',
            record_video_size={'width': 1920, 'height': 1080}
        )

        page = await context.new_page()

        # Perform test actions
        await page.goto('http://localhost:8080')
        await page.click('button')

        # Video saved automatically on context close
        await context.close()
        await browser.close()
```

### Network Interception (Mocking)

```python
async def mock_api_responses():
    """Mock API responses for testing."""

    async def handle_route(route):
        url = route.request.url

        if 'api/batch_items' in url:
            # Mock successful response
            await route.fulfill(json={
                'items': [
                    {'id': 1, 'status': 'completed'},
                    {'id': 2, 'status': 'pending'}
                ]
            })
        elif 'api/error' in url:
            # Mock error response
            await route.fulfill(status=500, json={'error': 'Server error'})
        else:
            # Continue with real request
            await route.continue_()

    await page.route('**/*', handle_route)
```

### Chrome DevTools Protocol (CDP)

```python
async def use_cdp_for_profiling():
    """Use CDP for advanced profiling."""

    # Get CDP session
    client = await page.context.new_cdp_session(page)

    # Enable JavaScript profiling
    await client.send('Profiler.enable')
    await client.send('Profiler.start')

    # Perform actions
    await page.click('button.expensive-operation')

    # Stop profiling and get results
    profile = await client.send('Profiler.stop')

    # Analyze profile
    print(f'Profile nodes: {len(profile["profile"]["nodes"])}')

    # Memory profiling
    await client.send('HeapProfiler.enable')
    await client.send('HeapProfiler.collectGarbage')
    heap_snapshot = await client.send('HeapProfiler.takeHeapSnapshot')
```

### Parallel Browser Contexts

```python
async def test_multiple_states():
    """Test different user states simultaneously."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # Context 1: Logged in user
        context1 = await browser.new_context(
            storage_state='logged_in_user.json'
        )
        page1 = await context1.new_page()

        # Context 2: Guest user
        context2 = await browser.new_context()
        page2 = await context2.new_page()

        # Test both simultaneously
        results = await asyncio.gather(
            test_logged_in_view(page1),
            test_guest_view(page2)
        )

        await browser.close()
```

---

## Debugging Techniques

### Silent Failure Detection

**Problem**: Component renders on server but not in browser, no errors.

**Diagnosis Approach**:

```python
async def diagnose_silent_failure():
    """Systematically identify silent failure cause."""

    # Step 1: Verify server rendering
    print("Checking server logs...")
    # Look for "rendered successfully" messages

    # Step 2: Test minimal version
    render_minimal()
    await page.goto('http://localhost:8080')
    minimal_works = await check_rendering()
    print(f"Minimal rendering: {minimal_works}")

    if not minimal_works:
        print("Issue in view switching mechanism")
        return "view_switching"

    # Step 3: Add components incrementally
    for component in ['header', 'content', 'charts', 'table']:
        add_component(component)
        await page.reload()

        if not await check_rendering():
            print(f"Issue in {component}")

            # Step 4: Check common causes
            await diagnose_component(component)
            return component

async def diagnose_component(component_name):
    """Diagnose specific component issues."""

    # Check 1: Lambda functions in config
    print(f"Checking {component_name} for lambda functions...")
    # Search for: formatter: lambda, on_click: lambda in config dicts

    # Check 2: Public callbacks
    print(f"Checking {component_name} for public callbacks...")
    # Search for: self.on_*, self.callback without _ prefix

    # Check 3: Circular references
    print(f"Checking {component_name} for circular refs...")

    # Check 4: Browser console
    console_logs = await page.evaluate('() => console.logs')
    print(f"Browser console: {console_logs}")
```

### JSON Serialization Issues

**Common Patterns to Avoid**:

```python
# ❌ WRONG: Lambda in configuration dict
chart_options = {
    'tooltip': {
        'formatter': lambda params: format_tooltip(params)
    }
}

# ✅ CORRECT: Pre-format data
tooltip_data = [format_tooltip(item) for item in items]
chart_options = {
    'tooltip': {'trigger': 'item'}
}

# ❌ WRONG: Function reference in config
config = {
    'handler': self.handle_click
}

# ✅ CORRECT: Use NiceGUI event binding
ui.button('Click', on_click=self._handle_click)

# ❌ WRONG: Public callback attribute
self.on_status_click = on_status_click

# ✅ CORRECT: Private callback attribute
self._on_status_click = on_status_click
```

### Screenshot-Based Debugging

```python
async def debug_with_screenshots():
    """Use screenshots to diagnose visual issues."""

    # Take screenshot at each step
    steps = ['load', 'login', 'navigate', 'interact']

    for step in steps:
        # Perform action
        await perform_step(step)

        # Capture state
        await page.screenshot(path=f'debug_{step}.png')

        # Check if expected element visible
        expected_visible = await page.is_visible('.expected-element')
        print(f'{step}: Expected element visible = {expected_visible}')

        if not expected_visible:
            print(f'Issue detected at step: {step}')
            # Capture additional diagnostics
            html = await page.content()
            with open(f'debug_{step}.html', 'w') as f:
                f.write(html)
            break
```

---

## Performance Profiling

### Interaction Performance

```python
async def profile_interaction():
    """Measure performance of user interactions."""

    # Start performance measurement
    await page.evaluate('() => performance.mark("interaction-start")')

    # Perform interaction
    await page.click('button.expensive-operation')

    # Wait for completion
    await page.wait_for_selector('.result-loaded')

    # Measure performance
    metrics = await page.evaluate('''() => {
        performance.mark("interaction-end");
        performance.measure("interaction", "interaction-start", "interaction-end");

        const measure = performance.getEntriesByName("interaction")[0];
        const memory = performance.memory || {};

        return {
            duration: measure.duration,
            usedJSHeapSize: memory.usedJSHeapSize || 0,
            totalJSHeapSize: memory.totalJSHeapSize || 0,
            jsHeapSizeLimit: memory.jsHeapSizeLimit || 0
        };
    }''')

    print(f'Interaction duration: {metrics["duration"]:.2f}ms')
    print(f'Memory used: {metrics["usedJSHeapSize"] / 1024 / 1024:.2f}MB')
```

### Page Load Performance

```python
async def measure_page_load():
    """Measure complete page load performance."""

    # Navigate with performance data
    await page.goto('http://localhost:8080')

    # Get performance timing
    perf = await page.evaluate('''() => {
        const timing = performance.timing;
        const navigation = performance.getEntriesByType('navigation')[0];

        return {
            // Traditional timing
            dns: timing.domainLookupEnd - timing.domainLookupStart,
            tcp: timing.connectEnd - timing.connectStart,
            request: timing.responseStart - timing.requestStart,
            response: timing.responseEnd - timing.responseStart,
            dom: timing.domComplete - timing.domLoading,
            load: timing.loadEventEnd - timing.loadEventStart,

            // Navigation timing
            domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
            total: navigation.loadEventEnd - navigation.fetchStart
        };
    }''')

    print(f'DNS: {perf["dns"]}ms')
    print(f'TCP: {perf["tcp"]}ms')
    print(f'Request: {perf["request"]}ms')
    print(f'Response: {perf["response"]}ms')
    print(f'DOM: {perf["dom"]}ms')
    print(f'Total: {perf["total"]}ms')
```

### Animation Performance

```python
async def profile_animation():
    """Measure animation frame rate."""

    # Start FPS counter
    await page.evaluate('''() => {
        window.frameCount = 0;
        window.lastTime = performance.now();

        function countFrames() {
            window.frameCount++;
            requestAnimationFrame(countFrames);
        }
        requestAnimationFrame(countFrames);
    }''')

    # Trigger animation
    await page.click('button.animate')
    await asyncio.sleep(2)  # Let animation run

    # Calculate FPS
    fps = await page.evaluate('''() => {
        const now = performance.now();
        const elapsed = (now - window.lastTime) / 1000;
        return Math.round(window.frameCount / elapsed);
    }''')

    print(f'Animation FPS: {fps}')

    if fps < 30:
        print('⚠️  Animation is janky (< 30 FPS)')
    elif fps < 60:
        print('⚠️  Animation could be smoother (< 60 FPS)')
    else:
        print('✅ Smooth animation (≥ 60 FPS)')
```

---

## Visual Regression Testing

### Screenshot Comparison

```python
from PIL import Image, ImageChops

async def test_visual_regression():
    """Detect visual changes between versions."""

    # Take current screenshot
    await page.screenshot(path='current.png')

    # Compare with baseline
    baseline = Image.open('baseline.png')
    current = Image.open('current.png')

    # Calculate difference
    diff = ImageChops.difference(baseline, current)

    # Check if there are differences
    if diff.getbbox():
        print('❌ Visual regression detected!')

        # Save diff image
        diff.save('visual_diff.png')

        # Calculate percentage difference
        diff_pixels = sum(1 for pixel in diff.getdata() if pixel != (0, 0, 0, 0))
        total_pixels = baseline.size[0] * baseline.size[1]
        diff_percent = (diff_pixels / total_pixels) * 100

        print(f'Difference: {diff_percent:.2f}% of pixels changed')

        return False
    else:
        print('✅ No visual regression')
        return True
```

### Element Screenshot Comparison

```python
async def compare_component_rendering():
    """Compare specific component rendering."""

    # Screenshot specific element
    element = await page.query_selector('.dashboard-card')
    await element.screenshot(path='card_current.png')

    # Compare with baseline
    baseline = Image.open('card_baseline.png')
    current = Image.open('card_current.png')

    # Check dimensions
    if baseline.size != current.size:
        print(f'❌ Size mismatch: {baseline.size} vs {current.size}')
        return False

    # Check visual difference
    diff = ImageChops.difference(baseline, current)
    if diff.getbbox():
        print('❌ Visual difference detected')
        diff.save('card_diff.png')
        return False

    print('✅ Component renders identically')
    return True
```

### Multi-Viewport Testing

```python
async def test_responsive_design():
    """Test design across multiple viewports."""

    viewports = [
        {'name': 'mobile', 'width': 375, 'height': 667},
        {'name': 'tablet', 'width': 768, 'height': 1024},
        {'name': 'desktop', 'width': 1920, 'height': 1080},
    ]

    for viewport in viewports:
        # Set viewport
        await page.set_viewport_size({
            'width': viewport['width'],
            'height': viewport['height']
        })

        # Take screenshot
        await page.screenshot(path=f'responsive_{viewport["name"]}.png')

        # Validate layout
        is_valid = await validate_layout(viewport['name'])
        print(f'{viewport["name"]}: {is_valid}')
```

---

## Best Practices Summary

### When to Use Each Technique

| Technique | Use Case |
|-----------|----------|
| **Incremental Testing** | Finding which component causes failure |
| **Diagnostic Capture** | Understanding all browser events |
| **Wait Strategies** | Ensuring elements load before interaction |
| **Network Mocking** | Testing without backend or specific scenarios |
| **Video Recording** | Debugging intermittent failures |
| **CDP Profiling** | Deep performance analysis |
| **Visual Regression** | Preventing unintended design changes |
| **Performance Profiling** | Optimizing slow interactions |

### Testing Checklist

- [ ] Test components incrementally (minimal → full)
- [ ] Capture all diagnostics (console, errors, network)
- [ ] Use condition-based waits (not fixed timeouts)
- [ ] Check for JSON serialization issues (lambdas in configs)
- [ ] Screenshot on failure for evidence
- [ ] Profile performance for critical paths
- [ ] Test across multiple viewports
- [ ] Verify accessibility with axe-core
- [ ] Run visual regression tests before deployment

### Common Pitfalls

**1. Lambda Functions in Configuration**
```python
# ❌ Silent failure
config = {'formatter': lambda x: x}

# ✅ Pre-format data
data = [format(x) for x in items]
```

**2. Fixed Timeouts**
```python
# ❌ Brittle, slow
await page.wait_for_timeout(5000)

# ✅ Wait for condition
await page.wait_for_selector('.loaded', timeout=10000)
```

**3. Public Callback Attributes**
```python
# ❌ Gets serialized
self.on_click = callback

# ✅ Private, not serialized
self._on_click = callback
```

---

## Additional Resources

- **Playwright Docs**: https://playwright.dev/python/
- **Chrome DevTools Protocol**: https://chromedevtools.github.io/devtools-protocol/
- **Web Performance API**: https://developer.mozilla.org/en-US/docs/Web/API/Performance
- **Accessibility Testing**: https://www.deque.com/axe/

---

**Related**: See `SKILL.md` for core workflow and design principles.
