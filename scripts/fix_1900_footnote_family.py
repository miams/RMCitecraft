#!/usr/bin/env python3
"""
Fix 1900 Census Footnotes - Add Family Numbers

Adds family numbers from source names to footnotes and short footnotes.
The source name format is: Fed Census: 1900, State, County [ED X, sheet Y, family Z, line W] Person
The footnotes need to have family Z added after the sheet reference.

Uses lambda function for regex replacement to avoid group reference errors.
"""

import re
import sqlite3
from pathlib import Path


def get_sources_missing_family_in_footnote(db_path: str) -> list[dict]:
    """Get 1900 census sources where footnote is missing family number."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT SourceID, Name, CAST(Fields AS TEXT) AS fields_text
        FROM SourceTable
        WHERE Name LIKE 'Fed Census: 1900%'
        ORDER BY SourceID
    """)

    sources = []
    for row in cursor.fetchall():
        source_id = row['SourceID']
        name = row['Name']
        fields_text = row['fields_text']

        # Extract family from source name
        name_match = re.search(r'family (\d+)', name)
        if not name_match:
            continue

        family_num = name_match.group(1)

        # Check if footnote is missing family in the citation portion
        # (not in "FamilySearch" which always appears)
        footnote_match = re.search(r'<Name>Footnote</Name>\s*<Value>(.*?)</Value>', fields_text, re.DOTALL)
        if footnote_match:
            footnote = footnote_match.group(1)
            # Check for "sheet X, family Y" pattern - if missing, needs update
            if not re.search(r'sheet \d+[AB]?, family \d+', footnote, re.IGNORECASE):
                sources.append({
                    'source_id': source_id,
                    'name': name,
                    'fields_text': fields_text,
                    'family_num': family_num,
                    'footnote': footnote
                })

    conn.close()
    return sources


def update_field_safe(fields_text: str, field_name: str, new_value: str) -> str:
    """
    Update a field value in the Fields XML, using a lambda to avoid regex errors.

    This version uses a replacement function instead of a raw replacement string,
    which prevents issues when new_value contains backslash sequences that look
    like group references.
    """
    pattern = rf'(<Name>{re.escape(field_name)}</Name>\s*<Value>)(.*?)(</Value>)'

    def replacer(m):
        return m.group(1) + new_value + m.group(3)

    return re.sub(pattern, replacer, fields_text, flags=re.DOTALL)


def add_family_to_footnote(footnote: str, family_num: str) -> str:
    """
    Add family number after sheet reference in footnote.

    Pattern: "sheet 8B, line 57" -> "sheet 8B, family 188, line 57"
    """
    # Match "sheet XY, line Z" pattern (with or without space variations)
    pattern = r'(sheet \d+[AB]?),\s*(line \d+)'
    replacement = rf'\1, family {family_num}, \2'
    return re.sub(pattern, replacement, footnote, flags=re.IGNORECASE)


def add_family_to_short_footnote(short_footnote: str, family_num: str) -> str:
    """
    Add family number after sheet reference in short footnote.

    Pattern: "sheet 8B, line 57" -> "sheet 8B, family 188, line 57"
    """
    pattern = r'(sheet \d+[AB]?),\s*(line \d+)'
    replacement = rf'\1, family {family_num}, \2'
    return re.sub(pattern, replacement, short_footnote, flags=re.IGNORECASE)


def main():
    db_path = Path(__file__).parent.parent / "data" / "Iiams.rmtree"

    print(f"Database: {db_path}")
    print()

    # Get sources needing family numbers
    sources = get_sources_missing_family_in_footnote(db_path)
    print(f"Found {len(sources)} sources missing family in footnotes")
    print()

    if not sources:
        print("No sources to update.")
        return

    # Preview first 3 updates
    print("Preview of first 3 updates:")
    print("=" * 80)
    for source in sources[:3]:
        print(f"\nSource ID: {source['source_id']}")
        print(f"Name: {source['name']}")
        print(f"Family: {source['family_num']}")

        # Get current footnote and short footnote
        fields_text = source['fields_text']

        fn_match = re.search(r'<Name>Footnote</Name>\s*<Value>(.*?)</Value>', fields_text, re.DOTALL)
        sfn_match = re.search(r'<Name>ShortFootnote</Name>\s*<Value>(.*?)</Value>', fields_text, re.DOTALL)

        if fn_match:
            old_fn = fn_match.group(1)
            new_fn = add_family_to_footnote(old_fn, source['family_num'])
            print(f"\nOld Footnote excerpt: ...{old_fn[old_fn.find('sheet'):old_fn.find('sheet')+50]}...")
            print(f"New Footnote excerpt: ...{new_fn[new_fn.find('sheet'):new_fn.find('sheet')+60]}...")

        if sfn_match:
            old_sfn = sfn_match.group(1)
            new_sfn = add_family_to_short_footnote(old_sfn, source['family_num'])
            print(f"\nOld ShortFootnote: {old_sfn[:100]}...")
            print(f"New ShortFootnote: {new_sfn[:100]}...")

    print("\n" + "=" * 80)
    print()

    # Apply updates
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    updated_count = 0
    error_count = 0

    for source in sources:
        try:
            fields_text = source['fields_text']
            family_num = source['family_num']

            # Update footnote
            fn_match = re.search(r'<Name>Footnote</Name>\s*<Value>(.*?)</Value>', fields_text, re.DOTALL)
            if fn_match:
                old_fn = fn_match.group(1)
                new_fn = add_family_to_footnote(old_fn, family_num)
                if new_fn != old_fn:
                    fields_text = update_field_safe(fields_text, 'Footnote', new_fn)

            # Update short footnote
            sfn_match = re.search(r'<Name>ShortFootnote</Name>\s*<Value>(.*?)</Value>', fields_text, re.DOTALL)
            if sfn_match:
                old_sfn = sfn_match.group(1)
                new_sfn = add_family_to_short_footnote(old_sfn, family_num)
                if new_sfn != old_sfn:
                    fields_text = update_field_safe(fields_text, 'ShortFootnote', new_sfn)

            # Update database
            cursor.execute("""
                UPDATE SourceTable
                SET Fields = ?
                WHERE SourceID = ?
            """, (fields_text.encode('utf-8'), source['source_id']))

            updated_count += 1

        except Exception as e:
            print(f"Error updating source {source['source_id']}: {e}")
            error_count += 1

    conn.commit()
    conn.close()

    print(f"Updated {updated_count} sources")
    if error_count > 0:
        print(f"Errors: {error_count}")

    # Verify updates
    print("\nVerification - checking 3 random updated sources:")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SourceID, Name, CAST(Fields AS TEXT) AS fields_text
        FROM SourceTable
        WHERE Name LIKE 'Fed Census: 1900%'
        ORDER BY RANDOM()
        LIMIT 3
    """)

    for row in cursor.fetchall():
        source_id = row[0]
        name = row[1]
        fields_text = row[2]

        fn_match = re.search(r'<Name>Footnote</Name>\s*<Value>(.*?)</Value>', fields_text, re.DOTALL)
        sfn_match = re.search(r'<Name>ShortFootnote</Name>\s*<Value>(.*?)</Value>', fields_text, re.DOTALL)

        print(f"\nSource ID: {source_id}")
        print(f"Name: {name}")

        if fn_match:
            footnote = fn_match.group(1)
            # Check for family in footnote
            has_family = 'family' in footnote.lower()
            print(f"Footnote has family: {has_family}")
            if has_family:
                # Extract the family portion
                family_match = re.search(r'sheet \d+[AB]?, family \d+, line \d+', footnote, re.IGNORECASE)
                if family_match:
                    print(f"  -> {family_match.group(0)}")

        if sfn_match:
            short_footnote = sfn_match.group(1)
            has_family = 'family' in short_footnote.lower()
            print(f"ShortFootnote has family: {has_family}")
            if has_family:
                family_match = re.search(r'sheet \d+[AB]?, family \d+, line \d+', short_footnote, re.IGNORECASE)
                if family_match:
                    print(f"  -> {family_match.group(0)}")

    conn.close()


if __name__ == "__main__":
    main()
