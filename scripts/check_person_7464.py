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

# Get citation for PersonID 7464
cursor.execute("""
    SELECT
        c.CitationID, s.SourceID, s.Name as SourceName,
        s.Fields, c.Fields as CitationFields
    FROM EventTable e
    JOIN CitationLinkTable cl ON e.EventID = cl.OwnerID AND cl.OwnerType = 2
    JOIN CitationTable c ON cl.CitationID = c.CitationID
    JOIN SourceTable s ON c.SourceID = s.SourceID
    WHERE e.OwnerID = 7464
      AND e.EventType = 18
      AND e.Date LIKE '%1940%'
""")

row = cursor.fetchone()
if row:
    citation_id, source_id, source_name, fields_blob, citation_fields_blob = row

    print("PersonID: 7464 (Veronica Constance Acord)")
    print(f"CitationID: {citation_id}")
    print(f"SourceID: {source_id}")
    print(f"\nSource Name:")
    print(source_name)

    if fields_blob:
        root = ET.fromstring(fields_blob.decode('utf-8'))
        footnote_elem = root.find('.//Field[Name="Footnote"]/Value')
        if footnote_elem is not None and footnote_elem.text:
            print(f"\n{'='*80}")
            print("FOOTNOTE FROM SourceTable.Fields:")
            print('='*80)
            print(footnote_elem.text)

            # Test different regex patterns
            footnote = footnote_elem.text

            print(f"\n{'='*80}")
            print("REGEX TESTING:")
            print('='*80)

            # Old pattern (broken)
            old_pattern = r'https?://[^)>\s]+familysearch\.org[^)>\s]+'
            old_match = re.search(old_pattern, footnote)
            print(f"\nOld pattern: {old_pattern}")
            print(f"Match: {old_match.group(0) if old_match else 'NO MATCH'}")

            # New pattern (fixed)
            new_pattern = r'https?://[^\s)>]*familysearch\.org[^\s)>]+'
            new_match = re.search(new_pattern, footnote)
            print(f"\nNew pattern: {new_pattern}")
            print(f"Match: {new_match.group(0) if new_match else 'NO MATCH'}")

            # Even simpler pattern
            simple_pattern = r'https?://familysearch\.org[^\s)>]+'
            simple_match = re.search(simple_pattern, footnote)
            print(f"\nSimple pattern: {simple_pattern}")
            print(f"Match: {simple_match.group(0) if simple_match else 'NO MATCH'}")

conn.close()
