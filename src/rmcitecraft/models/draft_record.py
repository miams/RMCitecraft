"""Data models for draft registration processing."""

from dataclasses import dataclass
from typing import Optional
from datetime import date


@dataclass
class DraftRecord:
    """Represents a single draft registration record from CSV/XLSX file.

    Attributes:
        row_number: Line number in the source file (for error reporting)
        rin: RootsMagic Record Identification Number (PersonID)
        given_name: Given name(s) of the person
        surname: Surname/family name
        birth_year: Year of birth (for validation and matching)
        death_year: Year of death (for validation)
        familysearch_citation: FamilySearch URL or citation text
        ancestry_url: AncestryLibrary URL (optional)
        registration_date: Date of draft registration (ISO format YYYY-MM-DD)
        state: State where registered (e.g., "Pennsylvania", "PA")
        county: County where registered (optional)
        notes: Additional notes or information
    """

    row_number: int
    rin: Optional[int]
    given_name: str
    surname: str
    birth_year: Optional[int]
    death_year: Optional[int]
    familysearch_citation: str
    ancestry_url: Optional[str] = None
    registration_date: Optional[str] = None
    state: Optional[str] = None
    county: Optional[str] = None
    notes: Optional[str] = None

    def __post_init__(self):
        """Validate and normalize data after initialization."""
        # Strip whitespace from string fields
        if self.given_name:
            self.given_name = self.given_name.strip()
        if self.surname:
            self.surname = self.surname.strip()
        if self.state:
            self.state = self.state.strip()
        if self.county:
            self.county = self.county.strip()
        if self.familysearch_citation:
            self.familysearch_citation = self.familysearch_citation.strip()
        if self.ancestry_url:
            self.ancestry_url = self.ancestry_url.strip()

    @property
    def full_name(self) -> str:
        """Return full name (Given Surname)."""
        return f"{self.given_name} {self.surname}".strip()

    @property
    def is_valid_rin(self) -> bool:
        """Check if RIN is valid (positive integer)."""
        return self.rin is not None and self.rin > 0

    @property
    def has_familysearch_url(self) -> bool:
        """Check if familysearch_citation contains a FamilySearch URL."""
        if not self.familysearch_citation:
            return False
        citation_lower = self.familysearch_citation.lower()
        return 'familysearch.org' in citation_lower or 'ark:/' in citation_lower

    @property
    def has_ancestry_url(self) -> bool:
        """Check if ancestry_url is populated."""
        if not self.ancestry_url:
            return False
        return 'ancestrylibrary.com' in self.ancestry_url.lower() or 'ancestry.com' in self.ancestry_url.lower()


@dataclass
class ValidationResult:
    """Result of validating a draft record.

    Attributes:
        is_valid: Whether the record passed validation
        errors: List of error messages
        warnings: List of warning messages
    """

    is_valid: bool
    errors: list[str]
    warnings: list[str]

    def __init__(self):
        self.is_valid = True
        self.errors = []
        self.warnings = []

    def add_error(self, message: str):
        """Add an error message and mark as invalid."""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str):
        """Add a warning message (doesn't invalidate record)."""
        self.warnings.append(message)

    @property
    def has_issues(self) -> bool:
        """Check if there are any errors or warnings."""
        return bool(self.errors or self.warnings)

    def __str__(self) -> str:
        """Return a formatted string of all issues."""
        parts = []
        if self.errors:
            parts.append(f"Errors: {'; '.join(self.errors)}")
        if self.warnings:
            parts.append(f"Warnings: {'; '.join(self.warnings)}")
        return ' | '.join(parts) if parts else 'No issues'


@dataclass
class RecordResult:
    """Result of processing a single draft record.

    Attributes:
        record: The original draft record
        success: Whether processing succeeded
        source_id: Created/matched SourceID (if successful)
        citation_id: Created CitationID (if successful)
        event_id: Created EventID (if successful and events enabled)
        media_id: Created MediaID (if successful and images downloaded)
        matched_person_id: PersonID matched to (may differ from record.rin)
        match_confidence: Confidence score of person match (0-100)
        error_message: Error message if failed
        warning_messages: List of warning messages
        skipped: Whether the record was skipped
        skip_reason: Reason for skipping
    """

    record: DraftRecord
    success: bool = False
    source_id: Optional[int] = None
    citation_id: Optional[int] = None
    event_id: Optional[int] = None
    media_id: Optional[int] = None
    matched_person_id: Optional[int] = None
    match_confidence: Optional[float] = None
    error_message: Optional[str] = None
    warning_messages: list[str] = None
    skipped: bool = False
    skip_reason: Optional[str] = None

    def __post_init__(self):
        if self.warning_messages is None:
            self.warning_messages = []

    def add_warning(self, message: str):
        """Add a warning message."""
        self.warning_messages.append(message)

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return bool(self.warning_messages)


@dataclass
class BatchResult:
    """Result of processing a batch of draft records.

    Attributes:
        batch_id: Unique identifier for this batch
        total_records: Total number of records in batch
        processed: Number of records processed (attempted)
        successful: Number of records successfully processed
        warnings: Number of records with warnings
        errors: Number of records with errors
        skipped: Number of records skipped
        record_results: Detailed results for each record
        processing_time: Total processing time in seconds
        start_time: When processing started
        end_time: When processing ended
    """

    batch_id: int
    total_records: int
    processed: int = 0
    successful: int = 0
    warnings: int = 0
    errors: int = 0
    skipped: int = 0
    record_results: list[RecordResult] = None
    processing_time: float = 0.0
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    def __post_init__(self):
        if self.record_results is None:
            self.record_results = []

    def add_result(self, result: RecordResult):
        """Add a record result and update counters."""
        self.record_results.append(result)
        self.processed += 1

        if result.skipped:
            self.skipped += 1
        elif result.success:
            self.successful += 1
            if result.has_warnings:
                self.warnings += 1
        else:
            self.errors += 1

    @property
    def success_rate(self) -> float:
        """Calculate success rate (0-100)."""
        if self.processed == 0:
            return 0.0
        return (self.successful / self.processed) * 100

    @property
    def completion_rate(self) -> float:
        """Calculate completion rate (0-100)."""
        if self.total_records == 0:
            return 0.0
        return (self.processed / self.total_records) * 100

    def get_summary(self) -> str:
        """Get a text summary of the batch results."""
        return (
            f"Batch {self.batch_id} Results:\n"
            f"  Total: {self.total_records}\n"
            f"  Processed: {self.processed} ({self.completion_rate:.1f}%)\n"
            f"  Successful: {self.successful} ({self.success_rate:.1f}%)\n"
            f"  Warnings: {self.warnings}\n"
            f"  Errors: {self.errors}\n"
            f"  Skipped: {self.skipped}\n"
            f"  Processing Time: {self.processing_time:.2f}s"
        )
