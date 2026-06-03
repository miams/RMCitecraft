#!/usr/bin/env python3
"""
Consolidate 1860 slave schedule events with population schedule events.

This script moves slave schedule citations from separate Census events
to the same Census event that has the population schedule citation,
following the "Same Event, Multiple Sources" approach.

Safety features:
- Preview mode by default (no changes made)
- Requires --execute flag to make changes
- Creates backup of affected records before changes
- Detailed logging of all operations
"""

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rmcitecraft.database.connection import connect_rmtree


def get_consolidation_plan(cursor):
    """Find slave schedule citations that need to be moved to population events."""

    cursor.execute("""
    WITH slave_events AS (
        SELECT DISTINCT
            e.OwnerID as RIN,
            e.EventID as slave_event_id,
            cl.LinkID,
            c.CitationID,
            s.SourceID,
            s.Name as source_name
        FROM EventTable e
        JOIN CitationLinkTable cl ON e.EventID = cl.OwnerID AND cl.OwnerType = 2
        JOIN CitationTable c ON cl.CitationID = c.CitationID
        JOIN SourceTable s ON c.SourceID = s.SourceID
        WHERE e.EventType = 18
          AND s.Name LIKE 'Fed Census Slave Schedule: 1860%'
    ),
    pop_events AS (
        SELECT DISTINCT e.OwnerID as RIN, e.EventID as pop_event_id
        FROM EventTable e
        JOIN CitationLinkTable cl ON e.EventID = cl.OwnerID AND cl.OwnerType = 2
        JOIN CitationTable c ON cl.CitationID = c.CitationID
        JOIN SourceTable s ON c.SourceID = s.SourceID
        WHERE e.EventType = 18
          AND s.Name LIKE 'Fed Census: 1860%'
    )
    SELECT
        se.RIN,
        n.Given,
        n.Surname,
        pe.pop_event_id,
        se.slave_event_id,
        se.LinkID,
        se.CitationID,
        se.SourceID,
        se.source_name
    FROM slave_events se
    JOIN pop_events pe ON se.RIN = pe.RIN
    JOIN NameTable n ON se.RIN = n.OwnerID AND n.IsPrimary = 1
    WHERE se.slave_event_id != pe.pop_event_id
    ORDER BY n.Surname, n.Given
    """)

    return cursor.fetchall()


def get_orphan_event_details(cursor, event_ids):
    """Get details of events that will be deleted."""
    if not event_ids:
        return []

    placeholders = ','.join('?' * len(event_ids))
    cursor.execute(f"""
        SELECT e.EventID, e.OwnerID, n.Given, n.Surname, e.Date, e.Details
        FROM EventTable e
        JOIN NameTable n ON e.OwnerID = n.OwnerID AND n.IsPrimary = 1
        WHERE e.EventID IN ({placeholders})
    """, list(event_ids))

    return cursor.fetchall()


def backup_affected_records(cursor, changes, orphan_events):
    """Create a backup record of all data that will be modified."""
    backup = {
        'timestamp': datetime.now().isoformat(),
        'citation_links_to_update': [],
        'events_to_delete': []
    }

    # Backup citation links
    link_ids = [row[5] for row in changes]  # LinkID
    if link_ids:
        placeholders = ','.join('?' * len(link_ids))
        cursor.execute(f"SELECT * FROM CitationLinkTable WHERE LinkID IN ({placeholders})", link_ids)
        columns = [desc[0] for desc in cursor.description]
        for row in cursor.fetchall():
            backup['citation_links_to_update'].append(dict(zip(columns, row)))

    # Backup events
    if orphan_events:
        placeholders = ','.join('?' * len(orphan_events))
        cursor.execute(f"SELECT * FROM EventTable WHERE EventID IN ({placeholders})", list(orphan_events))
        columns = [desc[0] for desc in cursor.description]
        for row in cursor.fetchall():
            backup['events_to_delete'].append(dict(zip(columns, row)))

    return backup


def execute_consolidation(cursor, changes, orphan_events):
    """Execute the consolidation changes."""

    # Step 1: Update CitationLinkTable to point to population events
    for row in changes:
        rin, given, surname, pop_event_id, slave_event_id, link_id, cit_id, src_id, src_name = row
        cursor.execute(
            "UPDATE CitationLinkTable SET OwnerID = ? WHERE LinkID = ?",
            (pop_event_id, link_id)
        )
        print(f"  Updated LinkID {link_id}: EventID {slave_event_id} -> {pop_event_id}")

    # Step 2: Delete orphaned events
    for event_id in orphan_events:
        cursor.execute("DELETE FROM EventTable WHERE EventID = ?", (event_id,))
        print(f"  Deleted EventID {event_id}")


def main():
    parser = argparse.ArgumentParser(
        description='Consolidate 1860 slave schedule events with population schedule events.'
    )
    parser.add_argument(
        '--db',
        default='data/Iiams.rmtree',
        help='Path to RootsMagic database'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually execute changes (default is preview only)'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("  1860 SLAVE SCHEDULE CONSOLIDATION")
    print("  Same Event, Multiple Sources Approach")
    print("=" * 70)
    print()

    # Connect to database
    read_only = not args.execute
    conn = connect_rmtree(args.db, read_only=read_only)
    cursor = conn.cursor()

    # Get consolidation plan
    changes = get_consolidation_plan(cursor)

    if not changes:
        print("No changes needed - all 1860 records already use same event approach.")
        conn.close()
        return

    # Identify orphan events
    orphan_events = set(row[4] for row in changes)  # slave_event_ids

    # Display plan
    print(f"Found {len(changes)} citation link(s) to move:\n")
    print(f"{'Person':<30} {'RIN':<6} {'From Event':<12} {'To Event':<10} {'CitationID':<10}")
    print("-" * 78)

    for row in changes:
        rin, given, surname, pop_event, slave_event, link_id, cit_id, src_id, src_name = row
        name = f"{given} {surname}"[:30]
        print(f"{name:<30} {rin:<6} {slave_event:<12} {pop_event:<10} {cit_id:<10}")

    print()
    print(f"Events that will be deleted ({len(orphan_events)}):")
    orphan_details = get_orphan_event_details(cursor, orphan_events)
    for event_id, owner_id, given, surname, date, details in orphan_details:
        print(f"  EventID {event_id}: {given} {surname} (RIN {owner_id})")

    print()

    if not args.execute:
        print("=" * 70)
        print("  PREVIEW MODE - No changes made")
        print("  Run with --execute to apply changes")
        print("=" * 70)
        conn.close()
        return

    # Create backup
    print("Creating backup of affected records...")
    backup = backup_affected_records(cursor, changes, orphan_events)

    backup_file = Path(f"backup/1860_consolidation_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    backup_file.parent.mkdir(exist_ok=True)
    with open(backup_file, 'w') as f:
        import json
        json.dump(backup, f, indent=2, default=str)
    print(f"Backup saved to: {backup_file}")
    print()

    # Execute changes
    print("Executing changes...")
    execute_consolidation(cursor, changes, orphan_events)

    # Commit
    conn.commit()
    print()
    print("=" * 70)
    print("  CHANGES COMMITTED SUCCESSFULLY")
    print("=" * 70)

    conn.close()


if __name__ == '__main__':
    main()
