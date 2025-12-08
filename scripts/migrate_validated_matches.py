#!/usr/bin/env python3
"""
Migration script for validated match_attempt records.

This script processes validated match_attempts that were created before the
extraction workflow was updated to create census_person records for all
household members.

For each validated match_attempt without a census_person:
1. Creates a census_person record from the match_attempt data
2. Updates match_attempt.matched_census_person_id
3. Creates rmtree_link to connect to RootsMagic

Run with: uv run python scripts/migrate_validated_matches.py
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from loguru import logger


def get_census_db_path() -> Path:
    """Get the census.db path."""
    return Path.home() / ".rmcitecraft" / "census.db"


def migrate_validated_matches(dry_run: bool = False) -> dict:
    """Migrate validated match_attempts to create census_person and rmtree_link records.

    Args:
        dry_run: If True, don't make any changes, just report what would be done

    Returns:
        Dict with migration statistics
    """
    db_path = get_census_db_path()
    if not db_path.exists():
        logger.error(f"Census database not found: {db_path}")
        return {"error": "Database not found"}

    stats = {
        "total_validated": 0,
        "needs_migration": 0,
        "census_person_created": 0,
        "rmtree_link_created": 0,
        "skipped_no_page": 0,
        "skipped_no_citation": 0,
        "errors": [],
    }

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        # Get all validated match_attempts without census_person
        cursor = conn.execute("""
            SELECT * FROM match_attempt
            WHERE match_status = 'validated'
            ORDER BY attempt_id
        """)
        all_validated = cursor.fetchall()
        stats["total_validated"] = len(all_validated)

        # Filter to those needing migration
        needs_migration = [
            row for row in all_validated
            if row["matched_census_person_id"] is None
        ]
        stats["needs_migration"] = len(needs_migration)

        logger.info(f"Found {stats['total_validated']} validated records, "
                    f"{stats['needs_migration']} need migration")

        if dry_run:
            logger.info("DRY RUN - No changes will be made")
            for row in needs_migration:
                logger.info(f"  Would migrate: {row['fs_full_name']} "
                           f"(attempt_id={row['attempt_id']}, page_id={row['page_id']}, "
                           f"rm_person_id={row['matched_rm_person_id']})")
            return stats

        # Process each record needing migration
        for row in needs_migration:
            attempt_id = row["attempt_id"]
            page_id = row["page_id"]
            rm_person_id = row["matched_rm_person_id"]
            fs_full_name = row["fs_full_name"]
            fs_ark = row["fs_ark"]

            logger.info(f"Migrating: {fs_full_name} (attempt_id={attempt_id})")

            if not page_id:
                logger.warning(f"  Skipping - no page_id for attempt {attempt_id}")
                stats["skipped_no_page"] += 1
                continue

            # Get citation_id from existing links on same page
            citation_row = conn.execute("""
                SELECT DISTINCT rl.rmtree_citation_id
                FROM rmtree_link rl
                JOIN census_person cp ON rl.census_person_id = cp.person_id
                WHERE cp.page_id = ?
                AND rl.rmtree_citation_id IS NOT NULL
                LIMIT 1
            """, (page_id,)).fetchone()

            if not citation_row:
                logger.warning(f"  Skipping - no citation_id found for page {page_id}")
                stats["skipped_no_citation"] += 1
                continue

            rmtree_citation_id = citation_row["rmtree_citation_id"]

            try:
                # Parse name
                name_parts = fs_full_name.split() if fs_full_name else []
                surname = name_parts[-1] if name_parts else ""
                given_name = " ".join(name_parts[:-1]) if len(name_parts) > 1 else ""

                # Create census_person
                cursor = conn.execute("""
                    INSERT INTO census_person (
                        page_id, full_name, given_name, surname,
                        line_number, relationship_to_head, sex, age, birthplace,
                        familysearch_ark, is_target_person, extracted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    page_id,
                    fs_full_name,
                    given_name,
                    surname,
                    row["fs_line_number"],
                    row["fs_relationship"],
                    "",  # sex - not in match_attempt
                    int(row["fs_age"]) if row["fs_age"] and row["fs_age"].isdigit() else None,
                    row["fs_birthplace"],
                    fs_ark,
                    1,  # is_target_person
                    datetime.now().isoformat(),
                ))
                census_person_id = cursor.lastrowid
                stats["census_person_created"] += 1
                logger.info(f"  Created census_person {census_person_id}")

                # Update match_attempt with census_person_id
                conn.execute("""
                    UPDATE match_attempt
                    SET matched_census_person_id = ?
                    WHERE attempt_id = ?
                """, (census_person_id, attempt_id))

                # Create rmtree_link if we have rm_person_id
                if rm_person_id:
                    conn.execute("""
                        INSERT INTO rmtree_link (
                            census_person_id, rmtree_person_id, rmtree_citation_id,
                            match_confidence, match_method, linked_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        census_person_id,
                        rm_person_id,
                        rmtree_citation_id,
                        1.0,  # Manual validation = high confidence
                        "migration_from_validation",
                        datetime.now().isoformat(),
                    ))
                    stats["rmtree_link_created"] += 1
                    logger.info(f"  Created rmtree_link to RIN {rm_person_id}")

                conn.commit()

            except Exception as e:
                logger.error(f"  Error migrating attempt {attempt_id}: {e}")
                stats["errors"].append(f"{fs_full_name}: {e}")
                conn.rollback()

    finally:
        conn.close()

    logger.info(f"Migration complete: {stats}")
    return stats


def main():
    """Run the migration."""
    import argparse

    parser = argparse.ArgumentParser(description="Migrate validated match_attempts")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without making changes")
    args = parser.parse_args()

    logger.info("Starting validated match migration...")
    stats = migrate_validated_matches(dry_run=args.dry_run)

    print("\n=== Migration Summary ===")
    print(f"Total validated records: {stats.get('total_validated', 0)}")
    print(f"Needed migration: {stats.get('needs_migration', 0)}")
    print(f"Census persons created: {stats.get('census_person_created', 0)}")
    print(f"RMTree links created: {stats.get('rmtree_link_created', 0)}")
    print(f"Skipped (no page): {stats.get('skipped_no_page', 0)}")
    print(f"Skipped (no citation): {stats.get('skipped_no_citation', 0)}")
    if stats.get("errors"):
        print(f"Errors: {len(stats['errors'])}")
        for err in stats["errors"]:
            print(f"  - {err}")


if __name__ == "__main__":
    main()
