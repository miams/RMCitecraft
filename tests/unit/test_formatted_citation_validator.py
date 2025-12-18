"""Unit tests for FormattedCitationValidator and is_citation_needs_processing."""

import pytest

from rmcitecraft.validation.data_quality import (
    FormattedCitationValidator,
    is_citation_needs_processing,
)


class TestFormattedCitationValidator:
    """Test FormattedCitationValidator class methods."""

    # =========================================================================
    # validate_footnote Tests
    # =========================================================================

    def test_validate_footnote_empty(self):
        """Test empty footnote returns False."""
        assert FormattedCitationValidator.validate_footnote(None, 1940) is False
        assert FormattedCitationValidator.validate_footnote("", 1940) is False
        assert FormattedCitationValidator.validate_footnote("   ", 1940) is False

    def test_validate_footnote_missing_year(self):
        """Test footnote missing census year returns False."""
        footnote = "U.S. census, Noble County, Ohio, FamilySearch, sheet 3B"
        assert FormattedCitationValidator.validate_footnote(footnote, 1940) is False

    def test_validate_footnote_missing_census(self):
        """Test footnote missing 'census' returns False."""
        footnote = "1940 U.S. enumeration, Noble County, Ohio, FamilySearch, sheet 3B"
        assert FormattedCitationValidator.validate_footnote(footnote, 1940) is False

    def test_validate_footnote_missing_familysearch(self):
        """Test footnote missing FamilySearch reference returns False."""
        footnote = "1940 U.S. census, Noble County, Ohio, E.D. 95, sheet 3B"
        assert FormattedCitationValidator.validate_footnote(footnote, 1940) is False

    def test_validate_footnote_missing_sheet(self):
        """Test footnote missing sheet/page returns False."""
        footnote = "1940 U.S. census, Noble County, Ohio, E.D. 95, FamilySearch"
        assert FormattedCitationValidator.validate_footnote(footnote, 1940) is False

    def test_validate_footnote_missing_ed_for_1940(self):
        """Test 1940 footnote missing ED returns False."""
        footnote = (
            "1940 U.S. census, Noble County, Ohio, sheet 3B, "
            "FamilySearch (https://familysearch.org)"
        )
        assert FormattedCitationValidator.validate_footnote(footnote, 1940) is False

    def test_validate_footnote_valid_1940_with_ed_abbreviation(self):
        """Test valid 1940 footnote with E.D. abbreviation."""
        footnote = (
            "1940 U.S. census, Noble County, Ohio, population schedule, "
            "enumeration district (E.D.) 95, sheet 3B, John Smith; "
            "FamilySearch (https://familysearch.org/ark:/61903/1:1:TEST)"
        )
        assert FormattedCitationValidator.validate_footnote(footnote, 1940) is True

    def test_validate_footnote_valid_1940_with_enumeration_district(self):
        """Test valid 1940 footnote with 'enumeration district'."""
        footnote = (
            "1940 U.S. census, Noble County, Ohio, population schedule, "
            "enumeration district 95, sheet 3B, John Smith; "
            "FamilySearch (https://familysearch.org/ark:/61903/1:1:TEST)"
        )
        assert FormattedCitationValidator.validate_footnote(footnote, 1940) is True

    def test_validate_footnote_1880_without_ed(self):
        """Test 1880 footnote without ED is valid (ED not required pre-1900)."""
        footnote = (
            "1880 U.S. census, Noble County, Ohio, population schedule, "
            "sheet 3B, John Smith; "
            "FamilySearch (https://familysearch.org/ark:/61903/1:1:TEST)"
        )
        assert FormattedCitationValidator.validate_footnote(footnote, 1880) is True

    def test_validate_footnote_with_page_instead_of_sheet(self):
        """Test footnote with 'page' instead of 'sheet' is valid."""
        footnote = (
            "1940 U.S. census, Noble County, Ohio, E.D. 95, page 3B, "
            "FamilySearch (https://familysearch.org)"
        )
        assert FormattedCitationValidator.validate_footnote(footnote, 1940) is True

    # =========================================================================
    # validate_short_footnote Tests
    # =========================================================================

    def test_validate_short_footnote_empty(self):
        """Test empty short footnote returns False."""
        assert FormattedCitationValidator.validate_short_footnote(None, 1940) is False
        assert FormattedCitationValidator.validate_short_footnote("", 1940) is False

    def test_validate_short_footnote_missing_year(self):
        """Test short footnote missing year returns False."""
        short = "U.S. census, Noble Co., Oh., sheet 3B, John Smith"
        assert FormattedCitationValidator.validate_short_footnote(short, 1940) is False

    def test_validate_short_footnote_missing_census(self):
        """Test short footnote missing 'census' or 'pop. sch.' returns False."""
        short = "1940 U.S. enumeration, Noble Co., sheet 3B, John Smith"
        assert FormattedCitationValidator.validate_short_footnote(short, 1940) is False

    def test_validate_short_footnote_missing_sheet(self):
        """Test short footnote missing sheet returns False."""
        short = "1940 U.S. census, Noble Co., Oh., E.D. 95, John Smith"
        assert FormattedCitationValidator.validate_short_footnote(short, 1940) is False

    def test_validate_short_footnote_valid_with_census(self):
        """Test valid short footnote with 'census'."""
        short = "1940 U.S. census, Noble Co., Oh., E.D. 95, sheet 3B, John Smith"
        assert FormattedCitationValidator.validate_short_footnote(short, 1940) is True

    def test_validate_short_footnote_valid_with_pop_sch(self):
        """Test valid short footnote with 'pop. sch.' abbreviation."""
        short = "1940 U.S. pop. sch., Noble Co., Oh., E.D. 95, sheet 3B, John Smith"
        assert FormattedCitationValidator.validate_short_footnote(short, 1940) is True

    # =========================================================================
    # validate_bibliography Tests
    # =========================================================================

    def test_validate_bibliography_empty(self):
        """Test empty bibliography returns False."""
        assert FormattedCitationValidator.validate_bibliography(None, 1940) is False
        assert FormattedCitationValidator.validate_bibliography("", 1940) is False

    def test_validate_bibliography_missing_year(self):
        """Test bibliography missing year returns False."""
        bib = "U.S. Ohio. Noble County. U.S Census. FamilySearch."
        assert FormattedCitationValidator.validate_bibliography(bib, 1940) is False

    def test_validate_bibliography_missing_census(self):
        """Test bibliography missing 'census' returns False."""
        bib = "1940 U.S. Ohio. Noble County. FamilySearch."
        assert FormattedCitationValidator.validate_bibliography(bib, 1940) is False

    def test_validate_bibliography_missing_familysearch(self):
        """Test bibliography missing FamilySearch returns False."""
        bib = "U.S. Ohio. Noble County. 1940 U.S Census. Population Schedule."
        assert FormattedCitationValidator.validate_bibliography(bib, 1940) is False

    def test_validate_bibliography_valid(self):
        """Test valid bibliography."""
        bib = (
            'U.S. Ohio. Noble County. 1940 U.S Census. Population Schedule. '
            'Imaged. "1940 United States Federal Census". FamilySearch '
            'https://www.familysearch.org/ark:/61903/1:1:TEST : 2023.'
        )
        assert FormattedCitationValidator.validate_bibliography(bib, 1940) is True

    # =========================================================================
    # _has_enumeration_district_reference Tests
    # =========================================================================

    def test_ed_reference_enumeration_district(self):
        """Test 'enumeration district' is detected."""
        text = "enumeration district 95"
        assert FormattedCitationValidator._has_enumeration_district_reference(text) is True

    def test_ed_reference_e_d_abbreviation(self):
        """Test 'E.D.' abbreviation is detected."""
        text = "e.d. 95"
        assert FormattedCitationValidator._has_enumeration_district_reference(text) is True

    def test_ed_reference_ed_uppercase(self):
        """Test 'E.D.' uppercase is detected."""
        text = "E.D. 95"
        assert FormattedCitationValidator._has_enumeration_district_reference(text.lower()) is True

    def test_ed_reference_standalone_ed(self):
        """Test standalone 'ed' with number is detected."""
        text = ", ed 95,"
        assert FormattedCitationValidator._has_enumeration_district_reference(text) is True

    def test_ed_reference_united_not_matched(self):
        """Test 'united' does not match as ED."""
        text = "united states federal"
        assert FormattedCitationValidator._has_enumeration_district_reference(text) is False

    def test_ed_reference_accessed_not_matched(self):
        """Test 'accessed' does not match as ED."""
        text = "accessed 24 july"
        assert FormattedCitationValidator._has_enumeration_district_reference(text) is False

    def test_ed_reference_district_ed_pattern(self):
        """Test 'district (ed)' pattern is detected."""
        text = "district (ed) 95"
        assert FormattedCitationValidator._has_enumeration_district_reference(text) is True

    # =========================================================================
    # is_citation_processed Tests
    # =========================================================================

    def test_is_citation_processed_same_footnote_and_short(self):
        """Test same footnote/short_footnote means not processed."""
        same_text = "Some unprocessed citation text"
        result = FormattedCitationValidator.is_citation_processed(
            footnote=same_text,
            short_footnote=same_text,
            bibliography=same_text,
            census_year=1940
        )
        assert result is False

    def test_is_citation_processed_empty_citations(self):
        """Test empty citations means not processed."""
        result = FormattedCitationValidator.is_citation_processed(
            footnote=None,
            short_footnote=None,
            bibliography=None,
            census_year=1940
        )
        assert result is False

    def test_is_citation_processed_valid_different_citations(self):
        """Test valid different citations means processed."""
        footnote = (
            "1940 U.S. census, Noble County, Ohio, population schedule, "
            "enumeration district (E.D.) 95, sheet 3B, line 45, John Smith; "
            'FamilySearch (https://familysearch.org/ark:/61903/1:1:TEST)'
        )
        short_footnote = (
            "1940 U.S. census, Noble Co., Ohio, pop. sch., E.D. 95, sheet 3B, John Smith."
        )
        bibliography = (
            'U.S. Ohio. Noble County. 1940 U.S Census. Population Schedule. '
            'Imaged. "1940 United States Federal Census". FamilySearch '
            'https://www.familysearch.org/ark:/61903/1:1:TEST : 2023.'
        )

        result = FormattedCitationValidator.is_citation_processed(
            footnote=footnote,
            short_footnote=short_footnote,
            bibliography=bibliography,
            census_year=1940
        )
        assert result is True

    def test_is_citation_processed_invalid_footnote(self):
        """Test invalid footnote means not processed even if different."""
        footnote = "1940 census, Ohio, sheet 3B"  # Missing required elements
        short_footnote = "1940 U.S. census, Noble Co., Ohio, pop. sch., sheet 3B, John Smith."
        bibliography = (
            'U.S. Ohio. Noble County. 1940 U.S Census. FamilySearch.'
        )

        result = FormattedCitationValidator.is_citation_processed(
            footnote=footnote,
            short_footnote=short_footnote,
            bibliography=bibliography,
            census_year=1940
        )
        assert result is False


class TestIsCitationNeedsProcessing:
    """Test is_citation_needs_processing convenience function."""

    def test_empty_citations_need_processing(self):
        """Test empty citations need processing."""
        result = is_citation_needs_processing(None, None, None, 1940)
        assert result is True

    def test_same_footnote_short_footnote_needs_processing(self):
        """Test same footnote/short_footnote needs processing."""
        same_text = "Unprocessed citation"
        result = is_citation_needs_processing(same_text, same_text, same_text, 1940)
        assert result is True

    def test_valid_processed_citations_dont_need_processing(self):
        """Test properly processed citations don't need processing."""
        footnote = (
            "1940 U.S. census, Noble County, Ohio, population schedule, "
            "enumeration district (E.D.) 95, sheet 3B, line 45, John Smith; "
            'FamilySearch (https://familysearch.org/ark:/61903/1:1:TEST)'
        )
        short_footnote = (
            "1940 U.S. census, Noble Co., Ohio, pop. sch., E.D. 95, sheet 3B, John Smith."
        )
        bibliography = (
            'U.S. Ohio. Noble County. 1940 U.S Census. Population Schedule. '
            'Imaged. "1940 United States Federal Census". FamilySearch '
            'https://www.familysearch.org/ark:/61903/1:1:TEST : 2023.'
        )

        result = is_citation_needs_processing(
            footnote, short_footnote, bibliography, 1940
        )
        assert result is False

    def test_missing_ed_for_1940_needs_processing(self):
        """Test 1940 citation missing ED needs processing."""
        footnote = (
            "1940 U.S. census, Noble County, Ohio, population schedule, "
            "sheet 3B, line 45, John Smith; "
            'FamilySearch (https://familysearch.org/ark:/61903/1:1:TEST)'
        )
        short_footnote = (
            "1940 U.S. census, Noble Co., Ohio, pop. sch., sheet 3B, John Smith."
        )
        bibliography = (
            'U.S. Ohio. Noble County. 1940 U.S Census. FamilySearch.'
        )

        result = is_citation_needs_processing(
            footnote, short_footnote, bibliography, 1940
        )
        assert result is True

    def test_1880_without_ed_doesnt_need_processing(self):
        """Test 1880 citation without ED doesn't need processing."""
        footnote = (
            "1880 U.S. census, Noble County, Ohio, population schedule, "
            "sheet 3B, line 45, John Smith; "
            'FamilySearch (https://familysearch.org/ark:/61903/1:1:TEST)'
        )
        short_footnote = (
            "1880 U.S. census, Noble Co., Ohio, pop. sch., sheet 3B, John Smith."
        )
        bibliography = (
            'U.S. Ohio. Noble County. 1880 U.S Census. FamilySearch.'
        )

        result = is_citation_needs_processing(
            footnote, short_footnote, bibliography, 1880
        )
        assert result is False

    def test_missing_sheet_in_short_footnote_needs_processing(self):
        """Test missing sheet in short footnote needs processing."""
        footnote = (
            "1940 U.S. census, Noble County, Ohio, E.D. 95, sheet 3B, "
            "FamilySearch (https://familysearch.org)"
        )
        short_footnote = "1940 U.S. census, Noble Co., Ohio, E.D. 95, John Smith."  # No sheet
        bibliography = (
            'U.S. Ohio. Noble County. 1940 U.S Census. FamilySearch.'
        )

        result = is_citation_needs_processing(
            footnote, short_footnote, bibliography, 1940
        )
        assert result is True

    def test_different_census_years(self):
        """Test validation works across different census years."""
        # Test valid citations for years 1900-1950 (ED required)
        for year in [1900, 1910, 1920, 1930, 1940, 1950]:
            footnote = (
                f"{year} U.S. census, Noble County, Ohio, E.D. 95, sheet 3B, "
                "FamilySearch (https://familysearch.org)"
            )
            short_footnote = f"{year} U.S. census, Noble Co., sheet 3B, John Smith."
            bibliography = f'{year} U.S Census. FamilySearch.'

            result = is_citation_needs_processing(
                footnote, short_footnote, bibliography, year
            )
            # These should NOT need processing (they're valid)
            assert result is False, f"Year {year} should not need processing"

        # Test years before 1900 (ED not required)
        # Pre-1880 uses "page", 1880+ uses "sheet"
        for year in [1850, 1860, 1870]:
            footnote = (
                f"{year} U.S. census, Noble County, Ohio, page 3, "
                "FamilySearch (https://familysearch.org)"
            )
            short_footnote = f"{year} U.S. census, Noble Co., page 3, John Smith."
            bibliography = f'{year} U.S Census. FamilySearch.'

            result = is_citation_needs_processing(
                footnote, short_footnote, bibliography, year
            )
            # These should NOT need processing (ED not required pre-1880, uses page)
            assert result is False, f"Year {year} should not need processing"

        # 1880 uses sheet (introduced same time as enumeration districts)
        footnote = (
            "1880 U.S. census, Noble County, Ohio, sheet 3B, "
            "FamilySearch (https://familysearch.org)"
        )
        short_footnote = "1880 U.S. census, Noble Co., sheet 3B, John Smith."
        bibliography = '1880 U.S Census. FamilySearch.'

        result = is_citation_needs_processing(
            footnote, short_footnote, bibliography, 1880
        )
        # 1880 should NOT need processing (uses sheet, ED optional for 1880)
        assert result is False, "Year 1880 should not need processing"
