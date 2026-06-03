#!/usr/bin/env python3
"""
RootsMagic Database Inspector

Interactive tool to explore RootsMagic database structure and data.
Provides common queries and data exploration functions.

Usage:
    uv run python skills/rootsmagic/scripts/inspect-db.py [database_path]

If no database path provided, uses default: data/Iiams.rmtree
"""

import sys
from pathlib import Path

# Add src to path so we can import rmcitecraft modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from rmcitecraft.database.connection import connect_rmtree


def print_header(title):
    """Print formatted section header."""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def print_table(headers, rows, max_width=30):
    """Print data as formatted table."""
    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            str_val = str(val) if val is not None else ""
            if len(str_val) > max_width:
                str_val = str_val[:max_width-3] + "..."
            widths[i] = max(widths[i], len(str_val))

    # Print header
    header_format = " | ".join(f"{{:<{w}}}" for w in widths)
    print(header_format.format(*headers))
    print("-+-".join("-" * w for w in widths))

    # Print rows
    for row in rows:
        formatted_row = []
        for val in row:
            str_val = str(val) if val is not None else ""
            if len(str_val) > max_width:
                str_val = str_val[:max_width-3] + "..."
            formatted_row.append(str_val)
        print(header_format.format(*formatted_row))


def show_database_info(cursor):
    """Display general database information."""
    print_header("Database Overview")

    # Count key tables
    tables = {
        "People": "PersonTable",
        "Names": "NameTable",
        "Families": "FamilyTable",
        "Children": "ChildTable",
        "Events": "EventTable",
        "Sources": "SourceTable",
        "Citations": "CitationTable",
        "Places": "PlaceTable",
        "Media": "MultimediaTable",
    }

    print("\nRecord Counts:")
    for name, table in tables.items():
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {name:<20} {count:>8,}")


def show_surname_distribution(cursor, limit=20):
    """Show most common surnames."""
    print_header(f"Top {limit} Surnames")

    cursor.execute(f"""
        SELECT Surname, COUNT(*) as Count
        FROM NameTable
        WHERE IsPrimary = 1 AND Surname IS NOT NULL AND Surname != ''
        GROUP BY Surname
        ORDER BY Count DESC, Surname
        LIMIT {limit}
    """)

    headers = ["Surname", "Count"]
    rows = cursor.fetchall()
    print_table(headers, rows)


def show_event_type_distribution(cursor):
    """Show event type distribution."""
    print_header("Event Type Distribution")

    cursor.execute("""
        SELECT ft.Name as EventType, ft.OwnerType, COUNT(*) as Count
        FROM EventTable e
        JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
        GROUP BY e.EventType, ft.Name, ft.OwnerType
        ORDER BY Count DESC
        LIMIT 20
    """)

    headers = ["Event Type", "Owner", "Count"]
    rows = [(name, "Person" if owner == 0 else "Family", count)
            for name, owner, count in cursor.fetchall()]
    print_table(headers, rows)


def show_source_templates(cursor):
    """Show source template usage."""
    print_header("Source Template Usage")

    cursor.execute("""
        SELECT
            CASE WHEN s.TemplateID = 0 THEN 'Free-form'
                 ELSE st.Name END as Template,
            COUNT(*) as SourceCount,
            COUNT(c.CitationID) as CitationCount
        FROM SourceTable s
        LEFT JOIN SourceTemplateTable st ON s.TemplateID = st.TemplateID
        LEFT JOIN CitationTable c ON c.SourceID = s.SourceID
        GROUP BY s.TemplateID
        HAVING SourceCount > 0
        ORDER BY SourceCount DESC
        LIMIT 15
    """)

    headers = ["Template", "Sources", "Citations"]
    rows = cursor.fetchall()
    print_table(headers, rows)


def show_place_hierarchy(cursor, limit=20):
    """Show most common places."""
    print_header(f"Top {limit} Places")

    cursor.execute(f"""
        SELECT
            p.Name,
            COUNT(DISTINCT e.EventID) as EventCount
        FROM PlaceTable p
        JOIN EventTable e ON e.PlaceID = p.PlaceID
        WHERE p.PlaceType = 0
        GROUP BY p.PlaceID, p.Name
        ORDER BY EventCount DESC
        LIMIT {limit}
    """)

    headers = ["Place", "Events"]
    rows = cursor.fetchall()
    print_table(headers, rows)


def search_person(cursor, surname_pattern):
    """Search for persons by surname pattern."""
    print_header(f"Search Results: {surname_pattern}")

    cursor.execute("""
        SELECT
            p.PersonID as RIN,
            n.Given,
            n.Surname,
            CASE WHEN p.Sex = 0 THEN 'M'
                 WHEN p.Sex = 1 THEN 'F'
                 ELSE 'U' END as Sex,
            n.BirthYear,
            n.DeathYear,
            CASE WHEN p.Living = 1 THEN 'Yes' ELSE 'No' END as Living
        FROM PersonTable p
        JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
        WHERE n.Surname LIKE ? COLLATE RMNOCASE
        ORDER BY n.Surname, n.Given, n.BirthYear
        LIMIT 50
    """, (f"%{surname_pattern}%",))

    headers = ["RIN", "Given", "Surname", "Sex", "Birth", "Death", "Living"]
    rows = cursor.fetchall()

    if rows:
        print_table(headers, rows)
        print(f"\nFound {len(rows)} person(s)")
    else:
        print("\nNo matching persons found.")


def show_person_details(cursor, person_id):
    """Show detailed information for a specific person."""
    print_header(f"Person Details: RIN {person_id}")

    # Basic info
    cursor.execute("""
        SELECT
            n.Given,
            n.Surname,
            CASE WHEN p.Sex = 0 THEN 'Male'
                 WHEN p.Sex = 1 THEN 'Female'
                 ELSE 'Unknown' END as Sex,
            n.BirthYear,
            n.DeathYear,
            CASE WHEN p.Living = 1 THEN 'Yes' ELSE 'No' END as Living,
            CASE WHEN p.Bookmark = 1 THEN 'Yes' ELSE 'No' END as Bookmarked
        FROM PersonTable p
        JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
        WHERE p.PersonID = ?
    """, (person_id,))

    row = cursor.fetchone()
    if not row:
        print(f"\nPerson with RIN {person_id} not found.")
        return

    given, surname, sex, birth, death, living, bookmarked = row
    print(f"\nName: {given} {surname}")
    print(f"Sex: {sex}")
    print(f"Birth Year: {birth if birth else 'Unknown'}")
    print(f"Death Year: {death if death else 'Unknown'}")
    print(f"Living: {living}")
    print(f"Bookmarked: {bookmarked}")

    # Parents
    print("\n--- Parents ---")
    cursor.execute("""
        SELECT
            f.FatherID,
            (SELECT n.Given || ' ' || n.Surname FROM NameTable n
             WHERE n.OwnerID = f.FatherID AND n.IsPrimary = 1) as Father,
            f.MotherID,
            (SELECT n.Given || ' ' || n.Surname FROM NameTable n
             WHERE n.OwnerID = f.MotherID AND n.IsPrimary = 1) as Mother
        FROM ChildTable c
        JOIN FamilyTable f ON c.FamilyID = f.FamilyID
        WHERE c.ChildID = ?
    """, (person_id,))

    parents = cursor.fetchone()
    if parents:
        print(f"Father: {parents[1]} (RIN {parents[0]})")
        print(f"Mother: {parents[3]} (RIN {parents[2]})")
    else:
        print("No parents recorded")

    # Events
    print("\n--- Events ---")
    cursor.execute("""
        SELECT
            ft.Name as EventType,
            SUBSTR(e.Date, 4, 4) as Year,
            pl.Name as Place
        FROM EventTable e
        JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
        LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
        WHERE e.OwnerID = ? AND e.OwnerType = 0
        ORDER BY e.SortDate
    """, (person_id,))

    events = cursor.fetchall()
    if events:
        headers = ["Event", "Year", "Place"]
        print_table(headers, events)
    else:
        print("No events recorded")

    # Census count
    cursor.execute("""
        SELECT COUNT(*)
        FROM EventTable e
        WHERE e.OwnerID = ? AND e.OwnerType = 0 AND e.EventType = 18
    """, (person_id,))
    owned_census = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM WitnessTable w
        JOIN EventTable e ON e.EventID = w.EventID
        WHERE w.PersonID = ? AND e.EventType = 18
    """, (person_id,))
    witnessed_census = cursor.fetchone()[0]

    print(f"\nCensus records: {owned_census + witnessed_census} "
          f"({owned_census} owned, {witnessed_census} witnessed)")


def interactive_menu(cursor):
    """Display interactive menu."""
    while True:
        print("\n" + "=" * 80)
        print(" RootsMagic Database Inspector")
        print("=" * 80)
        print("\n1. Database Overview")
        print("2. Top Surnames")
        print("3. Event Type Distribution")
        print("4. Source Template Usage")
        print("5. Top Places")
        print("6. Search Person by Surname")
        print("7. Show Person Details (by RIN)")
        print("0. Exit")

        choice = input("\nEnter choice: ").strip()

        if choice == "0":
            break
        elif choice == "1":
            show_database_info(cursor)
        elif choice == "2":
            show_surname_distribution(cursor)
        elif choice == "3":
            show_event_type_distribution(cursor)
        elif choice == "4":
            show_source_templates(cursor)
        elif choice == "5":
            show_place_hierarchy(cursor)
        elif choice == "6":
            surname = input("Enter surname pattern: ").strip()
            if surname:
                search_person(cursor, surname)
        elif choice == "7":
            rin = input("Enter RIN (PersonID): ").strip()
            if rin.isdigit():
                show_person_details(cursor, int(rin))
            else:
                print("Invalid RIN. Please enter a number.")
        else:
            print("Invalid choice. Please try again.")

        input("\nPress Enter to continue...")


def main():
    """Main entry point."""
    # Get database path
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = "data/Iiams.rmtree"

    db_path = Path(db_path)
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        print("\nUsage:")
        print(f"  {sys.argv[0]} [database_path]")
        sys.exit(1)

    print(f"Opening database: {db_path}")

    try:
        # Connect to database
        conn = connect_rmtree(db_path)
        cursor = conn.cursor()

        # Run interactive menu
        interactive_menu(cursor)

        # Close connection
        conn.close()
        print("\nGoodbye!")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
