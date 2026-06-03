#!/usr/bin/env python3
"""Fix 1950 Census citation issues.

Fixes:
1. Missing line numbers in footnotes (data available in source name)
2. Incorrect sheet/line template for stamp format citations
3. Missing ED values in footnotes
4. Empty county/state values in footnotes
"""

import re
import sqlite3
from pathlib import Path


STATE_ABBR = {
    'Alabama': 'Ala.', 'Alaska': 'Alaska', 'Arizona': 'Ariz.', 'Arkansas': 'Ark.',
    'California': 'Calif.', 'Colorado': 'Colo.', 'Connecticut': 'Conn.',
    'Delaware': 'Del.', 'Florida': 'Fla.', 'Georgia': 'Ga.', 'Hawaii': 'Hawaii',
    'Idaho': 'Idaho', 'Illinois': 'Ill.', 'Indiana': 'Ind.', 'Iowa': 'Iowa',
    'Kansas': 'Kans.', 'Kentucky': 'Ky.', 'Louisiana': 'La.', 'Maine': 'Maine',
    'Maryland': 'Md.', 'Massachusetts': 'Mass.', 'Michigan': 'Mich.',
    'Minnesota': 'Minn.', 'Mississippi': 'Miss.', 'Missouri': 'Mo.',
    'Montana': 'Mont.', 'Nebraska': 'Nebr.', 'Nevada': 'Nev.',
    'New Hampshire': 'N.H.', 'New Jersey': 'N.J.', 'New Mexico': 'N.M.',
    'New York': 'N.Y.', 'North Carolina': 'N.C.', 'North Dakota': 'N.D.',
    'Ohio': 'Ohio', 'Oklahoma': 'Okla.', 'Oregon': 'Oreg.', 'Pennsylvania': 'Pa.',
    'Rhode Island': 'R.I.', 'South Carolina': 'S.C.', 'South Dakota': 'S.D.',
    'Tennessee': 'Tenn.', 'Texas': 'Tex.', 'Utah': 'Utah', 'Vermont': 'Vt.',
    'Virginia': 'Va.', 'Washington': 'Wash.', 'West Virginia': 'W.Va.',
    'Wisconsin': 'Wis.', 'Wyoming': 'Wyo.', 'District of Columbia': 'D.C.'
}


def parse_source_name(name: str) -> dict | None:
    """Parse source name to extract components."""
    # Pattern: Fed Census: 1950, State, County [ED xx-xx, sheet yy, line zz] Person
    # Or: Fed Census: 1950, State, County [ED xx-xx, stamp xxxxx] Person

    match = re.match(
        r'Fed Census: 1950, ([^,]+), ([^\[]+) \[ED ([\d-]+), (?:sheet (\d+), line (\d+)|stamp ([\d-]+))\]',
        name
    )
    if not match:
        return None

    return {
        'state': match.group(1).strip(),
        'county': match.group(2).strip(),
        'ed': match.group(3),
        'sheet': match.group(4),
        'line': match.group(5),
        'stamp': match.group(6),
    }


def main():
    db_path = Path('data/Iiams.rmtree')
    conn = sqlite3.connect(db_path)

    # Load ICU extension
    conn.enable_load_extension(True)
    conn.load_extension('sqlite-extension/icu.dylib')
    conn.execute(
        "SELECT icu_load_collation("
        "'en_US@colStrength=primary;caseLevel=off;normalization=on',"
        "'RMNOCASE')"
    )
    conn.enable_load_extension(False)

    cursor = conn.cursor()

    # Get all 1950 Census sources
    cursor.execute('''
        SELECT SourceID, Name, Fields FROM SourceTable
        WHERE Name LIKE 'Fed Census: 1950,%'
    ''')

    fixed_line = 0
    fixed_stamp = 0
    fixed_ed = 0
    fixed_county = 0

    for source_id, name, fields_blob in cursor.fetchall():
        if not fields_blob:
            continue

        parsed = parse_source_name(name)
        if not parsed:
            continue

        fields_text = fields_blob.decode('utf-8', errors='ignore')

        # Extract current footnote and short footnote
        fn_match = re.search(r'<Name>Footnote</Name>\s*<Value>(.*?)</Value>', fields_text, re.DOTALL)
        sfn_match = re.search(r'<Name>ShortFootnote</Name>\s*<Value>(.*?)</Value>', fields_text, re.DOTALL)

        if not fn_match or not sfn_match:
            continue

        footnote = fn_match.group(1)
        short_fn = sfn_match.group(1)
        original_fn = footnote
        original_sfn = short_fn

        # Fix 1: Has 'line ,' with empty line - insert line number from source name
        if parsed['line'] and 'line ,' in footnote:
            footnote = re.sub(r'line ,', f"line {parsed['line']},", footnote)
            short_fn = re.sub(r'line ,', f"line {parsed['line']},", short_fn)
            fixed_line += 1

        # Fix 2: Has stamp format in source name but incorrect template in footnote
        if parsed['stamp'] and ('sheet ,' in footnote or 'enumeration district (ED) ,' in footnote):
            # Replace the location section with correct stamp format
            footnote = re.sub(
                r'enumeration district \(ED\) [^,]*, sheet [^,]*, line \d+,',
                f"enumeration district (ED) {parsed['ed']}, stamp {parsed['stamp']},",
                footnote
            )
            short_fn = re.sub(
                r'E\.D\. [^,]*, sheet [^,]*, line \d+,',
                f"E.D. {parsed['ed']}, stamp {parsed['stamp']},",
                short_fn
            )
            fixed_stamp += 1

        # Fix 3: Missing ED value - insert from source name
        if parsed['ed'] and 'enumeration district (ED) ,' in footnote:
            footnote = re.sub(
                r'enumeration district \(ED\) ,',
                f"enumeration district (ED) {parsed['ed']},",
                footnote
            )
            fixed_ed += 1

        if parsed['ed'] and 'E.D. ,' in short_fn:
            short_fn = re.sub(r'E\.D\. ,', f"E.D. {parsed['ed']},", short_fn)

        # Fix 4: Empty county/state - insert from source name
        if parsed['county'] and parsed['state']:
            # Fix "1950 U.S. census,  County, ," pattern
            if '1950 U.S. census,  County, ,' in footnote:
                footnote = re.sub(
                    r'1950 U\.S\. census,  County, ,',
                    f"1950 U.S. census, {parsed['county']} County, {parsed['state']},",
                    footnote
                )
                state_abbr = STATE_ABBR.get(parsed['state'], parsed['state'])
                county_abbr = parsed['county'].replace(' County', '')
                short_fn = re.sub(
                    r'1950 U\.S\. census,  Co\., ,',
                    f"1950 U.S. census, {county_abbr} Co., {state_abbr},",
                    short_fn
                )
                fixed_county += 1

        # Update fields if changed
        if footnote != original_fn or short_fn != original_sfn:
            fields_text = re.sub(
                r'(<Name>Footnote</Name>\s*<Value>)(.*?)(</Value>)',
                lambda m: f"{m.group(1)}{footnote}{m.group(3)}",
                fields_text,
                flags=re.DOTALL
            )
            fields_text = re.sub(
                r'(<Name>ShortFootnote</Name>\s*<Value>)(.*?)(</Value>)',
                lambda m: f"{m.group(1)}{short_fn}{m.group(3)}",
                fields_text,
                flags=re.DOTALL
            )
            cursor.execute(
                'UPDATE SourceTable SET Fields = ? WHERE SourceID = ?',
                (fields_text.encode('utf-8'), source_id)
            )

    conn.commit()

    print(f"Fixed {fixed_line} citations with missing line numbers")
    print(f"Fixed {fixed_stamp} citations with incorrect stamp format")
    print(f"Fixed {fixed_ed} citations with missing ED")
    print(f"Fixed {fixed_county} citations with missing county/state")
    print(f"Total fixes: {fixed_line + fixed_stamp + fixed_ed + fixed_county}")

    conn.close()


if __name__ == '__main__':
    main()
