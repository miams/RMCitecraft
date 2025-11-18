"""Unit tests for citation formatter."""

import pytest

from rmcitecraft.models.citation import ParsedCitation
from rmcitecraft.parsers.citation_formatter import CitationFormatter


class TestCitationFormatter:
    """Test Evidence Explained citation formatting."""

    @pytest.fixture
    def formatter(self) -> CitationFormatter:
        """Create formatter instance."""
        return CitationFormatter()

    @pytest.fixture
    def ella_ijams_citation(self) -> ParsedCitation:
        """Create Ella Ijams 1900 census citation (from README example)."""
        return ParsedCitation(
            citation_id=1,
            source_name="Fed Census: 1900, Ohio, Noble [citing sheet 3B, family 57] Ijams, Ella",
            familysearch_entry="...",
            census_year=1900,
            state="Ohio",
            county="Noble",
            town_ward="Olive Township Caldwell village",
            enumeration_district="95",
            sheet="3B",
            family_number="57",
            person_name="Ella Ijams",
            given_name="Ella",
            surname="Ijams",
            familysearch_url="https://familysearch.org/ark:/61903/1:1:MM6X-FGZ",
            access_date="24 July 2015",
            nara_publication="T623",
            fhl_microfilm="1,241,311",
            is_complete=True,
        )

    @pytest.fixture
    def william_ijams_citation(self) -> ParsedCitation:
        """Create William H. Ijams 1910 census citation (from README example)."""
        return ParsedCitation(
            citation_id=2,
            source_name=(
                "Fed Census: 1910, Maryland, Baltimore "
                "[citing enumeration district (ED) ED 214, sheet 3B] Ijams, William H."
            ),
            familysearch_entry="...",
            census_year=1910,
            state="Maryland",
            county="Baltimore City",
            town_ward="Baltimore Ward 13",
            enumeration_district="214",
            sheet="3B",
            family_number="52",
            person_name="William H. Ijams",
            given_name="William H.",
            surname="Ijams",
            familysearch_url="https://www.familysearch.org/ark:/61903/1:1:M2F4-SV9",
            access_date="27 November 2015",
            nara_publication="T624",
            fhl_microfilm="1,374,570",
            is_complete=True,
        )

    def test_format_1900_footnote(
        self,
        formatter: CitationFormatter,
        ella_ijams_citation: ParsedCitation,
    ) -> None:
        """Test 1900 census footnote formatting (Ella Ijams example)."""
        footnote, _, _ = formatter.format(ella_ijams_citation)

        # Expected from README:
        # 1900 U.S. census, Noble County, Ohio, population schedule,
        # Olive Township Caldwell village, enumeration district (ED) 95,
        # sheet 3B, family 57, Ella Ijams; imaged, "1900 United States Federal Census,"
        # <i>FamilySearch</i> (https://familysearch.org/ark:/61903/1:1:MM6X-FGZ :
        # accessed 24 July 2015).

        assert "1900 U.S. census" in footnote
        assert "Noble County" in footnote
        assert "Ohio" in footnote
        assert "population schedule" in footnote
        assert "Olive Township Caldwell village" in footnote
        assert "enumeration district (ED) 95" in footnote
        assert "sheet 3B" in footnote
        assert "family 57" in footnote
        assert "Ella Ijams" in footnote
        assert "<i>FamilySearch</i>" in footnote
        assert "https://familysearch.org/ark:/61903/1:1:MM6X-FGZ" in footnote
        assert "accessed 24 July 2015" in footnote

    def test_format_1900_short_footnote(
        self,
        formatter: CitationFormatter,
        ella_ijams_citation: ParsedCitation,
    ) -> None:
        """Test 1900 census short footnote formatting."""
        _, short_footnote, _ = formatter.format(ella_ijams_citation)

        # Expected from README:
        # 1900 U.S. census, Noble Co., Oh., pop. sch.,
        # Olive Township, E.D. 95, sheet 3B, Ella Ijams.

        assert "1900 U.S. census" in short_footnote
        assert "Noble Co." in short_footnote
        assert "OH." in short_footnote or "Oh." in short_footnote
        assert "pop. sch." in short_footnote
        assert ("Olive Township" in short_footnote or "Olive Twp." in short_footnote)
        assert "E.D. 95" in short_footnote
        assert "sheet 3B" in short_footnote
        assert "Ella Ijams" in short_footnote

    def test_format_1900_bibliography(
        self,
        formatter: CitationFormatter,
        ella_ijams_citation: ParsedCitation,
    ) -> None:
        """Test 1900 census bibliography formatting."""
        _, _, bibliography = formatter.format(ella_ijams_citation)

        # Expected from README:
        # U.S. Ohio. Noble County. 1900 U.S Census. Population Schedule. Imaged.
        # "1900 United States Federal Census". <i>FamilySearch</i>
        # https://www.familysearch.org/ark:/61903/1:1:MM6X-FGZ : 2015.

        assert "U.S." in bibliography
        assert "Ohio" in bibliography
        assert "Noble County" in bibliography
        assert "1900 U.S Census" in bibliography
        assert "Population Schedule" in bibliography
        assert "Imaged" in bibliography
        assert "<i>FamilySearch</i>" in bibliography
        assert "https://familysearch.org/ark:/61903/1:1:MM6X-FGZ" in bibliography
        assert "2015" in bibliography

    def test_format_1910_footnote(
        self,
        formatter: CitationFormatter,
        william_ijams_citation: ParsedCitation,
    ) -> None:
        """Test 1910 census footnote formatting (William H. Ijams example)."""
        footnote, _, _ = formatter.format(william_ijams_citation)

        # Expected: 1910-1940 omit "population schedule" (only type that survived)
        # 1910 U.S. census, Baltimore City, Maryland, Baltimore Ward 13,
        # enumeration district (ED) 214, sheet 3B, family 52,
        # William H. Ijams; imaged, "United States Census, 1910,"
        # <i>FamilySearch</i>, (https://www.familysearch.org/ark:/61903/1:1:M2F4-SV9 :
        # accessed 27 November 2015).

        assert "1910 U.S. census" in footnote
        assert "Baltimore City" in footnote
        assert "Maryland" in footnote
        # 1910-1940: "population schedule" omitted (only type that survived)
        assert "population schedule" not in footnote
        assert "Baltimore Ward 13" in footnote
        assert "enumeration district (ED) 214" in footnote
        assert "sheet 3B" in footnote
        assert "family 52" in footnote
        assert "William H. Ijams" in footnote
        assert "<i>FamilySearch</i>" in footnote

    def test_format_1910_short_footnote(
        self,
        formatter: CitationFormatter,
        william_ijams_citation: ParsedCitation,
    ) -> None:
        """Test 1910 census short footnote formatting."""
        _, short_footnote, _ = formatter.format(william_ijams_citation)

        # Expected: 1910-1940 omit "pop. sch." (only population schedules survived)
        # 1910 U.S. census, Baltimore City, Md., Baltimore Ward 13,
        # E.D. 214, sheet 3B, William H. Ijams.

        assert "1910 U.S. census" in short_footnote
        assert "Baltimore City" in short_footnote
        assert "MD." in short_footnote or "Md." in short_footnote
        # 1910-1940: "pop. sch." omitted (only population schedules survived)
        assert "pop. sch." not in short_footnote
        assert ("Baltimore Ward 13" in short_footnote or "Baltimore Ward" in short_footnote)
        assert "E.D. 214" in short_footnote
        assert "sheet 3B" in short_footnote
        assert "William H. Ijams" in short_footnote

    def test_format_1850_citation(self, formatter: CitationFormatter) -> None:
        """Test 1850 census formatting (no ED required)."""
        citation_1850 = ParsedCitation(
            citation_id=3,
            source_name="Fed Census: 1850, New York, Kings",
            familysearch_entry="...",
            census_year=1850,
            state="New York",
            county="Kings",
            town_ward="Brooklyn",
            enumeration_district=None,  # Not required for 1850
            sheet="15",
            family_number="200",
            dwelling_number="198",
            person_name="John Smith",
            given_name="John",
            surname="Smith",
            familysearch_url="https://familysearch.org/ark:/12345/1:1:ABCD",
            access_date="1 January 2020",
            is_complete=True,
        )

        footnote, short_footnote, bibliography = formatter.format(citation_1850)

        # 1850 should have "population schedule" but not ED
        assert "population schedule" in footnote
        assert "enumeration district" not in footnote
        assert "Brooklyn" in footnote
        assert "sheet 15" in footnote

        # Should have dwelling and family
        assert "dwelling 198" in footnote
        assert "family 200" in footnote

    def test_format_1790_citation(self, formatter: CitationFormatter) -> None:
        """Test 1790 census formatting (no population schedule, no ED)."""
        citation_1790 = ParsedCitation(
            citation_id=4,
            source_name="Fed Census: 1790, Virginia, Fairfax",
            familysearch_entry="...",
            census_year=1790,
            state="Virginia",
            county="Fairfax",
            town_ward="Alexandria",
            enumeration_district=None,
            sheet="5",
            family_number=None,
            person_name="George Washington",
            given_name="George",
            surname="Washington",
            familysearch_url="https://familysearch.org/ark:/12345/1:1:WXYZ",
            access_date="4 July 2020",
            is_complete=True,
        )

        footnote, short_footnote, bibliography = formatter.format(citation_1790)

        # 1790 should NOT have "population schedule" or ED
        assert "population schedule" not in footnote
        assert "enumeration district" not in footnote
        assert "1790 U.S. census" in footnote
        assert "Fairfax County" in footnote
        assert "Virginia" in footnote
        assert "Alexandria" in footnote
        assert "sheet 5" in footnote

    def test_state_abbreviations(self, formatter: CitationFormatter) -> None:
        """Test state abbreviation in short footnote."""
        states_to_test = [
            ("Ohio", "OH"),
            ("Maryland", "MD"),
            ("California", "CA"),
            ("New York", "NY"),
        ]

        for state_name, expected_abbrev in states_to_test:
            citation = ParsedCitation(
                citation_id=1,
                source_name=f"Fed Census: 1900, {state_name}, Test County",
                familysearch_entry="...",
                census_year=1900,
                state=state_name,
                county="Test County",
                person_name="Test Person",
                given_name="Test",
                surname="Person",
                familysearch_url="https://familysearch.org/test",
                access_date="1 Jan 2020",
                is_complete=True,
            )

            _, short_footnote, _ = formatter.format(citation)
            # Check for state abbreviation (with period)
            assert f"{expected_abbrev}." in short_footnote or f"{expected_abbrev.title()}." in short_footnote
