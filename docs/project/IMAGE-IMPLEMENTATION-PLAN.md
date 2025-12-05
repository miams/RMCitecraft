---
priority: reference
topics: [database, census, citation, batch, testing]
---

# Census Image Management - Implementation Plan

**For**: Developers
**Version**: 1.0
**Last Updated**: 2025-01-29
**Status**: Implementation Guide

## Overview

This document provides a detailed implementation plan for the Census Image Management system in RMCitecraft. It breaks down the architecture into concrete development phases with specific tasks, file locations, and code examples.

---

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)

**Goal**: Build foundation for image detection, processing, and database integration

**Estimated Time**: 5-7 days

#### Task 1.1: File Watcher Service

**Files**:
- `src/rmcitecraft/services/file_watcher.py` (new)
- `src/rmcitecraft/services/__init__.py` (update)

**Implementation**:

```python
"""File watcher service for monitoring downloads folder."""

from pathlib import Path
from typing import Callable

from loguru import logger
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class CensusImageHandler(FileSystemEventHandler):
    """Handle file system events for census images."""

    def __init__(self, callback: Callable[[Path], None]):
        """Initialize handler.

        Args:
            callback: Function to call when valid image detected
        """
        super().__init__()
        self.callback = callback
        self.valid_extensions = {'.jpg', '.jpeg', '.png', '.pdf', '.tiff', '.tif'}
        self.ignore_extensions = {'.crdownload', '.download', '.tmp', '.part'}

    def on_created(self, event):
        """Handle file creation event."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Ignore partial downloads
        if file_path.suffix.lower() in self.ignore_extensions:
            logger.debug(f"Ignoring partial download: {file_path.name}")
            return

        # Check if valid image
        if file_path.suffix.lower() in self.valid_extensions:
            logger.info(f"New image detected: {file_path.name}")
            self.callback(file_path)


class DownloadMonitor:
    """Monitor downloads folder for census images."""

    def __init__(self, downloads_dir: Path, callback: Callable[[Path], None]):
        """Initialize monitor.

        Args:
            downloads_dir: Path to downloads folder
            callback: Function to call when image detected
        """
        self.downloads_dir = downloads_dir
        self.callback = callback
        self.observer = Observer()
        self.handler = CensusImageHandler(callback)

    def start(self):
        """Start monitoring downloads folder."""
        logger.info(f"Starting download monitor: {self.downloads_dir}")
        self.observer.schedule(self.handler, str(self.downloads_dir), recursive=False)
        self.observer.start()

    def stop(self):
        """Stop monitoring."""
        logger.info("Stopping download monitor")
        self.observer.stop()
        self.observer.join()
```

**Tests**:
- `tests/unit/services/test_file_watcher.py`
- Test file creation detection
- Test partial download ignoring
- Test multiple file types

#### Task 1.2: Filename Generator

**Files**:
- `src/rmcitecraft/utils/filename_generator.py` (new)
- `tests/unit/utils/test_filename_generator.py` (new)

**Implementation**:

```python
"""Census image filename generation utilities."""

import re
from pathlib import Path


# US State abbreviations to full names
STATE_ABBREVIATIONS = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia"
}


def expand_state_abbreviation(state: str) -> str:
    """Expand state abbreviation to full name.

    Args:
        state: State abbreviation (e.g., "OK") or full name

    Returns:
        Full state name

    Examples:
        >>> expand_state_abbreviation("OK")
        "Oklahoma"
        >>> expand_state_abbreviation("Oklahoma")
        "Oklahoma"
    """
    state = state.strip().upper()
    return STATE_ABBREVIATIONS.get(state, state.title())


def sanitize_filename_component(text: str) -> str:
    """Sanitize text for use in filename.

    Args:
        text: Text to sanitize

    Returns:
        Sanitized text safe for filename

    Examples:
        >>> sanitize_filename_component("John/Jane")
        "John-Jane"
        >>> sanitize_filename_component('Test "Name" <>')
        "Test Name"
    """
    # Remove illegal characters: / \ : * ? " < > |
    illegal_chars = r'[/\\:*?"<>|]'
    text = re.sub(illegal_chars, '', text)

    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def generate_census_filename(
    census_year: int,
    state: str,
    county: str,
    surname: str,
    given_name: str,
    extension: str = ".jpg"
) -> str:
    """Generate standardized census image filename.

    Format: YYYY, State, County - Surname, GivenName.ext

    Args:
        census_year: 1790-1950 census year
        state: Full state name or 2-letter abbreviation
        county: County name
        surname: Person's surname
        given_name: Person's given name(s)
        extension: File extension (default .jpg)

    Returns:
        Standardized filename

    Raises:
        ValueError: If census year invalid or required fields empty

    Examples:
        >>> generate_census_filename(1930, "OK", "Tulsa", "Iams", "Jesse Dorsey")
        "1930, Oklahoma, Tulsa - Iams, Jesse Dorsey.jpg"

        >>> generate_census_filename(1940, "Texas", "Milam", "Iiams", "Frank W.")
        "1940, Texas, Milam - Iiams, Frank W..jpg"
    """
    # Validate census year
    if not 1790 <= census_year <= 1950:
        raise ValueError(f"Invalid census year: {census_year} (must be 1790-1950)")

    # Validate required fields
    if not all([state, county, surname, given_name]):
        raise ValueError("All fields required: state, county, surname, given_name")

    # Expand state abbreviation
    state_full = expand_state_abbreviation(state)

    # Sanitize components
    clean_county = sanitize_filename_component(county)
    clean_surname = sanitize_filename_component(surname)
    clean_given = sanitize_filename_component(given_name)

    # Ensure extension has leading dot
    if not extension.startswith('.'):
        extension = f'.{extension}'

    # Generate filename
    filename = f"{census_year}, {state_full}, {clean_county} - {clean_surname}, {clean_given}{extension}"

    # Truncate if too long (filesystem limit 255 chars)
    if len(filename) > 255:
        max_name_len = 255 - len(extension) - 3  # 3 for "..."
        filename = filename[:max_name_len] + "..." + extension

    return filename


def parse_census_filename(filename: str) -> dict | None:
    """Parse standardized census filename back to components.

    Args:
        filename: Census filename to parse

    Returns:
        Dictionary with components, or None if invalid format

    Examples:
        >>> parse_census_filename("1930, Oklahoma, Tulsa - Iams, Jesse Dorsey.jpg")
        {
            'census_year': 1930,
            'state': 'Oklahoma',
            'county': 'Tulsa',
            'surname': 'Iams',
            'given_name': 'Jesse Dorsey',
            'extension': '.jpg'
        }
    """
    # Pattern: YYYY, State, County - Surname, GivenName.ext
    pattern = r'^(\d{4}),\s+([^,]+),\s+([^-]+)\s+-\s+([^,]+),\s+(.+?)(\.\w+)$'
    match = re.match(pattern, filename)

    if not match:
        return None

    return {
        'census_year': int(match.group(1)),
        'state': match.group(2).strip(),
        'county': match.group(3).strip(),
        'surname': match.group(4).strip(),
        'given_name': match.group(5).strip(),
        'extension': match.group(6)
    }
```

**Tests**:
```python
def test_generate_census_filename():
    filename = generate_census_filename(1930, "OK", "Tulsa", "Iams", "Jesse Dorsey")
    assert filename == "1930, Oklahoma, Tulsa - Iams, Jesse Dorsey.jpg"

def test_expand_state_abbreviation():
    assert expand_state_abbreviation("OK") == "Oklahoma"
    assert expand_state_abbreviation("Oklahoma") == "Oklahoma"
    assert expand_state_abbreviation("TX") == "Texas"

def test_sanitize_filename():
    assert sanitize_filename_component("John/Jane") == "John-Jane"
    assert sanitize_filename_component('Test "Name"') == "Test Name"
```

#### Task 1.3: Directory Mapper

**Files**:
- `src/rmcitecraft/utils/census_directories.py` (new)
- `tests/unit/utils/test_census_directories.py` (new)

**Implementation**:

```python
"""Census directory mapping utilities."""

from pathlib import Path


def get_census_directory(
    census_year: int,
    schedule_type: str = "federal",
    media_root: str = "?"
) -> str:
    """Get RootsMagic media path for census year.

    Args:
        census_year: Census year (1790-1950)
        schedule_type: "federal", "slave", "mortality", "veterans"
        media_root: RootsMagic symbol (? = media root, ~ = home, * = db dir)

    Returns:
        RootsMagic symbolic path

    Examples:
        >>> get_census_directory(1930)
        "?/Records - Census/1930 Federal"

        >>> get_census_directory(1850, "slave")
        "?/Records - Census/1850 Federal Slave Schedule"
    """
    base = f"{media_root}/Records - Census"

    if schedule_type == "slave":
        if census_year in (1850, 1860):
            return f"{base}/{census_year} Federal Slave Schedule"
        raise ValueError(f"Slave schedules only available for 1850, 1860")

    elif schedule_type == "mortality":
        if 1850 <= census_year <= 1885 and census_year % 10 == 0:
            return f"{base}/Federal Mortality Schedule 1850-1885/{census_year} Mortality"
        raise ValueError(f"Mortality schedules available 1850-1885 only")

    elif schedule_type == "veterans":
        if census_year == 1890:
            return f"{base}/1890 Federal Veterans and Widows Schedule"
        raise ValueError(f"Veterans schedule only available for 1890")

    # Default: regular federal census
    if not (1790 <= census_year <= 1950 and census_year % 10 == 0):
        raise ValueError(f"Invalid census year: {census_year} (must be 1790-1950, decade)")

    return f"{base}/{census_year} Federal"


def ensure_census_directory(
    census_year: int,
    schedule_type: str = "federal",
    media_root_path: Path | None = None
) -> Path:
    """Ensure census directory exists, create if needed.

    Args:
        census_year: Census year
        schedule_type: Type of schedule
        media_root_path: Absolute path to media root (replaces ?)

    Returns:
        Absolute path to census directory

    Raises:
        ValueError: If media_root_path not provided
    """
    if not media_root_path:
        media_root_path = Path.home() / "Genealogy" / "RootsMagic" / "Files"

    # Get relative path (without ? symbol)
    rel_path = get_census_directory(census_year, schedule_type, media_root="")
    if rel_path.startswith("/"):
        rel_path = rel_path[1:]  # Remove leading slash

    # Build absolute path
    full_path = media_root_path / rel_path

    # Create directory if doesn't exist
    full_path.mkdir(parents=True, exist_ok=True)

    return full_path
```

#### Task 1.4: Database Media Integration

**Files**:
- `src/rmcitecraft/repositories/media_repository.py` (new)
- `tests/unit/repositories/test_media_repository.py` (new)

**Implementation**:

```python
"""Repository for RootsMagic MultimediaTable operations."""

from datetime import datetime, timezone
from pathlib import Path

from loguru import logger


def get_current_utc_moddate() -> float:
    """Get current UTC timestamp for RootsMagic UTCModDate field.

    Returns:
        Float timestamp (seconds since epoch)
    """
    return datetime.now(timezone.utc).timestamp()


class MediaRepository:
    """Repository for media operations in RootsMagic database."""

    def __init__(self, db_connection):
        """Initialize repository.

        Args:
            db_connection: DatabaseConnection instance
        """
        self.db = db_connection

    def create_media_record(
        self,
        media_path: str,
        media_file: str,
        caption: str,
        ref_number: str,
        date: str,
        media_type: int = 1
    ) -> int:
        """Create MultimediaTable record.

        Args:
            media_path: RootsMagic symbolic path (e.g., "?/Records - Census/1930 Federal")
            media_file: Filename
            caption: Human-readable caption
            ref_number: FamilySearch ARK URL
            date: RootsMagic date format
            media_type: 1=Image, 2=File, 3=Sound, 4=Video

        Returns:
            New MediaID
        """
        cursor = self.db.connection.cursor()

        cursor.execute("""
            INSERT INTO MultimediaTable (
                MediaType,
                MediaPath,
                MediaFile,
                Caption,
                RefNumber,
                Date,
                UTCModDate
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            media_type,
            media_path,
            media_file,
            caption,
            ref_number,
            date,
            get_current_utc_moddate()
        ))

        media_id = cursor.lastrowid
        self.db.connection.commit()

        logger.info(f"Created media record: MediaID={media_id}, File={media_file}")
        return media_id

    def link_media_to_event(self, media_id: int, event_id: int) -> None:
        """Link media to census event.

        Args:
            media_id: MediaID from MultimediaTable
            event_id: EventID from EventTable
        """
        cursor = self.db.connection.cursor()

        cursor.execute("""
            INSERT INTO MediaLinkTable (
                MediaID,
                OwnerType,
                OwnerID,
                UTCModDate
            ) VALUES (?, ?, ?, ?)
        """, (
            media_id,
            2,  # OwnerType: 2 = Event
            event_id,
            get_current_utc_moddate()
        ))

        self.db.connection.commit()
        logger.info(f"Linked media {media_id} to event {event_id}")

    def link_media_to_citation(self, media_id: int, citation_id: int) -> None:
        """Link media to citation.

        Args:
            media_id: MediaID from MultimediaTable
            citation_id: CitationID from CitationTable
        """
        cursor = self.db.connection.cursor()

        cursor.execute("""
            INSERT INTO MediaLinkTable (
                MediaID,
                OwnerType,
                OwnerID,
                UTCModDate
            ) VALUES (?, ?, ?, ?)
        """, (
            media_id,
            4,  # OwnerType: 4 = Citation
            citation_id,
            get_current_utc_moddate()
        ))

        self.db.connection.commit()
        logger.info(f"Linked media {media_id} to citation {citation_id}")

    def find_census_event_id(
        self,
        person_id: int,
        census_year: int
    ) -> int | None:
        """Find EventID for person's census event.

        Args:
            person_id: PersonID from PersonTable
            census_year: Census year (e.g., 1930)

        Returns:
            EventID if found, None otherwise
        """
        cursor = self.db.connection.cursor()

        # Get Census FactTypeID
        cursor.execute("""
            SELECT FactTypeID
            FROM FactTypeTable
            WHERE Name LIKE '%Census%'
            LIMIT 1
        """)
        fact_type_row = cursor.fetchone()
        if not fact_type_row:
            logger.warning("Census FactType not found in FactTypeTable")
            return None

        fact_type_id = fact_type_row[0]

        # Find event
        cursor.execute("""
            SELECT EventID
            FROM EventTable
            WHERE OwnerID = ?
              AND EventType = ?
              AND Date LIKE ?
            LIMIT 1
        """, (
            person_id,
            fact_type_id,
            f"D.+{census_year}%"
        ))

        row = cursor.fetchone()
        if row:
            logger.debug(f"Found census event: EventID={row[0]}, PersonID={person_id}, Year={census_year}")
            return row[0]

        logger.warning(f"No census event found: PersonID={person_id}, Year={census_year}")
        return None

    def check_duplicate_image(
        self,
        media_file: str,
        person_id: int,
        census_year: int
    ) -> int | None:
        """Check if image already exists for person/year.

        Args:
            media_file: Filename to check
            person_id: PersonID
            census_year: Census year

        Returns:
            Existing MediaID if duplicate found, None otherwise
        """
        cursor = self.db.connection.cursor()

        cursor.execute("""
            SELECT m.MediaID
            FROM MultimediaTable m
            JOIN MediaLinkTable ml ON m.MediaID = ml.MediaID
            JOIN EventTable e ON ml.OwnerID = e.EventID
            WHERE e.OwnerID = ?
              AND e.Date LIKE ?
              AND m.MediaFile = ?
              AND ml.OwnerType = 2
        """, (person_id, f"D.+{census_year}%", media_file))

        row = cursor.fetchone()
        return row[0] if row else None
```

#### Task 1.5: Image Processing Service

**Files**:
- `src/rmcitecraft/services/image_processor.py` (new)
- `tests/unit/services/test_image_processor.py` (new)

**Implementation**:

```python
"""Census image processing service."""

import shutil
from pathlib import Path

from loguru import logger

from rmcitecraft.repositories.media_repository import MediaRepository
from rmcitecraft.utils.census_directories import ensure_census_directory, get_census_directory
from rmcitecraft.utils.filename_generator import generate_census_filename


class ImageProcessor:
    """Process downloaded census images."""

    def __init__(
        self,
        media_repository: MediaRepository,
        media_root_path: Path
    ):
        """Initialize processor.

        Args:
            media_repository: MediaRepository instance
            media_root_path: Absolute path to RootsMagic media root
        """
        self.media_repo = media_repository
        self.media_root = media_root_path

    def process_census_image(
        self,
        source_file: Path,
        citation_data: dict
    ) -> dict:
        """Process downloaded census image.

        Args:
            source_file: Path to downloaded file
            citation_data: Citation metadata dict with keys:
                - census_year (int)
                - state (str)
                - county (str)
                - surname (str)
                - given_name (str)
                - person_id (int)
                - citation_id (int)
                - familysearch_url (str)
                - schedule_type (str, optional)

        Returns:
            Processing result dict:
                - success (bool)
                - media_id (int, if success)
                - target_path (Path, if success)
                - error (str, if failure)
        """
        try:
            # Extract data
            census_year = citation_data['census_year']
            state = citation_data['state']
            county = citation_data['county']
            surname = citation_data['surname']
            given_name = citation_data['given_name']
            person_id = citation_data['person_id']
            citation_id = citation_data.get('citation_id')
            familysearch_url = citation_data['familysearch_url']
            schedule_type = citation_data.get('schedule_type', 'federal')

            # Generate filename
            filename = generate_census_filename(
                census_year=census_year,
                state=state,
                county=county,
                surname=surname,
                given_name=given_name,
                extension=source_file.suffix
            )

            # Check for duplicate
            existing_media_id = self.media_repo.check_duplicate_image(
                filename,
                person_id,
                census_year
            )

            if existing_media_id:
                logger.info(f"Image already exists: MediaID={existing_media_id}")
                # Link to new citation if provided
                if citation_id:
                    self.media_repo.link_media_to_citation(existing_media_id, citation_id)
                return {
                    'success': True,
                    'media_id': existing_media_id,
                    'duplicate': True
                }

            # Get target directory
            target_dir = ensure_census_directory(
                census_year,
                schedule_type,
                self.media_root
            )

            # Move and rename file
            target_path = target_dir / filename
            shutil.move(str(source_file), str(target_path))
            logger.info(f"Moved image: {source_file.name} → {target_path}")

            # Create database record
            media_path = get_census_directory(census_year, schedule_type)
            caption = f"{census_year} U.S. Census, {state}, {county}"
            date = f"D.+{census_year}0000..+00000000.."  # RootsMagic date format

            media_id = self.media_repo.create_media_record(
                media_path=media_path,
                media_file=filename,
                caption=caption,
                ref_number=familysearch_url,
                date=date
            )

            # Find and link to event
            event_id = self.media_repo.find_census_event_id(person_id, census_year)
            if event_id:
                self.media_repo.link_media_to_event(media_id, event_id)
            else:
                logger.warning(f"No census event found for PersonID={person_id}, Year={census_year}")

            # Link to citation if provided
            if citation_id:
                self.media_repo.link_media_to_citation(media_id, citation_id)

            return {
                'success': True,
                'media_id': media_id,
                'target_path': target_path,
                'duplicate': False
            }

        except Exception as e:
            logger.error(f"Image processing failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
```

---

### Phase 2: Extension Integration (Week 2)

**Goal**: Implement communication between browser extension and RMCitecraft

**Estimated Time**: 5-7 days

#### Task 2.1: Image Tracking System

**Files**:
- `src/rmcitecraft/services/image_tracker.py` (new)

**Implementation**: See architecture document Section 6

#### Task 2.2: Enhanced API Endpoints

**Files**:
- `src/rmcitecraft/api/endpoints.py` (update)

**New Endpoints**:
```python
@router.post("/extension/image/downloaded")
async def image_downloaded(data: dict):
    """Handle image downloaded notification from extension."""
    tracking_id = data.get('tracking_id')
    filename = data.get('filename')
    status = data.get('status')

    # Update tracker
    image_tracker.update_status(tracking_id, ImageStatus.DOWNLOADED)

    # Trigger processing
    download_monitor.process_by_tracking_id(tracking_id, filename)

    return {"status": "processing"}
```

#### Task 2.3: Command Queue Enhancement

**Files**:
- `src/rmcitecraft/services/command_queue.py` (update)

**New Command Type**:
```python
def queue_image_download(
    citation_id: str,
    familysearch_url: str,
    tracking_id: str
) -> str:
    """Queue image download command for extension."""
    command = {
        "type": "download_image",
        "citation_id": citation_id,
        "url": familysearch_url,
        "tracking_id": tracking_id
    }
    return command_queue.add(command)
```

---

### Phase 3: UI Enhancement (Week 3)

**Goal**: Add UI elements for image status and management

**Estimated Time**: 5-7 days

#### Task 3.1: Image Status in Pending Citations

**Files**:
- `src/rmcitecraft/ui/tabs/citation_manager.py` (update)

**Implementation**: Add status indicator to pending citation cards

#### Task 3.2: Download Buttons

**Files**:
- `src/rmcitecraft/ui/tabs/citation_manager.py` (update)

**Implementation**: Add [Download Image] button to citations without images

#### Task 3.3: Image Manager Tab

**Files**:
- `src/rmcitecraft/ui/tabs/image_manager.py` (new)

**Implementation**: Complete tab with filtering and bulk operations

---

### Phase 4: Smart Features (Week 4)

**Goal**: Advanced features and optimizations

**Estimated Time**: 5-7 days

#### Task 4.1: Duplicate Detection

**Implementation**: Already included in ImageProcessor

#### Task 4.2: Retry Failed Downloads

**Files**:
- `src/rmcitecraft/services/download_retry.py` (new)

#### Task 4.3: Bulk Download Queue

**Files**:
- `src/rmcitecraft/services/bulk_downloader.py` (new)

---

## Testing Strategy

### Unit Tests

Each component should have comprehensive unit tests:

```
tests/
└── unit/
    ├── services/
    │   ├── test_file_watcher.py
    │   ├── test_image_processor.py
    │   └── test_image_tracker.py
    ├── repositories/
    │   └── test_media_repository.py
    └── utils/
        ├── test_filename_generator.py
        └── test_census_directories.py
```

### Integration Tests

```
tests/
└── integration/
    ├── test_image_workflow.py
    ├── test_extension_integration.py
    └── test_database_operations.py
```

### Manual Testing Checklist

- [ ] Download single image via extension
- [ ] Download image for existing citation
- [ ] Bulk download 5 images
- [ ] Handle download failure
- [ ] Process duplicate image
- [ ] Verify database links (event + citation)
- [ ] Verify file organization
- [ ] Test with various image formats (JPG, PNG, PDF)

---

## Code Review Checklist

Before merging each PR:

- [ ] Unit tests pass (>80% coverage)
- [ ] Integration tests pass
- [ ] Linting passes (ruff)
- [ ] Type checking passes (mypy)
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] No hardcoded paths
- [ ] Error handling comprehensive
- [ ] Logging at appropriate levels
- [ ] Database transactions used correctly
- [ ] File operations are safe (error handling)

---

## Deployment Checklist

Before releasing:

- [ ] All tests pass
- [ ] Documentation complete
- [ ] User guide reviewed
- [ ] Migration script for existing databases (if needed)
- [ ] Backup instructions clear
- [ ] Rollback procedure documented
- [ ] Performance testing complete
- [ ] Extension compatibility verified

---

## Monitoring & Observability

### Logging

**Key Log Points**:
```python
logger.info("Image detected: {filename}")
logger.info("Processing image: {tracking_id}")
logger.info("Image moved: {source} → {target}")
logger.info("Media record created: MediaID={media_id}")
logger.info("Image linked to event: EventID={event_id}")
logger.warning("Duplicate image detected: {filename}")
logger.error("Image processing failed: {error}")
```

### Metrics to Track

- Images processed per hour
- Processing success rate
- Average processing time
- Duplicate detection rate
- Download failure rate
- Storage usage

---

## Performance Targets

- **File detection**: < 1 second
- **Image processing**: < 3 seconds per image
- **Database writes**: < 500ms per transaction
- **Bulk download**: 1 image per 3 seconds
- **Memory usage**: < 100MB for monitor service
- **Disk I/O**: Minimize by batch operations

---

## Security Considerations

### File System

- Validate all file paths before operations
- Use symbolic paths (?, ~, *) for portability
- Check file sizes (warn if > 10MB)
- Verify file types (magic number check)
- Never follow symlinks outside approved directories

### Database

- Always use parameterized queries
- Use transactions for all writes
- Validate data before insertion
- Check RootsMagic not running during writes
- Log all database modifications

### Extension Communication

- Validate tracking IDs
- Rate limit API calls (prevent DoS)
- Sanitize all input from extension
- Use HTTPS only
- Implement request signing (future)

---

## Documentation Requirements

### Code Documentation

Each function should have:
```python
def function_name(param: type) -> return_type:
    """Short description.

    Longer description if needed.

    Args:
        param: Description of parameter

    Returns:
        Description of return value

    Raises:
        ErrorType: When this error occurs

    Examples:
        >>> function_name(value)
        expected_output
    """
```

### API Documentation

Use OpenAPI/Swagger for all endpoints:
```python
@router.post("/extension/image/downloaded", response_model=ImageResponse)
async def image_downloaded(data: ImageDownloadData):
    """
    Handle image downloaded notification from extension.

    Receives notification that browser extension has downloaded an image
    and triggers processing workflow.

    **Request Body:**
    - tracking_id: Unique identifier for this download
    - filename: Original downloaded filename
    - status: success or failed
    """
```

---

## Document Version

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-29 | Initial implementation plan |

