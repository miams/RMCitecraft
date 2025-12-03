"""
Census page boundary edge detection.

Detects when census persons appear near page boundaries (first or last lines),
which indicates the family may span multiple pages and requires manual review.
"""

from dataclasses import dataclass

# Maximum line numbers by census year
# These represent the last line that can contain census data
LINE_LIMITS = {
    1950: 30,  # 30 lines per sheet (population schedule Form P1)
    1940: 40,  # 40 lines per sheet
    1930: 100, # 100 lines per sheet (but often 50 per side)
    1920: 100, # 100 lines per sheet
    1910: 100, # 100 lines per sheet
    1900: 100, # 100 lines per sheet
    1890: 50,  # 1890 special schedule (most population records lost)
    1880: 50,  # 50 lines per sheet
    1870: 40,  # 40 lines per sheet
    1860: 40,  # 40 lines per sheet
    1850: 40,  # 40 lines per sheet (first census to name all individuals)
    # 1790-1840 only list head of household, no line numbers
}

# Relationships that indicate this is not the head of household
# If a non-head appears on line 1, family likely started on previous page
NON_HEAD_RELATIONSHIPS = {
    "wife", "husband", "spouse",
    "son", "daughter", "child",
    "mother", "father",
    "brother", "sister",
    "grandson", "granddaughter",
    "mother-in-law", "father-in-law",
    "son-in-law", "daughter-in-law",
    "boarder", "lodger", "servant",
    "nephew", "niece", "cousin",
    "other", "inmate", "patient",
}


@dataclass
class EdgeDetectionResult:
    """Result of edge detection analysis."""

    first_line_warning: bool = False
    last_line_warning: bool = False
    warning_message: str = ""
    line_number: int | None = None
    max_line: int | None = None


def detect_edge_conditions(
    line_number: int | None,
    census_year: int,
    relationship_to_head: str | None = None,
) -> EdgeDetectionResult:
    """
    Detect if a person may span page boundaries.

    Args:
        line_number: The line number on the census form (1-based)
        census_year: Census year (1850-1950)
        relationship_to_head: Relationship to head of household (e.g., "Wife", "Son")

    Returns:
        EdgeDetectionResult with warning flags and message
    """
    result = EdgeDetectionResult(line_number=line_number)

    # Can't detect without line number
    if line_number is None:
        return result

    # Get max line for this census year
    max_line = LINE_LIMITS.get(census_year)
    if not max_line:
        # Unknown census year or pre-1850 (no line numbers)
        return result

    result.max_line = max_line

    # Normalize relationship for comparison
    rel_lower = (relationship_to_head or "").lower().strip()

    # Check for first line warning
    # Line 1 with non-head relationship = family likely started on previous page
    if line_number == 1:
        result.first_line_warning = True
        if rel_lower in NON_HEAD_RELATIONSHIPS:
            result.warning_message = (
                f"Line 1: '{relationship_to_head}' relationship suggests "
                f"family may have started on previous page"
            )
        else:
            result.warning_message = (
                "Line 1: Family may have started on previous page"
            )

    # Check for last line warning
    # Within 2 lines of max = family may continue on next page
    elif line_number >= max_line - 2:
        result.last_line_warning = True
        result.warning_message = (
            f"Line {line_number}/{max_line}: Family may continue on next page"
        )

    return result


def is_edge_line(line_number: int | None, census_year: int) -> bool:
    """Quick check if line number is an edge line.

    Args:
        line_number: The line number on the census form
        census_year: Census year (1850-1950)

    Returns:
        True if line is at start or end of page
    """
    if line_number is None:
        return False

    max_line = LINE_LIMITS.get(census_year)
    if not max_line:
        return False

    return line_number == 1 or line_number >= max_line - 2


def get_max_line_for_year(census_year: int) -> int | None:
    """Get the maximum line number for a census year.

    Args:
        census_year: Census year (1850-1950)

    Returns:
        Maximum line number, or None if unknown
    """
    return LINE_LIMITS.get(census_year)
