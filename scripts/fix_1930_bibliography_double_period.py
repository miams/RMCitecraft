#!/usr/bin/env python3
"""
Fix double period in 1930 census bibliography entries.

The issue: "United States, Census, 1930.". <i>FamilySearch</i>.
Should be:  "United States, Census, 1930." <i>FamilySearch</i>.

The period should be INSIDE the quote only, per Evidence Explained.
"""

from pathlib import Path
from rmcitecraft.database.connection import connect_rmtree

def main():
    db_path = Path('data/Iiams.rmtree')

    # Connect with write access
    print("Connecting to database...")
    conn = connect_rmtree(db_path, read_only=False)
    cursor = conn.cursor()

    # Find affected sources
    print("\nFinding sources with double period issue...")
    cursor.execute("""
        SELECT SourceID, Name, CAST(Fields AS TEXT) as FieldsText
        FROM SourceTable
        WHERE Name LIKE 'Fed Census: 1930%'
          AND CAST(Fields AS TEXT) LIKE '%1930.&quot;.%'
        ORDER BY SourceID
    """)

    sources = cursor.fetchall()
    print(f"Found {len(sources)} sources with the issue\n")

    if not sources:
        print("No sources need fixing!")
        conn.close()
        return

    # Ask for confirmation
    print("This will fix the bibliography entries by removing the extra period after the quote.")
    print("Before: \"United States, Census, 1930.\". <i>FamilySearch</i>.")
    print("After:  \"United States, Census, 1930.\" <i>FamilySearch</i>.")
    response = input(f"\nProceed with fixing {len(sources)} sources? (yes/no): ")

    if response.lower() not in ['yes', 'y']:
        print("Aborted.")
        conn.close()
        return

    # Fix each source
    fixed_count = 0
    for source_id, name, fields_text in sources:
        # Replace the pattern: 1930.". with 1930."
        # In XML it's: 1930.&quot;. should become 1930.&quot;
        new_fields = fields_text.replace('1930.&quot;.', '1930.&quot;')

        # Verify we actually changed something
        if new_fields != fields_text:
            # Update the database (encode back to BLOB)
            cursor.execute(
                "UPDATE SourceTable SET Fields = ? WHERE SourceID = ?",
                (new_fields.encode('utf-8'), source_id)
            )
            fixed_count += 1
            if fixed_count <= 5:
                print(f"✓ Fixed SourceID {source_id}: {name[:60]}...")

    # Commit changes
    conn.commit()
    print(f"\n✅ Successfully fixed {fixed_count} sources")

    # Verify the fix
    print("\nVerifying fix...")
    cursor.execute("""
        SELECT COUNT(*)
        FROM SourceTable
        WHERE Name LIKE 'Fed Census: 1930%'
          AND CAST(Fields AS TEXT) LIKE '%1930.&quot;.%'
    """)
    remaining = cursor.fetchone()[0]

    if remaining == 0:
        print("✅ All sources fixed - no double periods remaining!")
    else:
        print(f"⚠️  Warning: {remaining} sources still have the issue")

    conn.close()

if __name__ == '__main__':
    main()
