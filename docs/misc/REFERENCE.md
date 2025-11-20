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

## User Journey Documentation

### Analyzing Existing Applications

Before redesigning an interface, systematically analyze existing user journey documentation.

#### Reading User Journey Maps

**Document Structure to Look For**:
```markdown
docs/USER_JOURNEY_MAP.md
├── Application Overview
│   ├── Core Workflows
│   ├── Navigation Structure
│   └── User Personas
├── Journey 1: [Workflow Name]
│   ├── Overview
│   ├── User Persona
│   ├── User Goals
│   ├── Workflow Steps (1-10+)
│   └── Key UI Components
├── Journey 2: [Another Workflow]
...
└── Less-Used Interfaces
    ├── Dialog flows
    ├── Settings
    └── Edge case handling
```

**Extraction Checklist**:
- [ ] Identify all user personas (who uses this?)
- [ ] Map critical workflows (what do they do most often?)
- [ ] Note pain points (where do they struggle?)
- [ ] List all UI components (what exists now?)
- [ ] Find edge cases (what's rarely used but important?)
- [ ] Understand technical constraints (framework, performance limits)

#### Example: Analyzing RMCitecraft User Journey

**From `docs/USER_JOURNEY_MAP.md`**:

**User Personas Identified**:
1. Genealogist processing 20-500 census citations
2. Genealogist processing Find a Grave memorials
3. Genealogist reviewing citations before database write

**Critical Workflows**:
1. Census Batch Processing (3-panel layout: Queue | Data Entry | Image Viewer)
2. Find a Grave Batch Processing (2-panel: Queue | Detail with extraction)
3. Citation Management (2-panel: Pending Queue | Citation Detail)
4. Dashboard Monitoring (4 phases: Overview | Charts | Detail | Analytics)

**Pain Points Discovered**:
- Census data entry requires window switching (alt-tab between app and FamilySearch)
- Missing data fields require manual lookup (no integrated image viewer)
- Validation errors appear after submission (no live preview)
- Place validation dialog appears mid-batch (interrupts flow)

**Less-Used But Critical**:
- Place Validation Dialog (gazetteer validation, duplicate detection)
- Resume Session Dialog (crash recovery)
- Settings Dialog (configuration)

### Creating Comparative Documentation

#### Template: Before/After Journey Improvement

```markdown
# Journey Improvement: [Workflow Name]

## Problem Analysis

### Current State (Before)

**Pain Points**:
- [Specific problem 1]: Description and impact
- [Specific problem 2]: Description and impact
- [Specific problem 3]: Description and impact

**Current Workflow**:
1. User action → System response → Time spent
2. User action → System response → Time spent
3. ...

**Metrics** (if available):
- Average time per task: X minutes
- Error rate: Y%
- User satisfaction: Z/10

**Screenshot**:
![Current State](screenshots/before_[workflow].png)

### Proposed Design (After)

**Solutions**:
- ✅ [Solution 1]: How it solves pain point 1
- ✅ [Solution 2]: How it solves pain point 2
- ✅ [Solution 3]: How it solves pain point 3

**New Workflow**:
1. User action → System response → Time spent
2. User action → System response → Time spent
3. ...

**Expected Metrics**:
- Average time per task: X minutes (Y% reduction)
- Error rate: Z% (W% reduction)
- User satisfaction: Q/10 (improvement)

**Screenshot**:
![Proposed Design](screenshots/after_[workflow].png)

## Design Improvements

### Improvement 1: [Feature Name]

**What Changed**:
- Before: [Description]
- After: [Description]

**Why It's Better**:
- [Benefit 1]
- [Benefit 2]

**Implementation Notes**:
- Technical approach
- Complexity estimate
- Dependencies

### Improvement 2: [Feature Name]
...

## Benefits Summary

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Time per task | 2 min | 45 sec | 62% faster |
| Window switches | 5-10 | 0 | Eliminated |
| Validation errors | 15% | 3% | 80% reduction |
| User satisfaction | 6/10 | 9/10 | +50% |

## Implementation Plan

1. **Phase 1**: Core layout changes (1-2 days)
2. **Phase 2**: Integrated components (2-3 days)
3. **Phase 3**: Testing and refinement (1 day)

**Total Effort**: 4-6 days
```

#### Real Example: Census Batch Processing Redesign

```markdown
# Journey Improvement: Census Batch Processing

## Problem Analysis

### Current State (Before)

**Pain Points**:
- **Window Switching**: Users alt-tab between RMCitecraft and FamilySearch browser to view census image while entering data (5-10 switches per citation)
- **No Live Preview**: Can't see generated citation until after submitting form (causes re-work if data is wrong)
- **Separate Image Viewer**: Image opens in external browser, requires manual navigation to FamilySearch each time

**Current Workflow**:
1. Click citation in queue → 5 sec
2. Open FamilySearch link in browser → 10 sec
3. Alt-tab to browser → 2 sec
4. Find person on census page → 15-30 sec
5. Alt-tab back to app → 2 sec
6. Enter ED field → 5 sec
7. Alt-tab to browser to check → 2 sec
8. Alt-tab back → 2 sec
9. Enter sheet field → 5 sec
10. Repeat for 3-5 more fields → 30-60 sec
11. Submit form → 2 sec
12. **Total: ~2 minutes per citation**

**Metrics**:
- Average time: 2 minutes per citation
- Window switches: 8-10 per citation
- Validation errors: 15% (typos from squinting at distant window)

![Current State](screenshots/before_census_batch.png)

### Proposed Design (After)

**Solutions**:
- ✅ **Integrated Image Viewer**: Embed FamilySearch image in right panel (eliminate alt-tabbing)
- ✅ **Live Citation Preview**: Show formatted citation as user types (immediate feedback)
- ✅ **Smart Field Focus**: Auto-advance to next field after valid input (keyboard efficiency)
- ✅ **Zoom Controls**: In-app zoom for image (no need to squint)

**New Workflow**:
1. Click citation in queue → 5 sec
2. View census image in integrated panel → 0 sec (already visible)
3. Enter ED field (with image visible) → 5 sec
4. Auto-advance to sheet field → 0 sec
5. Enter sheet → 5 sec
6. Enter line → 5 sec
7. Enter family → 5 sec
8. See live preview of citation → 0 sec (continuous)
9. Submit form → 2 sec
10. **Total: ~45 seconds per citation**

**Expected Metrics**:
- Average time: 45 seconds (62% reduction)
- Window switches: 0 (eliminated)
- Validation errors: 3% (clear visibility, live preview)

![Proposed Design](screenshots/after_census_batch.png)

## Design Improvements

### Improvement 1: Integrated Image Viewer

**What Changed**:
- Before: FamilySearch link opens external browser
- After: Census image embedded in right panel with zoom controls

**Why It's Better**:
- No context switching (eyes stay on single screen)
- Reduced cognitive load (no need to remember data while switching)
- Faster (no browser navigation delay)
- Better ergonomics (adjustable zoom, pan controls)

**Implementation**:
```python
# Image viewer component with FamilySearch integration
class IntegratedImageViewer:
    def __init__(self, familysearch_url):
        self.url = familysearch_url
        self.zoom_level = 1.0

    def render(self):
        with ui.card().classes('h-full'):
            # Image with zoom controls
            with ui.column().classes('w-full h-full'):
                # Zoom controls
                with ui.row().classes('gap-1'):
                    ui.button('−', on_click=self.zoom_out).props('dense')
                    ui.label(f'{int(self.zoom_level * 100)}%')
                    ui.button('+', on_click=self.zoom_in).props('dense')
                    ui.button('Reset', on_click=self.reset_zoom)

                # Image viewer
                ui.interactive_image(
                    self.url,
                    on_mouse=self.handle_pan
                ).classes('w-full').style(f'transform: scale({self.zoom_level})')
```

### Improvement 2: Live Citation Preview

**What Changed**:
- Before: Citation appears only after clicking "Update"
- After: Citation updates in real-time as user types

**Why It's Better**:
- Immediate validation feedback
- See formatting before committing
- Catch typos instantly
- Confidence in data accuracy

**Implementation**:
```python
def _on_field_change(self, field: str, value: str):
    """Update form data and regenerate citation preview."""
    self.form_data[field] = value

    # Merge with extracted data
    merged = {**self.citation.extracted_data, **self.form_data}

    # Generate preview
    preview = self.formatter.format_citation(merged)

    # Update preview display (reactive)
    self.preview_footnote.text = preview['footnote']
    self.preview_short.text = preview['short_footnote']
```

### Improvement 3: Smart Field Navigation

**What Changed**:
- Before: Manual tab/click to next field
- After: Auto-advance after valid input

**Why It's Better**:
- Faster keyboard workflow
- Eyes stay on image (no need to look at keyboard)
- Natural flow (like a wizard)

## Benefits Summary

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Time per citation | 2 min | 45 sec | **62% faster** |
| Window switches | 8-10 | 0 | **Eliminated** |
| Validation errors | 15% | 3% | **80% reduction** |
| Eye strain | High | Low | **Significant** |
| Workflow interruptions | 10-15 | 0 | **Eliminated** |

**Estimated ROI**:
- For 100 citations: Save 1.9 hours (115 minutes)
- For 500 citations: Save 9.6 hours (575 minutes)
- Error correction time reduced by ~80%

## Implementation Plan

### Phase 1: Layout Restructuring (Day 1-2)
- Modify 3-panel layout proportions (20% queue | 40% form | 40% image)
- Add image viewer component
- Integrate FamilySearch image loading

### Phase 2: Interactive Features (Day 3-4)
- Implement zoom/pan controls
- Add live citation preview
- Wire up reactive updates

### Phase 3: Smart Navigation (Day 5)
- Auto-advance logic
- Keyboard shortcuts
- Field validation

### Phase 4: Testing & Polish (Day 6)
- Playwright automated tests
- User acceptance testing
- Performance optimization

**Total Effort**: 6 days
```

### Capturing Comparative Screenshots

#### Automated Screenshot Workflow

```python
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def capture_before_after_screenshots():
    """Capture before and after screenshots for design comparison."""

    screenshots_dir = Path('docs/screenshots/design_comparison')
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page(viewport={'width': 1920, 'height': 1080})

        # ==== BEFORE STATE ====
        print("Capturing BEFORE state...")

        # Navigate to current design
        await page.goto('http://localhost:8080/census-batch')
        await page.wait_for_selector('.citation-queue')

        # Load sample data
        await page.click('button:has-text("Load")')
        await page.fill('input[label="Number of citations"]', '5')
        await page.click('button:has-text("Load"):visible')
        await page.wait_for_timeout(2000)

        # Select a citation
        await page.click('.citation-queue .citation-item:first-child')
        await page.wait_for_timeout(1000)

        # Capture full workflow
        await page.screenshot(
            path=screenshots_dir / 'before_census_batch_full.png',
            full_page=True
        )

        # Capture specific pain point (separate window requirement)
        await page.click('a:has-text("FamilySearch")')  # Opens external window
        await page.wait_for_timeout(2000)

        # Capture both windows (requires OS-level screenshot)
        await page.screenshot(path=screenshots_dir / 'before_window_switching.png')

        # ==== APPLY DESIGN CHANGES ====
        print("Applying design improvements...")

        # Option 1: Use feature flag to enable new design
        await page.goto('http://localhost:8080/census-batch?redesign=true')

        # Option 2: Inject CSS/JS for new layout
        await page.add_style_tag(content="""
            .census-batch-container {
                display: grid;
                grid-template-columns: 20% 40% 40%;
                gap: 1rem;
            }
            .integrated-image-viewer {
                display: block;
                height: 100%;
            }
        """)

        # Option 3: Deploy to staging environment
        # await page.goto('http://localhost:8081/census-batch')  # Staging with new design

        # ==== AFTER STATE ====
        print("Capturing AFTER state...")

        await page.wait_for_selector('.citation-queue')
        await page.wait_for_timeout(2000)

        # Capture new design with integrated image viewer
        await page.screenshot(
            path=screenshots_dir / 'after_census_batch_full.png',
            full_page=True
        )

        # Capture live preview feature
        await page.fill('input[name="enumeration_district"]', '96-413')
        await page.wait_for_timeout(500)  # Let live preview update

        await page.screenshot(path=screenshots_dir / 'after_live_preview.png')

        # ==== SIDE-BY-SIDE COMPARISON ====
        print("Creating comparison images...")

        # Use PIL to create side-by-side comparison
        from PIL import Image

        before = Image.open(screenshots_dir / 'before_census_batch_full.png')
        after = Image.open(screenshots_dir / 'after_census_batch_full.png')

        # Resize to same height
        height = min(before.height, after.height)
        before_resized = before.resize((int(before.width * height / before.height), height))
        after_resized = after.resize((int(after.width * height / after.height), height))

        # Create side-by-side
        comparison = Image.new('RGB', (before_resized.width + after_resized.width, height))
        comparison.paste(before_resized, (0, 0))
        comparison.paste(after_resized, (before_resized.width, 0))

        comparison.save(screenshots_dir / 'comparison_side_by_side.png')

        print(f"Screenshots saved to: {screenshots_dir}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_before_after_screenshots())
```

#### Annotating Screenshots

Use image annotation tools to highlight improvements:

```python
from PIL import Image, ImageDraw, ImageFont

def annotate_screenshot(image_path, annotations):
    """Add arrows and callouts to screenshot."""

    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)

    # Load font
    try:
        font = ImageFont.truetype("Arial.ttf", 24)
    except:
        font = ImageFont.load_default()

    for annotation in annotations:
        # Draw arrow
        x1, y1 = annotation['start']
        x2, y2 = annotation['end']
        draw.line([x1, y1, x2, y2], fill='red', width=3)

        # Draw arrowhead
        draw.polygon([
            (x2, y2),
            (x2 - 10, y2 - 5),
            (x2 - 10, y2 + 5)
        ], fill='red')

        # Draw text callout
        text = annotation['text']
        bbox = draw.textbbox((x2 + 10, y2 - 20), text, font=font)
        draw.rectangle(bbox, fill='yellow', outline='red')
        draw.text((x2 + 10, y2 - 20), text, fill='black', font=font)

    img.save(image_path.replace('.png', '_annotated.png'))

# Example usage
annotate_screenshot('docs/screenshots/after_census_batch_full.png', [
    {
        'start': (1200, 400),
        'end': (1400, 500),
        'text': '✅ Integrated image viewer\n(no window switching!)'
    },
    {
        'start': (600, 800),
        'end': (800, 900),
        'text': '✅ Live citation preview\n(see results as you type)'
    }
])
```

### Documentation Checklist

Before/After user journey documentation should include:

- [ ] **Problem statement** - Specific pain points with current design
- [ ] **Solution overview** - High-level approach to solving problems
- [ ] **Workflow comparison** - Step-by-step before/after
- [ ] **Time metrics** - Quantify improvements (seconds, minutes)
- [ ] **Error reduction** - Show validation/accuracy improvements
- [ ] **Screenshots** - Before, After, and Side-by-side comparison
- [ ] **Annotated images** - Highlight key improvements with arrows/callouts
- [ ] **Benefits summary table** - Quantified improvements
- [ ] **Implementation plan** - Effort estimate and phasing
- [ ] **ROI calculation** - Time saved over batch sizes

---

## Additional Resources

- **Playwright Docs**: https://playwright.dev/python/
- **Chrome DevTools Protocol**: https://chromedevtools.github.io/devtools-protocol/
- **Web Performance API**: https://developer.mozilla.org/en-US/docs/Web/API/Performance
- **Accessibility Testing**: https://www.deque.com/axe/
- **PIL (Image Manipulation)**: https://pillow.readthedocs.io/

---

**Related**: See `SKILL.md` for core workflow and design principles.
