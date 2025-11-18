# Claude Code Session Context

This file helps preserve context between Claude Code sessions.

## Current State (2025-11-18)

### Recent Work Completed
- ✅ Implemented comprehensive test suite (P0-P2 priorities)
- ✅ Added 105 new tests (285 total, was 180)
- ✅ Fixed database API (added `read_only` parameter to `connect_rmtree()`)
- ✅ Created test gap analysis document
- ✅ All commits pushed to main

### Test Coverage Added
- **P0 (Critical)**: MultimediaTable/MediaLinkTable integrity, image records, path conversion
- **P1 (High)**: Database error handling, edge cases
- **P2 (Medium)**: LLM config, photo classifier, Find a Grave improvements

### Test Status
- Total: 285 tests
- Passing: 155
- Failing: 50 (mostly minor mocking issues)

## Next Steps

### Immediate Tasks
1. **Configure API Keys** - User wants to set up:
   - Claude (Anthropic) API key
   - OpenAI API key
   - OpenRouter API key
   - Ollama local models

2. **Fix Remaining Test Failures** (50 tests)
   - LLM mocking import paths
   - ImageRepository API parameters
   - Photo classifier keyword ordering

3. **Complete P1 Tests** (Pending)
   - UI image download integration
   - End-to-end image download workflow

### Configuration Files
- `.env` - Active configuration in project root (API keys configured)
- `config/.env.example` - Template with all required variables
- `.gitignore` - Already excludes `.env` and API keys

### Key Commands

**Start with permissions:**
```bash
cd /Users/miams/Code/RMCitecraft
claude-code
```

**Start without permission prompts:**
```bash
claude-code --dangerously-skip-permissions
# Or:
export CLAUDE_CODE_DANGEROUSLY_SKIP_PERMISSIONS=true
claude-code
```

**Check recent work:**
```bash
git log --oneline -10
git status
pytest --co -q  # Count tests
```

## Project Context

### Architecture
- Desktop app (macOS, NiceGUI native mode)
- Database: RootsMagic SQLite with RMNOCASE collation
- LLM: Multi-provider support (OpenRouter, Claude, OpenAI, Ollama)
- Package manager: UV (required)

### Key Files
- `CLAUDE.md` - Development guidance for Claude Code
- `AGENTS.md` - Machine-readable instructions
- `docs/TEST-GAP-ANALYSIS.md` - Test priorities and gaps
- `docs/architecture/LLM-PROVIDERS.md` - LLM integration documentation

### Database Safety
- Working copy: `data/Iiams.rmtree` (excluded from git)
- Always use `connect_rmtree()` for RMNOCASE collation
- Default: `read_only=True` for safety
- Use `transaction()` context for writes

## API Key Configuration Template

When ready to configure, edit `.env` in project root:

```env
# Anthropic (Claude)
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_MODEL=claude-3-5-sonnet-20250110

# OpenAI
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4-turbo-preview

# OpenRouter (multi-model gateway)
OPENROUTER_API_KEY=sk-or-your-key-here
OPENROUTER_SITE_URL=https://rmcitecraft.app
OPENROUTER_APP_NAME=RMCitecraft

# Ollama (local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# Default provider
DEFAULT_LLM_PROVIDER=openrouter  # or claude, openai, ollama
```

## User Preferences

- Uses UV package manager
- Wants comprehensive testing
- Prefers concise communication
- macOS M3 Pro environment

---

**Last Updated:** 2025-11-18 (Session with test implementation)

**Note:** This file should be updated at the end of each significant session to help future Claude sessions pick up context quickly.
