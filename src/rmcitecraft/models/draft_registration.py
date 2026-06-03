"""Data structures for draft registration automation workflow."""

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from rmcitecraft.models.draft_record import DraftRecord


# Type alias for confirmation callbacks: async (person_name, ancestry_url, rin) -> bool
ConfirmationCallback = Optional[Callable[[str, str, int], Awaitable[bool]]]


@dataclass
class DraftAutomationOptions:
    """Options controlling the draft automation workflow."""

    discover_ancestry_urls: bool = True
    process_familysearch: bool = True
    process_ancestry: bool = True
    ancestry_metadata_only: bool = False
    notes: Optional[str] = None
    max_records: Optional[int] = None
    ancestry_url_confirmation_callback: ConfirmationCallback = None


@dataclass
class DraftAutomationRecordResult:
    """Result for a single record processed by the automation workflow."""

    record: DraftRecord
    success: bool = False
    skipped: bool = False
    skip_reason: Optional[str] = None
    message: Optional[str] = None
    source_type: Optional[str] = None
    url_type: Optional[str] = None
    registration_id: Optional[int] = None
    image_path: Optional[str] = None
    discovered_ancestry_url: Optional[str] = None


@dataclass
class DraftAutomationBatchResult:
    """Aggregated result for an automation batch."""

    total_records: int
    processed: int = 0
    successful: int = 0
    skipped: int = 0
    errors: int = 0
    record_results: list[DraftAutomationRecordResult] = field(default_factory=list)
    cancelled: bool = False
    limit_reached: bool = False

    def add_result(self, result: DraftAutomationRecordResult) -> None:
        """Add a record result and update counters."""
        self.record_results.append(result)
        self.processed += 1
        if result.skipped:
            self.skipped += 1
        elif result.success:
            self.successful += 1
        else:
            self.errors += 1


# Type alias for progress callbacks used by automation service
ProgressCallback = Optional[Callable[[int, int, str], None]]
