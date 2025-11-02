"""
Pending Request Service

Tracks FamilySearch page requests initiated from RMCiteCraft.
When user clicks "Open FamilySearch", we store the CitationID so
we can associate incoming browser extension data with the correct citation.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

from loguru import logger


@dataclass
class PendingRequest:
    """Represents a pending FamilySearch page request."""

    citation_id: int
    familysearch_url: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON storage."""
        return {
            "citation_id": self.citation_id,
            "familysearch_url": self.familysearch_url,
            "timestamp": self.timestamp,
        }


class PendingRequestService:
    """
    Service for managing pending FamilySearch page requests.

    When user clicks "Open FamilySearch" in RMCiteCraft, we store the
    CitationID. When the browser extension sends data, we match it to
    the pending request to get the correct CitationID.

    This eliminates the need to guess CitationID by matching names.
    """

    def __init__(self, storage_path: Path | None = None):
        """Initialize pending request service.

        Args:
            storage_path: Path to JSON file for persistent storage
                         (default: logs/pending_requests.json)
        """
        if storage_path is None:
            storage_path = Path("logs/pending_requests.json")

        self._storage_path = Path(storage_path)
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

        # Load existing pending requests from file
        self._load_from_file()

        logger.info(f"Pending Request Service initialized (storage: {self._storage_path})")

    def _load_from_file(self) -> None:
        """Load pending requests from JSON file."""
        try:
            if self._storage_path.exists():
                with open(self._storage_path) as f:
                    data = json.load(f)

                # Reconstruct PendingRequest objects from stored data
                self._pending_requests = []
                for req_dict in data.get("requests", []):
                    request = PendingRequest(
                        citation_id=req_dict["citation_id"],
                        familysearch_url=req_dict["familysearch_url"],
                        timestamp=req_dict.get("timestamp", time.time()),
                    )
                    self._pending_requests.append(request)

                # Clear old requests (older than 1 hour)
                self._clear_old_requests()

                logger.debug(f"Loaded {len(self._pending_requests)} pending request(s) from file")
            else:
                self._pending_requests = []
                logger.debug("No existing requests file found, starting fresh")

        except Exception as e:
            logger.error(f"Failed to load requests from file: {e}")
            self._pending_requests = []

    def _save_to_file(self) -> None:
        """Save pending requests to JSON file."""
        try:
            data = {"requests": [req.to_dict() for req in self._pending_requests]}

            # Write atomically using a temporary file
            temp_path = self._storage_path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2)

            # Atomic rename
            temp_path.replace(self._storage_path)

            logger.debug(f"Saved {len(self._pending_requests)} pending request(s) to file")

        except Exception as e:
            logger.error(f"Failed to save requests to file: {e}")

    def _clear_old_requests(self, max_age_seconds: float = 3600) -> None:
        """Remove requests older than max_age_seconds (default: 1 hour)."""
        now = time.time()
        before_count = len(self._pending_requests)

        self._pending_requests = [
            req for req in self._pending_requests if (now - req.timestamp) < max_age_seconds
        ]

        removed = before_count - len(self._pending_requests)
        if removed > 0:
            logger.debug(f"Cleared {removed} old pending request(s)")

    def register_request(self, citation_id: int, familysearch_url: str) -> None:
        """
        Register a pending FamilySearch page request.

        Called when user clicks "Open FamilySearch" button in UI.

        Args:
            citation_id: RootsMagic CitationID from database
            familysearch_url: FamilySearch ARK/PAL URL being opened
        """
        with self._lock:
            # Reload from file to get latest state
            self._load_from_file()

            # Create pending request
            request = PendingRequest(
                citation_id=citation_id,
                familysearch_url=familysearch_url,
            )

            self._pending_requests.append(request)

            # Save to file immediately
            self._save_to_file()

            logger.info(
                f"Registered pending request: CitationID={citation_id} for URL={familysearch_url}"
            )

    def _normalize_url(self, url: str) -> str:
        """
        Normalize FamilySearch URL for comparison.

        Removes www prefix, query parameters, and trailing slashes.

        Args:
            url: FamilySearch URL

        Returns:
            Normalized URL for comparison
        """
        # Remove query parameters
        if "?" in url:
            url = url.split("?")[0]

        # Remove www. prefix
        url = url.replace("://www.", "://")

        # Remove trailing slash
        url = url.rstrip("/")

        return url

    def match_and_consume(self, familysearch_url: str) -> int | None:
        """
        Match incoming browser extension data to pending request.

        Finds the most recent pending request for the given URL,
        removes it from the queue, and returns the CitationID.

        URLs are normalized before matching to handle variations like:
        - www. prefix differences
        - Query parameters (?lang=en)
        - Trailing slashes

        Args:
            familysearch_url: FamilySearch URL from browser extension

        Returns:
            CitationID if matched, None if no pending request found
        """
        with self._lock:
            # Reload from file to get latest state
            self._load_from_file()

            # Normalize incoming URL
            normalized_url = self._normalize_url(familysearch_url)

            # Find matching request (most recent first)
            matched_request = None
            for i in range(len(self._pending_requests) - 1, -1, -1):
                # Normalize stored URL for comparison
                stored_url = self._normalize_url(self._pending_requests[i].familysearch_url)

                if stored_url == normalized_url:
                    matched_request = self._pending_requests.pop(i)
                    break

            if matched_request:
                # Save updated list (with request removed)
                self._save_to_file()

                logger.info(
                    f"Matched pending request: CitationID={matched_request.citation_id} "
                    f"for URL={familysearch_url}"
                )
                return matched_request.citation_id
            else:
                logger.warning(
                    f"No pending request found for URL: {familysearch_url} "
                    f"(normalized: {normalized_url})"
                )
                return None

    def get_pending_count(self) -> int:
        """Get count of pending requests."""
        with self._lock:
            self._load_from_file()
            return len(self._pending_requests)


# Global singleton instance
_pending_request_service: PendingRequestService | None = None


def get_pending_request_service() -> PendingRequestService:
    """
    Get the global pending request service instance.

    Returns:
        PendingRequestService singleton instance
    """
    global _pending_request_service
    if _pending_request_service is None:
        _pending_request_service = PendingRequestService()
    return _pending_request_service
