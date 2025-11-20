#!/usr/bin/env python3
"""Check specific person's citation."""
import sqlite3
import xml.etree.ElementTree as ET
import re
from pathlib import Path

db_path = Path('./data/Iiams.rmtree')

conn = sqlite3.connect(db_path)
conn.enable_load_extension(True)
conn.load_extension('./sqlite-extension/icu.dylib')
conn.execute("SELECT icu_load_collation('en_US@colStrength=primary;caseLevel=off;normalization=on','RMNOCASE')")
conn.enable_load_extension(False)

cursor = conn.cursor()

# Get ALL citations for PersonID 856
cursor.execute("""
    SELECT
        c.CitationID, s.SourceID, s.Name as SourceName,
        s.Fields, c.Fields as CitationFields
    FROM EventTable e
    JOIN CitationLinkTable cl ON e.EventID = cl.OwnerID AND cl.OwnerType = 2
    JOIN CitationTable c ON cl.CitationID = c.CitationID
    JOIN SourceTable s ON c.SourceID = s.SourceID
    WHERE e.OwnerID = 856
      AND e.EventType = 18
      AND e.Date LIKE '%1940%'
""")

rows = cursor.fetchall()
print(f"Found {len(rows)} citations for PersonID 856")

for row in rows:
    citation_id, source_id, source_name, fields_blob, citation_fields_blob = row

    print(f"\n{'='*80}")
    print(f"CitationID: {citation_id}")
    print(f"SourceID: {source_id}")
    print(f"\nSource Name:")
    print(source_name)

    if fields_blob:
        root = ET.fromstring(fields_blob.decode('utf-8'))
        footnote_elem = root.find('.//Field[Name="Footnote"]/Value')
        if footnote_elem is not None and footnote_elem.text:
            print(f"\nFOOTNOTE:")
            print(footnote_elem.text)

            # Test regex
            footnote = footnote_elem.text

            # Current pattern (wrong - missing www.)
            current_pattern = r'https?://familysearch\.org[^\s)>]+'
            current_match = re.search(current_pattern, footnote, re.IGNORECASE)
            print(f"\nCurrent pattern: {current_pattern}")
            print(f"Match: {current_match.group(0) if current_match else 'NO MATCH'}")

            # Fixed pattern (with optional www.)
            fixed_pattern = r'https?://(?:www\.)?familysearch\.org[^\s)>]+'
            fixed_match = re.search(fixed_pattern, footnote, re.IGNORECASE)
            print(f"\nFixed pattern: {fixed_pattern}")
            print(f"Match: {fixed_match.group(0) if fixed_match else 'NO MATCH'}")

conn.close()
