"""Validation functions for census quality checking.

Contains all check_* functions that validate source names, footnotes,
short footnotes, bibliographies, and cross-field consistency.
"""

import re

from .constants import (
    STATE_ABBREVIATIONS,
    VALID_STATE_NAMES,
    normalize_state_for_comparison,
)
from .extractors import ComponentExtractor
from .models import CensusYearConfig, Issue

# Try to import independent cities module
try:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
    from rmcitecraft.config.independent_cities import (
        get_independent_city,
        is_independent_city,
    )

    HAS_INDEPENDENT_CITIES = True
except ImportError:
    HAS_INDEPENDENT_CITIES = False


def check_source_name(
    source_id: int, name: str, config: CensusYearConfig
) -> list[Issue]:
    """Check source name for issues."""
    issues = []

    # Check prefix
    if not name.startswith(config.source_name_prefix):
        issues.append(
            Issue(
                source_id=source_id,
                issue_type="wrong_source_prefix",
                severity="error",
                message=f"Source name should start with '{config.source_name_prefix}'",
                field="source_name",
                current_value=name[:50],
                expected_value=config.source_name_prefix,
                category="format",
            )
        )

    # Check ED
    if config.source_name_requires_ed:
        if config.source_name_ed_pattern:
            if not re.search(config.source_name_ed_pattern, name):
                issues.append(
                    Issue(
                        source_id=source_id,
                        issue_type="missing_ed",
                        severity="error",
                        message="Missing or malformed ED in source name",
                        field="source_name",
                        current_value=name[:80],
                        category="missing",
                    )
                )

    # Check sheet/stamp/page (1880 uses page, not sheet)
    # Match sheet with optional hyphen: "sheet 6B" or "sheet 6-B"
    has_sheet = bool(re.search(r"sheet\s+\d+-?[AB]?", name, re.IGNORECASE))
    has_stamp = bool(re.search(r"stamp\s+\d+", name, re.IGNORECASE))
    has_page = bool(re.search(r"page\s+\d+", name, re.IGNORECASE))

    # 1850-1880 use page numbers (not sheet)
    if config.year in (1850, 1860, 1870, 1880):
        if not has_page:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="missing_page",
                    severity="error",
                    message=f"Missing page number in source name ({config.year} uses page, not sheet)",
                    field="source_name",
                    current_value=name[:80],
                    category="missing",
                )
            )
    elif config.source_name_allows_sheet_or_stamp:
        if not has_sheet and not has_stamp:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="missing_sheet_or_stamp",
                    severity="error",
                    message="Missing sheet or stamp number in source name",
                    field="source_name",
                    current_value=name[:80],
                    category="missing",
                )
            )
    elif config.source_name_requires_sheet and not has_sheet:
        issues.append(
            Issue(
                source_id=source_id,
                issue_type="missing_sheet",
                severity="error",
                message="Missing sheet number in source name",
                field="source_name",
                current_value=name[:80],
                category="missing",
            )
        )

    # Check line
    has_line = bool(re.search(r"line\s+\d+", name, re.IGNORECASE))
    if config.source_name_requires_line:
        if config.source_name_line_required_with_sheet_only:
            if has_sheet and not has_line:
                issues.append(
                    Issue(
                        source_id=source_id,
                        issue_type="missing_line",
                        severity="error",
                        message="Missing line number (required with sheet format)",
                        field="source_name",
                        current_value=name[:80],
                        category="missing",
                    )
                )
        elif not has_line:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="missing_line",
                    severity="error",
                    message="Missing line number in source name",
                    field="source_name",
                    current_value=name[:80],
                    category="missing",
                )
            )

    # Check family/household ID (1860 census) - either term is acceptable
    if config.source_name_requires_family:
        has_family = bool(re.search(r"family\s+\d+", name, re.IGNORECASE))
        has_household_id = bool(re.search(r"household\s+ID\s+\d+", name, re.IGNORECASE))
        if not has_family and not has_household_id:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="missing_family",
                    severity="error",
                    message="Missing family or household ID in source name",
                    field="source_name",
                    current_value=name[:80],
                    category="missing",
                )
            )

    # Check state name
    components = ComponentExtractor.extract_from_source_name(name, config.year)
    if components.state and components.state not in VALID_STATE_NAMES:
        similar = find_similar_state(components.state)
        issues.append(
            Issue(
                source_id=source_id,
                issue_type="state_name_typo",
                severity="error",
                message=f"Invalid state name: '{components.state}'",
                field="source_name",
                current_value=components.state,
                expected_value=similar or "",
                category="typo",
            )
        )

    return issues


def check_footnote(
    source_id: int, footnote: str, config: CensusYearConfig
) -> list[Issue]:
    """Check footnote for issues."""
    issues = []

    if not footnote:
        issues.append(
            Issue(
                source_id=source_id,
                issue_type="empty_footnote",
                severity="error",
                message="Footnote is empty",
                field="footnote",
                category="missing",
            )
        )
        return issues

    # Check census reference
    if config.footnote_census_ref not in footnote:
        issues.append(
            Issue(
                source_id=source_id,
                issue_type="missing_census_ref",
                severity="error",
                message=f"Missing '{config.footnote_census_ref}' in footnote",
                field="footnote",
                current_value=footnote[:80],
                category="format",
            )
        )

    # Check ED
    if config.footnote_requires_ed and config.footnote_ed_pattern:
        if not re.search(config.footnote_ed_pattern, footnote, re.IGNORECASE):
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="missing_ed_in_footnote",
                    severity="error",
                    message="Missing enumeration district reference in footnote",
                    field="footnote",
                    current_value=footnote[:80],
                    category="missing",
                )
            )

    # Check sheet/stamp/page (1850-1880 use "page", 1900+ use "sheet")
    # Match sheet with optional hyphen: "sheet 6B" or "sheet 6-B"
    has_sheet = bool(re.search(r"sheet\s+\d+-?[AB]?", footnote, re.IGNORECASE))
    has_stamp = bool(re.search(r"stamp\s+\d+", footnote, re.IGNORECASE))
    has_page = bool(re.search(r"page\s+\d+", footnote, re.IGNORECASE))
    has_page_stamped = bool(
        re.search(r"page\s+\d+\s*\(stamped\)", footnote, re.IGNORECASE)
    )

    # 1850-1870 use "page X", 1880 uses "page X (stamped)"
    if config.year in (1850, 1860, 1870):
        if not has_page:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="missing_page_footnote",
                    severity="error",
                    message=f"Missing 'page X' in footnote ({config.year} uses page, not sheet)",
                    field="footnote",
                    category="missing",
                )
            )
    elif config.year == 1880:
        if not has_page_stamped:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="missing_page_stamped_footnote",
                    severity="error",
                    message="Missing 'page X (stamped)' in footnote (1880 format)",
                    field="footnote",
                    category="missing",
                )
            )
    elif config.footnote_allows_sheet_or_stamp:
        if not has_sheet and not has_stamp:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="missing_sheet_or_stamp_footnote",
                    severity="error",
                    message="Missing sheet or stamp in footnote",
                    field="footnote",
                    category="missing",
                )
            )
    elif config.footnote_requires_sheet and not has_sheet:
        issues.append(
            Issue(
                source_id=source_id,
                issue_type="missing_sheet_footnote",
                severity="error",
                message="Missing sheet number in footnote",
                field="footnote",
                category="missing",
            )
        )

    # Check line
    has_line = bool(re.search(r"line\s+\d+", footnote, re.IGNORECASE))
    if config.footnote_requires_line:
        if config.footnote_line_required_with_sheet_only:
            if has_sheet and not has_line:
                issues.append(
                    Issue(
                        source_id=source_id,
                        issue_type="missing_line_footnote",
                        severity="error",
                        message="Missing line number in footnote (required with sheet)",
                        field="footnote",
                        category="missing",
                    )
                )
        elif not has_line:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="missing_line_footnote",
                    severity="error",
                    message="Missing line number in footnote",
                    field="footnote",
                    category="missing",
                )
            )

    # Check family/household ID (1860 census) - either term is acceptable
    if config.footnote_requires_family:
        has_family = bool(re.search(r"family\s+\d+", footnote, re.IGNORECASE))
        has_household_id = bool(
            re.search(r"household\s+ID\s+\d+", footnote, re.IGNORECASE)
        )
        if not has_family and not has_household_id:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="missing_family_footnote",
                    severity="error",
                    message="Missing family or household ID in footnote",
                    field="footnote",
                    category="missing",
                )
            )

    # Check schedule type requirement
    if config.footnote_requires_schedule:
        schedule_found = False
        if config.footnote_schedule_patterns:
            for pattern in config.footnote_schedule_patterns:
                if pattern.lower() in footnote.lower():
                    schedule_found = True
                    break
        if not schedule_found:
            expected = ", ".join(config.footnote_schedule_patterns or [])
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="missing_schedule_type",
                    severity="error",
                    message=f"Missing schedule type in footnote (expected: {expected})",
                    field="footnote",
                    current_value=footnote[:80],
                    expected_value=expected,
                    category="missing",
                )
            )

    # Check quoted title
    title_match = re.search(r'"([^"]+)"', footnote)
    if title_match:
        found_title = title_match.group(1)
        if found_title != config.footnote_quoted_title:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="wrong_footnote_title",
                    severity="warning",
                    message="Wrong quoted title in footnote",
                    field="footnote",
                    current_value=found_title,
                    expected_value=config.footnote_quoted_title,
                    category="title",
                )
            )

    # Check for double spaces
    if "  " in footnote:
        issues.append(
            Issue(
                source_id=source_id,
                issue_type="double_space",
                severity="warning",
                message="Double space found in footnote",
                field="footnote",
                category="format",
            )
        )

    # Check FamilySearch is in italics
    # Matches both <i>FamilySearch</i> and &lt;i&gt;FamilySearch&lt;/i&gt; (XML-encoded)
    has_familysearch = "FamilySearch" in footnote
    has_italics = bool(
        re.search(r"<i>FamilySearch</i>|&lt;i&gt;FamilySearch&lt;/i&gt;", footnote)
    )
    if has_familysearch and not has_italics:
        issues.append(
            Issue(
                source_id=source_id,
                issue_type="familysearch_not_italic",
                severity="error",
                message="FamilySearch should be in italics (<i>FamilySearch</i>)",
                field="footnote",
                category="format",
            )
        )

    return issues


def check_short_footnote(
    source_id: int, short_footnote: str, config: CensusYearConfig
) -> list[Issue]:
    """Check short footnote for issues."""
    issues = []

    if not short_footnote:
        return issues  # Short footnote may be optional

    # Check census reference
    if config.short_census_ref not in short_footnote:
        issues.append(
            Issue(
                source_id=source_id,
                issue_type="short_missing_census_ref",
                severity="error",
                message=f"Missing '{config.short_census_ref}' in short footnote",
                field="short_footnote",
                current_value=short_footnote[:80],
                category="format",
            )
        )

    # Check ED abbreviation
    if config.short_requires_ed and config.short_ed_abbreviation:
        if config.short_ed_abbreviation not in short_footnote:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="short_missing_ed",
                    severity="error",
                    message=f"Missing '{config.short_ed_abbreviation}' in short footnote",
                    field="short_footnote",
                    current_value=short_footnote[:80],
                    category="missing",
                )
            )

    # Check sheet/stamp/page (1850-1880 use "page" or "p.", 1900+ use "sheet")
    # Match sheet with optional hyphen: "sheet 6B" or "sheet 6-B"
    has_sheet = bool(re.search(r"sheet\s+\d+-?[AB]?", short_footnote, re.IGNORECASE))
    has_stamp = bool(re.search(r"stamp\s+\d+", short_footnote, re.IGNORECASE))
    # Match "page X" or "p. X" for pre-1880 censuses
    has_page = bool(re.search(r"(?:page|p\.)\s+\d+", short_footnote, re.IGNORECASE))
    has_page_stamped = bool(
        re.search(r"(?:page|p\.)\s+\d+\s*\(stamped\)", short_footnote, re.IGNORECASE)
    )

    # 1850-1870 use "page X" or "p. X", 1880 uses "p. X (stamped)"
    if config.year in (1850, 1860, 1870):
        if not has_page:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="short_missing_page",
                    severity="error",
                    message=f"Missing 'page X' or 'p. X' in short footnote ({config.year} uses page, not sheet)",
                    field="short_footnote",
                    category="missing",
                )
            )
    elif config.year == 1880:
        if not has_page_stamped:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="short_missing_page_stamped",
                    severity="error",
                    message="Missing 'p. X (stamped)' in short footnote (1880 format)",
                    field="short_footnote",
                    category="missing",
                )
            )
    elif config.short_allows_sheet_or_stamp:
        if not has_sheet and not has_stamp:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="short_missing_sheet_or_stamp",
                    severity="error",
                    message="Missing sheet or stamp in short footnote",
                    field="short_footnote",
                    category="missing",
                )
            )
    elif config.short_requires_sheet and not has_sheet:
        issues.append(
            Issue(
                source_id=source_id,
                issue_type="short_missing_sheet",
                severity="error",
                message="Missing sheet number in short footnote",
                field="short_footnote",
                category="missing",
            )
        )

    # Check line (matches "line 41" or "ln. 41")
    has_line = bool(re.search(r"(?:line|ln\.?)\s*\d+", short_footnote, re.IGNORECASE))
    if config.short_requires_line:
        if config.short_line_required_with_sheet_only:
            if has_sheet and not has_line:
                issues.append(
                    Issue(
                        source_id=source_id,
                        issue_type="short_missing_line",
                        severity="error",
                        message="Missing line in short footnote (required with sheet)",
                        field="short_footnote",
                        category="missing",
                    )
                )
        elif not has_line:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="short_missing_line",
                    severity="error",
                    message="Missing line number in short footnote",
                    field="short_footnote",
                    category="missing",
                )
            )

    # Check family/household ID (1860 census) - either term is acceptable
    if config.short_requires_family:
        has_family = bool(re.search(r"family\s+\d+", short_footnote, re.IGNORECASE))
        has_household_id = bool(
            re.search(r"household\s+ID\s+\d+", short_footnote, re.IGNORECASE)
        )
        if not has_family and not has_household_id:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="short_missing_family",
                    severity="error",
                    message="Missing family or household ID in short footnote",
                    field="short_footnote",
                    category="missing",
                )
            )

    # Check schedule type requirement
    if config.short_requires_schedule:
        schedule_found = False
        if config.short_schedule_patterns:
            for pattern in config.short_schedule_patterns:
                if pattern.lower() in short_footnote.lower():
                    schedule_found = True
                    break
        if not schedule_found:
            expected = ", ".join(config.short_schedule_patterns or [])
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="short_missing_schedule_type",
                    severity="error",
                    message=f"Missing schedule type in short footnote (expected: {expected})",
                    field="short_footnote",
                    current_value=short_footnote[:80],
                    expected_value=expected,
                    category="missing",
                )
            )

    # Check ending period
    # Note: Period may be inside closing quote (e.g., "owner." or &quot;owner.&quot;)
    if config.short_requires_ending_period:
        stripped = short_footnote.rstrip()
        ends_with_period = (
            stripped.endswith(".")
            or stripped.endswith('.&quot;')  # Period before XML entity quote
            or stripped.endswith('."')       # Period before actual quote
        )
        if stripped and not ends_with_period:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="short_no_ending_period",
                    severity="warning",
                    message="Short footnote should end with period",
                    field="short_footnote",
                    current_value=(
                        short_footnote[-30:]
                        if len(short_footnote) > 30
                        else short_footnote
                    ),
                    category="format",
                )
            )

    return issues


def check_bibliography(
    source_id: int, bibliography: str, config: CensusYearConfig
) -> list[Issue]:
    """Check bibliography for issues."""
    issues = []

    if not bibliography:
        issues.append(
            Issue(
                source_id=source_id,
                issue_type="empty_bibliography",
                severity="error",
                message="Bibliography is empty",
                field="bibliography",
                category="missing",
            )
        )
        return issues

    # Check quoted title
    title_match = re.search(r'"([^"]+)"', bibliography)
    if title_match:
        found_title = title_match.group(1)
        expected = config.bibliography_quoted_title
        alt_titles = config.bibliography_alt_titles or []

        if found_title != expected and found_title not in alt_titles:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="wrong_bibliography_title",
                    severity="warning",
                    message="Wrong quoted title in bibliography",
                    field="bibliography",
                    current_value=found_title,
                    expected_value=expected,
                    category="title",
                )
            )

    # Check for double spaces
    if "  " in bibliography:
        issues.append(
            Issue(
                source_id=source_id,
                issue_type="bibliography_double_space",
                severity="warning",
                message="Double space found in bibliography",
                field="bibliography",
                category="format",
            )
        )

    # Check FamilySearch is in italics
    # Matches both <i>FamilySearch</i> and &lt;i&gt;FamilySearch&lt;/i&gt; (XML-encoded)
    has_familysearch = "FamilySearch" in bibliography
    has_italics = bool(
        re.search(r"<i>FamilySearch</i>|&lt;i&gt;FamilySearch&lt;/i&gt;", bibliography)
    )
    if has_familysearch and not has_italics:
        issues.append(
            Issue(
                source_id=source_id,
                issue_type="bibliography_familysearch_not_italic",
                severity="error",
                message="FamilySearch should be in italics (<i>FamilySearch</i>)",
                field="bibliography",
                category="format",
            )
        )

    return issues


def check_1850_duplicate_locality(
    source_id: int,
    footnote: str,
    short_footnote: str,
) -> list[Issue]:
    """Check for 1850 census where locality duplicates county name.

    In some cases, the city/locality field contains the county name,
    causing redundant text like:
    "1850 U.S. census, Monongalia County, Virginia, Monongalia county, population schedule..."

    The locality should be removed in such cases.
    """
    issues = []

    if not footnote:
        return issues

    # Pattern to extract county and locality from 1850 footnote
    # Format: "1850 U.S. census, [County] County, [State], [Locality], population schedule"
    pattern = r"1850 U\.S\. census,\s+(\w+(?:\s+\w+)?)\s+County,\s+[^,]+,\s+([^,]+),\s+population schedule"
    match = re.search(pattern, footnote, re.IGNORECASE)

    if match:
        county = match.group(1).strip()
        locality = match.group(2).strip()

        # Check if locality is just the county name (with optional "county" suffix)
        locality_normalized = re.sub(r"\s+county$", "", locality, flags=re.IGNORECASE).strip()

        if county.lower() == locality_normalized.lower():
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="duplicate_county_locality",
                    severity="error",
                    message=f"Locality '{locality}' duplicates county name '{county}'",
                    field="footnote",
                    current_value=f"{county} County, ..., {locality}",
                    expected_value=f"Remove '{locality}' from footnote and short footnote",
                    category="redundant",
                )
            )

    # Also check short footnote for same issue
    # Format: "1850 U.S. census, [County] Co., [State abbrev.], pop. sch., [Locality], ..."
    short_pattern = r"1850 U\.S\. census,\s+(\w+(?:\s+\w+)?)\s+Co\.,\s+[^,]+,\s+pop\. sch\.,\s+([^,]+),"
    short_match = re.search(short_pattern, short_footnote, re.IGNORECASE)

    if short_match:
        county = short_match.group(1).strip()
        locality = short_match.group(2).strip()

        locality_normalized = re.sub(r"\s+county$", "", locality, flags=re.IGNORECASE).strip()

        if county.lower() == locality_normalized.lower():
            # Only add if we haven't already flagged the footnote
            if not any(i.issue_type == "duplicate_county_locality" for i in issues):
                issues.append(
                    Issue(
                        source_id=source_id,
                        issue_type="duplicate_county_locality_short",
                        severity="error",
                        message=f"Short footnote locality '{locality}' duplicates county name '{county}'",
                        field="short_footnote",
                        current_value=f"{county} Co., ..., {locality}",
                        expected_value=f"Remove '{locality}' from short footnote",
                        category="redundant",
                    )
                )

    return issues


def check_cross_field_consistency(
    source_id: int,
    name: str,
    footnote: str,
    short_footnote: str,
    bibliography: str,
    config: CensusYearConfig,
) -> list[Issue]:
    """Check consistency between source name, footnote, short footnote, and bibliography."""
    issues = []

    # 1850 census: Check for duplicate county/locality
    if config.year == 1850:
        issues.extend(check_1850_duplicate_locality(source_id, footnote, short_footnote))

    # Extract components
    name_comp = ComponentExtractor.extract_from_source_name(name, config.year)
    fn_comp = ComponentExtractor.extract_from_footnote(footnote)
    short_comp = ComponentExtractor.extract_from_short_footnote(short_footnote)
    bib_comp = ComponentExtractor.extract_from_bibliography(bibliography)

    # Check ED consistency
    if name_comp.ed and fn_comp.ed:
        # Normalize EDs for comparison (strip trailing letters, leading zeros)
        name_ed_base = re.sub(r"[A-Z]$", "", name_comp.ed).lstrip("0") or "0"
        fn_ed_base = re.sub(r"[A-Z]$", "", fn_comp.ed).lstrip("0") or "0"

        if name_ed_base != fn_ed_base and name_comp.ed != fn_comp.ed:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="ed_mismatch",
                    severity="warning",
                    message="ED in source name doesn't match ED in footnote",
                    field="consistency",
                    current_value=f"Name: {name_comp.ed}, Footnote: {fn_comp.ed}",
                    category="consistency",
                )
            )

    # Check ED number is present in footnote when source name has ED
    # This catches cases where footnote has "enumeration district (ED) ," with no number
    if name_comp.ed and config.footnote_requires_ed:
        # Check footnote has actual ED number
        has_ed_in_footnote = bool(
            re.search(r"enumeration district \(ED\)\s*\d+", footnote, re.IGNORECASE)
        )
        if not has_ed_in_footnote:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="missing_ed_number_footnote",
                    severity="error",
                    message="Footnote has 'enumeration district (ED)' but no number",
                    field="footnote",
                    current_value="ED number missing after 'enumeration district (ED)'",
                    expected_value=f"ED {name_comp.ed}",
                    category="missing",
                )
            )

        # Check short footnote has actual ED number
        has_ed_in_short = bool(re.search(r"E\.D\.\s*\d+", short_footnote))
        if not has_ed_in_short:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="missing_ed_number_short",
                    severity="error",
                    message="Short footnote has 'E.D.' but no number",
                    field="short_footnote",
                    current_value="ED number missing after 'E.D.'",
                    expected_value=f"E.D. {name_comp.ed}",
                    category="missing",
                )
            )

    # Check sheet consistency
    if name_comp.sheet and fn_comp.sheet:
        if name_comp.sheet != fn_comp.sheet:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="sheet_mismatch",
                    severity="warning",
                    message="Sheet in source name doesn't match sheet in footnote",
                    field="consistency",
                    current_value=f"Name: {name_comp.sheet}, Footnote: {fn_comp.sheet}",
                    category="consistency",
                )
            )

    # Check state consistency (source name vs footnote)
    # Normalize to handle "Territory" suffix (e.g., "Colorado Territory" matches "Colorado")
    if name_comp.state and fn_comp.state:
        name_state_norm = normalize_state_for_comparison(name_comp.state).lower()
        fn_state_norm = normalize_state_for_comparison(fn_comp.state).lower()
        if name_state_norm != fn_state_norm:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="footnote_state_mismatch",
                    severity="error",
                    message="State in footnote doesn't match state in source name",
                    field="footnote",
                    current_value=fn_comp.state,
                    expected_value=name_comp.state,
                    category="consistency",
                )
            )

    # Check county consistency (source name vs footnote)
    if name_comp.county and fn_comp.county:
        if name_comp.county.lower() != fn_comp.county.lower():
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="footnote_county_mismatch",
                    severity="error",
                    message="County in footnote doesn't match county in source name",
                    field="footnote",
                    current_value=fn_comp.county,
                    expected_value=name_comp.county,
                    category="consistency",
                )
            )

    # Check state abbreviation in short footnote
    # Normalize to handle "Territory" suffix in short footnote
    if name_comp.state and short_comp.state:
        # Normalize short footnote state (e.g., "Colo. Territory" -> "Colo.")
        short_state_norm = re.sub(
            r"\s+Territory$", "", short_comp.state, flags=re.IGNORECASE
        )
        expected_abbrev = STATE_ABBREVIATIONS.get(name_comp.state)
        if expected_abbrev and short_state_norm != expected_abbrev:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="short_state_mismatch",
                    severity="error",
                    message="State abbreviation in short footnote doesn't match",
                    field="short_footnote",
                    current_value=short_comp.state,
                    expected_value=expected_abbrev,
                    category="consistency",
                )
            )

    # Check bibliography state consistency
    # Normalize to handle "Territory" suffix (e.g., "Colorado Territory" matches "Colorado")
    if name_comp.state and bib_comp.state:
        name_state_norm = normalize_state_for_comparison(name_comp.state)
        bib_state_norm = normalize_state_for_comparison(bib_comp.state)
        if bib_state_norm != name_state_norm:
            issues.append(
                Issue(
                    source_id=source_id,
                    issue_type="bibliography_state_mismatch",
                    severity="error",
                    message="State in bibliography doesn't match source name",
                    field="bibliography",
                    current_value=bib_comp.state,
                    expected_value=name_comp.state,
                    category="consistency",
                )
            )

    # Independent city validation (if module available)
    if HAS_INDEPENDENT_CITIES and name_comp.state and name_comp.county:
        issues.extend(
            check_independent_city(
                source_id, name_comp.county, name_comp.state, fn_comp.raw_text
            )
        )

    # Check family/household ID consistency (1860 census)
    if config.source_name_requires_family:
        # Detect which term is used in each field
        name_has_family = bool(re.search(r"family\s+\d+", name, re.IGNORECASE))
        name_has_household = bool(
            re.search(r"household\s+ID\s+\d+", name, re.IGNORECASE)
        )
        fn_has_family = bool(re.search(r"family\s+\d+", footnote, re.IGNORECASE))
        fn_has_household = bool(
            re.search(r"household\s+ID\s+\d+", footnote, re.IGNORECASE)
        )
        short_has_family = bool(
            re.search(r"family\s+\d+", short_footnote, re.IGNORECASE)
        )
        short_has_household = bool(
            re.search(r"household\s+ID\s+\d+", short_footnote, re.IGNORECASE)
        )

        # Determine which term is used in source name (the authoritative source)
        name_term = None
        if name_has_family:
            name_term = "family"
        elif name_has_household:
            name_term = "household ID"

        # Check consistency if source name has a term
        if name_term:
            # Check footnote consistency
            if name_term == "family" and fn_has_household and not fn_has_family:
                issues.append(
                    Issue(
                        source_id=source_id,
                        issue_type="family_term_mismatch_footnote",
                        severity="error",
                        message="Source name uses 'family' but footnote uses 'household ID'",
                        field="footnote",
                        current_value="household ID",
                        expected_value="family",
                        category="consistency",
                    )
                )
            elif name_term == "household ID" and fn_has_family and not fn_has_household:
                issues.append(
                    Issue(
                        source_id=source_id,
                        issue_type="family_term_mismatch_footnote",
                        severity="error",
                        message="Source name uses 'household ID' but footnote uses 'family'",
                        field="footnote",
                        current_value="family",
                        expected_value="household ID",
                        category="consistency",
                    )
                )

            # Check short footnote consistency
            if (
                name_term == "family"
                and short_has_household
                and not short_has_family
            ):
                issues.append(
                    Issue(
                        source_id=source_id,
                        issue_type="family_term_mismatch_short",
                        severity="error",
                        message="Source name uses 'family' but short footnote uses 'household ID'",
                        field="short_footnote",
                        current_value="household ID",
                        expected_value="family",
                        category="consistency",
                    )
                )
            elif (
                name_term == "household ID"
                and short_has_family
                and not short_has_household
            ):
                issues.append(
                    Issue(
                        source_id=source_id,
                        issue_type="family_term_mismatch_short",
                        severity="error",
                        message="Source name uses 'household ID' but short footnote uses 'family'",
                        field="short_footnote",
                        current_value="family",
                        expected_value="household ID",
                        category="consistency",
                    )
                )

    return issues


def check_independent_city(
    source_id: int, county_name: str, state_name: str, footnote_text: str
) -> list[Issue]:
    """Check for independent city / county confusion."""
    issues = []

    if not HAS_INDEPENDENT_CITIES:
        return issues

    if is_independent_city(county_name, state_name):
        ic_info = get_independent_city(county_name, state_name)

        county_pattern = f"{county_name} County"
        has_county_in_footnote = county_pattern in footnote_text
        has_independent_city = "(Independent City)" in footnote_text

        if has_county_in_footnote and not has_independent_city:
            # Check for patterns that suggest it's actually the county
            county_pattern_found = False
            city_pattern_found = False

            if ic_info and ic_info.county_locality_pattern:
                if ic_info.county_locality_pattern in footnote_text:
                    county_pattern_found = True

            if ic_info and ic_info.locality_pattern:
                if ic_info.locality_pattern in footnote_text:
                    city_pattern_found = True

            if county_pattern_found and not city_pattern_found:
                issues.append(
                    Issue(
                        source_id=source_id,
                        issue_type="independent_city_is_county",
                        severity="error",
                        message=f"Source Name says '{county_name}' but footnote indicates this is {ic_info.related_county}",
                        field="source_name",
                        current_value=county_name,
                        expected_value=(
                            ic_info.related_county
                            if ic_info
                            else f"{county_name} County"
                        ),
                        category="jurisdiction",
                    )
                )
            else:
                issues.append(
                    Issue(
                        source_id=source_id,
                        issue_type="independent_city_ambiguous",
                        severity="warning",
                        message=f"Source Name says '{county_name}' but footnote says '{county_name} County'",
                        field="footnote",
                        current_value=f"{county_name} County",
                        expected_value=f"{county_name} (Independent City)",
                        category="jurisdiction",
                    )
                )

    return issues


def find_similar_state(name: str) -> str | None:
    """Find a similar valid state name (for typo detection)."""
    name_lower = name.lower()
    for state in VALID_STATE_NAMES:
        if name_lower == state.lower():
            return state
        # Simple character difference check
        if len(name) == len(state):
            diffs = sum(1 for a, b in zip(name_lower, state.lower()) if a != b)
            if diffs <= 2:
                return state
    return None
