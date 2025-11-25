# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Note**: For AI coding agents, see AGENTS.md for machine-readable instructions, explicit do's/don'ts, and standardized commands. This file is optimized for Claude Code specifically.
@AGENTS.md

## Project Overview

**RMCitecraft** is a macOS desktop application that automates citation formatting and image management for US Federal census records in RootsMagic genealogy databases.

### Core Functionality
1. **Citation Transformation**: Converts FamilySearch placeholder citations into *Evidence Explained* compliant format
2. **Image Management**: Automatically processes, renames, organizes, and links downloaded census images to the RootsMagic database

### Target Environment
- Platform: macOS (Apple Silicon M3 Pro)
- Database: RootsMagic 8/9 (SQLite)
- Language: Python 3.11+
- UI Framework: NiceGUI 3.0+ (native mode)

### Python and Package Management

**UV Package Manager** is required for all Python and dependency management in this project.

**Installation (macOS):**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Why UV:**
- Fast, reliable Python package and project manager
- Replaces pip, pip-tools, pipx, poetry, pyenv, virtualenv
- 10-100x faster than pip
- Built-in virtual environment management
- Deterministic dependency resolution with uv.lock

**Documentation:** https://docs.astral.sh/uv/

## Current Project State

This is an **active, implemented application** with the following capabilities:

### Implemented Features
- **Census Batch Processing**: Automated extraction and formatting of census citations (1790-1950) with FamilySearch browser automation, 6-phase robust processing (health check → duplicate check → extraction → image download → status update → checkpoint)
- **Find a Grave Batch Processing**: Automated processing of Find a Grave citations with image downloads and primary photo assignment
- **Dashboard**: Real-time analytics with session management, status distributions, performance metrics, and error analysis
- **Citation Validation**: `FormattedCitationValidator` for validating footnote, short footnote, and bibliography against Evidence Explained standards
- **Browser Automation**: Chrome DevTools Protocol integration for FamilySearch and Find a Grave page interaction
- **Image Management**: Automatic download, renaming, and database linking of census/grave images
- **State Persistence**: SQLite-based batch state tracking with crash recovery and session resume

### Repository Contents
- Complete source code in `src/rmcitecraft/`
- Comprehensive test suite (unit, integration, e2e) in `tests/`
- Sample RootsMagic database: `data/Iiams.rmtree`
- RootsMagic schema documentation in `docs/reference/`

## Command-Line Interface (CLI)

RMCitecraft provides a standard CLI for managing the application lifecycle.

### CLI Commands

```bash
# Show help and available commands
rmcitecraft help

# Show version and last updated timestamp
rmcitecraft version

# Check application status
rmcitecraft status

# Start in foreground mode (interactive)
rmcitecraft start

# Start in background mode (daemon)
rmcitecraft start -d
# or
rmcitecraft start --daemon

# Stop the running application
rmcitecraft stop

# Restart (stop + start in background)
rmcitecraft restart
```

### Version Information

All commands that start the application (`start`, `status`) display:
- **Version number** (from pyproject.toml)
- **Last updated timestamp** (most recent file modification in src/)
- **Development/release status**

Example output:
```
RMCitecraft v0.1.0 (development)
Last updated: 2025-10-25 16:59:28
```

### Process Management

- **PID File**: Stored at `~/.rmcitecraft/rmcitecraft.pid`
- **Daemon Mode**: Application runs in background, detached from terminal
- **Foreground Mode**: Application runs interactively, stops with Ctrl+C
- **Process Tracking**: CLI automatically detects running instances and prevents duplicate launches

### Implementation Details

**Key Modules:**
- `src/rmcitecraft/cli.py` - CLI command handlers
- `src/rmcitecraft/daemon.py` - Process management and PID file operations
- `src/rmcitecraft/version.py` - Version information and timestamp tracking
- `src/rmcitecraft/__main__.py` - Entry point (delegates to CLI)

**Testing:**
- Unit tests: `tests/unit/test_cli.py`, `tests/unit/test_daemon.py`, `tests/unit/test_version.py`
- Coverage: 79% for CLI, 53% for daemon, 80% for version module

## RootsMagic Database Architecture

### Critical Tables for This Application

**CitationTable** - Store census citations
- `CitationID` (PK)
- `SourceID` (FK to SourceTable)
- `ActualText` - FamilySearch entry (input)
- `RefNumber` - FamilySearch ARK URL
- `Footnote` - Generated *Evidence Explained* format (output)
- `ShortFootnote` - Generated short form (output)
- `Bibliography` - Generated bibliography (output)
- `CitationName` - Citation display name

**SourceTable** - Master sources
- `SourceID` (PK)
- `Name` - Source name pattern: "Fed Census: YYYY, State, County [details] Surname, GivenName"

**MultimediaTable** - Census images
- `MediaID` (PK)
- `MediaType` - 1=Image, 2=File, 3=Sound, 4=Video
- `MediaPath` - Relative path (symbols: ?=Media Folder, ~=Home, *=Database folder)
- `MediaFile` - Filename
- `Caption` - Auto-generated from census details
- `RefNumber` - FamilySearch ARK URL
- `Date` - Census date

**MediaLinkTable** - Links media to citations/events
- `MediaID` (FK)
- `OwnerType` - 0=Person, 2=Event, 4=Citation
- `OwnerID` - FK to owner table based on OwnerType

**EventTable** - Census events
- `EventID` (PK)
- `EventType` - FK to FactTypeTable (Census = FactTypeID)
- `OwnerID` - PersonID from PersonTable
- `PlaceID` - FK to PlaceTable

### Database Safety Protocol

**Working Copy Architecture:**
- RMCitecraft operates on a database **working copy** located at `/Users/miams/Code/RMCitecraft/data/`
- Production database (in RootsMagic's document folder) remains untouched during processing
- Users manually copy the updated working database back to production when satisfied with results
- Census images are written directly to final locations in `~/Genealogy/RootsMagic/Files/Records - Census/`

**Write Safety Measures:**
- Always use `DatabaseConnection.transaction()` context manager for all database writes
- Check if RootsMagic is running before write operations (warn user if detected)
- Log all database modifications with timestamps
- Validate database schema version before operations
- Use atomic transactions to ensure all-or-nothing updates (no partial/corrupt citations)
- Validate data completeness before writing (missing required fields = validation error)
- Database connection defaults to `read_only=True` for safety, but batch export uses `read_only=False`

## Citation Formatting Rules

### Input Format (FamilySearch)
```
RM Source Name: Fed Census: 1900, Ohio, Noble [citing sheet 3B, family 57] Ijams, Ella
RM Family Search Entry: "United States Census, 1900," database with images, *FamilySearch* (https://familysearch.org/ark:/61903/1:1:MM6X-FGZ : accessed 24 July 2015), Ella Ijams, Olive Township Caldwell village, Noble, Ohio, United States; citing sheet 3B, family 57, NARA microfilm publication T623 (Washington, D.C.: National Archives and Records Administration, n.d.); FHL microfilm 1,241,311.
```

### Output Format (*Evidence Explained*)

**Footnote (1900-1950):**
```
1900 U.S. census, Noble County, Ohio, population schedule, Olive Township Caldwell village, enumeration district (ED) 95, sheet 3B, family 57, Ella Ijams; imaged, "1900 United States Federal Census," <i>FamilySearch</i> (https://familysearch.org/ark:/61903/1:1:MM6X-FGZ : accessed 24 July 2015).
```

**Short Footnote:**
```
1900 U.S. census, Noble Co., Oh., pop. sch., Olive Township, E.D. 95, sheet 3B, Ella Ijams.
```

**Bibliography:**
```
U.S. Ohio. Noble County. 1900 U.S Census. Population Schedule. Imaged. "1900 United States Federal Census". <i>FamilySearch</i> https://www.familysearch.org/ark:/61903/1:1:MM6X-FGZ : 2015.
```

### Template Variations by Census Year
- **1790-1840**: No ED, no population schedule terminology
- **1850-1880**: Population schedule, page/sheet, dwelling/family.
- **1880**: Enumeration District (ED) introduced.  Required for citations.
- **1890**: Most records destroyed in fire.
- **1900-1950**: Population schedule with ED, sheet, family number

### Special Schedules
- Slave Schedules (1850, 1860)
- Mortality Schedules (1850-1885)
- Veterans and Widows Schedule (1890)
- State Census (various states/years)

## File Naming and Organization

### Census Image Filename Pattern
```
YYYY, State, County - Surname, GivenName.ext
```

Examples:
- `1940, Texas, Milam - Iiams, Frank W..jpg`
- `1940, Washington, Clark - Iams, Elizabeth.jpg`

### Census Directory Structure
```
/Users/miams/Genealogy/RootsMagic/Files/Records - Census/
├── 1790 Federal/
├── 1800 Federal/
├── ...
├── 1900 Federal/
├── 1910 Federal/
├── ...
├── 1950 Federal/
├── 1850 Federal Slave Schedule/
├── 1860 Federal Slave Schedule/
├── 1890 Federal Veterans and Widows Schedule/
└── Federal Mortality Schedule 1850-1885/
    ├── 1850 Mortality/
    ├── 1860 Mortality/
    ├── 1870 Mortality/
    └── 1880 Mortality/
```

## Development Workflow

### When Implementing Citation Parsing (LLM-Based Architecture)

**Two-Phase Approach:**

#### Phase 1: LLM Extraction (with Missing Data Detection)
1. **Input**:
   - RM Source Name (from `SourceTable.Name`)
   - RM FamilySearch Entry (from `CitationTable.ActualText`)

2. **LLM Processing**:
   - Use structured output (Pydantic model) to extract all citation components
   - Cached prompt context (system instructions, examples, templates)
   - Only the citation text changes per query
   - LLM identifies missing required fields based on census year

3. **Output** (Pydantic Model):
   ```python
   class CitationExtraction(BaseModel):
       year: int
       state: str
       county: str
       person_name: str
       town_ward: str | None = None
       enumeration_district: str | None = None
       sheet: str | None = None
       family_number: str | None = None
       dwelling_number: str | None = None
       familysearch_url: str
       access_date: str
       nara_publication: str | None = None
       fhl_microfilm: str | None = None
       missing_fields: list[str] = []  # Fields LLM couldn't extract
       confidence: dict[str, float] = {}  # Per-field confidence scores
   ```

4. **Missing Data Handling**:
   - LLM populates `missing_fields` array with required but unavailable data
   - Example: `["enumeration_district", "family_number"]`
   - App uses this to prompt user in citation generation phase
   - User fills gaps while viewing FamilySearch page side-by-side

#### Phase 2: Template-Based Citation Generation
1. Validate extracted data (Pydantic validation + business rules)
2. Prompt user for any `missing_fields` (with FamilySearch page open)
3. Select template based on census year (1790-1840, 1850-1880, 1900-1950)
4. Apply deterministic template rendering
5. Generate all three forms (Footnote, Short Footnote, Bibliography)

**Key Architectural Points:**
- **LLM does parsing** (handles format variations)
- **Templates do formatting** (ensures consistent output)
- **Validation catches errors** (before user sees results)
- **Two-phase separation** allows user review/correction before final generation

### When Implementing Image Processing
1. Monitor downloads folder using `watchdog` library
2. Detect new image files (JPG, PNG, PDF)
3. Match to active citation context (tracked when user clicks "Download Image")
4. Generate filename using census details from citation
5. Determine destination folder based on census year and schedule type
6. Move and rename file
7. Create `MultimediaTable` record
8. Create `MediaLinkTable` entries linking to citation and event

### When Working with Database

**CRITICAL: Free-Form Citation Architecture**

For free-form sources (TemplateID=0), RootsMagic stores Footnote, ShortFootnote, and Bibliography in **SourceTable.Fields BLOB**, NOT in CitationTable TEXT fields.

**Citation Storage Locations:**
- **SourceTable.Fields BLOB** (TemplateID=0): Footnote, ShortFootnote, Bibliography fields (XML)
- **CitationTable.Fields BLOB** (TemplateID=0): "Page" field contains FamilySearch citation text (XML)
- **CitationTable TEXT fields**: Footnote, ShortFootnote, Bibliography (used for template-based sources, TemplateID>0)

**Census Facts are Shared Events:**

Census records in RootsMagic are often **shared facts** (witnesses). The census event is owned by one person (usually head of household) and shared with other household members via the WitnessTable.

**Example: Finding a Person's Census Citations**
```python
# Person may own the event OR be a witness to someone else's event
# Must check both EventTable (owned) and WitnessTable (shared)

# Option 1: Person owns the census event
cursor.execute("""
    SELECT e.EventID, c.CitationID, s.Name
    FROM EventTable e
    JOIN CitationLinkTable cl ON e.EventID = cl.OwnerID AND cl.OwnerType = 2
    JOIN CitationTable c ON cl.CitationID = c.CitationID
    JOIN SourceTable s ON c.SourceID = s.SourceID
    WHERE e.OwnerID = ? AND e.OwnerType = 0 AND e.EventType = 18
""", (person_id,))

# Option 2: Person is a witness to someone else's census event
cursor.execute("""
    SELECT e.EventID, c.CitationID, s.Name
    FROM WitnessTable w
    JOIN EventTable e ON w.EventID = e.EventID
    JOIN CitationLinkTable cl ON e.EventID = cl.OwnerID AND cl.OwnerType = 2
    JOIN CitationTable c ON cl.CitationID = c.CitationID
    JOIN SourceTable s ON c.SourceID = s.SourceID
    WHERE w.PersonID = ? AND e.EventType = 18
""", (person_id,))
```

**Reading Free-Form Citation Fields:**
```python
import xml.etree.ElementTree as ET

# Get citation's source
cursor.execute("""
    SELECT s.SourceID, s.TemplateID, s.Fields, c.Fields
    FROM CitationTable c
    JOIN SourceTable s ON c.SourceID = s.SourceID
    WHERE c.CitationID = ?
""", (citation_id,))

source_id, template_id, source_fields, citation_fields = cursor.fetchone()

if template_id == 0:  # Free-form source
    # Parse SourceTable.Fields for Footnote/ShortFootnote/Bibliography
    root = ET.fromstring(source_fields.decode('utf-8'))
    footnote = root.find('.//Field[Name="Footnote"]/Value').text
    short_footnote = root.find('.//Field[Name="ShortFootnote"]/Value').text
    bibliography = root.find('.//Field[Name="Bibliography"]/Value').text

    # Parse CitationTable.Fields for "Page" (FamilySearch citation)
    root = ET.fromstring(citation_fields.decode('utf-8'))
    familysearch_citation = root.find('.//Field[Name="Page"]/Value').text
```

**Writing Generated Citations (Free-Form Sources):**
```python
# For TemplateID=0, write to SourceTable.Fields BLOB, not CitationTable
xml_content = f"""<Root><Fields>
<Field><Name>Footnote</Name><Value>{footnote}</Value></Field>
<Field><Name>ShortFootnote</Name><Value>{short_footnote}</Value></Field>
<Field><Name>Bibliography</Name><Value>{bibliography}</Value></Field>
</Fields></Root>"""

cursor.execute("""
    UPDATE SourceTable
    SET Fields = ?
    WHERE SourceID = ?
""", (xml_content.encode('utf-8'), source_id))
```

**CRITICAL: RMNOCASE Collation Requirement**

RootsMagic uses a proprietary `RMNOCASE` collation for case-insensitive text sorting. Many fields (Surname, Given, Name, etc.) require this collation. **You must load the ICU extension** before querying the database.

**Database Connection Pattern:**
```python
import sqlite3

def connect_rmtree(db_path, extension_path='./sqlite-extension/icu.dylib'):
    """Connect to RootsMagic database with RMNOCASE collation support."""
    conn = sqlite3.connect(db_path)

    # Load ICU extension and register RMNOCASE collation
    conn.enable_load_extension(True)
    conn.load_extension(extension_path)
    conn.execute(
        "SELECT icu_load_collation('en_US@colStrength=primary;caseLevel=off;normalization=on','RMNOCASE')"
    )
    conn.enable_load_extension(False)

    return conn

# Usage
conn = connect_rmtree('data/Iiams.rmtree')
cursor = conn.cursor()
cursor.execute("SELECT Surname FROM NameTable ORDER BY Surname COLLATE RMNOCASE LIMIT 10")
```

**Key Points:**
1. Always use the ICU extension from `./sqlite-extension/icu.dylib`
2. Load extension at connection time (see `sqlite-extension/python_example.py` for working examples)
3. Fields requiring RMNOCASE: Surname, Given, Name, CitationName, etc.
4. Query example: `ORDER BY Surname COLLATE RMNOCASE`
5. Always check `UTCModDate` field before updates (detect conflicts)
6. For file paths in MediaPath, use symbols:
   - `?` = Media Folder (configured in `.env` as `RM_MEDIA_ROOT_DIRECTORY`)
   - `~` = User's home directory
   - `*` = Folder containing RM database
7. Store relative paths, not absolute
8. **Census citations**: Check both EventTable (owned events) and WitnessTable (shared events)

## Testing Strategy

### Test Organization
```
tests/
├── unit/                    # Fast, isolated tests
│   ├── test_census_batch_state_repository.py  # 43 tests
│   ├── test_formatted_citation_validator.py   # 27 tests
│   ├── test_find_census_citations.py          # 18 tests
│   └── test_database_integrity.py             # Schema validation
├── integration/             # Component interaction tests
│   └── test_census_batch_integration.py       # 18 tests
└── e2e/                     # Browser automation tests
    ├── test_census_analytics.py               # Dashboard validation
    └── test_census_batch_with_downloads.py    # Full workflow
```

### Running Tests
```bash
uv run pytest                           # All tests
uv run pytest tests/unit/ -v            # Unit tests only
uv run pytest tests/e2e/ -v             # E2E tests (requires Chrome)
uv run pytest --cov=src --cov-report=html  # With coverage
```

### Test Database
- Sample database: `data/Iiams.rmtree`
- Contains real genealogy data for testing

### Database Integrity Testing (CRITICAL)

**Why Comparison-Based Testing is Essential:**

When inserting new records into the RootsMagic database, schema validation alone is insufficient. RootsMagic has subtle conventions, undocumented fields, and implicit requirements that can only be discovered by comparing created records with existing records.

**Critical Bugs Caught by Comparison Testing:**
1. **Reverse Field** (99.9% populated, not documented): Tests discovered locations require a reversed hierarchy field ("Country, State, County, City"). Missing this field corrupts the database.
2. **NULL vs 0 for Integer Columns**: RootsMagic requires 0, not NULL, for integer columns (Latitude, Longitude, MasterID, fsID, anID). Schema tests wouldn't catch this.
3. **SortDate is BIGINT**: Field is BIGINT, not INTEGER, despite other ID fields being INTEGER.
4. **Empty Citation Fields for Free-Form Sources**: For TemplateID=0, Footnote/ShortFootnote/Bibliography must be empty in CitationTable (stored in SourceTable.Fields XML instead).

**Methodology: Field-by-Field Comparison**

When implementing database operations for a new record type:

1. **Find Similar Existing Records**:
   ```python
   # Get an existing record of the same type
   cursor.execute("SELECT * FROM PlaceTable WHERE PlaceType = 0 LIMIT 1")
   existing = cursor.fetchone()
   ```

2. **Create Test Record**:
   ```python
   # Use your new function to create a record
   new_place_id = create_location(...)
   cursor.execute("SELECT * FROM PlaceTable WHERE PlaceID = ?", (new_place_id,))
   created = cursor.fetchone()
   ```

3. **Compare Field-by-Field**:
   ```python
   # Compare data types
   assert type(created[0]) == type(existing[0]), "PlaceID types don't match"

   # Compare NULL vs 0 for integers
   assert created[4] is not None, "Latitude should not be NULL"
   assert created[5] is not None, "Longitude should not be NULL"

   # Compare patterns (e.g., Reverse field)
   name = created[10]
   reverse = created[7]
   expected_reverse = ', '.join(reversed([p.strip() for p in name.split(',')]))
   assert reverse == expected_reverse, f"Reverse field pattern incorrect"
   ```

4. **Validate Foreign Keys**:
   ```python
   # Cemetery should reference location
   cursor.execute("SELECT MasterID FROM PlaceTable WHERE PlaceID = ?", (cemetery_id,))
   master_id = cursor.fetchone()[0]
   assert master_id == location_id, "Cemetery MasterID should reference location"
   ```

5. **Test Full Workflow**:
   ```python
   # Create source → citation → event → places → links
   # Verify all relationships are correct
   # Ensure no orphaned records
   ```

**Required Tests for Each New Record Type:**

1. **Schema Tests**: Verify all columns exist with correct types
2. **NULL Tests**: Verify no NULL values in integer columns (use 0 instead)
3. **Pattern Tests**: Compare field patterns with existing records
4. **Foreign Key Tests**: Verify all relationships are valid
5. **Workflow Tests**: Test complete end-to-end creation with all dependencies

**Reference Implementation:**
- See `tests/unit/test_database_integrity.py` for comprehensive examples
- 19 tests covering PlaceTable, SourceTable, CitationTable, EventTable
- Tests caught critical bugs before production deployment

**Test Organization Pattern:**
```python
class TestNewRecordTypeIntegrity:
    """Test that new records match existing RootsMagic patterns."""

    def test_schema_columns(self, db_connection):
        """Verify table has expected columns with correct types."""
        # PRAGMA table_info checks

    def test_no_null_integer_columns(self, db_connection):
        """Verify integer columns use 0, not NULL."""
        # Check existing and created records

    def test_record_matches_existing(self, db_connection):
        """Compare created record field-by-field with existing record."""
        # Field-by-field comparison

    def test_full_workflow(self, db_connection, tmp_path):
        """Test complete creation with all dependencies and links."""
        # End-to-end integration test
```

**When to Run These Tests:**
- **Before every commit** that touches database operations
- **After discovering a new field requirement** (add test to prevent regression)
- **When adding new record types** (sources, citations, events, media, etc.)
- **Before deploying to production** (prevent database corruption)

**Testing Philosophy:**
> "Comparison-based testing reveals what documentation cannot. RootsMagic's database has evolved over 20+ years with subtle conventions that only emerge by studying existing data patterns. A test that compares your created record with an existing record will catch bugs that schema validation alone would miss—potentially months before corruption becomes apparent."

## Key Implementation Considerations

### Citation Parsing with LLM

**Why LLM Instead of Regex:**
- ED format varies: "ED 95", "enumeration district (ED) 214", "E.D. 95"
- Date formats inconsistent: "24 July 2015" vs "Fri Mar 08 08:10:13 UTC 2024"
- Person names complex: "Ella Ijams" vs "William H Ijams in household of Margaret E Brannon"
- Location variations: "Baltimore (Independent City)", "Olive Township Caldwell village"
- FamilySearch changes formats over time

**LLM Provider Configuration:**
- **Configurable**: Cloud (Anthropic, OpenAI, etc.) or Local (Ollama)
- **Multi-Cloud**: Support multiple providers for cost optimization
- **Recommended for quality**: Claude (best at citation understanding)
- **Recommended for cost**: GPT-4o-mini or local Llama 3.1
- **Fallback chain**: Primary → Secondary → Local

**Prompt Caching Strategy:**
- **Cached Context** (reused across all citations):
  - System instructions
  - Few-shot examples (the 2 complete examples from README)
  - Template specifications
  - Field definitions and validation rules
  - Census year variations guide

- **Variable Input** (per citation):
  - RM Source Name
  - RM FamilySearch Entry

- **Implementation**: Use Langchain's caching or provider-specific prompt caching (Claude has built-in prompt caching)
- **Benefit**: Reduces cost/latency by ~90% (only citation text is new tokens)

**Performance Expectations:**
- First citation: 2-3 seconds (cache warming)
- Subsequent citations: 1-2 seconds (cached prompts)
- Batch processing: Process 10-20 in parallel
- Acceptable for user workflow (batch processing with progress bar)

**Structured Output Validation:**
```python
# Pydantic enforces types, ranges, required fields
class CitationExtraction(BaseModel):
    year: int = Field(ge=1790, le=1950, description="Census year")
    state: str = Field(min_length=2, description="US state or territory")
    county: str = Field(min_length=1, description="County name")
    # ... other fields
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Array of required fields that couldn't be extracted"
    )

    @validator('year')
    def validate_census_year(cls, v):
        """Census years are every 10 years: 1790, 1800, ..., 1950"""
        if v % 10 != 0:
            raise ValueError(f"Invalid census year: {v}")
        return v
```

**Missing Data Workflow:**
1. LLM extraction identifies missing required fields
2. App stores `missing_fields` array with citation
3. User proceeds through citations (all parsed in batch)
4. Generation phase prompts for missing data (one citation at a time)
5. User views FamilySearch page while filling gaps
6. App generates final citations with complete data

### File Management Challenges
- Sanitize illegal filename characters: `/ \ : * ? " < > |`
- Handle filename length limits (255 chars)
- Preserve multi-part surnames (e.g., "Van Der Berg")
- Detect partial downloads (ignore .crdownload, .download, .tmp)
- Handle rapid multiple downloads (queue/context matching)

### UI/UX Considerations
- Side-by-side window positioning (app + browser) for missing data entry
- Progress indicators for batch processing
- Preview before applying changes
- Allow manual override of automatic processing
- Clear error messages with suggested actions

### Performance Requirements
- Citation parsing (LLM): 1-2 seconds per citation (acceptable for batch processing)
- Batch LLM processing: 10-20 citations in parallel
- Template rendering: <10ms per citation (deterministic)
- File detection: <2 seconds from download completion
- Database queries: <500ms
- Prompt caching: Reduces LLM latency by ~90% after first citation

## Technology Stack

### Package Management
- **UV** - Python package and project manager (required)
  - Manages virtual environments
  - Handles all dependencies via pyproject.toml
  - Creates deterministic builds with uv.lock

### Core Dependencies
- **NiceGUI** 3.0+ - UI framework with native mode
- **watchdog** 3.0+ - File system monitoring
- **pydantic** 2.0+ - Settings and data validation (also used for structured LLM outputs)
- **loguru** - Logging
- **pytest** 7.0+ - Testing
- **ruff** - Linting/formatting
- **mypy** - Type checking

### LLM Integration (Citation Parsing)
- **langchain-core** - Core LLM orchestration
- **langchain-anthropic** - Claude API integration
- **langchain-openai** - OpenAI/compatible API integration
- **langchain-community** - Additional provider integrations
- **langchain-ollama** - Local LLM support (Ollama)
- **litellm** (optional) - Unified API for cost optimization across providers

**Architecture Decision**: Use LLM for citation parsing instead of rule-based regex parsing due to:
- High variability in FamilySearch citation formats
- Inconsistent field formatting (ED, dates, names)
- Robust handling of edge cases
- Faster development and maintenance

### macOS Integration
- **pywebview** 4.0+ (via NiceGUI native mode)
- **pyobjc** - macOS window positioning via AppleScript

### Packaging
- **PyInstaller** or **py2app** - Create macOS .app bundle

## Project Structure

```
RMCitecraft/
├── config/
│   ├── .env                    # Active configuration (not in git)
│   └── .env.example            # Template configuration
├── data/
│   └── Iiams.rmtree           # Sample RootsMagic database
├── docs/
│   ├── architecture/          # Design docs (LLM-ARCHITECTURE.md, etc.)
│   ├── reference/             # Schema and query documentation
│   └── implementation/        # Implementation notes
├── src/rmcitecraft/
│   ├── config/                # Settings and constants
│   ├── database/              # Database access layer
│   │   ├── connection.py      # ICU extension loading, RMNOCASE
│   │   ├── batch_state_repository.py      # Find a Grave batch state
│   │   └── census_batch_state_repository.py  # Census batch state
│   ├── models/                # Pydantic models (citation, image)
│   ├── services/              # Business logic
│   │   ├── batch_processing.py           # Batch workflow controller
│   │   ├── familysearch_automation.py    # FamilySearch browser automation
│   │   ├── findagrave_automation.py      # Find a Grave automation
│   │   ├── image_processing.py           # Image download/rename
│   │   └── citation_formatter.py         # Evidence Explained formatting
│   ├── ui/
│   │   ├── tabs/              # Main UI tabs (dashboard, batch_processing)
│   │   └── components/        # Reusable UI components
│   │       └── dashboard/     # Dashboard widgets
│   ├── validation/            # Citation validation
│   │   └── data_quality.py    # FormattedCitationValidator
│   ├── cli.py                 # CLI commands
│   └── main.py                # Application entry point
├── sqlite-extension/
│   └── icu.dylib              # SQLite ICU extension (macOS)
├── tests/
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   └── e2e/                   # End-to-end tests (browser automation)
├── pyproject.toml             # Project configuration
└── CLAUDE.md                  # This file
```

## Important Files

**Core Configuration:**
- **pyproject.toml** - Project dependencies and tool settings
- **config/.env.example** - Configuration template (copy to `.env`)

**Key Source Files:**
- **src/rmcitecraft/main.py** - Application entry point
- **src/rmcitecraft/services/batch_processing.py** - Batch workflow controller
- **src/rmcitecraft/services/familysearch_automation.py** - FamilySearch browser automation
- **src/rmcitecraft/validation/data_quality.py** - FormattedCitationValidator
- **src/rmcitecraft/database/connection.py** - Database connection with ICU extension

**Documentation:**
- **CLAUDE.md** - Development guidance (this file)
- **AGENTS.md** - Machine-readable instructions for AI agents
- **docs/architecture/LLM-ARCHITECTURE.md** - LLM implementation guide
- **docs/reference/schema-reference.md** - RootsMagic database schema

**Testing:**
- **data/Iiams.rmtree** - Sample RootsMagic database
- **sqlite-extension/python_example.py** - Database connection examples

## Configuration Management

### Environment Variables (.env)

The application uses environment variables for configuration. Copy `config/.env.example` to `.env` in the project root and fill in your values.

**Key Configuration Variables:**

**LLM Provider Settings:**
- `DEFAULT_LLM_PROVIDER` - anthropic, openai, or ollama
- `LLM_TEMPERATURE` - 0.0-1.0 (0.2 recommended for consistent extraction)
- `LLM_MAX_TOKENS` - Max tokens for LLM response (1024 recommended)

**API Keys:**
- `ANTHROPIC_API_KEY` - Claude API key
- `ANTHROPIC_MODEL` - e.g., claude-3-5-sonnet-20250110
- `OPENAI_API_KEY` - OpenAI API key
- `OPENAI_MODEL` - e.g., gpt-4o-mini
- `OLLAMA_BASE_URL` - Local Ollama server URL
- `OLLAMA_MODEL` - e.g., llama3.1:8b

**Database Paths:**
- `RM_DATABASE_PATH` - Path to RootsMagic .rmtree file
- `SQLITE_ICU_EXTENSION` - Path to ICU extension (./sqlite-extension/icu.dylib)
- `RM_MEDIA_ROOT_DIRECTORY` - RootsMagic media folder (replaces `?` in paths)

**Output Settings:**
- `OUTPUT_DIR` - Output directory for generated files
- `EXPORT_DIR` - Export directory for processed data

**Logging:**
- `LOG_LEVEL` - DEBUG, INFO, WARNING, ERROR
- `LOG_FILE` - Main application log file
- `LLM_DEBUG_LOG_FILE` - LLM request/response debug log (logs/llm_debug.jsonl)

**Configuration Loading Pattern:**
```python
from pydantic_settings import BaseSettings

class Config(BaseSettings):
    # LLM Settings
    default_llm_provider: str
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-sonnet-20250110"

    # Database
    rm_database_path: str
    sqlite_icu_extension: str = "./sqlite-extension/icu.dylib"
    rm_media_root_directory: str

    # Logging
    log_level: str = "INFO"
    llm_debug_log_file: str = "logs/llm_debug.jsonl"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Usage
config = Config()
```

## State Abbreviations Reference

When generating short footnotes, use standard 2-letter state abbreviations (e.g., Oh. for Ohio, Md. for Maryland). County names are abbreviated as "Co." in short footnotes.

## LLM Configuration and Cost Management

### Provider Configuration (Multi-Cloud Strategy)
```python
# User-configurable in settings
LLM_PROVIDER = "anthropic"  # or "openai", "ollama", "litellm"
LLM_MODEL = "claude-3-5-sonnet-20241022"  # or "gpt-4o-mini", "llama3.1:8b"
LLM_FALLBACK_CHAIN = ["anthropic", "openai", "ollama"]
USE_PROMPT_CACHING = True
```

### Cost Estimates (per citation)
- **Claude Sonnet 3.5**: ~$0.0015/citation (recommended for quality)
- **GPT-4o-mini**: ~$0.0002/citation (budget option)
- **Local Ollama (Llama 3.1)**: $0/citation (slower, offline)
- **With prompt caching**: Reduce costs by ~75-90%

### Cost Optimization Strategies
1. **Prompt Caching**: Cache system instructions, examples, templates
2. **Multi-Cloud**: Let user choose provider based on cost/quality preference
3. **Batch Processing**: Amortize overhead across multiple citations
4. **Local Fallback**: Use Ollama for offline or high-volume processing
5. **Smart Routing**: Use litellm to automatically route to cheapest provider

### Example Cost Scenarios
- Process 100 citations (Claude Sonnet): ~$0.15
- Process 1000 citations (Claude Sonnet): ~$1.50
- Process 1000 citations (GPT-4o-mini): ~$0.20
- Process unlimited (Ollama local): $0

**Recommendation**: Default to Claude Sonnet for quality, allow user to switch to GPT-4o-mini or Ollama for cost savings.

## Implementation Guidance

### LLM Extraction Service Structure
```python
# services/llm_citation_extractor.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

class CitationExtractor:
    def __init__(self, provider: str, model: str, use_caching: bool):
        self.llm = self._create_llm(provider, model)
        self.prompt = self._build_cached_prompt()

    def _build_cached_prompt(self):
        """Build prompt with cached context (system + examples)"""
        # System instructions (cached)
        # Few-shot examples (cached)
        # Template guide (cached)
        # Variable: citation text (not cached)

    async def extract_citation(
        self,
        source_name: str,
        familysearch_entry: str
    ) -> CitationExtraction:
        """Extract structured data from FamilySearch citation"""
        # LLM call with structured output
        # Returns Pydantic model with missing_fields populated

    def detect_missing_fields(
        self,
        extraction: CitationExtraction,
        census_year: int
    ) -> list[str]:
        """Identify required fields based on census year"""
        # 1790-1840: No ED required
        # 1850-1880: No ED required
        # 1900-1950: ED required
```

### Two-Phase Processing Flow
```python
# Phase 1: Batch Extraction
async def process_citations_batch(citations: list[Citation]):
    """Process multiple citations in parallel"""
    tasks = [
        extractor.extract_citation(c.source_name, c.familysearch_entry)
        for c in citations
    ]
    extractions = await asyncio.gather(*tasks)
    return extractions

# Phase 2: Generation (one at a time with user input)
def generate_citation_with_user_input(
    extraction: CitationExtraction,
    user_supplied_data: dict[str, str]
):
    """Merge LLM extraction + user input, then generate citation"""
    # Fill in missing_fields with user data
    # Validate complete data
    # Apply year-appropriate template
    # Generate Footnote, ShortFootnote, Bibliography
```

## Getting Started

### Initial Setup

1. **Install UV package manager** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   # Restart your shell or run: source ~/.bashrc (or ~/.zshrc)
   ```

2. **Setup direnv for automatic environment activation (recommended):**
   ```bash
   # Install direnv
   brew install direnv

   # Add to your shell config (~/.zshrc)
   echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
   source ~/.zshrc

   # Allow direnv for this project
   direnv allow
   ```

   Alternatively, manually activate the virtual environment:
   ```bash
   # Create virtual environment (uses Python 3.11+)
   uv venv

   # Activate virtual environment
   source .venv/bin/activate
   ```

3. **Install project dependencies:**
   ```bash
   # Install all dependencies (runtime + development)
   uv sync

   # Or install only runtime dependencies
   uv sync --no-dev
   ```

4. **Install optional dependencies:**
   ```bash
   # For packaging macOS app bundles
   uv sync --extra packaging

   # For cost optimization with multiple LLM providers
   uv sync --extra cost-optimization

   # Install all extras
   uv sync --all-extras
   ```

5. **Copy configuration template:**
   ```bash
   cp config/.env.example .env
   # Edit .env with your API keys and paths

   # With direnv installed, environment variables will automatically load
   # when you cd into the project directory
   ```

6. **Test database connection:**
   ```bash
   # Run with UV (automatically uses virtual environment)
   uv run python sqlite-extension/python_example.py

   # Or if already activated
   python sqlite-extension/python_example.py
   ```
   This will verify:
   - ICU extension loads correctly
   - RMNOCASE collation works
   - Sample database is accessible
   - Example queries execute properly

7. **Verify configuration:**
   - Check `RM_DATABASE_PATH` points to your .rmtree file
   - Verify `SQLITE_ICU_EXTENSION` path is correct
   - Set `RM_MEDIA_ROOT_DIRECTORY` to your RootsMagic media folder
   - Configure at least one LLM provider (API key)

8. **Review documentation:**
   - Read `docs/architecture/LLM-ARCHITECTURE.md` for LLM implementation details
   - Review `docs/database/how-to-use-extension.md` for database connection patterns
   - Study `docs/reference/schema-reference.md` for database schema

### Common UV Commands

**Managing Dependencies:**
```bash
# Install/update all dependencies
uv sync

# Add a new runtime dependency
uv add <package-name>

# Add a development dependency
uv add --dev <package-name>

# Remove a dependency
uv remove <package-name>

# Update all dependencies
uv sync --upgrade

# List installed packages
uv pip list
```

**Running Commands:**
```bash
# Run Python scripts
uv run python script.py

# Run tests
uv run pytest

# Run type checking
uv run mypy src/

# Run linting
uv run ruff check .

# Format code
uv run ruff format .
```

**Python Version Management:**
```bash
# UV automatically downloads and uses Python 3.11+ if needed
# No need to manually install Python with pyenv, asdf, etc.

# Pin specific Python version (if needed)
uv venv --python 3.11
```

**Lock File:**
- UV automatically generates `uv.lock` when you run `uv sync`
- This file ensures reproducible builds
- Commit `uv.lock` to version control
- Team members running `uv sync` get identical dependencies

### Development Workflow

1. **Phase 1 - Foundation**: Database access and LLM integration
2. **Phase 2 - Citation Parsing**: Implement LLM extraction with structured output
3. **Phase 3 - Template Rendering**: Generate Evidence Explained citations
4. **Phase 4 - UI Integration**: Build NiceGUI interface
5. **Phase 5 - Image Management**: Implement file monitoring and processing

**See PRD.md Section 7 for complete development phase breakdown.**

## Notes

- This application is read-heavy (queries) but write-sensitive (database integrity)
- **Always load ICU extension** for RMNOCASE collation support
- All database writes must be atomic and logged
- User approval required before modifying database
- Support for state census (non-federal) is Phase 7 enhancement
- Consider implementing undo capability for database changes
- LLM extraction is cached/reusable; template rendering is deterministic
- Multi-cloud LLM strategy allows cost optimization and offline fallback
- **Security**: Never commit `.env` file with API keys to version control
- **Testing**: Use `sqlite-extension/python_example.py` as reference for database operations
