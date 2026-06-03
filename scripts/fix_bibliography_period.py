#!/usr/bin/env python3
"""Fix missing period after FamilySearch in census source bibliographies.

This script fixes bibliographies that are missing the period after the publisher
name (FamilySearch) before the URL.

Current format (wrong):  <i>FamilySearch</i> https://...
Correct format:          <i>FamilySearch</i>. https://...

In the XML-encoded SourceTable.Fields BLOB:
Current: &lt;/i&gt; https://
Correct: &lt;/i&gt;. https://

Safety features:
- Preview mode by default (no changes made)
- Requires --execute flag to make changes
- Creates backup of affected records before changes
- Detailed logging of all operations
"""

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rmcitecraft.database.connection import connect_rmtree


def get_affected_sources(cursor):
    """Find census sources with missing period after FamilySearch in bibliography."""
    cursor.execute("""
        SELECT SourceID, Name, CAST(Fields AS TEXT) as fields_text
        FROM SourceTable
        WHERE Name LIKE 'Fed Census:%'
          AND TemplateID = 0
          AND Fields IS NOT NULL
    """)

    affected = []
    for source_id, name, fields_text in cursor.fetchall():
        if not fields_text:
            continue

        # Extract bibliography section from the XML
        # Pattern: <Name>Bibliography</Name>\n<Value>...</Value>
        # Use DOTALL to match across newlines
        bib_match = re.search(
            r'<Name>Bibliography</Name>\s*<Value>(.*?)</Value>',
            fields_text,
            re.DOTALL
        )

        if not bib_match:
            continue

        bibliography = bib_match.group(1).strip()

        # Check for the wrong pattern in bibliography ONLY
        # (footnotes use "(https://" with parenthesis, which is correct)
        # Bibliography uses "https://" directly without parenthesis
        # Wrong: &lt;/i&gt; https://  (space without period)
        # Correct: &lt;/i&gt;. https:// (period then space)
        has_wrong_pattern = bool(
            re.search(r'&lt;/i&gt;\s+https://', bibliography)
        )

        # Check it doesn't already have the period
        has_correct_pattern = bool(
            re.search(r'&lt;/i&gt;\.\s*https://', bibliography)
        )

        if has_wrong_pattern and not has_correct_pattern:
            affected.append({
                'source_id': source_id,
                'name': name,
                'fields_text': fields_text,
                'bibliography': bibliography
            })

    return affected


def fix_bibliography(fields_text):
    """Fix the bibliography by adding period after FamilySearch closing tag.

    Only fixes bibliography section, NOT footnotes.
    Footnotes use "(https://..." format which is correct.
    Bibliography uses "https://..." directly which needs period before it.
    """
    # Only fix within Bibliography value - pattern without parenthesis
    # This targets: &lt;/i&gt; https://  (bibliography format, no parenthesis)
    # NOT: &lt;/i&gt; (https://  (footnote format, has parenthesis - correct)

    def fix_bib_value(match):
        """Replace function to fix bibliography value only."""
        before_value = match.group(1)  # whitespace/newline before Value
        bib_content = match.group(2)
        after_value = match.group(3)   # whitespace/newline after content
        # Fix: &lt;/i&gt; https:// → &lt;/i&gt;. https://
        fixed_bib = re.sub(
            r'(&lt;/i&gt;)\s+(https://)',
            r'\1. \2',
            bib_content
        )
        return f'<Name>Bibliography</Name>{before_value}<Value>{fixed_bib}{after_value}</Value>'

    fixed = re.sub(
        r'<Name>Bibliography</Name>(\s*)<Value>(.*?)(\s*)</Value>',
        fix_bib_value,
        fields_text,
        flags=re.DOTALL
    )

    return fixed


def backup_affected_records(cursor, affected_sources):
    """Create a backup record of all data that will be modified."""
    backup = {
        'timestamp': datetime.now().isoformat(),
        'description': 'Bibliography period fix - adding period after FamilySearch before URL',
        'records': []
    }

    for source in affected_sources:
        backup['records'].append({
            'source_id': source['source_id'],
            'name': source['name'],
            'original_fields': source['fields_text']
        })

    return backup


def execute_fixes(cursor, affected_sources):
    """Execute the bibliography fixes."""
    fixed_count = 0

    for source in affected_sources:
        fixed_fields = fix_bibliography(source['fields_text'])

        if fixed_fields != source['fields_text']:
            cursor.execute(
                "UPDATE SourceTable SET Fields = ? WHERE SourceID = ?",
                (fixed_fields.encode('utf-8'), source['source_id'])
            )
            print(f"  Fixed SourceID {source['source_id']}: {source['name'][:60]}...")
            fixed_count += 1

    return fixed_count


def main():
    parser = argparse.ArgumentParser(
        description='Fix missing period after FamilySearch in census source bibliographies.'
    )
    parser.add_argument(
        '--db',
        default='data/Iiams.rmtree',
        help='Path to RootsMagic database'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually execute changes (default is preview only)'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("  BIBLIOGRAPHY PERIOD FIX")
    print("  Add period after <i>FamilySearch</i> before URL")
    print("=" * 70)
    print()

    # Connect to database
    read_only = not args.execute
    conn = connect_rmtree(args.db, read_only=read_only)
    cursor = conn.cursor()

    # Get affected sources
    affected = get_affected_sources(cursor)

    if not affected:
        print("No bibliographies need fixing - all already have correct format.")
        conn.close()
        return

    # Display summary
    print(f"Found {len(affected)} source(s) with missing period:\n")

    # Show first 10 examples
    for source in affected[:10]:
        print(f"  SourceID {source['source_id']}: {source['name'][:65]}")

    if len(affected) > 10:
        print(f"  ... and {len(affected) - 10} more")

    print()

    # Show example of the fix
    if affected:
        example = affected[0]
        print(f"Example fix (SourceID {example['source_id']}):")
        print(f"  Bibliography before:")
        bib_before = example['bibliography']
        # Show the relevant part around FamilySearch
        fs_idx = bib_before.find('FamilySearch')
        if fs_idx >= 0:
            snippet = bib_before[max(0, fs_idx-10):min(len(bib_before), fs_idx+50)]
            print(f"    ...{snippet}...")

        # Fix and show after
        fixed_fields = fix_bibliography(example['fields_text'])
        fixed_bib_match = re.search(
            r'<Name>Bibliography</Name>\s*<Value>(.*?)</Value>',
            fixed_fields,
            re.DOTALL
        )
        if fixed_bib_match:
            bib_after = fixed_bib_match.group(1)
            fs_idx = bib_after.find('FamilySearch')
            if fs_idx >= 0:
                snippet = bib_after[max(0, fs_idx-10):min(len(bib_after), fs_idx+50)]
                print(f"  Bibliography after:")
                print(f"    ...{snippet}...")
        print()

    if not args.execute:
        print("=" * 70)
        print("  PREVIEW MODE - No changes made")
        print("  Run with --execute to apply changes")
        print("=" * 70)
        conn.close()
        return

    # Create backup
    print("Creating backup of affected records...")
    backup = backup_affected_records(cursor, affected)

    backup_file = Path(f"backup/bibliography_period_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    backup_file.parent.mkdir(exist_ok=True)
    with open(backup_file, 'w') as f:
        json.dump(backup, f, indent=2)
    print(f"Backup saved to: {backup_file}")
    print()

    # Execute fixes
    print("Executing fixes...")
    fixed_count = execute_fixes(cursor, affected)

    # Commit
    conn.commit()
    print()
    print("=" * 70)
    print(f"  FIXED {fixed_count} BIBLIOGRAPHY RECORDS")
    print("=" * 70)

    conn.close()


if __name__ == '__main__':
    main()
