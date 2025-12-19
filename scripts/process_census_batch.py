#!/usr/bin/env python3
"""
Generic Census Batch Processing Script

Processes census events for any year, extracting citation data, downloading images,
and updating database records. Generates detailed Markdown logs.

Usage:
    python3 process_census_batch.py [year] [limit]

Examples:
    python3 process_census_batch.py 1940 10    # Process 10 1940 census events
    python3 process_census_batch.py 1950 5     # Process 5 1950 census events
    python3 process_census_batch.py 1940       # Process 10 1940 census events (default)
"""
import asyncio
import sqlite3
import sys
import xml.etree.ElementTree as ET
import re
from pathlib import Path
from datetime import datetime
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from src.rmcitecraft.services.familysearch_automation import FamilySearchAutomation
from src.rmcitecraft.services.image_processing import ImageProcessingService
from src.rmcitecraft.models.image import ImageMetadata
from src.rmcitecraft.validation.data_quality import validate_before_update, is_citation_needs_processing
from src.rmcitecraft.parsers.source_name_parser import augment_citation_data_from_source
from src.rmcitecraft.database.connection import connect_rmtree


def retrieve_formatted_citations(citation_id: int, db_path: Path, icu_path: Path) -> dict[str, str]:
    """
    Retrieve formatted citations from database after processing.

    Args:
        citation_id: RootsMagic CitationID
        db_path: Path to RootsMagic database
        icu_path: Path to ICU extension

    Returns:
        Dictionary with 'footnote', 'short_footnote', 'bibliography'
    """
    try:
        conn = connect_rmtree(str(db_path), str(icu_path))
        cursor = conn.cursor()

        # Get SourceID and TemplateID
        cursor.execute("""
            SELECT s.SourceID, s.TemplateID, s.Fields
            FROM CitationTable c
            JOIN SourceTable s ON c.SourceID = s.SourceID
            WHERE c.CitationID = ?
        """, (citation_id,))

        row = cursor.fetchone()
        if not row:
            return {'footnote': '(Not found)', 'short_footnote': '(Not found)', 'bibliography': '(Not found)'}

        source_id, template_id, fields_blob = row

        # For free-form sources (TemplateID=0), parse SourceTable.Fields BLOB
        if template_id == 0 and fields_blob:
            fields_str = fields_blob.decode('utf-8') if isinstance(fields_blob, bytes) else fields_blob
            root = ET.fromstring(fields_str)
            footnote_elem = root.find('.//Field[Name="Footnote"]/Value')
            short_elem = root.find('.//Field[Name="ShortFootnote"]/Value')
            bib_elem = root.find('.//Field[Name="Bibliography"]/Value')

            conn.close()
            return {
                'footnote': footnote_elem.text if footnote_elem is not None and footnote_elem.text else '(Empty)',
                'short_footnote': short_elem.text if short_elem is not None and short_elem.text else '(Empty)',
                'bibliography': bib_elem.text if bib_elem is not None and bib_elem.text else '(Empty)'
            }

        conn.close()
        return {'footnote': '(Template-based source)', 'short_footnote': '(Template-based source)', 'bibliography': '(Template-based source)'}

    except Exception as e:
        return {'footnote': f'(Error: {e})', 'short_footnote': f'(Error: {e})', 'bibliography': f'(Error: {e})'}


class MarkdownLogger:
    """Generates detailed Markdown logs for census processing."""

    def __init__(self, census_year: int, output_dir: Path = Path('./logs')):
        self.census_year = census_year
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = self.output_dir / f"census_batch_{census_year}_{timestamp}.md"
        self.entries = []
        self.start_time = datetime.now()

    def add_entry(self, entry_data: dict[str, Any]):
        """Add a processed entry to the log."""
        self.entries.append(entry_data)

    def write_log(self):
        """Write the complete Markdown log file."""
        with open(self.log_file, 'w') as f:
            # Header
            f.write(f"# Census Batch Processing Report\n\n")
            f.write(f"**Census Year:** {self.census_year}  \n")
            f.write(f"**Date:** {self.start_time.strftime('%B %d, %Y at %I:%M %p')}  \n")
            f.write(f"**Total Entries:** {len(self.entries)}  \n\n")

            # Summary statistics
            successful = sum(1 for e in self.entries if e['success'])
            failed = len(self.entries) - successful
            existing_media = sum(1 for e in self.entries if e.get('had_existing_media'))
            new_media = sum(1 for e in self.entries if e['success'] and not e.get('had_existing_media'))

            f.write(f"## Summary\n\n")
            f.write(f"- ✅ **Successful:** {successful}\n")
            f.write(f"- ❌ **Failed:** {failed}\n")
            f.write(f"- 📷 **New Images:** {new_media}\n")
            f.write(f"- 📋 **Existing Media (Citations Updated):** {existing_media}\n\n")

            f.write("---\n\n")

            # Detailed entries
            for i, entry in enumerate(self.entries, 1):
                self._write_entry(f, i, entry)

            # Footer
            end_time = datetime.now()
            duration = (end_time - self.start_time).total_seconds()
            f.write(f"\n---\n\n")
            f.write(f"**Processing completed in {duration:.1f} seconds**\n")

        print(f"\n✓ Detailed log written to: {self.log_file}")

    def _write_entry(self, f, index: int, entry: dict[str, Any]):
        """Write a single entry to the log."""
        status_icon = "✅" if entry['success'] else "❌"

        f.write(f"## {index}. {status_icon} {entry['full_name']}\n\n")

        # Person details
        f.write(f"**Person ID:** {entry['person_id']}  \n")
        f.write(f"**Citation ID:** {entry['citation_id']}  \n")
        f.write(f"**Event ID:** {entry['event_id']}  \n")
        f.write(f"**Location:** {entry.get('county', 'Unknown')}, {entry.get('state', 'Unknown')}  \n\n")

        # Image status
        if entry.get('had_existing_media') and entry['success']:
            f.write(f"**Image Status:** ⚠️ Existing media found  \n")
            if entry.get('existing_files'):
                f.write(f"**Existing File:** `{entry['existing_files']}`  \n")
            f.write(f"**Action:** Citation fields updated (image processing skipped)  \n\n")
        elif entry['success'] and entry.get('media_id'):
            f.write(f"**Image Status:** ✅ New image downloaded and attached  \n")
            f.write(f"**Media ID:** {entry['media_id']}  \n")
            f.write(f"**File:** `{entry.get('filename', 'N/A')}`  \n")
            f.write(f"**Path:** `{entry.get('final_path', 'N/A')}`  \n\n")
        else:
            # Failed processing - show error details
            if entry.get('had_existing_media'):
                f.write(f"**Image Status:** ⚠️ Existing media found, but update failed  \n")
                if entry.get('existing_files'):
                    f.write(f"**Existing File:** `{entry['existing_files']}`  \n")
            else:
                f.write(f"**Image Status:** ❌ Failed to process  \n")

            if entry.get('error'):
                f.write(f"**Error:** {entry['error']}  \n")

            # Show validation errors if present
            if entry.get('validation_errors'):
                f.write(f"\n**Validation Errors:**\n")
                for error in entry['validation_errors']:
                    f.write(f"- {error}\n")
                f.write("\n")

            # Show validation warnings if present
            if entry.get('validation_warnings'):
                f.write(f"**Validation Warnings:**\n")
                for warning in entry['validation_warnings']:
                    f.write(f"- {warning}\n")
                f.write("\n")

        # Formatted citations (if successful)
        if entry['success'] and entry.get('citations'):
            f.write(f"### Formatted Citations\n\n")

            citations = entry['citations']

            f.write(f"#### Footnote\n")
            f.write(f"```\n{citations.get('footnote', 'N/A')}\n```\n\n")

            f.write(f"#### Short Footnote\n")
            f.write(f"```\n{citations.get('short_footnote', 'N/A')}\n```\n\n")

            f.write(f"#### Bibliography\n")
            f.write(f"```\n{citations.get('bibliography', 'N/A')}\n```\n\n")

        # FamilySearch URL
        if entry.get('familysearch_url'):
            f.write(f"**FamilySearch URL:** [{entry['familysearch_url']}]({entry['familysearch_url']})  \n\n")

        f.write("---\n\n")


def find_census_citations(
    db_path: str,
    census_year: int,
    limit: int = 10,
    offset: int = 0,
    exclude_processed: bool = True
):
    """Find census events for specified year by parsing SourceTable.Fields BLOB.

    Args:
        db_path: Path to RootsMagic database
        census_year: Census year to search for (e.g., 1940, 1950)
        limit: Maximum number of citations to return
        offset: Number of citations to skip (for pagination)
        exclude_processed: If True, excludes citations that have already been properly
            processed. A citation is considered processed if:
            1. Footnote != ShortFootnote (they differ after processing)
            2. All three citation forms (Footnote, ShortFootnote, Bibliography)
               pass validation for essential elements

    Returns:
        dict with keys:
            - 'citations': list of citation dicts
            - 'examined': number of citations examined
            - 'found': number with FamilySearch URLs
            - 'excluded': number without FamilySearch URLs
            - 'skipped_processed': number skipped because already processed
    """
    # Load ICU extension
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    conn.load_extension('./sqlite-extension/icu.dylib')
    conn.execute("SELECT icu_load_collation('en_US@colStrength=primary;caseLevel=off;normalization=on','RMNOCASE')")
    conn.enable_load_extension(False)

    cursor = conn.cursor()

    # Find ALL census events for specified year (regardless of existing media).
    #
    # MEDIA EXISTENCE CHECK: Census images in RootsMagic can be linked to any of three
    # entity types via MediaLinkTable.OwnerType:
    #   - Event (OwnerType=2): The census event itself
    #   - Source (OwnerType=3): The source document (most common for Evidence Explained practice)
    #   - Citation (OwnerType=4): The specific citation
    #
    # To avoid downloading duplicate images, we must check ALL THREE link types.
    # Previously, only Event links were checked, which could miss images linked
    # only to the Source or Citation, resulting in duplicate downloads.
    #
    # The subqueries check for media linked to ANY of the three related entities
    # (the event, its citation's source, or the citation itself).
    query = """
        SELECT
            e.EventID, e.OwnerID as PersonID, n.Given, n.Surname,
            c.CitationID, s.SourceID, s.Name as SourceName,
            s.Fields, c.Fields as CitationFields,
            -- Count distinct media IDs linked to Event, Source, OR Citation
            (
                SELECT COUNT(DISTINCT ml.MediaID)
                FROM MediaLinkTable ml
                WHERE (ml.OwnerID = e.EventID AND ml.OwnerType = 2)      -- Event
                   OR (ml.OwnerID = s.SourceID AND ml.OwnerType = 3)     -- Source
                   OR (ml.OwnerID = c.CitationID AND ml.OwnerType = 4)   -- Citation
            ) as existing_media_count,
            -- Get filenames from all three link types (using ||| delimiter since filenames may contain commas)
            (
                SELECT GROUP_CONCAT(m.MediaFile, '|||')
                FROM MediaLinkTable ml
                JOIN MultimediaTable m ON ml.MediaID = m.MediaID
                WHERE (ml.OwnerID = e.EventID AND ml.OwnerType = 2)
                   OR (ml.OwnerID = s.SourceID AND ml.OwnerType = 3)
                   OR (ml.OwnerID = c.CitationID AND ml.OwnerType = 4)
            ) as existing_files,
            -- Get media paths from all three link types
            (
                SELECT GROUP_CONCAT(m.MediaPath, '|||')
                FROM MediaLinkTable ml
                JOIN MultimediaTable m ON ml.MediaID = m.MediaID
                WHERE (ml.OwnerID = e.EventID AND ml.OwnerType = 2)
                   OR (ml.OwnerID = s.SourceID AND ml.OwnerType = 3)
                   OR (ml.OwnerID = c.CitationID AND ml.OwnerType = 4)
            ) as existing_media_paths
        FROM EventTable e
        JOIN NameTable n ON e.OwnerID = n.OwnerID AND n.IsPrimary = 1
        JOIN CitationLinkTable cl ON e.EventID = cl.OwnerID AND cl.OwnerType = 2
        JOIN CitationTable c ON cl.CitationID = c.CitationID
        JOIN SourceTable s ON c.SourceID = s.SourceID
        WHERE e.EventType = 18
          AND e.Date LIKE ?
          AND s.TemplateID = 0
        GROUP BY e.EventID
        ORDER BY n.Surname COLLATE RMNOCASE, n.Given COLLATE RMNOCASE
        LIMIT ? OFFSET ?
    """

    results = []
    examined = 0
    excluded = 0
    skipped_processed = 0

    # Initialize media path resolver
    from src.rmcitecraft.utils.media_resolver import MediaPathResolver
    from src.rmcitecraft.config import Config
    config = Config()
    media_resolver = MediaPathResolver(
        media_root=str(config.rm_media_root_directory),
        database_path=db_path
    )

    # Fetch in batches until we have enough unprocessed records
    # This handles the case where many records at the start are already processed
    batch_size = max(limit * 5, 100)  # Fetch larger batches to find unprocessed records
    current_offset = offset
    max_iterations = 20  # Safety limit to prevent infinite loops

    for iteration in range(max_iterations):
        cursor.execute(query, (f'%{census_year}%', batch_size, current_offset))
        rows = cursor.fetchall()

        if not rows:
            # No more records in database
            break

        for row in rows:
            examined += 1
            event_id, person_id, given, surname, citation_id, source_id, source_name, fields_blob, citation_fields_blob, existing_media_count, existing_files, existing_media_paths = row

            # Parse SourceTable.Fields BLOB for Footnote with FamilySearch URL
            familysearch_url = None

            if fields_blob:
                try:
                    fields_str = fields_blob.decode('utf-8') if isinstance(fields_blob, bytes) else fields_blob
                    root = ET.fromstring(fields_str)
                    footnote_elem = root.find('.//Field[Name="Footnote"]/Value')
                    if footnote_elem is not None and footnote_elem.text:
                        footnote = footnote_elem.text
                        if 'familysearch.org' in footnote.lower():
                            url_match = re.search(r'https?://(?:www\.)?familysearch\.org[^\s)>]+', footnote, re.IGNORECASE)
                            if url_match:
                                familysearch_url = url_match.group(0).rstrip('.,;')
                except Exception:
                    pass

            # Also check CitationTable.Fields for Page field
            if not familysearch_url and citation_fields_blob:
                try:
                    citation_fields_str = citation_fields_blob.decode('utf-8') if isinstance(citation_fields_blob, bytes) else citation_fields_blob
                    root = ET.fromstring(citation_fields_str)
                    page_elem = root.find('.//Field[Name="Page"]/Value')
                    if page_elem is not None and page_elem.text:
                        page_text = page_elem.text
                        if 'familysearch.org' in page_text.lower():
                            url_match = re.search(r'https?://(?:www\.)?familysearch\.org[^\s)>]+', page_text, re.IGNORECASE)
                            if url_match:
                                familysearch_url = url_match.group(0).rstrip('.,;')
                except Exception:
                    pass

            if familysearch_url:
                # Resolve media path to absolute path if existing media
                existing_image_path = None
                if existing_media_count > 0 and existing_files and existing_media_paths:
                    # Take first media file and path (if multiple, use first)
                    # Use ||| delimiter since filenames contain commas
                    media_file = existing_files.split('|||')[0] if existing_files else None
                    media_path = existing_media_paths.split('|||')[0] if existing_media_paths else None

                    if media_file and media_path:
                        resolved_path = media_resolver.resolve(media_path, media_file)
                        if resolved_path:
                            existing_image_path = str(resolved_path)

                # Read formatted citations from SourceTable.Fields if they exist
                footnote = None
                short_footnote = None
                bibliography = None

                if fields_blob:
                    try:
                        fields_str = fields_blob.decode('utf-8') if isinstance(fields_blob, bytes) else fields_blob
                        root = ET.fromstring(fields_str)
                        footnote_elem = root.find('.//Field[Name="Footnote"]/Value')
                        short_elem = root.find('.//Field[Name="ShortFootnote"]/Value')
                        bib_elem = root.find('.//Field[Name="Bibliography"]/Value')

                        if footnote_elem is not None and footnote_elem.text:
                            footnote = footnote_elem.text
                        if short_elem is not None and short_elem.text:
                            short_footnote = short_elem.text
                        if bib_elem is not None and bib_elem.text:
                            bibliography = bib_elem.text
                    except Exception:
                        pass

                # Apply filtering criteria 5 & 6: exclude already-processed citations
                if exclude_processed:
                    needs_processing = is_citation_needs_processing(
                        footnote=footnote,
                        short_footnote=short_footnote,
                        bibliography=bibliography,
                        census_year=census_year
                    )

                    # Also check if Source Name has empty brackets [] - indicates incomplete processing
                    # even if the citation text passes validation (may have template with empty values)
                    has_empty_brackets = source_name and '[]' in source_name

                    if not needs_processing and not has_empty_brackets:
                        # Citation is already properly processed, skip it
                        skipped_processed += 1
                        continue

                results.append({
                    'event_id': event_id,
                    'person_id': person_id,
                    'given_name': given or '',
                    'surname': surname or '',
                    'full_name': f"{given or ''} {surname or ''}".strip(),
                    'citation_id': citation_id,
                    'source_id': source_id,
                    'source_name': source_name,
                    'familysearch_url': familysearch_url,
                    'has_existing_media': existing_media_count > 0,
                    'existing_files': existing_files,
                    'existing_image_path': existing_image_path,
                    'footnote': footnote,
                    'short_footnote': short_footnote,
                    'bibliography': bibliography,
                    'census_year': census_year,
                })
            else:
                excluded += 1

            if len(results) >= limit:
                break

        # Check if we have enough results or no more records
        if len(results) >= limit:
            break

        # Move offset for next batch
        current_offset += batch_size

    conn.close()

    return {
        'citations': results,
        'examined': examined,
        'found': len(results),
        'excluded': excluded,
        'skipped_processed': skipped_processed
    }


async def process_census_entry(
    entry: dict,
    automation: FamilySearchAutomation,
    image_service: ImageProcessingService,
    temp_dir: Path,
    census_year: int,
    md_logger: MarkdownLogger,
    db_path: Path,
    icu_path: Path
) -> dict[str, Any]:
    """Process a single census entry and return results for logging."""

    log_entry = {
        'success': False,
        'person_id': entry['person_id'],
        'event_id': entry['event_id'],
        'citation_id': entry['citation_id'],
        'full_name': entry['full_name'],
        'had_existing_media': entry['has_existing_media'],
        'existing_files': entry.get('existing_files'),
        'familysearch_url': entry['familysearch_url']
    }

    print(f"\n{'='*80}")
    print(f"Processing: {entry['full_name']}")
    print(f"EventID: {entry['event_id']} | PersonID: {entry['person_id']} | CitationID: {entry['citation_id']}")

    if entry['has_existing_media']:
        print(f"⚠️  Existing Media: {entry['existing_files']}")
        print(f"   (Will skip download but update citation fields)")
    else:
        print(f"○  No existing media (Will download and attach)")

    print(f"{'='*80}")

    familysearch_url = entry['familysearch_url']
    print(f"FamilySearch URL: {familysearch_url}")

    download_path = temp_dir / f"census_{entry['citation_id']}.jpg"

    try:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Extracting citation data...")

        if entry['has_existing_media']:
            citation_data = await automation.extract_citation_data(familysearch_url)
        else:
            citation_data = await automation.extract_and_download(familysearch_url, str(download_path))

        if not citation_data:
            log_entry['error'] = "Failed to extract citation data"
            print("❌ Failed to extract citation data")
            return log_entry

        state = citation_data.get('state', '')
        county = citation_data.get('county', '')

        # Apply fallback parser if extraction failed
        if not state or not county:
            print(f"⚠️  Extraction incomplete (state='{state}', county='{county}')")
            print(f"   Attempting fallback from SourceTable.Name...")
            citation_data = augment_citation_data_from_source(citation_data, entry['source_name'])
            state = citation_data.get('state', '')
            county = citation_data.get('county', '')
            if state and county:
                print(f"✓ Fallback successful: {state}, {county}")

        log_entry['state'] = state
        log_entry['county'] = county

        print(f"✓ Extracted: {state}, {county}")

        # Validate data quality before proceeding
        validation = validate_before_update(citation_data, census_year)
        if not validation:
            print("\n❌ Data quality validation FAILED:")
            print(validation.summary())
            for error in validation.errors:
                print(f"   - {error}")
            log_entry['error'] = 'Data quality validation failed'
            log_entry['validation_errors'] = validation.errors
            log_entry['validation_warnings'] = validation.warnings
            return log_entry

        # Show validation warnings (non-blocking)
        if validation.warnings:
            print("\n⚠️  Data quality warnings:")
            for warning in validation.warnings:
                print(f"   - {warning}")

        # Generate metadata
        image_id = f"{census_year}_{state}_{county}_{entry['surname']}_{entry['given_name']}"
        access_date = datetime.now().strftime('%d %B %Y')

        metadata = ImageMetadata(
            image_id=image_id,
            citation_id=str(entry['citation_id']),
            year=census_year,
            state=state,
            county=county,
            surname=entry['surname'],
            given_name=entry['given_name'],
            familysearch_url=citation_data.get('arkUrl', familysearch_url),
            access_date=access_date,
            town_ward=citation_data.get('townWard'),
            enumeration_district=citation_data.get('enumerationDistrict'),
            sheet=citation_data.get('sheet'),
            line=citation_data.get('line'),
            family_number=citation_data.get('familyNumber'),
            dwelling_number=citation_data.get('dwellingNumber'),
            familysearch_name=citation_data.get('personName')
        )

        if entry['has_existing_media']:
            # Update citation fields only
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Updating citation fields...")
            success = image_service.update_citation_fields_only(metadata)

            if success:
                print(f"✓ Citation fields updated (Footnote, ShortFootnote, Bibliography)")
                log_entry['success'] = True
                # Retrieve actual formatted citations from database
                log_entry['citations'] = retrieve_formatted_citations(
                    entry['citation_id'],
                    db_path,
                    icu_path
                )
            else:
                log_entry['error'] = "Failed to update citation fields"
                print(f"❌ Failed to update citation fields")
        else:
            # Download and process image
            print(f"✓ Image Downloaded: {download_path.exists()}")

            if not download_path.exists():
                log_entry['error'] = "Image file not found after download"
                print("❌ Image file not found after download")
                return log_entry

            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Processing image...")
            image_service.register_pending_image(metadata)
            result = image_service.process_downloaded_file(str(download_path))

            if result:
                log_entry['success'] = True
                log_entry['media_id'] = result.media_id
                log_entry['filename'] = result.final_filename
                log_entry['final_path'] = str(result.final_path) if result.final_path else None
                # Retrieve actual formatted citations from database
                log_entry['citations'] = retrieve_formatted_citations(
                    entry['citation_id'],
                    db_path,
                    icu_path
                )
                print(f"✓ MediaID: {result.media_id}")
                print(f"✓ Final Path: {result.final_path}")
            else:
                log_entry['error'] = "Failed to process image"
                print("❌ Failed to process image")

        return log_entry

    except Exception as e:
        log_entry['error'] = str(e)
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return log_entry


async def main():
    # Parse command-line arguments
    if len(sys.argv) < 2:
        print("Usage: python3 process_census_batch.py [year] [limit] [offset]")
        print("Example: python3 process_census_batch.py 1940 10")
        print("Example: python3 process_census_batch.py 1940 10 7  # Start at entry 8 (skip first 7)")
        sys.exit(1)

    census_year = int(sys.argv[1])
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    offset = int(sys.argv[3]) if len(sys.argv) > 3 else 0

    db_path = Path('./data/Iiams.rmtree')
    temp_dir = Path('./temp_downloads')
    temp_dir.mkdir(exist_ok=True)

    icu_path = Path('./sqlite-extension/icu.dylib')
    media_root = Path('/Users/miams/Genealogy/RootsMagic/Files')

    print("\n" + "="*80)
    print(f"{census_year} CENSUS BATCH PROCESSING")
    if offset > 0:
        print(f"Starting at entry {offset + 1} (skipping first {offset})")
    print("="*80)

    # Find citations
    print(f"\nFinding {census_year} census events...")
    result = find_census_citations(str(db_path), census_year, limit=limit, offset=offset)

    if not result['citations']:
        print("❌ No citations found")
        return

    citations = result['citations']
    examined = result['examined']
    found = result['found']
    excluded = result['excluded']
    skipped_processed = result.get('skipped_processed', 0)

    # Count media status
    with_media = sum(1 for c in citations if c['has_existing_media'])
    without_media = len(citations) - with_media

    print(f"✓ Found {found} events needing processing")
    if excluded > 0 or skipped_processed > 0:
        details = []
        if excluded > 0:
            details.append(f"{excluded} without FamilySearch URLs")
        if skipped_processed > 0:
            details.append(f"{skipped_processed} already processed")
        print(f"  (Examined {examined} citations, excluded: {', '.join(details)})")
    print(f"  - {with_media} with existing media (will update citations only)")
    print(f"  - {without_media} without media (will download and attach)")

    print("\nEntries to process:")
    for i, entry in enumerate(citations, 1):
        status = "⚠️" if entry['has_existing_media'] else "○"
        print(f"  {i}. {status} {entry['full_name']} (EventID: {entry['event_id']})")

    # Initialize services
    automation = FamilySearchAutomation()
    image_service = ImageProcessingService(
        db_path=db_path,
        icu_extension_path=icu_path,
        media_root=media_root
    )

    # Initialize Markdown logger
    md_logger = MarkdownLogger(census_year)

    successful = 0
    failed = 0

    for i, entry in enumerate(citations, 1):
        print(f"\n\n{'#'*80}")
        print(f"# ENTRY {i}/{len(citations)}")
        print(f"{'#'*80}")

        log_entry = await process_census_entry(entry, automation, image_service, temp_dir, census_year, md_logger, db_path, icu_path)
        md_logger.add_entry(log_entry)

        if log_entry['success']:
            successful += 1
        else:
            failed += 1

        # Small delay between entries
        if i < len(citations):
            print(f"\nWaiting 2 seconds before next entry...")
            await asyncio.sleep(2)

    print(f"\n\n{'='*80}")
    print("SUMMARY")
    print("="*80)
    print(f"Processed: {len(citations)} entries")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")

    print(f"\nDetails:")
    for i, entry in enumerate(citations, 1):
        status = "✅" if md_logger.entries[i-1]['success'] else "❌"
        print(f"  {i}. {status} {entry['full_name']}")

    print("="*80)
    print("BATCH COMPLETE")
    print("="*80 + "\n")

    # Write Markdown log
    md_logger.write_log()


if __name__ == '__main__':
    asyncio.run(main())
