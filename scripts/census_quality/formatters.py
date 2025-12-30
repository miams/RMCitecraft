"""Output formatting for census quality check results.

Contains functions for formatting results in various output formats:
compact (token-efficient for LLMs) and text (human-readable).
"""

from collections import defaultdict
from pathlib import Path


def format_compact_output(result: dict, detailed: bool = False) -> str:
    """Format result as compact, token-efficient text optimized for LLM consumption.

    This format minimizes tokens while preserving all semantic information.
    Preferred when output will be processed by Claude or other LLMs.
    """
    lines = []

    year = result["year"]
    total = result["total_sources"]
    issues = result["total_issues"]
    errors = result.get("by_severity", {}).get("error", 0)
    warnings = result.get("by_severity", {}).get("warning", 0)

    # Single-line summary
    quality = result.get("quality_counts", {})
    pdo = quality.get("PDO", 0)
    non_pdo = sum(v for k, v in quality.items() if k != "PDO")

    status = "PASS" if issues == 0 else "FAIL" if errors > 0 else "WARN"
    lines.append(
        f"{year} Census: {status} | {total} sources | {issues} issues ({errors}E/{warnings}W) | quality:{pdo}PDO/{non_pdo}other"
    )

    # Media summary
    mc = result.get("media_counts", {})
    media_str = f"media:{mc.get('single',0)}ok/{mc.get('multiple',0)}multi/{mc.get('no_media',0)}missing"

    mfc = result.get("media_file_check")
    if mfc:
        file_status = (
            "✓" if mfc["missing_files"] == 0 and mfc["orphaned_files"] == 0 else "✗"
        )
        media_str += f" | files:{mfc['total_files_on_disk']}disk/{mfc['total_linked_files']}linked/{mfc['orphaned_files']}orphaned {file_status}"

    lines.append(media_str)

    # Issue breakdown (only if issues exist)
    if result.get("by_type"):
        lines.append("")
        lines.append("Issues:")

        # Group issues by type
        issues_by_type: dict[str, list[dict]] = defaultdict(list)
        for issue in result.get("issues", []):
            issues_by_type[issue["issue_type"]].append(issue)

        for issue_type, issue_list in sorted(
            issues_by_type.items(), key=lambda x: -len(x[1])
        ):
            count = len(issue_list)
            severity = issue_list[0]["severity"][0].upper()  # E/W/I
            source_ids = [i["source_id"] for i in issue_list if i["source_id"] != 0]

            line = f"  [{severity}] {issue_type}: {count}"
            if source_ids and (detailed or len(source_ids) <= 8):
                line += f" | sources: {','.join(str(s) for s in source_ids)}"
            elif source_ids:
                line += f" | {len(source_ids)} sources"

            lines.append(line)

            # Show file names for media issues if detailed
            if detailed and issue_type in ("orphaned_media_file", "media_file_missing"):
                for issue in issue_list[:10]:
                    if issue.get("current_value"):
                        lines.append(f"    {issue['current_value']}")
                if len(issue_list) > 10:
                    lines.append(f"    ...+{len(issue_list)-10} more")

    return "\n".join(lines)


def format_text_output(result: dict, detailed: bool = False) -> str:
    """Format result as human-readable text with improved visual layout."""
    lines = []
    width = 78  # Output width

    def header(title: str) -> list[str]:
        """Create a section header."""
        return [f"\n{'─' * width}", f"  {title}", "─" * width]

    def subheader(title: str) -> str:
        """Create a subsection header."""
        return f"\n  ▸ {title}"

    def stat_line(label: str, value, width: int = 24) -> str:
        """Format a statistic line with right-aligned value."""
        return f"  {label:<{width}} {value:>6}"

    def status_icon(is_good: bool) -> str:
        return "✓" if is_good else "✗"

    # Title block
    lines.append("═" * width)
    lines.append(f"  {result['year']} CENSUS QUALITY CHECK")
    lines.append(f"  {result.get('description', '')}")
    lines.append("═" * width)

    # Overview section
    lines.extend(header("OVERVIEW"))
    total_sources = result["total_sources"]
    total_issues = result["total_issues"]
    errors = result.get("by_severity", {}).get("error", 0)
    warnings = result.get("by_severity", {}).get("warning", 0)

    lines.append(stat_line("Sources checked:", total_sources))

    if total_issues == 0:
        lines.append(stat_line("Issues found:", f"{status_icon(True)} None"))
    else:
        # Build grammatically correct summary
        parts = []
        if errors:
            parts.append(f"{errors} error{'s' if errors != 1 else ''}")
        if warnings:
            parts.append(f"{warnings} warning{'s' if warnings != 1 else ''}")
        issue_summary = (
            f"{total_issues} ({', '.join(parts)})"
            if len(parts) > 1
            else parts[0] if parts else str(total_issues)
        )
        lines.append(stat_line("Issues found:", issue_summary))

    # Citation quality
    quality_counts = result.get("quality_counts", {})
    pdo_count = quality_counts.get("PDO", 0)
    non_pdo = sum(v for k, v in quality_counts.items() if k != "PDO")
    if non_pdo == 0 and pdo_count > 0:
        lines.append(stat_line("Citation quality:", f"{status_icon(True)} All {pdo_count} PDO"))
    elif non_pdo > 0:
        lines.append(stat_line("Citation quality:", f"{status_icon(False)} {non_pdo} not PDO"))

    # Media section
    lines.extend(header("MEDIA"))
    mc = result.get("media_counts", {})
    no_media = mc.get("no_media", 0)
    single = mc.get("single", 0)
    multiple = mc.get("multiple", 0)

    # Compact media summary
    parts = []
    if single:
        parts.append(f"{single} single")
    if multiple:
        parts.append(f"{multiple} multiple")
    if no_media:
        parts.append(f"{no_media} missing")
    lines.append(f"  Attachments:           {', '.join(parts) if parts else 'None'}")

    # Media file validation (if --check-media was used)
    mfc = result.get("media_file_check")
    if mfc:
        on_disk = mfc.get("total_files_on_disk", 0)
        linked = mfc.get("total_linked_files", 0)
        missing = mfc.get("missing_files", 0)
        orphaned = mfc.get("orphaned_files", 0)

        lines.append(f"  Directory files:       {on_disk} on disk, {linked} linked in database")

        if missing == 0 and orphaned == 0:
            lines.append(f"  Validation:            {status_icon(True)} All files verified")
        else:
            issues = []
            if missing:
                issues.append(f"{missing} missing")
            if orphaned:
                issues.append(f"{orphaned} orphaned")
            lines.append(f"  Validation:            {status_icon(False)} {', '.join(issues)}")

    # Issue breakdown section (only if there are issues)
    if result.get("by_type"):
        lines.extend(header("ISSUES BY TYPE"))

        # Sort by count descending
        sorted_types = sorted(result["by_type"].items(), key=lambda x: -x[1])
        max_type_len = max(len(t) for t, _ in sorted_types)

        for issue_type, count in sorted_types:
            # Find severity for this type
            severity = "warning"
            for issue in result.get("issues", []):
                if issue["issue_type"] == issue_type:
                    severity = issue["severity"]
                    break
            sev_char = "E" if severity == "error" else "W" if severity == "warning" else "I"
            lines.append(f"  [{sev_char}] {issue_type:<{max_type_len}}  {count:>4}")

    # Issue details section
    if result.get("issues"):
        lines.extend(header("ISSUE DETAILS"))

        # Group issues by type
        issues_by_type: dict[str, list[dict]] = defaultdict(list)
        for issue in result["issues"]:
            issues_by_type[issue["issue_type"]].append(issue)

        source_names = result.get("source_names", {})

        for issue_type, issues in sorted(issues_by_type.items(), key=lambda x: -len(x[1])):
            count = len(issues)
            severity = issues[0]["severity"]
            sev_label = severity.upper()

            lines.append(subheader(f"{issue_type} ({count} {sev_label})"))

            # Get representative message
            sample = issues[0]
            lines.append(f"    {sample['message']}")

            if detailed:
                # Show details based on issue type
                if issue_type == "orphaned_media_file":
                    lines.append("    Files:")
                    for issue in issues[:20]:  # Limit to 20
                        lines.append(f"      • {issue.get('current_value', 'unknown')}")
                    if count > 20:
                        lines.append(f"      ... and {count - 20} more")

                elif issue_type == "media_file_missing":
                    lines.append("    Missing files:")
                    for issue in issues:
                        sid = issue["source_id"]
                        fname = Path(issue.get("current_value", "")).name
                        lines.append(f"      • Source {sid}: {fname}")

                elif issue_type == "media_filename_case_mismatch":
                    lines.append("    Mismatches (DB → Disk):")
                    for issue in issues:
                        val = issue.get("current_value", "")
                        lines.append(f"      • {val}")

                elif issue_type in ("independent_city_ambiguous", "independent_city_is_county"):
                    lines.append("    Affected sources:")
                    for issue in issues:
                        sid = issue["source_id"]
                        name = source_names.get(sid, f"Source {sid}")
                        lines.append(f"      • [{sid}] {name}")

                else:
                    # Generic detail view - show full source names
                    source_ids = [i["source_id"] for i in issues if i["source_id"] != 0]
                    if source_ids:
                        lines.append(f"    Affected sources ({len(source_ids)}):")
                        for sid in source_ids:
                            name = source_names.get(sid, f"Source {sid}")
                            lines.append(f"      • [{sid}] {name}")

                    if issues[0].get("current_value") and issue_type not in ("no_media",):
                        lines.append(f"    Sample value: {issues[0]['current_value'][:60]}")
            else:
                # Non-detailed: just show source count or sample
                source_ids = [i["source_id"] for i in issues if i["source_id"] != 0]
                if source_ids:
                    if len(source_ids) <= 5:
                        lines.append(f"    Sources: {', '.join(str(s) for s in source_ids)}")
                    else:
                        preview = ", ".join(str(s) for s in source_ids[:3])
                        lines.append(f"    Sources: {preview}, ... ({len(source_ids)} total)")

    # Footer
    lines.append("")
    lines.append("═" * width)

    return "\n".join(lines)
