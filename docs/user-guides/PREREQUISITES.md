---
priority: essential
topics: [setup, installation, requirements]
---

# Prerequisites for RMCitecraft

**For**: New users preparing their system for RMCitecraft
**Time to Complete**: 10-20 minutes

## Overview

RMCitecraft requires several components to be installed and configured before first use. This guide walks you through each requirement.

---

## System Requirements

### Hardware

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Processor | Intel or Apple Silicon | Apple Silicon (M1/M2/M3) |
| Memory | 8 GB RAM | 16 GB RAM |
| Storage | 500 MB free | 2 GB+ (for census images) |
| Display | 1280x720 | 1920x1080+ |

### Operating System

- **macOS**: 11.0 (Big Sur) or later
- **Windows**: Not currently supported (planned for future release)
- **Linux**: Not currently supported

---

## Required Software

### 1. Python 3.11 or Later

**Check if installed:**
```bash
python3 --version
```

Expected output: `Python 3.11.x` or higher

**If not installed:**

macOS users can install via Homebrew:
```bash
brew install python@3.11
```

Or download from [python.org](https://www.python.org/downloads/).

### 2. UV Package Manager

UV is a fast Python package installer that RMCitecraft uses for dependency management.

**Install UV:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Restart your terminal** after installation.

**Verify installation:**
```bash
uv --version
```

### 3. Git

**Check if installed:**
```bash
git --version
```

**If not installed:**
```bash
# macOS (Xcode Command Line Tools)
xcode-select --install
```

### 4. Google Chrome

Chrome is required for FamilySearch automation. RMCitecraft connects to a running Chrome instance via the DevTools Protocol.

**Download**: [google.com/chrome](https://www.google.com/chrome/)

---

## Required Accounts

### FamilySearch Account

You need a free FamilySearch account to access census records.

1. Go to [familysearch.org](https://www.familysearch.org)
2. Click "Create Account" if you don't have one
3. Complete the registration process

**Note**: RMCitecraft uses your existing FamilySearch session in Chrome. You'll log in once and the automation uses that session.

---

## Optional Components

### LLM API Key (For AI Transcription)

If you want RMCitecraft to automatically transcribe census images using AI, you'll need an API key from one of these providers:

#### Option A: Anthropic Claude (Recommended)

1. Sign up at [anthropic.com](https://www.anthropic.com)
2. Navigate to API Keys in your account
3. Create a new API key
4. Copy the key (starts with `sk-ant-`)

**Approximate cost**: $0.01-0.05 per census page transcription

#### Option B: OpenAI GPT-4

1. Sign up at [platform.openai.com](https://platform.openai.com)
2. Navigate to API Keys
3. Create a new API key
4. Copy the key (starts with `sk-proj-`)

**Approximate cost**: $0.03-0.10 per census page transcription

### OpenRouter (Multi-Provider)

For access to multiple LLM providers through a single API:

1. Sign up at [openrouter.ai](https://openrouter.ai)
2. Add credits to your account
3. Create an API key

---

## RootsMagic Database Preparation

### Supported Versions

RMCitecraft works with:
- RootsMagic 8
- RootsMagic 9
- RootsMagic 10
- RootsMagic 11

### Database Location

Find your RootsMagic database file:

1. Open RootsMagic
2. Note the database filename in the title bar
3. Common locations:
   - `~/Documents/RootsMagic/`
   - `~/Genealogy/`
   - Custom location you specified

The file extension is `.rmtree`.

### Critical: Work on a Copy

RMCitecraft modifies your database. **Always work on a copy**:

```bash
# Create working directory
mkdir -p ~/RMCitecraft/data

# Copy your database
cp "/path/to/Your Family.rmtree" ~/RMCitecraft/data/working.rmtree
```

After processing, manually compare and merge changes back to your production database.

---

## Chrome Configuration for FamilySearch

RMCitecraft connects to Chrome via the DevTools Protocol. You must start Chrome with remote debugging enabled.

### Create Launch Script

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

### First-Time Setup

1. Run the script:
   ```bash
   ~/start-chrome.sh
   ```

2. A new Chrome window opens with a fresh profile

3. Navigate to [familysearch.org](https://www.familysearch.org)

4. Sign in with your FamilySearch account

5. **Keep this Chrome window open** while using RMCitecraft

### Why a Separate Chrome Profile?

The `--user-data-dir` flag creates a separate profile:
- Keeps your regular browsing separate
- Stores FamilySearch login persistently
- Avoids conflicts with existing Chrome extensions

---

## Directory Structure

RMCitecraft expects this directory structure for media files:

```
~/Genealogy/RootsMagic/Files/
├── Records - Census/
│   ├── 1790 Federal/
│   ├── 1800 Federal/
│   ├── 1850 Federal/
│   ├── ...
│   ├── 1940 Federal/
│   └── 1950 Federal/
└── Records - Find a Grave/
    └── (organized by cemetery)
```

RMCitecraft will create these directories automatically when processing records.

---

## Verification Checklist

Before proceeding to installation, verify:

- [ ] macOS 11.0 or later
- [ ] Python 3.11+ installed (`python3 --version`)
- [ ] UV package manager installed (`uv --version`)
- [ ] Git installed (`git --version`)
- [ ] Google Chrome installed
- [ ] FamilySearch account created
- [ ] RootsMagic database location known
- [ ] Working copy of database created
- [ ] Chrome launch script created

---

## Common Issues

### "command not found: uv"

Restart your terminal after installing UV, or add to your PATH:
```bash
source ~/.bashrc  # or ~/.zshrc on newer macOS
```

### Python version too old

If your system Python is older than 3.11:
```bash
# Install specific version with Homebrew
brew install python@3.11

# Use it explicitly
python3.11 --version
```

### Chrome won't start with debugging

Check if Chrome is already running:
```bash
pkill -f "Google Chrome"
~/start-chrome.sh
```

### Can't find RootsMagic database

Search for `.rmtree` files:
```bash
find ~ -name "*.rmtree" 2>/dev/null
```

---

## Next Steps

Once all prerequisites are met, proceed to:

- **[Getting Started Guide](GETTING-STARTED.md)** - Install and configure RMCitecraft

---

**Document Version**: 1.0
**Last Updated**: 2025-12-30
