"""
Census Transcription Batch Processing Service.

Orchestrates batch extraction of census data from FamilySearch into census.db.
Uses the CensusTranscriptionRepository for state persistence and the
FamilySearchCensusExtractor for actual data extraction.

Key features:
- Primary extraction method: Family member ARKs from person page table
- Secondary extraction method: SLS API for complete page coverage
- Duplicate prevention via processed_census_images tracking
- Edge detection for page boundary warnings
- Checkpoint/resume support for crash recovery
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from rmcitecraft.config.settings import Config
from rmcitecraft.database.census_transcription_repository import (
    CensusTranscriptionRepository,
    TranscriptionItem,
)
from rmcitecraft.database.connection import connect_rmtree
from rmcitecraft.services.census_edge_detection import detect_edge_conditions
from rmcitecraft.services.census_rmtree_matcher import create_matcher
from rmcitecraft.services.familysearch_census_extractor import (
    FamilySearchCensusExtractor,
)


@dataclass
class BatchResult:
    """Result of batch processing."""

    total_items: int = 0
    completed: int = 0
    errors: int = 0
    skipped: int = 0
    edge_warnings: int = 0
    error_messages: list[str] | None = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_items == 0:
            return 0.0
        return (self.completed / self.total_items) * 100


@dataclass
class QueueItem:
    """Item in the transcription queue (before session creation)."""

    rmtree_citation_id: int  # Actually source_id when using source-based queue
    rmtree_person_id: int | None
    person_name: str
    census_year: int
    state: str
    county: str
    familysearch_ark: str
    image_ark: str | None = None  # Populated if we can determine it
    already_processed: bool = False
    surname: str = ""  # For sorting


@dataclass
class QueueStats:
    """Statistics about the transcription queue."""

    total_sources: int = 0
    already_processed: int = 0
    remaining: int = 0


class CensusTranscriptionBatchService:
    """Orchestrates census transcription batch processing."""

    def __init__(
        self,
        extractor: FamilySearchCensusExtractor | None = None,
        state_repo: CensusTranscriptionRepository | None = None,
        settings: Config | None = None,
    ):
        """Initialize batch service.

        Args:
            extractor: FamilySearch census extractor (created if not provided)
            state_repo: State persistence repository (created if not provided)
            settings: Application settings (loaded if not provided)
        """
        self.settings = settings or Config()
        self.state_repo = state_repo or CensusTranscriptionRepository()
        self._extractor = extractor
        self._matcher = None

    @property
    def extractor(self) -> FamilySearchCensusExtractor:
        """Get or create extractor."""
        if self._extractor is None:
            self._extractor = FamilySearchCensusExtractor()
        return self._extractor

    @property
    def matcher(self):
        """Get or create RootsMagic matcher."""
        if self._matcher is None:
            self._matcher = create_matcher()
        return self._matcher

    async def build_transcription_queue(
        self,
        census_year: int | None = None,
        state_filter: str | None = None,
        sort_by: str = "location",  # "location" or "name"
    ) -> tuple[list[QueueItem], QueueStats]:
        """
        Build queue of sources to transcribe.

        Queries from SourceTable (not Citations) to avoid duplicates.
        Each Source with a FamilySearch ARK represents one census page to process.

        Args:
            census_year: Filter to specific census year (1790-1950)
            state_filter: Filter to specific state abbreviation
            sort_by: Sort order - "location" (State, County) or "name" (Surname)

        Returns:
            Tuple of (queue items, statistics)
        """
        logger.info(
            f"Building transcription queue (year={census_year}, state={state_filter})"
        )

        queue: list[QueueItem] = []
        stats = QueueStats()

        try:
            conn = connect_rmtree(
                self.settings.rm_database_path,
                self.settings.sqlite_icu_extension,
            )
            cursor = conn.cursor()

            # Build query with year filter in SQL for efficiency
            # Source name format: "Fed Census: 1950, Arizona, Pima [citing ...]"
            year_clause = ""
            if census_year:
                year_clause = f"AND s.Name LIKE 'Fed Census: {census_year},%'"

            # Query 1: Get all matching sources (fast)
            source_query = f"""
                SELECT s.SourceID, s.Name, s.Fields
                FROM SourceTable s
                WHERE s.TemplateID = 0
                  AND s.Name LIKE 'Fed Census:%'
                  {year_clause}
            """
            cursor.execute(source_query)
            source_rows = cursor.fetchall()

            logger.debug(f"Found {len(source_rows)} census sources in RootsMagic")

            # Query 2: Get person names and RINs for all sources in one query
            # Group by SourceID, take first match (the primary target person)
            person_query = """
                SELECT
                    c.SourceID,
                    TRIM(COALESCE(n.Given, '') || ' ' || COALESCE(n.Surname, '')) as person_name,
                    n.Surname,
                    n.OwnerID as person_id
                FROM CitationTable c
                JOIN CitationLinkTable cl ON c.CitationID = cl.CitationID
                JOIN EventTable e ON cl.OwnerID = e.EventID AND cl.OwnerType = 2
                JOIN NameTable n ON e.OwnerID = n.OwnerID AND n.IsPrimary = 1
                GROUP BY c.SourceID
            """
            cursor.execute(person_query)
            person_rows = cursor.fetchall()
            conn.close()

            # Build lookup dict for person names and RINs
            # Key: SourceID, Value: (person_name, surname, person_id/RIN)
            person_lookup: dict[int, tuple[str, str, int | None]] = {}
            for prow in person_rows:
                person_lookup[prow[0]] = (prow[1] or "", prow[2] or "", prow[3])

            # Combine into rows format
            rows = []
            for srow in source_rows:
                source_id = srow[0]
                pname, surname, person_id = person_lookup.get(source_id, ("", "", None))
                rows.append((source_id, srow[1], srow[2], pname, surname, person_id))

            # Pre-load all processed ARKs from census.db into a set for O(1) lookup
            from rmcitecraft.database.census_extraction_db import get_census_repository
            census_repo = get_census_repository()

            processed_arks: set[str] = set()
            with census_repo._connect() as census_conn:
                ark_rows = census_conn.execute(
                    "SELECT familysearch_ark FROM census_person WHERE familysearch_ark IS NOT NULL"
                ).fetchall()
                for ark_row in ark_rows:
                    processed_arks.add(ark_row[0])

            logger.debug(f"Loaded {len(processed_arks)} processed ARKs")

            # Process rows - now just string parsing, no additional queries
            for row in rows:
                source_id = row[0]
                source_name = row[1] or ""
                source_fields = row[2]
                person_name = row[3] or source_name
                surname = row[4] or ""
                person_id = row[5]  # RIN from RootsMagic (primary target)

                # Extract year, state, county from source name
                name_match = re.match(
                    r"Fed Census:\s*(\d{4}),\s*([^,]+),\s*([^\s\[]+)",
                    source_name,
                    re.IGNORECASE,
                )
                if not name_match:
                    continue

                year = int(name_match.group(1))
                state = name_match.group(2).strip()
                county = name_match.group(3).strip()

                # Apply state filter if provided
                if state_filter and state.upper() != state_filter.upper():
                    continue

                # Extract ARK from Fields blob (simple string search, no XML parsing)
                if not source_fields:
                    continue

                fields_str = (
                    source_fields.decode("utf-8")
                    if isinstance(source_fields, bytes)
                    else source_fields
                )

                ark_match = re.search(
                    r"familysearch\.org/ark:/61903/(1:1:[A-Z0-9-]+)", fields_str
                )
                if not ark_match:
                    continue

                fs_ark = ark_match.group(1)
                full_ark = f"https://www.familysearch.org/ark:/61903/{fs_ark}"

                # Count for stats
                stats.total_sources += 1

                # Check if already processed - O(1) set lookup
                if full_ark in processed_arks:
                    stats.already_processed += 1
                    continue

                queue.append(
                    QueueItem(
                        rmtree_citation_id=source_id,
                        rmtree_person_id=person_id,  # RIN from RootsMagic for primary target
                        person_name=person_name,
                        census_year=year,
                        state=state,
                        county=county,
                        familysearch_ark=fs_ark,
                        already_processed=False,
                        surname=surname,
                    )
                )

            # Calculate remaining
            stats.remaining = stats.total_sources - stats.already_processed

            # Sort the queue
            if sort_by == "name":
                queue.sort(key=lambda x: (x.surname.lower(), x.person_name.lower()))
            else:  # location
                queue.sort(key=lambda x: (x.state.lower(), x.county.lower(), x.surname.lower()))

        except Exception as e:
            logger.error(f"Error building transcription queue: {e}")
            raise

        logger.info(
            f"Built queue: {len(queue)} unprocessed, "
            f"{stats.already_processed} already processed, "
            f"{stats.total_sources} total for year filter"
        )
        return queue, stats

    def create_session_from_queue(
        self,
        queue: list[QueueItem],
        census_year: int | None = None,
        state_filter: str | None = None,
    ) -> str:
        """
        Create a transcription session from a queue.

        Args:
            queue: List of QueueItem objects
            census_year: Census year filter used to build queue
            state_filter: State filter used to build queue

        Returns:
            Session ID
        """
        # Generate session ID
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        year_str = f"_{census_year}" if census_year else ""
        session_id = f"transcription{year_str}_{timestamp}"

        # Create session
        self.state_repo.create_session(
            session_id=session_id,
            total_items=len(queue),
            census_year=census_year,
            state_filter=state_filter,
        )

        # Create items in bulk
        items = [
            {
                "session_id": session_id,
                "rmtree_citation_id": q.rmtree_citation_id,
                "rmtree_person_id": q.rmtree_person_id,
                "person_name": q.person_name,
                "census_year": q.census_year,
                "state": q.state,
                "county": q.county,
                "familysearch_ark": q.familysearch_ark,
            }
            for q in queue
        ]
        self.state_repo.create_items_bulk(items)

        logger.info(f"Created session {session_id} with {len(queue)} items")
        return session_id

    async def process_batch(
        self,
        session_id: str,
        on_progress: Callable[[int, int, str], None] | None = None,
        on_edge_warning: Callable[[str, dict], None] | None = None,
        max_retries: int = 3,
    ) -> BatchResult:
        """
        Process all items in a session.

        Args:
            session_id: Session to process
            on_progress: Callback(completed, total, current_name) for progress updates
            on_edge_warning: Callback(message, item_data) for edge warnings
            max_retries: Maximum retry attempts for failed items

        Returns:
            BatchResult with processing statistics
        """
        result = BatchResult()
        result.error_messages = []

        # Start session
        self.state_repo.start_session(session_id)

        # Get pending items
        items = self.state_repo.get_pending_items(session_id)
        result.total_items = len(items)

        logger.info(f"Processing batch {session_id}: {len(items)} items")

        # Ensure extractor is connected
        await self.extractor.connect()

        try:
            for idx, item in enumerate(items):
                try:
                    # Report progress
                    if on_progress:
                        on_progress(idx, result.total_items, item.person_name)

                    # Process the item
                    item_result = await self._process_item(item)

                    if item_result.get("success"):
                        result.completed += 1

                        # Check for edge warnings
                        if item_result.get("edge_warning"):
                            result.edge_warnings += 1
                            if on_edge_warning:
                                on_edge_warning(
                                    item_result["edge_message"],
                                    {"item_id": item.item_id, "name": item.person_name},
                                )

                    elif item_result.get("skipped"):
                        result.skipped += 1
                    else:
                        result.errors += 1
                        if item_result.get("error"):
                            result.error_messages.append(
                                f"{item.person_name}: {item_result['error']}"
                            )

                    # Checkpoint
                    self.state_repo.create_checkpoint(
                        session_id,
                        item.item_id,
                        item.rmtree_citation_id,
                    )

                    # Update session counts
                    self.state_repo.update_session_counts(
                        session_id,
                        completed_count=result.completed,
                        error_count=result.errors,
                        skipped_count=result.skipped,
                        edge_warning_count=result.edge_warnings,
                    )

                except Exception as e:
                    logger.error(f"Error processing item {item.item_id}: {e}")
                    result.errors += 1
                    result.error_messages.append(f"{item.person_name}: {str(e)}")

                    self.state_repo.update_item_status(
                        item.item_id,
                        "error",
                        error_message=str(e),
                    )

        finally:
            # Complete session
            self.state_repo.complete_session(session_id)

        # Final progress report
        if on_progress:
            on_progress(result.total_items, result.total_items, "Complete")

        logger.info(
            f"Batch {session_id} complete: "
            f"{result.completed} completed, {result.errors} errors, "
            f"{result.skipped} skipped, {result.edge_warnings} edge warnings"
        )

        return result

    async def _process_item(self, item: TranscriptionItem) -> dict[str, Any]:
        """
        Process a single transcription item.

        1. Check if image already processed → skip with link to existing data
        2. Navigate to person ARK
        3. Extract family member ARKs from person page table (PRIMARY)
        4. Filter to RootsMagic persons using fuzzy name matching
        5. Extract data for matched persons
        6. Detect edge conditions and flag for review
        7. Mark image as processed

        Returns:
            Dict with keys: success, skipped, error, edge_warning, edge_message
        """
        result: dict[str, Any] = {
            "success": False,
            "skipped": False,
            "error": None,
            "edge_warning": False,
            "edge_message": "",
        }

        try:
            # Update status to extracting
            self.state_repo.update_item_status(item.item_id, "extracting")

            # Build full ARK URL
            ark_url = f"https://www.familysearch.org/ark:/61903/{item.familysearch_ark}"

            # Get RootsMagic persons for this source (for filtering extraction)
            # Note: rmtree_citation_id is actually a SourceID when using source-based queue
            rm_persons = []
            try:
                rm_persons, _, _ = self.matcher.get_rm_persons_for_source(
                    item.rmtree_citation_id  # This is a SourceID
                )
                logger.info(f"Found {len(rm_persons)} RM persons for source {item.rmtree_citation_id}")
            except Exception as e:
                logger.warning(f"Could not get RM persons for source {item.rmtree_citation_id}: {e}")

            # Extract census data
            extraction_result = await self.extractor.extract_from_ark(
                ark_url=ark_url,
                census_year=item.census_year,
                rmtree_citation_id=item.rmtree_citation_id,
                rmtree_person_id=item.rmtree_person_id,
                extract_household=True,
                rm_persons_filter=rm_persons if rm_persons else None,
            )

            if not extraction_result.success:
                result["error"] = extraction_result.error_message
                self.state_repo.update_item_status(
                    item.item_id,
                    "error",
                    error_message=extraction_result.error_message,
                )
                return result

            # Get extracted data for edge detection
            line_number = None
            relationship = None
            if extraction_result.extracted_data:
                line_str = extraction_result.extracted_data.get("line_number", "")
                if line_str and str(line_str).isdigit():
                    line_number = int(line_str)
                relationship = extraction_result.extracted_data.get(
                    "relationship_to_head_of_household", ""
                )

            # Detect edge conditions
            edge_result = detect_edge_conditions(
                line_number=line_number,
                census_year=item.census_year,
                relationship_to_head=relationship,
            )

            # Get image ARK from URL or extracted data
            image_ark = ""
            page = await self.extractor.automation.get_or_create_page()
            if page:
                url = page.url
                image_match = re.search(r"ark:/61903/(3:1:[A-Z0-9-]+)", url)
                if image_match:
                    image_ark = image_match.group(1)

            # Update item with extraction results
            self.state_repo.update_item_extraction(
                item_id=item.item_id,
                image_ark=image_ark,
                census_db_person_id=extraction_result.person_id or 0,
                census_db_page_id=extraction_result.page_id or 0,
                household_extracted_count=len(extraction_result.related_persons),
                extraction_method="table_arks",  # Primary method
                line_number=line_number,
                first_line_flag=edge_result.first_line_warning,
                last_line_flag=edge_result.last_line_warning,
                edge_warning_message=edge_result.warning_message,
            )

            # Mark image as processed (if we have the image ARK)
            if image_ark and extraction_result.page_id:
                # Get page info from census.db
                from rmcitecraft.database.census_extraction_db import get_census_repository
                census_repo = get_census_repository()

                try:
                    page_info = None
                    with census_repo._connect() as conn:
                        row = conn.execute(
                            "SELECT * FROM census_page WHERE page_id = ?",
                            (extraction_result.page_id,),
                        ).fetchone()
                        if row:
                            page_info = dict(row)

                    if page_info:
                        self.state_repo.mark_image_processed(
                            image_ark=image_ark,
                            census_year=item.census_year,
                            state=page_info.get("state", ""),
                            county=page_info.get("county", ""),
                            enumeration_district=page_info.get("enumeration_district", ""),
                            sheet_number=page_info.get("sheet_number", ""),
                            stamp_number=page_info.get("stamp_number", ""),
                            census_db_page_id=extraction_result.page_id,
                            person_count=1 + len(extraction_result.related_persons),
                            session_id=item.session_id,
                        )
                except Exception as e:
                    logger.debug(f"Could not mark image as processed: {e}")

            # Complete item
            self.state_repo.complete_item(item.item_id)

            result["success"] = True
            result["edge_warning"] = edge_result.first_line_warning or edge_result.last_line_warning
            result["edge_message"] = edge_result.warning_message

            logger.info(
                f"Extracted {item.person_name}: "
                f"person_id={extraction_result.person_id}, "
                f"household={len(extraction_result.related_persons)}"
            )

        except Exception as e:
            logger.error(f"Error processing item {item.item_id}: {e}")
            result["error"] = str(e)
            self.state_repo.update_item_status(
                item.item_id,
                "error",
                error_message=str(e),
            )

        return result

    async def resume_session(
        self,
        session_id: str,
        on_progress: Callable[[int, int, str], None] | None = None,
        on_edge_warning: Callable[[str, dict], None] | None = None,
    ) -> BatchResult:
        """Resume a paused or interrupted session."""
        session = self.state_repo.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        if session["status"] not in ("running", "paused", "queued"):
            raise ValueError(
                f"Cannot resume session with status: {session['status']}"
            )

        return await self.process_batch(
            session_id,
            on_progress=on_progress,
            on_edge_warning=on_edge_warning,
        )

    def get_edge_warnings(self, session_id: str) -> list[TranscriptionItem]:
        """Get all items with edge warnings from a session."""
        return self.state_repo.get_edge_warning_items(session_id)

    def get_session_summary(self, session_id: str) -> dict[str, Any]:
        """Get summary statistics for a session."""
        return self.state_repo.get_session_summary(session_id)


def get_batch_service() -> CensusTranscriptionBatchService:
    """Get singleton instance of batch service."""
    return CensusTranscriptionBatchService()
