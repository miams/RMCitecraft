---
priority: archive
topics: [database, census, citation, batch, findagrave]
---

# GEMINI.md

This document provides a comprehensive overview of the RMCitecraft project, its architecture, and development conventions to be used as a guide for future interactions.

## Project Overview

RMCitecraft is a Python-based desktop application designed to automate citation formatting and image management for the RootsMagic genealogy software. It primarily targets US Federal Census (1790-1950) and Find a Grave records. The application provides a user-friendly interface built with NiceGUI to streamline the process of creating *Evidence Explained* compliant citations and organizing associated images.

The core value proposition is to save genealogists significant time and effort by automating tedious manual tasks, such as reformatting citations, renaming image files, and linking media to records within the RootsMagic database.

## Architecture

RMCitecraft is built on a modern Python stack and employs a service-oriented architecture.

*   **Frontend:** The user interface is a web-based UI powered by **NiceGUI** (native mode). The UI is structured into tabs for different functionalities like batch processing and citation management.
*   **Backend:** Python 3.11+ handles core logic, database interactions, and browser automation.
*   **Database:** The application directly interacts with **SQLite** databases (RootsMagic 8/9 format).
    *   **CRITICAL:** Uses the ICU extension for `RMNOCASE` collation.
    *   **State Persistence:** Application state is saved to `~/.rmcitecraft/batch_state.db` for crash recovery.
*   **Browser Automation:** **Playwright** is used to extract data from websites like FamilySearch and Find a Grave.
*   **LLM Integration:** **LangChain** integrates LLMs (Claude, GPT, Ollama) for intelligent citation parsing.
*   **Asynchronous Operations:** Extensive use of `asyncio` for non-blocking I/O and web automation.

### Robustness Features
*   **Adaptive Timeouts:** Dynamic adjustments for unreliable network connections.
*   **Page Health Monitoring:** Detects and recovers from browser crashes.
*   **Atomic Transactions:** Ensures database integrity during batch writes.

## Critical Protocols

### 1. Database Safety
*   **Working Copy:** Operations must be performed on a working copy (e.g., `data/Iiams.rmtree`), NEVER on the production database.
*   **RMNOCASE Collation:** You **must** load the ICU extension before querying the database.
    ```python
    from src.rmcitecraft.database.connection import connect_rmtree
    conn = connect_rmtree('data/Iiams.rmtree')  # Loads ICU extension automatically
    ```
*   **Free-Form Citations:** For census citations, RootsMagic stores data in the **SourceTable.Fields BLOB**, not CitationTable TEXT fields.
*   **Shared Events:** Census records are often shared via `WitnessTable`. Check both `EventTable` and `WitnessTable`.

### 2. Citation Formatting
*   **Standard:** Output must strictly adhere to *Evidence Explained* format.
*   **Validation:** `FormattedCitationValidator` enforces rules (e.g., `footnote != short_footnote`).
*   **Census Variations:**
    *   1790-1840: Household head only.
    *   1850-1870: Individual, no ED.
    *   1880-1940: ED, sheet, family number.
    *   1950: Uses "stamp" instead of "sheet".

## Key Components

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
│   ├── tabs/              # Main UI tabs (BatchProcessing, CitationManager)
│   └── components/        # Reusable components
├── validation/
│   └── data_quality.py    # FormattedCitationValidator
└── main.py                # Application entry point
```

## Development Setup

1.  **Install UV:** `curl -LsSf https://astral.sh/uv/install.sh | sh`
2.  **Clone:** `git clone <repo_url>` and `cd RMCitecraft`
3.  **Install:** `uv sync`
4.  **Configure:** Copy `config/.env.example` to `.env` and set `RM_DATABASE_PATH`.

## Building and Running

| Command | Description |
|---------|-------------|
| `rmcitecraft start` | Start application (interactive) |
| `rmcitecraft start -d` | Start in background |
| `rmcitecraft status` | Check application status |
| `rmcitecraft stop` | Stop application |
| `uv run python sqlite-extension/python_example.py` | Verify DB connection |

## Development Conventions

### Before Modifying Code
1.  **Read source:** Understand the specific module.
2.  **Check tests:** Look for existing tests in `tests/unit/` and `tests/integration/`.
3.  **Database Ops:** Review `docs/reference/DATABASE_PATTERNS.md` before writing SQL.
4.  **Batch Processing:** Check state schema in `docs/reference/BATCH_STATE_DATABASE_SCHEMA.md`.

### Testing Strategy
*   **Unit Tests (`tests/unit/`):** Fast, isolated logic tests.
*   **Integration Tests (`tests/integration/`):** Component interaction.
*   **E2E Tests (`tests/e2e/`):** Browser automation (requires Chrome).
*   **Database Integrity:** Use comparison-based testing to catch undocumented RootsMagic conventions.

### Code Quality
*   **Lint/Format:** `uv run ruff check . && uv run ruff format .`
*   **Type Check:** `uv run mypy src/`
*   **Test:** `uv run pytest`

## Key Documentation
*   **`CLAUDE.md`**: Primary developer guide and project status.
*   **`AGENTS.md`**: Machine-readable instructions.
*   **`docs/reference/schema-reference.md`**: RootsMagic database schema.
*   **`docs/reference/DATABASE_PATTERNS.md`**: SQL patterns and examples.
*   **`docs/BATCH_PROCESSING_PHASE1_IMPLEMENTATION.md`**: Details on the batch processing UI.
*   **`docs/analysis/`**: In-depth analysis of Census eras and data structures.