#!/usr/bin/env python3
"""
Refactor Documentation Organization

This script reorganizes documentation files into a clean directory structure,
ensuring minimal files in the root directory and updating all references.
"""

import re
import shutil
from pathlib import Path
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class FileMove:
    """Represents a file move operation."""
    source: Path
    destination: Path
    reason: str


@dataclass
class ReferenceUpdate:
    """Represents a reference that needs updating."""
    file_path: Path
    old_ref: str
    new_ref: str
    line_number: int


class DocumentRefactorer:
    """Handles documentation refactoring and reference updates."""

    # Files that should remain in root directory
    ROOT_ALLOWLIST = {
        'README.md',
        'CLAUDE.md',
        'AGENTS.md',  # AI agent instructions
        'claude_code_docs_map.md',
        'QUICKSTART.md',
        'PRD.md',  # Product Requirements Document
    }

    # Files that should be excluded from refactoring
    EXCLUDE_PATTERNS = {
        '.venv',
        'node_modules',
        '.git',
        '.pytest_cache',
        '__pycache__',
    }

    def __init__(self, repo_root: Path, dry_run: bool = False):
        self.repo_root = repo_root
        self.dry_run = dry_run
        self.moves: List[FileMove] = []
        self.reference_updates: List[ReferenceUpdate] = []

    def categorize_file(self, file_path: Path) -> Tuple[Path, str]:
        """
        Determine the target location for a documentation file.

        Returns: (target_path, reason)
        """
        relative_path = file_path.relative_to(self.repo_root)
        filename = file_path.name

        # Keep root allowlist files in root
        if filename in self.ROOT_ALLOWLIST:
            return file_path, "Root allowlist"

        # Keep .github docs in .github
        if str(relative_path).startswith('.github/'):
            return file_path, "GitHub directory structure"

        # Categorize based on filename patterns and content
        filename_lower = filename.lower()

        # Weekly summaries and progress reports -> archive
        if re.match(r'week\d+-', filename_lower) or 'progress' in filename_lower:
            target = self.repo_root / 'docs' / 'archive' / filename
            return target, "Development archive (weekly summaries/progress)"

        # Fix/patch/optimization documents -> implementation notes
        if any(x in filename_lower for x in ['fix', 'optimization', 'support', 'updates']):
            target = self.repo_root / 'docs' / 'implementation' / filename
            return target, "Implementation notes (fixes/optimizations)"

        # Project planning documents
        if any(x in filename_lower for x in ['plan', 'project']):
            target = self.repo_root / 'docs' / 'project' / filename
            return target, "Project planning"

        # Census analysis documents
        if 'census' in filename_lower and 'analysis' in filename_lower:
            target = self.repo_root / 'docs' / 'analysis' / filename
            return target, "Census data analysis"

        # Technical architecture documents
        if any(x in filename_lower for x in ['architecture', 'design', 'llm']):
            target = self.repo_root / 'docs' / 'architecture' / filename
            return target, "Architecture and design"

        # Database/extension documentation
        if str(relative_path).startswith('sqlite-extension/'):
            target = self.repo_root / 'docs' / 'database' / filename
            return target, "Database integration"

        # Extension documentation
        if str(relative_path).startswith('extension/'):
            target = self.repo_root / 'docs' / 'extension' / filename
            return target, "Browser extension"

        # Reference documentation (already in docs/reference)
        if str(relative_path).startswith('docs/reference/'):
            return file_path, "Already in reference"

        # Already properly organized in docs/
        if str(relative_path).startswith('docs/') and not filename.startswith('CENSUS'):
            return file_path, "Already in docs"

        # Quickstart guides (only one should be in root, others archived)
        if 'quickstart' in filename_lower and filename != 'QUICKSTART.md':
            target = self.repo_root / 'docs' / 'archive' / filename
            return target, "Archived quickstart variant"

        # Default: move to docs/misc
        target = self.repo_root / 'docs' / 'misc' / filename
        return target, "Miscellaneous documentation"

    def scan_for_moves(self) -> List[FileMove]:
        """Scan all markdown files and determine necessary moves."""
        moves = []

        # Find all markdown files
        for md_file in self.repo_root.rglob('*.md'):
            # Skip excluded directories
            if any(excluded in md_file.parts for excluded in self.EXCLUDE_PATTERNS):
                continue

            # Determine target location
            target, reason = self.categorize_file(md_file)

            # If location differs, add to move list
            if target != md_file:
                moves.append(FileMove(
                    source=md_file,
                    destination=target,
                    reason=reason
                ))

        return moves

    def find_references(self, search_text: str) -> List[Tuple[Path, int, str]]:
        """
        Find all references to a file path in the repository.

        Returns: List of (file_path, line_number, line_content)
        """
        references = []

        # File extensions to scan for references
        extensions = {'.md', '.py', '.yml', '.yaml', '.toml', '.txt', '.sh'}

        for file_path in self.repo_root.rglob('*'):
            # Skip excluded directories
            if any(excluded in file_path.parts for excluded in self.EXCLUDE_PATTERNS):
                continue

            # Only scan text files
            if file_path.suffix not in extensions:
                continue

            if not file_path.is_file():
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if search_text in line:
                            references.append((file_path, line_num, line.strip()))
            except (UnicodeDecodeError, PermissionError):
                continue

        return references

    def calculate_relative_path(self, from_file: Path, to_file: Path) -> str:
        """Calculate relative path from one file to another."""
        try:
            # Get the directory containing the source file
            from_dir = from_file.parent
            # Calculate relative path to target
            rel_path = to_file.relative_to(from_dir)
            return str(rel_path)
        except ValueError:
            # Files don't share a common base, use .. notation
            from_parts = from_file.parent.parts
            to_parts = to_file.parts

            # Find common prefix
            common = 0
            for i, (a, b) in enumerate(zip(from_parts, to_parts)):
                if a == b:
                    common = i + 1
                else:
                    break

            # Build relative path with ..
            ups = len(from_parts) - common
            rel_parts = ['..'] * ups + list(to_parts[common:])
            return '/'.join(rel_parts)

    def detect_reference_updates(self) -> List[ReferenceUpdate]:
        """Detect all references that need updating after file moves."""
        updates = []

        for move in self.moves:
            source_rel = move.source.relative_to(self.repo_root)
            dest_rel = move.destination.relative_to(self.repo_root)

            # Search patterns for this file
            search_patterns = [
                str(source_rel),  # Relative path from root
                str(source_rel).replace('\\', '/'),  # Unix-style path
                move.source.name,  # Just filename (might need context)
            ]

            for pattern in search_patterns:
                references = self.find_references(pattern)

                for ref_file, line_num, line_content in references:
                    # Skip the file itself
                    if ref_file == move.source:
                        continue

                    # Calculate appropriate replacement
                    old_ref = str(source_rel)
                    new_ref = str(dest_rel)

                    # If it's a relative reference, calculate relative path
                    if not line_content.strip().startswith('http'):
                        # Check if reference is relative
                        if './' in line_content or '../' in line_content:
                            new_ref = self.calculate_relative_path(ref_file, move.destination)
                            old_ref = self.calculate_relative_path(ref_file, move.source)

                    updates.append(ReferenceUpdate(
                        file_path=ref_file,
                        old_ref=old_ref,
                        new_ref=new_ref,
                        line_number=line_num
                    ))

        return updates

    def apply_reference_updates(self):
        """Apply all reference updates to files."""
        # Group updates by file
        updates_by_file: Dict[Path, List[ReferenceUpdate]] = {}
        for update in self.reference_updates:
            if update.file_path not in updates_by_file:
                updates_by_file[update.file_path] = []
            updates_by_file[update.file_path].append(update)

        for file_path, updates in updates_by_file.items():
            if self.dry_run:
                print(f"  [DRY RUN] Would update {len(updates)} references in {file_path}")
                continue

            try:
                # Read file content
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Apply all updates for this file
                for update in updates:
                    content = content.replace(update.old_ref, update.new_ref)

                # Write back
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                print(f"  ✓ Updated {len(updates)} references in {file_path.relative_to(self.repo_root)}")

            except Exception as e:
                print(f"  ✗ Error updating {file_path}: {e}")

    def apply_moves(self):
        """Execute all file moves."""
        for move in self.moves:
            if self.dry_run:
                print(f"  [DRY RUN] {move.source.relative_to(self.repo_root)} -> {move.destination.relative_to(self.repo_root)}")
                continue

            try:
                # Create destination directory
                move.destination.parent.mkdir(parents=True, exist_ok=True)

                # Move file
                shutil.move(str(move.source), str(move.destination))
                print(f"  ✓ Moved {move.source.name} -> {move.destination.relative_to(self.repo_root)}")

            except Exception as e:
                print(f"  ✗ Error moving {move.source}: {e}")

    def generate_summary(self) -> str:
        """Generate a summary of changes."""
        lines = [
            "# Documentation Refactoring Summary",
            "",
            f"> Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
        ]

        # Group moves by category
        moves_by_category: Dict[str, List[FileMove]] = {}
        for move in self.moves:
            category = move.destination.parent.relative_to(self.repo_root)
            category_str = str(category)
            if category_str not in moves_by_category:
                moves_by_category[category_str] = []
            moves_by_category[category_str].append(move)

        if self.moves:
            lines.append(f"## File Moves ({len(self.moves)} files)")
            lines.append("")

            for category in sorted(moves_by_category.keys()):
                lines.append(f"### {category}/")
                lines.append("")
                for move in moves_by_category[category]:
                    source_name = move.source.relative_to(self.repo_root)
                    lines.append(f"- `{source_name}` → `{move.destination.relative_to(self.repo_root)}`")
                    lines.append(f"  - Reason: {move.reason}")
                lines.append("")
        else:
            lines.append("## No file moves required")
            lines.append("")
            lines.append("All documentation files are already properly organized.")
            lines.append("")

        if self.reference_updates:
            lines.append(f"## Reference Updates ({len(self.reference_updates)} updates)")
            lines.append("")

            # Group by file being updated
            updates_by_file: Dict[Path, List[ReferenceUpdate]] = {}
            for update in self.reference_updates:
                if update.file_path not in updates_by_file:
                    updates_by_file[update.file_path] = []
                updates_by_file[update.file_path].append(update)

            for file_path in sorted(updates_by_file.keys()):
                updates = updates_by_file[file_path]
                rel_path = file_path.relative_to(self.repo_root)
                lines.append(f"### {rel_path}")
                lines.append(f"- {len(updates)} reference(s) updated")
                lines.append("")

        return '\n'.join(lines)

    def refactor(self):
        """Execute the full refactoring process."""
        print("=" * 80)
        print("Documentation Refactoring")
        print("=" * 80)
        print()

        # Step 1: Scan for necessary moves
        print("📋 Scanning documentation files...")
        self.moves = self.scan_for_moves()
        print(f"   Found {len(self.moves)} files to reorganize")
        print()

        if not self.moves:
            print("✓ All documentation files are already properly organized!")
            return

        # Step 2: Detect reference updates
        print("🔍 Detecting reference updates...")
        self.reference_updates = self.detect_reference_updates()
        print(f"   Found {len(self.reference_updates)} references to update")
        print()

        # Step 3: Apply reference updates first (before moving files)
        if self.reference_updates:
            print("📝 Updating references...")
            self.apply_reference_updates()
            print()

        # Step 4: Move files
        print("📦 Moving files...")
        self.apply_moves()
        print()

        # Step 5: Print summary
        summary = self.generate_summary()

        print("📄 Summary:")
        print()
        print(summary)
        print()
        print("=" * 80)
        print("✓ Documentation refactoring complete!")
        print("=" * 80)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Refactor documentation organization')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without making changes')
    parser.add_argument('--repo-root', type=Path,
                        help='Repository root directory (default: auto-detect)')

    args = parser.parse_args()

    # Detect repository root
    if args.repo_root:
        repo_root = args.repo_root
    else:
        # Assume script is in .github/scripts/
        script_dir = Path(__file__).parent
        repo_root = script_dir.parent.parent

    # Run refactoring
    refactorer = DocumentRefactorer(repo_root, dry_run=args.dry_run)
    refactorer.refactor()


if __name__ == '__main__':
    main()
