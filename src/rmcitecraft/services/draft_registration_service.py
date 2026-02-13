"""Draft registration automation service.

This orchestrates the Playwright-powered workflows for:
- Discovering AncestryLibrary URLs for FamilySearch records
- Scraping metadata from Ancestry (ALWAYS - superior data quality)
- Downloading images from FamilySearch (preferred) or Ancestry (fallback)
- Persisting metadata in ww2-draft.db with Ancestry URLs

SOURCE HIERARCHY:
- Metadata: ALWAYS Ancestry (never FamilySearch)
- Images: FamilySearch preferred, Ancestry fallback
- Citations: FamilySearch preferred, Ancestry fallback

The service is asynchronous because it relies on Playwright CDP connections.
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, Iterable, Optional

from loguru import logger

from rmcitecraft.config import get_config
from rmcitecraft.database.draft_registration_db import (
    DraftRegistration,
    DraftRegistrationRepository,
    get_draft_repository,
)
from rmcitecraft.models.draft_record import DraftRecord
from rmcitecraft.models.draft_registration import (
    DraftAutomationBatchResult,
    DraftAutomationOptions,
    DraftAutomationRecordResult,
    ProgressCallback,
)
from rmcitecraft.services.ancestry_url_discoverer import AncestryUrlDiscoverer
from rmcitecraft.services.ancestrylibrary_draft_scraper import AncestryLibraryDraftScraper
from rmcitecraft.services.familysearch_draft_scraper import FamilySearchDraftScraper

# URL extraction patterns
# _URL_RE: Matches complete URLs starting with http:// or https://
_URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
# _ARK_RE: Matches FamilySearch ARK identifiers (e.g., ark:/61903/1:1:ABCD-123 or ark:/61903/3:1:EFGH-456)
# Format: ark:/61903/[1 or 3]:[sequence number]:[identifier with uppercase letters, numbers, and hyphens]
_ARK_RE = re.compile(r"ark:/61903/[13]:[0-9]:[A-Z0-9-]+", re.IGNORECASE)


class DraftRegistrationService:
    """High-level automation service for draft registration scraping."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        download_dir: Optional[Path] = None,
    ):
        cfg = get_config()
        self.db_path = Path(db_path or cfg.draft_metadata_db_path).expanduser()
        self.download_dir = Path(download_dir or cfg.draft_download_dir).expanduser()
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.repository: DraftRegistrationRepository = get_draft_repository(self.db_path)
        self.familysearch_scraper = FamilySearchDraftScraper(download_dir=self.download_dir)
        self.ancestry_scraper = AncestryLibraryDraftScraper()  # Gets config from settings
        self.url_discoverer = AncestryUrlDiscoverer()

        self._fs_connected = False
        self._ancestry_connected = False
        self._discovery_connected = False

        self._batch_id: Optional[int] = None

    async def run_batch(
        self,
        records: Iterable[DraftRecord],
        options: Optional[DraftAutomationOptions] = None,
        progress_callback: ProgressCallback = None,
        stop_event: Optional[asyncio.Event] = None,
    ) -> DraftAutomationBatchResult:
        """Process a batch of records asynchronously."""
        logger.info("🚀 DraftRegistrationService.run_batch() called")
        logger.info("⚙️  WORKFLOW OPTIONS:")
        logger.info(f"    • Discover Ancestry URLs: {options.discover_ancestry_urls if options else None}")
        logger.info(f"    • Process FamilySearch: {options.process_familysearch if options else None}")
        logger.info(f"    • Process Ancestry: {options.process_ancestry if options else None}")
        logger.info(f"    • Ancestry Metadata Only: {options.ancestry_metadata_only if options else None}")
        logger.info(f"    • Max Records: {options.max_records if options else None}")

        options = options or DraftAutomationOptions()
        records_list = list(records)
        logger.info(f"📋 Processing {len(records_list)} records")

        result = DraftAutomationBatchResult(total_records=len(records_list))
        target_limit = options.max_records if options.max_records and options.max_records > 0 else None
        progress_total = target_limit or len(records_list)
        non_skipped_processed = 0

        if not records_list:
            logger.warning("No records to process")
            return result

        logger.info(f"Starting record processing loop (target_limit={target_limit})")

        try:
            for idx, record in enumerate(records_list, start=1):
                if stop_event and stop_event.is_set():
                    result.cancelled = True
                    break

                record_result = await self._process_record(record, options)
                result.add_result(record_result)

                if not record_result.skipped:
                    non_skipped_processed += 1

                progress_current = (
                    min(non_skipped_processed, progress_total)
                    if target_limit
                    else min(idx, progress_total)
                )
                progress_message = self._format_progress_message(
                    record,
                    record_result,
                    non_skipped_processed,
                    target_limit,
                )
                await self._emit_progress(
                    progress_callback,
                    progress_current,
                    progress_total,
                    progress_message,
                )

                if target_limit and non_skipped_processed >= target_limit:
                    result.limit_reached = True
                    break
        finally:
            await self._disconnect()

        return result

    async def _process_record(
        self,
        record: DraftRecord,
        options: DraftAutomationOptions,
    ) -> DraftAutomationRecordResult:
        logger.debug(f"Processing record: {record.full_name} (row {record.row_number})")
        record_result = DraftAutomationRecordResult(record=record)
        citation_text = record.familysearch_citation or ""
        citation_lower = citation_text.lower()

        has_familysearch = "familysearch.org" in citation_lower or "ark:/" in citation_lower
        # Check BOTH citation text AND ancestry_url spreadsheet column
        has_ancestry = ("ancestrylibrary.com" in citation_lower) or bool(record.ancestry_url and record.ancestry_url.strip())
        logger.debug(f"  has_familysearch={has_familysearch}, has_ancestry={has_ancestry}, discover={options.discover_ancestry_urls}")

        # Skip only if no URLs AND discovery is disabled
        if not has_familysearch and not has_ancestry and not options.discover_ancestry_urls:
            record_result.skipped = True
            record_result.skip_reason = "No supported URL found in citation and discovery disabled"
            return record_result

        # Allow discovery to run even if process_familysearch=False, as long as discover_ancestry_urls=True
        if has_familysearch and not has_ancestry and not options.process_familysearch and not options.discover_ancestry_urls:
            record_result.skipped = True
            record_result.skip_reason = "FamilySearch processing and discovery both disabled"
            return record_result

        if has_ancestry and not options.process_ancestry:
            record_result.skipped = True
            record_result.skip_reason = "Ancestry processing disabled"
            return record_result

        # Run discovery if enabled and we don't already have an Ancestry URL
        if options.discover_ancestry_urls and not has_ancestry:
            logger.info(f"🔍 Discovering Ancestry URL for {record.full_name}...")
            record_result.discovered_ancestry_url = await self._discover_ancestry_url(
                record,
                confirmation_callback=options.ancestry_url_confirmation_callback,
            )
            if record_result.discovered_ancestry_url:
                logger.info(f"✅ Discovered: {record_result.discovered_ancestry_url}")
            else:
                logger.info("❌ No Ancestry URL found")

        # If we have an Ancestry URL (either in citation, ancestry_url column, or discovered), process via Ancestry
        if has_ancestry or record_result.discovered_ancestry_url:
            record_result.source_type = "ancestrylibrary"
            # Priority: ancestry_url column > citation text > discovered URL
            ancestry_url = (
                record.ancestry_url.strip() if record.ancestry_url and record.ancestry_url.strip()
                else self._extract_ancestry_url(citation_text) if has_ancestry
                else record_result.discovered_ancestry_url
            )
            if not ancestry_url:
                record_result.skipped = True
                record_result.skip_reason = "Unable to extract Ancestry URL"
                return record_result
            return await self._process_ancestry(record_result, ancestry_url, options)

        # Only process via FamilySearch if no Ancestry URL available
        if has_familysearch:
            record_result.source_type = "familysearch"
            fs_url = self._extract_familysearch_url(citation_text)
            if not fs_url:
                record_result.skipped = True
                record_result.skip_reason = "Unable to extract FamilySearch URL"
                return record_result
            return await self._process_familysearch(record_result, fs_url, options)

        record_result.skipped = True
        record_result.skip_reason = "Citation did not match supported workflows"
        return record_result

    async def _process_familysearch(
        self,
        record_result: DraftAutomationRecordResult,
        url: str,
        options: DraftAutomationOptions,
    ) -> DraftAutomationRecordResult:
        if not await self._ensure_familysearch_connected():
            record_result.message = "Failed to connect to Chrome for FamilySearch"
            return record_result

        try:
            # Pass RIN for proper file naming
            rin = record_result.record.rin if record_result.record else None
            registration, image_path = await self.familysearch_scraper.scrape_and_download(
                url, rin=rin, metadata_only=options.ancestry_metadata_only
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(f"FamilySearch scraping failed: {exc}", exc_info=True)
            record_result.message = str(exc)
            return record_result

        if not registration:
            record_result.message = "FamilySearch scraping returned no data"
            return record_result

        # If Ancestry URL was discovered, add it to the registration
        if record_result.discovered_ancestry_url:
            registration.ancestry_url = record_result.discovered_ancestry_url
            logger.info(f"Added discovered Ancestry URL: {registration.ancestry_url}")

        registration.batch_id = self._get_batch_id()
        registration.extracted_at = datetime.now(timezone.utc).isoformat()
        if image_path:
            registration.image_downloaded = 1
            registration.image_file_path = str(image_path)

        registration_id = self.repository.insert_registration(registration)

        record_result.registration_id = registration_id
        record_result.image_path = str(image_path) if image_path else None
        record_result.source_type = registration.source_type
        record_result.success = True
        record_result.message = "FamilySearch metadata stored"
        return record_result

    async def _process_ancestry(
        self,
        record_result: DraftAutomationRecordResult,
        url: str,
        options: DraftAutomationOptions,
    ) -> DraftAutomationRecordResult:
        if not await self._ensure_ancestry_connected():
            record_result.message = "Failed to connect to Chrome for AncestryLibrary"
            return record_result

        try:
            # Pass RIN for proper file naming
            rin = record_result.record.rin if record_result.record else None
            registration, image_path = await self.ancestry_scraper.scrape_and_download(
                url, rin=rin, metadata_only=options.ancestry_metadata_only
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(f"Ancestry scraping failed: {exc}", exc_info=True)
            record_result.message = str(exc)
            return record_result

        if not registration:
            record_result.message = "Ancestry scraping returned no data"
            return record_result

        registration.batch_id = self._get_batch_id()
        registration.extracted_at = datetime.now(timezone.utc).isoformat()
        if image_path:
            registration.image_downloaded = 1
            registration.image_file_path = str(image_path)

        registration_id = self.repository.insert_registration(registration)

        record_result.registration_id = registration_id
        record_result.image_path = str(image_path) if image_path else None
        record_result.source_type = registration.source_type
        record_result.success = True
        record_result.message = "Ancestry metadata stored"
        return record_result

    async def _discover_ancestry_url(
        self,
        record: DraftRecord,
        confirmation_callback: Optional[Callable[[str, str, int], Awaitable[bool]]] = None,
    ) -> Optional[str]:
        """Run Ancestry URL discovery for a record."""
        logger.debug(f"  _discover_ancestry_url called for {record.full_name}")

        logger.debug("  Ensuring discovery connection...")
        if not await self._ensure_discovery_connected():
            logger.warning("  Failed to connect for discovery")
            return None

        if not (record.given_name and record.surname and record.birth_year):
            logger.debug("  Missing name or birth year, skipping discovery")
            return None

        try:
            logger.debug(f"  Searching Ancestry for {record.given_name} {record.surname} (b.{record.birth_year})")
            discovered_url = await self.url_discoverer.search_and_get_url(
                first_middle_name=record.given_name,
                last_name=record.surname,
                birth_year=record.birth_year,
            )
            logger.debug(f"  Search completed, result: {discovered_url}")

            if not discovered_url:
                return None

            # If confirmation callback provided, ask user to confirm
            if confirmation_callback:
                confirmed = await confirmation_callback(record.full_name, discovered_url, record.rin)
                if not confirmed:
                    logger.info(f"User declined Ancestry URL for {record.full_name}")
                    return None

            return discovered_url

        except Exception as exc:  # pragma: no cover - Playwright safety
            logger.error(f"Ancestry URL discovery failed: {exc}", exc_info=True)
            return None

    async def _ensure_familysearch_connected(self) -> bool:
        if self._fs_connected:
            return True
        self._fs_connected = await self.familysearch_scraper.connect()
        return self._fs_connected

    async def _ensure_ancestry_connected(self) -> bool:
        if self._ancestry_connected:
            return True
        self._ancestry_connected = await self.ancestry_scraper.connect()
        return self._ancestry_connected

    async def _ensure_discovery_connected(self) -> bool:
        if self._discovery_connected:
            logger.debug("  Already connected to discovery service")
            return True
        logger.info("  Connecting to discovery service...")
        self._discovery_connected = await self.url_discoverer.connect()
        logger.info(f"  Discovery connection result: {self._discovery_connected}")
        return self._discovery_connected

    async def _disconnect(self) -> None:
        if self._fs_connected:
            try:
                await self.familysearch_scraper.disconnect()
            finally:
                self._fs_connected = False

        if self._ancestry_connected:
            try:
                await self.ancestry_scraper.disconnect()
            finally:
                self._ancestry_connected = False

        if self._discovery_connected:
            try:
                await self.url_discoverer.disconnect()
            finally:
                self._discovery_connected = False


    def _get_batch_id(self) -> int:
        """Get or create a batch ID for this service instance."""
        if self._batch_id is not None:
            return self._batch_id

        batch_name = f"Draft batch {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        self._batch_id = self.repository.create_batch(batch_name=batch_name, notes=None)
        return self._batch_id

    @staticmethod
    def _extract_familysearch_url(text: str) -> Optional[str]:
        """Extract FamilySearch URL or ARK identifier from citation text.

        Handles two formats:
        1. Complete URLs containing 'familysearch.org' (e.g., https://familysearch.org/ark:/...)
        2. Standalone ARK identifiers (e.g., ark:/61903/1:1:ABCD-123) which are converted to full URLs

        Args:
            text: Citation text that may contain a FamilySearch URL or ARK

        Returns:
            Complete FamilySearch URL if found, None otherwise
        """
        # First try to find a complete familysearch.org URL
        for match in _URL_RE.finditer(text):
            cleaned = DraftRegistrationService._cleanup_url(match.group(0))
            if "familysearch.org" in cleaned:
                return cleaned

        # If no URL found, look for standalone ARK identifier and convert to URL
        ark_match = _ARK_RE.search(text)
        if ark_match:
            return f"https://www.familysearch.org/{ark_match.group(0)}"
        return None

    @staticmethod
    def _extract_ancestry_url(text: str) -> Optional[str]:
        for match in _URL_RE.finditer(text):
            cleaned = DraftRegistrationService._cleanup_url(match.group(0))
            if "ancestrylibrary.com" in cleaned:
                return cleaned.split("?")[0]
        return None

    @staticmethod
    def _cleanup_url(url: str) -> str:
        return url.rstrip(").,;\">'")

    @staticmethod
    def _format_progress_message(
        record: DraftRecord,
        record_result: DraftAutomationRecordResult,
        counted: int,
        limit: Optional[int],
    ) -> str:
        status = (
            "skipped"
            if record_result.skipped
            else ("error" if not record_result.success else "done")
        )
        base = f"{record.full_name} • {status}"
        if limit:
            return f"{base} ({counted}/{limit} counted)"
        return base

    async def _emit_progress(
        self,
        callback: ProgressCallback,
        current: int,
        total: int,
        message: str,
    ) -> None:
        if not callback:
            return
        try:
            maybe_coro = callback(current, total, message)
            if asyncio.iscoroutine(maybe_coro):
                await maybe_coro
        except Exception as exc:  # pragma: no cover - UI safety
            logger.warning(f"Progress callback raised an exception: {exc}")
