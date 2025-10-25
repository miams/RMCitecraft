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
- **LLM Integration**: Multi-provider support (Anthropic Claude, OpenAI, Ollama)
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
- **Follow Evidence Explained** citation formatting rules strictly (see `docs/architecture/LLM-ARCHITECTURE.md`)
- **Use structured output** (Pydantic models) for LLM extraction
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
# Edit .env with your API keys and paths

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
├── models/          # Pydantic models
├── services/        # Business logic (LLM, parser, formatter)
├── database/        # Database access layer
├── ui/              # NiceGUI components
└── utils/           # Shared utilities

tests/
├── unit/            # Unit tests (fast, no I/O)
├── integration/     # Integration tests (DB, LLM)
└── fixtures/        # Test data and fixtures
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

- **Read-only by default** - warn before writes
- **Use transactions** for all write operations
- **Check `UTCModDate`** before updates (detect conflicts)
- **Validate schema version** before operations
- **Never modify without user confirmation**
- **Log all database modifications**

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

### LLM Provider Configuration

- **Multi-provider support**: Allow user choice (cost/quality trade-offs)
- **API key validation** on startup
- **Rate limiting** awareness (respect provider limits)
- **Prompt caching** for cost optimization
- **Local fallback** (Ollama) for offline/high-volume use
- **No hard-coded models** (configurable via `.env`)

---

## Project-Specific Context

### Citation Parsing Complexity

**Challenge**: FamilySearch citation formats vary significantly across:
- Census years (1790-1950, every 10 years)
- Format changes (ED introduced 1880, population schedules 1850+)
- Special schedules (Slave 1850/1860, Mortality 1850-1885, Veterans 1890)

**Solution**: LLM-based extraction (handles variations) + template formatting (ensures consistency)

### Database Schema Constraints

- **RMNOCASE collation**: Required for text fields (case-insensitive sorting)
- **MediaPath symbols**: `?` = Media Folder, `~` = Home, `*` = Database folder
- **FactTypeID mapping**: Census events use dynamic IDs (not hard-coded)
- **XML in Fields BLOB**: Free-form citations (TemplateID=0) store text in XML

### Key Files for Reference

- **`CLAUDE.md`**: Comprehensive development guidance (read first)
- **`docs/architecture/LLM-ARCHITECTURE.md`**: LLM implementation details
- **`docs/reference/schema-reference.md`**: Complete RootsMagic database schema
- **`docs/database/how-to-use-extension.md`**: ICU extension usage patterns
- **`sqlite-extension/python_example.py`**: Working database connection examples
- **`PRD.md`**: Complete product requirements and architecture

---

## Common Tasks

### Query Citations from Database

```python
from src.rmcitecraft.database.connection import connect_rmtree

# Always load ICU extension first
conn = connect_rmtree('data/Iiams.rmtree')
cursor = conn.cursor()

# Use RMNOCASE for text comparisons
cursor.execute("""
    SELECT CitationID, SourceID, ActualText
    FROM CitationTable
    WHERE CitationName COLLATE RMNOCASE LIKE ?
""", ('%1900%',))
```

### Parse and Format Citation

```python
from src.rmcitecraft.services.parser import parse_familysearch_citation
from src.rmcitecraft.services.formatter import format_evidence_explained

# Phase 1: Extract with LLM
extraction = parse_familysearch_citation(
    source_name="Fed Census: 1900, Ohio, Noble [citing sheet 3B, family 57] Ijams, Ella",
    familysearch_entry="...",
)

# Phase 2: Format with template
footnote, short_footnote, bibliography = format_evidence_explained(extraction)
```

### Run UI in Native Mode

```python
# Recommended for macOS
uv run python src/rmcitecraft/main.py --native

# Web mode (for testing)
uv run python src/rmcitecraft/main.py --web
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

**"LLM parsing returns incomplete data"**
- **Cause**: Citation format variation not in training examples
- **Fix**: Check `missing_fields` array in extraction result
- **Solution**: Prompt user to fill gaps or add example to training set

**"Citation formatting incorrect"**
- **Cause**: Using wrong template for census year
- **Fix**: Verify year detection and template selection logic
- **Reference**: `docs/architecture/LLM-ARCHITECTURE.md` for templates

---

## Additional Resources

- **UV Documentation**: https://docs.astral.sh/uv/
- **NiceGUI Documentation**: https://nicegui.io/
- **Ruff Documentation**: https://docs.astral.sh/ruff/
- **Evidence Explained**: Mills, Elizabeth Shown. *Evidence Explained* (citation style guide)
- **RootsMagic**: https://rootsmagic.com/
- **FamilySearch**: https://familysearch.org/

---

**Last Updated**: 2025-10-25
**For Human Developers**: See `CLAUDE.md` for comprehensive development guidance
**For Questions**: Review `claude_code_docs_map.md` for complete documentation index
