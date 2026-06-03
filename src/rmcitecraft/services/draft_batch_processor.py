"""Service for batch processing draft registration records.

Orchestrates the complete workflow:
1. Read records from file (via DraftFileReader)
2. Build citations (via DraftCitationBuilder)
3. Write to database (via DraftDatabaseWriter)
4. Track progress and handle errors
"""

from pathlib import Path
from typing import List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import time
from loguru import logger

from rmcitecraft.models.draft_record import (
    DraftRecord,
    RecordResult,
    BatchResult,
    ValidationResult,
)
from rmcitecraft.services.draft_file_reader import DraftFileReader
from rmcitecraft.services.draft_citation_builder import DraftCitationBuilder
from rmcitecraft.services.draft_database_writer import DraftDatabaseWriter


@dataclass
class ProcessingConfig:
    """Configuration for batch processing."""

    db_path: Path
    """Path to RootsMagic database."""

    skip_duplicates: bool = True
    """Skip records that already have citations (default: True)."""

    validate_persons: bool = True
    """Verify persons exist in database before processing (default: True)."""

    stop_on_error: bool = False
    """Stop processing on first error (default: False - continue with remaining records)."""

    dry_run: bool = False
    """Preview processing without writing to database (default: False)."""


class DraftBatchProcessor:
    """Batch process draft registration records with progress tracking and error handling.

    Orchestrates the complete workflow:
    - File reading and validation
    - Citation building with Evidence Explained formatting
    - Database writes with duplicate detection
    - Progress tracking with callbacks
    - Comprehensive error handling and logging
    """

    def __init__(
        self,
        config: ProcessingConfig,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ):
        """Initialize the batch processor.

        Args:
            config: Processing configuration
            progress_callback: Optional callback for progress updates.
                Called with (current_record, total_records, status_message)
        """
        self.config = config
        self.progress_callback = progress_callback

        # Initialize services
        self.file_reader = DraftFileReader()
        self.citation_builder = DraftCitationBuilder()

    def process_file(self, file_path: Path) -> BatchResult:
        """Process a complete file of draft registration records.

        Args:
            file_path: Path to CSV or XLSX file

        Returns:
            BatchResult with processing summary and detailed results
        """
        logger.info(f"Starting batch processing of {file_path}")

        # Read and validate file
        try:
            records = self.file_reader.read_file(file_path)
        except Exception as e:
            logger.error(f"Failed to read file: {e}")
            # Create batch ID from timestamp
            batch_id = int(time.time())
            batch_result = BatchResult(
                batch_id=batch_id,
                total_records=0,
            )
            # Create a RecordResult with the error
            # (Note: no records, so just return empty result with error counter)
            batch_result.errors = 1
            return batch_result

        if not records:
            logger.warning("No records found in file")
            batch_id = int(time.time())
            return BatchResult(
                batch_id=batch_id,
                total_records=0,
            )

        logger.info(f"Read {len(records)} records from file")

        # Process batch
        return self.process_batch(records)

    def process_batch(self, records: List[DraftRecord]) -> BatchResult:
        """Process a batch of draft registration records.

        Args:
            records: List of DraftRecord objects to process

        Returns:
            BatchResult with processing summary and detailed results
        """
        # Create batch ID from timestamp
        batch_id = int(time.time())
        start_time = datetime.now()

        batch_result = BatchResult(
            batch_id=batch_id,
            total_records=len(records),
            start_time=start_time.isoformat(),
        )

        # Open database connection (read-only for dry run)
        read_only = self.config.dry_run
        with DraftDatabaseWriter(
            self.config.db_path, read_only=read_only
        ) as db_writer:

            for idx, record in enumerate(records, start=1):
                # Report progress
                if self.progress_callback:
                    self.progress_callback(
                        idx, len(records), f"Processing {record.full_name}"
                    )

                # Process record
                result = self._process_record(record, db_writer)

                # Use BatchResult.add_result() to update counters automatically
                batch_result.add_result(result)

                # Stop on error if configured
                if not result.success and not result.skipped and self.config.stop_on_error:
                    logger.error(f"Stopping batch processing due to error: {result.error_message}")
                    break

        # Calculate processing time
        end_time = datetime.now()
        batch_result.end_time = end_time.isoformat()
        batch_result.processing_time = (end_time - start_time).total_seconds()

        logger.info(
            f"Batch processing complete: {batch_result.successful} successful, "
            f"{batch_result.errors} errors, {batch_result.skipped} skipped"
        )

        return batch_result

    def _process_record(
        self, record: DraftRecord, db_writer: DraftDatabaseWriter
    ) -> RecordResult:
        """Process a single draft registration record.

        Args:
            record: Draft record to process
            db_writer: Database writer instance (already connected)

        Returns:
            RecordResult with processing outcome
        """
        result = RecordResult(
            record=record,
            success=False,
            skipped=False,
        )

        try:
            # Validate record
            validation = self.file_reader.validate_record(record)
            if not validation.is_valid:
                result.error_message = "; ".join(validation.errors)
                result.warning_messages = validation.warnings
                logger.warning(
                    f"Skipping invalid record at row {record.row_number}: {result.error_message}"
                )
                return result

            # Collect warnings
            result.warning_messages = validation.warnings.copy()

            # Check if citation can be processed
            if not record.familysearch_citation:
                result.skipped = True
                result.skip_reason = "No citation provided"
                result.add_warning("Skipping - no citation provided")
                return result

            citation_lower = record.familysearch_citation.lower()

            if 'not found' in citation_lower or 'no record' in citation_lower:
                result.skipped = True
                result.skip_reason = "Draft registration not found"
                result.add_warning("Skipping - draft registration marked as not found")
                return result

            # Must have FamilySearch or AncestryLibrary URL to process
            has_familysearch = 'familysearch.org' in citation_lower or 'ark:/' in citation_lower
            has_ancestry = 'ancestrylibrary.com' in citation_lower

            if not (has_familysearch or has_ancestry):
                result.skipped = True
                result.skip_reason = "No FamilySearch or AncestryLibrary URL"
                result.add_warning("Skipping - citation does not contain FamilySearch or AncestryLibrary URL")
                return result

            # Verify person exists (if configured)
            if self.config.validate_persons:
                if not record.is_valid_rin:
                    result.error_message = "Invalid or missing RIN"
                    return result

                if not db_writer.verify_person_exists(record.rin):
                    result.error_message = f"Person with RIN {record.rin} not found in database"
                    return result

            # Check for duplicate citation (if configured)
            if self.config.skip_duplicates and record.is_valid_rin:
                # Detect source type
                citation_lower = record.familysearch_citation.lower()
                is_ancestry = 'ancestrylibrary.com' in citation_lower

                if is_ancestry:
                    # For AncestryLibrary, do a simpler duplicate check by URL
                    # since we don't have full metadata yet
                    existing_source_id = db_writer.check_duplicate_source_by_url(
                        record.familysearch_citation
                    )
                else:
                    # Parse metadata to get state
                    metadata = self.citation_builder.parse_familysearch_url(
                        record.familysearch_citation, state_hint=record.state
                    )

                    # Build source to check for duplicate by name
                    source_data = self.citation_builder.build_source(metadata)
                    existing_source_id = db_writer.check_duplicate_source(source_data)

                if existing_source_id:
                    # Check if citation already exists for this person
                    existing_citation_id = db_writer.check_duplicate_citation(
                        record.rin, existing_source_id
                    )
                    if existing_citation_id:
                        result.skipped = True
                        result.skip_reason = "Citation already exists"
                        result.source_id = existing_source_id
                        result.citation_id = existing_citation_id
                        result.add_warning(
                            f"Citation already exists (Source: {existing_source_id}, "
                            f"Citation: {existing_citation_id})"
                        )
                        logger.info(
                            f"Skipping duplicate citation for {record.full_name} "
                            f"(row {record.row_number})"
                        )
                        return result

            # Dry run - stop here
            if self.config.dry_run:
                result.success = True
                result.add_warning("Dry run - no database changes made")
                return result

            # Detect source type and parse accordingly
            citation_lower = record.familysearch_citation.lower()
            is_ancestry = 'ancestrylibrary.com' in citation_lower

            if is_ancestry:
                # For AncestryLibrary, create a minimal source/citation with the URL
                # Image downloading will happen separately via AncestryLibraryAutomation service
                logger.info(f"Processing AncestryLibrary citation for {record.full_name}")

                # Create a simple source for AncestryLibrary draft registration
                from rmcitecraft.models.citation_data import SourceData, CitationData

                source_name = f"U.S., {record.state or 'Unknown State'} Draft Registration Cards"
                if hasattr(record, 'draft_year') and record.draft_year:
                    source_name = f"{record.draft_year} {source_name}"

                source_data = SourceData(
                    name=source_name,
                    ref_number="",
                    comments=f"Draft registration from {record.familysearch_citation}",
                    bibliography="",
                    footnote_template="",
                    short_footnote_template="",
                    fields_blob=None,
                    template_id=0,  # Free-form
                )

                citation_data = CitationData(
                    source_id=0,  # Will be set by create_citation_for_person
                    comments="",
                    ref_number=record.familysearch_citation,  # Store the URL
                    footnote="",
                    short_footnote="",
                    bibliography="",
                    fields_blob=None,
                    actual_text=record.familysearch_citation,
                    quality=0,
                )
            else:
                # Parse FamilySearch URL/citation
                metadata = self.citation_builder.parse_familysearch_url(
                    record.familysearch_citation, state_hint=record.state
                )

                # Build source data
                source_data = self.citation_builder.build_source(metadata)

                # Build citation data (source_id will be set by create_citation_for_person)
                citation_data = self.citation_builder.build_citation(
                    record, metadata, source_id=0  # Will be updated
                )

            # Create citation for person (complete workflow)
            source_id, citation_id, link_id, source_created = (
                db_writer.create_citation_for_person(
                    record.rin, source_data, citation_data
                )
            )

            # Success
            result.success = True
            result.source_id = source_id
            result.citation_id = citation_id
            # Note: link_id and source_created are not fields in RecordResult model

            logger.info(
                f"Successfully processed {record.full_name} (row {record.row_number}): "
                f"Source {source_id}, Citation {citation_id}"
            )

        except Exception as e:
            result.error_message = str(e)
            logger.error(
                f"Error processing {record.full_name} (row {record.row_number}): {e}",
                exc_info=True,
            )

        return result

    def validate_file(self, file_path: Path) -> BatchResult:
        """Validate a file without writing to database.

        Args:
            file_path: Path to CSV or XLSX file

        Returns:
            BatchResult with validation results (no database writes)
        """
        # Temporarily set dry_run
        original_dry_run = self.config.dry_run
        self.config.dry_run = True

        try:
            result = self.process_file(file_path)
            return result
        finally:
            # Restore original setting
            self.config.dry_run = original_dry_run

    def preview_file(self, file_path: Path, limit: int = 10) -> List[DraftRecord]:
        """Preview records from a file without processing.

        Args:
            file_path: Path to CSV or XLSX file
            limit: Maximum number of records to preview

        Returns:
            List of DraftRecord objects (up to limit)
        """
        return self.file_reader.preview(file_path, limit=limit)
