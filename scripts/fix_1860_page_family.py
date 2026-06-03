#!/usr/bin/env python3
"""Fix 1860 census sources missing page and family in footnotes.

Extracts page and family/household ID from source name bracket and adds
to footnote and short footnote where missing.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rmcitecraft.database.connection import connect_rmtree


def fix_1860_page_family(db_path: str, dry_run: bool = True) -> None:
    """Fix missing page and family in 1860 census citations."""
    conn = connect_rmtree(db_path, read_only=dry_run)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT SourceID, Name, CAST(Fields AS TEXT) as Fields
        FROM SourceTable
        WHERE Name LIKE 'Fed Census: 1860,%'
    """)

    rows = cursor.fetchall()
    print(f"Found {len(rows)} sources")

    updates = 0
    for source_id, name, fields in rows:
        if not fields:
            continue

        # Extract page and family/household from source name bracket
        bracket = re.search(r'\[([^\]]+)\]', name)
        if not bracket:
            continue

        bracket_data = bracket.group(1)

        # Extract page number
        page_match = re.search(r'page\s+(\d+)', bracket_data, re.IGNORECASE)
        page_num = page_match.group(1) if page_match else None

        # Extract family or household ID
        family_match = re.search(r'(?:family|household\s+ID)\s+(\d+)', bracket_data, re.IGNORECASE)
        family_num = family_match.group(1) if family_match else None

        if not page_num and not family_num:
            continue

        new_fields = fields
        changed = False

        # Fix footnote - add page before family if missing
        fn_match = re.search(r'<Name>Footnote</Name>\s*<Value>(.*?)</Value>', new_fields, re.DOTALL)
        if fn_match:
            footnote = fn_match.group(1)
            new_fn = footnote

            # Add page if missing
            if page_num and not re.search(r'page\s+\d+', footnote, re.IGNORECASE):
                # Insert 'page X,' before 'family Y,'
                if re.search(r'family\s+\d+', footnote, re.IGNORECASE):
                    new_fn = re.sub(r'(family\s+\d+)', f'page {page_num}, \\1', new_fn)

            # Add family if missing (after page if present, before person name)
            if family_num and not re.search(r'family\s+\d+', new_fn, re.IGNORECASE):
                # Insert before person name (look for pattern like ', Name Name;')
                new_fn = re.sub(r'(,\s+)([A-Z][a-z]+ [A-Z][a-z]+;)', f'\\1family {family_num}, \\2', new_fn, count=1)

            if new_fn != footnote:
                new_fields = new_fields.replace(footnote, new_fn)
                changed = True

        # Fix short footnote - add p. and family if missing
        sf_match = re.search(r'<Name>ShortFootnote</Name>\s*<Value>(.*?)</Value>', new_fields, re.DOTALL)
        if sf_match:
            short_fn = sf_match.group(1)
            new_sf = short_fn

            has_page = bool(re.search(r'p\.\s*\d+', short_fn, re.IGNORECASE))
            has_family = bool(re.search(r'family\s+\d+', short_fn, re.IGNORECASE))

            if (page_num and not has_page) or (family_num and not has_family):
                # Find the last segment before person name
                # Short footnote ends with: ..., PersonName.
                parts = new_sf.rsplit(', ', 1)
                if len(parts) == 2:
                    prefix, person_part = parts
                    insert_parts = []
                    if page_num and not has_page:
                        insert_parts.append(f'p. {page_num}')
                    if family_num and not has_family:
                        insert_parts.append(f'family {family_num}')

                    if insert_parts:
                        new_sf = prefix + ', ' + ', '.join(insert_parts) + ', ' + person_part

            if new_sf != short_fn:
                new_fields = new_fields.replace(short_fn, new_sf)
                changed = True

        if changed:
            if dry_run:
                print(f"Would update: {name[:70]}...")
            else:
                cursor.execute('UPDATE SourceTable SET Fields = ? WHERE SourceID = ?',
                              (new_fields.encode('utf-8'), source_id))
            updates += 1

    if not dry_run:
        conn.commit()
    conn.close()
    print(f"\n{'Would update' if dry_run else 'Updated'} {updates} sources")


if __name__ == "__main__":
    db_path = Path(__file__).parent.parent / "data" / "Iiams.rmtree"

    # Dry run first
    print("=== DRY RUN ===")
    fix_1860_page_family(str(db_path), dry_run=True)

    # Apply changes
    print("\n=== APPLYING CHANGES ===")
    fix_1860_page_family(str(db_path), dry_run=False)
