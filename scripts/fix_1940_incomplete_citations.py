#!/usr/bin/env python3
"""Fix incomplete 1940 Census Footnotes and Short Footnotes.

This script:
1. Finds 1940 Census sources with incomplete Footnotes/Short Footnotes (missing sheet/line)
2. Parses the Source Name to extract ED, sheet, line, state, county
3. Preserves existing person names in citations (only populates if empty)
4. Generates complete Evidence Explained format citations
"""

import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


def parse_source_name(source_name: str) -> dict | None:
    """Parse 1940 Census Source Name to extract components.

    Format: Fed Census: 1940, State, County [ED xx-xx, sheet yy, line zz] Person Name

    Returns dict with: state, county, ed, sheet, line, person_name
    """
    # Pattern: Fed Census: 1940, State, County [ED xx-xx, sheet yy, line zz] Person
    pattern = r'Fed Census: 1940,\s*([^,]+),\s*([^\[]+?)\s*\[ED\s*(\d+[A-Z]?-\d+[A-Z]?),\s*sheet\s*(\d+[AB]?),\s*line\s*(\d+)\]\s*[- ]*(.+)?$'

    match = re.match(pattern, source_name, re.IGNORECASE)
    if not match:
        return None

    state = match.group(1).strip()
    county = match.group(2).strip()
    ed = match.group(3).strip()
    sheet = match.group(4).strip()
    line = match.group(5).strip()
    person_name = match.group(6).strip() if match.group(6) else ''

    return {
        'state': state,
        'county': county,
        'ed': ed,
        'sheet': sheet,
        'line': line,
        'person_name': person_name
    }


def extract_person_from_citation(citation: str) -> str | None:
    """Extract person name from existing citation text.

    Looks for the person name before '; imaged' or at end of short footnote.
    """
    if not citation:
        return None

    # For footnote: person name comes before '; imaged'
    match = re.search(r',\s*([^,;]+?);\s*imaged', citation)
    if match:
        return match.group(1).strip()

    # For short footnote: person name is at the end after the last comma before period
    # Pattern: ..., E.D. xx-xx, sheet yy, line zz, Person Name.
    match = re.search(r'line\s+\d+,\s*([^.]+)\.$', citation)
    if match:
        return match.group(1).strip()

    # Fallback: last segment before period
    match = re.search(r',\s*([^,]+)\.$', citation)
    if match:
        return match.group(1).strip()

    return None


def get_state_abbreviation(state: str) -> str:
    """Get standard state abbreviation for short footnote."""
    abbreviations = {
        'Alabama': 'Ala.', 'Alaska': 'Alaska', 'Arizona': 'Ariz.',
        'Arkansas': 'Ark.', 'California': 'Calif.', 'Colorado': 'Colo.',
        'Connecticut': 'Conn.', 'Delaware': 'Del.', 'Florida': 'Fla.',
        'Georgia': 'Ga.', 'Hawaii': 'Hawaii', 'Idaho': 'Idaho',
        'Illinois': 'Ill.', 'Indiana': 'Ind.', 'Indiania': 'Ind.',  # Handle typo
        'Iowa': 'Iowa', 'Kansas': 'Kans.', 'Kentucky': 'Ky.',
        'Louisiana': 'La.', 'Maine': 'Maine', 'Maryland': 'Md.',
        'Massachusetts': 'Mass.', 'Masssachusetts': 'Mass.',  # Handle typo
        'Michigan': 'Mich.', 'Minnesota': 'Minn.', 'Mississippi': 'Miss.',
        'Missouri': 'Mo.', 'Montana': 'Mont.', 'Nebraska': 'Nebr.',
        'Nevada': 'Nev.', 'New Hampshire': 'N.H.', 'New Jersey': 'N.J.',
        'New Mexico': 'N.M.', 'New York': 'N.Y.', 'North Carolina': 'N.C.',
        'North Dakota': 'N.D.', 'Ohio': 'Oh.', 'Oklahoma': 'Okla.',
        'Oregon': 'Oreg.', 'Pennsylvania': 'Pa.', 'Rhode Island': 'R.I.',
        'South Carolina': 'S.C.', 'South Dakota': 'S.D.', 'Tennessee': 'Tenn.',
        'Texas': 'Tex.', 'Utah': 'Utah', 'Vermont': 'Vt.',
        'Virginia': 'Va.', 'Washington': 'Wash.', 'West Virginia': 'W.Va.',
        'Wisconsin': 'Wis.', 'Wyoming': 'Wyo.', 'District of Columbia': 'D.C.'
    }
    return abbreviations.get(state, state)


def generate_footnote(parsed: dict, person_name: str, existing_url: str | None = None) -> str:
    """Generate Evidence Explained format footnote for 1940 Census.

    Format: 1940 U.S. census, County County, State, enumeration district (ED) xx-xx,
    sheet yy, line zz, Person Name; imaged, "United States Census, 1940,"
    <i>FamilySearch</i> (URL : accessed date).
    """
    state = parsed['state']
    county = parsed['county']
    ed = parsed['ed']
    sheet = parsed['sheet']
    line = parsed['line']

    # Build county name (add "County" if not already present)
    if not county.lower().endswith('county'):
        county_full = f"{county} County"
    else:
        county_full = county

    # Build the footnote
    footnote = (
        f"1940 U.S. census, {county_full}, {state}, "
        f"enumeration district (ED) {ed}, sheet {sheet}, line {line}, "
        f"{person_name}; imaged, &quot;United States Census, 1940,&quot; "
        f"&lt;i&gt;FamilySearch&lt;/i&gt;"
    )

    # Add URL if available
    if existing_url:
        footnote += f" ({existing_url})."
    else:
        footnote += "."

    return footnote


def generate_short_footnote(parsed: dict, person_name: str) -> str:
    """Generate Evidence Explained format short footnote for 1940 Census.

    Format: 1940 U.S. census, County Co., State abbrev., E.D. xx-xx, sheet yy, line zz, Person Name.
    """
    state = parsed['state']
    county = parsed['county']
    ed = parsed['ed']
    sheet = parsed['sheet']
    line = parsed['line']

    # Abbreviate state
    state_abbr = get_state_abbreviation(state)

    # Abbreviate county (remove "County" and add "Co.")
    county_abbr = re.sub(r'\s*County\s*$', '', county, flags=re.IGNORECASE).strip()
    county_abbr = f"{county_abbr} Co."

    short = (
        f"1940 U.S. census, {county_abbr}, {state_abbr}, "
        f"E.D. {ed}, sheet {sheet}, line {line}, {person_name}."
    )

    return short


def extract_url_from_footnote(footnote: str) -> str | None:
    """Extract FamilySearch URL from existing footnote."""
    # Look for URL pattern
    match = re.search(r'\(https?://[^\s)]+', footnote)
    if match:
        url = match.group(0)[1:]  # Remove leading (
        # Clean up and return with access date
        if ' : accessed' not in url:
            today = datetime.now().strftime('%d %B %Y')
            return f"{url} : accessed {today}"
        return url
    return None


def update_fields_blob(fields_blob: bytes, new_footnote: str | None, new_short: str | None) -> bytes:
    """Update the Fields BLOB with new footnote and/or short footnote values."""
    if not fields_blob:
        return fields_blob

    fields_text = fields_blob.decode('utf-8', errors='ignore')

    if new_footnote:
        # Replace footnote value
        fields_text = re.sub(
            r'(<Name>Footnote</Name>\s*<Value>)(.*?)(</Value>)',
            lambda m: f"{m.group(1)}{new_footnote}{m.group(3)}",
            fields_text,
            flags=re.DOTALL
        )

    if new_short:
        # Replace short footnote value
        fields_text = re.sub(
            r'(<Name>ShortFootnote</Name>\s*<Value>)(.*?)(</Value>)',
            lambda m: f"{m.group(1)}{new_short}{m.group(3)}",
            fields_text,
            flags=re.DOTALL
        )

    return fields_text.encode('utf-8')


def main():
    """Main function to fix incomplete 1940 Census citations."""
    db_path = Path('data/Iiams.rmtree')
    backup_path = Path(f'data/Iiams.rmtree.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}')

    # Create backup
    print(f"Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)
    print(f"Backup created successfully")

    # Load ICU extension for RMNOCASE
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    conn.load_extension('sqlite-extension/icu.dylib')
    conn.enable_load_extension(False)

    cursor = conn.cursor()

    # Get all 1940 Census sources
    cursor.execute('''
        SELECT SourceID, Name, Fields
        FROM SourceTable
        WHERE Name LIKE 'Fed Census: 1940,%'
    ''')

    sources = cursor.fetchall()
    print(f"\nFound {len(sources)} 1940 Census sources")

    # Analyze and fix
    footnote_fixed = 0
    short_fixed = 0
    errors = []

    for source_id, name, fields_blob in sources:
        if not fields_blob:
            continue

        fields_text = fields_blob.decode('utf-8', errors='ignore')

        # Extract current values
        fn_match = re.search(r'<Name>Footnote</Name>\s*<Value>(.*?)</Value>', fields_text, re.DOTALL)
        current_footnote = fn_match.group(1) if fn_match else ''

        sfn_match = re.search(r'<Name>ShortFootnote</Name>\s*<Value>(.*?)</Value>', fields_text, re.DOTALL)
        current_short = sfn_match.group(1) if sfn_match else ''

        # Check if complete
        fn_has_sheet = bool(re.search(r'sheet\s+\d+[AB]?', current_footnote, re.IGNORECASE))
        fn_has_line = bool(re.search(r'line\s+\d+', current_footnote, re.IGNORECASE))
        fn_complete = fn_has_sheet and fn_has_line

        sfn_has_sheet = bool(re.search(r'sheet\s+\d+[AB]?', current_short, re.IGNORECASE))
        sfn_has_line = bool(re.search(r'line\s+\d+', current_short, re.IGNORECASE))
        sfn_complete = sfn_has_sheet and sfn_has_line

        # Skip if both are complete
        if fn_complete and sfn_complete:
            continue

        # Parse source name
        parsed = parse_source_name(name)
        if not parsed:
            errors.append(f"Source {source_id}: Could not parse source name: {name}")
            continue

        new_footnote = None
        new_short = None

        # Fix footnote if incomplete
        if not fn_complete:
            # Get person name - preserve existing if present, otherwise use source name
            existing_person = extract_person_from_citation(current_footnote)
            if existing_person and existing_person.strip():
                person_name = existing_person
            else:
                # Use person from source name
                person_name = parsed['person_name']

            if not person_name:
                errors.append(f"Source {source_id}: No person name available for footnote")
                continue

            # Get existing URL
            existing_url = extract_url_from_footnote(current_footnote)

            new_footnote = generate_footnote(parsed, person_name, existing_url)
            footnote_fixed += 1

        # Fix short footnote if incomplete
        if not sfn_complete:
            # Get person name - preserve existing if present, otherwise use source name
            existing_person = extract_person_from_citation(current_short)

            # If short footnote has no person but footnote does, try footnote
            if not existing_person and fn_complete:
                existing_person = extract_person_from_citation(current_footnote)
            # If we just generated a new footnote, extract from the source name
            elif not existing_person and new_footnote:
                # Use same person as footnote
                existing_person = extract_person_from_citation(new_footnote) or parsed['person_name']

            if existing_person and existing_person.strip():
                person_name = existing_person
            else:
                person_name = parsed['person_name']

            if not person_name:
                errors.append(f"Source {source_id}: No person name available for short footnote")
                continue

            new_short = generate_short_footnote(parsed, person_name)
            short_fixed += 1

        # Update database
        if new_footnote or new_short:
            updated_blob = update_fields_blob(fields_blob, new_footnote, new_short)
            cursor.execute(
                'UPDATE SourceTable SET Fields = ? WHERE SourceID = ?',
                (updated_blob, source_id)
            )

    # Commit changes
    conn.commit()
    conn.close()

    print(f"\n=== Results ===")
    print(f"Footnotes fixed: {footnote_fixed}")
    print(f"Short Footnotes fixed: {short_fixed}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for error in errors[:10]:
            print(f"  {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    print(f"\nBackup saved to: {backup_path}")


if __name__ == '__main__':
    main()
