# RMCitecraft

**Automated Census Citation Management for RootsMagic**

RMCitecraft transforms FamilySearch placeholder citations into professional, *Evidence Explained*-compliant citations and manages census image organization in RootsMagic genealogy databases.

## Value Proposition

Genealogists using RootsMagic spend significant time manually formatting census citations and organizing downloaded images. RMCitecraft automates this workflow:

- **Before**: Copy-paste FamilySearch citations, manually reformat to Evidence Explained style, rename and organize downloaded images, update database media links
- **After**: Batch process citations automatically, fill in only missing data when prompted, images auto-renamed and organized

## Key Features

### Census Citation Processing
- **Batch Processing**: Process multiple census citations in a single session (1790-1950)
- **Smart Validation**: Automatically identifies citations needing processing vs. already-formatted ones
- **Evidence Explained Compliance**: Generates proper footnote, short footnote, and bibliography formats
- **Missing Data Prompts**: When enumeration districts or other data are missing, prompts user with FamilySearch page displayed

### Census Image Management
- **Automatic File Naming**: Renames downloads to standardized format: `YYYY, State, County - Surname, GivenName.ext`
- **Organized Storage**: Routes images to correct census year folders
- **Database Integration**: Creates media records and links to citations/events in RootsMagic

### Find a Grave Integration
- **Batch Processing**: Process Find a Grave citations with photo downloads
- **Image Management**: Automatic photo organization and database linking

### Dashboard Analytics
- **Real-time Progress**: Monitor batch processing status
- **Session Management**: Resume interrupted sessions
- **Performance Metrics**: Track processing times and success rates

## Use Cases

1. **New Census Records**: Import FamilySearch hints, then batch-format all new census citations
2. **Legacy Cleanup**: Process existing placeholder citations in bulk
3. **Image Organization**: Standardize naming and storage of census images across your database
4. **Quality Assurance**: Validate citations meet Evidence Explained standards

## Requirements

### System
- **Platform**: macOS (Apple Silicon M3 Pro optimized)
- **Python**: 3.11+
- **Database**: RootsMagic 8 or 9 (.rmtree SQLite database)

### Optional
- **LLM API Key**: For citation parsing (Anthropic Claude, OpenAI, or local Ollama)
- **Chrome Browser**: For FamilySearch automation features

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
git clone https://github.com/yourusername/RMCitecraft.git
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

## Citation Format Example

**Input (FamilySearch placeholder):**
```
"United States Census, 1900," database with images, FamilySearch
(https://familysearch.org/ark:/61903/1:1:MM6X-FGZ : accessed 24 July 2015),
Ella Ijams, Olive Township Caldwell village, Noble, Ohio...
```

**Output (Evidence Explained format):**

*Footnote:*
> 1900 U.S. census, Noble County, Ohio, population schedule, Olive Township Caldwell village, enumeration district (ED) 95, sheet 3B, family 57, Ella Ijams; imaged, "1900 United States Federal Census," *FamilySearch* (https://familysearch.org/ark:/61903/1:1:MM6X-FGZ : accessed 24 July 2015).

*Short Footnote:*
> 1900 U.S. census, Noble Co., Oh., pop. sch., Olive Township, E.D. 95, sheet 3B, Ella Ijams.

*Bibliography:*
> U.S. Ohio. Noble County. 1900 U.S Census. Population Schedule. Imaged. "1900 United States Federal Census". *FamilySearch* https://www.familysearch.org/ark:/61903/1:1:MM6X-FGZ : 2015.

## License

MIT License - See LICENSE file for details.
