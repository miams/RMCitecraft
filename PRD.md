---
priority: essential
topics: [database, census, citation, batch, testing]
---

# Product Requirements Document
## RMCitecraft
### RootsMagic Census Citation Assistant

---

## 1. Executive Summary

### 1.1 Project Overview
RMCitecraft is a desktop application for macOS that enhances the genealogy research workflow by automating citation formatting and image management for US Federal census records stored in RootsMagic databases.

### 1.2 Problem Statement
Genealogy researchers using RootsMagic face two time-consuming manual tasks:
1. Converting FamilySearch placeholder citations into proper *Evidence Explained* compliant format
2. Managing downloaded census images (renaming, organizing, and linking to database records)

### 1.3 Solution
A native macOS desktop application that:
- Automatically transforms FamilySearch citations into *Evidence Explained* format
- Provides intelligent prompts for missing citation data with contextual web assistance
- Monitors downloads folder for census images
- Automatically processes, renames, organizes, and links images to RootsMagic database

### 1.4 Target Platform
- macOS (Apple Silicon M3 Pro and compatible)
- RootsMagic 8/9 (SQLite database format)

### 1.5 Success Metrics
- Reduce citation formatting time from 5+ minutes to <30 seconds per citation
- Eliminate manual file management errors (incorrect naming, wrong folders)
- 100% accuracy in *Evidence Explained* citation formatting
- Zero data loss or corruption in RootsMagic database

---

## 2. User Personas

### Primary User: Genealogy Researcher
- **Name**: Sarah (Representative user)
- **Experience**: Intermediate to advanced genealogy researcher
- **Technical Skill**: Comfortable with desktop applications, basic file management
- **Goals**: Maintain professional-quality research documentation, comply with genealogical standards
- **Pain Points**: Tedious citation reformatting, error-prone file management, context switching between apps

---

## 3. User Stories & Use Cases

### 3.1 Citation Formatting

#### US-1.1: Process Citations in Small Batches
**As a** genealogy researcher
**I want to** select a small batch of census citations to process
**So that** I can test and verify formatting accuracy before processing larger batches

**Acceptance Criteria:**
- User can select citations by year (e.g., all 1900 census citations)
- App displays preview of transformations before applying
- User can review and approve/reject each transformation
- Changes are written to database only after confirmation

#### US-1.2: Batch Process Census Year
**As a** genealogy researcher
**I want to** process all citations from a specific census year
**So that** I can efficiently format all citations for that decade

**Acceptance Criteria:**
- User selects census year from dropdown (1790-1950)
- App scans database for all matching citations
- Progress indicator shows processing status
- Summary report shows: processed count, skipped count, errors

#### US-1.3: Handle Missing Citation Data
**As a** genealogy researcher
**I want to** be prompted for missing data with contextual assistance
**So that** I can complete citations with accurate information

**Acceptance Criteria:**
- App detects missing required fields (e.g., Enumeration District)
- Side-by-side windows: App form + FamilySearch webpage
- Form pre-populates known data
- User inputs missing data while viewing source
- App validates input format

**Workflow:**
1. App identifies citation missing ED number
2. Opens FamilySearch URL in default browser
3. Positions browser and app side-by-side
4. Shows form: "Enumeration District: [___]"
5. User views image, enters "ED 95"
6. App validates format, updates citation

### 3.2 Image Management

#### US-2.1: Monitor Downloads Folder
**As a** genealogy researcher
**I want to** have my downloads automatically monitored
**So that** census images are processed without manual intervention

**Acceptance Criteria:**
- App monitors user-configured folder when running
- Detects new image files (JPG, PNG, PDF)
- Visual indicator shows monitoring status
- No performance impact on system

#### US-2.2: Download Census Image from Active Citation
**As a** genealogy researcher
**I want to** click to download an image and have it automatically processed
**So that** I don't have to manually rename and organize files

**Acceptance Criteria:**
- User clicks "Download Image" button for citation
- App opens FamilySearch URL in browser
- App tracks this citation as "active download context"
- When image downloads, app automatically:
  - Renames using pattern: `YYYY, State, County - Surname, GivenName.jpg`
  - Moves to appropriate census year folder
  - Updates RootsMagic database with media record
  - Links media to citation and person

**Example Workflow:**
1. User viewing citation for "Ella Ijams, 1900 census, Noble County, Ohio"
2. User clicks "Download Image"
3. Browser opens FamilySearch page
4. User downloads image (arbitrary FamilySearch filename)
5. App detects download
6. App renames to: `1900, Ohio, Noble - Ijams, Ella.jpg`
7. App moves to: `/Users/miams/Genealogy/RootsMagic/Files/Records - Census/1900 Federal/`
8. App creates RootsMagic media record with caption
9. App links to citation and census event

#### US-2.3: Handle Multiple Downloads
**As a** genealogy researcher
**I want to** download multiple images in sequence
**So that** I can efficiently process multiple census records

**Acceptance Criteria:**
- App queues downloads if multiple occur
- Each download is matched to correct citation based on download order
- User can review pending downloads before processing
- User can manually override automatic matching if needed

---

## 4. Functional Requirements

### 4.1 Citation Formatting Engine

#### FR-1.1: Parse FamilySearch Citations
**Priority**: P0 (Critical)

**Input Fields:**
- RM Source Name (existing)
- RM FamilySearch Entry (existing)

**Output Fields:**
- RM Footnote (generated)
- RM Short Footnote (generated)
- RM Bibliography (generated)

**Parsing Requirements:**
- Extract year, state, county from source name
- Parse person name, location details from FamilySearch entry
- Extract enumeration district (ED), sheet, family number
- Extract FamilySearch ARK URL
- Extract access date
- Extract NARA publication info (e.g., "T623")
- Extract FHL microfilm number

#### FR-1.2: Citation Templates by Census Year

**1790-1840 Federal Census:**
```
Footnote: [Year] U.S. census, [County] County, [State], [Town/Township], [page/sheet], [name]; imaged, "[Year] United States Federal Census," FamilySearch ([URL] : accessed [date]).

Short: [Year] U.S. census, [County] Co., [State abbrev.], [Town], [page], [name].

Bibliography: U.S. [State]. [County] County. [Year] U.S Census. Imaged. "[Year] United States Federal Census". FamilySearch [URL] : [year].
```

**1850-1880 Federal Census:**
```
Footnote: [Year] U.S. census, [County] County, [State], population schedule, [Town/Township], [page/sheet], [dwelling/family], [name]; imaged, "[Year] United States Federal Census," FamilySearch ([URL] : accessed [date]).

Short: [Year] U.S. census, [County] Co., [State abbrev.], pop. sch., [Town], [page], [name].

Bibliography: U.S. [State]. [County] County. [Year] U.S Census. Population Schedule. Imaged. "[Year] United States Federal Census". FamilySearch [URL] : [year].
```

**1890 Federal Census:**
(Special handling - mostly destroyed)
```
Footnote: [Year] U.S. census, [County] County, [State], population schedule, [Town/Township], enumeration district (ED) [#], sheet [#], [dwelling/family], [name]; imaged, "[Year] United States Federal Census," FamilySearch ([URL] : accessed [date]).
```

**1900-1950 Federal Census:**
```
Footnote: [Year] U.S. census, [County] County, [State], population schedule, [Town/Township/Ward], enumeration district (ED) [#], sheet [#], family [#], [name]; imaged, "[Year] United States Federal Census," FamilySearch ([URL] : accessed [date]).

Short: [Year] U.S. census, [County] Co., [State abbrev.], pop. sch., [Town], E.D. [#], sheet [#], [name].

Bibliography: U.S. [State]. [County] County. [Year] U.S Census. Population Schedule. Imaged. "[Year] United States Federal Census". FamilySearch [URL] : [year].
```

**Special Schedules:**
- Slave Schedules (1850, 1860)
- Mortality Schedules (1850-1885)
- Veterans and Widows Schedule (1890)

#### FR-1.3: Data Validation
- Census year must be valid (1790-1950, every 10 years)
- State name must be valid US state or territory for that year
- County must not be empty
- ED required for 1880-1950
- FamilySearch URL must be valid ARK format
- Access date must be valid date format

#### FR-1.4: Missing Data Prompts
**Required Fields by Census Year:**

1790-1840:
- Year, State, County, Town, Page, Name

1850-1880:
- Year, State, County, Town, Page, Dwelling/Family, Name

1900-1950:
- Year, State, County, Town/Ward, ED, Sheet, Family, Name

**Prompt UI:**
- Display citation preview
- Highlight missing fields in red
- Show embedded browser with FamilySearch page
- Provide input fields with validation
- Show example format for each field

### 4.2 Image Management Engine

#### FR-2.1: File System Monitoring
**Priority**: P0 (Critical)

**Requirements:**
- Monitor user-configured download folder
- Detect new image files: .jpg, .jpeg, .png, .pdf
- Ignore partial downloads (.crdownload, .download, .tmp)
- React within 2 seconds of file appearing
- Handle rapid multiple downloads

**Configuration:**
- Default: `~/Downloads`
- User can change via Settings
- Validate folder exists and is writable
- Persist configuration between sessions

#### FR-2.2: Citation Context Tracking
**Priority**: P0 (Critical)

When user initiates download:
1. Record citation ID
2. Record person name
3. Record census details (year, state, county)
4. Set "awaiting download" flag
5. Start timeout timer (15 minutes)

When download detected:
1. Match to most recent "awaiting download" citation
2. Extract data for filename generation
3. Process file

#### FR-2.3: File Naming Schema
**Pattern:** `YYYY, State, County - Surname, GivenName.extension`

**Examples:**
- `1900, Ohio, Noble - Ijams, Ella.jpg`
- `1940, Texas, Milam - Iiams, Frank W..jpg`
- `1950, California, Los Angeles - Smith, John A..pdf`

**Rules:**
- Preserve file extension from original
- Handle multi-part surnames (e.g., "Van Der Berg")
- Handle suffixes (Jr., Sr., III)
- Sanitize illegal filename characters
- Truncate if total length > 255 characters

#### FR-2.4: File Organization
**Base Path:** `/Users/miams/Genealogy/RootsMagic/Files/Records - Census`

**Folder Structure:**
```
1790 Federal/
1800 Federal/
...
1900 Federal/
1910 Federal/
...
1950 Federal/
1850 Federal Slave Schedule/
1860 Federal Slave Schedule/
1890 Federal Veterans and Widows Schedule/
Federal Mortality Schedule 1850-1885/
  1850 Mortality/
  1860 Mortality/
  1870 Mortality/
  1880 Mortality/
```

**Mapping Logic:**
- Standard census: `[Year] Federal/`
- Slave schedule: `[Year] Federal Slave Schedule/`
- Mortality: `Federal Mortality Schedule 1850-1885/[Year] Mortality/`
- Veterans (1890): `1890 Federal Veterans and Widows Schedule/`

**Future State Census Support:**
```
1855 New York/
1865 New York/
1875 New York/
1885 Colorado/
1885 Iowa/
1885 New Jersey/
1895 Iowa/
1925 Iowa/
1945 Florida/
```

#### FR-2.5: RootsMagic Database Integration
**Priority**: P0 (Critical)

**Database Updates:**

1. **Create Media Record** (MediaTable)
   - MediaType: 0 (Image)
   - MediaFile: relative path from RM database
   - MediaPath: folder path
   - Caption: Generated from citation data
   - RefNumber: FamilySearch ARK
   - Date: Census date
   - Description: Auto-generated

2. **Link to Citation** (MediaLinkTable)
   - LinkType: Citation
   - LinkID: Citation OwnerID
   - MediaID: New media record ID

3. **Link to Person Event** (MediaLinkTable)
   - LinkType: Event
   - LinkID: Census event ID
   - MediaID: New media record ID

**Caption Format:**
```
[Year] U.S. Federal Census, [County] County, [State]
[Name], enumeration district [ED], sheet [Sheet], family [Family]
```

**Example:**
```
1900 U.S. Federal Census, Noble County, Ohio
Ella Ijams, enumeration district 95, sheet 3B, family 57
```

### 4.3 Database Access

#### FR-3.1: Database Connection
**Priority**: P0 (Critical)

- SQLite3 direct access to .rmtree file
- Read-only mode for citation browsing
- Read-write mode for updates
- Implement connection pooling
- Handle database locks gracefully
- Close connections properly on exit

**Safety Measures:**
- Check if RootsMagic is running (warn user)
- Validate database schema version
- Test read access before allowing write operations
- Log all database modifications
- Provide manual database path selection

#### FR-3.2: Database Schema (Read)
**Tables to Query:**

**CitationTable:**
- CitationID (primary key)
- SourceID (foreign key to SourceTable)
- CitationName
- ActualText (FamilySearch entry)
- RefNumber (URL)
- Comments
- Footnote (to be updated)
- ShortFootnote (to be updated)
- Bibliography (to be updated)

**SourceTable:**
- SourceID (primary key)
- Name (RM Source Name)
- SourceType

**PersonTable:**
- PersonID
- GivenName
- Surname

**EventTable:**
- EventID
- EventType (Census)
- PersonID
- Date
- Place

**MediaTable:**
- MediaID (primary key)
- MediaType (0=Image)
- MediaFile
- MediaPath
- Caption
- RefNumber

**MediaLinkTable:**
- LinkID (citation or event ID)
- LinkType (0=Person, 1=Family, 2=Event, 3=Source, 4=Citation)
- MediaID

#### FR-3.3: Query Patterns

**Get all census citations for a year:**
```sql
SELECT c.CitationID, c.CitationName, c.ActualText, c.RefNumber, s.Name
FROM CitationTable c
JOIN SourceTable s ON c.SourceID = s.SourceID
WHERE s.Name LIKE 'Fed Census: [year]%'
ORDER BY s.Name
```

**Get citation details with person info:**
```sql
SELECT c.*, p.GivenName, p.Surname, e.Date, e.Place
FROM CitationTable c
JOIN EventTable e ON e.EventID = c.LinkID
JOIN PersonTable p ON e.PersonID = p.PersonID
WHERE c.CitationID = ?
```

**Check if citation has linked media:**
```sql
SELECT COUNT(*)
FROM MediaLinkTable
WHERE LinkType = 4 AND LinkID = ?
```

### 4.4 User Interface

#### FR-4.1: Main Window Layout
**Priority**: P0 (Critical)

**Components:**
1. **Top Navigation Bar**
   - App title
   - Settings button
   - Help button

2. **Main Content Area (Tabbed)**
   - Tab 1: Citation Manager
   - Tab 2: Image Monitor
   - Tab 3: Settings

3. **Status Bar**
   - Database connection status
   - Download monitor status
   - Last action timestamp

#### FR-4.2: Citation Manager Tab
**Priority**: P0 (Critical)

**Layout:**

**Left Panel (30% width):**
- Census year selector (dropdown: 1790-1950)
- "Load Citations" button
- Citation list (scrollable table):
  - Person name
  - Location (County, State)
  - Status icon (✓ formatted, ⚠ incomplete, ✗ error)
- Filter: Show only unformatted
- Selection: single or batch select

**Right Panel (70% width):**
- **Citation Details (read-only display):**
  - RM Source Name
  - RM FamilySearch Entry
  - Current Footnote
  - Current Short Footnote
  - Current Bibliography

- **Generated Preview (highlighted):**
  - New Footnote
  - New Short Footnote
  - New Bibliography

- **Missing Data Form (if applicable):**
  - Input fields with labels
  - "Open FamilySearch Page" button
  - Validation messages

**Action Buttons:**
- "Process Selected" (primary)
- "Process All in Year" (secondary)
- "Preview Changes" (secondary)
- "Cancel" (tertiary)

#### FR-4.3: Image Monitor Tab
**Priority**: P0 (Critical)

**Layout:**

**Monitor Status Panel:**
- Status indicator: ● Active / ○ Inactive
- Monitored folder path
- "Change Folder" button
- Active citation context display:
  - Person name
  - Census details
  - "Awaiting download..." indicator

**Recent Activity Log:**
- Scrollable list of processed images:
  - Timestamp
  - Original filename
  - New filename
  - Destination folder
  - Status (✓ success, ✗ error)
- Clear log button

**Manual Processing:**
- "Process File Manually" button
- File picker for one-off processing
- Override citation context

#### FR-4.4: Settings Tab
**Priority**: P1 (High)

**Database Settings:**
- RootsMagic database path
- "Browse..." button
- "Test Connection" button
- Connection status indicator

**Download Monitor Settings:**
- Download folder path
- "Browse..." button
- File types to monitor (checkboxes)
- Download timeout (minutes)

**Citation Preferences:**
- Default access date format
- Preview before applying changes (checkbox)
- Batch size limit

**File Management:**
- Census records base path
- "Browse..." button
- "Verify Folders" button (check all year folders exist)

**Application:**
- Launch at startup (checkbox)
- Minimize to menu bar (checkbox)
- Enable logging (checkbox)
- Log file location

#### FR-4.5: Side-by-Side Browser Integration
**Priority**: P0 (Critical)

**Behavior:**
- When missing data detected, or "Open FamilySearch Page" clicked:
  1. Get screen dimensions
  2. Position app window on left 50%
  3. Open FamilySearch URL in default browser
  4. Use AppleScript to position browser on right 50%
  5. Bring both windows to front

**Fallback:**
- If window positioning fails, just open browser
- Show notification: "Position browser and app side-by-side to view citation source"

---

## 5. Non-Functional Requirements

### 5.1 Performance
**Priority**: P0 (Critical)

- Citation parsing: <100ms per citation
- Batch processing: >10 citations/second
- File monitoring: <2 second detection latency
- Database queries: <500ms for typical queries
- UI responsiveness: <100ms for user actions
- Application startup: <3 seconds

### 5.2 Reliability
**Priority**: P0 (Critical)

- 99.9% uptime while running
- Zero data loss on crashes
- Graceful handling of database locks
- Automatic recovery from file system errors
- All database writes are atomic
- Comprehensive error logging

### 5.3 Usability
**Priority**: P0 (Critical)

- Intuitive UI requiring no training
- Clear error messages with suggested actions
- Undo capability for database changes
- Keyboard shortcuts for common actions
- Accessible design (minimum font sizes, contrast)

### 5.4 Security
**Priority**: P1 (High)

- Read-only access to RootsMagic database by default
- No network access except opening URLs
- No data transmission to external services
- Secure storage of user preferences
- File system access limited to configured paths

### 5.5 Compatibility
**Priority**: P0 (Critical)

- macOS 12 Monterey or later
- Apple Silicon (M1/M2/M3) native
- Intel Mac support (via Rosetta if needed)
- RootsMagic 8/9 database format
- SQLite 3.x

### 5.6 Maintainability
**Priority**: P1 (High)

- Modular architecture
- Comprehensive unit tests (>80% coverage)
- Integration tests for database operations
- Inline documentation
- Type hints throughout codebase
- Logging framework for debugging

---

## 6. Technical Architecture

### 6.1 Recommended Technology Stack

#### Core Framework
**NiceGUI 3.0+** with native mode
- Modern, clean Material Design aesthetic
- Native window via PyWebView
- Built-in web components
- Reactive UI updates with observable properties
- Embedded browser capability
- Script mode for simplified app structure
- Tailwind 4 styling support
- Enhanced event system for long-living objects

#### Programming Language
**Python 3.11+**
- Excellent performance on Apple Silicon
- Rich ecosystem of libraries
- Strong typing support
- Great for data processing

#### Key Libraries

**Database Access:**
- `sqlite3` (built-in) - RootsMagic database operations
- `sqlalchemy` (optional) - ORM if complexity grows

**File System Monitoring:**
- `watchdog` 3.0+ - Cross-platform file system events
- Robust, battle-tested
- Low CPU overhead

**Text Parsing:**
- `pyparsing` 3.1+ - Structured citation parsing
- Regular expressions (built-in `re` module)
- `python-dateutil` - Date parsing and formatting

**Configuration Management:**
- `pydantic` 2.0+ - Settings with validation
- `pydantic-settings` - Environment and file-based config
- JSON or TOML for config files

**Window Management:**
- `pywebview` 4.0+ (via NiceGUI native mode)
- `pyobjc` - macOS-specific window positioning via AppleScript

**Logging:**
- `loguru` - Beautiful, modern logging
- Automatic rotation and retention
- Structured logging support

**Testing:**
- `pytest` 7.0+ - Test framework
- `pytest-qt` - UI testing
- `pytest-cov` - Coverage reporting
- `pytest-mock` - Mocking support

**Code Quality:**
- `ruff` - Fast Python linter and formatter
- `mypy` - Static type checking
- `black` - Code formatting (or use ruff)

**Packaging:**
- `PyInstaller` or `py2app` - macOS .app bundle creation
- `briefcase` (alternative) - Cross-platform packaging

### 6.2 Application Architecture

#### Layered Architecture

```
┌─────────────────────────────────────────┐
│         Presentation Layer              │
│        (NiceGUI Components)             │
├─────────────────────────────────────────┤
│         Application Layer               │
│   (Business Logic, Controllers)         │
├─────────────────────────────────────────┤
│          Service Layer                  │
│  ┌──────────────┐  ┌─────────────────┐ │
│  │   Citation   │  │  Image          │ │
│  │   Service    │  │  Service        │ │
│  └──────────────┘  └─────────────────┘ │
├─────────────────────────────────────────┤
│         Data Access Layer               │
│  ┌──────────────┐  ┌─────────────────┐ │
│  │  Database    │  │  File System    │ │
│  │  Repository  │  │  Monitor        │ │
│  └──────────────┘  └─────────────────┘ │
└─────────────────────────────────────────┘
```

#### Module Structure

```
rmcitecraft/
├── __init__.py
├── main.py                          # Application entry point
├── config/
│   ├── __init__.py
│   ├── settings.py                  # Pydantic settings
│   └── constants.py                 # Census years, folder mappings
├── ui/
│   ├── __init__.py
│   ├── main_window.py              # Main NiceGUI app
│   ├── citation_tab.py             # Citation manager UI
│   ├── image_tab.py                # Image monitor UI
│   ├── settings_tab.py             # Settings UI
│   └── components/                 # Reusable UI components
│       ├── citation_preview.py
│       └── status_indicator.py
├── services/
│   ├── __init__.py
│   ├── citation_service.py         # Citation parsing & formatting
│   ├── image_service.py            # Image processing logic
│   └── database_service.py         # Database operations
├── repositories/
│   ├── __init__.py
│   ├── citation_repository.py      # Citation data access
│   ├── media_repository.py         # Media data access
│   └── database.py                 # Database connection management
├── models/
│   ├── __init__.py
│   ├── citation.py                 # Citation data models
│   ├── media.py                    # Media data models
│   └── census.py                   # Census metadata models
├── parsers/
│   ├── __init__.py
│   ├── familysearch_parser.py      # Parse FamilySearch citations
│   ├── citation_formatter.py       # Generate Evidence Explained format
│   └── templates/                  # Citation templates by year
│       ├── template_1790_1840.py
│       ├── template_1850_1880.py
│       ├── template_1900_1950.py
│       └── special_schedules.py
├── monitoring/
│   ├── __init__.py
│   ├── file_watcher.py            # Watchdog integration
│   └── download_tracker.py        # Track active download context
├── utils/
│   ├── __init__.py
│   ├── filename_generator.py      # Generate standardized filenames
│   ├── folder_mapper.py           # Map census year to folder
│   ├── validation.py              # Data validation utilities
│   └── window_manager.py          # macOS window positioning
└── tests/
    ├── __init__.py
    ├── unit/
    │   ├── test_citation_parser.py
    │   ├── test_citation_formatter.py
    │   ├── test_filename_generator.py
    │   └── test_database_service.py
    ├── integration/
    │   ├── test_citation_workflow.py
    │   └── test_image_workflow.py
    └── fixtures/
        ├── sample_citations.json
        └── test_database.rmtree
```

### 6.3 Data Models

#### Citation Model
```python
from pydantic import BaseModel, HttpUrl, Field
from datetime import date
from typing import Optional

class ParsedCitation(BaseModel):
    # Source data
    citation_id: int
    source_name: str
    familysearch_entry: str

    # Parsed components
    census_year: int = Field(ge=1790, le=1950)
    state: str
    county: str
    town_ward: Optional[str] = None
    enumeration_district: Optional[str] = None
    sheet: Optional[str] = None
    family_number: Optional[str] = None
    dwelling_number: Optional[str] = None

    # Person info
    person_name: str
    given_name: str
    surname: str

    # URLs and references
    familysearch_url: HttpUrl
    access_date: date
    nara_publication: Optional[str] = None  # e.g., "T623"
    fhl_microfilm: Optional[str] = None     # e.g., "1,241,311"

    # Generated citations
    footnote: Optional[str] = None
    short_footnote: Optional[str] = None
    bibliography: Optional[str] = None

    # Validation status
    is_complete: bool = False
    missing_fields: list[str] = []
    errors: list[str] = []
```

#### Census Metadata Model
```python
class CensusYear(BaseModel):
    year: int
    name: str                        # "1900 Federal"
    folder_name: str                 # "1900 Federal"
    requires_ed: bool               # True for 1880+
    schedule_type: str              # "population", "slave", "mortality", "veterans"
    template_version: str           # "1900-1950"
```

#### Media Model
```python
class MediaRecord(BaseModel):
    media_id: Optional[int] = None
    media_type: int = 0             # 0 = Image
    media_file: str                 # Relative path
    media_path: str                 # Folder path
    caption: str
    ref_number: str                 # FamilySearch ARK
    date: Optional[str] = None      # Census date
    description: Optional[str] = None

    # Links
    citation_id: Optional[int] = None
    event_id: Optional[int] = None
```

#### Download Context Model
```python
class DownloadContext(BaseModel):
    citation_id: int
    person_name: str
    given_name: str
    surname: str
    census_year: int
    state: str
    county: str
    timestamp: datetime
    timeout_at: datetime
    status: str = "awaiting"  # awaiting, matched, timeout, cancelled
```

### 6.4 Key Algorithms

#### Citation Parser Algorithm
```python
def parse_familysearch_citation(source_name: str,
                                familysearch_entry: str) -> ParsedCitation:
    """
    Parse FamilySearch citation into structured components.

    Algorithm:
    1. Extract census year from source_name (regex: r'Fed Census: (\d{4})')
    2. Extract state and county from source_name
    3. Extract person name from source_name
    4. Parse familysearch_entry for:
       - Location details (town, ward)
       - ED, sheet, family numbers (regex patterns by year)
       - FamilySearch URL (ARK format)
       - Access date (dateutil parser)
       - NARA/FHL references
    5. Validate required fields for census year
    6. Return ParsedCitation with missing_fields list if incomplete
    """
```

#### Citation Formatter Algorithm
```python
def format_citation(parsed: ParsedCitation) -> tuple[str, str, str]:
    """
    Generate Evidence Explained formatted citations.

    Algorithm:
    1. Select template based on census_year:
       - 1790-1840: Early template
       - 1850-1880: Mid-century template (with pop. schedule)
       - 1900-1950: Modern template (with ED)
       - Special schedules: Custom templates
    2. Populate template with parsed data
    3. Apply formatting rules:
       - Italicize FamilySearch
       - County abbreviation rules for short footnote
       - State abbreviation (2-letter) for short footnote
       - URL formatting
       - Date formatting
    4. Return (footnote, short_footnote, bibliography)
    """
```

#### Filename Generator Algorithm
```python
def generate_census_filename(context: DownloadContext,
                            original_extension: str) -> str:
    """
    Generate standardized census image filename.

    Algorithm:
    1. Format: "YYYY, State, County - Surname, GivenName.ext"
    2. Sanitize components:
       - Remove illegal characters: / \ : * ? " < > |
       - Preserve periods in names (e.g., "W." in "William W.")
       - Handle suffixes (Jr., Sr., III)
    3. Truncate if total > 255 characters:
       - Priority: Year, State, County (always included)
       - Shorten names if needed (GivenName first initial)
    4. Return filename

    Examples:
    - "1900, Ohio, Noble - Ijams, Ella.jpg"
    - "1940, Texas, Milam - Iiams, Frank W..jpg"
    """
```

#### Folder Mapper Algorithm
```python
def map_census_to_folder(year: int,
                         schedule_type: str = "population") -> Path:
    """
    Map census year and type to folder path.

    Algorithm:
    1. Base path: /Users/miams/Genealogy/RootsMagic/Files/Records - Census
    2. If schedule_type == "population":
       return base_path / f"{year} Federal"
    3. If schedule_type == "slave":
       return base_path / f"{year} Federal Slave Schedule"
    4. If schedule_type == "mortality":
       return base_path / "Federal Mortality Schedule 1850-1885" / f"{year} Mortality"
    5. If schedule_type == "veterans" and year == 1890:
       return base_path / "1890 Federal Veterans and Widows Schedule"
    6. Validate folder exists, create if missing (with user permission)
    """
```

### 6.5 Database Operations

#### Safe Database Writing
```python
class DatabaseService:
    def update_citation(self, citation_id: int,
                       footnote: str,
                       short_footnote: str,
                       bibliography: str) -> bool:
        """
        Safely update citation in RootsMagic database.

        Safety measures:
        1. Check if database file is locked
        2. Begin transaction
        3. Verify citation exists
        4. Update CitationTable SET Footnote, ShortFootnote, Bibliography
        5. Log change to audit table (optional)
        6. Commit transaction
        7. Rollback on any error
        8. Return success/failure
        """

    def create_media_record(self, media: MediaRecord) -> int:
        """
        Create media record and link to citation/event.

        Algorithm:
        1. Begin transaction
        2. Insert into MediaTable, get media_id
        3. Insert into MediaLinkTable (citation link)
        4. Insert into MediaLinkTable (event link) if event_id provided
        5. Commit transaction
        6. Return media_id
        """
```

#### Query Optimization
- Use indexes on CitationID, SourceID for fast lookups
- Limit result sets for large databases (pagination)
- Cache census year folder mappings
- Prepare statements for repeated queries

---

## 7. Development Phases

### Phase 1: Foundation (Weeks 1-2)
**Goal**: Basic infrastructure and citation parsing

**Deliverables:**
- Project structure and configuration
- Database connection and schema exploration
- FamilySearch citation parser (1900-1950)
- Citation formatter for modern census (1900-1950)
- Unit tests for parser and formatter
- Basic NiceGUI application window

**Acceptance Criteria:**
- Can connect to RootsMagic database
- Can parse example citations from README
- Generated citations match examples exactly
- Tests achieve >80% coverage

### Phase 2: Citation UI (Weeks 3-4)
**Goal**: Full citation management interface

**Deliverables:**
- Citation Manager tab UI
- Citation list view with filtering
- Citation preview and edit
- Missing data prompts
- Batch processing
- Database write operations
- Integration tests

**Acceptance Criteria:**
- User can load citations by year
- User can preview transformations
- User can provide missing data
- User can process citations and update database
- Changes persist correctly in RootsMagic

### Phase 3: Image Monitoring (Weeks 5-6)
**Goal**: File system monitoring and image processing

**Deliverables:**
- File watcher service (watchdog)
- Download context tracking
- Filename generator
- Folder mapper
- File move operations
- Image Monitor tab UI
- Activity log

**Acceptance Criteria:**
- Downloads are detected within 2 seconds
- Files renamed correctly
- Files moved to correct folders
- No file system errors or data loss

### Phase 4: Image-Database Integration (Week 7)
**Goal**: Link images to RootsMagic database

**Deliverables:**
- Media record creation
- MediaLinkTable updates
- Caption generation
- Complete workflow: download → rename → move → link
- Integration tests for full workflow

**Acceptance Criteria:**
- Images appear in RootsMagic media gallery
- Images linked to correct citation
- Images linked to correct person/event
- Captions formatted correctly

### Phase 5: Polish & Extended Support (Week 8)
**Goal**: Full census year support and UX improvements

**Deliverables:**
- Citation templates for 1790-1890
- Special schedule support (slave, mortality, veterans)
- Settings tab with all configurations
- Keyboard shortcuts
- Error handling and user feedback
- Help documentation
- Application icon and branding

**Acceptance Criteria:**
- Supports all federal census years (1790-1950)
- Handles all special schedules
- User can configure all settings
- Clear error messages guide users
- Professional appearance

### Phase 6: Testing & Release (Week 9-10)
**Goal**: Production-ready application

**Deliverables:**
- Comprehensive testing (unit, integration, E2E)
- Performance optimization
- macOS .app bundle packaging
- Installation guide
- User manual
- Demo video
- GitHub repository with README

**Acceptance Criteria:**
- All tests passing
- Performance meets requirements
- Packaged .app runs on clean macOS system
- Documentation complete
- Ready for user acceptance testing

---

## 8. Testing Strategy

### 8.1 Unit Tests
**Coverage Target**: >80%

**Key Test Suites:**
- Citation parser (all census years)
- Citation formatter (all templates)
- Filename generator (edge cases)
- Folder mapper (all year/schedule combinations)
- Database repository methods
- Validation utilities

### 8.2 Integration Tests
**Key Scenarios:**
- End-to-end citation processing workflow
- End-to-end image download workflow
- Database read/write operations
- File system operations
- UI interactions

### 8.3 Manual Testing
**Test Cases:**
- Real RootsMagic database
- Actual FamilySearch downloads
- Side-by-side browser positioning
- Rapid multiple downloads
- Error scenarios (locked database, missing folders)
- macOS permissions (file access, browser control)

### 8.4 Performance Testing
**Benchmarks:**
- Parse 1000 citations < 10 seconds
- Format 100 citations/second
- File detection < 2 seconds
- Database query < 500ms
- UI responsiveness < 100ms

---

## 9. Deployment & Distribution

### 9.1 Packaging
**Tool**: PyInstaller or py2app

**Bundle Contents:**
- Python runtime
- All dependencies
- Application code
- Configuration templates
- Documentation

**Output**: `RMCitecraft.app`

### 9.2 Installation
**Requirements:**
- macOS 12+ (Monterey or later)
- 100 MB disk space
- RootsMagic 8 or 9

**Installation Steps:**
1. Download .app from GitHub releases
2. Drag to Applications folder
3. First launch: Grant permissions (file access)
4. Configure RootsMagic database path
5. Configure download folder path

### 9.3 Updates
**Strategy**: Manual download from GitHub releases

**Future**: Implement auto-update check (sparkle or similar)

---

## 10. Risks & Mitigations

### Risk 1: Database Schema Changes
**Impact**: High
**Probability**: Low
**Mitigation**:
- Detect schema version on connection
- Support multiple RootsMagic versions
- Comprehensive testing with different database versions
- Graceful degradation if schema incompatible

### Risk 2: Citation Parsing Ambiguity
**Impact**: Medium
**Probability**: Medium
**Mitigation**:
- Extensive test suite with real citations
- Allow manual overrides for parsing
- User can edit generated citations before saving
- Comprehensive error messages

### Risk 3: File System Permissions
**Impact**: High
**Probability**: Low
**Mitigation**:
- Clear permission prompts on first launch
- Validate access before operations
- Graceful error messages
- Fallback to manual file selection

### Risk 4: RootsMagic Database Corruption
**Impact**: Critical
**Probability**: Very Low
**Mitigation**:
- Read-only mode by default
- Atomic transactions
- Extensive testing
- Recommend database backups
- Log all write operations

### Risk 5: Browser Automation Limitations
**Impact**: Low
**Probability**: Medium
**Mitigation**:
- Use standard URL opening (not automation)
- Window positioning is best-effort (fallback to manual)
- Clear instructions if automation fails

---

## 11. Future Enhancements

### Phase 7: State Census Support
- Templates for state census years
- Extended folder structure
- State-specific formatting rules

### Phase 8: Other Record Types
- Vital records (birth, marriage, death)
- Military records
- Immigration records
- Church records

### Phase 9: Advanced Features
- Batch export to CSV
- Citation style switching (Chicago, MLA, etc.)
- Integration with other genealogy software
- Cloud backup of citations
- Collaborative features

### Phase 10: AI Enhancement
- Auto-detect missing data from image OCR
- Suggest corrections for common errors
- Smart matching of downloads to citations

---

## 12. Appendix

### A. Glossary

**RootsMagic**: Commercial genealogy software using SQLite database
**Evidence Explained**: Authoritative guide for citing genealogical sources
**FamilySearch**: Free genealogy website with census images
**ARK**: Archival Resource Key, persistent URL format used by FamilySearch
**ED**: Enumeration District (census geographic subdivision)
**NARA**: National Archives and Records Administration
**FHL**: Family History Library

### B. Reference Citations

*Evidence Explained: Citing History Sources from Artifacts to Cyberspace* by Elizabeth Shown Mills (3rd edition, 2015)

RootsMagic Database Structure: https://sqlitetoolsforrootsmagic.com/

FamilySearch API Documentation: https://www.familysearch.org/developers/

### C. Technology Stack Summary

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Framework | NiceGUI | 3.0+ | UI framework with native mode |
| Language | Python | 3.11+ | Core application logic |
| Database | SQLite3 | 3.x | RootsMagic database access |
| Monitoring | Watchdog | 3.0+ | File system event monitoring |
| Parsing | pyparsing | 3.1+ | Citation parsing |
| Settings | Pydantic | 2.0+ | Configuration management |
| Logging | Loguru | latest | Application logging |
| Testing | Pytest | 7.0+ | Test framework |
| Packaging | PyInstaller | latest | macOS app bundling |
| Window Mgmt | PyObjC | latest | macOS window positioning |

### D. Contact & Support

**Project Repository**: [To be created on GitHub]
**Issue Tracker**: GitHub Issues
**Documentation**: GitHub Wiki
**Maintainer**: [User name]

---

**Document Version**: 1.0
**Last Updated**: 2025-10-19
**Status**: Draft for Review
