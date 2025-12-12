---
priority: archive
topics: [citation, batch, testing, ui, automation]
---

# Claude Skills Best Practices

Guidelines for creating effective, context-efficient Claude Code skills.

## Core Principles

### 1. Context Window Efficiency

**Skills ARE loaded into context when invoked** - Every line counts.

**Best Practices:**
- ✅ Keep SKILL.md concise (150-200 lines ideal)
- ✅ Focus on principles, not exhaustive references
- ✅ Use clear hierarchy (headers enable quick scanning)
- ✅ Externalize detailed patterns to REFERENCE.md
- ✅ Show pattern with one example, not every variation

**Anti-Patterns:**
- ❌ Including full API documentation
- ❌ Repeating similar examples
- ❌ Verbose explanations when concise works
- ❌ Kitchen-sink approach (everything in one file)

### 2. Structure: Core vs Reference

**SKILL.md** (loaded into context):
- What the skill does
- When to use it
- Core workflow
- Key principles
- One representative example per pattern
- Quick reference
- Pointer to REFERENCE.md

**REFERENCE.md** (consulted as needed):
- Detailed patterns and variations
- Advanced techniques
- Comprehensive examples
- Troubleshooting guides
- Code snippets library
- Edge cases and gotchas

### 3. Information Hierarchy

Use headers strategically for quick scanning:

```markdown
## Design Thinking          # High-level approach
### When to Use            # Decision criteria
### Core Approach          # Main workflow
### Common Patterns        # Frequent use cases
### Quick Reference        # At-a-glance guide
```

Claude can quickly locate relevant sections without parsing everything.

## Skill Document Template

### Minimal Effective Structure

```markdown
---
name: skill-name
description: One-line description (what it does, when to use it)
---

Brief introduction (1-2 paragraphs).

## Core Concept

High-level principle or philosophy.

## When to Use This Skill

- Bullet list of scenarios
- Keep to 3-5 items
- Be specific

## Core Workflow

Step-by-step approach:
1. Step one
2. Step two
3. Step three

### Pattern 1: Common Use Case

One clear example showing the pattern:

```code
# Example demonstrating the pattern
# Keep concise but complete
```

### Pattern 2: Another Common Use Case

Another example, different from Pattern 1.

## Quick Reference

**Common Task 1:**
```code
# Minimal code snippet
```

**Common Task 2:**
```code
# Minimal code snippet
```

**For detailed patterns**, see: `./REFERENCE.md`

---

## Skill Integration

How this skill fits with overall workflow.
```

### Example: frontend-design Skill

**SKILL.md structure** (162 lines):
1. Design Thinking (20 lines)
2. Frontend Aesthetics Guidelines (15 lines)
3. Automated UI Testing (50 lines)
   - When to use
   - Core approach (one example)
   - Common issues (quick list)
4. Quick Reference (20 lines)
5. Integration (10 lines)

**REFERENCE.md** (634 lines):
- Comprehensive testing patterns
- Advanced automation techniques
- Debugging guides
- Performance profiling
- Visual regression testing

## Context Usage Analysis

### Before Refactoring
- **338 lines** in SKILL.md
- All content loaded into context
- ~6,000 tokens consumed

### After Refactoring
- **162 lines** in SKILL.md (core only)
- **634 lines** in REFERENCE.md (consulted as needed)
- ~3,000 tokens for core skill
- ~10,000 tokens if reference needed
- **52% reduction in typical context usage**

## Skill Invocation Behavior

### What Gets Loaded

When you invoke a skill:
```
User: "Use frontend-design skill to create a button"
       ↓
Claude: Invokes Skill tool
       ↓
System: Loads SKILL.md into context (162 lines)
       ↓
Claude: Applies principles from SKILL.md
```

### When Reference is Needed

If Claude needs detailed patterns:
```
Claude: "I need advanced Playwright patterns"
       ↓
Claude: Reads REFERENCE.md
       ↓
Claude: Applies specific pattern
```

**Key Insight**: REFERENCE.md is only loaded if needed, saving context for most invocations.

## Writing Effective Skills

### Do's

✅ **Start with "Why"** - Explain the purpose and context
✅ **Focus on principles** - Teach approach, not just code
✅ **One clear example** - Show pattern with minimal code
✅ **Use headers** - Enable quick navigation
✅ **Link to reference** - Point to detailed docs
✅ **Be opinionated** - Provide clear guidance
✅ **Show workflow** - Step-by-step process
✅ **Include quick reference** - Common tasks at a glance

### Don'ts

❌ **Don't duplicate examples** - Show pattern once
❌ **Don't include full APIs** - Link to docs instead
❌ **Don't explain obvious things** - Assume competent user
❌ **Don't use verbose language** - Be concise
❌ **Don't include every edge case** - Focus on common cases
❌ **Don't mix principles and details** - Separate core and reference
❌ **Don't repeat yourself** - DRY applies to docs too

### Example: Good vs Bad

**❌ Bad** (verbose, exhaustive):
```markdown
## Typography

Typography is very important for web design. You should always
choose fonts carefully. Here are 50 different font combinations
you could use in various scenarios...

### Font Combination 1: For E-commerce
Use Montserrat Bold for headings...
[300 lines of font combinations]
```

**✅ Good** (concise, principled):
```markdown
## Typography

Choose distinctive, characterful fonts. Avoid generic choices (Inter, Roboto).

**Pattern**: Pair display font (headings) with refined body font.

Example:
- Display: Playfair Display (elegant, editorial)
- Body: Source Serif Pro (readable, professional)

**For 50+ font pairings**, see: `REFERENCE.md#typography-library`
```

## Measuring Skill Quality

### Metrics

1. **Conciseness**: SKILL.md < 200 lines
2. **Completeness**: All core concepts covered
3. **Clarity**: Can understand workflow in 2 minutes
4. **Usability**: Quick reference enables immediate action
5. **Scalability**: Easy to add patterns without bloating

### Quality Checklist

- [ ] Core principles clearly stated
- [ ] Workflow is step-by-step
- [ ] One example per major pattern
- [ ] Quick reference for common tasks
- [ ] Link to REFERENCE.md for details
- [ ] Headers enable quick scanning
- [ ] Total < 200 lines
- [ ] No duplicate information
- [ ] Opinionated and actionable

## Skill Types and Approaches

### Type 1: Workflow Skills

**Focus**: Process and methodology

**Example**: `frontend-design` (design thinking → implement → test)

**Structure**:
- Core workflow steps
- When to use each step
- One example per step
- Integration with overall process

### Type 2: Technical Skills

**Focus**: Technical implementation

**Example**: `api-integration` (connect to APIs)

**Structure**:
- Authentication patterns
- Request/response handling
- Error handling
- One example per API type
- Quick reference for common APIs

### Type 3: Domain Skills

**Focus**: Domain-specific expertise

**Example**: `genealogy-research` (research best practices)

**Structure**:
- Domain principles
- Research methodology
- Source evaluation
- Citation standards
- One example per source type

## Maintenance and Evolution

### When to Update Skills

- **New patterns emerge** - Add to REFERENCE.md
- **Core approach changes** - Update SKILL.md
- **Better examples found** - Replace in SKILL.md
- **Edge cases discovered** - Document in REFERENCE.md

### Versioning

Skills don't need semantic versioning, but document major changes:

```markdown
## Changelog

### 2025-11-20: Major refactor
- Split into SKILL.md (core) and REFERENCE.md (details)
- Reduced context usage by 52%
- Added Playwright automated testing section

### 2025-11-15: Initial version
- Design aesthetics guidelines
- Typography and color principles
```

## Real-World Example

**Before**: frontend-design skill (338 lines, all in SKILL.md)
- Design thinking: 25 lines
- Aesthetics guidelines: 20 lines
- Playwright testing: 293 lines (too detailed!)

**After**: Split into two files
- **SKILL.md** (162 lines): Core principles, one testing example, quick ref
- **REFERENCE.md** (634 lines): Comprehensive patterns, advanced techniques

**Result**:
- 52% reduction in typical context usage
- Faster skill activation (less to parse)
- Preserved all information (nothing lost)
- Better organization (clear hierarchy)

## Conclusion

**Great skills are concise, principled, and actionable.**

Follow the 80/20 rule:
- **80% of use cases** covered in SKILL.md (core)
- **20% of advanced cases** in REFERENCE.md (details)

Every line in SKILL.md should earn its place by being:
1. **Essential** to understanding the skill
2. **Actionable** for immediate use
3. **Non-redundant** with other content

**When in doubt, move to REFERENCE.md.**

---

**See also**:
- `docs/misc/SKILL.md` - Well-crafted example
- `docs/misc/REFERENCE.md` - Reference document pattern
