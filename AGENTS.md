---
priority: essential
topics: [database, census, citation, batch, findagrave]
---

# AGENTS.md

**Machine-readable instructions for AI coding agents working on RMCitecraft**

This file provides explicit guidelines, commands, and standards for AI agents assisting with development. For human-oriented documentation, see `README.md` and `CLAUDE.md`.

---

## Project Overview

**RMCitecraft** is a macOS desktop application that automates citation formatting and image management for US Federal census records in RootsMagic genealogy databases.

- **Language**: Python 3.11+
- **Package Manager**: UV (required - replaces pip, poetry, pyenv)
- **UI Framework**: NiceGUI 3.0+ (native mode)
- **Database**: SQLite with custom RMNOCASE collation via ICU extension
- **Browser Automation**: Chrome DevTools Protocol for FamilySearch/Find a Grave
- **Target Platform**: macOS (Apple Silicon M3 Pro primary)

---

## Communication Style
LLM coding agents should:
  - Be Concise: avoid unnecessary explanations unless requested
  - Avoid unnecessarily compliments with phases like "Your right!", "That's insightful."
  - Respond with questions if clarity can improve a response.  Questions should be phrased so that responses can be precise.
  - Regularly engage in constructive criticism behaving in the role of a trusted advisor.

## Do's and Don'ts

### Do

- **Always use UV** for Python dependency management (never pip, poetry, or pipenv)
- **Load ICU extension** before any database operations (see `sqlite-extension/python_example.py`)
- **Use RMNOCASE collation** for text fields in database queries (Surname, Given, Name, etc.)
- **Follow Evidence Explained** citation formatting rules strictly
- **Use Pydantic models** for data validation and structured data
- **Write comprehensive unit tests** for all citation parsing and formatting logic
- **Use Ruff** for linting and formatting (configured in `pyproject.toml`)
- **Use MyPy** for static type checking with strict mode
- **Commit with semantic messages**: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- **Reference files with line numbers** in responses: `file_path:line_number`
- **Check RootsMagic schema** in `docs/reference/schema-reference.md` before database operations
- **Use Loguru** for logging (never print statements in production code)
- **Handle FamilySearch citation format variations** (1790-1950 census years)
- **Test with sample database** at `data/Iiams.rmtree`
- **Document breaking changes** in commit messages and relevant docs
- **Use `census.db`** for AI-extracted census data (separate from RootsMagic database)
- **Check `census_transcription_items`** table for batch transcription state (not old `census_batch_items`)
- **Handle name matching edge cases**: abbreviations (L vs Lyndon), married vs maiden names, spelling variations (Katherine/Catherine)

### Don't

- **Never use pip** or other package managers (UV only)
- **Never query database without loading ICU extension first** (will fail on RMNOCASE fields)
- **Never modify database without user confirmation** and transaction safety
- **Never hard-code file paths** (use environment variables from `.env`)
- **Never commit `.env` files** (use `.env.example` as template)
- **Never skip tests** when modifying citation parsing or formatting logic
- **Never use `print()` for logging** (use Loguru)
- **Never create markdown files proactively** unless explicitly requested
- **Never use emojis** unless user explicitly requests them
- **Never assume citation format** - handle 1790-1950 variations per year
- **Never modify schema** without checking `docs/reference/schema-reference.md`
- **Never bypass git hooks** with `--no-verify` unless explicitly requested
- **Never force push to main/master** branches
- **Never use deprecated datetime.utcnow()** (use `datetime.now(timezone.utc)`)
- **Never write citations to CitationTable TEXT fields for free-form sources** (TemplateID=0 uses SourceTable.Fields BLOB)
- **Never assume census events are owned by the person** (check WitnessTable for shared facts)
- **Never confuse `rmtree_citation_id` column** in batch_state.db - it actually contains Source IDs, not Citation IDs
- **Never extract "Vacant" entries** from FamilySearch census as persons (these are empty dwelling markers)
- **Never rely on exact name match only** - FamilySearch often has initials while RootsMagic has full names

---

## Setup & Build Steps

### Initial Setup

```bash
# 1. Install UV package manager (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Create and activate virtual environment
uv venv
source .venv/bin/activate  # macOS/Linux

# 3. Install all dependencies
uv sync

# 4. Copy environment configuration
cp config/.env.example .env
# Edit .env in project root with your API keys and paths

# 5. Verify database connection
uv run python sqlite-extension/python_example.py
```

### Development Environment

```bash
# Install all extras (packaging + cost optimization)
uv sync --all-extras

# Install only runtime dependencies
uv sync --no-dev

# Add a new dependency
uv add <package-name>           # Runtime
uv add --dev <package-name>     # Development only
```

---

## Test Commands & CI

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/test_parser.py

# Run with verbose output
uv run pytest -vv

# Run tests matching pattern
uv run pytest -k "test_parse_1900"
```

### Code Quality Checks

```bash
# Run all checks (recommended before commit)
uv run ruff check .                    # Lint
uv run ruff format .                   # Format
uv run mypy src/                       # Type check

# Auto-fix linting issues
uv run ruff check . --fix

# Check specific file
uv run ruff check src/rmcitecraft/parser.py
uv run mypy src/rmcitecraft/parser.py
```

### Database Connection Test

```bash
# Test ICU extension and RMNOCASE collation
uv run python sqlite-extension/python_example.py

# Should output:
# - Extension loaded successfully
# - RMNOCASE collation registered
# - Sample queries with sorted results
```

### Database Integrity Tests (CRITICAL)

**Always run database integrity tests when modifying database operations:**

```bash
# Run all database integrity tests
uv run pytest tests/unit/test_database_integrity.py -v

# Run specific integrity test category
uv run pytest tests/unit/test_database_integrity.py::TestPlaceTableIntegrity -v
uv run pytest tests/unit/test_database_integrity.py::TestSourceTableIntegrity -v
uv run pytest tests/unit/test_database_integrity.py::TestCitationTableIntegrity -v
uv run pytest tests/unit/test_database_integrity.py::TestEventTableIntegrity -v
```

**When to Write New Integrity Tests:**

1. **Adding new record type** (e.g., MediaTable, PersonTable)
2. **Modifying existing insert operations** (e.g., adding new fields)
3. **After discovering undocumented field requirements** (add test to prevent regression)

**Comparison-Based Testing Template:**

```python
def test_new_record_matches_existing(db_connection):
    """Compare created record field-by-field with existing record."""
    cursor = db_connection.cursor()

    # Get existing record
    cursor.execute("SELECT * FROM TableName WHERE condition LIMIT 1")
    existing = cursor.fetchone()

    # Create new record using your function
    new_id = create_new_record(...)

    # Fetch created record
    cursor.execute("SELECT * FROM TableName WHERE ID = ?", (new_id,))
    created = cursor.fetchone()

    # Compare field-by-field
    assert type(created[0]) == type(existing[0]), "ID type mismatch"
    assert created[1] is not None, "Field should not be NULL"
    # ... continue for all critical fields
```

**Critical Lessons from Find a Grave Implementation:**

- **Reverse field**: 99.9% of locations have it, not documented anywhere
- **NULL vs 0**: RootsMagic breaks with NULL in integer columns
- **SortDate is BIGINT**: Not INTEGER like other ID fields
- **Empty citation fields**: Free-form sources (TemplateID=0) store differently

See `CLAUDE.md` "Database Integrity Testing" section for full methodology and philosophy.

---

## Code Style & Formatting Rules

### Python Style

- **PEP 8 compliant** via Ruff (configured in `pyproject.toml`)
- **Type hints required** for all function signatures
- **Line length**: 100 characters (Ruff configured)
- **Import order**: stdlib → third-party → local (Ruff auto-sorts)
- **Docstrings**: Google style for public APIs
- **String quotes**: Double quotes preferred (Ruff enforces)

### Architecture Patterns

- **Two-phase citation processing**:
  1. LLM extraction (with missing field detection)
  2. Template-based formatting (deterministic)
- **Pydantic models** for all structured data (LLM output, configs)
- **Repository pattern** for database access
- **Service layer** for business logic
- **Dependency injection** via constructor parameters

### File Organization

```
src/rmcitecraft/
├── config/          # Settings and constants
├── database/        # Database access (connection, repositories)
├── models/          # Pydantic models (citation, image)
├── services/        # Business logic
│   ├── batch_processing.py           # Find a Grave batch workflow
│   ├── familysearch_automation.py    # FamilySearch browser automation
│   ├── familysearch_census_extractor.py  # Census page extraction
│   ├── census_transcription_batch.py     # Census batch transcription
│   ├── census_form_service.py            # Census form data service
│   ├── census_form_renderer.py           # Jinja2 census form rendering
│   ├── census_rmtree_matcher.py          # RM person name matching
│   ├── findagrave_automation.py          # Find a Grave automation
│   └── citation_formatter.py             # Evidence Explained formatting
├── ui/
│   ├── tabs/        # Main UI tabs (dashboard, batch_processing)
│   └── components/  # Reusable UI components
├── validation/      # Citation validation (FormattedCitationValidator)
└── utils/           # Shared utilities

tests/
├── unit/            # Fast, isolated tests (no I/O)
├── integration/     # Component interaction tests
└── e2e/             # Browser automation tests (requires Chrome)
```

### Naming Conventions

- **Files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions/Variables**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private members**: `_leading_underscore`
- **Test functions**: `test_<functionality>_<scenario>`

---

## Commit & PR Guidelines

### Commit Messages

Follow semantic commit format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring (no behavior change)
- `test`: Test additions or modifications
- `chore`: Build/tooling changes
- `perf`: Performance improvements

**Examples:**
```
feat(parser): add support for 1850 census format variations

- Handle dwelling/family number extraction
- Add page vs. sheet detection logic
- Update tests for 1850-1880 formats

Closes #42

fix(database): correct RMNOCASE collation loading

The ICU extension was not loading before queries on Surname field,
causing query failures. Now loads extension in connect_rmtree().

Fixes #38

docs: update AGENTS.md with commit guidelines
```

### Pull Request Process

1. **Create feature branch**: `git checkout -b feat/description` or `fix/description`
2. **Run all checks**: Ruff, MyPy, Pytest
3. **Update tests** for new functionality
4. **Update documentation** if behavior changes
5. **Ensure CI passes** before requesting review
6. **Link related issues** in PR description

### Git Workflow

- **Main branch**: Production-ready code only
- **Dev branch**: Integration branch (if using gitflow)
- **Feature branches**: `feat/<name>`, `fix/<name>`, `docs/<name>`
- **No direct commits to main** (use PRs)
- **Squash and merge** for feature PRs
- **Use `[skip ci]`** in commit messages for docs-only changes

---

## Security & Dependency Policies

### Secrets Management

- **Never commit secrets** (API keys, database passwords, tokens)
- **Use `.env` files** for local development (gitignored)
- **Use environment variables** in production
- **Store in `.env.example`** with placeholder values:
  ```
  ANTHROPIC_API_KEY=your_api_key_here
  OPENAI_API_KEY=your_api_key_here
  ```

### Database Safety

**Working Copy Architecture:**
- RMCitecraft operates on a **working copy** at `/Users/miams/Code/RMCitecraft/data/`
- Production database remains untouched during batch processing
- Users manually copy working database to production when satisfied
- Census images written to final locations: `~/Genealogy/RootsMagic/Files/Records - Census/`

**Write Safety:**
- **Use `DatabaseConnection.transaction()`** for all write operations (read-write mode)
- **Connection defaults to `read_only=True`** for safety (must explicitly use `transaction()` for writes)
- **Check `UTCModDate`** before updates (detect conflicts)
- **Validate schema version** before operations
- **Atomic transactions** ensure all-or-nothing updates (no partial citations)
- **Log all database modifications** with timestamps
- **Validate data completeness** before writing (missing required fields = error)

### Critical Database Architecture

**Free-Form Citation Storage (TemplateID=0):**

For free-form sources (all census citations in this project), RootsMagic stores citation output in **SourceTable.Fields BLOB**, NOT CitationTable TEXT fields.

```python
# WRONG - Don't write to CitationTable for TemplateID=0
cursor.execute("""
    UPDATE CitationTable
    SET Footnote = ?, ShortFootnote = ?, Bibliography = ?
    WHERE CitationID = ?
""", (footnote, short, bib, citation_id))

# CORRECT - Write to SourceTable.Fields BLOB for TemplateID=0
import xml.etree.ElementTree as ET

xml_content = f"""<Root><Fields>
<Field><Name>Footnote</Name><Value>{footnote}</Value></Field>
<Field><Name>ShortFootnote</Name><Value>{short_footnote}</Value></Field>
<Field><Name>Bibliography</Name><Value>{bibliography}</Value></Field>
</Fields></Root>"""

cursor.execute("""
    UPDATE SourceTable
    SET Fields = ?
    WHERE SourceID = (SELECT SourceID FROM CitationTable WHERE CitationID = ?)
""", (xml_content.encode('utf-8'), citation_id))
```

**Census Events are Shared Facts:**

Census records are often shared between household members via WitnessTable. Always check both owned events (EventTable) and witnessed events (WitnessTable).

```python
# Find all census citations for a person (owned + shared)
def get_person_census_citations(person_id):
    # Owned census events
    cursor.execute("""
        SELECT e.EventID, c.CitationID, s.SourceID, s.Name
        FROM EventTable e
        JOIN CitationLinkTable cl ON e.EventID = cl.OwnerID AND cl.OwnerType = 2
        JOIN CitationTable c ON cl.CitationID = c.CitationID
        JOIN SourceTable s ON c.SourceID = s.SourceID
        WHERE e.OwnerID = ? AND e.OwnerType = 0 AND e.EventType = 18
    """, (person_id,))
    owned = cursor.fetchall()

    # Shared census events (as witness)
    cursor.execute("""
        SELECT e.EventID, c.CitationID, s.SourceID, s.Name
        FROM WitnessTable w
        JOIN EventTable e ON w.EventID = e.EventID
        JOIN CitationLinkTable cl ON e.EventID = cl.OwnerID AND cl.OwnerType = 2
        JOIN CitationTable c ON cl.CitationID = c.CitationID
        JOIN SourceTable s ON c.SourceID = s.SourceID
        WHERE w.PersonID = ? AND e.EventType = 18
    """, (person_id,))
    shared = cursor.fetchall()

    return owned + shared
```

### Dependencies

- **Pin major versions** in `pyproject.toml`
- **Use `uv.lock`** for deterministic builds
- **Review new dependencies** before adding (size, maintenance, alternatives)
- **Prefer stdlib** when available
- **Document large dependencies** (> 10MB) and their necessity
- **Keep UV updated**: `curl -LsSf https://astral.sh/uv/install.sh | sh`

### Browser Automation

- **Chrome DevTools Protocol**: Used for FamilySearch and Find a Grave automation
- **Page health monitoring**: Detect and recover from browser crashes
- **Adaptive timeouts**: Self-tune based on network performance
- **Checkpoint system**: Save progress for crash recovery

---

## Project-Specific Context

### Citation Formatting Complexity

**Challenge**: Census citation formats vary by year:
- 1790-1840: No ED, no population schedule terminology
- 1850-1870: Population schedule, page/sheet, dwelling/family
- 1880: ED introduced (required for citations)
- 1900-1940: Population schedule with ED, sheet, family number
- 1950: Uses "stamp" instead of "sheet"

**Solution**: Browser automation extracts FamilySearch data + `citation_formatter.py` applies Evidence Explained templates

### Database Schema Constraints

- **RMNOCASE collation**: Required for text fields (case-insensitive sorting)
- **MediaPath symbols**: `?` = Media Folder, `~` = Home, `*` = Database folder
- **FactTypeID mapping**: Census events use dynamic IDs (not hard-coded)
- **XML in Fields BLOB**: Free-form citations (TemplateID=0) store text in XML

### Key Files for Reference

- **`CLAUDE.md`**: Development guidance and quick reference
- **`docs/reference/schema-reference.md`**: Complete RootsMagic database schema
- **`docs/reference/DATABASE_PATTERNS.md`**: SQL patterns and code examples
- **`docs/reference/DATABASE_TESTING.md`**: Integrity testing methodology
- **`docs/reference/CENSUS_EXTRACTION_DATABASE_SCHEMA.md`**: Census extraction database (census.db) schema
- **`docs/architecture/CENSUS_BATCH_PROCESSING_ARCHITECTURE.md`**: Census workflow details
- **`docs/architecture/CENSUS_FORM_RENDERING.md`**: Census form rendering with Jinja2
- **`sqlite-extension/python_example.py`**: Database connection examples

---

## Common Tasks

### Query Citations from Database

```python
from rmcitecraft.database.connection import DatabaseConnection

# Connection handles ICU extension automatically
with DatabaseConnection() as conn:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT CitationID, SourceID, ActualText
        FROM CitationTable
        WHERE CitationName COLLATE RMNOCASE LIKE ?
    """, ('%1900%',))
```

### Validate Citation Format

```python
from rmcitecraft.validation.data_quality import (
    FormattedCitationValidator,
    is_citation_needs_processing,
)

# Check if citation needs processing (criteria 5 & 6)
needs_work = is_citation_needs_processing(
    footnote=footnote_text,
    short_footnote=short_text,
    bibliography=bib_text,
    census_year=1940
)

# Validate individual components
valid_footnote = FormattedCitationValidator.validate_footnote(footnote_text, 1940)
```

### Run Application

```bash
# Start in foreground (interactive)
rmcitecraft start

# Start in background (daemon)
rmcitecraft start -d

# Check status
rmcitecraft status
```

---

## Troubleshooting

### Common Issues

**"RMNOCASE collation not found"**
- **Cause**: ICU extension not loaded
- **Fix**: Use `connect_rmtree()` function (not raw `sqlite3.connect()`)
- **Example**: See `sqlite-extension/python_example.py`

**"Import errors after adding dependencies"**
- **Cause**: Virtual environment not updated
- **Fix**: Run `uv sync` to install new dependencies

**"Tests fail on database operations"**
- **Cause**: ICU extension path incorrect or missing
- **Fix**: Verify `SQLITE_ICU_EXTENSION` in `.env` points to `./sqlite-extension/icu.dylib`

**"Browser automation times out"**
- **Cause**: FamilySearch page slow to load or network issues
- **Fix**: Increase `CENSUS_BASE_TIMEOUT_SECONDS` in settings
- **Check**: Page health monitoring logs for crash recovery attempts

**"Citation validation fails"**
- **Cause**: Missing required fields (ED for 1900+, sheet/stamp)
- **Fix**: Check `FormattedCitationValidator` in `validation/data_quality.py`
- **Note**: 1950 census uses "stamp" instead of "sheet"

---

## Additional Resources

- **UV Documentation**: https://docs.astral.sh/uv/
- **NiceGUI Documentation**: https://nicegui.io/
- **Ruff Documentation**: https://docs.astral.sh/ruff/
- **Evidence Explained**: Mills, Elizabeth Shown. *Evidence Explained* (citation style guide)
- **RootsMagic**: https://rootsmagic.com/
- **FamilySearch**: https://familysearch.org/

---

**Last Updated**: 2025-12-05
**For Human Developers**: See `CLAUDE.md` for development guidance
**Documentation Index**: See `CLAUDE.md` for complete documentation reference
