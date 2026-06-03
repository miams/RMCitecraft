#!/usr/bin/env python3
"""
Census Match Script for RootsMagic Genealogy Skill

Find RIN candidates for a census record based on name, age, and location.

Usage:
    uv run python .claude/skills/rootsmagic-genealogy/scripts/census_match.py \
        --name "Sarah Iiams" --year 1790 --age-range 50 60 --state Maryland

    uv run python .claude/skills/rootsmagic-genealogy/scripts/census_match.py \
        --census-id 2499
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from rmcitecraft.database.connection import connect_rmtree

# Surname variants for Iiams family
SURNAME_VARIANTS = ['Iiams', 'Ijams', 'Iams', 'Imes', 'Iames', 'Ijames', 'Iiames', 'Himes', 'Himas']


def parse_year(date_str: str) -> int | None:
    """Extract year from RootsMagic date format."""
    if date_str and len(date_str) >= 7:
        year_str = date_str[3:7]
        if year_str.isdigit():
            return int(year_str)
    return None


def get_census_record(census_person_id: int) -> dict | None:
    """Get census record from census.db."""
    census_path = Path.home() / ".rmcitecraft" / "census.db"
    if not census_path.exists():
        return None

    conn = sqlite3.connect(str(census_path))
    cursor = conn.cursor()

    cursor.execute("""
        SELECT cp.person_id, cp.full_name, cp.surname, cp.given_name,
               pg.census_year, pg.state, pg.county,
               cp.age, cp.sex
        FROM census_person cp
        JOIN census_page pg ON cp.page_id = pg.page_id
        WHERE cp.person_id = ?
    """, (census_person_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        'person_id': row[0],
        'full_name': row[1],
        'surname': row[2],
        'given_name': row[3],
        'census_year': row[4],
        'state': row[5],
        'county': row[6],
        'age': row[7],
        'sex': row[8]
    }


def calculate_birth_range(census_year: int, age: int = None, age_range: tuple = None) -> tuple:
    """Calculate birth year range from census year and age."""
    if age is not None:
        # Age at census ± 2 years for accuracy
        birth_year = census_year - age
        return (birth_year - 2, birth_year + 2)
    elif age_range:
        # Convert age range to birth range
        min_age, max_age = age_range
        return (census_year - max_age - 2, census_year - min_age + 2)
    else:
        # Default: could be any adult (16+) in census year
        return (census_year - 100, census_year - 16)


def find_candidates(cursor, surname: str, given: str = None,
                    birth_range: tuple = None, state: str = None,
                    sex: str = None) -> list:
    """Find RIN candidates matching criteria."""

    # Build surname variants search
    surname_base = surname.strip().title()
    variants = [surname_base]

    # Add known variants if it's an Iiams-like name
    for variant in SURNAME_VARIANTS:
        if variant.lower() in surname_base.lower() or surname_base.lower() in variant.lower():
            variants = SURNAME_VARIANTS
            break

    surname_conditions = " OR ".join(["n.Surname LIKE ?" for _ in variants])
    params = [f"%{v}%" for v in variants]

    # Base query
    query = f"""
        SELECT p.PersonID, n.Given, n.Surname, p.Sex,
               (SELECT e.Date FROM EventTable e
                WHERE e.OwnerID = p.PersonID AND e.EventType = 1) as Birth,
               (SELECT pl.Name FROM EventTable e
                LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
                WHERE e.OwnerID = p.PersonID AND e.EventType = 1) as BirthPlace,
               (SELECT e.Date FROM EventTable e
                WHERE e.OwnerID = p.PersonID AND e.EventType = 2) as Death
        FROM PersonTable p
        JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
        WHERE ({surname_conditions})
    """

    # Add given name filter
    if given:
        query += " AND n.Given LIKE ?"
        params.append(f"%{given}%")

    # Add sex filter
    if sex:
        sex_code = 0 if sex.upper() == 'M' else 1 if sex.upper() == 'F' else None
        if sex_code is not None:
            query += " AND p.Sex = ?"
            params.append(sex_code)

    query += " ORDER BY n.Surname, Birth"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    # Filter and score candidates
    candidates = []
    for row in rows:
        rin, given_name, surname, sex_code, birth, birthplace, death = row

        birth_year = parse_year(birth)
        death_year = parse_year(death)

        # Skip if birth year doesn't match range
        if birth_range and birth_year:
            if birth_year < birth_range[0] or birth_year > birth_range[1]:
                continue

        # Skip if deceased before census
        # (We'd need census_year passed in for this check)

        # Calculate match score
        score = 0.5  # Base score

        # Boost for exact name match
        if given and given_name and given.lower() in given_name.lower():
            score += 0.2

        # Boost for location match
        if state and birthplace and state.lower() in birthplace.lower():
            score += 0.15

        # Boost for having birth date
        if birth_year:
            score += 0.1

        candidates.append({
            'rin': rin,
            'given': given_name or '',
            'surname': surname or '',
            'sex': 'M' if sex_code == 0 else 'F' if sex_code == 1 else '?',
            'birth_year': birth_year,
            'birthplace': birthplace or '',
            'death_year': death_year,
            'score': min(score, 1.0)
        })

    # Sort by score descending
    candidates.sort(key=lambda c: c['score'], reverse=True)
    return candidates


def print_candidates(candidates: list, limit: int = 20) -> None:
    """Print candidate matches."""
    if not candidates:
        print("No candidates found.")
        return

    print(f"\nFound {len(candidates)} candidate(s):\n")
    print(f"{'Score':<6} {'RIN':<6} {'Name':<25} {'Sex':<4} {'Birth':<6} {'Birthplace'}")
    print("-" * 80)

    for cand in candidates[:limit]:
        score = f"{cand['score']:.2f}"
        name = f"{cand['given']} {cand['surname']}"[:25]
        birth = str(cand['birth_year']) if cand['birth_year'] else '?'
        place = cand['birthplace'][:30]

        print(f"{score:<6} {cand['rin']:<6} {name:<25} {cand['sex']:<4} {birth:<6} {place}")


def main():
    parser = argparse.ArgumentParser(description="Find RIN candidates for census records")
    parser.add_argument("--db", default="data/Iiams.rmtree", help="RootsMagic database path")
    parser.add_argument("--census-id", type=int, help="Census person ID from census.db")
    parser.add_argument("--name", help="Full name to search")
    parser.add_argument("--surname", help="Surname to search")
    parser.add_argument("--given", help="Given name to search")
    parser.add_argument("--year", type=int, help="Census year")
    parser.add_argument("--age", type=int, help="Age at census")
    parser.add_argument("--age-range", nargs=2, type=int, metavar=("MIN", "MAX"),
                        help="Age range at census")
    parser.add_argument("--state", help="State filter")
    parser.add_argument("--sex", choices=['M', 'F'], help="Sex filter")
    parser.add_argument("--limit", type=int, default=20, help="Max results to show")

    args = parser.parse_args()

    # Get search criteria from census.db record or arguments
    surname = args.surname
    given = args.given
    census_year = args.year
    state = args.state
    sex = args.sex
    age = args.age

    if args.census_id:
        census = get_census_record(args.census_id)
        if not census:
            print(f"Census ID {args.census_id} not found.", file=sys.stderr)
            sys.exit(1)

        print(f"Census record: {census['full_name']}, {census['census_year']}, "
              f"{census['state']}, {census['county']}")

        surname = surname or census['surname'] or census['full_name'].split()[-1]
        given = given or census['given_name']
        census_year = census_year or census['census_year']
        state = state or census['state']
        sex = sex or census['sex']
        age = age or census['age']

    elif args.name:
        parts = args.name.split()
        if len(parts) >= 2:
            surname = surname or parts[-1]
            given = given or parts[0]
        else:
            surname = surname or args.name

    if not surname:
        parser.error("Surname required (via --surname, --name, or --census-id)")

    # Calculate birth year range
    if census_year:
        birth_range = calculate_birth_range(census_year, age, args.age_range)
        print(f"Birth year range: {birth_range[0]}-{birth_range[1]}")
    else:
        birth_range = None

    try:
        conn = connect_rmtree(args.db)
        cursor = conn.cursor()

        candidates = find_candidates(cursor, surname, given, birth_range, state, sex)
        print_candidates(candidates, args.limit)

        conn.close()

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
