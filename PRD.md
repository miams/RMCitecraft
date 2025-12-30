# Product Requirements Document: RMCitecraft (v2.1)
## Active Genealogy Automation Agent

**Last Updated**: 2025-12-30

---

## 1. Executive Summary

### 1.1 Product Vision
RMCitecraft is an **active automation agent** for genealogy research. Unlike passive tools that wait for user input, RMCitecraft actively navigates genealogy websites (FamilySearch, Find a Grave), extracts comprehensive data, interprets it using AI, and synchronizes the results with the user's RootsMagic database. It transforms the role of the genealogist from "data entry clerk" to "research reviewer."

### 1.2 Core Value Proposition
*   **Active Extraction**: Automatically navigates to source URLs to scrape full record details, not just citations.
*   **AI-Powered Transcription**: Uses Large Language Models (LLMs) to transcribe handwriting and interpret unstructured data from census images.
*   **Sidecar Database Architecture**: Maintains a comprehensive `census.db` research log separate from the main genealogy tree, enabling deep analysis and data quality tracking.
*   **Crash-Proof Workflow**: Robust state management ensures long-running batch processes can pause, resume, and recover from failures without data loss.

### 1.3 Target Platform
*   **OS**: macOS (primary), Windows (planned).
*   **Integration**: RootsMagic 8/9/10/11 (SQLite format).
*   **Browser**: Google Chrome (via CDP/Playwright).

---

## 2. System Architecture

### 2.1 The "Agent" Model
RMCitecraft operates as a local agent with four distinct subsystems:

1.  **The Orchestrator (Python/NiceGUI)**: The central brain that manages queues, user interaction, and state.
2.  **The Driver (Playwright/CDP)**: Connects to a user's existing Chrome session (with FamilySearch login) to navigate websites, manage sessions, and download media.
3.  **The Analyst (LLM/Regex)**: A processing layer that parses raw HTML/Text into structured data.
4.  **The Archivist (Database Layer)**: Manages the `census.db` (transcription data) and synchronizes validated facts to the RootsMagic database.

### 2.2 Data Flow
1.  **Ingest**: Scan RootsMagic for placeholder citations (e.g., "Fed Census: 1950...").
2.  **Queue**: Add targets to the active batch session.
3.  **Extract**: The Driver navigates to the Source URL.
4.  **Transcribe**: The Analyst extracts full household data (names, ages, relationships).
5.  **Store**: Save full transcription to `census.db`.
6.  **Format**: Generate *Evidence Explained* citations and file names.
7.  **Sync**: Update RootsMagic (Citations, Media Links) and move downloaded images to the file system.

---

## 3. Core Features

### 3.1 Census Batch Automation
**Goal**: Convert thousands of placeholder citations into fully sourced, media-linked records.

*   **Supported Records**:
    *   US Federal Census 1790-1950 (population schedules).
    *   Slave Schedules (1850, 1860).
    *   Mortality Schedules (1850-1880).
*   **Extraction**:
    *   Metadata: Year, State, County, Township, ED, Sheet/Stamp, Line.
    *   Household: Full roster extraction (names, relationships, ages) for validation.
    *   Hungarian algorithm for optimal person-to-RIN matching.
*   **Formatting**:
    *   Generates `Footnote`, `Short Footnote`, and `Bibliography` strictly adhering to *Evidence Explained*.
    *   Year-specific templates (1850 penned pages, 1880+ stamped, 1950 stamps).
    *   Special schedule formatting (slave schedules with owner attribution, mortality schedules).
*   **Validation**:
    *   6-criterion validation: year format, census reference, sheet/stamp, ED (1880+), distinct footnote vs short footnote, all forms complete.
    *   Cross-referencing extracted data with existing RootsMagic data.
    *   Quality check script for batch validation across census years.

### 3.2 Find a Grave Integration
**Goal**: Automate the retrieval of burial details and memorial photos.

*   **Extraction**: Birth/Death dates, Cemetery details, Bio text, Family links.
*   **Image Handling**:
    *   Download primary headstone photos.
    *   Skip generic "flower" images.
    *   Deduplicate existing media.
*   **Citation**: Specialized templates for online memorial citations.

### 3.3 The Sidecar Database (`census.db`)
**Goal**: A persistent, schema-less (EAV) storage for transcription data that exceeds RootsMagic's schema limits.

*   **Schema**: Entity-Attribute-Value pattern to support varying census columns (e.g., "Radio Ownership" in 1930 vs. "Years Married" in 1900).
*   **Analysis**: Enables SQL queries across the entire research set (e.g., "Find all neighbors of ancestors in 1940").
*   **Quality Control**: Tracks "Confidence Score" for every extracted field.

### 3.4 Image Management
**Goal**: Zero-touch file organization.

*   **Naming Convention**: `YYYY, State, County - Surname, GivenName.ext`.
*   **Organization**: Auto-sorts into folder hierarchy: `RootsMagic/Records - Census/[Year] Federal/`.
*   **Linking**: Creates `MultimediaTable` records and links them to:
    *   The `Citation`.
    *   The `Event` (Census Fact).
    *   The `Source` (optional).

### 3.5 Census Extraction Viewer
**Goal**: Browse and link extracted census data to RootsMagic persons.

*   **Page View Mode**: Browse extracted census pages with all household members displayed.
*   **Census Form Rendering**: Jinja2 templates render 30-line census forms matching original document layout.
*   **Match Suggestions**: Confidence-scored candidate matches using fuzzy name matching.
*   **Manual RIN Linking**: Enter RIN directly or select from household members.
*   **Link Status Indicators**: Visual icons show linked (purple) vs citation-only (gray) status.
*   **Hybrid Citation Lookup**: Finds valid citations via stored ID, RIN lookup, or location matching.

### 3.6 Interactive Dashboard
**Goal**: Real-time monitoring and manual intervention.

*   **Live Progress**: Progress bars for batch operations.
*   **Review Queue**: "Traffic light" system (Green=Auto-Approved, Yellow=Review, Red=Error).
*   **Manual Override**: Form-based editor to correct extraction errors before syncing.
*   **Image Viewer**: Side-by-side view of downloaded images vs. transcription data (275% zoom default).

---

## 4. Technical Requirements

### 4.1 Technology Stack
*   **Language**: Python 3.11+.
*   **Package Manager**: `uv` (strict requirement).
*   **UI Framework**: NiceGUI (Native Mode via PyWebView).
*   **Browser Automation**: Playwright (connected to Chrome via CDP).
*   **Database**: SQLite with `ICU` extension (required for RMNOCASE collation).
*   **LLM Integration**: LangChain (supporting Anthropic/OpenAI).

### 4.2 Database Safety Protocols
*   **No-Write Default**: Database connections default to Read-Only.
*   **Atomic Transactions**: All writes wrapped in transaction blocks.
*   **Backup Check**: Warn user if no recent backup is detected (future).
*   **Version Pinning**: Validate RootsMagic database version before connecting.

### 4.3 Performance Goals
*   **Extraction**: < 5 seconds per page (cached).
*   **Batch Throughput**: Process > 500 citations/hour (unattended).
*   **Startup**: < 2 seconds to interactive UI.

---

## 5. Roadmap

### Phase 1: Core Consolidation (Complete)
*   [x] Establish `census.db` sidecar architecture.
*   [x] Implement robust batch processing state machine.
*   [x] Deprecate passive file monitoring and Chrome Extension.
*   [x] Finalize Playwright/CDP transition for all extractors.
*   [x] Census Extraction Viewer with form rendering.
*   [x] 6-criterion citation validation.
*   [x] Slave and mortality schedule support.

### Phase 2: Enhanced Transcription (Current)
*   [x] LLM integration for census image transcription.
*   [x] Hungarian algorithm for household member matching.
*   [ ] "Household Reconstruction": Automatically creating missing family members in RootsMagic based on `census.db` data.
*   [ ] Improved handling of "hard to read" handwritten records.

### Phase 3: State Census & Expansion
*   [ ] Support for State Census records (NY, IA, KS, etc.).
*   [ ] Generalized "Generic Source" extractor for sites like Ancestry or MyHeritage (long-term).

---

## 6. Glossary
*   **Agent**: The autonomous process performing tasks.
*   **CDP (Chrome DevTools Protocol)**: The interface used to drive the browser.
*   **EAV (Entity-Attribute-Value)**: Database pattern for flexible schema.
*   **ED (Enumeration District)**: Geographic subdivision used for census taking (1880+).
*   **Evidence Explained**: The citation style guide by Elizabeth Shown Mills; the standard for genealogical citations.
*   **Hungarian Algorithm**: Optimal assignment algorithm used for matching extracted household members to RootsMagic persons.
*   **RIN (Record Identification Number)**: Unique identifier for a person in RootsMagic.
*   **RMNOCASE**: Custom collation used by RootsMagic; requires ICU extension.
*   **Sidecar**: The `census.db` database living alongside the main `.rmtree` file.