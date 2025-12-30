---
priority: essential
topics: [user-guide, installation, setup]
---

# Getting Started with RMCitecraft

**For**: RootsMagic users new to RMCitecraft
**Time to Complete**: 15-30 minutes

## What is RMCitecraft?

RMCitecraft automates the tedious parts of genealogy citation management:

- **Extracts** census data from FamilySearch pages
- **Formats** citations to *Evidence Explained* standards
- **Downloads** and organizes census images
- **Links** images to your RootsMagic database

### What You'll Need

- macOS (Apple Silicon recommended)
- RootsMagic 8, 9, 10, or 11
- Google Chrome browser
- Python 3.11+ (installed automatically with UV)
- Optional: Anthropic or OpenAI API key (for AI transcription features)

---

## Step 1: Install RMCitecraft

### Install UV Package Manager

Open Terminal and run:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close and reopen Terminal for the installation to take effect.

### Clone the Repository

```bash
git clone https://github.com/miams/RMCitecraft.git
cd RMCitecraft
```

### Install Dependencies

```bash
uv sync
```

This creates a virtual environment and installs all required packages.

---

## Step 2: Configure Your Environment

### Create Configuration File

```bash
cp config/.env.example .env
```

### Edit Configuration

Open `.env` in a text editor and update these essential settings:

```bash
# Path to your RootsMagic database (REQUIRED)
RM_DATABASE_PATH=/path/to/your/database.rmtree

# Path to your RootsMagic media folder (REQUIRED)
RM_MEDIA_ROOT_DIRECTORY=/Users/yourname/Genealogy/RootsMagic/Files

# SQLite ICU extension (usually works as-is)
SQLITE_ICU_EXTENSION=./sqlite-extension/icu.dylib
```

### Optional: Configure AI Features

For census image transcription, add an API key:

```bash
# Option 1: Anthropic Claude (recommended)
ANTHROPIC_API_KEY=sk-ant-xxxxx

# Option 2: OpenAI
OPENAI_API_KEY=sk-proj-xxxxx
```

---

## Step 3: Set Up Chrome for FamilySearch

RMCitecraft connects to Chrome to access FamilySearch. You must start Chrome with remote debugging enabled.

### Create a Chrome Launch Script

Save this as `start-chrome.sh` in your home directory:

```bash
#!/bin/bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --no-first-run \
  --user-data-dir=~/.chrome-debug-profile
```

Make it executable:

```bash
chmod +x ~/start-chrome.sh
```

### Start Chrome and Log Into FamilySearch

1. Run `~/start-chrome.sh` from Terminal
2. Navigate to [familysearch.org](https://www.familysearch.org)
3. Sign in with your FamilySearch account
4. **Keep this Chrome window open** while using RMCitecraft

> **Important**: RMCitecraft uses your existing FamilySearch session. If you're logged out, you'll need to log back in.

---

## Step 4: Prepare Your Database

### Critical: Work on a Copy

RMCitecraft modifies your database. **Always work on a copy**, not your production file.

1. **Close RootsMagic** completely
2. **Copy your database** to the `data/` folder:
   ```bash
   cp "/path/to/your/Family Tree.rmtree" data/working.rmtree
   ```
3. Update `.env` to point to the copy:
   ```bash
   RM_DATABASE_PATH=data/working.rmtree
   ```

### Verify Database Connection

```bash
uv run python sqlite-extension/python_example.py
```

You should see output confirming the ICU extension loaded and RMNOCASE collation works.

---

## Step 5: Start RMCitecraft

### Start the Application

```bash
uv run python src/rmcitecraft/main.py
```

Or use the CLI:

```bash
rmcitecraft start
```

A browser window will open with the RMCitecraft interface.

### First-Time Orientation

The interface has several tabs:

| Tab | Purpose |
|-----|---------|
| **Citation Manager** | Browse and process census citations |
| **Batch Processing** | Run automated batch operations |
| **Dashboard** | Monitor progress and view analytics |
| **Settings** | Configure application options |

---

## Step 6: Process Your First Citation

### Find Unprocessed Citations

1. Go to the **Citation Manager** tab
2. Select a census year (e.g., 1930)
3. Filter by "Incomplete" to see citations needing processing

### What Makes a Citation "Incomplete"?

RMCitecraft looks for citations that:
- Have a FamilySearch URL but no formatted footnote
- Are missing required fields (ED, sheet number, etc.)
- Have identical footnote and short footnote (not yet differentiated)

### Process a Citation

1. Click on a citation to select it
2. Review the extracted data
3. Fill in any missing fields
4. Click "Save" to write the formatted citation to your database

---

## Understanding RMCitecraft's Assumptions

### Source Name Format

RMCitecraft expects census sources to be named in this format:

```
Fed Census: YYYY, State, County [citing details] Surname, GivenName
```

Examples:
- `Fed Census: 1930, Pennsylvania, Greene [citing ED 30-17, sheet 13-A] Iams, George B`
- `Fed Census: 1950, Ohio, Stark [] Adams, Verne`

> **Note**: Citations created from FamilySearch hints in RootsMagic follow this pattern automatically.

### Citation Style

RMCitecraft formats citations following *Evidence Explained* conventions with some specific choices. See [Citation Style Guide](../reference/CITATION-STYLE-GUIDE.md) for details.

---

## Next Steps

- **[Census Batch Workflow](CENSUS-BATCH-WORKFLOW.md)** - Process multiple citations at once
- **[Image Workflow](IMAGE-WORKFLOW.md)** - Download and organize census images
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions
- **[FAQ](FAQ.md)** - Frequently asked questions

---

## Getting Help

- **GitHub Issues**: [Report bugs or request features](https://github.com/miams/RMCitecraft/issues)
- **Documentation**: Browse the `docs/` folder for detailed guides
- **Citation Style Questions**: See [Citation Style Guide](../reference/CITATION-STYLE-GUIDE.md)

---

## Quick Reference

### Start Chrome for FamilySearch
```bash
~/start-chrome.sh
```

### Start RMCitecraft
```bash
cd /path/to/RMCitecraft
uv run python src/rmcitecraft/main.py
```

### Stop RMCitecraft
```bash
rmcitecraft stop
```

### Check Status
```bash
rmcitecraft status
```

---

**Document Version**: 1.0
**Last Updated**: 2025-12-30
