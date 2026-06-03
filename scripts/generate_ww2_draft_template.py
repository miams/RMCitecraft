#!/usr/bin/env python3
"""
Generate CSV template for WWII Draft Registration batch updates.

This script queries the database for all WWII Selective Service sources
and generates a template CSV file that the user can populate with
FamilySearch citations.

Output: ww2_draft_import_template.csv
"""

import csv
from pathlib import Path
from rmcitecraft.database.connection import connect_rmtree


def get_ww2_sources_with_persons():
    """Query all WWII Selective Service sources and find their associated persons."""
    conn = connect_rmtree('data/Iiams.rmtree')
    cursor = conn.cursor()

    # Get all WWII Selective Service sources
    cursor.execute('''
        SELECT s.SourceID, s.Name, s.RefNumber
        FROM SourceTable s
        WHERE s.Name LIKE 'Military Records: World War II Selective Service Registration Cards%'
        ORDER BY s.Name
    ''')

    sources = cursor.fetchall()
    print(f"Found {len(sources)} WWII Selective Service sources")

    results = []

    for source_id, source_name, ref_number in sources:
        # Extract person name from source name
        # Pattern: "Military Records: World War II Selective Service Registration Cards - Surname, Given (years)"
        import re
        name_match = re.search(r' - (.+?)(?:\s*\(\d{4}-\d{4}\))?$', source_name)
        if not name_match:
            print(f"  Warning: Could not extract name from: {source_name}")
            continue

        person_name = name_match.group(1).strip()

        # Try to find the person by name
        # Split "Surname, Given" format
        if ',' in person_name:
            parts = person_name.split(',', 1)
            surname = parts[0].strip()
            given = parts[1].strip() if len(parts) > 1 else ""
        else:
            # Handle cases without comma
            name_parts = person_name.split()
            given = name_parts[0] if name_parts else ""
            surname = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ""

        # Find person in database
        cursor.execute('''
            SELECT n.OwnerID, n.Given, n.Surname, n.BirthYear, n.DeathYear
            FROM NameTable n
            WHERE n.Surname = ? AND n.Given = ? AND n.IsPrimary = 1
        ''', (surname, given))

        person_result = cursor.fetchone()

        if person_result:
            rin, db_given, db_surname, birth_year, death_year = person_result

            # Check if this person has a WWII draft event (EventType 1025)
            cursor.execute('''
                SELECT EventID
                FROM EventTable
                WHERE OwnerType = 0 AND OwnerID = ? AND EventType = 1025
            ''', (rin,))

            event_result = cursor.fetchone()
            has_event = bool(event_result)

            # Check existing media
            cursor.execute('''
                SELECT COUNT(*)
                FROM MultimediaTable m
                JOIN MediaLinkTable ml ON ml.MediaID = m.MediaID
                WHERE ml.OwnerType = 3 AND ml.OwnerID = ?
            ''', (source_id,))

            media_count = cursor.fetchone()[0]

            # Check if any existing media is from FamilySearch
            cursor.execute('''
                SELECT m.RefNumber
                FROM MultimediaTable m
                JOIN MediaLinkTable ml ON ml.MediaID = m.MediaID
                WHERE ml.OwnerType = 3 AND ml.OwnerID = ?
            ''', (source_id,))

            media_refs = [row[0] for row in cursor.fetchall()]
            has_familysearch = any('familysearch.org' in (ref or '').lower() for ref in media_refs)

            results.append({
                'source_id': source_id,
                'source_name': source_name,
                'rin': rin,
                'given': db_given,
                'surname': db_surname,
                'birth_year': birth_year or "",
                'death_year': death_year or "",
                'has_event': has_event,
                'media_count': media_count,
                'has_familysearch': has_familysearch,
                'fold3_ref': ref_number or ""
            })
        else:
            print(f"  Warning: Person not found - {surname}, {given}")
            results.append({
                'source_id': source_id,
                'source_name': source_name,
                'rin': 'NOT_FOUND',
                'given': given,
                'surname': surname,
                'birth_year': "",
                'death_year': "",
                'has_event': False,
                'media_count': 0,
                'has_familysearch': False,
                'fold3_ref': ref_number or ""
            })

    conn.close()
    return results


def generate_csv_template(results, output_path):
    """Generate CSV template with all sources."""

    # CSV columns
    fieldnames = [
        'rin',
        'source_id',
        'given_name',
        'surname',
        'birth_year',
        'death_year',
        'familysearch_citation',
        'entry_name',
        'county',
        'state',
        'registration_date',
        'has_event',
        'media_count',
        'has_familysearch',
        'notes'
    ]

    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for result in results:
            # Flag records that need attention
            notes = []
            if result['rin'] == 'NOT_FOUND':
                notes.append("PERSON NOT FOUND IN DATABASE")
            if result['has_familysearch']:
                notes.append("Already has FamilySearch media")
            if not result['has_event']:
                notes.append("No WWII draft event")

            writer.writerow({
                'rin': result['rin'],
                'source_id': result['source_id'],
                'given_name': result['given'],
                'surname': result['surname'],
                'birth_year': result['birth_year'],
                'death_year': result['death_year'],
                'familysearch_citation': '',  # User will fill this in
                'entry_name': '',  # Optional - will prompt if empty
                'county': '',  # User will fill this in
                'state': '',  # Will be extracted from citation
                'registration_date': '',  # Will be extracted from citation
                'has_event': 'YES' if result['has_event'] else 'NO',
                'media_count': result['media_count'],
                'has_familysearch': 'YES' if result['has_familysearch'] else 'NO',
                'notes': '; '.join(notes)
            })

    print(f"\n✓ Generated template: {output_path}")
    print(f"  Total sources: {len(results)}")
    print(f"  Need FamilySearch citations: {sum(1 for r in results if not r['has_familysearch'])}")
    print(f"  Already have FamilySearch: {sum(1 for r in results if r['has_familysearch'])}")
    print(f"  No WWII event: {sum(1 for r in results if not r['has_event'])}")
    print(f"  Person not found: {sum(1 for r in results if r['rin'] == 'NOT_FOUND')}")


def main():
    """Main script execution."""
    print("\n" + "="*70)
    print("WWII DRAFT REGISTRATION - CSV TEMPLATE GENERATOR")
    print("="*70)

    print("\nQuerying database for WWII Selective Service sources...")
    results = get_ww2_sources_with_persons()

    output_path = Path("ww2_draft_import_template.csv")
    print(f"\nGenerating CSV template...")
    generate_csv_template(results, output_path)

    print("\n" + "="*70)
    print("INSTRUCTIONS FOR FILLING OUT THE TEMPLATE")
    print("="*70)
    print("\n1. Open ww2_draft_import_template.csv in Excel/Google Sheets")
    print("\n2. For each row, fill in the 'familysearch_citation' column:")
    print('   Example:')
    print('   "Pennsylvania, World War II Draft Registration Cards, 1940-1945",')
    print('   FamilySearch (https://www.familysearch.org/ark:/61903/1:1:Q2SF-G31L :')
    print('   Fri Feb 23 21:21:36 UTC 2024), Entry for Alexander Murdoch Iams and')
    print('   Grace D Iams, 16 Oct 1940.')
    print("\n3. Fill in the 'county' column (just the county name, e.g., 'Allegheny')")
    print("\n4. Optional columns:")
    print("   - entry_name: Only fill if name on card differs from database name")
    print("   - state/registration_date: Will be auto-extracted from citation")
    print("\n5. Review the 'notes' column for any issues:")
    print("   - 'Already has FamilySearch media' - may want to skip")
    print("   - 'No WWII draft event' - will skip event linking")
    print("   - 'PERSON NOT FOUND' - needs manual investigation")
    print("\n6. Save the file and use it with the batch processing script")
    print("\nDone!")


if __name__ == '__main__':
    main()
