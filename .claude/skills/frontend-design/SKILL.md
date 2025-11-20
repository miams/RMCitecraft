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

## Automated UI Testing & Debugging

When building complex UIs, use **Playwright for automated testing and rapid iteration**. This enables systematic, evidence-based debugging.

### When to Use Automated Testing

- Building complex multi-component UIs (dashboards, forms, workflows)
- Debugging "silent failures" (renders on server but not in browser)
- Verifying interactions across multiple components
- Preventing visual regressions
- Performance profiling

### Core Testing Approach

**Incremental Component Testing** - Test components one at a time to isolate failures:

```python
from playwright.async_api import async_playwright

async def test_component():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Capture diagnostics
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))

        # Navigate and test
        await page.goto('http://localhost:8080')
        await page.click('button:has-text("Dashboard")')
        await page.wait_for_selector('.dashboard-loaded', timeout=10000)

        # Validate
        body_text = await page.inner_text('body')
        assert 'Expected Content' in body_text

        # Screenshot on failure
        if errors:
            await page.screenshot(path='failure.png')

        await browser.close()
```

**Bisect Failures** - Add components incrementally to find the problem:
1. Test minimal version → Works?
2. Add component A → Works?
3. Add component B → Fails? → B is the problem

### Common Issues and Patterns

**Silent Failures (No JavaScript Errors)**
- **Cause**: Lambda functions in config dicts (`formatter: lambda x: ...`)
- **Solution**: Pre-format data, use template strings, make callbacks private (`_callback`)

**Wait Strategies**
```python
# ❌ Bad: Fixed timeout
await page.wait_for_timeout(5000)

# ✅ Good: Wait for condition
await page.wait_for_selector('.loaded', timeout=10000)
```

**Diagnostic Capture**
```python
# Capture everything for analysis
console_logs = []
errors = []
page.on('console', lambda m: console_logs.append(f"{m.type}: {m.text}"))
page.on('pageerror', lambda e: errors.append(str(e)))
```

### Testing Workflow

When building complex UIs:

1. **Design** - Create distinctive interface following aesthetic guidelines
2. **Implement** - Write production code
3. **Test Incrementally** - Add components one at a time, test after each
4. **Capture Diagnostics** - Screenshots, console logs, errors, network
5. **Fix Issues** - Evidence-based debugging with captured data
6. **Verify** - Re-test to confirm fix

### Quick Reference

**Create test script:**
```python
async def test_ui():
    # Launch browser, capture diagnostics
    # Navigate, interact, validate
    # Screenshot on failure, report findings
```

**Isolate failure:**
```python
# Test: minimal → + header → + charts → + table
# When it fails, you found the problematic component
```

**Common fixes:**
- Lambda in config dict → Pre-format data or use template string
- Public callbacks → Make private with `_` prefix
- Fixed timeouts → Use `wait_for_selector()` with timeout

**For detailed patterns and advanced techniques**, see: `.claude/skills/frontend-design/REFERENCE.md`

---

## Skill Integration

This skill combines **creative design** with **systematic testing**:
- Choose bold aesthetic direction
- Implement with attention to detail
- Test incrementally with Playwright
- Debug with evidence (screenshots + logs)
- Iterate rapidly with automation

Every frontend should be both **visually distinctive** and **reliably functional**.
