#!/usr/bin/env python3
"""Fix 1860 census source formatting.

In source name: convert "citing p. " to "citing page "
In short footnote: convert "page " to "p. "
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rmcitecraft.database.connection import connect_rmtree


def fix_1860_census_sources(db_path: str, dry_run: bool = True) -> None:
    """Fix 1860 census source formatting."""
    conn = connect_rmtree(db_path, read_only=dry_run)
    cursor = conn.cursor()

    # Find all 1860 census sources (excluding slave schedules and other types)
    cursor.execute("""
        SELECT SourceID, Name, CAST(Fields AS TEXT) as Fields
        FROM SourceTable
        WHERE Name LIKE 'Fed Census: 1860,%'
    """)

    rows = cursor.fetchall()
    print(f"Found {len(rows)} 1860 census sources")

    updates = []

    for source_id, name, fields in rows:
        new_name = name
        new_fields = fields
        changes = []

        # Fix source name: "citing p. " -> "citing page "
        if "citing p. " in name:
            new_name = name.replace("citing p. ", "citing page ")
            changes.append(f"Name: 'citing p. ' -> 'citing page '")

        # Fix short footnote in Fields: "page " -> "p. "
        # But only in the ShortFootnote section, not Footnote
        if fields and "<Name>ShortFootnote</Name>" in fields:
            # Extract ShortFootnote value
            match = re.search(
                r'(<Name>ShortFootnote</Name>\s*<Value>)(.*?)(</Value>)',
                fields,
                re.DOTALL
            )
            if match:
                prefix, value, suffix = match.groups()
                # Replace "page " with "p. " in the short footnote value
                # But be careful not to replace in other contexts
                if ", page " in value:
                    new_value = value.replace(", page ", ", p. ")
                    new_fields = fields[:match.start()] + prefix + new_value + suffix + fields[match.end():]
                    changes.append(f"ShortFootnote: ', page ' -> ', p. '")

        if changes:
            updates.append((source_id, name, new_name, new_fields, changes))

    print(f"\nFound {len(updates)} sources to update")

    # Show sample updates
    for source_id, old_name, new_name, new_fields, changes in updates[:5]:
        print(f"\n--- SourceID {source_id} ---")
        print(f"Old Name: {old_name}")
        print(f"New Name: {new_name}")
        print(f"Changes: {', '.join(changes)}")

    if len(updates) > 5:
        print(f"\n... and {len(updates) - 5} more")

    if dry_run:
        print("\n[DRY RUN] No changes made. Run with dry_run=False to apply.")
    else:
        for source_id, old_name, new_name, new_fields, changes in updates:
            cursor.execute("""
                UPDATE SourceTable
                SET Name = ?, Fields = ?
                WHERE SourceID = ?
            """, (new_name, new_fields.encode('utf-8'), source_id))

        conn.commit()
        print(f"\nUpdated {len(updates)} sources")

    conn.close()


if __name__ == "__main__":
    db_path = Path(__file__).parent.parent / "data" / "Iiams.rmtree"

    # First do a dry run
    print("=== DRY RUN ===")
    fix_1860_census_sources(str(db_path), dry_run=True)

    # Apply changes:
    print("\n=== APPLYING CHANGES ===")
    fix_1860_census_sources(str(db_path), dry_run=False)
