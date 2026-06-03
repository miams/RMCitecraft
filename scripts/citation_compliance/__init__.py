"""Citation compliance CLI tools.

This package provides command-line tools for analyzing and fixing
citation compliance issues in RootsMagic Free Form sources.

Tools:
- analyze_compliance.py: Scan sources for compliance issues
- fix_simple_issues.py: Fix Tier 1 issues (double spaces, missing periods)
- transform_citations.py: Generate FN→SF and FN→BIB transformation proposals
- apply_proposals.py: Apply approved transformation proposals
- verify_compliance.py: Verify fixes and track progress

Usage:
    uv run python scripts/citation_compliance/analyze_compliance.py
    uv run python scripts/citation_compliance/fix_simple_issues.py --dry-run
    uv run python scripts/citation_compliance/transform_citations.py -o proposals.json
    uv run python scripts/citation_compliance/apply_proposals.py proposals.json --apply
    uv run python scripts/citation_compliance/verify_compliance.py
"""
