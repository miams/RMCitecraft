---
name: frontend-design
description: Create distinctive, production-grade frontend interfaces with high design quality. Use this skill when the user asks to build web components, pages, or applications. Generates creative, polished code that avoids generic AI aesthetics.
license: Complete terms in LICENSE.txt
---

This skill guides creation of distinctive, production-grade frontend interfaces that avoid generic "AI slop" aesthetics. Implement real working code with exceptional attention to aesthetic details and creative choices.

The user provides frontend requirements: a component, page, application, or interface to build. They may include context about the purpose, audience, or technical constraints.

## Design Thinking

Before coding, understand the context and commit to a BOLD aesthetic direction:
- **Purpose**: What problem does this interface solve? Who uses it?
- **Tone**: Pick an extreme: brutally minimal, maximalist chaos, retro-futuristic, organic/natural, luxury/refined, playful/toy-like, editorial/magazine, brutalist/raw, art deco/geometric, soft/pastel, industrial/utilitarian, etc. There are so many flavors to choose from. Use these for inspiration but design one that is true to the aesthetic direction.
- **Constraints**: Technical requirements (framework, performance, accessibility).
- **Differentiation**: What makes this UNFORGETTABLE? What's the one thing someone will remember?

**CRITICAL**: Choose a clear conceptual direction and execute it with precision. Bold maximalism and refined minimalism both work - the key is intentionality, not intensity.

Then implement working code (HTML/CSS/JS, React, Vue, etc.) that is:
- Production-grade and functional
- Visually striking and memorable
- Cohesive with a clear aesthetic point-of-view
- Meticulously refined in every detail

## Frontend Aesthetics Guidelines

Focus on:
- **Typography**: Choose fonts that are beautiful, unique, and interesting. Avoid generic fonts like Arial and Inter; opt instead for distinctive choices that elevate the frontend's aesthetics; unexpected, characterful font choices. Pair a distinctive display font with a refined body font.
- **Color & Theme**: Commit to a cohesive aesthetic. Use CSS variables for consistency. Dominant colors with sharp accents outperform timid, evenly-distributed palettes.
- **Motion**: Use animations for effects and micro-interactions. Prioritize CSS-only solutions for HTML. Use Motion library for React when available. Focus on high-impact moments: one well-orchestrated page load with staggered reveals (animation-delay) creates more delight than scattered micro-interactions. Use scroll-triggering and hover states that surprise.
- **Spatial Composition**: Unexpected layouts. Asymmetry. Overlap. Diagonal flow. Grid-breaking elements. Generous negative space OR controlled density.
- **Backgrounds & Visual Details**: Create atmosphere and depth rather than defaulting to solid colors. Add contextual effects and textures that match the overall aesthetic. Apply creative forms like gradient meshes, noise textures, geometric patterns, layered transparencies, dramatic shadows, decorative borders, custom cursors, and grain overlays.

NEVER use generic AI-generated aesthetics like overused font families (Inter, Roboto, Arial, system fonts), cliched color schemes (particularly purple gradients on white backgrounds), predictable layouts and component patterns, and cookie-cutter design that lacks context-specific character.

Interpret creatively and make unexpected choices that feel genuinely designed for the context. No design should be the same. Vary between light and dark themes, different fonts, different aesthetics. NEVER converge on common choices (Space Grotesk, for example) across generations.

**IMPORTANT**: Match implementation complexity to the aesthetic vision. Maximalist designs need elaborate code with extensive animations and effects. Minimalist or refined designs need restraint, precision, and careful attention to spacing, typography, and subtle details. Elegance comes from executing the vision well.

Remember: Claude is capable of extraordinary creative work. Don't hold back, show what can truly be created when thinking outside the box and committing fully to a distinctive vision.

## Automated UI Testing & Debugging with Playwright

When building complex frontends, use **Playwright with Chrome Debug Mode** for AI-assisted automated testing and rapid iteration. This transforms development from manual testing to systematic, evidence-based debugging.

### Core Workflow: Automated Browser Control

```python
from playwright.async_api import async_playwright
import asyncio

async def test_ui():
    async with async_playwright() as p:
        # Launch browser (headless=False for visual debugging)
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        page = await browser.new_page()

        # Capture all diagnostics
        console_messages = []
        errors = []
        page.on('console', lambda m: console_messages.append(f"{m.type}: {m.text}"))
        page.on('pageerror', lambda e: errors.append(str(e)))

        # Navigate and test
        await page.goto('http://localhost:8080')
        await page.click('button:has-text("Dashboard")')
        await page.wait_for_timeout(2000)

        # Validate UI state
        body_text = await page.inner_text('body')
        assert 'Expected Content' in body_text

        # Report findings
        if errors:
            print('JavaScript Errors:', errors)

        await browser.close()

# Run test
asyncio.run(test_ui())
```

### Incremental Component Testing

**Strategy**: Test components one at a time to isolate failures.

```python
async def bisect_component_failure():
    """Find which component causes the failure."""
    components = ['minimal', 'header', 'charts', 'table', 'detail']

    for comp in components:
        # Enable only this component
        enable_component(comp)

        # Test
        result = await test_dashboard()

        if not result.passed:
            print(f'❌ {comp} caused failure')
            await page.screenshot(path=f'failure_{comp}.png')
            return comp
        else:
            print(f'✅ {comp} works')
```

**Real Example from Dashboard Debugging**:
1. ✅ Minimal (labels only) → Works
2. ✅ + Header → Works
3. ✅ + Phase 1 components → Works
4. ❌ + Phase 2 charts → **FAILS** → Isolated problem to ECharts components

### Diagnostic Data Capture

Capture everything for comprehensive debugging:

```python
class ComprehensiveDiagnostics:
    def __init__(self, page):
        self.console = []
        self.errors = []
        self.requests = []
        self.screenshots = []

        # Capture browser events
        page.on('console', lambda m: self.console.append(m))
        page.on('pageerror', lambda e: self.errors.append(e))
        page.on('request', lambda r: self.requests.append(r))
        page.on('response', lambda r: self._check_response(r))

    async def export_report(self):
        return {
            'console': [f"{m.type}: {m.text}" for m in self.console],
            'errors': [str(e) for e in self.errors],
            'network_failed': [r for r in self.requests if r.failed],
            'screenshot': await page.screenshot(),
            'html_snapshot': await page.content()
        }
```

### Common Debugging Patterns

#### 1. Silent Failures (No Errors in Console)

**Problem**: Component renders on server but not in browser, no JavaScript errors.

**Solution**: Incremental testing + JSON serialization check.

```python
# Test each component independently
async def isolate_silent_failure():
    test_cases = [
        ('phase1', render_phase1),
        ('phase2', render_phase2),
        ('phase3', render_phase3)
    ]

    for name, render_func in test_cases:
        render_func()
        await page.wait_for_timeout(2000)

        # Check if rendered
        body = await page.inner_text('body')
        if expected_text not in body:
            print(f'Silent failure in {name}')
            # Likely: JSON serialization issue (lambdas, functions)
            return name
```

**Common Causes**:
- Lambda functions in configuration dictionaries (e.g., ECharts `formatter: lambda x: ...`)
- Public callback attributes (`self.on_click = callback` instead of `self._on_click = callback`)
- Function references in state that gets serialized to JSON

#### 2. Visual Regression Detection

```python
# Baseline screenshot
await page.screenshot(path='baseline.png')

# After changes
await page.screenshot(path='current.png')

# Compare (requires PIL)
from PIL import Image, ImageChops

baseline = Image.open('baseline.png')
current = Image.open('current.png')
diff = ImageChops.difference(baseline, current)

if diff.getbbox():
    print('Visual regression detected!')
    diff.save('visual_diff.png')
```

#### 3. Performance Profiling

```python
async def profile_interaction():
    # Start performance measurement
    await page.evaluate('() => performance.mark("start")')

    # Perform action
    await page.click('button.expensive-operation')

    # Measure
    metrics = await page.evaluate('''() => {
        performance.mark("end");
        performance.measure("operation", "start", "end");
        const measure = performance.getEntriesByName("operation")[0];
        return {
            duration: measure.duration,
            memory: performance.memory?.usedJSHeapSize || 0
        };
    }''')

    print(f'Operation: {metrics["duration"]}ms, Memory: {metrics["memory"]} bytes')
```

### Advanced Techniques

#### Network Interception (Mock APIs)

```python
async def mock_api_responses(page):
    async def handle_route(route):
        if 'api/batch_items' in route.request.url:
            # Mock response
            await route.fulfill(json={
                'items': [{'id': 1, 'status': 'completed'}]
            })
        else:
            await route.continue_()

    await page.route('**/*', handle_route)
```

#### Video Recording

```python
context = await browser.new_context(
    record_video_dir='./debug_videos',
    record_video_size={'width': 1920, 'height': 1080}
)

page = await context.new_page()
# ... perform actions ...
await context.close()  # Video saved automatically
```

#### Chrome DevTools Protocol (CDP) Access

```python
# Get CDP session for advanced profiling
client = await page.context.new_cdp_session(page)

# Enable JavaScript profiling
await client.send('Profiler.enable')
await client.send('Profiler.start')

# Interact with UI
await page.click('button')

# Stop and analyze profile
result = await client.send('Profiler.stop')
print(f'Profile data: {result}')
```

### Wait Strategies (Critical for Reliability)

```python
# ❌ BAD: Fixed timeouts (brittle, slow)
await page.wait_for_timeout(5000)

# ✅ GOOD: Wait for specific conditions
await page.wait_for_selector('.dashboard-loaded')
await page.wait_for_function('() => window.appReady === true')
await page.wait_for_response('**/api/data')

# ✅ BEST: Condition + timeout with error handling
try:
    await page.wait_for_selector('.dashboard', timeout=10000)
except TimeoutError:
    await page.screenshot(path='timeout_failure.png')
    print(f'Console logs: {console_messages}')
    raise
```

### AI-Specific Benefits

1. **Rapid Iteration**: Test 5 design variants in parallel, get instant feedback
2. **Evidence-Based Decisions**: Every conclusion backed by screenshots + diagnostics
3. **No Manual Testing**: AI runs tests while analyzing results
4. **Pattern Recognition**: Analyze 100 test runs to find failure patterns

### Testing Checklist for Frontend Development

When building complex UIs:

- [ ] **Incremental Testing**: Add components one at a time, test after each
- [ ] **Capture Diagnostics**: Console logs, errors, network requests, screenshots
- [ ] **Wait Strategies**: Use condition-based waits, not fixed timeouts
- [ ] **JSON Serialization**: Check for lambdas/functions in config dicts
- [ ] **Visual Regression**: Compare screenshots before/after changes
- [ ] **Performance**: Profile critical interactions
- [ ] **Cross-Browser**: Test on Chromium, Firefox, WebKit
- [ ] **Accessibility**: Run automated accessibility audits (axe-core)

### Real-World Success Story

**Problem**: Dashboard renders on server but not in browser (silent failure)

**Method**: Incremental automated testing with Playwright

**Process**:
1. Test minimal dashboard → ✅ Works
2. Test + header → ✅ Works
3. Test + Phase 1 components → ✅ Works
4. Test + Phase 2 charts → ❌ **FAILS** (isolated problem)
5. Inspect charts → Found lambda functions in ECharts config
6. Fix lambdas → ✅ All tests pass

**Result**: 30 minutes from problem to solution (vs. 2-4 hours manual debugging)

### Integration with Design Workflow

Use Playwright throughout the design process:

1. **Initial Build**: Create distinctive design
2. **Automated Testing**: Verify all interactions work
3. **Iteration**: Test each design variant automatically
4. **Regression Prevention**: Screenshot comparisons on every change
5. **Performance**: Profile animations and transitions
6. **Deployment**: Automated smoke tests before release

This transforms frontend development from manual trial-and-error into systematic, automated, evidence-based iteration.
