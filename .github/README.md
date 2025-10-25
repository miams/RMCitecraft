# GitHub Actions Workflows

This directory contains automated workflows for the RMCitecraft project.

## Workflow Execution Order

The documentation workflows execute in the following order:

1. **Documentation Refactoring** (`refactor-docs.yml`) - Reorganizes files into clean structure
2. **Documentation Map Generation** (`generate-docs-map.yml`) - Generates comprehensive index

This ensures the documentation map always reflects the current, organized structure.

---

## Documentation Refactoring

### Workflow: `refactor-docs.yml`

Automatically reorganizes documentation files into a clean directory structure with minimal files in the root directory.

**Purpose:**
- Maintains clean root directory (only `README.md`, `CLAUDE.md`, `AGENTS.md`, `PRD.md`, `QUICKSTART.md`, `claude_code_docs_map.md`)
- Organizes documentation into logical subdirectories
- Automatically updates all internal references when files move
- Prevents documentation sprawl

**Triggers:**
- **Push to main/dev**: When markdown files are modified
- **Pull requests**: Generates dry-run preview
- **Manual**: Via workflow dispatch with optional dry-run mode

**How It Works:**

1. **Categorization** - Files are organized into:
   - `docs/project/` - Project plans and roadmaps
   - `docs/archive/` - Weekly summaries and historical progress
   - `docs/implementation/` - Bug fixes, optimizations, feature support
   - `docs/architecture/` - Design decisions, LLM architecture
   - `docs/analysis/` - Census data analysis documents
   - `docs/database/` - Database integration guides
   - `docs/extension/` - Browser extension documentation
   - `docs/reference/` - Technical reference (existing)
   - `docs/misc/` - Uncategorized documentation

2. **Reference Detection** - Scans all files (`.md`, `.py`, `.yml`, `.yaml`, `.toml`, `.txt`, `.sh`) for:
   - Markdown links: `[text](path/to/doc.md)`
   - Relative file paths
   - GitHub URLs

3. **Reference Updates** - Automatically updates all references to moved files

4. **File Moves** - Relocates files to target directories

5. **Summary Output** - Prints detailed change log to workflow console

**Outputs:**

On **main/dev branch pushes**:
- Commits reorganized files to appropriate branch (gitflow-aware)
- Updates all references automatically
- Triggers documentation map generation
- Includes `[skip ci]` to prevent workflow loops
- Logs detailed summary to GitHub Actions console

On **pull requests**:
- Runs in dry-run mode (preview only)
- Posts comment with proposed changes
- Detailed changes visible in workflow logs

**Gitflow Support:**
- Detects if `dev` branch exists
- Commits to `main` if working in main-only workflow
- Commits to `dev` if gitflow is enabled

**Script Location:**
`.github/scripts/refactor_docs.py`

**Customization:**

To modify categorization rules, edit `categorize_file()` method in the script:

```python
def categorize_file(self, file_path: Path) -> Tuple[Path, str]:
    """Determine the target location for a documentation file."""
    # Add custom categorization logic here
```

To change root allowlist:

```python
ROOT_ALLOWLIST = {
    'README.md',
    'CLAUDE.md',
    'AGENTS.md',
    'claude_code_docs_map.md',
    'QUICKSTART.md',
    'PRD.md',
}
```

**Manual Execution:**

```bash
# Dry-run (preview only)
python3 .github/scripts/refactor_docs.py --dry-run

# Execute refactoring
python3 .github/scripts/refactor_docs.py
```

**Permissions:**
- `contents: write` - To commit reorganized files
- `pull-requests: write` - To post PR comments

---

## Documentation Map Generator

### Workflow: `generate-docs-map.yml`

Automatically generates and maintains a comprehensive documentation map (`claude_code_docs_map.md`) that indexes all markdown files in the repository with their heading structure.

**Purpose:**
- Provides LLMs (like Claude Code) with a quick overview of all project documentation
- Helps developers navigate the documentation structure
- Automatically stays up-to-date with documentation changes

**Triggers:**
- **Workflow dispatch**: Triggered automatically by refactor-docs workflow
- **Pull requests**: When markdown files are modified (generates preview)
- **Scheduled**: Weekly on Sundays at midnight UTC
- **Manual**: Via workflow dispatch for testing

**How It Works:**
1. Scans all `.md` files in the repository
2. Extracts headings from each document
3. Categorizes documents into logical groups:
   - Getting Started
   - Project Overview
   - Architecture & Design
   - Database Reference
   - Database Integration
   - Browser Extension
   - Implementation Notes
   - Development Progress
4. Generates `DOCS_MAP.md` with:
   - GitHub links to each document
   - Hierarchical heading structure
   - Auto-generated metadata (timestamp)

**Outputs:**

On **main branch pushes**:
- Commits updated `claude_code_docs_map.md` automatically (with `[skip ci]` to prevent loops)

On **pull requests**:
- Uploads `claude_code_docs_map.md` as workflow artifact
- Posts comment with preview of changes

**Script Location:**
`.github/scripts/generate_docs_map.py`

**Customization:**

To modify document categorization, edit the `categorize_document()` function in the Python script:

```python
def categorize_document(relative_path: str) -> str:
    """Categorize a document based on its path and name."""
    # Add custom categorization logic here
```

**Manual Execution:**

Run locally to test changes:
```bash
python3 .github/scripts/generate_docs_map.py
```

**Permissions:**
- `contents: write` - To commit changes to main branch
- `pull-requests: write` - To post PR comments

## Adding New Workflows

When adding new workflows to this directory:

1. Create a descriptive YAML filename (e.g., `my-workflow.yml`)
2. Add comprehensive inline comments explaining workflow purpose
3. Document the workflow in this README
4. Test workflow with `workflow_dispatch` trigger before enabling automatic triggers
5. Use appropriate permissions (principle of least privilege)

## Workflow Best Practices

- **Use latest actions versions**: Keep `@v4`, `@v5` updated
- **Cache dependencies**: Use caching for faster builds
- **Conditional execution**: Use `if:` to prevent unnecessary runs
- **Commit messages**: Include `[skip ci]` for bot commits to prevent loops
- **Artifacts**: Upload important outputs for debugging
- **Job summaries**: Use `$GITHUB_STEP_SUMMARY` for visibility
- **Error handling**: Use `if: always()` for cleanup steps
