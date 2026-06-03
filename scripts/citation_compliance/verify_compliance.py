#!/usr/bin/env python3
"""Verify compliance after applying fixes.

This script re-scans sources after fixes have been applied to verify
that the issues have been resolved and no regressions occurred.

Compares current state against a baseline report (if provided) to show
improvement metrics.

Usage:
    uv run python scripts/citation_compliance/verify_compliance.py
    uv run python scripts/citation_compliance/verify_compliance.py --baseline report.json
    uv run python scripts/citation_compliance/verify_compliance.py --source-type "Fed Census"
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.rmcitecraft.database.connection import connect_rmtree


def extract_field_from_blob(fields_text: str, field_name: str) -> str:
    """Extract a field value from the SourceTable.Fields XML text."""
    if not fields_text:
        return ""
    pattern = rf'<Name>{field_name}</Name>\s*<Value>(.*?)</Value>'
    match = re.search(pattern, fields_text, re.DOTALL)
    return match.group(1).strip() if match else ""


def check_compliance(fields_text: str, source_name: str) -> dict[str, Any]:
    """Check a single source for compliance issues.

    Returns:
        Dictionary with issue flags and details
    """
    footnote = extract_field_from_blob(fields_text, 'Footnote')
    short_footnote = extract_field_from_blob(fields_text, 'ShortFootnote')
    bibliography = extract_field_from_blob(fields_text, 'Bibliography')

    # Decode entities for comparison
    fn = footnote.replace('&lt;', '<').replace('&gt;', '>')
    sf = short_footnote.replace('&lt;', '<').replace('&gt;', '>')
    bib = bibliography.replace('&lt;', '<').replace('&gt;', '>')

    issues = {}

    # P1: Double spaces
    has_double_spaces = (
        bool(re.search(r'  +', fn)) or
        bool(re.search(r'  +', sf)) or
        bool(re.search(r'  +', bib))
    )
    if has_double_spaces:
        issues['P1_DOUBLE_SPACES'] = True

    # P2: Missing period
    for field_name, text in [('footnote', fn), ('bibliography', bib)]:
        text = text.strip()
        if text and not text.endswith('.'):
            if text[-1] in ')"\'' or text[-1].isalnum():
                issues['P2_MISSING_PERIOD'] = True

    # P3: FN = SF
    if fn and sf and fn.strip() == sf.strip():
        issues['P3_FN_EQUALS_SF'] = True

    # P4: FN = BIB
    if fn and bib and fn.strip() == bib.strip():
        issues['P4_FN_EQUALS_BIB'] = True

    # P5: Missing access date (for sources with URLs)
    has_url = 'http' in fn.lower() or 'familysearch' in fn.lower()
    has_accessed = bool(re.search(r'accessed\s+\d{1,2}\s+\w+\s+\d{4}', fn, re.IGNORECASE))
    has_alt_accessed = bool(re.search(r'accessed\s+\w+\s+\d{1,2},?\s+\d{4}', fn, re.IGNORECASE))
    if has_url and not has_accessed and not has_alt_accessed:
        issues['P5_MISSING_ACCESS_DATE'] = True

    # P6: Empty citations
    if not fn.strip():
        issues['P6_EMPTY_FN'] = True
    if not sf.strip():
        issues['P6_EMPTY_SF'] = True
    if not bib.strip():
        issues['P6_EMPTY_BIB'] = True

    return {
        'has_issues': len(issues) > 0,
        'issues': issues,
        'issue_count': len(issues),
    }


def load_baseline(filepath: str) -> Optional[dict]:
    """Load baseline report for comparison."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def extract_source_type(source_name: str) -> str:
    """Extract source type from source name."""
    if ':' in source_name:
        return source_name.split(':')[0].strip()
    return "Other"


def main():
    parser = argparse.ArgumentParser(
        description='Verify compliance after applying fixes.'
    )
    parser.add_argument(
        '--db',
        default='data/Iiams.rmtree',
        help='Path to RootsMagic database'
    )
    parser.add_argument(
        '--baseline', '-b',
        help='Baseline report JSON file for comparison'
    )
    parser.add_argument(
        '--output', '-o',
        help='Output verification report to JSON file'
    )
    parser.add_argument(
        '--source-type',
        help='Filter to specific source type'
    )
    parser.add_argument(
        '--show-remaining',
        action='store_true',
        help='Show details of remaining issues'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("  COMPLIANCE VERIFICATION")
    print("=" * 70)
    print()

    # Load baseline if provided
    baseline = None
    if args.baseline:
        baseline = load_baseline(args.baseline)
        if baseline:
            print(f"Baseline loaded: {args.baseline}")
            print(f"  Baseline date: {baseline.get('timestamp', 'unknown')}")
            print()
        else:
            print(f"Warning: Could not load baseline from {args.baseline}")
            print()

    # Connect to database
    conn = connect_rmtree(args.db)
    cursor = conn.cursor()

    # Query sources
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

    print(f"Verifying {len(rows)} Free Form sources...")
    print()

    # Check each source
    results: dict[str, Any] = {
        'timestamp': datetime.now().isoformat(),
        'database': args.db,
        'total_sources': len(rows),
        'compliant_sources': 0,
        'sources_with_issues': 0,
        'issue_counts': defaultdict(int),
        'by_source_type': defaultdict(lambda: {
            'total': 0,
            'compliant': 0,
            'with_issues': 0,
            'issues': defaultdict(int)
        }),
        'remaining_issues': []
    }

    for source_id, name, fields_text in rows:
        compliance = check_compliance(fields_text, name)
        source_type = extract_source_type(name)

        results['by_source_type'][source_type]['total'] += 1

        if compliance['has_issues']:
            results['sources_with_issues'] += 1
            results['by_source_type'][source_type]['with_issues'] += 1

            for issue in compliance['issues']:
                results['issue_counts'][issue] += 1
                results['by_source_type'][source_type]['issues'][issue] += 1

            results['remaining_issues'].append({
                'source_id': source_id,
                'name': name,
                'source_type': source_type,
                'issues': list(compliance['issues'].keys())
            })
        else:
            results['compliant_sources'] += 1
            results['by_source_type'][source_type]['compliant'] += 1

    conn.close()

    # Convert defaultdicts for display
    results['issue_counts'] = dict(results['issue_counts'])
    results['by_source_type'] = {
        k: {
            'total': v['total'],
            'compliant': v['compliant'],
            'with_issues': v['with_issues'],
            'issues': dict(v['issues'])
        }
        for k, v in results['by_source_type'].items()
    }

    # Display results
    print("=" * 70)
    print("  VERIFICATION RESULTS")
    print("=" * 70)
    print()

    compliance_rate = (results['compliant_sources'] / results['total_sources'] * 100
                       if results['total_sources'] > 0 else 0)

    print(f"Total sources:          {results['total_sources']}")
    print(f"Compliant sources:      {results['compliant_sources']}")
    print(f"Sources with issues:    {results['sources_with_issues']}")
    print(f"Compliance rate:        {compliance_rate:.1f}%")
    print()

    # Issue breakdown
    print("Issues by Type:")
    print("-" * 50)
    issue_order = ['P1_DOUBLE_SPACES', 'P2_MISSING_PERIOD', 'P3_FN_EQUALS_SF',
                   'P4_FN_EQUALS_BIB', 'P5_MISSING_ACCESS_DATE',
                   'P6_EMPTY_FN', 'P6_EMPTY_SF', 'P6_EMPTY_BIB']

    for issue_type in issue_order:
        count = results['issue_counts'].get(issue_type, 0)
        if count > 0:
            print(f"  {issue_type:25} {count:5}")

    print()

    # Comparison with baseline
    if baseline:
        print("=" * 70)
        print("  COMPARISON WITH BASELINE")
        print("=" * 70)
        print()

        baseline_summary = baseline.get('summary', {})
        baseline_issues = baseline_summary.get('issue_counts', {})

        print(f"{'Issue Type':<25} {'Baseline':>10} {'Current':>10} {'Change':>10}")
        print("-" * 60)

        total_baseline = 0
        total_current = 0
        total_resolved = 0

        for issue_type in issue_order:
            bl_count = baseline_issues.get(issue_type, 0)
            cur_count = results['issue_counts'].get(issue_type, 0)
            change = cur_count - bl_count

            total_baseline += bl_count
            total_current += cur_count
            if change < 0:
                total_resolved += abs(change)

            change_str = f"{change:+d}" if change != 0 else "0"
            if bl_count > 0 or cur_count > 0:
                print(f"  {issue_type:<23} {bl_count:>10} {cur_count:>10} {change_str:>10}")

        print("-" * 60)
        print(f"  {'TOTAL':<23} {total_baseline:>10} {total_current:>10} {total_current - total_baseline:+10}")
        print()

        if total_resolved > 0:
            print(f"Issues resolved: {total_resolved}")
            resolution_rate = (total_resolved / total_baseline * 100) if total_baseline > 0 else 0
            print(f"Resolution rate: {resolution_rate:.1f}%")
        print()

    # By source type
    print("=" * 70)
    print("  BY SOURCE TYPE")
    print("=" * 70)
    print()

    print(f"{'Source Type':<25} {'Total':>8} {'Compliant':>10} {'Issues':>8} {'Rate':>8}")
    print("-" * 65)

    for source_type in sorted(results['by_source_type'].keys()):
        stats = results['by_source_type'][source_type]
        rate = (stats['compliant'] / stats['total'] * 100) if stats['total'] > 0 else 0
        print(f"  {source_type:<23} {stats['total']:>8} {stats['compliant']:>10} {stats['with_issues']:>8} {rate:>7.1f}%")

    print()

    # Show remaining issues if requested
    if args.show_remaining and results['remaining_issues']:
        print("=" * 70)
        print("  REMAINING ISSUES (first 20)")
        print("=" * 70)
        print()

        for item in results['remaining_issues'][:20]:
            print(f"SourceID {item['source_id']}: {item['name'][:50]}")
            print(f"  Issues: {', '.join(item['issues'])}")
            print()

        if len(results['remaining_issues']) > 20:
            print(f"... and {len(results['remaining_issues']) - 20} more")
        print()

    # Save output
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Verification report saved to: {output_path}")
        print()

    print("=" * 70)
    print("  VERIFICATION COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    main()
