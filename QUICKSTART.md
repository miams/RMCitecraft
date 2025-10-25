# RMCitecraft - Quick Start Guide

## Prerequisites

- macOS 12+ (Apple Silicon M1/M2/M3 or Intel)
- UV package manager installed

## Installation

### 1. Install UV (if not already installed)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# Restart your shell or run: source ~/.bashrc (or ~/.zshrc)
```

### 2. Clone or Navigate to Project
```bash
cd /path/to/RMCitecraft
```

### 3. Install Dependencies
```bash
# UV will automatically create virtual environment and install dependencies
uv sync
```

### 4. Configure Environment
```bash
# Copy example config (if not already done)
cp config/.env.example .env

# Edit .env with your settings
# Required: RM_DATABASE_PATH (path to your .rmtree file)
# Optional: API keys for LLM providers
```

## Running Tests

### Run All Unit Tests
```bash
uv run pytest tests/unit/ -v
```

### Run Database Connection Test
```bash
uv run python test_db_connection.py
```

### Run with Coverage
```bash
uv run pytest tests/unit/ --cov=rmcitecraft --cov-report=html
# View coverage report: open htmlcov/index.html
```

## Running the Application

### Start the Web UI (Week 1 - Basic)
```bash
uv run python -m rmcitecraft.main
```

Then open your browser to: http://localhost:8080

### Run Parser/Formatter Test
```bash
uv run python -c "
from rmcitecraft.parsers.familysearch_parser import FamilySearchParser
from rmcitecraft.parsers.citation_formatter import CitationFormatter

parser = FamilySearchParser()
formatter = CitationFormatter()

source_name = 'Fed Census: 1900, Ohio, Noble [citing sheet 3B, family 57] Ijams, Ella'
familysearch_entry = '\"United States Census, 1900,\" database with images, *FamilySearch* (https://familysearch.org/ark:/61903/1:1:MM6X-FGZ : accessed 24 July 2015), Ella Ijams, Olive Township Caldwell village, Noble, Ohio, United States; citing sheet 3B, family 57, NARA microfilm publication T623 (Washington, D.C.: National Archives and Records Administration, n.d.); FHL microfilm 1,241,311.'

citation = parser.parse(source_name, familysearch_entry, citation_id=1)
footnote, short_footnote, bibliography = formatter.format(citation)

print('=== FOOTNOTE ===')
print(footnote)
print('\n=== SHORT FOOTNOTE ===')
print(short_footnote)
print('\n=== BIBLIOGRAPHY ===')
print(bibliography)
"
```

## Development Commands

### Code Formatting
```bash
uv run ruff format .
```

### Linting
```bash
uv run ruff check .
```

### Type Checking
```bash
uv run mypy src/rmcitecraft
```

### Add New Dependency
```bash
# Runtime dependency
uv add <package-name>

# Development dependency
uv add --dev <package-name>
```

## Project Structure

```
RMCitecraft/
├── src/rmcitecraft/           # Main application code
│   ├── config/                # Configuration
│   ├── models/                # Data models
│   ├── repositories/          # Database access
│   ├── parsers/               # Citation parsing/formatting
│   └── main.py                # Application entry point
├── tests/                     # Test suite
├── data/                      # Sample database
├── sqlite-extension/          # ICU extension for RMNOCASE
└── logs/                      # Application logs
```

## Common Tasks

### Query Citations from Database
```python
from rmcitecraft.repositories import DatabaseConnection, CitationRepository

db = DatabaseConnection()
repo = CitationRepository(db)

# Get all census years
years = repo.get_all_census_years()
print(f"Census years: {years}")

# Get citations for 1900
citations = repo.get_citations_by_year(1900)
print(f"Found {len(citations)} citations for 1900")

db.close()
```

### Parse and Format a Citation
```python
from rmcitecraft.parsers.familysearch_parser import FamilySearchParser
from rmcitecraft.parsers.citation_formatter import CitationFormatter

parser = FamilySearchParser()
formatter = CitationFormatter()

# Your source name and FamilySearch entry here
source_name = "Fed Census: 1900, Ohio, Noble..."
familysearch_entry = "\"United States Census, 1900,\"..."

citation = parser.parse(source_name, familysearch_entry, citation_id=1)
footnote, short_footnote, bibliography = formatter.format(citation)
```

## Troubleshooting

### Database Connection Errors
- Verify `RM_DATABASE_PATH` in `.env` points to valid .rmtree file
- Check that `sqlite-extension/icu.dylib` exists
- Test with: `uv run python test_db_connection.py`

### Import Errors
- Make sure you're running commands with `uv run`
- Verify virtual environment is activated: `source .venv/bin/activate`

### Test Failures
- Check that all dependencies are installed: `uv sync`
- Review log files in `logs/` directory
- Run with verbose output: `pytest -vv`

## Getting Help

- Review `CLAUDE.md` for detailed development guidance
- Check `PRD.md` for project requirements
- See `docs/archive/WEEK1-SUMMARY.md` for what's been completed
- Examine test files for usage examples

## Week 1 Status

✅ All foundation tasks complete:
- Project structure and configuration
- Database connection with RMNOCASE
- Citation parser (1790-1950)
- Citation formatter (Evidence Explained)
- 18 unit tests passing
- Basic NiceGUI application

**Ready for Week 2: Citation Manager UI**
