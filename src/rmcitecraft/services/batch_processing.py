"""Batch Processing Controller for RMCitecraft.

This module manages the state and workflow for batch processing of census citations.
It implements the state machine: queued → extracting → manual_review → complete/error
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger

from rmcitecraft.models.image import ImageMetadata
from rmcitecraft.validation.data_quality import CensusDataValidator, ValidationResult


class CitationStatus(Enum):
    """Status of a citation in the batch processing workflow."""

    QUEUED = "queued"  # Waiting to be processed
    EXTRACTING = "extracting"  # Currently extracting from FamilySearch
    MANUAL_REVIEW = "manual_review"  # Needs manual data entry
    VALIDATING = "validating"  # Running validation
    COMPLETE = "complete"  # Successfully processed and validated
    ERROR = "error"  # Failed processing


class BatchProcessingState(Enum):
    """Overall state of the batch processing session."""

    IDLE = "idle"  # No active batch
    LOADING = "loading"  # Loading citations from database
    READY = "ready"  # Citations loaded, ready to process
    PROCESSING = "processing"  # Actively processing citations
    PAUSED = "paused"  # Processing paused by user
    COMPLETE = "complete"  # All citations processed
    ERROR = "error"  # Batch processing failed


@dataclass
class CitationBatchItem:
    """Represents a single citation in the batch processing queue."""

    # Database IDs
    event_id: int
    person_id: int
    citation_id: int
    source_id: int

    # Person info
    given_name: str
    surname: str
    full_name: str

    # Census info
    census_year: int
    source_name: str
    familysearch_url: str | None = None

    # Processing status
    status: CitationStatus = CitationStatus.QUEUED

    # Extracted data (from FamilySearch)
    extracted_data: dict[str, Any] = field(default_factory=dict)

    # Manual data (user entered)
    manual_data: dict[str, Any] = field(default_factory=dict)

    # Merged data (extracted + manual)
    merged_data: dict[str, Any] = field(default_factory=dict)

    # Validation results
    validation: ValidationResult | None = None

    # Error message (if status == ERROR)
    error: str | None = None

    # Formatted citations (after successful processing)
    footnote: str | None = None
    short_footnote: str | None = None
    bibliography: str | None = None

    # Existing media
    has_existing_media: bool = False
    existing_files: str | None = None

    # Downloaded image (for manual entry)
    local_image_path: str | None = None

    # Timestamps
    queued_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def is_complete(self) -> bool:
        """Check if citation processing is complete."""
        return self.status == CitationStatus.COMPLETE

    @property
    def is_error(self) -> bool:
        """Check if citation processing failed."""
        return self.status == CitationStatus.ERROR

    @property
    def needs_manual_entry(self) -> bool:
        """Check if citation needs manual data entry."""
        return self.status == CitationStatus.MANUAL_REVIEW

    @property
    def missing_fields(self) -> list[str]:
        """Get list of missing required fields."""
        if self.validation:
            return self.validation.missing_required
        return []


@dataclass
class BatchProcessingSession:
    """Represents a batch processing session."""

    session_id: str
    census_year: int
    state: BatchProcessingState = BatchProcessingState.IDLE
    citations: list[CitationBatchItem] = field(default_factory=list)
    current_index: int = 0
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    @property
    def current_citation(self) -> CitationBatchItem | None:
        """Get the currently selected citation."""
        if 0 <= self.current_index < len(self.citations):
            return self.citations[self.current_index]
        return None

    @property
    def total_count(self) -> int:
        """Total number of citations in batch."""
        return len(self.citations)

    @property
    def complete_count(self) -> int:
        """Number of completed citations."""
        return sum(1 for c in self.citations if c.is_complete)

    @property
    def error_count(self) -> int:
        """Number of failed citations."""
        return sum(1 for c in self.citations if c.is_error)

    @property
    def pending_count(self) -> int:
        """Number of pending citations (queued or manual review)."""
        return sum(
            1
            for c in self.citations
            if c.status in (CitationStatus.QUEUED, CitationStatus.MANUAL_REVIEW)
        )

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_count == 0:
            return 0.0
        return (self.complete_count / self.total_count) * 100

    def get_citations_by_status(self, status: CitationStatus) -> list[CitationBatchItem]:
        """Get all citations with specified status."""
        return [c for c in self.citations if c.status == status]

    def move_to_next(self) -> bool:
        """Move to next citation in queue.

        Returns:
            True if moved to next citation, False if at end
        """
        if self.current_index < len(self.citations) - 1:
            self.current_index += 1
            return True
        return False

    def move_to_previous(self) -> bool:
        """Move to previous citation in queue.

        Returns:
            True if moved to previous citation, False if at beginning
        """
        if self.current_index > 0:
            self.current_index -= 1
            return True
        return False

    def move_to_citation(self, citation_id: int) -> bool:
        """Jump to specific citation by citation_id.

        Args:
            citation_id: The citation ID to jump to

        Returns:
            True if found and moved, False otherwise
        """
        for i, citation in enumerate(self.citations):
            if citation.citation_id == citation_id:
                self.current_index = i
                return True
        return False


class BatchProcessingController:
    """Controls batch processing workflow and state management."""

    def __init__(self):
        """Initialize batch processing controller."""
        self.session: BatchProcessingSession | None = None
        self.validator = CensusDataValidator()

    def create_session(self, census_year: int, citations_data: list[dict]) -> BatchProcessingSession:
        """Create a new batch processing session.

        Args:
            census_year: Census year being processed
            citations_data: List of citation data dictionaries from database query

        Returns:
            New BatchProcessingSession instance
        """
        session_id = f"batch_{census_year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        citations = []
        for data in citations_data:
            # Check if citation already has formatted output from database
            footnote = data.get('footnote')
            short_footnote = data.get('short_footnote')
            bibliography = data.get('bibliography')

            # Determine if this is an Evidence Explained citation (not original FamilySearch)
            # Evidence Explained format starts with "YYYY U.S. census,"
            # FamilySearch format starts with '"United States Census, YYYY,"'
            is_evidence_explained = False
            if footnote:
                # Check for Evidence Explained pattern: "1930 U.S. census, ..."
                if re.match(r'^\d{4}\s+U\.S\.\s+census,', footnote):
                    is_evidence_explained = True

            # Determine initial status based on whether Evidence Explained citations exist
            initial_status = CitationStatus.COMPLETE if is_evidence_explained else CitationStatus.QUEUED

            citation = CitationBatchItem(
                event_id=data['event_id'],
                person_id=data['person_id'],
                citation_id=data['citation_id'],
                source_id=data['source_id'],
                given_name=data.get('given_name', ''),
                surname=data.get('surname', ''),
                full_name=data.get('full_name', ''),
                census_year=census_year,
                source_name=data.get('source_name', ''),
                familysearch_url=data.get('familysearch_url'),
                has_existing_media=data.get('has_existing_media', False),
                existing_files=data.get('existing_files'),
                local_image_path=data.get('existing_image_path'),  # Use existing image if available
                status=initial_status,
                footnote=footnote if is_evidence_explained else None,
                short_footnote=short_footnote if is_evidence_explained else None,
                bibliography=bibliography if is_evidence_explained else None,
            )

            # If citation is complete, parse source_name to populate extracted_data
            if initial_status == CitationStatus.COMPLETE and data.get('source_name'):
                from rmcitecraft.parsers.source_name_parser import SourceNameParser
                try:
                    # Parse source name to get basic location data
                    parsed = SourceNameParser.parse(data['source_name'])
                    if parsed:
                        citation.extracted_data = {
                            'state': parsed.get('state', ''),
                            'county': parsed.get('county', ''),
                        }
                        citation.merged_data = citation.extracted_data.copy()
                except Exception as e:
                    logger.warning(f"Could not parse source name for citation {citation.citation_id}: {e}")

            citations.append(citation)

        self.session = BatchProcessingSession(
            session_id=session_id,
            census_year=census_year,
            state=BatchProcessingState.READY,
            citations=citations,
        )

        logger.info(f"Created batch session {session_id} with {len(citations)} citations")
        return self.session

    def update_citation_extracted_data(self, citation: CitationBatchItem, extracted_data: dict) -> None:
        """Update citation with extracted data from FamilySearch.

        Args:
            citation: Citation to update
            extracted_data: Extracted data dictionary
        """
        citation.extracted_data = extracted_data
        citation.merged_data = {**citation.merged_data, **extracted_data}

        # DEBUG: Log merged data after update
        logger.debug(f"After extraction - citation {citation.citation_id}: merged_data keys={list(citation.merged_data.keys())}, merged_data={citation.merged_data}")

        # Validate extracted data
        validation = self.validator.validate(
            citation.merged_data,
            citation.census_year
        )
        citation.validation = validation

        # Update status based on validation
        if validation.is_valid:
            citation.status = CitationStatus.COMPLETE

            # Generate formatted citations
            try:
                from rmcitecraft.services.citation_formatter import format_census_citation_preview

                # Add person name to data for formatting
                formatting_data = {
                    **citation.merged_data,
                    'person_name': citation.full_name,
                    'familysearch_url': citation.familysearch_url,
                }

                formatted = format_census_citation_preview(formatting_data, citation.census_year)
                citation.footnote = formatted.get('footnote')
                citation.short_footnote = formatted.get('short_footnote')
                citation.bibliography = formatted.get('bibliography')

                logger.debug(f"Generated formatted citations for {citation.citation_id}")
            except Exception as e:
                logger.error(f"Failed to format citation {citation.citation_id}: {e}")
                # Keep status as COMPLETE but log error
        else:
            citation.status = CitationStatus.MANUAL_REVIEW

        logger.debug(
            f"Updated citation {citation.citation_id}: "
            f"status={citation.status.value}, "
            f"validation={validation.is_valid}"
        )

    def update_citation_manual_data(self, citation: CitationBatchItem, manual_data: dict) -> None:
        """Update citation with manually entered data.

        Args:
            citation: Citation to update
            manual_data: Manually entered data dictionary
        """
        citation.manual_data = manual_data
        citation.merged_data = {**citation.extracted_data, **manual_data}

        # Re-validate with complete data
        validation = self.validator.validate(
            citation.merged_data,
            citation.census_year
        )
        citation.validation = validation

        # Update status
        if validation.is_valid:
            citation.status = CitationStatus.COMPLETE
            citation.completed_at = datetime.now()

            # Generate formatted citations
            try:
                from rmcitecraft.services.citation_formatter import format_census_citation_preview

                # Add person name to data for formatting
                formatting_data = {
                    **citation.merged_data,
                    'person_name': citation.full_name,
                    'familysearch_url': citation.familysearch_url,
                }

                formatted = format_census_citation_preview(formatting_data, citation.census_year)
                citation.footnote = formatted.get('footnote')
                citation.short_footnote = formatted.get('short_footnote')
                citation.bibliography = formatted.get('bibliography')

                logger.debug(f"Generated formatted citations for {citation.citation_id}")
            except Exception as e:
                logger.error(f"Failed to format citation {citation.citation_id}: {e}")
                # Keep status as COMPLETE but log error
        else:
            citation.status = CitationStatus.MANUAL_REVIEW

        logger.debug(
            f"Updated manual data for citation {citation.citation_id}: "
            f"validation={validation.is_valid}"
        )

    def mark_citation_error(self, citation: CitationBatchItem, error: str) -> None:
        """Mark citation as failed with error message.

        Args:
            citation: Citation to mark as error
            error: Error message
        """
        citation.status = CitationStatus.ERROR
        citation.error = error
        citation.completed_at = datetime.now()
        logger.error(f"Citation {citation.citation_id} failed: {error}")

    def get_session_summary(self) -> dict[str, Any]:
        """Get summary statistics for current session.

        Returns:
            Dictionary with session statistics
        """
        if not self.session:
            return {}

        return {
            'session_id': self.session.session_id,
            'census_year': self.session.census_year,
            'state': self.session.state.value,
            'total': self.session.total_count,
            'complete': self.session.complete_count,
            'error': self.session.error_count,
            'pending': self.session.pending_count,
            'progress_percentage': self.session.progress_percentage,
            'started_at': self.session.started_at.isoformat(),
            'completed_at': self.session.completed_at.isoformat() if self.session.completed_at else None,
        }
