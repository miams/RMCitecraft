#!/usr/bin/env python3
"""
Check Documentation Frontmatter

Validates that all markdown files have required frontmatter with priority field.
Used by GitHub Actions to enforce frontmatter standards on PRs.

Exit codes:
- 0: All files have valid frontmatter
- 1: Some files are missing frontmatter

Usage:
    python3 .github/scripts/check_frontmatter.py           # Check all files
    python3 .github/scripts/check_frontmatter.py file1.md file2.md  # Check specific files
"""

import sys
import re
from pathlib import Path
from typing import List, Tuple


# Directories to skip
EXCLUDE_DIRS = {'.git', '.venv', 'node_modules', '.github', '.pytest_cache'}

# Files that don't need frontmatter
EXCLUDE_FILES = {'claude_code_docs_map.md', 'FULL_INDEX.md', 'CHANGELOG.md', 'LICENSE.md'}

# Valid priority values
VALID_PRIORITIES = {'essential', 'reference', 'archive'}


def has_valid_frontmatter(filepath: Path) -> Tuple[bool, str]:
    """Check if a file has valid frontmatter.

    Returns: (is_valid, message)
    """
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception as e:
        return False, f"Could not read file: {e}"

    # Check for frontmatter start
    if not content.startswith('---\n'):
        return False, "Missing frontmatter (no opening ---)"

    # Find closing ---
    end_match = re.search(r'\n---\n', content[4:])
    if not end_match:
        return False, "Malformed frontmatter (no closing ---)"

    yaml_content = content[4:4 + end_match.start()]

    # Check for priority field
    priority_match = re.search(r'^priority:\s*(\w+)', yaml_content, re.MULTILINE)
    if not priority_match:
        return False, "Missing 'priority' field in frontmatter"

    priority = priority_match.group(1).strip()
    if priority not in VALID_PRIORITIES:
        return False, f"Invalid priority '{priority}' (must be: {', '.join(VALID_PRIORITIES)})"

    return True, f"Valid frontmatter (priority: {priority})"


def find_markdown_files(root: Path) -> List[Path]:
    """Find all markdown files to check."""
    md_files = []

    for md_file in root.glob('**/*.md'):
        # Skip excluded directories
        if any(part in EXCLUDE_DIRS for part in md_file.parts):
            continue
        # Skip excluded files
        if md_file.name in EXCLUDE_FILES:
            continue
        md_files.append(md_file)

    return sorted(md_files)


def main():
    # Determine files to check
    if len(sys.argv) > 1:
        # Check specific files passed as arguments
        files = [Path(f) for f in sys.argv[1:] if f.endswith('.md')]
    else:
        # Check all files in repo
        script_dir = Path(__file__).parent
        repo_root = script_dir.parent.parent
        files = find_markdown_files(repo_root)

    if not files:
        print("No markdown files to check")
        sys.exit(0)

    print(f"Checking {len(files)} markdown files for frontmatter...\n")

    errors = []
    valid_count = 0

    for filepath in files:
        is_valid, message = has_valid_frontmatter(filepath)

        if is_valid:
            valid_count += 1
            print(f"✓ {filepath.name}: {message}")
        else:
            errors.append((filepath, message))
            print(f"✗ {filepath}: {message}")

    print(f"\n{'='*60}")
    print(f"Results: {valid_count} valid, {len(errors)} missing/invalid")

    if errors:
        print("\n## Files Missing Frontmatter\n")
        print("Add frontmatter to these files:")
        print("```yaml")
        print("---")
        print("priority: reference  # or: essential, archive")
        print("topics: []")
        print("---")
        print("```\n")

        for filepath, message in errors:
            print(f"- {filepath}: {message}")

        print("\n### Auto-fix Command")
        print("Run this to add frontmatter automatically:")
        print("```bash")
        print("python3 .github/scripts/add_frontmatter.py")
        print("```")

        sys.exit(1)

    print("\nAll files have valid frontmatter!")
    sys.exit(0)


if __name__ == '__main__':
    main()
