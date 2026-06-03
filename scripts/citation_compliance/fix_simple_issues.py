#!/usr/bin/env python3
"""Fix simple formatting issues in Free Form citations (Tier 1 automated fixes).

This script fixes straightforward formatting issues that can be corrected
programmatically without human review:

- Double spaces -> single space
- Non-breaking space (\xa0) -> regular space
- Missing terminal period on footnotes ending with ) or alphanumeric
- Missing terminal period on bibliographies

Safety features:
- Dry-run mode by default (no changes made)
- Requires --apply flag to make changes
- Creates backup of affected records before changes
- Detailed logging of all operations

Usage:
    uv run python scripts/citation_compliance/fix_simple_issues.py --dry-run
    uv run python scripts/citation_compliance/fix_simple_issues.py --apply
    uv run python scripts/citation_compliance/fix_simple_issues.py --apply --source-type "Fed Census"
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.rmcitecraft.database.connection import connect_rmtree


@dataclass
class FixApplied:
    """Record of a fix applied to a citation field."""
    fix_type: str
    field: str  # 'footnote', 'short_footnote', 'bibliography'
    original: str
    fixed: str


@dataclass
class SourceFixes:
    """All fixes applied to a single source."""
    source_id: int
    name: str
    original_fields_text: str
    fixed_fields_text: str
    fixes: list[FixApplied] = field(default_factory=list)

    @property
    def has_fixes(self) -> bool:
        return len(self.fixes) > 0


def extract_field_from_blob(fields_text: str, field_name: str) -> str:
    """Extract a field value from the SourceTable.Fields XML text."""
    if not fields_text:
        return ""
    pattern = rf'<Name>{field_name}</Name>\s*<Value>(.*?)</Value>'
    match = re.search(pattern, fields_text, re.DOTALL)
    return match.group(1) if match else ""


def update_field_in_blob(fields_text: str, field_name: str, new_value: str) -> str:
    """Update a field value in the SourceTable.Fields XML text.

    Args:
        fields_text: The full XML text
        field_name: Field name ('Footnote', 'ShortFootnote', 'Bibliography')
        new_value: The new value to set

    Returns:
        Updated XML text
    """
    pattern = rf'(<Name>{field_name}</Name>\s*<Value>)(.*?)(</Value>)'

    def replacer(match):
        return match.group(1) + new_value + match.group(3)

    return re.sub(pattern, replacer, fields_text, flags=re.DOTALL)


def fix_double_spaces(text: str) -> tuple[str, bool]:
    """Replace multiple consecutive spaces with single space.

    Returns:
        Tuple of (fixed_text, was_changed)
    """
    if not text:
        return text, False

    fixed = re.sub(r'  +', ' ', text)
    return fixed, fixed != text


def fix_non_breaking_spaces(text: str) -> tuple[str, bool]:
    """Replace non-breaking spaces with regular spaces.

    Returns:
        Tuple of (fixed_text, was_changed)
    """
    if not text:
        return text, False

    fixed = text.replace('\xa0', ' ')
    return fixed, fixed != text


def fix_missing_period(text: str, field_type: str) -> tuple[str, bool]:
    """Add missing terminal period to citation text.

    Args:
        text: The citation text
        field_type: 'footnote', 'short_footnote', or 'bibliography'

    Returns:
        Tuple of (fixed_text, was_changed)
    """
    if not text:
        return text, False

    text = text.rstrip()
    if not text:
        return text, False

    # Already ends with period
    if text.endswith('.'):
        return text, False

    # Add period after:
    # - Closing parenthesis: "(accessed 5 September 2015)" -> "...2015)."
    # - Alphanumeric: "some text" -> "some text."
    # - Closing quote: "some title"" -> "some title"."
    if text[-1] in ')"\'' or text[-1].isalnum():
        return text + '.', True

    return text, False


def analyze_and_fix_source(source_id: int, name: str, fields_text: str) -> SourceFixes:
    """Analyze and fix a single source.

    Args:
        source_id: The SourceID from RootsMagic
        name: The source name
        fields_text: The decoded Fields BLOB text

    Returns:
        SourceFixes with all applied fixes
    """
    result = SourceFixes(
        source_id=source_id,
        name=name,
        original_fields_text=fields_text,
        fixed_fields_text=fields_text
    )

    # Process each field
    field_names = ['Footnote', 'ShortFootnote', 'Bibliography']
    field_keys = ['footnote', 'short_footnote', 'bibliography']

    for field_name, field_key in zip(field_names, field_keys):
        original = extract_field_from_blob(result.fixed_fields_text, field_name)
        if not original:
            continue

        current = original

        # Fix 1: Non-breaking spaces
        fixed, changed = fix_non_breaking_spaces(current)
        if changed:
            result.fixes.append(FixApplied(
                fix_type='NON_BREAKING_SPACE',
                field=field_key,
                original=current,
                fixed=fixed
            ))
            current = fixed

        # Fix 2: Double spaces
        fixed, changed = fix_double_spaces(current)
        if changed:
            result.fixes.append(FixApplied(
                fix_type='DOUBLE_SPACES',
                field=field_key,
                original=current,
                fixed=fixed
            ))
            current = fixed

        # Fix 3: Missing period (only for footnote and bibliography)
        if field_key in ('footnote', 'bibliography'):
            fixed, changed = fix_missing_period(current, field_key)
            if changed:
                result.fixes.append(FixApplied(
                    fix_type='MISSING_PERIOD',
                    field=field_key,
                    original=current,
                    fixed=fixed
                ))
                current = fixed

        # Update the fields text if anything changed
        if current != original:
            result.fixed_fields_text = update_field_in_blob(
                result.fixed_fields_text, field_name, current
            )

    return result


def create_backup(fixes_list: list[SourceFixes]) -> dict[str, Any]:
    """Create a backup record of all changes."""
    return {
        'timestamp': datetime.now().isoformat(),
        'description': 'Simple formatting fixes: double spaces, non-breaking spaces, missing periods',
        'total_sources': len(fixes_list),
        'records': [
            {
                'source_id': f.source_id,
                'name': f.name,
                'original_fields': f.original_fields_text,
                'fixes': [
                    {
                        'type': fix.fix_type,
                        'field': fix.field,
                        'original': fix.original[:100] + '...' if len(fix.original) > 100 else fix.original,
                        'fixed': fix.fixed[:100] + '...' if len(fix.fixed) > 100 else fix.fixed,
                    }
                    for fix in f.fixes
                ]
            }
            for f in fixes_list
        ]
    }


def main():
    parser = argparse.ArgumentParser(
        description='Fix simple formatting issues in Free Form citations.'
    )
    parser.add_argument(
        '--db',
        default='data/Iiams.rmtree',
        help='Path to RootsMagic database'
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Apply fixes (default is dry-run/preview mode)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview mode without changes (default behavior)'
    )
    parser.add_argument(
        '--source-type',
        help='Filter to specific source type (e.g., "Fed Census")'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of sources to process'
    )
    parser.add_argument(
        '--backup-dir',
        default='backup',
        help='Directory for backup files'
    )

    args = parser.parse_args()

    # Default to dry-run if --apply not specified
    is_dry_run = not args.apply

    print("=" * 70)
    print("  SIMPLE CITATION FIXES (TIER 1)")
    print("  Double spaces, non-breaking spaces, missing periods")
    print("=" * 70)
    print()
    print(f"Mode: {'DRY-RUN (no changes)' if is_dry_run else 'APPLY FIXES'}")
    print()

    # Connect to database
    conn = connect_rmtree(args.db, read_only=is_dry_run)
    cursor = conn.cursor()

    # Query all Free Form sources
    query = """
        SELECT SourceID, Name, CAST(Fields AS TEXT) as fields_text
        FROM SourceTable
        WHERE TemplateID = 0
          AND Fields IS NOT NULL
    """

    if args.source_type:
        query += f" AND Name LIKE '{args.source_type}%'"

    query += " ORDER BY Name"

    if args.limit:
        query += f" LIMIT {args.limit}"

    cursor.execute(query)
    rows = cursor.fetchall()

    print(f"Processing {len(rows)} Free Form sources...")
    print()

    # Analyze and fix each source
    all_fixes: list[SourceFixes] = []
    fix_counts: dict[str, int] = {
        'DOUBLE_SPACES': 0,
        'NON_BREAKING_SPACE': 0,
        'MISSING_PERIOD': 0,
    }

    for source_id, name, fields_text in rows:
        source_fixes = analyze_and_fix_source(source_id, name, fields_text)

        if source_fixes.has_fixes:
            all_fixes.append(source_fixes)

            for fix in source_fixes.fixes:
                fix_counts[fix.fix_type] += 1

    # Display summary
    print("=" * 70)
    print("  FIXES SUMMARY")
    print("=" * 70)
    print()
    print(f"Sources with fixes:  {len(all_fixes)}")
    print()
    print("Fix types:")
    for fix_type, count in sorted(fix_counts.items()):
        if count > 0:
            print(f"  {fix_type:25} {count:5} fixes")
    print()

    # Show sample fixes
    if all_fixes:
        print("Sample fixes (first 5 sources):")
        print("-" * 50)
        for source_fixes in all_fixes[:5]:
            print(f"\nSourceID {source_fixes.source_id}: {source_fixes.name[:55]}")
            for fix in source_fixes.fixes[:3]:  # Show first 3 fixes per source
                print(f"  [{fix.fix_type}] {fix.field}")
                # Show a snippet of the change
                orig_snippet = fix.original[:50].replace('\n', ' ')
                fixed_snippet = fix.fixed[:50].replace('\n', ' ')
                print(f"    - \"{orig_snippet}...\"")
                print(f"    + \"{fixed_snippet}...\"")

        print()

    if is_dry_run:
        print("=" * 70)
        print("  DRY-RUN MODE - No changes made")
        print("  Run with --apply to apply these fixes")
        print("=" * 70)
        conn.close()
        return

    # Apply fixes
    if not all_fixes:
        print("No fixes to apply.")
        conn.close()
        return

    # Create backup before applying
    print("Creating backup...")
    backup = create_backup(all_fixes)

    backup_dir = Path(args.backup_dir)
    backup_dir.mkdir(exist_ok=True)
    backup_file = backup_dir / f"simple_fixes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(backup_file, 'w') as f:
        json.dump(backup, f, indent=2)
    print(f"Backup saved to: {backup_file}")
    print()

    # Apply fixes to database
    print("Applying fixes...")
    applied_count = 0

    for source_fixes in all_fixes:
        if source_fixes.fixed_fields_text != source_fixes.original_fields_text:
            cursor.execute(
                "UPDATE SourceTable SET Fields = ? WHERE SourceID = ?",
                (source_fixes.fixed_fields_text.encode('utf-8'), source_fixes.source_id)
            )
            applied_count += 1
            if applied_count % 100 == 0:
                print(f"  Applied {applied_count} fixes...")

    # Commit changes
    conn.commit()
    conn.close()

    print()
    print("=" * 70)
    print(f"  APPLIED {applied_count} FIXES")
    print(f"  Backup saved to: {backup_file}")
    print("=" * 70)


if __name__ == '__main__':
    main()
