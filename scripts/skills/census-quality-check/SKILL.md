# Census Quality Check Skill

A comprehensive validation tool for Federal Census source records in RootsMagic databases.

## Overview

This skill validates census source records against Evidence Explained citation standards and FamilySearch official naming conventions. It performs:

1. **Component Extraction**: Parses source name, footnote, short footnote, and bibliography fields
2. **Cross-Validation**: Ensures consistency between fields (ED, sheet, line)
3. **Format Validation**: Verifies year-specific citation requirements
4. **Issue Detection**: Finds duplicates, orphans, typos, and media anomalies

## Usage

```bash
# Check a specific census year
python scripts/census_quality_check_v2.py 1930

# Check multiple years
python scripts/census_quality_check_v2.py 1930 1940 1950

# Check all supported years (1880-1950)
python scripts/census_quality_check_v2.py --all

# Output as Markdown
python scripts/census_quality_check_v2.py 1930 --format md

# Output as JSON
python scripts/census_quality_check_v2.py 1930 --format json

# Custom database path
python scripts/census_quality_check_v2.py 1930 --db /path/to/database.rmtree
```

## Supported Census Years

| Year Range | Format Details |
|------------|----------------|
| 1790-1870 | Pre-ED era, page/sheet format only |
| 1880 | ED introduced, simple format |
| 1900-1920 | ED required, sheet/line/family format |
| 1930 | Simple ED, `[citing enumeration district (ED) XXX,` format |
| 1940 | Compound ED (XX-YY), `[ED XX-YY,` format |
| 1950 | Compound ED, allows stamp OR sheet format |

## Issue Categories

| Category | Description |
|----------|-------------|
| TITLE | Wrong FamilySearch title format |
| FORMAT | Citation format issues (double spaces, missing periods) |
| MISSING | Missing required fields (ED, sheet, line) |
| CONSISTENCY | Mismatches between source name and footnote |
| DUPLICATE | Multiple sources for same census entry |
| MEDIA | Media attachment anomalies |
| QUALITY | Citation quality not set to "PDO" |
| TYPO | Spelling errors or typos |

## Issue Severities

- **ERROR**: Must be fixed for proper citations
- **WARNING**: Should be reviewed and likely fixed
- **INFO**: Informational only (e.g., multiple media)

## Output Formats

### Text (default)
Plain text summary with statistics and sample issues.

### Markdown (--format md)
Formatted tables suitable for documentation or reports.

### JSON (--format json)
Machine-readable format with full issue details for programmatic processing.

## FamilySearch Title Standards

The script validates against official FamilySearch collection titles:

| Year | Bibliography Title | Footnote Title |
|------|-------------------|----------------|
| 1930 | "United States, Census, 1930." | "United States, Census, 1930," |
| 1940 | "United States, Census, 1940." | "United States, Census, 1940," |
| 1950 | "United States, Census, 1950." | "United States, Census, 1950," |

Note: Bibliography uses trailing period; footnote uses trailing comma.

## Example Output

```
======================================================================
CENSUS QUALITY CHECK: 1930
======================================================================

Total Sources: 548
Total Issues: 74

Issues by Severity:
  error: 61
  warning: 12
  info: 1

Issues by Type:
  missing_sheet: 41
  ed_number_missing: 9
  ed_mismatch: 5
  ...

Sample Issues (first 15):
  [ERROR] Source 772: ed_number_missing
    ED number missing after 'E.D.' abbreviation
    Current: 1930 U.S. census, Denver Co., Colo., E.D. , sheet 10B...
    Fix: Add ED number after 'E.D.'
```

## Related Fix Scripts

When issues are found, use these companion scripts to apply fixes:

| Script | Purpose |
|--------|---------|
| `fix_census_titles.py` | Standardize bibliography/footnote titles to FamilySearch format |
| `fix_1930_missing_line.py` | Add line numbers from footnote to source name |
| `fix_1930_bibliography_comma.py` | Fix trailing punctuation in bibliography |

## Architecture

```
census_quality_check_v2.py
├── TextNormalizer      # Quote/whitespace normalization
├── ComponentExtractor  # Regex-based field parsing
├── CensusValidator     # Validation logic per year
├── DatabaseAccess      # SQLite/ICU connection handling
├── YearConfig          # Year-specific configuration
└── ReportFormatter     # Text/Markdown/JSON output
```

## Requirements

- Python 3.11+
- RootsMagic database (.rmtree)
- ICU extension for RMNOCASE collation (sqlite-extension/icu.dylib)

## Integration with Claude

When invoking this skill:

1. Run the quality check script with appropriate year(s)
2. Review the output for issues by severity
3. For ERROR issues, investigate and apply fixes
4. For WARNING issues, review and determine if fixes are needed
5. Use companion fix scripts for bulk corrections
6. Re-run quality check to verify fixes

## Version History

- **v2.0**: Complete rewrite with component extraction, cross-validation, multiple output formats
- **v1.0**: Initial version with basic title and format validation
