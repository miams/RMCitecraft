# Citation Compliance Tools

Command-line tools for analyzing and fixing Evidence Explained citation compliance issues in RootsMagic Free Form sources.

## Issue Types

| Priority | Code | Issue | Automation |
|----------|------|-------|------------|
| P1 | `P1_DOUBLE_SPACES` | Multiple consecutive spaces | Fully Automated |
| P2 | `P2_MISSING_PERIOD` | Missing terminal period | Fully Automated |
| P3 | `P3_FN_EQUALS_SF` | Footnote = Short Footnote | AI-Assisted |
| P4 | `P4_FN_EQUALS_BIB` | Footnote = Bibliography | AI-Assisted |
| P5 | `P5_MISSING_ACCESS_DATE` | URL without access date | AI-Assisted |
| P6 | `P6_EMPTY_*` | Empty citation field | Human Review |

## Quick Start

```bash
# 1. Analyze all sources
uv run python scripts/citation_compliance/analyze_compliance.py --output report.json

# 2. Fix simple issues (Tier 1)
uv run python scripts/citation_compliance/fix_simple_issues.py --dry-run
uv run python scripts/citation_compliance/fix_simple_issues.py --apply

# 3. Generate transformation proposals (Tier 2)
uv run python scripts/citation_compliance/transform_citations.py --output proposals.json

# 4. Review and apply proposals
# Edit proposals.json to change status from 'pending' to 'approved'
uv run python scripts/citation_compliance/apply_proposals.py proposals.json --apply

# 5. Verify results
uv run python scripts/citation_compliance/verify_compliance.py --baseline report.json
```

## Tools

### analyze_compliance.py

Scans all Free Form sources and identifies compliance issues.

```bash
# Basic analysis
uv run python scripts/citation_compliance/analyze_compliance.py

# Save detailed report
uv run python scripts/citation_compliance/analyze_compliance.py -o report.json --show-details

# Filter by source type
uv run python scripts/citation_compliance/analyze_compliance.py --source-type "Fed Census"

# Filter by issue type
uv run python scripts/citation_compliance/analyze_compliance.py --issue-type P3_FN_EQUALS_SF
```

### fix_simple_issues.py

Fixes Tier 1 issues that can be corrected programmatically:
- Double spaces → single space
- Non-breaking spaces → regular spaces
- Missing terminal periods

```bash
# Preview mode (default)
uv run python scripts/citation_compliance/fix_simple_issues.py --dry-run

# Apply fixes
uv run python scripts/citation_compliance/fix_simple_issues.py --apply

# Filter by source type
uv run python scripts/citation_compliance/fix_simple_issues.py --apply --source-type "Fed Census"

# Limit number of sources
uv run python scripts/citation_compliance/fix_simple_issues.py --apply --limit 100
```

### transform_citations.py

Generates transformation proposals for FN→SF and FN→BIB issues.

```bash
# Generate proposals
uv run python scripts/citation_compliance/transform_citations.py -o proposals.json

# Filter by issue type
uv run python scripts/citation_compliance/transform_citations.py --issue-type P3_FN_EQUALS_SF

# Filter by confidence
uv run python scripts/citation_compliance/transform_citations.py --min-confidence 0.8
```

Output format (`proposals.json`):
```json
{
  "proposals": [
    {
      "source_id": 123,
      "source_name": "Fed Census: 1930, ...",
      "issue_type": "P3_FN_EQUALS_SF",
      "original": {
        "footnote": "...",
        "short_footnote": "..."
      },
      "proposed": {
        "short_footnote": "..."
      },
      "confidence": {
        "short_footnote": 0.85
      },
      "status": "pending"  // Change to "approved" to apply
    }
  ]
}
```

### apply_proposals.py

Applies approved transformation proposals to the database.

```bash
# Preview what would be applied
uv run python scripts/citation_compliance/apply_proposals.py proposals.json --dry-run

# Apply approved proposals
uv run python scripts/citation_compliance/apply_proposals.py proposals.json --apply

# Auto-approve high-confidence proposals
uv run python scripts/citation_compliance/apply_proposals.py proposals.json --apply --auto-approve-confidence 0.9
```

### verify_compliance.py

Verifies compliance after fixes and tracks progress.

```bash
# Basic verification
uv run python scripts/citation_compliance/verify_compliance.py

# Compare against baseline
uv run python scripts/citation_compliance/verify_compliance.py --baseline report.json

# Show remaining issues
uv run python scripts/citation_compliance/verify_compliance.py --show-remaining

# Save verification report
uv run python scripts/citation_compliance/verify_compliance.py -o verification.json
```

## Workflow

### Tier 1: Automated Fixes

1. Run analysis to get baseline
2. Apply simple fixes (double spaces, periods)
3. Verify improvements

```bash
uv run python scripts/citation_compliance/analyze_compliance.py -o baseline.json
uv run python scripts/citation_compliance/fix_simple_issues.py --apply
uv run python scripts/citation_compliance/verify_compliance.py --baseline baseline.json
```

### Tier 2: Transformation Proposals

1. Generate proposals for FN=SF/FN=BIB issues
2. Review proposals in JSON file
3. Approve high-confidence proposals
4. Apply approved proposals
5. Verify results

```bash
uv run python scripts/citation_compliance/transform_citations.py -o proposals.json
# Edit proposals.json - change status to "approved"
uv run python scripts/citation_compliance/apply_proposals.py proposals.json --apply
uv run python scripts/citation_compliance/verify_compliance.py
```

### Batch Auto-Approval

For high-confidence proposals, use auto-approval:

```bash
uv run python scripts/citation_compliance/apply_proposals.py proposals.json \
    --apply --auto-approve-confidence 0.85
```

## Safety Features

- **Dry-run by default**: All scripts preview changes without modifying
- **Backups**: Changes create JSON backups in `backup/` directory
- **Rollback**: Backup files contain original values for manual rollback
- **Audit trail**: Compliance service tracks all sessions and changes

## Files Created

| File | Purpose |
|------|---------|
| `scripts/citation_compliance/analyze_compliance.py` | Analysis CLI |
| `scripts/citation_compliance/fix_simple_issues.py` | Tier 1 fixer |
| `scripts/citation_compliance/transform_citations.py` | Proposal generator |
| `scripts/citation_compliance/apply_proposals.py` | Proposal applier |
| `scripts/citation_compliance/verify_compliance.py` | Verification |
| `src/rmcitecraft/services/citation_transformer.py` | Transformation logic |
| `src/rmcitecraft/services/citation_compliance_service.py` | Orchestration |
| `migrations/006_create_compliance_batch_tables.sql` | State tracking |
