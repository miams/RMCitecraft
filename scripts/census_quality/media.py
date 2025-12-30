"""Media file validation for census quality checking.

Contains functions for validating media file attachments and
checking for orphaned or missing files.
"""

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .constants import CENSUS_DIRECTORIES, MEDIA_ROOT


@dataclass
class MediaCheckResult:
    """Result of media file validation."""

    sources_without_media: list[tuple[int, str]]  # (source_id, source_name)
    missing_files: list[tuple[int, str, str]]  # (source_id, source_name, file_path)
    orphaned_files: list[str]  # Files on disk not linked to any source
    case_mismatches: list[
        tuple[str, str]
    ]  # (db_filename, disk_filename) where case differs
    total_linked_files: int
    total_files_on_disk: int


def normalize_media_path(media_path: str, media_file: str) -> Path:
    """Convert RootsMagic media path to actual filesystem path.

    RootsMagic stores paths like:
    - MediaPath: '?\\Records - Census\\1940 Federal' (Windows-style)
    - MediaPath: '?/Records - Census/1940 Federal' (Mac-style)
    - MediaFile: '1940, Ohio, Stark - Iams, Cash Harold.jpg'

    The '?' prefix indicates a relative path from MEDIA_ROOT.
    Backslashes are converted to forward slashes for macOS.
    """
    # Remove leading '?' and any slashes, convert backslashes
    clean_path = media_path.lstrip("?").lstrip("/").lstrip("\\").replace("\\", "/")
    return MEDIA_ROOT / clean_path / media_file


def get_source_media_links(
    conn: sqlite3.Connection, year_key: int | str
) -> dict[int, list[tuple[str, str]]]:
    """Get media links for all sources of a census year.

    Args:
        conn: Database connection
        year_key: Either an integer year (1850, 1860, etc.) or a string key
                  like "1860-slave" for slave schedules.

    Returns:
        Dict mapping source_id to list of (media_path, media_file) tuples
    """
    cursor = conn.cursor()

    # Determine source name prefix based on year_key
    if isinstance(year_key, str) and year_key.endswith("-slave"):
        year = int(year_key.replace("-slave", ""))
        name_prefix = f"Fed Census Slave Schedule: {year},%"
    elif isinstance(year_key, str) and year_key.endswith("-mortality"):
        year = int(year_key.replace("-mortality", ""))
        name_prefix = f"Fed Census Mortality Schedule: {year},%"
    else:
        name_prefix = f"Fed Census: {year_key},%"

    cursor.execute(
        """
        SELECT s.SourceID, m.MediaPath, m.MediaFile
        FROM SourceTable s
        LEFT JOIN MediaLinkTable ml ON ml.OwnerID = s.SourceID AND ml.OwnerType = 4
        LEFT JOIN MultimediaTable m ON m.MediaID = ml.MediaID
        WHERE s.Name LIKE ?
        ORDER BY s.SourceID
    """,
        (name_prefix,),
    )

    result: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for row in cursor.fetchall():
        source_id, media_path, media_file = row
        if media_path and media_file:
            result[source_id].append((media_path, media_file))
        elif source_id not in result:
            result[source_id] = []  # Mark as having no media

    return dict(result)


def get_all_media_in_directory(
    conn: sqlite3.Connection, year_key: int | str
) -> dict[str, str]:
    """Get all media files in MultimediaTable that are in the census year's directory.

    Args:
        conn: Database connection
        year_key: Either an integer year (1850, 1860, etc.) or a string key
                  like "1860-slave" for slave schedules.

    Returns:
        Dict mapping lowercase path -> original path for case-insensitive comparison.
    """
    cursor = conn.cursor()
    # Extract numeric year for directory lookup
    if isinstance(year_key, str) and year_key.endswith("-slave"):
        year = int(year_key.replace("-slave", ""))
    elif isinstance(year_key, str) and year_key.endswith("-mortality"):
        year = int(year_key.replace("-mortality", ""))
    else:
        year = int(year_key)
    dir_name = CENSUS_DIRECTORIES.get(year, f"{year} Federal")

    cursor.execute(
        """
        SELECT MediaPath, MediaFile
        FROM MultimediaTable
        WHERE MediaPath LIKE ?
    """,
        (f"%{dir_name}%",),
    )

    # Map lowercase path -> original path
    files: dict[str, str] = {}
    for row in cursor.fetchall():
        media_path, media_file = row
        if media_path and media_file:
            full_path = normalize_media_path(media_path, media_file)
            files[str(full_path).lower()] = str(full_path)

    return files


def run_media_check(conn: sqlite3.Connection, year_key: int | str) -> MediaCheckResult:
    """Run comprehensive media file validation for a census year.

    Args:
        conn: Database connection
        year_key: Either an integer year (1850, 1860, etc.) or a string key
                  like "1860-slave" for slave schedules.

    Checks:
    1. Every source has media linked
    2. Every linked media file exists on disk
    3. Every file in the directory is linked to a source
    4. Case consistency between database and disk filenames
    """
    # Extract numeric year for directory lookup
    if isinstance(year_key, str) and year_key.endswith("-slave"):
        year = int(year_key.replace("-slave", ""))
        name_prefix = f"Fed Census Slave Schedule: {year},%"
    elif isinstance(year_key, str) and year_key.endswith("-mortality"):
        year = int(year_key.replace("-mortality", ""))
        name_prefix = f"Fed Census Mortality Schedule: {year},%"
    else:
        year = int(year_key) if isinstance(year_key, str) else year_key
        name_prefix = f"Fed Census: {year},%"

    dir_name = CENSUS_DIRECTORIES.get(year, f"{year} Federal")
    census_dir = MEDIA_ROOT / "Records - Census" / dir_name

    # Get all source names
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT SourceID, Name FROM SourceTable WHERE Name LIKE ?
    """,
        (name_prefix,),
    )
    source_names = {row[0]: row[1] for row in cursor.fetchall()}

    # Get media links for sources
    source_media = get_source_media_links(conn, year_key)

    # Get all media files linked to this census year's directory in RootsMagic
    # Returns dict: lowercase_path -> original_path
    linked_media_paths = get_all_media_in_directory(conn, year_key)

    # Check 1: Sources without media
    sources_without_media = []
    for source_id, name in source_names.items():
        if source_id not in source_media or not source_media[source_id]:
            sources_without_media.append((source_id, name))

    # Check 2: Linked media files that don't exist on disk
    missing_files = []
    all_linked_paths = set()
    for source_id, media_list in source_media.items():
        for media_path, media_file in media_list:
            full_path = normalize_media_path(media_path, media_file)
            all_linked_paths.add(str(full_path))

            # Only check files that should be in this year's directory
            if dir_name in str(full_path):
                if not full_path.exists():
                    source_name = source_names.get(source_id, f"Source {source_id}")
                    missing_files.append((source_id, source_name, str(full_path)))

    # Check 3 & 4: Files on disk - check for orphans and case mismatches
    orphaned_files = []
    case_mismatches = []
    total_files_on_disk = 0

    if census_dir.exists():
        for file_path in census_dir.iterdir():
            # Skip .DS_Store and other hidden files
            if file_path.name.startswith("."):
                continue

            if file_path.is_file():
                total_files_on_disk += 1
                disk_path = str(file_path)
                disk_path_lower = disk_path.lower()

                # Check if this file is linked in RootsMagic
                if disk_path_lower not in linked_media_paths:
                    orphaned_files.append(file_path.name)
                else:
                    # Check for case mismatch
                    db_path = linked_media_paths[disk_path_lower]
                    if db_path != disk_path:
                        # Extract just filenames for clearer output
                        db_filename = Path(db_path).name
                        disk_filename = file_path.name
                        case_mismatches.append((db_filename, disk_filename))

    return MediaCheckResult(
        sources_without_media=sources_without_media,
        missing_files=missing_files,
        orphaned_files=orphaned_files,
        case_mismatches=case_mismatches,
        total_linked_files=len(linked_media_paths),
        total_files_on_disk=total_files_on_disk,
    )
