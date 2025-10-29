"""
Citation Import Service

Handles citation data imported from the browser extension.
Validates, processes, and queues citations for user review.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

from loguru import logger
from pydantic import BaseModel, Field, validator


class ImportedCitationData(BaseModel):
    """
    Pydantic model for citation data imported from extension.

    Validates data structure from browser extension.
    """

    # Metadata
    familySearchUrl: str = Field(..., description="FamilySearch ARK/PAL URL")
    extractedAt: str = Field(..., description="ISO timestamp when extracted")
    censusYear: int | None = Field(None, ge=1790, le=1950, description="Census year")

    # Person information
    name: str | None = Field(None, description="Person name")
    sex: str | None = Field(None, description="Sex/Gender")
    age: str | None = Field(None, description="Age")
    birthYear: str | None = Field(None, description="Birth year")
    race: str | None = Field(None, description="Race")
    relationship: str | None = Field(None, description="Relationship to head")
    maritalStatus: str | None = Field(None, description="Marital status")
    occupation: str | None = Field(None, description="Occupation")
    industry: str | None = Field(None, description="Industry")

    # Event information
    eventDate: str | None = Field(None, description="Event date")
    eventPlace: str | None = Field(None, description="Event place")
    eventPlaceOriginal: str | None = Field(None, description="Original place")

    # Census-specific fields
    enumerationDistrict: str | None = Field(None, description="Enumeration District")
    lineNumber: str | None = Field(None, description="Line number")
    pageNumber: str | None = Field(None, description="Page number")
    sheetNumber: str | None = Field(None, description="Sheet number")
    familyNumber: str | None = Field(None, description="Family number")
    dwellingNumber: str | None = Field(None, description="Dwelling number")

    # Additional metadata
    filmNumber: str | None = Field(None, description="Film number")
    imageNumber: str | None = Field(None, description="Image number")

    @validator("familySearchUrl")
    def validate_url(cls, v):
        """Validate FamilySearch URL format."""
        if not v or not isinstance(v, str):
            raise ValueError("familySearchUrl is required")
        if "familysearch.org" not in v.lower():
            raise ValueError("URL must be from familysearch.org")
        if not ("/ark:/" in v or "/pal:/" in v):
            raise ValueError("URL must contain /ark:/ or /pal:/")
        return v

    class Config:
        extra = "allow"  # Allow additional fields from extension


@dataclass
class PendingCitation:
    """Represents a citation pending user review."""

    id: str
    data: ImportedCitationData
    imported_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending, reviewed, approved, rejected

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "data": self.data.dict(),
            "imported_at": self.imported_at,
            "status": self.status,
        }


class CitationImportService:
    """
    Service for managing imported citations from browser extension.

    Handles validation, storage, and retrieval of imported citations.
    Uses file-based storage to persist across multiple processes.
    """

    def __init__(self, storage_path: Path | None = None):
        """Initialize citation import service.

        Args:
            storage_path: Path to JSON file for persistent storage
                         (default: logs/pending_citations.json)
        """
        if storage_path is None:
            storage_path = Path("logs/pending_citations.json")

        self._storage_path = Path(storage_path)
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

        # Load existing pending citations from file
        self._load_from_file()

        logger.info(f"Citation Import Service initialized (storage: {self._storage_path})")

    def _load_from_file(self) -> None:
        """Load pending citations from JSON file."""
        try:
            if self._storage_path.exists():
                with open(self._storage_path) as f:
                    data = json.load(f)

                # Reconstruct PendingCitation objects from stored data
                self._pending_citations = {}
                self._import_counter = data.get("import_counter", 0)

                for cit_dict in data.get("citations", []):
                    citation_data = ImportedCitationData(**cit_dict["data"])
                    pending = PendingCitation(
                        id=cit_dict["id"],
                        data=citation_data,
                        imported_at=cit_dict.get("imported_at", time.time()),
                        status=cit_dict.get("status", "pending")
                    )
                    self._pending_citations[pending.id] = pending

                logger.debug(f"Loaded {len(self._pending_citations)} pending citation(s) from file")
            else:
                self._pending_citations = {}
                self._import_counter = 0
                logger.debug("No existing citations file found, starting fresh")

        except Exception as e:
            logger.error(f"Failed to load citations from file: {e}")
            self._pending_citations = {}
            self._import_counter = 0

    def _save_to_file(self) -> None:
        """Save pending citations to JSON file."""
        try:
            data = {
                "import_counter": self._import_counter,
                "citations": [cit.to_dict() for cit in self._pending_citations.values()]
            }

            # Write atomically using a temporary file
            temp_path = self._storage_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2)

            # Atomic rename
            temp_path.replace(self._storage_path)

            logger.debug(f"Saved {len(self._pending_citations)} pending citation(s) to file")

        except Exception as e:
            logger.error(f"Failed to save citations to file: {e}")

    def import_citation(self, data: dict) -> str:
        """
        Import citation data from extension.

        Args:
            data: Raw citation data from extension

        Returns:
            Citation ID

        Raises:
            ValueError: If data validation fails
        """
        with self._lock:
            try:
                # Reload from file to get latest state
                self._load_from_file()

                # Validate data structure
                validated_data = ImportedCitationData(**data)

                # Generate citation ID
                self._import_counter += 1
                citation_id = f"import_{int(time.time())}_{self._import_counter}"

                # Create pending citation
                pending = PendingCitation(
                    id=citation_id,
                    data=validated_data,
                )

                self._pending_citations[citation_id] = pending

                # Save to file immediately
                self._save_to_file()

                logger.info(
                    f"Imported citation: {citation_id} - "
                    f"{validated_data.name or 'Unknown'} ({validated_data.censusYear or 'No year'})"
                )

                return citation_id

            except Exception as e:
                logger.error(f"Failed to import citation: {e}")
                raise ValueError(f"Invalid citation data: {e}")

    def get_pending(self) -> list[dict]:
        """
        Get all pending citations.

        Returns:
            List of pending citation dictionaries
        """
        with self._lock:
            # Reload from file to get latest state (may be from different process)
            self._load_from_file()

            pending = [
                cit.to_dict()
                for cit in self._pending_citations.values()
                if cit.status == "pending"
            ]

            logger.debug(f"Retrieved {len(pending)} pending citation(s)")
            return pending

    def get(self, citation_id: str) -> dict | None:
        """
        Get a specific citation by ID.

        Args:
            citation_id: Citation ID

        Returns:
            Citation dictionary if found, None otherwise
        """
        citation = self._pending_citations.get(citation_id)
        return citation.to_dict() if citation else None

    def update_status(
        self, citation_id: str, status: str
    ) -> bool:
        """
        Update citation status.

        Args:
            citation_id: Citation ID
            status: New status (pending, reviewed, approved, rejected)

        Returns:
            True if updated, False if not found
        """
        if citation_id not in self._pending_citations:
            logger.warning(f"Attempted to update unknown citation: {citation_id}")
            return False

        citation = self._pending_citations[citation_id]
        old_status = citation.status
        citation.status = status

        logger.info(f"Updated citation {citation_id}: {old_status} → {status}")
        return True

    def approve(self, citation_id: str) -> bool:
        """
        Approve a citation for processing.

        Args:
            citation_id: Citation ID

        Returns:
            True if approved, False if not found
        """
        return self.update_status(citation_id, "approved")

    def reject(self, citation_id: str) -> bool:
        """
        Reject a citation.

        Args:
            citation_id: Citation ID

        Returns:
            True if rejected, False if not found
        """
        if self.update_status(citation_id, "rejected"):
            # Remove from pending queue
            del self._pending_citations[citation_id]
            return True
        return False

    def remove(self, citation_id: str) -> bool:
        """
        Remove a citation from pending queue.

        Args:
            citation_id: Citation ID

        Returns:
            True if removed, False if not found
        """
        with self._lock:
            self._load_from_file()

            if citation_id in self._pending_citations:
                del self._pending_citations[citation_id]
                self._save_to_file()
                logger.info(f"Removed citation: {citation_id}")
                return True
            return False

    def clear(self) -> int:
        """
        Clear all pending citations.

        Returns:
            Number of citations cleared
        """
        count = len(self._pending_citations)
        self._pending_citations.clear()
        logger.info(f"Cleared {count} pending citation(s)")
        return count

    def get_stats(self) -> dict:
        """
        Get import statistics.

        Returns:
            Dictionary with statistics
        """
        status_counts = {}
        for citation in self._pending_citations.values():
            status_counts[citation.status] = status_counts.get(citation.status, 0) + 1

        return {
            "total": len(self._pending_citations),
            "total_imported": self._import_counter,
            "by_status": status_counts,
        }


# Global singleton instance
_citation_import_service: CitationImportService | None = None


def get_citation_import_service() -> CitationImportService:
    """
    Get the global citation import service instance.

    Returns:
        CitationImportService singleton instance
    """
    global _citation_import_service
    if _citation_import_service is None:
        _citation_import_service = CitationImportService()
    return _citation_import_service
