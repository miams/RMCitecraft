#!/usr/bin/env python3
"""
Generate RMCitecraft Documentation Maps

This script scans all Markdown files with frontmatter and creates two documentation maps:

1. claude_code_docs_map.md (compact, ~3k tokens)
   - Essential docs only (priority: essential)
   - H2 headings only (no deep nesting)
   - Designed for LLM context efficiency

2. docs/FULL_INDEX.md (comprehensive)
   - Essential + Reference docs
   - Full heading tree
   - For human developers

Archive docs (priority: archive) are excluded from both.
"""

import re
import yaml
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class Heading:
    """Represents a heading in a markdown file."""
    level: int
    text: str
    line_number: int


@dataclass
class Frontmatter:
    """Parsed frontmatter from a markdown file."""
    priority: str  # essential, reference, archive
    topics: List[str]

    @classmethod
    def default(cls) -> 'Frontmatter':
        """Return default frontmatter for files without it."""
        return cls(priority='reference', topics=[])


@dataclass
class DocumentEntry:
    """Represents a documentation file with its metadata."""
    path: Path
    relative_path: str
    title: str
    headings: List[Heading]
    category: str
    frontmatter: Frontmatter


def parse_frontmatter(content: str) -> Tuple[Optional[Frontmatter], str]:
    """Parse YAML frontmatter from content.

    Returns: (frontmatter, remaining_content)
    """
    if not content.startswith('---\n'):
        return None, content

    # Find the closing ---
    end_match = re.search(r'\n---\n', content[4:])
    if not end_match:
        return None, content

    yaml_content = content[4:4 + end_match.start()]
    remaining = content[4 + end_match.end():]

    try:
        data = yaml.safe_load(yaml_content)
        if not isinstance(data, dict):
            return None, content

        priority = data.get('priority', 'reference')
        topics = data.get('topics', [])
        if isinstance(topics, str):
            topics = [t.strip() for t in topics.split(',')]

        return Frontmatter(priority=priority, topics=topics), remaining
    except yaml.YAMLError:
        return None, content


def extract_headings(file_path: Path) -> Tuple[List[Heading], Frontmatter]:
    """Extract all headings and frontmatter from a markdown file."""
    headings = []
    frontmatter = Frontmatter.default()

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse frontmatter first
        parsed_fm, remaining = parse_frontmatter(content)
        if parsed_fm:
            frontmatter = parsed_fm

        # Extract headings from remaining content
        for line_num, line in enumerate(remaining.split('\n'), 1):
            match = re.match(r'^(#{1,6})\s+(.+)$', line.strip())
            if match:
                level = len(match.group(1))
                text = match.group(2).strip()
                headings.append(Heading(level, text, line_num))

    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")

    return headings, frontmatter


def categorize_document(relative_path: str, frontmatter: Frontmatter) -> str:
    """Categorize a document based on its path and frontmatter topics."""
    path_lower = relative_path.lower()

    # Root-level categorization
    if path_lower in ['readme.md', 'quickstart.md']:
        return 'Getting Started'

    if path_lower in ['claude.md', 'agents.md', 'prd.md']:
        return 'Project Overview'

    # Directory-based categorization
    if 'docs/reference/' in path_lower:
        return 'Reference'

    if 'docs/architecture/' in path_lower:
        return 'Architecture'

    if 'docs/implementation/' in path_lower:
        return 'Implementation'

    if 'docs/analysis/' in path_lower:
        return 'Analysis'

    if 'docs/project/' in path_lower:
        return 'Project Planning'

    if 'docs/testing/' in path_lower or 'tests/' in path_lower:
        return 'Testing'

    if 'docs/user-guides/' in path_lower:
        return 'User Guides'

    if 'docs/database/' in path_lower or 'sqlite-extension/' in path_lower:
        return 'Database'

    if 'docs/archive/' in path_lower or 'docs/misc/' in path_lower:
        return 'Archive'

    # Topic-based fallback
    if frontmatter.topics:
        if 'database' in frontmatter.topics:
            return 'Database'
        if 'testing' in frontmatter.topics:
            return 'Testing'
        if 'census' in frontmatter.topics:
            return 'Census Processing'

    return 'Other'


def get_document_title(doc_path: Path, headings: List[Heading]) -> str:
    """Get the title of a document from its first H1 heading or filename."""
    for heading in headings:
        if heading.level == 1:
            return heading.text

    return doc_path.stem.replace('-', ' ').replace('_', ' ').title()


def scan_documentation(root_dir: Path) -> List[DocumentEntry]:
    """Scan all markdown files in the project."""
    docs = []
    exclude_dirs = {'.git', '.venv', 'node_modules', '.github', '.pytest_cache'}

    md_files = sorted(root_dir.glob('**/*.md'))

    for md_file in md_files:
        relative_path = md_file.relative_to(root_dir)

        # Skip excluded directories
        if any(part in exclude_dirs for part in relative_path.parts):
            continue

        # Skip generated files
        if md_file.name in ['claude_code_docs_map.md', 'FULL_INDEX.md']:
            continue

        headings, frontmatter = extract_headings(md_file)
        title = get_document_title(md_file, headings)
        category = categorize_document(str(relative_path), frontmatter)

        docs.append(DocumentEntry(
            path=md_file,
            relative_path=str(relative_path),
            title=title,
            headings=headings,
            category=category,
            frontmatter=frontmatter
        ))

    return docs


def format_heading_tree_compact(headings: List[Heading]) -> List[str]:
    """Format only H2 headings for compact output."""
    lines = []
    for heading in headings:
        if heading.level == 2:  # Only H2
            lines.append(f"- {heading.text}")
    return lines[:10]  # Limit to 10 headings max


def format_heading_tree_full(headings: List[Heading]) -> List[str]:
    """Format all headings (H2-H4) for full output."""
    lines = []
    for heading in headings:
        if heading.level == 1:
            continue  # Skip H1 (title)
        if heading.level > 4:
            continue  # Skip H5, H6

        indent = '  ' * (heading.level - 2)
        lines.append(f"{indent}- {heading.text}")
    return lines


def generate_compact_map(docs: List[DocumentEntry], github_base: str) -> str:
    """Generate compact documentation map for LLMs (essential docs only)."""
    # Filter to essential only
    essential_docs = [d for d in docs if d.frontmatter.priority == 'essential']

    lines = [
        "# RMCitecraft Documentation Map",
        "",
        "> **For LLMs**: This compact index contains essential docs only.",
        "> For complete documentation, see `docs/FULL_INDEX.md`.",
        f"> Last generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        f"**Essential docs**: {len(essential_docs)} | ",
        f"**Total docs**: {len(docs)} (use Glob/Grep for full search)",
        "",
    ]

    # Group by category
    categories: Dict[str, List[DocumentEntry]] = {}
    for doc in essential_docs:
        if doc.category not in categories:
            categories[doc.category] = []
        categories[doc.category].append(doc)

    # Define category order
    category_order = [
        'Getting Started',
        'Project Overview',
        'Reference',
        'Architecture',
        'Database',
        'Testing',
        'Other',
    ]

    sorted_categories = sorted(
        categories.keys(),
        key=lambda x: category_order.index(x) if x in category_order else 999
    )

    for category in sorted_categories:
        category_docs = sorted(categories[category], key=lambda x: x.relative_path)

        lines.append(f"## {category}")
        lines.append("")

        for doc in category_docs:
            github_url = f"{github_base}/{doc.relative_path}"
            topics = ', '.join(doc.frontmatter.topics) if doc.frontmatter.topics else ''

            lines.append(f"### [{doc.title}]({github_url})")
            if topics:
                lines.append(f"*Topics: {topics}*")
            lines.append("")

            # Compact heading tree (H2 only, max 10)
            heading_tree = format_heading_tree_compact(doc.headings)
            if heading_tree:
                lines.extend(heading_tree)
                lines.append("")

    return '\n'.join(lines)


def generate_full_index(docs: List[DocumentEntry], github_base: str) -> str:
    """Generate comprehensive index (essential + reference docs)."""
    # Filter out archive
    included_docs = [d for d in docs if d.frontmatter.priority != 'archive']

    lines = [
        "# RMCitecraft Full Documentation Index",
        "",
        "> Complete documentation index for developers.",
        "> For LLM-optimized compact map, see `claude_code_docs_map.md` in repo root.",
        f"> Last generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
    ]

    # Summary stats
    essential = len([d for d in docs if d.frontmatter.priority == 'essential'])
    reference = len([d for d in docs if d.frontmatter.priority == 'reference'])
    archive = len([d for d in docs if d.frontmatter.priority == 'archive'])

    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Priority | Count | Included |")
    lines.append(f"|----------|-------|----------|")
    lines.append(f"| Essential | {essential} | Yes |")
    lines.append(f"| Reference | {reference} | Yes |")
    lines.append(f"| Archive | {archive} | No |")
    lines.append("")

    # Group by category
    categories: Dict[str, List[DocumentEntry]] = {}
    for doc in included_docs:
        if doc.category not in categories:
            categories[doc.category] = []
        categories[doc.category].append(doc)

    # Define category order
    category_order = [
        'Getting Started',
        'Project Overview',
        'Reference',
        'Architecture',
        'Implementation',
        'Analysis',
        'Project Planning',
        'Database',
        'Testing',
        'User Guides',
        'Census Processing',
        'Other',
    ]

    sorted_categories = sorted(
        categories.keys(),
        key=lambda x: category_order.index(x) if x in category_order else 999
    )

    for category in sorted_categories:
        category_docs = sorted(categories[category], key=lambda x: x.relative_path)

        lines.append(f"## {category} ({len(category_docs)} docs)")
        lines.append("")

        for doc in category_docs:
            github_url = f"{github_base}/{doc.relative_path}"
            priority_badge = f"[{doc.frontmatter.priority}]" if doc.frontmatter.priority == 'essential' else ''

            lines.append(f"### [{doc.title}]({github_url}) {priority_badge}")
            lines.append("")

            # Full heading tree (H2-H4)
            heading_tree = format_heading_tree_full(doc.headings)
            if heading_tree:
                lines.extend(heading_tree)
                lines.append("")

    return '\n'.join(lines)


def main():
    """Main entry point."""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent.parent

    # GitHub base URL (adjust as needed)
    github_base = "https://github.com/mikeiacovacci/RMCitecraft/blob/main"

    print(f"Scanning documentation in: {repo_root}")

    docs = scan_documentation(repo_root)
    print(f"Found {len(docs)} documentation files")

    # Count by priority
    essential = len([d for d in docs if d.frontmatter.priority == 'essential'])
    reference = len([d for d in docs if d.frontmatter.priority == 'reference'])
    archive = len([d for d in docs if d.frontmatter.priority == 'archive'])
    print(f"  Essential: {essential}")
    print(f"  Reference: {reference}")
    print(f"  Archive: {archive}")

    # Generate compact map (essential only)
    compact_map = generate_compact_map(docs, github_base)
    compact_path = repo_root / 'claude_code_docs_map.md'
    with open(compact_path, 'w', encoding='utf-8') as f:
        f.write(compact_map)
    print(f"\nCompact map generated: {compact_path}")
    print(f"  Lines: {len(compact_map.splitlines())}")

    # Generate full index
    full_index = generate_full_index(docs, github_base)
    full_path = repo_root / 'docs' / 'FULL_INDEX.md'
    full_path.parent.mkdir(exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(full_index)
    print(f"\nFull index generated: {full_path}")
    print(f"  Lines: {len(full_index.splitlines())}")


if __name__ == '__main__':
    main()
