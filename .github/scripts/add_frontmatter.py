#!/usr/bin/env python3
"""
Add Frontmatter to Documentation Files

This script analyzes all markdown files and adds priority-based frontmatter
for the documentation map generator to use.

Priority levels:
- essential: Core docs that should always appear in claude_code_docs_map.md
- reference: Detailed docs that appear in docs/FULL_INDEX.md
- archive: Historical/superseded docs, excluded from both indexes

Usage:
    python3 .github/scripts/add_frontmatter.py --dry-run  # Preview changes
    python3 .github/scripts/add_frontmatter.py            # Apply changes
    python3 .github/scripts/add_frontmatter.py --report   # Generate classification report
"""

import re
import argparse
from pathlib import Path
from datetime import datetime
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class Classification:
    """Document classification result."""
    priority: str  # essential, reference, archive
    topics: list[str]
    reason: str


# Documents that should always be essential (by filename pattern)
# Note: Only exact matches; files like '.envrc.README.md' will NOT match 'README.md'
ESSENTIAL_PATTERNS = [
    'CLAUDE.md',
    'AGENTS.md',
    'PRD.md',
    'QUICKSTART.md',
    'schema-reference.md',
    'DATABASE_PATTERNS.md',
    'DATABASE_TESTING.md',
    'BATCH_STATE_DATABASE_SCHEMA.md',
    'CENSUS_EXTRACTION_DATABASE_SCHEMA.md',
    'CENSUS_BATCH_PROCESSING_ARCHITECTURE.md',
    'BATCH_PROCESSING_ARCHITECTURE.md',
    'CENSUS_FORM_RENDERING.md',
]

# Root-level README.md is essential, but not subdirectory READMEs
ESSENTIAL_ROOT_FILES = ['README.md']

# Patterns that indicate archive status
ARCHIVE_PATTERNS = [
    r'WEEK\d+-',  # Weekly summaries
    r'_\d{8}_\d{6}',  # Timestamped files (YYYYMMDD_HHMMSS)
    r'census_batch_\d{4}_',  # Census batch session logs
]

# Directory-based classifications
ARCHIVE_DIRS = ['docs/archive', 'docs/misc']
REFERENCE_DIRS = ['docs/reference', 'docs/architecture', 'docs/implementation']

# Topic extraction patterns
TOPIC_PATTERNS = {
    'database': ['database', 'schema', 'sqlite', 'rmtree', 'table'],
    'census': ['census', '1950', '1940', '1930', '1900', 'enumeration'],
    'citation': ['citation', 'footnote', 'bibliography', 'evidence explained'],
    'batch': ['batch', 'processing', 'workflow'],
    'findagrave': ['findagrave', 'find a grave', 'memorial', 'burial'],
    'testing': ['test', 'pytest', 'e2e', 'integration'],
    'ui': ['ui', 'nicegui', 'dashboard', 'component'],
    'automation': ['playwright', 'browser', 'familysearch', 'automation'],
}


def extract_topics(content: str, filepath: str) -> list[str]:
    """Extract relevant topics from document content and path."""
    topics = []
    combined = (content + ' ' + filepath).lower()

    for topic, keywords in TOPIC_PATTERNS.items():
        if any(kw in combined for kw in keywords):
            topics.append(topic)

    return topics[:5]  # Limit to 5 topics


def classify_document(filepath: Path, content: str) -> Classification:
    """Classify a document based on path, filename, and content."""
    filename = filepath.name
    rel_path = str(filepath)

    # Check essential patterns first (exact filename match only)
    for pattern in ESSENTIAL_PATTERNS:
        if filename == pattern:
            return Classification(
                priority='essential',
                topics=extract_topics(content, rel_path),
                reason=f"Matches essential pattern: {pattern}"
            )

    # Root-level essential files (README.md at repo root only)
    for pattern in ESSENTIAL_ROOT_FILES:
        if filename == pattern and '/' not in rel_path:
            return Classification(
                priority='essential',
                topics=extract_topics(content, rel_path),
                reason=f"Root-level essential file: {pattern}"
            )

    # Check archive patterns
    for pattern in ARCHIVE_PATTERNS:
        if re.search(pattern, filename):
            return Classification(
                priority='archive',
                topics=extract_topics(content, rel_path),
                reason=f"Matches archive pattern: {pattern}"
            )

    # Check archive directories
    for archive_dir in ARCHIVE_DIRS:
        if archive_dir in rel_path:
            return Classification(
                priority='archive',
                topics=extract_topics(content, rel_path),
                reason=f"Located in archive directory: {archive_dir}"
            )

    # Check reference directories
    for ref_dir in REFERENCE_DIRS:
        if ref_dir in rel_path:
            return Classification(
                priority='reference',
                topics=extract_topics(content, rel_path),
                reason=f"Located in reference directory: {ref_dir}"
            )

    # Default to reference for docs/ directory
    if 'docs/' in rel_path:
        return Classification(
            priority='reference',
            topics=extract_topics(content, rel_path),
            reason="Default classification for docs/ directory"
        )

    # Root-level docs default to essential (only true root, not subdirectory READMEs)
    if filepath.parent.name in ['', 'RMCitecraft'] and 'docs/' not in rel_path:
        return Classification(
            priority='essential',
            topics=extract_topics(content, rel_path),
            reason="Root-level documentation"
        )

    # Subdirectory READMEs are reference, not essential
    if filename == 'README.md' and 'docs/' in rel_path:
        return Classification(
            priority='reference',
            topics=extract_topics(content, rel_path),
            reason="Subdirectory README"
        )

    return Classification(
        priority='reference',
        topics=extract_topics(content, rel_path),
        reason="Default fallback classification"
    )


def has_frontmatter(content: str) -> bool:
    """Check if document already has YAML frontmatter."""
    return content.startswith('---\n')


def extract_existing_frontmatter(content: str) -> Tuple[Optional[dict], str]:
    """Extract existing frontmatter and return (frontmatter_dict, remaining_content)."""
    if not has_frontmatter(content):
        return None, content

    # Find the closing ---
    lines = content.split('\n')
    end_idx = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == '---':
            end_idx = i
            break

    if end_idx is None:
        return None, content

    # Parse frontmatter (simple key: value parsing)
    frontmatter = {}
    for line in lines[1:end_idx]:
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            # Handle list values
            if value.startswith('[') and value.endswith(']'):
                value = [v.strip().strip('"\'') for v in value[1:-1].split(',')]
            frontmatter[key] = value

    remaining = '\n'.join(lines[end_idx + 1:]).lstrip('\n')
    return frontmatter, remaining


def generate_frontmatter(classification: Classification) -> str:
    """Generate YAML frontmatter string."""
    topics_str = ', '.join(classification.topics) if classification.topics else ''

    frontmatter = f"""---
priority: {classification.priority}
topics: [{topics_str}]
---

"""
    return frontmatter


def process_file(filepath: Path, dry_run: bool = True) -> Tuple[str, Classification, bool]:
    """Process a single file, adding or updating frontmatter.

    Returns: (action_taken, classification, was_modified)
    """
    content = filepath.read_text(encoding='utf-8')

    existing_fm, body = extract_existing_frontmatter(content)
    classification = classify_document(filepath, body)

    if existing_fm:
        # Check if priority already matches
        if existing_fm.get('priority') == classification.priority:
            return "unchanged (frontmatter exists)", classification, False
        else:
            # Update priority but preserve other fields
            action = f"updated priority: {existing_fm.get('priority')} -> {classification.priority}"
    else:
        action = f"added frontmatter (priority: {classification.priority})"
        body = content

    # Generate new content with frontmatter
    new_frontmatter = generate_frontmatter(classification)
    new_content = new_frontmatter + body

    if not dry_run:
        filepath.write_text(new_content, encoding='utf-8')

    return action, classification, True


def find_markdown_files(root: Path) -> list[Path]:
    """Find all markdown files, excluding certain directories."""
    exclude_dirs = {'.git', '.venv', 'node_modules', '.github', '.pytest_cache'}

    md_files = []
    for md_file in root.glob('**/*.md'):
        # Skip excluded directories
        if any(part in exclude_dirs for part in md_file.parts):
            continue
        # Skip the generated docs map itself
        if md_file.name == 'claude_code_docs_map.md':
            continue
        # Skip FULL_INDEX.md (generated file)
        if md_file.name == 'FULL_INDEX.md':
            continue
        md_files.append(md_file)

    return sorted(md_files)


def generate_report(results: list[Tuple[Path, str, Classification, bool]]) -> str:
    """Generate a classification report."""
    lines = [
        "# Documentation Classification Report",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
    ]

    # Count by priority
    counts = {'essential': 0, 'reference': 0, 'archive': 0}
    for _, _, classification, _ in results:
        counts[classification.priority] += 1

    lines.append(f"| Priority | Count |")
    lines.append(f"|----------|-------|")
    for priority, count in counts.items():
        lines.append(f"| {priority} | {count} |")
    lines.append("")

    # List by priority
    for priority in ['essential', 'reference', 'archive']:
        lines.append(f"## {priority.title()} Documents ({counts[priority]})")
        lines.append("")

        for filepath, action, classification, modified in results:
            if classification.priority == priority:
                rel_path = filepath.relative_to(filepath.parents[len(filepath.parents)-2])
                topics = ', '.join(classification.topics) if classification.topics else 'none'
                lines.append(f"- **{rel_path}**")
                lines.append(f"  - Topics: {topics}")
                lines.append(f"  - Reason: {classification.reason}")
        lines.append("")

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Add frontmatter to documentation files')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without modifying files')
    parser.add_argument('--report', action='store_true', help='Generate classification report')
    parser.add_argument('--report-file', type=str, default='/tmp/docs_classification_report.md',
                        help='Output file for classification report')
    args = parser.parse_args()

    # Find repository root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent.parent

    print(f"Scanning for markdown files in: {repo_root}")
    md_files = find_markdown_files(repo_root)
    print(f"Found {len(md_files)} markdown files")

    if args.dry_run:
        print("\n=== DRY RUN MODE - No files will be modified ===\n")

    results = []
    modified_count = 0

    for filepath in md_files:
        rel_path = filepath.relative_to(repo_root)
        action, classification, modified = process_file(filepath, dry_run=args.dry_run)
        results.append((filepath, action, classification, modified))

        if modified:
            modified_count += 1
            status = "[WOULD MODIFY]" if args.dry_run else "[MODIFIED]"
        else:
            status = "[UNCHANGED]"

        print(f"{status} {rel_path}: {action}")

    print(f"\n{'Would modify' if args.dry_run else 'Modified'}: {modified_count} files")

    # Count by priority
    counts = {'essential': 0, 'reference': 0, 'archive': 0}
    for _, _, classification, _ in results:
        counts[classification.priority] += 1

    print(f"\nClassification summary:")
    print(f"  Essential: {counts['essential']}")
    print(f"  Reference: {counts['reference']}")
    print(f"  Archive:   {counts['archive']}")

    if args.report:
        report = generate_report(results)
        report_path = Path(args.report_file)
        report_path.write_text(report, encoding='utf-8')
        print(f"\nClassification report written to: {report_path}")


if __name__ == '__main__':
    main()
