#!/usr/bin/env python3
"""Analyze citation compliance across all Free Form sources.

This script scans all TemplateID=0 (Free Form) sources in the RootsMagic database
and checks for Evidence Explained compliance issues.

Issues detected:
- P1: Double spaces
- P2: Missing punctuation (footnote/bibliography ending period)
- P3: FN = SF (footnote same as short footnote)
- P4: FN = BIB (footnote same as bibliography)
- P5: Missing access dates
- P6: Empty citations (footnote, short footnote, or bibliography)

Output: JSON report with issue counts by source type and specific source IDs.

Usage:
    uv run python scripts/citation_compliance/analyze_compliance.py
    uv run python scripts/citation_compliance/analyze_compliance.py --output report.json
    uv run python scripts/citation_compliance/analyze_compliance.py --source-type "Fed Census"
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.rmcitecraft.database.connection import connect_rmtree


@dataclass
class ComplianceIssue:
    """Represents a compliance issue found in a source."""
    issue_type: str
    description: str
    field: str  # 'footnote', 'short_footnote', 'bibliography', or 'all'
    severity: str = 'warning'  # 'error', 'warning', 'info'


@dataclass
class SourceAnalysis:
    """Analysis results for a single source."""
    source_id: int
    name: str
    source_type: str  # Extracted from name (e.g., "Fed Census", "Find a Grave")
    footnote: str = ''
    short_footnote: str = ''
    bibliography: str = ''
    issues: list[ComplianceIssue] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return len(self.issues) > 0

    @property
    def issue_types(self) -> set[str]:
        return {issue.issue_type for issue in self.issues}


def extract_field_from_blob(fields_text: str, field_name: str) -> str:
    """Extract a field value from the SourceTable.Fields XML text.

    Args:
        fields_text: The decoded XML text from SourceTable.Fields
        field_name: Field name to extract ('Footnote', 'ShortFootnote', 'Bibliography')

    Returns:
        The field value, or empty string if not found
    """
    if not fields_text:
        return ""

    pattern = rf'<Name>{field_name}</Name>\s*<Value>(.*?)</Value>'
    match = re.search(pattern, fields_text, re.DOTALL)
    return match.group(1).strip() if match else ""


def extract_source_type(source_name: str) -> str:
    """Extract the source type from the source name.

    Examples:
        "Fed Census: 1930, Greene County..." -> "Fed Census"
        "Find a Grave: John Smith..." -> "Find a Grave"
        "Military Records: WWII Draft..." -> "Military Records"
    """
    if ':' in source_name:
        return source_name.split(':')[0].strip()
    return "Other"


def check_double_spaces(text: str) -> bool:
    """Check if text contains double (or more) consecutive spaces."""
    return bool(re.search(r'  +', text))


def check_missing_period(text: str, field_type: str) -> bool:
    """Check if citation text is missing terminal period.

    Args:
        text: The citation text to check
        field_type: 'footnote', 'short_footnote', or 'bibliography'

    Returns:
        True if period is missing, False otherwise
    """
    if not text:
        return False

    text = text.strip()
    if not text:
        return False

    # Footnotes and bibliographies should end with period
    # Exception: If text ends with closing paren, it might be "(accessed DATE)."
    # which is correct, or just ")" which needs a period
    if text.endswith('.'):
        return False

    # Check for common valid endings that need a period
    # - Ends with ) from "(accessed DATE)"
    # - Ends with alphanumeric
    # - Ends with closing quote
    return text[-1] in ')"\'' or text[-1].isalnum()


def check_access_date_missing(footnote: str) -> bool:
    """Check if footnote is missing an access date.

    Access date patterns:
    - "accessed 5 September 2015"
    - "accessed September 5, 2015"
    - ": accessed DATE"
    """
    if not footnote:
        return False

    # Look for "accessed" keyword with a date
    has_accessed = bool(re.search(r'accessed\s+\d{1,2}\s+\w+\s+\d{4}', footnote, re.IGNORECASE))
    if has_accessed:
        return False

    # Alternative format: "accessed Month DD, YYYY"
    has_alt_accessed = bool(re.search(r'accessed\s+\w+\s+\d{1,2},?\s+\d{4}', footnote, re.IGNORECASE))
    if has_alt_accessed:
        return False

    # If the footnote contains a URL but no access date, it's missing
    has_url = 'http' in footnote.lower() or 'familysearch' in footnote.lower()
    return has_url


def analyze_source(source_id: int, name: str, fields_text: str) -> SourceAnalysis:
    """Analyze a single source for compliance issues.

    Args:
        source_id: The SourceID from RootsMagic
        name: The source name
        fields_text: The decoded Fields BLOB text

    Returns:
        SourceAnalysis with all detected issues
    """
    analysis = SourceAnalysis(
        source_id=source_id,
        name=name,
        source_type=extract_source_type(name)
    )

    # Extract citation fields
    analysis.footnote = extract_field_from_blob(fields_text, 'Footnote')
    analysis.short_footnote = extract_field_from_blob(fields_text, 'ShortFootnote')
    analysis.bibliography = extract_field_from_blob(fields_text, 'Bibliography')

    # Decode HTML entities for comparison (but keep original for display)
    fn_decoded = analysis.footnote.replace('&lt;', '<').replace('&gt;', '>')
    sf_decoded = analysis.short_footnote.replace('&lt;', '<').replace('&gt;', '>')
    bib_decoded = analysis.bibliography.replace('&lt;', '<').replace('&gt;', '>')

    # P1: Double spaces
    for field_name, text in [('footnote', fn_decoded), ('short_footnote', sf_decoded), ('bibliography', bib_decoded)]:
        if check_double_spaces(text):
            analysis.issues.append(ComplianceIssue(
                issue_type='P1_DOUBLE_SPACES',
                description=f'Double spaces found in {field_name}',
                field=field_name,
                severity='warning'
            ))

    # P2: Missing punctuation
    if check_missing_period(fn_decoded, 'footnote'):
        analysis.issues.append(ComplianceIssue(
            issue_type='P2_MISSING_PERIOD',
            description='Footnote missing terminal period',
            field='footnote',
            severity='warning'
        ))

    if check_missing_period(bib_decoded, 'bibliography'):
        analysis.issues.append(ComplianceIssue(
            issue_type='P2_MISSING_PERIOD',
            description='Bibliography missing terminal period',
            field='bibliography',
            severity='warning'
        ))

    # P3: FN = SF (should be different)
    # Skip for empty citations
    if fn_decoded and sf_decoded and fn_decoded.strip() == sf_decoded.strip():
        analysis.issues.append(ComplianceIssue(
            issue_type='P3_FN_EQUALS_SF',
            description='Footnote identical to short footnote',
            field='all',
            severity='error'
        ))

    # P4: FN = BIB (should be different)
    if fn_decoded and bib_decoded and fn_decoded.strip() == bib_decoded.strip():
        analysis.issues.append(ComplianceIssue(
            issue_type='P4_FN_EQUALS_BIB',
            description='Footnote identical to bibliography',
            field='all',
            severity='error'
        ))

    # P5: Missing access dates (for citations with URLs)
    if check_access_date_missing(fn_decoded):
        analysis.issues.append(ComplianceIssue(
            issue_type='P5_MISSING_ACCESS_DATE',
            description='Footnote contains URL but missing access date',
            field='footnote',
            severity='warning'
        ))

    # P6: Empty citations
    if not fn_decoded.strip():
        analysis.issues.append(ComplianceIssue(
            issue_type='P6_EMPTY_CITATION',
            description='Footnote is empty',
            field='footnote',
            severity='error'
        ))

    if not sf_decoded.strip():
        analysis.issues.append(ComplianceIssue(
            issue_type='P6_EMPTY_CITATION',
            description='Short footnote is empty',
            field='short_footnote',
            severity='error'
        ))

    if not bib_decoded.strip():
        analysis.issues.append(ComplianceIssue(
            issue_type='P6_EMPTY_CITATION',
            description='Bibliography is empty',
            field='bibliography',
            severity='error'
        ))

    return analysis


def generate_report(analyses: list[SourceAnalysis]) -> dict[str, Any]:
    """Generate a comprehensive compliance report.

    Args:
        analyses: List of SourceAnalysis objects

    Returns:
        Dictionary with report data
    """
    report: dict[str, Any] = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_sources': len(analyses),
            'sources_with_issues': 0,
            'sources_compliant': 0,
            'issue_counts': defaultdict(int),
            'issue_counts_by_severity': defaultdict(int),
        },
        'by_source_type': defaultdict(lambda: {
            'total': 0,
            'with_issues': 0,
            'issue_counts': defaultdict(int),
            'source_ids': [],
        }),
        'issues_by_type': defaultdict(list),  # issue_type -> [source_ids]
    }

    for analysis in analyses:
        source_type_stats = report['by_source_type'][analysis.source_type]
        source_type_stats['total'] += 1

        if analysis.has_issues:
            report['summary']['sources_with_issues'] += 1
            source_type_stats['with_issues'] += 1

            for issue in analysis.issues:
                report['summary']['issue_counts'][issue.issue_type] += 1
                report['summary']['issue_counts_by_severity'][issue.severity] += 1
                source_type_stats['issue_counts'][issue.issue_type] += 1

                # Track source IDs for each issue type
                if analysis.source_id not in report['issues_by_type'][issue.issue_type]:
                    report['issues_by_type'][issue.issue_type].append(analysis.source_id)
        else:
            report['summary']['sources_compliant'] += 1

    # Convert defaultdicts to regular dicts for JSON serialization
    report['summary']['issue_counts'] = dict(report['summary']['issue_counts'])
    report['summary']['issue_counts_by_severity'] = dict(report['summary']['issue_counts_by_severity'])
    report['by_source_type'] = {
        k: {
            'total': v['total'],
            'with_issues': v['with_issues'],
            'issue_counts': dict(v['issue_counts']),
        }
        for k, v in report['by_source_type'].items()
    }
    report['issues_by_type'] = dict(report['issues_by_type'])

    return report


def main():
    parser = argparse.ArgumentParser(
        description='Analyze citation compliance for Free Form sources.'
    )
    parser.add_argument(
        '--db',
        default='data/Iiams.rmtree',
        help='Path to RootsMagic database'
    )
    parser.add_argument(
        '--output', '-o',
        help='Output JSON file path (default: print to stdout)'
    )
    parser.add_argument(
        '--source-type',
        help='Filter to specific source type (e.g., "Fed Census", "Find a Grave")'
    )
    parser.add_argument(
        '--show-details',
        action='store_true',
        help='Show detailed issues for each source'
    )
    parser.add_argument(
        '--issue-type',
        help='Filter to specific issue type (e.g., "P1_DOUBLE_SPACES", "P3_FN_EQUALS_SF")'
    )
    parser.add_argument(
        '--list-sources',
        action='store_true',
        help='List full source names for sources with issues (for finding in RootsMagic)'
    )
    parser.add_argument(
        '--list-format',
        choices=['full', 'compact', 'csv'],
        default='full',
        help='Format for --list-sources: full (with issues), compact (names only), csv'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("  CITATION COMPLIANCE ANALYSIS")
    print("  Evidence Explained compliance check for Free Form sources")
    print("=" * 70)
    print()

    # Connect to database
    conn = connect_rmtree(args.db)
    cursor = conn.cursor()

    # Query all Free Form sources
    query = """
        SELECT SourceID, Name, CAST(Fields AS TEXT) as fields_text
        FROM SourceTable
        WHERE TemplateID = 0
          AND Fields IS NOT NULL
    """

    if args.source_type:
        query += f" AND Name LIKE '{args.source_type}%'"

    query += " ORDER BY Name"

    cursor.execute(query)
    rows = cursor.fetchall()

    print(f"Analyzing {len(rows)} Free Form sources...")
    print()

    # Analyze each source
    analyses = []
    for source_id, name, fields_text in rows:
        analysis = analyze_source(source_id, name, fields_text)
        analyses.append(analysis)

    conn.close()

    # Generate report
    report = generate_report(analyses)

    # Filter by issue type if specified
    if args.issue_type:
        filtered_ids = set(report['issues_by_type'].get(args.issue_type, []))
        analyses = [a for a in analyses if a.source_id in filtered_ids]

    # Display summary
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print()
    print(f"Total Free Form sources:  {report['summary']['total_sources']}")
    print(f"Sources with issues:      {report['summary']['sources_with_issues']}")
    print(f"Sources compliant:        {report['summary']['sources_compliant']}")
    print()

    # Issue counts
    print("Issues by Type:")
    print("-" * 50)
    issue_order = ['P1_DOUBLE_SPACES', 'P2_MISSING_PERIOD', 'P3_FN_EQUALS_SF',
                   'P4_FN_EQUALS_BIB', 'P5_MISSING_ACCESS_DATE', 'P6_EMPTY_CITATION']

    for issue_type in issue_order:
        count = report['summary']['issue_counts'].get(issue_type, 0)
        source_count = len(report['issues_by_type'].get(issue_type, []))
        if count > 0:
            print(f"  {issue_type:25} {count:5} occurrences in {source_count:4} sources")

    print()

    # Issues by source type
    print("Issues by Source Type:")
    print("-" * 50)
    for source_type in sorted(report['by_source_type'].keys()):
        stats = report['by_source_type'][source_type]
        if stats['with_issues'] > 0:
            print(f"  {source_type:25} {stats['with_issues']:4}/{stats['total']:4} sources with issues")

    print()

    # Show detailed issues if requested
    if args.show_details:
        print("=" * 70)
        print("  DETAILED ISSUES")
        print("=" * 70)
        print()

        for analysis in analyses:
            if analysis.has_issues:
                print(f"SourceID {analysis.source_id}: {analysis.name}")
                for issue in analysis.issues:
                    print(f"  [{issue.severity.upper()}] {issue.issue_type}: {issue.description}")
                print()

    # List source names if requested (for finding in RootsMagic)
    if args.list_sources:
        sources_with_issues = [a for a in analyses if a.has_issues]

        print("=" * 70)
        print(f"  SOURCE NAMES ({len(sources_with_issues)} sources with issues)")
        print("=" * 70)
        print()

        if args.list_format == 'csv':
            # CSV format for import into spreadsheet
            print("SourceID,Source Name,Issue Types")
            for analysis in sources_with_issues:
                # Escape quotes in name for CSV
                name_escaped = analysis.name.replace('"', '""')
                issues_str = "|".join(sorted(analysis.issue_types))
                print(f'{analysis.source_id},"{name_escaped}","{issues_str}"')

        elif args.list_format == 'compact':
            # Just the names, one per line
            for analysis in sources_with_issues:
                print(analysis.name)

        else:  # 'full' format
            # Full format with SourceID and issues
            for analysis in sources_with_issues:
                print(f"[{analysis.source_id}] {analysis.name}")
                print(f"    Issues: {', '.join(sorted(analysis.issue_types))}")
                print()

        print()

    # Save or display report
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Add detailed analysis to report (always include for searchability)
        if args.show_details or args.list_sources:
            report['sources_with_issues'] = [
                {
                    'source_id': a.source_id,
                    'name': a.name,
                    'source_type': a.source_type,
                    'issue_types': sorted(list(a.issue_types)),
                    'issues': [
                        {'type': i.issue_type, 'description': i.description,
                         'field': i.field, 'severity': i.severity}
                        for i in a.issues
                    ]
                }
                for a in analyses if a.has_issues
            ]

        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to: {output_path}")
    else:
        print("(Use --output FILE to save detailed report as JSON)")

    print()
    print("=" * 70)
    print("  ANALYSIS COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    main()
