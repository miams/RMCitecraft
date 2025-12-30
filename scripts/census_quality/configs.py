"""Census year configurations for quality checking.

Each census year has explicit, self-contained validation rules with no
inheritance or implicit defaults. This ensures clarity and maintainability.
"""

from .models import CensusYearConfig


def build_census_configs() -> dict[int | str, CensusYearConfig]:
    """Build explicit configurations for each census year.

    Each year is fully defined with no inheritance or implicit defaults.
    """
    configs = {}

    # =========================================================================
    # 1790 Census
    # =========================================================================
    configs[1790] = CensusYearConfig(
        year=1790,
        description="First U.S. Census - heads of household only",
        # Source name
        source_name_prefix="Fed Census: 1790,",
        source_name_requires_ed=False,
        source_name_ed_pattern=None,
        source_name_requires_sheet=False,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=False,
        source_name_line_required_with_sheet_only=False,
        source_name_requires_family=False,
        # Footnote
        footnote_census_ref="1790 U.S. census",
        footnote_requires_ed=False,
        footnote_ed_pattern=None,
        footnote_requires_sheet=False,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=False,
        footnote_line_required_with_sheet_only=False,
        footnote_requires_family=False,
        footnote_quoted_title="United States, Census, 1790,",
        footnote_requires_schedule=False,
        footnote_schedule_patterns=None,
        # Short footnote
        short_census_ref="1790 U.S. census",
        short_requires_ed=False,
        short_ed_abbreviation=None,
        short_requires_sheet=False,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=False,
        short_line_required_with_sheet_only=False,
        short_requires_family=False,
        short_requires_ending_period=True,
        short_requires_schedule=False,
        short_schedule_patterns=None,
        # Bibliography
        bibliography_quoted_title="United States, Census, 1790.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1800-1840 Censuses (similar structure, heads of household)
    # =========================================================================
    for year in [1800, 1810, 1820, 1830, 1840]:
        ordinal = {
            1800: "Second",
            1810: "Third",
            1820: "Fourth",
            1830: "Fifth",
            1840: "Sixth",
        }[year]
        configs[year] = CensusYearConfig(
            year=year,
            description=f"{ordinal} U.S. Census - heads of household only",
            # Source name
            source_name_prefix=f"Fed Census: {year},",
            source_name_requires_ed=False,
            source_name_ed_pattern=None,
            source_name_requires_sheet=False,
            source_name_requires_stamp=False,
            source_name_allows_sheet_or_stamp=False,
            source_name_requires_line=False,
            source_name_line_required_with_sheet_only=False,
            source_name_requires_family=False,
            # Footnote
            footnote_census_ref=f"{year} U.S. census",
            footnote_requires_ed=False,
            footnote_ed_pattern=None,
            footnote_requires_sheet=False,
            footnote_requires_stamp=False,
            footnote_allows_sheet_or_stamp=False,
            footnote_requires_line=False,
            footnote_line_required_with_sheet_only=False,
            footnote_requires_family=False,
            footnote_quoted_title=f"United States, Census, {year},",
            footnote_requires_schedule=False,
            footnote_schedule_patterns=None,
            # Short footnote
            short_census_ref=f"{year} U.S. census",
            short_requires_ed=False,
            short_ed_abbreviation=None,
            short_requires_sheet=False,
            short_requires_stamp=False,
            short_allows_sheet_or_stamp=False,
            short_requires_line=False,
            short_line_required_with_sheet_only=False,
            short_requires_family=False,
            short_requires_ending_period=True,
            short_requires_schedule=False,
            short_schedule_patterns=None,
            # Bibliography
            bibliography_quoted_title=f"United States, Census, {year}.",
            # Quality
            expected_citation_quality="PDO",
        )

    # =========================================================================
    # 1850 and 1870 Censuses - All persons named, no ED, requires line
    # =========================================================================
    for year in [1850, 1870]:
        ordinal = {1850: "Seventh", 1870: "Ninth"}[year]
        configs[year] = CensusYearConfig(
            year=year,
            description=f"{ordinal} U.S. Census - all persons named, no ED, uses page (not sheet)",
            # Source name: uses "page" not "sheet"
            source_name_prefix=f"Fed Census: {year},",
            source_name_requires_ed=False,
            source_name_ed_pattern=None,
            source_name_requires_sheet=False,  # 1850/1870 use page, not sheet
            source_name_requires_stamp=False,
            source_name_allows_sheet_or_stamp=False,
            source_name_requires_line=True,
            source_name_line_required_with_sheet_only=False,
            source_name_requires_family=False,
            # Footnote: uses "page" not "sheet"
            footnote_census_ref=f"{year} U.S. census",
            footnote_requires_ed=False,
            footnote_ed_pattern=None,
            footnote_requires_sheet=False,  # 1850/1870 use page, not sheet
            footnote_requires_stamp=False,
            footnote_allows_sheet_or_stamp=False,
            footnote_requires_line=True,
            footnote_line_required_with_sheet_only=False,
            footnote_requires_family=False,
            footnote_quoted_title=f"United States, Census, {year},",
            footnote_requires_schedule=True,
            footnote_schedule_patterns=["population schedule", "slave schedule"],
            # Short footnote: uses "p." not "sheet"
            short_census_ref=f"{year} U.S. census",
            short_requires_ed=False,
            short_ed_abbreviation=None,
            short_requires_sheet=False,  # 1850/1870 use p., not sheet
            short_requires_stamp=False,
            short_allows_sheet_or_stamp=False,
            short_requires_line=True,
            short_line_required_with_sheet_only=False,
            short_requires_family=False,
            short_requires_ending_period=True,
            short_requires_schedule=True,
            short_schedule_patterns=["pop. sch.", "slave sch."],
            # Bibliography
            bibliography_quoted_title=f"United States, Census, {year}.",
            # Quality
            expected_citation_quality="PDO",
        )

    # =========================================================================
    # 1860 Census - All persons named, no ED, requires family/household ID
    # =========================================================================
    configs[1860] = CensusYearConfig(
        year=1860,
        description="Eighth U.S. Census - all persons named, no ED, requires family/household ID",
        # Source name: uses "page" not "sheet", requires family/household ID
        source_name_prefix="Fed Census: 1860,",
        source_name_requires_ed=False,
        source_name_ed_pattern=None,
        source_name_requires_sheet=False,  # 1860 uses page, not sheet
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=False,  # 1860 uses family, not line
        source_name_line_required_with_sheet_only=False,
        source_name_requires_family=True,  # Requires "family X" or "household ID X"
        # Footnote: uses "page" not "sheet"
        footnote_census_ref="1860 U.S. census",
        footnote_requires_ed=False,
        footnote_ed_pattern=None,
        footnote_requires_sheet=False,  # 1860 uses page, not sheet
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=False,  # 1860 uses family, not line
        footnote_line_required_with_sheet_only=False,
        footnote_requires_family=True,  # Requires "family X"
        footnote_quoted_title="United States, Census, 1860,",
        footnote_requires_schedule=True,
        footnote_schedule_patterns=["population schedule", "slave schedule"],
        # Short footnote: uses "p." not "sheet"
        short_census_ref="1860 U.S. census",
        short_requires_ed=False,
        short_ed_abbreviation=None,
        short_requires_sheet=False,  # 1860 uses p., not sheet
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=False,  # 1860 uses family, not line
        short_line_required_with_sheet_only=False,
        short_requires_family=True,  # Requires "family X"
        short_requires_ending_period=True,
        short_requires_schedule=True,
        short_schedule_patterns=["pop. sch.", "slave sch."],
        # Bibliography
        bibliography_quoted_title="United States, Census, 1860.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1880 Census - ED introduced, uses stamped page numbers (not sheet)
    # =========================================================================
    configs[1880] = CensusYearConfig(
        year=1880,
        description="Tenth U.S. Census - ED introduced, stamped page numbers",
        # Source name: uses "page" not "sheet"
        source_name_prefix="Fed Census: 1880,",
        source_name_requires_ed=True,
        source_name_ed_pattern=r"\[ED (\d+),",
        source_name_requires_sheet=False,  # 1880 uses page, not sheet
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=True,
        source_name_line_required_with_sheet_only=False,
        source_name_requires_family=False,
        # Footnote: uses "page X (stamped)" not "sheet"
        footnote_census_ref="1880 U.S. census",
        footnote_requires_ed=True,
        footnote_ed_pattern=r"enumeration district \(ED\)",
        footnote_requires_sheet=False,  # 1880 uses page (stamped)
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=True,
        footnote_line_required_with_sheet_only=False,
        footnote_requires_family=False,
        footnote_quoted_title="United States, Census, 1880,",
        footnote_requires_schedule=True,
        footnote_schedule_patterns=["population schedule"],
        # Short footnote: uses "p. X (stamped)" not "sheet"
        short_census_ref="1880 U.S. census",
        short_requires_ed=True,
        short_ed_abbreviation="E.D.",
        short_requires_sheet=False,  # 1880 uses p. (stamped)
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=True,
        short_line_required_with_sheet_only=False,
        short_requires_family=False,
        short_requires_ending_period=True,
        short_requires_schedule=True,
        short_schedule_patterns=["pop. sch."],
        # Bibliography
        bibliography_quoted_title="United States, Census, 1880.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1890 Census - Mostly destroyed
    # =========================================================================
    configs[1890] = CensusYearConfig(
        year=1890,
        description="Eleventh U.S. Census - mostly destroyed by fire",
        # Source name
        source_name_prefix="Fed Census: 1890,",
        source_name_requires_ed=True,
        source_name_ed_pattern=r"\[ED (\d+),",
        source_name_requires_sheet=True,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=True,
        source_name_line_required_with_sheet_only=False,
        source_name_requires_family=False,
        # Footnote
        footnote_census_ref="1890 U.S. census",
        footnote_requires_ed=True,
        footnote_ed_pattern=r"enumeration district \(ED\)",
        footnote_requires_sheet=True,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=True,
        footnote_line_required_with_sheet_only=False,
        footnote_requires_family=False,
        footnote_quoted_title="United States, Census, 1890,",
        footnote_requires_schedule=True,
        footnote_schedule_patterns=["population schedule"],
        # Short footnote
        short_census_ref="1890 U.S. census",
        short_requires_ed=True,
        short_ed_abbreviation="E.D.",
        short_requires_sheet=True,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=True,
        short_line_required_with_sheet_only=False,
        short_requires_family=False,
        short_requires_ending_period=True,
        short_requires_schedule=True,
        short_schedule_patterns=["pop. sch."],
        # Bibliography
        bibliography_quoted_title="United States, Census, 1890.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1900 Census - ED format, requires population schedule
    # =========================================================================
    configs[1900] = CensusYearConfig(
        year=1900,
        description="Twelfth U.S. Census - requires population schedule",
        # Source name
        source_name_prefix="Fed Census: 1900,",
        source_name_requires_ed=True,
        source_name_ed_pattern=r"\[ED (\d+),",
        source_name_requires_sheet=True,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=True,
        source_name_line_required_with_sheet_only=False,
        source_name_requires_family=False,
        # Footnote
        footnote_census_ref="1900 U.S. census",
        footnote_requires_ed=True,
        footnote_ed_pattern=r"enumeration district \(ED\)",
        footnote_requires_sheet=True,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=True,
        footnote_line_required_with_sheet_only=False,
        footnote_requires_family=False,
        footnote_quoted_title="United States, Census, 1900,",
        footnote_requires_schedule=True,
        footnote_schedule_patterns=["population schedule"],
        # Short footnote
        short_census_ref="1900 U.S. census",
        short_requires_ed=True,
        short_ed_abbreviation="E.D.",
        short_requires_sheet=True,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=True,
        short_line_required_with_sheet_only=False,
        short_requires_family=False,
        short_requires_ending_period=True,
        short_requires_schedule=True,
        short_schedule_patterns=["pop. sch."],
        # Bibliography
        bibliography_quoted_title="United States, Census, 1900.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1910 Census - FamilySearch does NOT extract line numbers
    # =========================================================================
    configs[1910] = CensusYearConfig(
        year=1910,
        description="Thirteenth U.S. Census (no line numbers from FamilySearch)",
        # Source name
        source_name_prefix="Fed Census: 1910,",
        source_name_requires_ed=True,
        source_name_ed_pattern=r"\[ED (\d+),",
        source_name_requires_sheet=True,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=False,  # FamilySearch doesn't provide line numbers
        source_name_line_required_with_sheet_only=False,
        source_name_requires_family=False,
        # Footnote
        footnote_census_ref="1910 U.S. census",
        footnote_requires_ed=True,
        footnote_ed_pattern=r"enumeration district \(ED\)",
        footnote_requires_sheet=True,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=False,
        footnote_line_required_with_sheet_only=False,
        footnote_requires_family=False,
        footnote_quoted_title="United States, Census, 1910,",
        footnote_requires_schedule=False,
        footnote_schedule_patterns=None,
        # Short footnote
        short_census_ref="1910 U.S. census",
        short_requires_ed=True,
        short_ed_abbreviation="E.D.",
        short_requires_sheet=True,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=False,
        short_line_required_with_sheet_only=False,
        short_requires_family=False,
        short_requires_ending_period=True,
        short_requires_schedule=False,
        short_schedule_patterns=None,
        # Bibliography
        bibliography_quoted_title="United States, Census, 1910.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1920 Census
    # =========================================================================
    configs[1920] = CensusYearConfig(
        year=1920,
        description="Fourteenth U.S. Census",
        # Source name
        source_name_prefix="Fed Census: 1920,",
        source_name_requires_ed=True,
        source_name_ed_pattern=r"\[ED (\d+(-\d+)?),",  # Accepts both "ED 29" and "ED 13-22"
        source_name_requires_sheet=True,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=True,
        source_name_line_required_with_sheet_only=False,
        source_name_requires_family=False,
        # Footnote
        footnote_census_ref="1920 U.S. census",
        footnote_requires_ed=True,
        footnote_ed_pattern=r"enumeration district \(ED\)",
        footnote_requires_sheet=True,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=True,
        footnote_line_required_with_sheet_only=False,
        footnote_requires_family=False,
        footnote_quoted_title="United States, Census, 1920,",
        footnote_requires_schedule=False,
        footnote_schedule_patterns=None,
        # Short footnote
        short_census_ref="1920 U.S. census",
        short_requires_ed=True,
        short_ed_abbreviation="E.D.",
        short_requires_sheet=True,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=True,
        short_line_required_with_sheet_only=False,
        short_requires_family=False,
        short_requires_ending_period=True,
        short_requires_schedule=False,
        short_schedule_patterns=None,
        # Bibliography
        bibliography_quoted_title="United States, Census, 1920.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1930 Census
    # =========================================================================
    configs[1930] = CensusYearConfig(
        year=1930,
        description="Fifteenth U.S. Census",
        # Source name
        source_name_prefix="Fed Census: 1930,",
        source_name_requires_ed=True,
        source_name_ed_pattern=r"\[ED (\d+(-\d+)?),",  # Accepts both "ED 29" and "ED 20-14"
        source_name_requires_sheet=True,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=True,
        source_name_line_required_with_sheet_only=False,
        source_name_requires_family=False,
        # Footnote
        footnote_census_ref="1930 U.S. census",
        footnote_requires_ed=True,
        footnote_ed_pattern=r"enumeration district \(ED\)",
        footnote_requires_sheet=True,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=True,
        footnote_line_required_with_sheet_only=False,
        footnote_requires_family=False,
        footnote_quoted_title="United States, Census, 1930,",
        footnote_requires_schedule=False,
        footnote_schedule_patterns=None,
        # Short footnote
        short_census_ref="1930 U.S. census",
        short_requires_ed=True,
        short_ed_abbreviation="E.D.",
        short_requires_sheet=True,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=True,
        short_line_required_with_sheet_only=False,
        short_requires_family=False,
        short_requires_ending_period=True,
        short_requires_schedule=False,
        short_schedule_patterns=None,
        # Bibliography
        bibliography_quoted_title="United States, Census, 1930.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1940 Census
    # =========================================================================
    configs[1940] = CensusYearConfig(
        year=1940,
        description="Sixteenth U.S. Census",
        # Source name
        source_name_prefix="Fed Census: 1940,",
        source_name_requires_ed=True,
        source_name_ed_pattern=r"\[ED (\d+[A-Z]?-\d+[A-Z]?),",
        source_name_requires_sheet=True,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=True,
        source_name_line_required_with_sheet_only=False,
        source_name_requires_family=False,
        # Footnote
        footnote_census_ref="1940 U.S. census",
        footnote_requires_ed=True,
        footnote_ed_pattern=r"enumeration district \(ED\)",
        footnote_requires_sheet=True,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=True,
        footnote_line_required_with_sheet_only=False,
        footnote_requires_family=False,
        footnote_quoted_title="United States, Census, 1940,",
        footnote_requires_schedule=False,
        footnote_schedule_patterns=None,
        # Short footnote
        short_census_ref="1940 U.S. census",
        short_requires_ed=True,
        short_ed_abbreviation="E.D.",
        short_requires_sheet=True,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=True,
        short_line_required_with_sheet_only=False,
        short_requires_family=False,
        short_requires_ending_period=True,
        short_requires_schedule=False,
        short_schedule_patterns=None,
        # Bibliography
        bibliography_quoted_title="United States, Census, 1940.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1950 Census - Can use stamp instead of sheet
    # =========================================================================
    configs[1950] = CensusYearConfig(
        year=1950,
        description="Seventeenth U.S. Census - stamp format available",
        # Source name
        source_name_prefix="Fed Census: 1950,",
        source_name_requires_ed=True,
        source_name_ed_pattern=r"\[ED (\d+[A-Z]?-\d+[A-Z]?),",
        source_name_requires_sheet=False,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=True,  # Either sheet or stamp
        source_name_requires_line=True,
        source_name_line_required_with_sheet_only=True,  # Line only with sheet format
        source_name_requires_family=False,
        # Footnote
        footnote_census_ref="1950 U.S. census",
        footnote_requires_ed=True,
        footnote_ed_pattern=r"enumeration district \(ED\)",
        footnote_requires_sheet=False,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=True,
        footnote_requires_line=True,
        footnote_line_required_with_sheet_only=True,
        footnote_requires_family=False,
        footnote_quoted_title="United States, Census, 1950,",
        footnote_requires_schedule=False,
        footnote_schedule_patterns=None,
        # Short footnote
        short_census_ref="1950 U.S. census",
        short_requires_ed=True,
        short_ed_abbreviation="E.D.",
        short_requires_sheet=False,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=True,
        short_requires_line=True,
        short_line_required_with_sheet_only=True,
        short_requires_family=False,
        short_requires_ending_period=True,
        short_requires_schedule=False,
        short_schedule_patterns=None,
        # Bibliography
        bibliography_quoted_title="United States, Census, 1950.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1850 Slave Schedule
    # =========================================================================
    configs["1850-slave"] = CensusYearConfig(
        year=1850,
        description="Seventh U.S. Census - Slave Schedule",
        # Source name: uses "page" not "sheet"
        source_name_prefix="Fed Census Slave Schedule: 1850,",
        source_name_requires_ed=False,
        source_name_ed_pattern=None,
        source_name_requires_sheet=False,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=False,  # Line format varies
        source_name_line_required_with_sheet_only=False,
        source_name_requires_family=False,
        # Footnote
        footnote_census_ref="1850 U.S. census",
        footnote_requires_ed=False,
        footnote_ed_pattern=None,
        footnote_requires_sheet=False,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=False,
        footnote_line_required_with_sheet_only=False,
        footnote_requires_family=False,
        footnote_quoted_title="United States, Census (Slave Schedule), 1850,",
        footnote_requires_schedule=True,
        footnote_schedule_patterns=["slave schedule"],
        # Short footnote
        short_census_ref="1850 U.S. census",
        short_requires_ed=False,
        short_ed_abbreviation=None,
        short_requires_sheet=False,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=False,
        short_line_required_with_sheet_only=False,
        short_requires_family=False,
        short_requires_ending_period=True,
        short_requires_schedule=True,
        short_schedule_patterns=["slave sch."],
        # Bibliography
        bibliography_quoted_title="United States, Census (Slave Schedule), 1850.",
        # Quality
        expected_citation_quality="PDO",
    )

    # =========================================================================
    # 1860 Slave Schedule
    # =========================================================================
    configs["1860-slave"] = CensusYearConfig(
        year=1860,
        description="Eighth U.S. Census - Slave Schedule",
        # Source name: uses "page" not "sheet"
        source_name_prefix="Fed Census Slave Schedule: 1860,",
        source_name_requires_ed=False,
        source_name_ed_pattern=None,
        source_name_requires_sheet=False,
        source_name_requires_stamp=False,
        source_name_allows_sheet_or_stamp=False,
        source_name_requires_line=False,  # Line format varies (line X, lines X-Y, etc.)
        source_name_line_required_with_sheet_only=False,
        source_name_requires_family=False,
        # Footnote
        footnote_census_ref="1860 U.S. census",
        footnote_requires_ed=False,
        footnote_ed_pattern=None,
        footnote_requires_sheet=False,
        footnote_requires_stamp=False,
        footnote_allows_sheet_or_stamp=False,
        footnote_requires_line=False,
        footnote_line_required_with_sheet_only=False,
        footnote_requires_family=False,
        footnote_quoted_title="United States, Census (Slave Schedule), 1860,",
        footnote_requires_schedule=True,
        footnote_schedule_patterns=["slave schedule"],
        # Short footnote
        short_census_ref="1860 U.S. census",
        short_requires_ed=False,
        short_ed_abbreviation=None,
        short_requires_sheet=False,
        short_requires_stamp=False,
        short_allows_sheet_or_stamp=False,
        short_requires_line=False,
        short_line_required_with_sheet_only=False,
        short_requires_family=False,
        short_requires_ending_period=True,
        short_requires_schedule=True,
        short_schedule_patterns=["slave sch."],
        # Bibliography
        bibliography_quoted_title="United States, Census (Slave Schedule), 1860.",
        # Quality
        expected_citation_quality="PDO",
    )

    return configs
