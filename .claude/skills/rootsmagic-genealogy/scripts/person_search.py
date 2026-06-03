#!/usr/bin/env python3
"""
Person Search Script for RootsMagic Genealogy Skill

Search for persons in RootsMagic database by various criteria.

Usage:
    uv run python .claude/skills/rootsmagic-genealogy/scripts/person_search.py --surname Iiams
    uv run python .claude/skills/rootsmagic-genealogy/scripts/person_search.py --given Sarah --surname Iiams
    uv run python .claude/skills/rootsmagic-genealogy/scripts/person_search.py --birth-range 1730 1750
    uv run python .claude/skills/rootsmagic-genealogy/scripts/person_search.py --birthplace "Anne Arundel"
    uv run python .claude/skills/rootsmagic-genealogy/scripts/person_search.py --rin 1561
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from rmcitecraft.database.connection import connect_rmtree


def parse_year(date_str: str) -> str | None:
    """Extract year from RootsMagic date format."""
    if date_str and len(date_str) >= 7:
        return date_str[3:7]
    return None


def search_by_rin(cursor, rin: int) -> list:
    """Get detailed info for a specific RIN."""
    cursor.execute("""
        SELECT p.PersonID, n.Given, n.Surname, p.Sex,
               (SELECT e.Date FROM EventTable e
                WHERE e.OwnerID = p.PersonID AND e.EventType = 1) as Birth,
               (SELECT pl.Name FROM EventTable e
                LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
                WHERE e.OwnerID = p.PersonID AND e.EventType = 1) as BirthPlace,
               (SELECT e.Date FROM EventTable e
                WHERE e.OwnerID = p.PersonID AND e.EventType = 2) as Death,
               (SELECT pl.Name FROM EventTable e
                LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
                WHERE e.OwnerID = p.PersonID AND e.EventType = 2) as DeathPlace
        FROM PersonTable p
        JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
        WHERE p.PersonID = ?
    """, (rin,))
    return cursor.fetchall()


def search_by_name(cursor, surname: str = None, given: str = None) -> list:
    """Search persons by name."""
    conditions = []
    params = []

    if surname:
        conditions.append("n.Surname LIKE ?")
        params.append(f"%{surname}%")
    if given:
        conditions.append("n.Given LIKE ?")
        params.append(f"%{given}%")

    if not conditions:
        return []

    where_clause = " AND ".join(conditions)

    cursor.execute(f"""
        SELECT p.PersonID, n.Given, n.Surname, p.Sex,
               (SELECT e.Date FROM EventTable e
                WHERE e.OwnerID = p.PersonID AND e.EventType = 1) as Birth,
               (SELECT pl.Name FROM EventTable e
                LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
                WHERE e.OwnerID = p.PersonID AND e.EventType = 1) as BirthPlace,
               (SELECT e.Date FROM EventTable e
                WHERE e.OwnerID = p.PersonID AND e.EventType = 2) as Death,
               (SELECT pl.Name FROM EventTable e
                LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
                WHERE e.OwnerID = p.PersonID AND e.EventType = 2) as DeathPlace
        FROM PersonTable p
        JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
        WHERE {where_clause}
        ORDER BY n.Surname, Birth
    """, params)
    return cursor.fetchall()


def search_by_birth_range(cursor, start_year: int, end_year: int) -> list:
    """Search persons by birth year range."""
    cursor.execute("""
        SELECT p.PersonID, n.Given, n.Surname, p.Sex,
               e.Date as Birth,
               (SELECT pl.Name FROM PlaceTable pl WHERE pl.PlaceID = e.PlaceID) as BirthPlace,
               (SELECT e2.Date FROM EventTable e2
                WHERE e2.OwnerID = p.PersonID AND e2.EventType = 2) as Death,
               NULL as DeathPlace
        FROM PersonTable p
        JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
        JOIN EventTable e ON e.OwnerID = p.PersonID AND e.EventType = 1
        WHERE SUBSTR(e.Date, 4, 4) BETWEEN ? AND ?
        ORDER BY e.Date, n.Surname
    """, (str(start_year), str(end_year)))
    return cursor.fetchall()


def search_by_birthplace(cursor, place: str) -> list:
    """Search persons by birthplace."""
    cursor.execute("""
        SELECT p.PersonID, n.Given, n.Surname, p.Sex,
               e.Date as Birth,
               pl.Name as BirthPlace,
               (SELECT e2.Date FROM EventTable e2
                WHERE e2.OwnerID = p.PersonID AND e2.EventType = 2) as Death,
               NULL as DeathPlace
        FROM PersonTable p
        JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
        JOIN EventTable e ON e.OwnerID = p.PersonID AND e.EventType = 1
        JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
        WHERE pl.Name LIKE ?
        ORDER BY n.Surname, e.Date
    """, (f"%{place}%",))
    return cursor.fetchall()


def format_results(results: list) -> None:
    """Print formatted search results."""
    if not results:
        print("No results found.")
        return

    print(f"\nFound {len(results)} person(s):\n")
    print(f"{'RIN':<6} {'Name':<25} {'Sex':<4} {'Birth':<6} {'Death':<6} {'Birthplace'}")
    print("-" * 80)

    for row in results:
        rin, given, surname, sex, birth, birthplace, death, deathplace = row

        name = f"{given or ''} {surname or ''}".strip()[:25]
        sex_str = 'M' if sex == 0 else 'F' if sex == 1 else '?'
        birth_yr = parse_year(birth) or '?'
        death_yr = parse_year(death) or '?'
        birthplace = (birthplace or '')[:30]

        print(f"{rin:<6} {name:<25} {sex_str:<4} {birth_yr:<6} {death_yr:<6} {birthplace}")


def main():
    parser = argparse.ArgumentParser(description="Search RootsMagic database for persons")
    parser.add_argument("--db", default="data/Iiams.rmtree", help="Database path")
    parser.add_argument("--rin", type=int, help="Search by RIN")
    parser.add_argument("--surname", help="Search by surname (partial match)")
    parser.add_argument("--given", help="Search by given name (partial match)")
    parser.add_argument("--birth-range", nargs=2, type=int, metavar=("START", "END"),
                        help="Search by birth year range")
    parser.add_argument("--birthplace", help="Search by birthplace (partial match)")

    args = parser.parse_args()

    # Validate at least one search criteria
    if not any([args.rin, args.surname, args.given, args.birth_range, args.birthplace]):
        parser.error("At least one search criteria required")

    try:
        conn = connect_rmtree(args.db)
        cursor = conn.cursor()

        if args.rin:
            results = search_by_rin(cursor, args.rin)
        elif args.birth_range:
            results = search_by_birth_range(cursor, args.birth_range[0], args.birth_range[1])
        elif args.birthplace:
            results = search_by_birthplace(cursor, args.birthplace)
        else:
            results = search_by_name(cursor, args.surname, args.given)

        format_results(results)

        conn.close()

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
