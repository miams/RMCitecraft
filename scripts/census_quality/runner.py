"""Main quality check orchestration for census sources.

Contains the run_quality_check function that coordinates all validation.
"""

import sqlite3
from collections import Counter
from pathlib import Path

from .configs import build_census_configs
from .database import get_citation_quality_counts, get_sources_for_year
from .media import run_media_check
from .models import Issue
from .validators import (
    check_bibliography,
    check_cross_field_consistency,
    check_footnote,
    check_short_footnote,
    check_source_name,
)


def run_quality_check(
    db_path: Path,
    year_key: int | str,
    include_all: bool = False,
    check_media: bool = False,
) -> dict:
    """Run quality check for a specific census year.

    Args:
        db_path: Path to RootsMagic database
        year_key: Census year to check (e.g., 1860) or special key (e.g., "1860-slave")
        include_all: Include informational issues
        check_media: Run comprehensive media file validation (slower)
    """
    configs = build_census_configs()

    if year_key not in configs:
        # Sort keys: integers first (sorted), then strings (sorted)
        int_keys = sorted(k for k in configs.keys() if isinstance(k, int))
        str_keys = sorted(k for k in configs.keys() if isinstance(k, str))
        return {
            "error": f"No configuration for census year {year_key}",
            "supported_years": int_keys + str_keys,
        }

    config = configs[year_key]

    conn = sqlite3.connect(db_path)
    sources = get_sources_for_year(conn, year_key)
    quality_counts = get_citation_quality_counts(conn, year_key)

    # Run media check if requested (before closing connection)
    media_check_result = None
    if check_media:
        media_check_result = run_media_check(conn, year_key)

    conn.close()

    all_issues = []
    media_counts = {"no_media": 0, "single": 0, "multiple": 0}
    source_names = {}

    for source in sources:
        source_id = source["source_id"]
        name = source["name"]
        footnote = source["footnote"]
        short_footnote = source["short_footnote"]
        bibliography = source["bibliography"]
        media_count = source["media_count"]

        source_names[source_id] = name

        # Run all checks
        all_issues.extend(check_source_name(source_id, name, config))
        all_issues.extend(check_footnote(source_id, footnote, config))
        all_issues.extend(check_short_footnote(source_id, short_footnote, config))
        all_issues.extend(check_bibliography(source_id, bibliography, config))
        all_issues.extend(
            check_cross_field_consistency(
                source_id, name, footnote, short_footnote, bibliography, config
            )
        )

        # Track media counts
        if media_count == 0:
            media_counts["no_media"] += 1
            all_issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="no_media",
                    severity="warning",
                    message="Source has no media attachments",
                    field="media",
                    category="media",
                )
            )
        elif media_count == 1:
            media_counts["single"] += 1
        else:
            media_counts["multiple"] += 1
            if include_all:
                all_issues.append(
                    Issue(
                        source_id=source_id,
                        issue_type="multiple_media",
                        severity="info",
                        message=f"Source has {media_count} media attachments",
                        field="media",
                        category="media",
                    )
                )

    # Check citation quality
    wrong_quality_issues = []
    for quality, _count in quality_counts.items():
        if quality != config.expected_citation_quality:
            wrong_quality_issues.append(
                Issue(
                    source_id=0,  # Aggregate issue
                    issue_type="wrong_citation_quality",
                    severity="warning",
                    message=f"Citation quality should be '{config.expected_citation_quality}'",
                    field="quality",
                    current_value=quality,
                    expected_value=config.expected_citation_quality,
                    category="quality",
                )
            )

    # Add media check issues if enabled
    media_file_check = None
    if media_check_result:
        media_file_check = {
            "sources_without_media": len(media_check_result.sources_without_media),
            "missing_files": len(media_check_result.missing_files),
            "orphaned_files": len(media_check_result.orphaned_files),
            "case_mismatches": len(media_check_result.case_mismatches),
            "total_linked_files": media_check_result.total_linked_files,
            "total_files_on_disk": media_check_result.total_files_on_disk,
            "sources_without_media_list": media_check_result.sources_without_media,
            "missing_files_list": media_check_result.missing_files,
            "orphaned_files_list": media_check_result.orphaned_files,
            "case_mismatches_list": media_check_result.case_mismatches,
        }

        # Add issues for missing files
        for source_id, _source_name, file_path in media_check_result.missing_files:
            all_issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="media_file_missing",
                    severity="error",
                    message="Linked media file does not exist on disk",
                    field="media",
                    current_value=file_path,
                    category="media",
                )
            )

        # Add issues for orphaned files (files on disk not linked)
        for file_name in media_check_result.orphaned_files:
            all_issues.append(
                Issue(
                    source_id=0,
                    issue_type="orphaned_media_file",
                    severity="warning",
                    message=f"File on disk not linked to any source: {file_name}",
                    field="media",
                    current_value=file_name,
                    category="media",
                )
            )

        # Add issues for case mismatches (db filename differs from disk filename in case)
        for db_filename, disk_filename in media_check_result.case_mismatches:
            all_issues.append(
                Issue(
                    source_id=0,
                    issue_type="media_filename_case_mismatch",
                    severity="warning",
                    message=f"Filename case mismatch: DB='{db_filename}' vs Disk='{disk_filename}'",
                    field="media",
                    current_value=f"{db_filename} -> {disk_filename}",
                    category="media",
                )
            )

    # Compile results
    by_severity = Counter(i.severity for i in all_issues)
    by_type = Counter(i.issue_type for i in all_issues)

    result = {
        "year": year_key,
        "description": config.description,
        "total_sources": len(sources),
        "total_issues": len(all_issues),
        "by_severity": dict(by_severity),
        "by_type": dict(by_type),
        "quality_counts": quality_counts,
        "media_counts": media_counts,
        "issues": [i.to_dict() for i in all_issues],
        "source_names": source_names,
    }

    # Add media file check results if enabled
    if media_file_check:
        result["media_file_check"] = media_file_check

    return result
