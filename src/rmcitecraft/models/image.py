"""
Data models for census image management.

Provides Pydantic models and enums for tracking census images throughout
their lifecycle from download to database integration.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class ImageStatus(str, Enum):
    """Status of a census image in the processing pipeline."""

    PENDING = "pending"  # Waiting for download
    DOWNLOADING = "downloading"  # Extension is downloading
    DOWNLOADED = "downloaded"  # File detected in downloads folder
    PROCESSING = "processing"  # Being renamed/moved
    LINKED = "linked"  # Successfully linked to RootsMagic
    FAILED = "failed"  # Processing failed
    DUPLICATE = "duplicate"  # Duplicate of existing image


class ImageMetadata(BaseModel):
    """
    Metadata for a census image.

    Tracks all information needed to download, process, organize,
    and link a census image to the RootsMagic database.
    """

    # Identification
    image_id: str = Field(description="Unique identifier for this image")
    citation_id: str = Field(description="Associated citation ID")

    # Census Details (for filename/folder)
    year: int = Field(ge=1790, le=1950, description="Census year")
    state: str = Field(description="State name")
    county: str = Field(description="County name")
    surname: str = Field(description="Person's surname (for filename)")
    given_name: str = Field(description="Person's given name (for filename)")

    # FamilySearch name (as it appears in the record, for citations)
    familysearch_name: str | None = Field(
        default=None, description="Name as it appears in FamilySearch record (for citations)"
    )

    # Additional Census Details (for citation formatting)
    town_ward: str | None = Field(default=None, description="Town/Ward/Township")
    enumeration_district: str | None = Field(default=None, description="Enumeration District")
    sheet: str | None = Field(default=None, description="Sheet number")
    line: str | None = Field(default=None, description="Line number")
    family_number: str | None = Field(default=None, description="Family number")
    dwelling_number: str | None = Field(default=None, description="Dwelling number")

    # Schedule Type (for folder selection)
    schedule_type: str = Field(default="population", description="Census schedule type")

    # FamilySearch Details
    familysearch_url: str = Field(description="FamilySearch ARK URL")
    access_date: str = Field(description="Date accessed (for citation)")

    # File Processing
    status: ImageStatus = Field(default=ImageStatus.PENDING)
    download_path: Path | None = Field(default=None, description="Path to downloaded file")
    final_path: Path | None = Field(
        default=None, description="Final destination path in RootsMagic structure"
    )
    final_filename: str | None = Field(default=None, description="Generated standardized filename")

    # Database Integration
    media_id: int | None = Field(default=None, description="RootsMagic MediaID after linking")
    event_id: int | None = Field(default=None, description="RootsMagic EventID for census event")

    # Error Tracking
    error_message: str | None = Field(default=None, description="Error details if failed")
    retry_count: int = Field(default=0, description="Number of retry attempts")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    downloaded_at: datetime | None = Field(default=None, description="When file was downloaded")
    linked_at: datetime | None = Field(default=None, description="When linked to database")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True  # Store enum values as strings

    def update_status(self, status: ImageStatus, error: str | None = None) -> None:
        """
        Update image status and timestamp.

        Args:
            status: New status
            error: Error message if status is FAILED
        """
        self.status = status
        self.updated_at = datetime.now()

        if status == ImageStatus.FAILED:
            self.error_message = error
            self.retry_count += 1
        elif status == ImageStatus.DOWNLOADED:
            self.downloaded_at = datetime.now()
        elif status == ImageStatus.LINKED:
            self.linked_at = datetime.now()

    def can_retry(self, max_retries: int = 3) -> bool:
        """
        Check if image processing can be retried.

        Args:
            max_retries: Maximum number of retry attempts

        Returns:
            True if retry is allowed
        """
        return self.status == ImageStatus.FAILED and self.retry_count < max_retries

    def get_expected_filename(self) -> str:
        """
        Generate expected standardized filename.

        Returns:
            Filename in format: YYYY, State, County - Surname, GivenName.ext

        Example:
            "1930, Oklahoma, Tulsa - Iams, Jesse Dorsey.jpg"
        """
        if self.final_filename:
            return self.final_filename

        # Will be set by FilenameGenerator service
        return f"{self.year}, {self.state}, {self.county} - {self.surname}, {self.given_name}.jpg"

    def get_expected_directory(self) -> str:
        """
        Get expected directory based on census year and schedule type.

        Returns:
            Relative path from media root

        Examples:
            "Records - Census/1930 Federal/"
            "Records - Census/1850 Federal Slave Schedule/"
        """
        # Will be determined by DirectoryMapper service
        base = "Records - Census"

        if self.schedule_type == "slave":
            return f"{base}/{self.year} Federal Slave Schedule/"
        elif self.schedule_type == "mortality":
            return f"{base}/Federal Mortality Schedule 1850-1885/{self.year} Mortality/"
        elif self.schedule_type == "veterans":
            return f"{base}/{self.year} Federal Veterans and Widows Schedule/"
        else:  # population (default)
            return f"{base}/{self.year} Federal/"
