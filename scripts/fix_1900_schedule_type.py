#!/usr/bin/env python3
"""
Fix 1900 Census Schedule Type

Adds "population schedule" to footnotes and "pop. sch." to short footnotes
for 1900 census sources that are missing this required element.

The schedule type is inserted after the state name, before the locality or ED.

Usage:
    python scripts/fix_1900_schedule_type.py --dry-run    # Preview changes
    python scripts/fix_1900_schedule_type.py              # Apply changes
"""

import argparse
import re
import sqlite3
from pathlib import Path


# State names for matching in footnotes
STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "District of Columbia", "Florida", "Georgia",
    "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky",
    "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire",
    "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota",
    "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island",
    "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont",
    "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
    # Territories
    "Arizona Territory", "New Mexico Territory", "Oklahoma Territory",
    "Indian Territory", "Utah Territory",
]

# State abbreviations for matching in short footnotes
STATE_ABBREVS = [
    "Ala.", "Alaska", "Ariz.", "Ark.", "Calif.", "Colo.", "Conn.", "Del.",
    "D.C.", "Fla.", "Ga.", "Hawaii", "Idaho", "Ill.", "Ind.", "Iowa",
    "Kans.", "Ky.", "La.", "Maine", "Md.", "Mass.", "Mich.", "Minn.",
    "Miss.", "Mo.", "Mont.", "Nebr.", "Nev.", "N.H.", "N.J.", "N.Mex.",
    "N.Y.", "N.C.", "N.Dak.", "Ohio", "Okla.", "Oreg.", "Pa.", "R.I.",
    "S.C.", "S.Dak.", "Tenn.", "Tex.", "Utah", "Vt.", "Va.", "Wash.",
    "W.Va.", "Wis.", "Wyo.",
    # Territories (various forms)
    "Ariz. Terr.", "N.Mex. Terr.", "Okla. Terr.", "Ind. Terr.", "Utah Terr.",
    "Ariz. Territory", "N.Mex. Territory", "Okla. Territory", "Ind. Territory", "Utah Territory",
]


def extract_field(fields_text: str, field_name: str) -> str:
    """Extract a field value from Fields XML."""
    pattern = rf'<Name>{field_name}</Name>\s*<Value>(.*?)</Value>'
    match = re.search(pattern, fields_text, re.DOTALL)
    return match.group(1) if match else ""


def update_field(fields_text: str, field_name: str, new_value: str) -> str:
    """Update a field value in Fields XML using safe replacement."""
    pattern = rf'(<Name>{re.escape(field_name)}</Name>\s*<Value>)(.*?)(</Value>)'

    def replacer(m):
        return m.group(1) + new_value + m.group(3)

    return re.sub(pattern, replacer, fields_text, flags=re.DOTALL)


def add_schedule_to_footnote(footnote: str) -> tuple[str, bool]:
    """
    Add 'population schedule, ' to footnote after state name.

    Returns: (modified_footnote, was_modified)
    """
    if "population schedule" in footnote.lower():
        return footnote, False

    # Try to find pattern: "State, " followed by locality or ED
    # We need to insert "population schedule, " after the state

    for state in sorted(STATES, key=len, reverse=True):  # Longest first
        # Pattern: "County, State, " - insert after State
        pattern = rf'(\b{re.escape(state)},\s*)'
        match = re.search(pattern, footnote)
        if match:
            # Insert "population schedule, " after the state
            insert_pos = match.end()
            new_footnote = footnote[:insert_pos] + "population schedule, " + footnote[insert_pos:]
            return new_footnote, True

    return footnote, False


def add_schedule_to_short_footnote(short_footnote: str) -> tuple[str, bool]:
    """
    Add 'pop. sch., ' to short footnote after state abbreviation.

    Returns: (modified_short_footnote, was_modified)
    """
    if "pop. sch." in short_footnote.lower():
        return short_footnote, False

    # Try to find pattern: "Co., StateAbbrev., " followed by locality or ED
    for abbrev in sorted(STATE_ABBREVS, key=len, reverse=True):  # Longest first
        # Pattern: "StateAbbrev., " - insert after abbreviation
        pattern = rf'(\b{re.escape(abbrev)},\s*)'
        match = re.search(pattern, short_footnote)
        if match:
            # Insert "pop. sch., " after the state abbreviation
            insert_pos = match.end()
            new_short = short_footnote[:insert_pos] + "pop. sch., " + short_footnote[insert_pos:]
            return new_short, True

    return short_footnote, False


def get_sources_missing_schedule(db_path: str) -> list[dict]:
    """Get 1900 census sources missing schedule type in footnote or short footnote."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT SourceID, Name, CAST(Fields AS TEXT) as fields_text
        FROM SourceTable
        WHERE Name LIKE 'Fed Census: 1900%'
        ORDER BY SourceID
    """)

    sources = []
    for row in cursor.fetchall():
        source_id, name, fields_text = row

        footnote = extract_field(fields_text, "Footnote")
        short_footnote = extract_field(fields_text, "ShortFootnote")

        missing_fn = "population schedule" not in footnote.lower()
        missing_short = "pop. sch." not in short_footnote.lower()

        if missing_fn or missing_short:
            sources.append({
                'source_id': source_id,
                'name': name,
                'fields_text': fields_text,
                'footnote': footnote,
                'short_footnote': short_footnote,
                'missing_fn': missing_fn,
                'missing_short': missing_short,
            })

    conn.close()
    return sources


def main():
    parser = argparse.ArgumentParser(
        description="Add schedule type to 1900 census footnotes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying database"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/Iiams.rmtree"),
        help="Path to RootsMagic database"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of sources to process (0 = all)"
    )

    args = parser.parse_args()

    print(f"Database: {args.db}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY CHANGES'}")
    print()

    # Get sources needing updates
    sources = get_sources_missing_schedule(str(args.db))

    if args.limit > 0:
        sources = sources[:args.limit]

    print(f"Found {len(sources)} sources needing schedule type updates")
    print()

    if not sources:
        print("No sources to update.")
        return

    # Process sources
    fn_updated = 0
    fn_failed = 0
    short_updated = 0
    short_failed = 0

    updates = []  # Collect updates for batch apply

    for source in sources:
        source_id = source['source_id']
        fields_text = source['fields_text']
        footnote = source['footnote']
        short_footnote = source['short_footnote']

        new_fields = fields_text
        fn_changed = False
        short_changed = False

        # Update footnote if needed
        if source['missing_fn']:
            new_footnote, fn_changed = add_schedule_to_footnote(footnote)
            if fn_changed:
                new_fields = update_field(new_fields, "Footnote", new_footnote)
                fn_updated += 1
            else:
                fn_failed += 1

        # Update short footnote if needed
        if source['missing_short']:
            new_short, short_changed = add_schedule_to_short_footnote(short_footnote)
            if short_changed:
                new_fields = update_field(new_fields, "ShortFootnote", new_short)
                short_updated += 1
            else:
                short_failed += 1

        if fn_changed or short_changed:
            updates.append({
                'source_id': source_id,
                'name': source['name'],
                'new_fields': new_fields,
                'fn_changed': fn_changed,
                'short_changed': short_changed,
                'old_footnote': footnote,
                'new_footnote': new_footnote if fn_changed else footnote,
                'old_short': short_footnote,
                'new_short': new_short if short_changed else short_footnote,
            })

    # Print summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Footnotes to update: {fn_updated}")
    print(f"Footnotes failed (no state match): {fn_failed}")
    print(f"Short footnotes to update: {short_updated}")
    print(f"Short footnotes failed (no state match): {short_failed}")
    print()

    # Show preview of changes
    print("=" * 70)
    print("PREVIEW OF CHANGES (first 10)")
    print("=" * 70)

    for update in updates[:10]:
        print(f"\nSource {update['source_id']}: {update['name'][:60]}...")

        if update['fn_changed']:
            # Show just the changed portion
            old_fn = update['old_footnote']
            new_fn = update['new_footnote']

            # Find where they differ
            for i, (a, b) in enumerate(zip(old_fn, new_fn)):
                if a != b:
                    start = max(0, i - 30)
                    end = min(len(new_fn), i + 50)
                    print(f"  Footnote change at position {i}:")
                    print(f"    Before: ...{old_fn[start:i+20]}...")
                    print(f"    After:  ...{new_fn[start:end]}...")
                    break

        if update['short_changed']:
            old_short = update['old_short']
            new_short = update['new_short']

            for i, (a, b) in enumerate(zip(old_short, new_short)):
                if a != b:
                    start = max(0, i - 30)
                    end = min(len(new_short), i + 40)
                    print(f"  Short footnote change at position {i}:")
                    print(f"    Before: ...{old_short[start:i+15]}...")
                    print(f"    After:  ...{new_short[start:end]}...")
                    break

    if len(updates) > 10:
        print(f"\n... and {len(updates) - 10} more updates")

    # Show failed sources
    failed_sources = [s for s in sources
                      if (s['missing_fn'] and "population schedule" not in
                          add_schedule_to_footnote(s['footnote'])[0].lower())]

    if failed_sources:
        print()
        print("=" * 70)
        print(f"SOURCES THAT COULD NOT BE UPDATED ({len(failed_sources)})")
        print("=" * 70)
        for source in failed_sources[:5]:
            print(f"\nSource {source['source_id']}: {source['name']}")
            print(f"  Footnote: {source['footnote'][:100]}...")

    # Apply changes if not dry run
    if not args.dry_run and updates:
        print()
        print("=" * 70)
        print("APPLYING CHANGES")
        print("=" * 70)

        conn = sqlite3.connect(str(args.db))
        cursor = conn.cursor()

        for update in updates:
            cursor.execute("""
                UPDATE SourceTable
                SET Fields = ?
                WHERE SourceID = ?
            """, (update['new_fields'].encode('utf-8'), update['source_id']))

        conn.commit()
        conn.close()

        print(f"Updated {len(updates)} sources")

        # Verify
        print()
        print("Verification - checking 3 random updated sources:")
        conn = sqlite3.connect(str(args.db))
        cursor = conn.cursor()

        sample_ids = [u['source_id'] for u in updates[:3]]
        for sid in sample_ids:
            cursor.execute("""
                SELECT Name, CAST(Fields AS TEXT) as fields_text
                FROM SourceTable WHERE SourceID = ?
            """, (sid,))
            row = cursor.fetchone()
            if row:
                name, fields_text = row
                footnote = extract_field(fields_text, "Footnote")
                short = extract_field(fields_text, "ShortFootnote")

                has_fn = "population schedule" in footnote.lower()
                has_short = "pop. sch." in short.lower()

                print(f"\nSource {sid}:")
                print(f"  Footnote has 'population schedule': {has_fn}")
                print(f"  Short has 'pop. sch.': {has_short}")

        conn.close()

    elif args.dry_run:
        print()
        print("=" * 70)
        print("DRY RUN COMPLETE - No changes made")
        print("Run without --dry-run to apply changes")
        print("=" * 70)


if __name__ == "__main__":
    main()
