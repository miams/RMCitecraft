#!/usr/bin/env python3
"""
Family Tree Script for RootsMagic Genealogy Skill

Display family relationships for a person.

Usage:
    uv run python .claude/skills/rootsmagic-genealogy/scripts/family_tree.py 1561
    uv run python .claude/skills/rootsmagic-genealogy/scripts/family_tree.py 1561 --ancestors 3
    uv run python .claude/skills/rootsmagic-genealogy/scripts/family_tree.py 1561 --descendants 2
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


def get_person_info(cursor, rin: int) -> dict | None:
    """Get basic info for a person."""
    cursor.execute("""
        SELECT p.PersonID, n.Given, n.Surname, p.Sex,
               (SELECT e.Date FROM EventTable e
                WHERE e.OwnerID = p.PersonID AND e.EventType = 1) as Birth,
               (SELECT e.Date FROM EventTable e
                WHERE e.OwnerID = p.PersonID AND e.EventType = 2) as Death
        FROM PersonTable p
        JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
        WHERE p.PersonID = ?
    """, (rin,))
    row = cursor.fetchone()
    if not row:
        return None

    return {
        'rin': row[0],
        'given': row[1] or '',
        'surname': row[2] or '',
        'sex': 'M' if row[3] == 0 else 'F' if row[3] == 1 else '?',
        'birth': parse_year(row[4]) or '?',
        'death': parse_year(row[5]) or '?'
    }


def format_person(person: dict) -> str:
    """Format person for display."""
    return f"{person['given']} {person['surname']} (RIN {person['rin']}, {person['sex']}, b.{person['birth']} d.{person['death']})"


def get_parents(cursor, rin: int) -> tuple:
    """Get parents of a person."""
    cursor.execute("""
        SELECT f.FatherID, f.MotherID
        FROM ChildTable c
        JOIN FamilyTable f ON c.FamilyID = f.FamilyID
        WHERE c.ChildID = ?
    """, (rin,))
    row = cursor.fetchone()
    if row:
        father = get_person_info(cursor, row[0]) if row[0] else None
        mother = get_person_info(cursor, row[1]) if row[1] else None
        return father, mother
    return None, None


def get_spouses(cursor, rin: int) -> list:
    """Get spouses of a person."""
    cursor.execute("""
        SELECT
            CASE WHEN f.FatherID = ? THEN f.MotherID ELSE f.FatherID END as SpouseID,
            (SELECT e.Date FROM EventTable e
             WHERE e.OwnerID = f.FamilyID AND e.OwnerType = 1 AND e.EventType = 300) as MarrDate
        FROM FamilyTable f
        WHERE f.FatherID = ? OR f.MotherID = ?
    """, (rin, rin, rin))

    spouses = []
    for row in cursor.fetchall():
        spouse_id, marr_date = row
        if spouse_id:
            spouse = get_person_info(cursor, spouse_id)
            if spouse:
                spouse['marriage'] = parse_year(marr_date) or '?'
                spouses.append(spouse)
    return spouses


def get_children(cursor, rin: int) -> list:
    """Get children of a person."""
    cursor.execute("""
        SELECT c.ChildID
        FROM FamilyTable f
        JOIN ChildTable c ON c.FamilyID = f.FamilyID
        WHERE f.FatherID = ? OR f.MotherID = ?
    """, (rin, rin))

    children = []
    for row in cursor.fetchall():
        child = get_person_info(cursor, row[0])
        if child:
            children.append(child)

    # Sort by birth year
    children.sort(key=lambda c: c['birth'] if c['birth'] != '?' else '9999')
    return children


def get_siblings(cursor, rin: int) -> list:
    """Get siblings of a person."""
    cursor.execute("""
        SELECT c2.ChildID
        FROM ChildTable c1
        JOIN ChildTable c2 ON c1.FamilyID = c2.FamilyID
        WHERE c1.ChildID = ? AND c2.ChildID != ?
    """, (rin, rin))

    siblings = []
    for row in cursor.fetchall():
        sibling = get_person_info(cursor, row[0])
        if sibling:
            siblings.append(sibling)

    siblings.sort(key=lambda s: s['birth'] if s['birth'] != '?' else '9999')
    return siblings


def print_ancestors(cursor, rin: int, generations: int, level: int = 0) -> None:
    """Recursively print ancestors."""
    if level >= generations:
        return

    father, mother = get_parents(cursor, rin)

    indent = "  " * level

    if father:
        print(f"{indent}Father: {format_person(father)}")
        print_ancestors(cursor, father['rin'], generations, level + 1)

    if mother:
        print(f"{indent}Mother: {format_person(mother)}")
        print_ancestors(cursor, mother['rin'], generations, level + 1)


def print_descendants(cursor, rin: int, generations: int, level: int = 0) -> None:
    """Recursively print descendants."""
    if level >= generations:
        return

    children = get_children(cursor, rin)
    indent = "  " * level

    for child in children:
        print(f"{indent}Child: {format_person(child)}")
        print_descendants(cursor, child['rin'], generations, level + 1)


def main():
    parser = argparse.ArgumentParser(description="Display family relationships")
    parser.add_argument("rin", type=int, help="Person RIN")
    parser.add_argument("--db", default="data/Iiams.rmtree", help="Database path")
    parser.add_argument("--ancestors", type=int, default=0,
                        help="Number of ancestor generations to show")
    parser.add_argument("--descendants", type=int, default=0,
                        help="Number of descendant generations to show")

    args = parser.parse_args()

    try:
        conn = connect_rmtree(args.db)
        cursor = conn.cursor()

        # Get person info
        person = get_person_info(cursor, args.rin)
        if not person:
            print(f"RIN {args.rin} not found.", file=sys.stderr)
            sys.exit(1)

        # Print header
        print("=" * 60)
        print(f"FAMILY TREE: {format_person(person)}")
        print("=" * 60)

        # Parents
        father, mother = get_parents(cursor, args.rin)
        if father or mother:
            print("\nPARENTS:")
            if father:
                print(f"  Father: {format_person(father)}")
            if mother:
                print(f"  Mother: {format_person(mother)}")

        # Ancestors (if requested)
        if args.ancestors > 1:
            print(f"\nANCESTORS ({args.ancestors} generations):")
            print_ancestors(cursor, args.rin, args.ancestors)

        # Siblings
        siblings = get_siblings(cursor, args.rin)
        if siblings:
            print(f"\nSIBLINGS ({len(siblings)}):")
            for sib in siblings:
                print(f"  {format_person(sib)}")

        # Spouses
        spouses = get_spouses(cursor, args.rin)
        if spouses:
            print(f"\nSPOUSES ({len(spouses)}):")
            for sp in spouses:
                print(f"  {format_person(sp)} m.{sp.get('marriage', '?')}")

        # Children
        children = get_children(cursor, args.rin)
        if children:
            print(f"\nCHILDREN ({len(children)}):")
            for child in children:
                print(f"  {format_person(child)}")

        # Descendants (if requested)
        if args.descendants > 1:
            print(f"\nDESCENDANTS ({args.descendants} generations):")
            print_descendants(cursor, args.rin, args.descendants)

        conn.close()

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
