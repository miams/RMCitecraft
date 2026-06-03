#!/usr/bin/env python3
"""
Update WW2 draft CSV with birth/death years from RootsMagic database.
Then append additional men who should have draft registrations.

WW2 Draft Registration Dates:
- First: Oct 16, 1940 - males 21-35 (born 1905-1919)
- Second: Jul 1, 1941 - males who reached 21 since first (born 1920)
- Third: Feb 16, 1942 - males 20-45 not previously registered (born 1897-1922)
- Fourth: Apr 27, 1942 - males 45-65 (born 1877-1897)
- Fifth: Jun 30, 1942 - males 18-20 (born 1922-1924)
- Sixth: Dec 10-31, 1942 - males who reached 18 after Nov 12, 1942 (born 1924)
- Additional: Nov 16-Dec 31, 1943 - citizens abroad 18-45 (born 1898-1925)
"""

import csv
import sys
from pathlib import Path
from typing import Optional, Tuple, List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from rmcitecraft.database.connection import connect_rmtree
from rmcitecraft.utils.rm_date import RMDateParser


def get_birth_death_years(conn, rin: int) -> Tuple[Optional[int], Optional[int], List[str]]:
    """
    Get birth and death years for a person by RIN.
    Checks both EventTable (birth/death events) and NameTable (BirthYear/DeathYear fields).

    Returns:
        Tuple of (birth_year, death_year, warnings)
        - birth_year: Year of birth or None
        - death_year: Year of death or None
        - warnings: List of warning messages if multiple non-primary events exist
    """
    cursor = conn.cursor()
    warnings = []

    # Get birth events
    cursor.execute("""
        SELECT Date, IsPrimary, EventID
        FROM EventTable
        WHERE OwnerID = ? AND OwnerType = 0 AND EventType = 1
        ORDER BY IsPrimary DESC, EventID
    """, (rin,))

    birth_events = cursor.fetchall()
    birth_year = None

    if birth_events:
        primary_births = [e for e in birth_events if e[1] == 1]

        if len(primary_births) > 1:
            warnings.append(f"RIN {rin}: Multiple primary birth events found")
        elif len(primary_births) == 0 and len(birth_events) > 1:
            warnings.append(f"RIN {rin}: Multiple birth events, none marked primary")

        # Use primary if exists, otherwise first event
        birth_date = primary_births[0][0] if primary_births else birth_events[0][0]
        birth_year = RMDateParser.extract_year(birth_date)

    # If no birth event, check NameTable.BirthYear
    if not birth_year:
        cursor.execute("""
            SELECT BirthYear
            FROM NameTable
            WHERE OwnerID = ? AND IsPrimary = 1
        """, (rin,))
        result = cursor.fetchone()
        if result and result[0]:
            birth_year = result[0]

    # Get death events
    cursor.execute("""
        SELECT Date, IsPrimary, EventID
        FROM EventTable
        WHERE OwnerID = ? AND OwnerType = 0 AND EventType = 2
        ORDER BY IsPrimary DESC, EventID
    """, (rin,))

    death_events = cursor.fetchall()
    death_year = None

    if death_events:
        primary_deaths = [e for e in death_events if e[1] == 1]

        if len(primary_deaths) > 1:
            warnings.append(f"RIN {rin}: Multiple primary death events found")
        elif len(primary_deaths) == 0 and len(death_events) > 1:
            warnings.append(f"RIN {rin}: Multiple death events, none marked primary")

        # Use primary if exists, otherwise first event
        death_date = primary_deaths[0][0] if primary_deaths else death_events[0][0]
        death_year = RMDateParser.extract_year(death_date)

    # If no death event, check NameTable.DeathYear
    if not death_year:
        cursor.execute("""
            SELECT DeathYear
            FROM NameTable
            WHERE OwnerID = ? AND IsPrimary = 1
        """, (rin,))
        result = cursor.fetchone()
        if result and result[0]:
            death_year = result[0]

    return birth_year, death_year, warnings


def estimate_birth_year_from_family(conn, rin: int) -> Optional[int]:
    """
    Estimate birth year from siblings and parents when direct data is unavailable.

    Returns:
        Estimated birth year or None if cannot estimate
    """
    cursor = conn.cursor()

    # Try to find siblings and their birth years
    cursor.execute("""
        SELECT DISTINCT sib_birth.Date
        FROM PersonTable p
        JOIN FamilyTable f ON p.ParentID = f.FamilyID
        JOIN ChildTable ct ON f.FamilyID = ct.FamilyID
        JOIN PersonTable sibling ON ct.ChildID = sibling.PersonID
        JOIN EventTable sib_birth ON sibling.PersonID = sib_birth.OwnerID
            AND sib_birth.EventType = 1 AND sib_birth.IsPrimary = 1
        WHERE p.PersonID = ? AND sibling.PersonID != ?
        ORDER BY sib_birth.SortDate
    """, (rin, rin))

    sibling_dates = cursor.fetchall()
    sibling_years = [RMDateParser.extract_year(d[0]) for d in sibling_dates if d[0]]
    sibling_years = [y for y in sibling_years if y]

    if len(sibling_years) >= 2:
        # Estimate as midpoint of sibling range
        return (min(sibling_years) + max(sibling_years)) // 2

    # Try to estimate from parents
    cursor.execute("""
        SELECT father_birth.Date, mother_birth.Date
        FROM PersonTable p
        JOIN FamilyTable f ON p.ParentID = f.FamilyID
        LEFT JOIN EventTable father_birth ON f.FatherID = father_birth.OwnerID
            AND father_birth.EventType = 1 AND father_birth.IsPrimary = 1
        LEFT JOIN EventTable mother_birth ON f.MotherID = mother_birth.OwnerID
            AND mother_birth.EventType = 1 AND mother_birth.IsPrimary = 1
        WHERE p.PersonID = ?
    """, (rin,))

    parent_data = cursor.fetchone()
    if parent_data:
        father_year = RMDateParser.extract_year(parent_data[0]) if parent_data[0] else None
        mother_year = RMDateParser.extract_year(parent_data[1]) if parent_data[1] else None

        # Estimate as parent birth + 25-30 years (typical generation gap)
        if father_year and mother_year:
            parent_avg = (father_year + mother_year) // 2
            return parent_avg + 28
        elif father_year:
            return father_year + 28
        elif mother_year:
            return mother_year + 26

    return None


def get_eligible_registrations(birth_year: int, death_year: Optional[int] = None) -> List[str]:
    """
    Determine which WW2 draft registrations a person was eligible for.

    Returns:
        List of registration names the person was eligible for
    """
    registrations = []

    # Calculate age on each registration date
    # First: Oct 16, 1940 - males 21-35
    age_first = 1940 - birth_year
    if 21 <= age_first <= 35 and (not death_year or death_year >= 1940):
        registrations.append("1st (Oct 1940)")

    # Second: Jul 1, 1941 - males who reached 21 since first (turned 21 between Oct 1940 and Jul 1941)
    if birth_year == 1920 and (not death_year or death_year >= 1941):
        registrations.append("2nd (Jul 1941)")

    # Third: Feb 16, 1942 - males 20-45 not previously registered
    age_third = 1942 - birth_year
    if 20 <= age_third <= 45 and (not death_year or death_year >= 1942):
        registrations.append("3rd (Feb 1942)")

    # Fourth: Apr 27, 1942 - males 45-65
    if 45 <= age_third <= 65 and (not death_year or death_year >= 1942):
        registrations.append("4th (Apr 1942, ages 45-65)")

    # Fifth: Jun 30, 1942 - males 18-20
    if 18 <= age_third <= 20 and (not death_year or death_year >= 1942):
        registrations.append("5th (Jun 1942)")

    # Sixth: Dec 10-31, 1942 - males who reached 18 after Nov 12, 1942
    # Born in late 1924 (turned 18 in late 1942)
    if birth_year == 1924 and (not death_year or death_year >= 1942):
        registrations.append("6th (Dec 1942)")

    # Additional: Nov 16-Dec 31, 1943 - citizens abroad 18-45
    age_additional = 1943 - birth_year
    if 18 <= age_additional <= 45 and (not death_year or death_year >= 1943):
        registrations.append("Additional (1943, abroad)")

    return registrations


def should_have_draft_registration(birth_year: Optional[int], death_year: Optional[int],
                                   estimated_birth: Optional[int] = None) -> bool:
    """
    Determine if a person should have a WW2 draft registration based on birth/death years.

    WW2 registrations: 1940-1943, ages 18-65
    - Born 1877-1925 would be eligible for at least one registration
    - Must be alive during 1940-1943
    """
    # Use direct birth year if available, otherwise estimated
    by = birth_year if birth_year else estimated_birth

    if not by:
        return False

    # Must be born between 1877 and 1925 to be 18-65 during registrations
    if by < 1877 or by > 1925:
        return False

    # If death year known and died before 1940, no registration
    if death_year and death_year < 1940:
        return False

    # Check if eligible for at least one registration
    registrations = get_eligible_registrations(by, death_year)
    return len(registrations) > 0


def could_reasonably_be_alive(birth_year: Optional[int], death_year: Optional[int],
                              estimated_birth: Optional[int] = None) -> bool:
    """
    Determine if person could reasonably be alive during 1940-1943 based on available data.
    """
    by = birth_year if birth_year else estimated_birth

    if not by:
        return True  # Unknown, give benefit of doubt

    # If died before 1940, definitely not alive
    if death_year and death_year < 1940:
        return False

    # If born after 1943, definitely not eligible
    if by > 1925:
        return False

    # If born before 1850, would be 90+ in 1940, unlikely to be alive
    if by < 1850:
        return False

    return True


def find_additional_candidates(conn) -> List[Dict]:
    """
    Find all men in database who should have WW2 draft registrations
    but are not currently in the CSV.
    Checks both EventTable and NameTable for birth/death information.
    """
    cursor = conn.cursor()

    # Find all males - check both EventTable and NameTable for birth/death info
    cursor.execute("""
        SELECT
            p.PersonID as rin,
            n.Given as given_name,
            n.Surname as surname,
            birth.Date as birth_date,
            death.Date as death_date,
            n.BirthYear,
            n.DeathYear
        FROM PersonTable p
        JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
        LEFT JOIN EventTable birth ON p.PersonID = birth.OwnerID
            AND birth.EventType = 1 AND birth.IsPrimary = 1
        LEFT JOIN EventTable death ON p.PersonID = death.OwnerID
            AND death.EventType = 2 AND death.IsPrimary = 1
        WHERE p.Sex = 0  -- Male
        ORDER BY n.Surname, n.Given
    """)

    candidates = []
    for row in cursor.fetchall():
        rin, given_name, surname, birth_date, death_date, name_birth_year, name_death_year = row

        # Filter out entries without surnames
        if not surname or surname.strip() == '':
            continue

        # Filter out "infant" entries
        given_lower = (given_name or '').lower().strip()
        surname_lower = surname.lower().strip()
        if given_lower == 'infant' or surname_lower == 'infant':
            continue

        # Get birth year from event first, then from NameTable if not available
        birth_year = RMDateParser.extract_year(birth_date) if birth_date else None
        if not birth_year and name_birth_year:
            birth_year = name_birth_year

        # Get death year from event first, then from NameTable if not available
        death_year = RMDateParser.extract_year(death_date) if death_date else None
        if not death_year and name_death_year:
            death_year = name_death_year

        # Try to estimate birth year if still not available
        estimated_birth = None
        if not birth_year:
            estimated_birth = estimate_birth_year_from_family(conn, rin)

        if should_have_draft_registration(birth_year, death_year, estimated_birth):
            # Determine which registrations they were eligible for
            final_birth_year = birth_year or estimated_birth
            eligible_regs = get_eligible_registrations(final_birth_year, death_year)

            # Build notes
            if not birth_year and estimated_birth:
                notes = f"CANDIDATE - Birth year estimated. Eligible: {', '.join(eligible_regs)}"
            else:
                notes = f"CANDIDATE - Eligible: {', '.join(eligible_regs)}"

            candidates.append({
                'rin': rin,
                'given_name': given_name or '',
                'surname': surname or '',
                'birth_year': final_birth_year or '',
                'death_year': death_year or '',
                'notes': notes
            })

    return candidates


def main():
    # Paths
    input_csv = Path('ww2_draft.csv')
    output_csv = Path('ww2_draft_updated.csv')
    log_file = Path('ww2_draft_update.log')

    # Connect to database
    db_path = Path('data/Iiams.rmtree')
    conn = connect_rmtree(db_path)

    print(f"Reading {input_csv}...")

    # Read existing CSV
    with open(input_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    print(f"Found {len(rows)} existing entries")

    # Collect all warnings
    all_warnings = []

    # Update birth/death years for existing entries
    existing_rins = set()
    for row in rows:
        rin = row.get('rin', '').strip()
        if not rin or rin == '':
            continue

        try:
            rin_int = int(rin)
            existing_rins.add(rin_int)

            birth_year, death_year, warnings = get_birth_death_years(conn, rin_int)
            all_warnings.extend(warnings)

            # Update CSV fields (only if we got data from database)
            if birth_year is not None:
                row['birth_year'] = str(birth_year)
            if death_year is not None:
                row['death_year'] = str(death_year)

            # Add eligible registrations to notes if we have birth year
            birth_yr = birth_year
            if not birth_yr and row.get('birth_year'):
                try:
                    birth_yr = int(row['birth_year'])
                except ValueError:
                    pass

            if birth_yr:
                death_yr = death_year
                if not death_yr and row.get('death_year'):
                    try:
                        death_yr = int(row['death_year'])
                    except ValueError:
                        pass

                eligible_regs = get_eligible_registrations(birth_yr, death_yr)
                if eligible_regs:
                    existing_notes = row.get('notes', '').strip()
                    reg_note = f"Eligible: {', '.join(eligible_regs)}"
                    if existing_notes:
                        row['notes'] = f"{existing_notes}; {reg_note}"
                    else:
                        row['notes'] = reg_note

        except ValueError:
            all_warnings.append(f"Invalid RIN: {rin}")

    print(f"Updated {len(rows)} existing entries")

    # Find additional candidates
    print("\nFinding additional candidates...")
    all_candidates = find_additional_candidates(conn)

    # Filter out those already in CSV
    new_candidates = [c for c in all_candidates if c['rin'] not in existing_rins]

    print(f"Found {len(new_candidates)} additional candidates")

    # Add new candidates to rows
    for candidate in new_candidates:
        rows.append({
            'rin': candidate['rin'],
            'source_id': '',
            'given_name': candidate['given_name'],
            'surname': candidate['surname'],
            'birth_year': candidate['birth_year'],
            'death_year': candidate['death_year'],
            'familysearch_citation': '',
            'entry_name': '',
            'county': '',
            'state': '',
            'registration_date': '',
            'has_event': 'NO',
            'media_count': '0',
            'has_familysearch': 'NO',
            'notes': candidate['notes']
        })

    # Write updated CSV
    print(f"\nWriting {output_csv}...")
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} total entries ({len(new_candidates)} new)")

    # Write log file
    print(f"\nWriting {log_file}...")
    with open(log_file, 'w') as f:
        f.write("WW2 Draft Update Log\n")
        f.write("=" * 60 + "\n\n")

        if all_warnings:
            f.write("WARNINGS (Multiple Events):\n")
            f.write("-" * 60 + "\n")
            for warning in all_warnings:
                f.write(f"{warning}\n")
            f.write("\n")

        f.write(f"Summary:\n")
        f.write(f"  Existing entries updated: {len(rows) - len(new_candidates)}\n")
        f.write(f"  New candidates added: {len(new_candidates)}\n")
        f.write(f"  Total entries: {len(rows)}\n")
        f.write(f"  Warnings logged: {len(all_warnings)}\n")

    print(f"\nComplete! Check {log_file} for warnings.")

    conn.close()


if __name__ == '__main__':
    main()
