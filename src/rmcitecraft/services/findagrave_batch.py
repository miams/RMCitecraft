"""
Find a Grave Batch Processing Controller

Manages state and workflow for batch processing Find a Grave memorials.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from loguru import logger

from rmcitecraft.validation.data_quality import ValidationResult


class FindAGraveStatus(Enum):
    """Status of a Find a Grave item in batch processing."""

    QUEUED = "queued"  # Waiting to be processed
    EXTRACTING = "extracting"  # Currently extracting from Find a Grave
    NEEDS_REVIEW = "needs_review"  # Needs user review/decision
    COMPLETE = "complete"  # Successfully processed
    ERROR = "error"  # Failed processing


@dataclass
class FindAGraveBatchItem:
    """Represents a single Find a Grave memorial in batch processing."""

    # Database IDs
    person_id: int
    link_id: int  # URLTable LinkID

    # Person info
    surname: str
    given_name: str
    full_name: str
    birth_year: int | None
    death_year: int | None
    sex: int  # 0=Male, 1=Female, 2=Unknown

    # Find a Grave info
    memorial_id: str
    url: str
    note: str | None = None

    # Processing status
    status: FindAGraveStatus = FindAGraveStatus.QUEUED

    # Extracted data (from Find a Grave page)
    extracted_data: dict[str, Any] = field(default_factory=dict)

    # Photo information
    photos: list[dict[str, Any]] = field(default_factory=list)

    # Event IDs (for linking citations)
    burial_event_id: int | None = None
    death_event_id: int | None = None
    birth_event_id: int | None = None

    # Created source and citation IDs
    source_id: int | None = None
    citation_id: int | None = None

    # Validation results
    validation: ValidationResult | None = None

    # Error message (if status == ERROR)
    error: str | None = None

    # Formatted citations
    footnote: str | None = None
    short_footnote: str | None = None
    bibliography: str | None = None

    # Downloaded image info
    downloaded_images: list[str] = field(default_factory=list)

    # Timestamps
    queued_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def is_complete(self) -> bool:
        """Check if processing is complete."""
        return self.status == FindAGraveStatus.COMPLETE

    @property
    def is_error(self) -> bool:
        """Check if processing failed."""
        return self.status == FindAGraveStatus.ERROR

    @property
    def needs_review(self) -> bool:
        """Check if item needs user review."""
        return self.status == FindAGraveStatus.NEEDS_REVIEW

    @property
    def maiden_name(self) -> str | None:
        """Extract maiden name if available."""
        # Maiden name detected from Find a Grave HTML (italicized)
        return self.extracted_data.get('maidenName')

    @property
    def cemetery_name(self) -> str | None:
        """Get cemetery name from extracted data."""
        return self.extracted_data.get('cemeteryName')

    @property
    def cemetery_location(self) -> str | None:
        """Get formatted cemetery location."""
        parts = []
        if city := self.extracted_data.get('cemeteryCity'):
            parts.append(city)
        if county := self.extracted_data.get('cemeteryCounty'):
            parts.append(f"{county} County")
        if state := self.extracted_data.get('cemeteryState'):
            parts.append(state)
        if country := self.extracted_data.get('cemeteryCountry'):
            if country != 'USA':
                parts.append(country)

        return ', '.join(parts) if parts else None


@dataclass
class FindAGraveBatchSession:
    """Represents a Find a Grave batch processing session."""

    session_id: str
    items: list[FindAGraveBatchItem] = field(default_factory=list)
    current_index: int = 0
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    @property
    def current_item(self) -> FindAGraveBatchItem | None:
        """Get the currently selected item."""
        if 0 <= self.current_index < len(self.items):
            return self.items[self.current_index]
        return None

    @property
    def total_count(self) -> int:
        """Total number of items in batch."""
        return len(self.items)

    @property
    def complete_count(self) -> int:
        """Number of completed items."""
        return sum(1 for item in self.items if item.is_complete)

    @property
    def error_count(self) -> int:
        """Number of failed items."""
        return sum(1 for item in self.items if item.is_error)

    @property
    def pending_count(self) -> int:
        """Number of pending items."""
        return sum(
            1 for item in self.items
            if item.status in (FindAGraveStatus.QUEUED, FindAGraveStatus.NEEDS_REVIEW)
        )

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_count == 0:
            return 0.0
        return (self.complete_count / self.total_count) * 100

    def get_items_by_status(self, status: FindAGraveStatus) -> list[FindAGraveBatchItem]:
        """Get all items with specified status."""
        return [item for item in self.items if item.status == status]

    def move_to_next(self) -> bool:
        """Move to next item in queue."""
        if self.current_index < len(self.items) - 1:
            self.current_index += 1
            return True
        return False

    def move_to_previous(self) -> bool:
        """Move to previous item in queue."""
        if self.current_index > 0:
            self.current_index -= 1
            return True
        return False

    def move_to_item(self, person_id: int) -> bool:
        """Jump to specific item by person_id."""
        for i, item in enumerate(self.items):
            if item.person_id == person_id:
                self.current_index = i
                return True
        return False


class FindAGraveBatchController:
    """Controls Find a Grave batch processing workflow."""

    def __init__(self):
        """Initialize batch controller."""
        self.session: FindAGraveBatchSession | None = None

    def create_session(self, people_data: list[dict]) -> FindAGraveBatchSession:
        """
        Create a new batch processing session.

        Args:
            people_data: List of person data from database query

        Returns:
            New FindAGraveBatchSession instance
        """
        session_id = f"findagrave_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        items = []
        for data in people_data:
            item = FindAGraveBatchItem(
                person_id=data['person_id'],
                link_id=data['link_id'],
                surname=data['surname'],
                given_name=data['given_name'],
                full_name=data['full_name'],
                birth_year=data.get('birth_year'),
                death_year=data.get('death_year'),
                sex=data['sex'],
                memorial_id=data['memorial_id'],
                url=data['url'],
                note=data.get('note'),
            )
            items.append(item)

        self.session = FindAGraveBatchSession(
            session_id=session_id,
            items=items,
        )

        logger.info(f"Created Find a Grave batch session {session_id} with {len(items)} items")
        return self.session

    def update_item_extracted_data(self, item: FindAGraveBatchItem, extracted_data: dict) -> None:
        """
        Update item with extracted data from Find a Grave.

        Args:
            item: Item to update
            extracted_data: Extracted data dictionary
        """
        item.extracted_data = extracted_data
        item.photos = extracted_data.get('photos', [])

        logger.debug(
            f"Updated item {item.person_id}: "
            f"cemetery={item.cemetery_name}, "
            f"photos={len(item.photos)}"
        )

    def mark_item_complete(
        self,
        item: FindAGraveBatchItem,
        source_id: int,
        citation_id: int,
        burial_event_id: int | None = None,
    ) -> None:
        """
        Mark item as complete.

        Args:
            item: Item to mark complete
            source_id: Created source ID
            citation_id: Created citation ID
            burial_event_id: Created burial event ID (if applicable)
        """
        item.status = FindAGraveStatus.COMPLETE
        item.source_id = source_id
        item.citation_id = citation_id
        item.burial_event_id = burial_event_id
        item.completed_at = datetime.now()

        logger.info(f"Item {item.person_id} marked complete")

    def mark_item_error(self, item: FindAGraveBatchItem, error: str) -> None:
        """
        Mark item as failed with error message.

        Args:
            item: Item to mark as error
            error: Error message
        """
        item.status = FindAGraveStatus.ERROR
        item.error = error
        item.completed_at = datetime.now()

        logger.error(f"Item {item.person_id} failed: {error}")

    def mark_item_needs_review(self, item: FindAGraveBatchItem, reason: str) -> None:
        """
        Mark item as needing user review.

        Args:
            item: Item to mark for review
            reason: Reason for review
        """
        item.status = FindAGraveStatus.NEEDS_REVIEW
        item.error = f"Needs review: {reason}"

        logger.warning(f"Item {item.person_id} needs review: {reason}")

    def get_session_summary(self) -> dict[str, Any]:
        """Get summary statistics for current session."""
        if not self.session:
            return {}

        return {
            'session_id': self.session.session_id,
            'total': self.session.total_count,
            'complete': self.session.complete_count,
            'error': self.session.error_count,
            'pending': self.session.pending_count,
            'progress_percentage': self.session.progress_percentage,
            'started_at': self.session.started_at.isoformat(),
            'completed_at': self.session.completed_at.isoformat() if self.session.completed_at else None,
        }
