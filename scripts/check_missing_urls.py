#!/usr/bin/env python3
"""Check for census citations without FamilySearch URLs."""
import sqlite3
import xml.etree.ElementTree as ET
import re
from pathlib import Path

db_path = Path('./data/Iiams.rmtree')

# Load ICU extension
conn = sqlite3.connect(db_path)
conn.enable_load_extension(True)
conn.load_extension('./sqlite-extension/icu.dylib')
conn.execute("SELECT icu_load_collation('en_US@colStrength=primary;caseLevel=off;normalization=on','RMNOCASE')")
conn.enable_load_extension(False)

cursor = conn.cursor()

# Find 1940 census events
cursor.execute("""
    SELECT
        e.EventID, e.OwnerID as PersonID, n.Given, n.Surname,
        c.CitationID, s.SourceID, s.Name as SourceName,
        s.Fields, c.Fields as CitationFields
    FROM EventTable e
    JOIN NameTable n ON e.OwnerID = n.OwnerID AND n.IsPrimary = 1
    JOIN CitationLinkTable cl ON e.EventID = cl.OwnerID AND cl.OwnerType = 2
    JOIN CitationTable c ON cl.CitationID = c.CitationID
    JOIN SourceTable s ON c.SourceID = s.SourceID
    WHERE e.EventType = 18
      AND e.Date LIKE ?
      AND s.TemplateID = 0
    ORDER BY n.Surname COLLATE RMNOCASE, n.Given COLLATE RMNOCASE
    LIMIT 20
""", ('%1940%',))

with_urls = []
without_urls = []

for row in cursor.fetchall():
    event_id, person_id, given, surname, citation_id, source_id, source_name, fields_blob, citation_fields_blob = row

    full_name = f"{given or ''} {surname or ''}".strip()

    # Parse SourceTable.Fields BLOB for Footnote with FamilySearch URL
    familysearch_url = None

    if fields_blob:
        try:
            root = ET.fromstring(fields_blob.decode('utf-8'))
            footnote_elem = root.find('.//Field[Name="Footnote"]/Value')
            if footnote_elem is not None and footnote_elem.text:
                footnote = footnote_elem.text
                if 'familysearch.org' in footnote.lower():
                    url_match = re.search(r'https?://(?:www\.)?familysearch\.org[^\s)>]+', footnote, re.IGNORECASE)
                    if url_match:
                        familysearch_url = url_match.group(0).rstrip('.,;')
        except Exception:
            pass

    # Also check CitationTable.Fields for Page field
    if not familysearch_url and citation_fields_blob:
        try:
            root = ET.fromstring(citation_fields_blob.decode('utf-8'))
            page_elem = root.find('.//Field[Name="Page"]/Value')
            if page_elem is not None and page_elem.text:
                page_text = page_elem.text
                if 'familysearch.org' in page_text.lower():
                    url_match = re.search(r'https?://(?:www\.)?familysearch\.org[^\s)>]+', page_text, re.IGNORECASE)
                    if url_match:
                        familysearch_url = url_match.group(0).rstrip('.,;')
        except Exception:
            pass

    if familysearch_url:
        with_urls.append({
            'person_id': person_id,
            'full_name': full_name,
            'citation_id': citation_id,
            'url': familysearch_url
        })
    else:
        without_urls.append({
            'person_id': person_id,
            'full_name': full_name,
            'citation_id': citation_id,
            'source_name': source_name
        })

conn.close()

print("\n" + "="*80)
print("1940 CENSUS CITATIONS - URL ANALYSIS")
print("="*80)
print(f"\nExamined: {len(with_urls) + len(without_urls)} citations")
print(f"With FamilySearch URLs: {len(with_urls)}")
print(f"WITHOUT FamilySearch URLs: {len(without_urls)}")

if without_urls:
    print("\n" + "="*80)
    print("CITATIONS WITHOUT FAMILYSEARCH URLs:")
    print("="*80)
    for item in without_urls:
        print(f"\nPersonID: {item['person_id']}")
        print(f"Name: {item['full_name']}")
        print(f"CitationID: {item['citation_id']}")
        print(f"Source: {item['source_name'][:80]}...")
else:
    print("\n✓ All examined citations have FamilySearch URLs!")

if with_urls:
    print("\n" + "="*80)
    print("CITATIONS WITH FAMILYSEARCH URLs:")
    print("="*80)
    for i, item in enumerate(with_urls[:10], 1):
        print(f"\n{i}. PersonID: {item['person_id']} - {item['full_name']}")
        print(f"   URL: {item['url'][:60]}...")
