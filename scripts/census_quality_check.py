#!/usr/bin/env python3
"""
Census Quality Check Tool for RMCitecraft.

Performs comprehensive quality checks on Federal Census sources (1790-1950)
in a RootsMagic database. Designed to be used as a tool by Claude Code.

Checks include:
- Source Name format and consistency
- Footnote completeness and format
- Short Footnote completeness and format
- Bibliography format
- Citation Quality settings
- Media attachments

Usage:
    python scripts/census_quality_check.py 1940
    python scripts/census_quality_check.py 1940 --format json
    python scripts/census_quality_check.py 1940 --format text --verbose
    python scripts/census_quality_check.py --help

Output:
    JSON (default): Structured output for programmatic parsing
    Text: Human-readable report

Exit Codes:
    0: Success (issues may still be found, check output)
    1: Error (script failed to run)
"""

import argparse
import json
import logging
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# Configure logging to stderr only
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


# =============================================================================
# Census Year Configuration
# =============================================================================

@dataclass
class CensusYearConfig:
    """Configuration for a specific census year's validation rules."""
    year: int
    has_ed: bool = False  # Enumeration District (1880+)
    has_sheet: bool = True  # Sheet number
    has_line: bool = True  # Line number (1850+)
    has_stamp: bool = False  # 1950 uses stamp instead of sheet
    has_family_number: bool = False  # Family number in citation
    has_dwelling_number: bool = False  # Dwelling number (1850-1880)
    has_population_schedule: bool = True  # "population schedule" in footnote
    source_name_pattern: str = ""  # Regex pattern for source name
    footnote_title: str = ""  # Expected quoted title in footnote
    bibliography_title: str = ""  # Expected quoted title in bibliography
    short_ed_format: str = "E.D."  # ED abbreviation in short footnote


def get_census_config(year: int) -> CensusYearConfig:
    """Get validation configuration for a census year."""

    # Base configuration
    config = CensusYearConfig(year=year)

    # Year-specific settings
    if year <= 1840:
        # 1790-1840: No ED, no line numbers, basic format
        config.has_ed = False
        config.has_line = False
        config.has_population_schedule = False
        config.has_dwelling_number = False
        config.source_name_pattern = rf'^Fed Census: {year}, ([^,]+), ([^\]]+)'

    elif year <= 1870:
        # 1850-1870: Population schedule, page/sheet, dwelling/family
        config.has_ed = False
        config.has_dwelling_number = True
        config.has_family_number = True
        config.source_name_pattern = rf'^Fed Census: {year}, ([^,]+), ([^\[]+) \[.*\]'

    elif year == 1880:
        # 1880: First year with ED
        config.has_ed = True
        config.has_dwelling_number = True
        config.has_family_number = True
        config.source_name_pattern = rf'^Fed Census: {year}, ([^,]+), ([^\[]+) \[ED (\d+[A-Z]?), .*\]'

    elif year <= 1940:
        # 1900-1940: ED with suffix format (e.g., 7-36A)
        config.has_ed = True
        config.has_family_number = True
        config.source_name_pattern = rf'^Fed Census: {year}, ([^,]+), ([^\[]+) \[ED (\d+[A-Z]?-\d+[A-Z]?), sheet (\d+[AB]?), line (\d+)\]'

    elif year == 1950:
        # 1950: Uses "stamp" instead of "sheet"
        config.has_ed = True
        config.has_sheet = False
        config.has_stamp = True
        config.has_family_number = False
        config.source_name_pattern = rf'^Fed Census: {year}, ([^,]+), ([^\[]+) \[ED (\d+-\d+), stamp (\d+), line (\d+)\]'

    # Titles (same for all years with minor variations)
    config.footnote_title = f"United States Census, {year},"
    config.bibliography_title = f"United States Census, {year}."

    return config


# Known valid US state names
VALID_STATES = {
    'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado',
    'Connecticut', 'Delaware', 'Florida', 'Georgia', 'Hawaii', 'Idaho',
    'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky', 'Louisiana',
    'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota',
    'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada',
    'New Hampshire', 'New Jersey', 'New Mexico', 'New York',
    'North Carolina', 'North Dakota', 'Ohio', 'Oklahoma', 'Oregon',
    'Pennsylvania', 'Rhode Island', 'South Carolina', 'South Dakota',
    'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia', 'Washington',
    'West Virginia', 'Wisconsin', 'Wyoming', 'District of Columbia'
}


# =============================================================================
# Data Classes for Results
# =============================================================================

@dataclass
class Issue:
    """Represents a single quality issue."""
    source_id: int
    issue_type: str
    severity: str  # error, warning, info
    message: str
    field: str  # source_name, footnote, short_footnote, bibliography, quality, media
    current_value: str = ""
    expected_value: str = ""


@dataclass
class QualityCheckResult:
    """Complete result of quality check."""
    success: bool
    census_year: int
    total_sources: int
    issues: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


# =============================================================================
# Database Connection
# =============================================================================

def connect_database(db_path: Path) -> sqlite3.Connection:
    """Connect to RootsMagic database with ICU extension."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)

    # Try to load ICU extension for RMNOCASE collation
    # Look in multiple locations
    script_dir = Path(__file__).parent.parent  # Go up from scripts/ to project root
    possible_paths = [
        script_dir / 'sqlite-extension/icu.dylib',
        Path('sqlite-extension/icu.dylib'),
        Path.cwd() / 'sqlite-extension/icu.dylib',
    ]

    icu_loaded = False
    for icu_path in possible_paths:
        if icu_path.exists():
            try:
                conn.enable_load_extension(True)
                conn.load_extension(str(icu_path))

                # Register RMNOCASE collation using ICU
                conn.execute(
                    "SELECT icu_load_collation("
                    "'en_US@colStrength=primary;caseLevel=off;normalization=on',"
                    "'RMNOCASE')"
                )

                conn.enable_load_extension(False)
                logger.debug(f"Loaded ICU extension and registered RMNOCASE from {icu_path}")
                icu_loaded = True
                break
            except Exception as e:
                logger.warning(f"Could not load ICU extension from {icu_path}: {e}")

    if not icu_loaded:
        logger.warning("ICU extension not loaded - RMNOCASE collation may fail")

    return conn


# =============================================================================
# Validation Functions
# =============================================================================

def extract_field_from_blob(fields_blob: bytes, field_name: str) -> str:
    """Extract a field value from the Fields BLOB XML structure."""
    if not fields_blob:
        return ""

    try:
        fields_text = fields_blob.decode('utf-8', errors='ignore')
        pattern = rf'<Name>{field_name}</Name>\s*<Value>(.*?)</Value>'
        match = re.search(pattern, fields_text, re.DOTALL)
        return match.group(1) if match else ""
    except Exception:
        return ""


def check_source_name(source_id: int, name: str, config: CensusYearConfig) -> list[Issue]:
    """Check source name format and content."""
    issues = []
    year = config.year

    # Check basic pattern
    if not name.startswith(f'Fed Census: {year},'):
        issues.append(Issue(
            source_id=source_id,
            issue_type="source_name_format",
            severity="error",
            message=f"Source name doesn't start with 'Fed Census: {year},'",
            field="source_name",
            current_value=name[:50]
        ))
        return issues

    # Extract state name
    state_match = re.match(rf'Fed Census: {year}, ([^,]+),', name)
    if state_match:
        state = state_match.group(1).strip()
        if state not in VALID_STATES:
            issues.append(Issue(
                source_id=source_id,
                issue_type="state_name_typo",
                severity="error",
                message=f"Invalid state name: '{state}'",
                field="source_name",
                current_value=state
            ))

    # Check for required components based on year
    if config.has_ed and '[ED' not in name:
        issues.append(Issue(
            source_id=source_id,
            issue_type="source_name_missing_ed",
            severity="error",
            message="Missing ED (enumeration district) in source name",
            field="source_name",
            current_value=name[:80]
        ))

    if config.has_sheet and 'sheet' not in name.lower():
        issues.append(Issue(
            source_id=source_id,
            issue_type="source_name_missing_sheet",
            severity="error",
            message="Missing sheet number in source name",
            field="source_name",
            current_value=name[:80]
        ))

    if config.has_stamp and 'stamp' not in name.lower():
        issues.append(Issue(
            source_id=source_id,
            issue_type="source_name_missing_stamp",
            severity="error",
            message="Missing stamp number in source name (1950 census)",
            field="source_name",
            current_value=name[:80]
        ))

    if config.has_line and 'line' not in name.lower():
        issues.append(Issue(
            source_id=source_id,
            issue_type="source_name_missing_line",
            severity="error",
            message="Missing line number in source name",
            field="source_name",
            current_value=name[:80]
        ))

    return issues


def check_footnote(source_id: int, footnote: str, config: CensusYearConfig) -> list[Issue]:
    """Check footnote format and content."""
    issues = []
    year = config.year

    if not footnote:
        issues.append(Issue(
            source_id=source_id,
            issue_type="empty_footnote",
            severity="error",
            message="Footnote is empty",
            field="footnote"
        ))
        return issues

    # Check census reference
    if not re.search(rf'{year} U\.S\. census', footnote):
        issues.append(Issue(
            source_id=source_id,
            issue_type="footnote_missing_census_ref",
            severity="error",
            message=f"Missing '{year} U.S. census' reference",
            field="footnote",
            current_value=footnote[:100]
        ))

    # Check for ED (if required)
    if config.has_ed and not re.search(r'enumeration district \(ED\)', footnote, re.IGNORECASE):
        issues.append(Issue(
            source_id=source_id,
            issue_type="footnote_missing_ed",
            severity="error",
            message="Missing 'enumeration district (ED)' in footnote",
            field="footnote",
            current_value=footnote[:100]
        ))

    # Check for sheet/stamp
    if config.has_sheet and not re.search(r'sheet \d+[AB]?', footnote, re.IGNORECASE):
        issues.append(Issue(
            source_id=source_id,
            issue_type="footnote_missing_sheet",
            severity="error",
            message="Missing sheet number in footnote",
            field="footnote",
            current_value=footnote[:100]
        ))

    if config.has_stamp and not re.search(r'stamp \d+', footnote, re.IGNORECASE):
        issues.append(Issue(
            source_id=source_id,
            issue_type="footnote_missing_stamp",
            severity="error",
            message="Missing stamp number in footnote (1950 census)",
            field="footnote",
            current_value=footnote[:100]
        ))

    # Check for line number
    if config.has_line and not re.search(r'line \d+', footnote, re.IGNORECASE):
        issues.append(Issue(
            source_id=source_id,
            issue_type="footnote_missing_line",
            severity="error",
            message="Missing line number in footnote",
            field="footnote",
            current_value=footnote[:100]
        ))

    # Check quoted title
    title_match = re.search(r'["\u201c]([^"\u201d]+)["\u201d]', footnote) or \
                  re.search(r'&quot;([^&]+)&quot;', footnote)
    if title_match:
        title = title_match.group(1)
        if title != config.footnote_title:
            issues.append(Issue(
                source_id=source_id,
                issue_type="footnote_wrong_title",
                severity="warning",
                message=f"Wrong quoted title in footnote",
                field="footnote",
                current_value=title,
                expected_value=config.footnote_title
            ))

    # Check for double spaces
    if '  ' in footnote:
        issues.append(Issue(
            source_id=source_id,
            issue_type="footnote_double_space",
            severity="warning",
            message="Double space found in footnote",
            field="footnote"
        ))

    return issues


def check_short_footnote(source_id: int, short_footnote: str, config: CensusYearConfig) -> list[Issue]:
    """Check short footnote format and content."""
    issues = []
    year = config.year

    if not short_footnote:
        issues.append(Issue(
            source_id=source_id,
            issue_type="empty_short_footnote",
            severity="error",
            message="Short footnote is empty",
            field="short_footnote"
        ))
        return issues

    # Check census reference
    if not re.search(rf'{year} U\.S\. census', short_footnote):
        issues.append(Issue(
            source_id=source_id,
            issue_type="short_missing_census_ref",
            severity="error",
            message=f"Missing '{year} U.S. census' reference",
            field="short_footnote",
            current_value=short_footnote[:100]
        ))

    # Check for ED abbreviation (should use E.D. not enumeration district)
    if config.has_ed:
        if not re.search(rf'{config.short_ed_format}\s+\d+', short_footnote):
            # Check if using long form instead
            if 'enumeration district' in short_footnote.lower():
                issues.append(Issue(
                    source_id=source_id,
                    issue_type="short_ed_not_abbreviated",
                    severity="warning",
                    message=f"Short footnote should use '{config.short_ed_format}' not 'enumeration district'",
                    field="short_footnote",
                    current_value=short_footnote[:100]
                ))
            else:
                issues.append(Issue(
                    source_id=source_id,
                    issue_type="short_missing_ed",
                    severity="error",
                    message=f"Missing '{config.short_ed_format}' in short footnote",
                    field="short_footnote",
                    current_value=short_footnote[:100]
                ))

    # Check for sheet/stamp
    if config.has_sheet and not re.search(r'sheet \d+[AB]?', short_footnote, re.IGNORECASE):
        issues.append(Issue(
            source_id=source_id,
            issue_type="short_missing_sheet",
            severity="error",
            message="Missing sheet number in short footnote",
            field="short_footnote",
            current_value=short_footnote[:100]
        ))

    if config.has_stamp and not re.search(r'stamp \d+', short_footnote, re.IGNORECASE):
        issues.append(Issue(
            source_id=source_id,
            issue_type="short_missing_stamp",
            severity="error",
            message="Missing stamp number in short footnote",
            field="short_footnote",
            current_value=short_footnote[:100]
        ))

    # Check for line number
    if config.has_line and not re.search(r'line \d+', short_footnote, re.IGNORECASE):
        issues.append(Issue(
            source_id=source_id,
            issue_type="short_missing_line",
            severity="error",
            message="Missing line number in short footnote",
            field="short_footnote",
            current_value=short_footnote[:100]
        ))

    # Check ending period
    if not short_footnote.strip().endswith('.'):
        issues.append(Issue(
            source_id=source_id,
            issue_type="short_no_ending_period",
            severity="warning",
            message="Short footnote doesn't end with period",
            field="short_footnote",
            current_value=short_footnote[-30:]
        ))

    # Check for double spaces
    if '  ' in short_footnote:
        issues.append(Issue(
            source_id=source_id,
            issue_type="short_double_space",
            severity="warning",
            message="Double space found in short footnote",
            field="short_footnote"
        ))

    return issues


def check_bibliography(source_id: int, bibliography: str, config: CensusYearConfig) -> list[Issue]:
    """Check bibliography format and content."""
    issues = []

    if not bibliography:
        issues.append(Issue(
            source_id=source_id,
            issue_type="empty_bibliography",
            severity="error",
            message="Bibliography is empty",
            field="bibliography"
        ))
        return issues

    # Check quoted title
    title_match = re.search(r'["\u201c]([^"\u201d]+)["\u201d]', bibliography) or \
                  re.search(r'&quot;([^&]+)&quot;', bibliography)
    if title_match:
        title = title_match.group(1)
        if title != config.bibliography_title:
            issues.append(Issue(
                source_id=source_id,
                issue_type="bibliography_wrong_title",
                severity="warning",
                message="Wrong quoted title in bibliography",
                field="bibliography",
                current_value=title,
                expected_value=config.bibliography_title
            ))

    # Check for trailing period after closing quote
    if f'"{config.bibliography_title}".' in bibliography or \
       f'&quot;{config.bibliography_title}&quot;.' in bibliography:
        issues.append(Issue(
            source_id=source_id,
            issue_type="bibliography_trailing_period",
            severity="warning",
            message="Trailing period after closing quote in bibliography",
            field="bibliography"
        ))

    # Check for double spaces
    if '  ' in bibliography:
        issues.append(Issue(
            source_id=source_id,
            issue_type="bibliography_double_space",
            severity="warning",
            message="Double space found in bibliography",
            field="bibliography"
        ))

    return issues


def check_citation_quality(conn: sqlite3.Connection, year: int) -> tuple[list[Issue], dict]:
    """Check citation quality settings."""
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            cl.LinkID,
            cl.CitationID,
            cl.Quality,
            c.SourceID,
            s.Name
        FROM CitationLinkTable cl
        JOIN CitationTable c ON c.CitationID = cl.CitationID
        JOIN SourceTable s ON s.SourceID = c.SourceID
        WHERE s.Name LIKE ?
    ''', (f'Fed Census: {year},%',))

    issues = []
    quality_counts = Counter()

    # Expected quality: PDO = Primary, Direct, Original
    expected_quality = "PDO"

    for link_id, cit_id, quality, source_id, source_name in cursor.fetchall():
        quality_counts[quality or '(empty)'] += 1

        if quality != expected_quality:
            issues.append(Issue(
                source_id=source_id,
                issue_type="wrong_citation_quality",
                severity="warning",
                message=f"Citation quality should be '{expected_quality}' (Primary, Direct, Original)",
                field="quality",
                current_value=quality or '(empty)',
                expected_value=expected_quality
            ))

    return issues, dict(quality_counts)


def check_media(conn: sqlite3.Connection, year: int) -> tuple[list[Issue], dict]:
    """Check media attachments for census sources."""
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            s.SourceID,
            s.Name,
            COUNT(ml.LinkID) as media_count
        FROM SourceTable s
        LEFT JOIN MediaLinkTable ml ON ml.OwnerID = s.SourceID AND ml.OwnerType = 3
        WHERE s.Name LIKE ?
        GROUP BY s.SourceID, s.Name
    ''', (f'Fed Census: {year},%',))

    issues = []
    no_media = 0
    single_media = 0
    multiple_media = 0

    for source_id, name, count in cursor.fetchall():
        if count == 0:
            no_media += 1
            issues.append(Issue(
                source_id=source_id,
                issue_type="no_media",
                severity="warning",
                message="Source has no media attachment",
                field="media",
                current_value=name[:60]
            ))
        elif count == 1:
            single_media += 1
        else:
            multiple_media += 1
            issues.append(Issue(
                source_id=source_id,
                issue_type="multiple_media",
                severity="info",
                message=f"Source has {count} media attachments",
                field="media",
                current_value=name[:60]
            ))

    media_summary = {
        "no_media": no_media,
        "single_media": single_media,
        "multiple_media": multiple_media
    }

    return issues, media_summary


# =============================================================================
# Main Quality Check Function
# =============================================================================

def run_quality_check(db_path: Path, year: int) -> QualityCheckResult:
    """Run comprehensive quality check on census sources."""

    config = get_census_config(year)
    result = QualityCheckResult(
        success=True,
        census_year=year,
        total_sources=0,
        issues=[],
        summary={},
        metadata={"config": asdict(config)}
    )

    try:
        conn = connect_database(db_path)
    except FileNotFoundError as e:
        result.success = False
        result.metadata["error"] = str(e)
        return result

    cursor = conn.cursor()

    # Get all sources for this census year
    cursor.execute('''
        SELECT SourceID, Name, Fields
        FROM SourceTable
        WHERE Name LIKE ?
    ''', (f'Fed Census: {year},%',))

    sources = cursor.fetchall()
    result.total_sources = len(sources)

    if result.total_sources == 0:
        result.metadata["warning"] = f"No sources found for census year {year}"
        conn.close()
        return result

    # Check each source
    all_issues = []

    for source_id, name, fields_blob in sources:
        # Source name checks
        all_issues.extend(check_source_name(source_id, name, config))

        # Extract fields from BLOB
        footnote = extract_field_from_blob(fields_blob, "Footnote")
        short_footnote = extract_field_from_blob(fields_blob, "ShortFootnote")
        bibliography = extract_field_from_blob(fields_blob, "Bibliography")

        # Field checks
        all_issues.extend(check_footnote(source_id, footnote, config))
        all_issues.extend(check_short_footnote(source_id, short_footnote, config))
        all_issues.extend(check_bibliography(source_id, bibliography, config))

    # Citation quality checks
    quality_issues, quality_summary = check_citation_quality(conn, year)
    all_issues.extend(quality_issues)

    # Media checks
    media_issues, media_summary = check_media(conn, year)
    all_issues.extend(media_issues)

    conn.close()

    # Compile results
    result.issues = [asdict(issue) for issue in all_issues]

    # Create summary by issue type
    issue_summary = Counter(issue.issue_type for issue in all_issues)
    severity_summary = Counter(issue.severity for issue in all_issues)
    field_summary = Counter(issue.field for issue in all_issues)

    result.summary = {
        "total_issues": len(all_issues),
        "by_type": dict(issue_summary),
        "by_severity": dict(severity_summary),
        "by_field": dict(field_summary),
        "quality": quality_summary,
        "media": media_summary
    }

    return result


# =============================================================================
# Output Formatting
# =============================================================================

def format_text_output(result: QualityCheckResult) -> str:
    """Format result as human-readable text."""
    lines = []

    lines.append(f"{'=' * 60}")
    lines.append(f"CENSUS QUALITY CHECK: {result.census_year}")
    lines.append(f"{'=' * 60}")
    lines.append(f"Total sources: {result.total_sources}")
    lines.append(f"Total issues: {result.summary.get('total_issues', 0)}")
    lines.append("")

    # Severity breakdown
    if result.summary.get('by_severity'):
        lines.append("Issues by severity:")
        for severity, count in sorted(result.summary['by_severity'].items()):
            lines.append(f"  {severity}: {count}")
        lines.append("")

    # Issue type breakdown
    if result.summary.get('by_type'):
        lines.append("Issues by type:")
        for issue_type, count in sorted(result.summary['by_type'].items(), key=lambda x: -x[1]):
            lines.append(f"  {issue_type}: {count}")
        lines.append("")

    # Quality summary
    if result.summary.get('quality'):
        lines.append("Citation quality values:")
        for quality, count in result.summary['quality'].items():
            status = '✓' if quality == 'PDO' else '✗'
            lines.append(f"  {status} {quality}: {count}")
        lines.append("")

    # Media summary
    if result.summary.get('media'):
        media = result.summary['media']
        lines.append("Media attachments:")
        lines.append(f"  No media: {media.get('no_media', 0)}")
        lines.append(f"  Single media: {media.get('single_media', 0)}")
        lines.append(f"  Multiple media: {media.get('multiple_media', 0)}")
        lines.append("")

    # Sample issues (first 10)
    if result.issues:
        lines.append("Sample issues (first 10):")
        for issue in result.issues[:10]:
            lines.append(f"  Source {issue['source_id']}: [{issue['severity']}] {issue['issue_type']}")
            lines.append(f"    {issue['message']}")
            if issue.get('current_value'):
                lines.append(f"    Current: {issue['current_value'][:60]}")
        if len(result.issues) > 10:
            lines.append(f"  ... and {len(result.issues) - 10} more issues")

    return "\n".join(lines)


# =============================================================================
# Main Entry Point
# =============================================================================

def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "year",
        type=int,
        help="Census year to check (1790-1950)"
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/Iiams.rmtree"),
        help="Path to RootsMagic database (default: data/Iiams.rmtree)"
    )

    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    parser.add_argument(
        "--include-all-issues",
        action="store_true",
        help="Include all issues in output (default: summary only for JSON)"
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Validate year
    if args.year < 1790 or args.year > 1950:
        error = {
            "success": False,
            "error": f"Invalid census year: {args.year}. Must be between 1790 and 1950.",
            "error_type": "ValueError"
        }
        print(json.dumps(error), file=sys.stderr)
        return 1

    # Valid census years
    valid_years = list(range(1790, 1850, 10)) + list(range(1850, 1890, 10)) + \
                  list(range(1900, 1960, 10))
    if args.year not in valid_years:
        logger.warning(f"Year {args.year} is not a standard census year. Valid years: {valid_years}")

    # Run quality check
    logger.debug(f"Running quality check for {args.year} census")
    result = run_quality_check(args.db, args.year)

    # Format output
    if args.format == "json":
        output = asdict(result)
        if not args.include_all_issues and len(output.get('issues', [])) > 20:
            # Truncate issues for summary
            output['issues'] = output['issues'][:20]
            output['metadata']['issues_truncated'] = True
            output['metadata']['total_issues'] = result.summary.get('total_issues', 0)
        print(json.dumps(output, indent=2))
    else:
        print(format_text_output(result))

    return 0


if __name__ == "__main__":
    sys.exit(main())
