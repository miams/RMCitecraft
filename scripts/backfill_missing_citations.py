"""
Backfill citations for the 32 collection 1002 records whose source citation
page returned an abbreviated text (no series title), leaving citations empty.

Uses residence state as the state fallback — for WW2 draft registrations,
men registered at their local draft board in their state of residence.

Safe to re-run: only processes records where all three citation fields are empty.
"""

import asyncio
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from rmcitecraft.services.draft_citation_builder import DraftCitationBuilder
from rmcitecraft.database.draft_registration_db import DraftRegistrationRepository

DB_PATH = Path("/Users/miams/.rmcitecraft/ww2-draft.db")


def extract_state_from_city(city: str | None) -> str | None:
    """Extract state name from a residence_city string like 'Lima, Allen, Ohio' or 'Lima, Ohio, USA'."""
    if not city:
        return None
    parts = [p.strip() for p in city.split(",")]
    for part in reversed(parts):
        part = part.strip()
        if part in ("USA", ""):
            continue
        return part
    return None


def load_missing_citation_records(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT registration_id, rin, given_name, surname, full_name,
               ancestry_url, residence_city, extracted_at
        FROM draft_registration
        WHERE (rm_source_footnote IS NULL OR rm_source_footnote = '')
          AND ancestry_url LIKE '%/collections/1002/%'
        ORDER BY rin
    """)
    return [dict(r) for r in cur.fetchall()]


async def backfill():
    repo = DraftRegistrationRepository(DB_PATH)
    builder = DraftCitationBuilder()

    conn = sqlite3.connect(DB_PATH)
    records = load_missing_citation_records(conn)
    conn.close()

    logger.info(f"Found {len(records)} records needing citation backfill")

    success = 0
    failed = []

    for rec in records:
        reg_id = rec["registration_id"]
        rin = rec["rin"]
        name = rec["full_name"] or f"{rec['given_name']} {rec['surname']}".strip()
        url = rec["ancestry_url"]
        residence = rec["residence_city"]

        state = extract_state_from_city(residence)
        if not state:
            logger.warning(f"RIN {rin} ({name}): no state found in residence '{residence}'")
            failed.append((rin, name, "no state in residence"))
            continue

        # Use scrape timestamp if stored, otherwise today
        extracted_at = rec.get("extracted_at") or datetime.now(timezone.utc).isoformat()

        footnote, short_footnote, bibliography, warnings = await builder.build_ancestry_citations(
            page=None,
            url=url,
            person_name=name,
            extracted_at=extracted_at,
            state_fallback=state,
        )

        if footnote and short_footnote and bibliography:
            repo.update_citations(reg_id, footnote, short_footnote, bibliography)
            logger.info(f"  ✅ RIN {rin}: {name} ({state})")
            success += 1
        else:
            logger.warning(f"  ❌ RIN {rin}: {name} — {warnings}")
            failed.append((rin, name, "; ".join(warnings)))

    print(f"\n{'='*60}")
    print(f"Backfill complete: {success}/{len(records)} citations built")
    if failed:
        print(f"\nFailed ({len(failed)}):")
        for rin, name, reason in failed:
            print(f"  RIN {rin}: {name} — {reason}")


if __name__ == "__main__":
    asyncio.run(backfill())
