#!/usr/bin/env python3
"""Verify MediaLinkTable / CitationLinkTable OwnerType mapping against a live DB.

Run this BEFORE writing any new MediaLink / CitationLink rows to confirm the
integer mapping hasn't changed (or to detect that you guessed wrong).

Usage:
    uv run python3 verify_owner_types.py <path-to-rmtree>

The test is: for each OwnerType present in a link table, does the EXPECTED
target table contain every OwnerID? Coincidental matches against other tables
are tolerated as long as the expected one is 100%.

Exit codes:
    0 = OK (all OwnerTypes in the standard set 0/1/2/3/4/5 validate against
        their expected target table; unexpected OwnerTypes — rare edge cases —
        are flagged as INFO but don't fail the run)
    1 = MISMATCH on a standard OwnerType (DO NOT proceed with writes)
"""
import sys
from rmcitecraft.database.connection import connect_rmtree

EXPECTED = {
    0: ('PersonTable', 'PersonID'),
    1: ('FamilyTable', 'FamilyID'),
    2: ('EventTable', 'EventID'),
    3: ('SourceTable', 'SourceID'),
    4: ('CitationTable', 'CitationID'),
    5: ('PlaceTable', 'PlaceID'),
}

ALL_TABLES = [
    ('PersonTable',   'PersonID'),
    ('FamilyTable',   'FamilyID'),
    ('EventTable',    'EventID'),
    ('SourceTable',   'SourceID'),
    ('CitationTable', 'CitationID'),
    ('PlaceTable',    'PlaceID'),
]


def analyze(cur, link_table: str) -> list[dict]:
    cur.execute(f"SELECT DISTINCT OwnerType FROM {link_table} ORDER BY OwnerType")
    types = [r[0] for r in cur.fetchall()]
    rows = []
    for ot in types:
        cur.execute(f"SELECT COUNT(*) FROM {link_table} WHERE OwnerType = ?", (ot,))
        total = cur.fetchone()[0]
        matches = {}
        for tbl, col in ALL_TABLES:
            cur.execute(
                f"SELECT COUNT(*) FROM {link_table} l "
                f"WHERE l.OwnerType = ? AND EXISTS (SELECT 1 FROM {tbl} t WHERE t.{col} = l.OwnerID)",
                (ot,)
            )
            matches[tbl] = cur.fetchone()[0]
        rows.append({'owner_type': ot, 'total': total, 'matches': matches})
    return rows


def evaluate(rows: list[dict]) -> tuple[bool, list[str]]:
    notes = []
    mismatches = 0
    for row in rows:
        ot = row['owner_type']
        total = row['total']
        matches = row['matches']
        expected = EXPECTED.get(ot)
        # Tables that match ALL rows
        full_matches = [tbl for tbl, n in matches.items() if n == total]
        if expected is None:
            full_str = ','.join(full_matches) if full_matches else 'no table fully matches'
            notes.append(f"OwnerType {ot} (total={total}): UNEXPECTED — full matches: {full_str}")
        else:
            expected_table = expected[0]
            if matches.get(expected_table, 0) == total:
                # Expected table contains every OwnerID — pass even if other tables also coincidentally match
                others = [t for t in full_matches if t != expected_table]
                extra = f" (also matched coincidentally: {','.join(others)})" if others else ""
                notes.append(f"OwnerType {ot} (total={total}): OK -> {expected_table}{extra}")
            else:
                hit = matches.get(expected_table, 0)
                full_str = ','.join(full_matches) if full_matches else 'NONE'
                notes.append(
                    f"OwnerType {ot} (total={total}): MISMATCH — expected {expected_table} "
                    f"({hit}/{total} match); full matches: {full_str}"
                )
                mismatches += 1
    return mismatches == 0, notes


def main(db_path: str) -> int:
    conn = connect_rmtree(db_path, read_only=True)
    cur = conn.cursor()
    try:
        overall_ok = True
        for link_table in ('MediaLinkTable', 'CitationLinkTable'):
            rows = analyze(cur, link_table)
            ok, notes = evaluate(rows)
            print(f"\n=== {link_table} ===")
            for n in notes:
                print(f"  {n}")
            overall_ok = overall_ok and ok

        print("\n" + "=" * 70)
        if overall_ok:
            print("PASS — standard OwnerType mapping (0=Person, 1=Family, 2=Event, "
                  "3=Source, 4=Citation, 5=Place) is valid in this database.")
            print("Safe to use these constants when inserting new link rows.")
            return 0
        else:
            print("FAIL — a standard OwnerType doesn't validate against its expected table.")
            print("DO NOT proceed with writes until you understand why.")
            return 1
    finally:
        conn.close()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
