#!/usr/bin/env python3
"""
Census Quality Check Tool for RMCitecraft.

Performs comprehensive quality checks on Federal Census sources (1790-1950)
in a RootsMagic database. Designed to be used as a tool by Claude Code.

Each census year has explicit, self-contained validation rules with no
implicit assumptions or inheritance between years.

Checks include:
- Source Name format and consistency
- Footnote completeness and format (including schedule type requirement)
- Short Footnote completeness and format
- Bibliography format
- Cross-field consistency (state, county, ED, sheet matching)
- Independent city validation
- Citation Quality settings
- Media attachments

Usage:
    python scripts/census_quality_check.py 1940
    python scripts/census_quality_check.py 1940 --format json
    python scripts/census_quality_check.py 1940 --format text --detailed
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
import sys
from pathlib import Path

from census_quality import (
    format_compact_output,
    format_text_output,
    run_quality_check,
)

# Standard population schedule years
ALL_CENSUS_YEARS: list[int | str] = [
    1790, 1800, 1810, 1820, 1830, 1840, 1850, 1860, 1870, 1880,
    1900, 1910, 1920, 1930, 1940, 1950
]

# Slave schedule years (separate from population schedules)
SLAVE_SCHEDULE_YEARS = ["1850-slave", "1860-slave"]

# Mortality schedule years
MORTALITY_SCHEDULE_YEARS = ["1850-mortality"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Census Quality Check - Validate Federal Census sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Single year:
    %(prog)s 1880 --check-media --detailed

  Multiple years:
    %(prog)s 1880 1900 1910 1920 --format compact

  All census years:
    %(prog)s all --format compact

  Slave schedules:
    %(prog)s 1860-slave --format compact
    %(prog)s 1850-slave 1860-slave --detailed

  Mortality schedules:
    %(prog)s 1850-mortality --format compact

  All years with media check:
    %(prog)s all --check-media --format compact
""",
    )

    parser.add_argument(
        "years",
        nargs="+",
        help="Census year(s) to check (1790-1950), 'all' for all years, slave schedules (1850-slave, 1860-slave), or mortality schedules (1850-mortality)",
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/Iiams.rmtree"),
        help="Path to RootsMagic database",
    )

    parser.add_argument(
        "--format",
        choices=["json", "text", "compact"],
        default="text",
        help="Output format: text (visual), compact (token-efficient), json (structured)",
    )

    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show all issues with full details",
    )

    parser.add_argument(
        "--include-all-issues",
        action="store_true",
        help="Include informational issues (multiple media, etc.)",
    )

    parser.add_argument(
        "--check-media",
        action="store_true",
        help="Validate media files: check linked files exist, find orphaned files (slower)",
    )

    args = parser.parse_args()

    # Parse years - handle "all" keyword and special schedule types
    years_to_check: list[int | str] = []
    for y in args.years:
        if y.lower() == "all":
            years_to_check = list(ALL_CENSUS_YEARS)
            break
        # Check for slave schedule format (e.g., "1860-slave")
        if y.endswith("-slave"):
            if y in SLAVE_SCHEDULE_YEARS:
                years_to_check.append(y)
            else:
                print(f"Error: Invalid slave schedule year: {y}", file=sys.stderr)
                print(
                    f"Valid slave schedule years: {', '.join(SLAVE_SCHEDULE_YEARS)}",
                    file=sys.stderr,
                )
                return 1
        # Check for mortality schedule format (e.g., "1850-mortality")
        elif y.endswith("-mortality"):
            if y in MORTALITY_SCHEDULE_YEARS:
                years_to_check.append(y)
            else:
                print(f"Error: Invalid mortality schedule year: {y}", file=sys.stderr)
                print(
                    f"Valid mortality schedule years: {', '.join(MORTALITY_SCHEDULE_YEARS)}",
                    file=sys.stderr,
                )
                return 1
        else:
            try:
                year = int(y)
                if year < 1790 or year > 1950 or year % 10 != 0 or year == 1890:
                    print(f"Error: Invalid census year: {year}", file=sys.stderr)
                    print(
                        "Valid years: 1790, 1800, ..., 1880, 1900, ..., 1950 (no 1890)",
                        file=sys.stderr,
                    )
                    print(
                        f"For slave schedules, use: {', '.join(SLAVE_SCHEDULE_YEARS)}",
                        file=sys.stderr,
                    )
                    print(
                        f"For mortality schedules, use: {', '.join(MORTALITY_SCHEDULE_YEARS)}",
                        file=sys.stderr,
                    )
                    return 1
                years_to_check.append(year)
            except ValueError:
                print(f"Error: Invalid year value: {y}", file=sys.stderr)
                return 1

    # Show detailed tables when --detailed or --include-all-issues is used
    show_detailed = args.detailed or args.include_all_issues

    # Run check for each year
    all_results = []
    for year in years_to_check:
        result = run_quality_check(args.db, year, args.include_all_issues, args.check_media)

        if "error" in result:
            print(f"Error for {year}: {result['error']}", file=sys.stderr)
            continue

        all_results.append(result)

        if args.format == "json":
            print(json.dumps(result, indent=2))
        elif args.format == "compact":
            print(format_compact_output(result, show_detailed))
        else:
            print(format_text_output(result, show_detailed))

    return 0 if all_results else 1


if __name__ == "__main__":
    sys.exit(main())
