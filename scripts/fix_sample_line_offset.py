#!/usr/bin/env python3
"""
Fix sample line data offset in census.db.

FamilySearch indexes 1950 census sample line data (columns 21-33) with a +2 line offset.
Sample lines are 1, 6, 11, 16, 21, 26 but the data is stored at lines 3, 8, 13, 18, 23, 28.

This script moves the sample line fields from the offset lines to the correct sample line persons.
"""

import sqlite3
from pathlib import Path


# Sample line fields that need to be moved (columns 21-33 from 1950 census)
SAMPLE_LINE_FIELDS = {
    # Residence April 1, 1949 (cols 21-24)
    "residence_1949_same_house",
    "residence_1949_on_farm",
    "residence_1949_same_county",
    "residence_1949_different_location",
    # Education (cols 26-28)
    "highest_grade_attended",
    "completed_grade",
    "school_attendance",
    # Employment/income history (cols 29-33)
    "weeks_looking_for_work",
    "weeks_worked_1949",
    "income_wages_1949",
    "income_self_employment_1949",
    "income_other_1949",
    # Veteran status
    "veteran_status",
    "veteran_ww1",
    "veteran_ww2",
}

# Mapping: offset line -> correct sample line
OFFSET_TO_SAMPLE = {
    3: 1,
    8: 6,
    13: 11,
    18: 16,
    23: 21,
    28: 26,
}


def fix_sample_line_offset(db_path: Path, dry_run: bool = True) -> dict:
    """Fix sample line data offset for all pages in the database.

    Args:
        db_path: Path to census.db
        dry_run: If True, show changes without applying them

    Returns:
        Summary of changes made/to be made
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    summary = {
        "pages_processed": 0,
        "fields_moved": 0,
        "errors": [],
    }

    try:
        # Get all pages (for now, focus on 1950 census)
        cursor.execute("""
            SELECT page_id, state, county, enumeration_district, page_number
            FROM census_page
            WHERE census_year = 1950
        """)
        pages = cursor.fetchall()

        for page in pages:
            page_id = page["page_id"]
            page_info = f"{page['county']}, {page['state']} ED {page['enumeration_district']} p{page['page_number']}"

            print(f"\nProcessing page {page_id}: {page_info}")
            summary["pages_processed"] += 1

            # For each offset line, find the person and their sample line fields
            for offset_line, sample_line in OFFSET_TO_SAMPLE.items():
                # Find person at offset line
                cursor.execute("""
                    SELECT person_id, full_name, line_number
                    FROM census_person
                    WHERE page_id = ? AND line_number = ?
                """, (page_id, offset_line))
                offset_person = cursor.fetchone()

                if not offset_person:
                    continue

                # Find person at correct sample line
                cursor.execute("""
                    SELECT person_id, full_name, line_number
                    FROM census_person
                    WHERE page_id = ? AND line_number = ?
                """, (page_id, sample_line))
                sample_person = cursor.fetchone()

                if not sample_person:
                    print(f"  WARNING: No person found at sample line {sample_line}")
                    continue

                # Find sample line fields on the offset person
                cursor.execute("""
                    SELECT field_id, field_name, field_value, familysearch_label
                    FROM census_person_field
                    WHERE person_id = ? AND field_name IN ({})
                """.format(",".join("?" * len(SAMPLE_LINE_FIELDS))),
                    (offset_person["person_id"], *SAMPLE_LINE_FIELDS))
                fields_to_move = cursor.fetchall()

                if not fields_to_move:
                    continue

                print(f"  Line {offset_line} ({offset_person['full_name']}) -> Line {sample_line} ({sample_person['full_name']})")

                for field in fields_to_move:
                    print(f"    Moving {field['field_name']}: {field['field_value']}")
                    summary["fields_moved"] += 1

                    if not dry_run:
                        # Check if field already exists on sample person
                        cursor.execute("""
                            SELECT field_id FROM census_person_field
                            WHERE person_id = ? AND field_name = ?
                        """, (sample_person["person_id"], field["field_name"]))
                        existing = cursor.fetchone()

                        if existing:
                            # Update existing field
                            cursor.execute("""
                                UPDATE census_person_field
                                SET field_value = ?, familysearch_label = ?
                                WHERE field_id = ?
                            """, (field["field_value"], field["familysearch_label"], existing["field_id"]))
                            # Delete the old field
                            cursor.execute("DELETE FROM census_person_field WHERE field_id = ?",
                                         (field["field_id"],))
                        else:
                            # Move field to correct person
                            cursor.execute("""
                                UPDATE census_person_field
                                SET person_id = ?
                                WHERE field_id = ?
                            """, (sample_person["person_id"], field["field_id"]))

        if not dry_run:
            conn.commit()
            print(f"\nCommitted changes to database")
        else:
            print(f"\nDRY RUN - No changes made. Run with --apply to apply changes.")

    except Exception as e:
        summary["errors"].append(str(e))
        print(f"ERROR: {e}")
        conn.rollback()

    finally:
        conn.close()

    return summary


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fix sample line data offset in census.db")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry run)")
    parser.add_argument("--db", type=Path, default=Path.home() / ".rmcitecraft" / "census.db",
                       help="Path to census.db")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"Database not found: {args.db}")
        return 1

    print(f"Database: {args.db}")
    print(f"Mode: {'APPLY CHANGES' if args.apply else 'DRY RUN'}")
    print("=" * 60)

    summary = fix_sample_line_offset(args.db, dry_run=not args.apply)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Pages processed: {summary['pages_processed']}")
    print(f"Fields moved: {summary['fields_moved']}")
    if summary["errors"]:
        print(f"Errors: {len(summary['errors'])}")
        for err in summary["errors"]:
            print(f"  - {err}")

    return 0


if __name__ == "__main__":
    exit(main())
