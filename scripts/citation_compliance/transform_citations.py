#!/usr/bin/env python3
"""Generate transformation proposals for citations needing FN→SF or FN→BIB fixes.

This script identifies sources where footnote equals short footnote (FN=SF) or
footnote equals bibliography (FN=BIB), then generates transformation proposals
using the CitationTransformer.

Proposals are saved to a JSON file for review before applying.

Usage:
    uv run python scripts/citation_compliance/transform_citations.py
    uv run python scripts/citation_compliance/transform_citations.py --source-type "Fed Census" -o proposals.json
    uv run python scripts/citation_compliance/transform_citations.py --issue-type P3_FN_EQUALS_SF
"""

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.rmcitecraft.database.connection import connect_rmtree
from src.rmcitecraft.services.citation_transformer import CitationTransformer, TransformationResult


@dataclass
class TransformationProposal:
    """A proposed transformation for a source."""
    source_id: int
    source_name: str
    source_type: str
    issue_type: str  # 'P3_FN_EQUALS_SF' or 'P4_FN_EQUALS_BIB'

    original_footnote: str
    original_short_footnote: str
    original_bibliography: str

    proposed_short_footnote: Optional[str] = None
    proposed_bibliography: Optional[str] = None

    sf_confidence: float = 0.0
    bib_confidence: float = 0.0
    sf_notes: list[str] = field(default_factory=list)
    bib_notes: list[str] = field(default_factory=list)

    status: str = 'pending'  # 'pending', 'approved', 'rejected', 'modified'
    review_notes: str = ''

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'source_id': self.source_id,
            'source_name': self.source_name,
            'source_type': self.source_type,
            'issue_type': self.issue_type,
            'original': {
                'footnote': self.original_footnote,
                'short_footnote': self.original_short_footnote,
                'bibliography': self.original_bibliography,
            },
            'proposed': {
                'short_footnote': self.proposed_short_footnote,
                'bibliography': self.proposed_bibliography,
            },
            'confidence': {
                'short_footnote': self.sf_confidence,
                'bibliography': self.bib_confidence,
            },
            'notes': {
                'short_footnote': self.sf_notes,
                'bibliography': self.bib_notes,
            },
            'status': self.status,
            'review_notes': self.review_notes,
        }


def extract_field_from_blob(fields_text: str, field_name: str) -> str:
    """Extract a field value from the SourceTable.Fields XML text."""
    if not fields_text:
        return ""
    pattern = rf'<Name>{field_name}</Name>\s*<Value>(.*?)</Value>'
    match = re.search(pattern, fields_text, re.DOTALL)
    return match.group(1).strip() if match else ""


def extract_source_type(source_name: str) -> str:
    """Extract source type from source name."""
    if ':' in source_name:
        return source_name.split(':')[0].strip()
    return "Other"


def find_sources_needing_transformation(cursor, source_type_filter: str = None,
                                         issue_type: str = None) -> list[dict]:
    """Find sources with FN=SF or FN=BIB issues.

    Args:
        cursor: Database cursor
        source_type_filter: Optional filter for source type
        issue_type: Optional filter for issue type ('P3_FN_EQUALS_SF' or 'P4_FN_EQUALS_BIB')

    Returns:
        List of source dictionaries with issue information
    """
    query = """
        SELECT SourceID, Name, CAST(Fields AS TEXT) as fields_text
        FROM SourceTable
        WHERE TemplateID = 0
          AND Fields IS NOT NULL
    """

    if source_type_filter:
        query += f" AND Name LIKE '{source_type_filter}%'"

    query += " ORDER BY Name"

    cursor.execute(query)
    rows = cursor.fetchall()

    sources_needing_work = []

    for source_id, name, fields_text in rows:
        footnote = extract_field_from_blob(fields_text, 'Footnote')
        short_footnote = extract_field_from_blob(fields_text, 'ShortFootnote')
        bibliography = extract_field_from_blob(fields_text, 'Bibliography')

        # Decode entities for comparison
        fn_decoded = footnote.replace('&lt;', '<').replace('&gt;', '>')
        sf_decoded = short_footnote.replace('&lt;', '<').replace('&gt;', '>')
        bib_decoded = bibliography.replace('&lt;', '<').replace('&gt;', '>')

        issues = []

        # Check FN = SF
        if fn_decoded and sf_decoded and fn_decoded.strip() == sf_decoded.strip():
            issues.append('P3_FN_EQUALS_SF')

        # Check FN = BIB
        if fn_decoded and bib_decoded and fn_decoded.strip() == bib_decoded.strip():
            issues.append('P4_FN_EQUALS_BIB')

        # Filter by issue type if specified
        if issue_type and issue_type not in issues:
            continue

        if issues:
            sources_needing_work.append({
                'source_id': source_id,
                'name': name,
                'fields_text': fields_text,
                'footnote': footnote,
                'short_footnote': short_footnote,
                'bibliography': bibliography,
                'issues': issues,
            })

    return sources_needing_work


def generate_proposals(sources: list[dict], transformer: CitationTransformer) -> list[TransformationProposal]:
    """Generate transformation proposals for sources.

    Args:
        sources: List of source dictionaries
        transformer: CitationTransformer instance

    Returns:
        List of TransformationProposal objects
    """
    proposals = []

    for source in sources:
        footnote = source['footnote']
        source_type = extract_source_type(source['name'])

        # Determine what transformations are needed
        needs_sf = 'P3_FN_EQUALS_SF' in source['issues']
        needs_bib = 'P4_FN_EQUALS_BIB' in source['issues']

        # Primary issue type for the proposal
        issue_type = source['issues'][0]

        proposal = TransformationProposal(
            source_id=source['source_id'],
            source_name=source['name'],
            source_type=source_type,
            issue_type=issue_type,
            original_footnote=footnote,
            original_short_footnote=source['short_footnote'],
            original_bibliography=source['bibliography'],
        )

        # Generate short footnote if needed
        if needs_sf:
            sf_result = transformer.generate_short_footnote(footnote, source_type.lower() if source_type == 'Fed Census' else 'auto')
            proposal.proposed_short_footnote = sf_result.transformed
            proposal.sf_confidence = sf_result.confidence
            proposal.sf_notes = sf_result.notes

        # Generate bibliography if needed
        if needs_bib:
            bib_result = transformer.generate_bibliography(footnote, source_type.lower() if source_type == 'Fed Census' else 'auto')
            proposal.proposed_bibliography = bib_result.transformed
            proposal.bib_confidence = bib_result.confidence
            proposal.bib_notes = bib_result.notes

        proposals.append(proposal)

    return proposals


def main():
    parser = argparse.ArgumentParser(
        description='Generate transformation proposals for citations with FN=SF or FN=BIB issues.'
    )
    parser.add_argument(
        '--db',
        default='data/Iiams.rmtree',
        help='Path to RootsMagic database'
    )
    parser.add_argument(
        '--output', '-o',
        default='proposals.json',
        help='Output JSON file for proposals'
    )
    parser.add_argument(
        '--source-type',
        help='Filter to specific source type (e.g., "Fed Census")'
    )
    parser.add_argument(
        '--issue-type',
        choices=['P3_FN_EQUALS_SF', 'P4_FN_EQUALS_BIB'],
        help='Filter to specific issue type'
    )
    parser.add_argument(
        '--min-confidence',
        type=float,
        default=0.0,
        help='Minimum confidence threshold (0.0-1.0)'
    )
    parser.add_argument(
        '--show-samples',
        type=int,
        default=5,
        help='Number of sample proposals to display'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("  CITATION TRANSFORMATION PROPOSALS")
    print("  Generate FN→SF and FN→BIB transformations")
    print("=" * 70)
    print()

    # Connect to database
    conn = connect_rmtree(args.db)
    cursor = conn.cursor()

    # Find sources needing transformation
    print("Finding sources with FN=SF or FN=BIB issues...")
    sources = find_sources_needing_transformation(
        cursor,
        source_type_filter=args.source_type,
        issue_type=args.issue_type
    )
    conn.close()

    print(f"Found {len(sources)} sources needing transformation")
    print()

    if not sources:
        print("No sources need transformation.")
        return

    # Generate proposals
    print("Generating transformation proposals...")
    transformer = CitationTransformer()
    proposals = generate_proposals(sources, transformer)

    # Filter by confidence if specified
    if args.min_confidence > 0:
        filtered = []
        for p in proposals:
            min_conf = min(
                p.sf_confidence if p.proposed_short_footnote else 1.0,
                p.bib_confidence if p.proposed_bibliography else 1.0
            )
            if min_conf >= args.min_confidence:
                filtered.append(p)
        proposals = filtered
        print(f"Filtered to {len(proposals)} proposals with confidence >= {args.min_confidence}")

    # Display summary
    print()
    print("=" * 70)
    print("  PROPOSAL SUMMARY")
    print("=" * 70)
    print()

    # Count by issue type
    fn_sf_count = sum(1 for p in proposals if p.issue_type == 'P3_FN_EQUALS_SF')
    fn_bib_count = sum(1 for p in proposals if p.issue_type == 'P4_FN_EQUALS_BIB')

    print(f"Total proposals:      {len(proposals)}")
    print(f"  FN = SF issues:     {fn_sf_count}")
    print(f"  FN = BIB issues:    {fn_bib_count}")
    print()

    # Count by source type
    by_source_type: dict[str, int] = {}
    for p in proposals:
        by_source_type[p.source_type] = by_source_type.get(p.source_type, 0) + 1

    print("By source type:")
    for st, count in sorted(by_source_type.items(), key=lambda x: -x[1]):
        print(f"  {st:25} {count}")
    print()

    # Confidence distribution
    high_conf = sum(1 for p in proposals
                    if min(p.sf_confidence or 1.0, p.bib_confidence or 1.0) >= 0.8)
    med_conf = sum(1 for p in proposals
                   if 0.5 <= min(p.sf_confidence or 1.0, p.bib_confidence or 1.0) < 0.8)
    low_conf = sum(1 for p in proposals
                   if min(p.sf_confidence or 1.0, p.bib_confidence or 1.0) < 0.5)

    print("Confidence distribution:")
    print(f"  High (>= 0.8):   {high_conf}")
    print(f"  Medium (0.5-0.8): {med_conf}")
    print(f"  Low (< 0.5):     {low_conf}")
    print()

    # Show sample proposals
    if args.show_samples and proposals:
        print("=" * 70)
        print(f"  SAMPLE PROPOSALS (first {min(args.show_samples, len(proposals))})")
        print("=" * 70)
        print()

        for proposal in proposals[:args.show_samples]:
            print(f"SourceID {proposal.source_id}: {proposal.source_name[:55]}")
            print(f"  Issue: {proposal.issue_type}")
            print()

            if proposal.proposed_short_footnote:
                print("  ORIGINAL SHORT FOOTNOTE:")
                print(f"    {proposal.original_short_footnote[:100]}...")
                print("  PROPOSED SHORT FOOTNOTE (confidence: {:.2f}):".format(proposal.sf_confidence))
                print(f"    {proposal.proposed_short_footnote[:100]}...")
                if proposal.sf_notes:
                    print(f"  Notes: {', '.join(proposal.sf_notes)}")
                print()

            if proposal.proposed_bibliography:
                print("  ORIGINAL BIBLIOGRAPHY:")
                print(f"    {proposal.original_bibliography[:100]}...")
                print("  PROPOSED BIBLIOGRAPHY (confidence: {:.2f}):".format(proposal.bib_confidence))
                print(f"    {proposal.proposed_bibliography[:100]}...")
                if proposal.bib_notes:
                    print(f"  Notes: {', '.join(proposal.bib_notes)}")
                print()

            print("-" * 50)
            print()

    # Save proposals
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_data = {
        'timestamp': datetime.now().isoformat(),
        'database': args.db,
        'filters': {
            'source_type': args.source_type,
            'issue_type': args.issue_type,
            'min_confidence': args.min_confidence,
        },
        'summary': {
            'total_proposals': len(proposals),
            'fn_sf_issues': fn_sf_count,
            'fn_bib_issues': fn_bib_count,
            'by_source_type': by_source_type,
            'confidence_high': high_conf,
            'confidence_medium': med_conf,
            'confidence_low': low_conf,
        },
        'proposals': [p.to_dict() for p in proposals]
    }

    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"Proposals saved to: {output_path}")
    print()
    print("=" * 70)
    print("  NEXT STEPS")
    print("=" * 70)
    print()
    print("1. Review proposals in the JSON file")
    print("2. Edit 'status' field: 'approved', 'rejected', or 'modified'")
    print("3. For 'modified' status, edit the proposed values")
    print("4. Run apply_proposals.py to apply approved changes")
    print()


if __name__ == '__main__':
    main()
