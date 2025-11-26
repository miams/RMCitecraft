# CLAUDE.md

Project guidance for Claude Code. For machine-readable instructions, see [AGENTS.md](AGENTS.md).

## Quick Reference

```bash
# Start application
uv run python src/rmcitecraft/main.py

# Run tests
uv run pytest                              # All tests
uv run pytest tests/unit/ -v               # Unit tests only
uv run pytest tests/e2e/ -v                # E2E tests (requires Chrome)
uv run pytest --cov=src --cov-report=html  # With coverage

# Code quality
uv run ruff check . && uv run ruff format . && uv run mypy src/

# Verify database connection
uv run python sqlite-extension/python_example.py

# CLI commands
rmcitecraft start      # Start in foreground
rmcitecraft start -d   # Start as daemon
rmcitecraft stop       # Stop application
rmcitecraft status     # Check status
```

## Project Overview

**RMCitecraft** automates citation formatting and image management for US Federal census records in RootsMagic genealogy databases.

| Aspect | Details |
|--------|---------|
| Platform | macOS (Apple Silicon) |
| Language | Python 3.11+ |
| Package Manager | UV (required) |
| UI Framework | NiceGUI 3.0+ (native mode) |
| Database | RootsMagic 8/9 (SQLite) |

### Core Features

- **Census Batch Processing**: Browser automation extracts FamilySearch data, formats *Evidence Explained* citations
- **Find a Grave Processing**: Automated memorial data extraction with image downloads
- **Citation Validation**: `FormattedCitationValidator` validates against Evidence Explained standards
- **State Persistence**: SQLite-based crash recovery at `~/.rmcitecraft/batch_state.db`
- **Dashboard**: Real-time analytics, session management, error analysis

## Before Modifying Code

1. **Read the source file(s)** you plan to modify
2. **Check for existing tests** in `tests/unit/` and `tests/integration/`
3. **For database operations**: Review [schema-reference.md](docs/reference/schema-reference.md) and [DATABASE_PATTERNS.md](docs/reference/DATABASE_PATTERNS.md)
4. **For batch processing**: Check state in `~/.rmcitecraft/batch_state.db`
5. **Run affected tests** before committing: `uv run pytest tests/unit/test_<module>.py -v`

## Project Structure

```
src/rmcitecraft/
├── config/                # Settings (settings.py)
├── database/              # Database access layer
│   ├── connection.py                    # ICU extension, RMNOCASE
│   ├── batch_state_repository.py        # Find a Grave state
│   └── census_batch_state_repository.py # Census state
├── services/              # Business logic
│   ├── batch_processing.py              # Workflow controller
│   ├── familysearch_automation.py       # FamilySearch browser automation
│   ├── findagrave_automation.py         # Find a Grave automation
│   └── citation_formatter.py            # Evidence Explained formatting
├── ui/
│   ├── tabs/              # Main UI tabs
│   └── components/        # Reusable components
├── validation/
│   └── data_quality.py    # FormattedCitationValidator
└── main.py                # Entry point

tests/
├── unit/                  # Fast, isolated tests
├── integration/           # Component interaction tests
└── e2e/                   # Browser automation tests
```

## Critical: Database Safety

### Working Copy Architecture

- RMCitecraft operates on a **working copy** at `data/Iiams.rmtree`
- Production database remains untouched during processing
- Users manually copy back to production when satisfied
- Census images write directly to `~/Genealogy/RootsMagic/Files/Records - Census/`

### RMNOCASE Collation (Required)

**Always load ICU extension before querying.** Many fields (Surname, Given, Name) require RMNOCASE collation.

```python
from src.rmcitecraft.database.connection import connect_rmtree
conn = connect_rmtree('data/Iiams.rmtree')  # Loads ICU extension automatically
```

See [DATABASE_PATTERNS.md](docs/reference/DATABASE_PATTERNS.md) for connection patterns and SQL examples.

### Free-Form Citations (TemplateID=0)

For census citations, RootsMagic stores Footnote/ShortFootnote/Bibliography in **SourceTable.Fields BLOB**, NOT CitationTable TEXT fields. See [DATABASE_PATTERNS.md](docs/reference/DATABASE_PATTERNS.md#free-form-citation-architecture).

### Census Events are Shared Facts

Census records are often shared via WitnessTable. Always check both owned events (EventTable) AND witnessed events (WitnessTable). See [DATABASE_PATTERNS.md](docs/reference/DATABASE_PATTERNS.md#census-events-shared-facts).

## Citation Formatting

### Evidence Explained Format

**Footnote (1900-1950):**
```
1900 U.S. census, Noble County, Ohio, population schedule, Olive Township,
enumeration district (ED) 95, sheet 3B, family 57, Ella Ijams; imaged,
"1900 United States Federal Census," FamilySearch (https://familysearch.org/ark:/...).
```

**Short Footnote:**
```
1900 U.S. census, Noble Co., Oh., pop. sch., Olive Township, E.D. 95, sheet 3B, Ella Ijams.
```

### Template Variations by Census Year

| Years | Format |
|-------|--------|
| 1790-1840 | No ED, no population schedule terminology |
| 1850-1870 | Population schedule, page/sheet, dwelling/family |
| 1880 | ED introduced (required for citations) |
| 1900-1940 | Population schedule with ED, sheet, family number |
| 1950 | Uses "stamp" instead of "sheet" |

### Validation Logic

`FormattedCitationValidator` in `src/rmcitecraft/validation/data_quality.py`:
- **Criterion 5**: `footnote != short_footnote` (different after processing)
- **Criterion 6**: All three forms pass validation (year, census ref, sheet/stamp, ED for 1900+)

## Testing

### Test Organization

| Directory | Purpose | Example |
|-----------|---------|---------|
| `tests/unit/` | Fast, isolated | `test_formatted_citation_validator.py` |
| `tests/integration/` | Component interaction | `test_census_batch_integration.py` |
| `tests/e2e/` | Browser automation | `test_census_batch_with_downloads.py` |

### Database Integrity Testing

When modifying database operations, use comparison-based testing to catch undocumented RootsMagic conventions. See [DATABASE_TESTING.md](docs/reference/DATABASE_TESTING.md) for methodology.

**Key bugs caught by comparison testing:**
- Reverse field (99.9% populated, undocumented)
- NULL vs 0 for integer columns
- SortDate is BIGINT, not INTEGER

## Configuration

Copy `config/.env.example` to `.env` and configure:

```bash
# Required
RM_DATABASE_PATH=./data/Iiams.rmtree
SQLITE_ICU_EXTENSION=./sqlite-extension/icu.dylib
RM_MEDIA_ROOT_DIRECTORY=~/Genealogy/RootsMagic/Files

# Logging
LOG_LEVEL=INFO
```

## Key Files

| File | Purpose |
|------|---------|
| `src/rmcitecraft/main.py` | Application entry point |
| `src/rmcitecraft/services/batch_processing.py` | Batch workflow controller |
| `src/rmcitecraft/services/familysearch_automation.py` | FamilySearch browser automation |
| `src/rmcitecraft/validation/data_quality.py` | Citation validation |
| `src/rmcitecraft/database/connection.py` | Database connection with ICU |
| `sqlite-extension/python_example.py` | Database connection examples |

## Documentation Index

| Document | Content |
|----------|---------|
| [AGENTS.md](AGENTS.md) | Machine-readable do's/don'ts for AI agents |
| [docs/reference/schema-reference.md](docs/reference/schema-reference.md) | RootsMagic database schema |
| [docs/reference/DATABASE_PATTERNS.md](docs/reference/DATABASE_PATTERNS.md) | SQL patterns and examples |
| [docs/reference/DATABASE_TESTING.md](docs/reference/DATABASE_TESTING.md) | Integrity testing methodology |
| [docs/reference/BATCH_STATE_DATABASE_SCHEMA.md](docs/reference/BATCH_STATE_DATABASE_SCHEMA.md) | Batch state database schema |
| [docs/reference/CENSUS_BATCH_PROCESSING_ARCHITECTURE.md](docs/reference/CENSUS_BATCH_PROCESSING_ARCHITECTURE.md) | Census processing workflow |
| [docs/architecture/BATCH_PROCESSING_ARCHITECTURE.md](docs/architecture/BATCH_PROCESSING_ARCHITECTURE.md) | Find a Grave processing |

## Common Tasks

### Adding a New Database Record Type

1. Review existing records: `SELECT * FROM TableName LIMIT 1`
2. Check [schema-reference.md](docs/reference/schema-reference.md) for field definitions
3. Write comparison-based tests (see [DATABASE_TESTING.md](docs/reference/DATABASE_TESTING.md))
4. Use 0 instead of NULL for integer columns
5. Check for undocumented fields (Reverse, SortDate, etc.)

### Modifying Batch Processing

1. Check current implementation in `src/rmcitecraft/services/batch_processing.py`
2. Review state schema in [BATCH_STATE_DATABASE_SCHEMA.md](docs/reference/BATCH_STATE_DATABASE_SCHEMA.md)
3. Run existing tests: `uv run pytest tests/unit/test_*batch*.py -v`
4. Test with real data using sample database

### Updating Citation Validation

1. Review `FormattedCitationValidator` in `src/rmcitecraft/validation/data_quality.py`
2. Check year-specific rules (1950 uses "stamp", 1900+ requires ED)
3. Run validation tests: `uv run pytest tests/unit/test_formatted_citation_validator.py -v`

## Notes

- **Read-heavy, write-sensitive**: All database writes must be atomic and logged
- **User approval required** before modifying database
- **Always load ICU extension** for RMNOCASE collation
- **Never commit `.env`** with secrets to version control

## Evolving This File

This file loads with every Claude Code conversation. Keep it concise:

- **Add instructions you repeat** using `#` during conversations
- **Move detailed content** to reference docs in `docs/`
- **Remove theoretical content** that doesn't reflect actual practice
- **Update when implementation changes** to stay accurate

---

*Last updated: 2025-11-26*
