---
priority: essential
topics: [database, census, citation, batch, findagrave]
---

# RMCitecraft

**Automated Citation and Image Management for RootsMagic**

RMCitecraft automates citation formatting and image management for genealogy records in RootsMagic databases. It handles two primary record types: **US Federal Census** (1790-1950) and **Find a Grave** memorials.

## Value Proposition

Genealogists using RootsMagic spend significant time manually formatting citations and organizing downloaded images. RMCitecraft automates these workflows:

| Task | Before | After |
|------|--------|-------|
| Citation formatting | Manual reformat to Evidence Explained style | Batch process with auto-formatting |
| Missing data | Hunt through source pages | Prompted with source page displayed |
| Image naming | Manual rename each file | Auto-renamed to standard schema |
| Image organization | Drag files to correct folders | Auto-routed by record type/year |
| Database linking | Manual media record creation | Auto-linked to citations and events |

## Key Features

### Census Records (1790-1950)

**AI-Powered Census Extraction:**
- Playwright automation navigates FamilySearch census pages
- AI (Claude/GPT) transcribes census images using schema-based prompts
- Extracts all household members with line numbers, relationships, ages, birthplaces
- Matches extracted persons to RootsMagic database with fuzzy name matching (Hungarian algorithm for optimal assignment)
- Stores extracted data in `~/.rmcitecraft/census.db` using EAV (Entity-Attribute-Value) pattern for extensible fields
- Achieves ~85% automatic matching coverage for 1950 census records

**Citation Processing:**
- Batch process multiple citations per session
- Smart validation identifies unprocessed vs. already-formatted citations
- *Evidence Explained* compliant output (footnote, short footnote, bibliography)
- Prompts for missing data (e.g., enumeration district) with FamilySearch page displayed

**Census Extraction Viewer:**
- **Page View Mode**: Browse extracted census pages with all household members
- **Match Suggestions**: Confidence-scored candidate matches with fuzzy name matching
- **Manual RIN Linking**: Enter RIN directly or select from household members
- **Link Status Indicators**: Purple icon = linked to RIN, gray = citation only
- **Hybrid Citation Lookup**: Automatically finds valid citations via stored ID, RIN lookup, or location matching
- Renders extracted census data using Jinja2 templates matching original document layout

**Image Management:**
- Auto-rename: `YYYY, State, County - Surname, GivenName.ext`
- Auto-route to year-specific folders (`1900 Federal/`, `1940 Federal/`, etc.)
- Database integration: creates media records, links to citations and events

### Find a Grave Records

**Citation Processing:**
- Batch process burial citations from Find a Grave
- Extract memorial data (cemetery, location, dates)
- Generate formatted citations with proper attribution

**Image Management:**
- Download and organize memorial photos and headstone images
- Auto-rename with cemetery and person identifiers
- Link images to burial events and citations in RootsMagic
- Primary photo assignment for person profiles

### Dashboard & Analytics

- **Real-time Progress**: Monitor batch processing status
- **Session Management**: Pause, resume, and recover interrupted sessions
- **Crash Recovery**: SQLite-based state persistence at `~/.rmcitecraft/batch_state.db` enables recovery from interruptions
- **Error Analysis**: Track failures with categorized error reporting
- **Performance Metrics**: Processing times, success rates, throughput

## Use Cases

1. **Census Batch Transcription**: Extract and transcribe census pages from FamilySearch using AI
2. **Census Cleanup**: Batch-format existing FamilySearch placeholder citations
3. **Find a Grave Integration**: Process burial records with photo downloads
4. **New Record Import**: Format citations immediately after accepting FamilySearch hints
5. **Image Standardization**: Organize scattered downloads into consistent folder structure
6. **Quality Assurance**: Validate citations against Evidence Explained standards using 6-criterion validation (year format, census reference, sheet/stamp, ED for 1900+, unique footnote vs short footnote, all forms complete)

## Requirements

### System
- **Platform**: macOS (Apple Silicon optimized)
- **Python**: 3.11+
- **Database**: RootsMagic 8, 9, 10, or 11

### Optional
- **LLM API Key**: For census image transcription (Anthropic Claude or OpenAI)
- **Chrome Browser**: For FamilySearch/Find a Grave automation (must be started with `--remote-debugging-port=9222` for Playwright CDP connection)

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| Package Manager | UV |
| UI Framework | NiceGUI 3.0+ (native mode) |
| Database | SQLite with ICU extension |
| Browser Automation | Playwright / Chrome DevTools Protocol |
| LLM Integration | LangChain (multi-provider) |
| Testing | pytest |
| Linting | Ruff, MyPy |

## Installation

```bash
# Install UV package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone https://github.com/miams/RMCitecraft.git
cd RMCitecraft

# Install dependencies
uv sync

# Copy and configure environment
cp config/.env.example .env
# Edit .env with your database path and API keys
```

## Quick Start

```bash
# Show version
rmcitecraft version

# Start application (interactive mode)
rmcitecraft start

# Start in background
rmcitecraft start -d

# Check status
rmcitecraft status

# Stop application
rmcitecraft stop

# Show help
rmcitecraft help
```

## Documentation

- **[CLAUDE.md](CLAUDE.md)** - Development guidance and architecture details
- **[AGENTS.md](AGENTS.md)** - Machine-readable instructions for AI agents
- **[PRD.md](PRD.md)** - Complete product requirements
- **[docs/reference/schema-reference.md](docs/reference/schema-reference.md)** - RootsMagic database schema

## Caveats and Known Issues
1. The 1950 Census tested the household-based form in a few jurisdictions in Ohio and Michigan, instead of the traditional multi-family form. The household form is not as well-parsed by FamilySearch, so RMCiteCraft asks for some fields.  The ED can be identified using the Information button when displaying the image. These forms do not have sheet/page numbers, nor line numbers.  Instead, I substitute a sequential stamped number and the image number, and I note the family form.  For example:


   1950 U.S. census, Genesee County, Michigan, Burton Township, enumeration district (ED) 25-11, stamp 366, image 372 of 441, Brady G Ijames and Charlotte Ijames; imaged, "United States Census, 1950, household form," *FamilySearch*, (https://www.familysearch.org/ark:/61903/1:1:6JJZ-JB42  : accessed 25 November 2025).


## License

MIT License - See LICENSE file for details.
