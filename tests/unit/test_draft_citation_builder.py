"""Unit tests for DraftCitationBuilder service."""

import pytest
from rmcitecraft.services.draft_citation_builder import DraftCitationBuilder
from rmcitecraft.models.draft_record import DraftRecord
from rmcitecraft.models.citation_data import (
    FamilySearchMetadata,
    get_state_abbreviation,
    get_state_full_name,
)


@pytest.fixture
def citation_builder():
    """Create a DraftCitationBuilder instance."""
    return DraftCitationBuilder()


@pytest.fixture
def sample_ww2_record():
    """Create a sample WW2 draft record."""
    return DraftRecord(
        row_number=1,
        rin=527,
        given_name="John",
        surname="Smith",
        birth_year=1918,
        death_year=1994,
        familysearch_citation='https://familysearch.org/ark:/61903/1:1:ABC123',
        registration_date="1940-10-16",
        state="Pennsylvania",
        county="Allegheny",
        notes=None
    )


@pytest.fixture
def sample_ww1_record():
    """Create a sample WW1 draft record."""
    return DraftRecord(
        row_number=2,
        rin=999,
        given_name="William",
        surname="Jones",
        birth_year=1895,
        death_year=1965,
        familysearch_citation='https://familysearch.org/ark:/61903/3:1:XYZ789',
        registration_date="1917-06-05",
        state="Ohio",
        county="Noble",
        notes=None
    )


class TestStateHelpers:
    """Test state abbreviation helper functions."""

    def test_get_state_abbreviation(self):
        """Test getting state abbreviation from full name."""
        assert get_state_abbreviation("Pennsylvania") == "PA"
        assert get_state_abbreviation("pennsylvania") == "PA"
        assert get_state_abbreviation("PENNSYLVANIA") == "PA"
        assert get_state_abbreviation("Ohio") == "OH"
        assert get_state_abbreviation("New York") == "NY"
        assert get_state_abbreviation("District of Columbia") == "DC"

    def test_get_state_abbreviation_from_abbr(self):
        """Test that abbreviations are returned unchanged."""
        assert get_state_abbreviation("PA") == "PA"
        assert get_state_abbreviation("pa") == "PA"
        assert get_state_abbreviation("OH") == "OH"

    def test_get_state_abbreviation_invalid(self):
        """Test invalid state names return None."""
        assert get_state_abbreviation("Invalid State") is None
        assert get_state_abbreviation("") is None
        assert get_state_abbreviation(None) is None

    def test_get_state_full_name(self):
        """Test getting full state name from abbreviation."""
        assert get_state_full_name("PA") == "Pennsylvania"
        assert get_state_full_name("pa") == "Pennsylvania"
        assert get_state_full_name("OH") == "Ohio"
        assert get_state_full_name("NY") == "New York"
        assert get_state_full_name("DC") == "District Of Columbia"

    def test_get_state_full_name_invalid(self):
        """Test invalid abbreviations return None."""
        assert get_state_full_name("XX") is None
        assert get_state_full_name("") is None
        assert get_state_full_name(None) is None


class TestParseFamilySearchURL:
    """Test parsing FamilySearch URLs and citations."""

    def test_parse_url_with_ark(self, citation_builder):
        """Test parsing URL with ARK identifier."""
        url = "https://familysearch.org/ark:/61903/1:1:ABC123"
        metadata = citation_builder.parse_familysearch_url(url)

        assert metadata.ark_id == "61903/1:1:ABC123"
        assert metadata.url == url

    def test_parse_citation_with_state(self, citation_builder):
        """Test parsing citation text with state name."""
        citation = (
            '"Pennsylvania, World War II Draft Registration Cards, 1940-1945", '
            'FamilySearch (https://familysearch.org/ark:/61903/1:1:Q2SF-G31L)'
        )
        metadata = citation_builder.parse_familysearch_url(citation)

        assert metadata.state == "Pennsylvania"
        assert metadata.state_abbr == "PA"
        assert metadata.ark_id == "61903/1:1:Q2SF-G31L"
        assert metadata.collection_name == "Pennsylvania, World War II Draft Registration Cards, 1940-1945"

    def test_parse_ww2_citation(self, citation_builder):
        """Test parsing WW2 citation."""
        citation = (
            '"Ohio, World War II Draft Registration Cards, 1940-1947", '
            'FamilySearch (https://familysearch.org/ark:/61903/1:1:XYZ)'
        )
        metadata = citation_builder.parse_familysearch_url(citation)

        assert metadata.registration_type == "WW2"
        assert metadata.is_ww2
        assert not metadata.is_ww1
        assert metadata.state == "Ohio"

    def test_parse_ww1_citation(self, citation_builder):
        """Test parsing WW1 citation."""
        citation = (
            '"United States, World War I Draft Registration Cards, 1917-1918", '
            'FamilySearch (https://familysearch.org/ark:/61903/3:1:ABC)'
        )
        metadata = citation_builder.parse_familysearch_url(citation)

        assert metadata.registration_type == "WW1"
        assert metadata.is_ww1
        assert not metadata.is_ww2

    def test_parse_with_state_hint(self, citation_builder):
        """Test parsing with state hint."""
        citation = "https://familysearch.org/ark:/61903/1:1:ABC"
        metadata = citation_builder.parse_familysearch_url(citation, state_hint="PA")

        assert metadata.state == "Pennsylvania"
        assert metadata.state_abbr == "PA"

    def test_parse_with_year(self, citation_builder):
        """Test year extraction from citation."""
        citation = '"Pennsylvania Draft Cards, 1942", FamilySearch'
        metadata = citation_builder.parse_familysearch_url(citation)

        assert metadata.year == 1942
        assert metadata.registration_type == "WW2"

    def test_parse_empty_citation(self, citation_builder):
        """Test parsing empty citation."""
        metadata = citation_builder.parse_familysearch_url("")
        assert metadata.ark_id is None
        assert metadata.state is None


class TestMetadataProperties:
    """Test FamilySearchMetadata properties."""

    def test_county_citation_form(self):
        """Test county citation form property."""
        metadata = FamilySearchMetadata(county="Noble")
        assert metadata.county_citation_form == "Noble County"

        metadata = FamilySearchMetadata(county="Noble County")
        assert metadata.county_citation_form == "Noble County"

        metadata = FamilySearchMetadata(county=None)
        assert metadata.county_citation_form == ""

    def test_county_short_form(self):
        """Test county short form property."""
        metadata = FamilySearchMetadata(county="Noble")
        assert metadata.county_short_form == "Noble Co."

        metadata = FamilySearchMetadata(county="Noble County")
        assert metadata.county_short_form == "Noble Co."

        metadata = FamilySearchMetadata(county=None)
        assert metadata.county_short_form == ""

    def test_state_forms(self):
        """Test state citation forms."""
        metadata = FamilySearchMetadata(state="Pennsylvania", state_abbr="PA")
        assert metadata.state_citation_form == "Pennsylvania"
        assert metadata.state_short_form == "PA"


class TestFormatFootnote:
    """Test footnote formatting."""

    def test_format_ww2_footnote_full(self, citation_builder, sample_ww2_record):
        """Test formatting WW2 footnote with all details."""
        metadata = FamilySearchMetadata(
            state="Pennsylvania",
            state_abbr="PA",
            county="Allegheny",
            year=1940,
            registration_type="WW2",
            collection_name="Pennsylvania, World War II Draft Registration Cards, 1940-1945",
            url="https://familysearch.org/ark:/61903/1:1:ABC123"
        )

        footnote = citation_builder.format_footnote(sample_ww2_record, metadata)

        assert "1940 U.S. draft registration" in footnote
        assert "Allegheny County, Pennsylvania" in footnote
        assert "John Smith" in footnote
        assert "imaged" in footnote
        assert "FamilySearch" in footnote
        assert metadata.url in footnote

    def test_format_ww2_footnote_no_county(self, citation_builder, sample_ww2_record):
        """Test formatting WW2 footnote without county."""
        sample_ww2_record.county = None
        metadata = FamilySearchMetadata(
            state="Pennsylvania",
            state_abbr="PA",
            year=1940,
            registration_type="WW2",
            collection_name="Pennsylvania, World War II Draft Registration Cards, 1940-1945",
            url="https://familysearch.org/ark:/61903/1:1:ABC123"
        )

        footnote = citation_builder.format_footnote(sample_ww2_record, metadata)

        assert "1940 U.S. draft registration" in footnote
        assert "Pennsylvania" in footnote
        assert "Allegheny" not in footnote
        assert "John Smith" in footnote

    def test_format_ww1_footnote(self, citation_builder, sample_ww1_record):
        """Test formatting WW1 footnote."""
        metadata = FamilySearchMetadata(
            state="Ohio",
            state_abbr="OH",
            county="Noble",
            year=1917,
            registration_type="WW1",
            collection_name="United States, World War I Draft Registration Cards, 1917-1918",
            url="https://familysearch.org/ark:/61903/3:1:XYZ789"
        )

        footnote = citation_builder.format_footnote(sample_ww1_record, metadata)

        assert "1917 U.S. draft registration" in footnote
        assert "Noble County, Ohio" in footnote
        assert "William Jones" in footnote
        assert "imaged" in footnote

    def test_format_footnote_extracts_year_from_date(self, citation_builder, sample_ww2_record):
        """Test that footnote extracts year from registration_date."""
        sample_ww2_record.registration_date = "1942-02-16"
        metadata = FamilySearchMetadata(
            state="Pennsylvania",
            year=1940,  # Different year in metadata
            registration_type="WW2",
            url="https://familysearch.org/test"
        )

        footnote = citation_builder.format_footnote(sample_ww2_record, metadata)

        assert "1942 U.S. draft registration" in footnote
        assert "1940" not in footnote


class TestFormatShortFootnote:
    """Test short footnote formatting."""

    def test_format_ww2_short_footnote(self, citation_builder, sample_ww2_record):
        """Test formatting WW2 short footnote."""
        metadata = FamilySearchMetadata(
            state="Pennsylvania",
            state_abbr="PA",
            county="Allegheny",
            year=1940,
            registration_type="WW2"
        )

        short = citation_builder.format_short_footnote(sample_ww2_record, metadata)

        assert "1940 U.S. draft reg." in short
        assert "Allegheny Co., PA" in short
        assert "John Smith" in short
        assert short.endswith(".")

    def test_format_short_footnote_no_county(self, citation_builder, sample_ww2_record):
        """Test formatting short footnote without county."""
        sample_ww2_record.county = None
        metadata = FamilySearchMetadata(
            state="Pennsylvania",
            state_abbr="PA",
            year=1940,
            registration_type="WW2"
        )

        short = citation_builder.format_short_footnote(sample_ww2_record, metadata)

        assert "1940 U.S. draft reg." in short
        assert "PA" in short
        assert "Allegheny" not in short
        assert "John Smith" in short


class TestFormatBibliography:
    """Test bibliography formatting."""

    def test_format_bibliography_ww2(self, citation_builder):
        """Test formatting WW2 bibliography."""
        metadata = FamilySearchMetadata(
            state="Pennsylvania",
            collection_name="Pennsylvania, World War II Draft Registration Cards, 1940-1945"
        )

        bib = citation_builder.format_bibliography(metadata)

        assert "Pennsylvania, World War II Draft Registration Cards, 1940-1945" in bib
        assert "Database with images" in bib
        assert "FamilySearch" in bib
        assert "http://FamilySearch.org" in bib

    def test_format_bibliography_ww1(self, citation_builder):
        """Test formatting WW1 bibliography."""
        metadata = FamilySearchMetadata(
            state="Ohio",
            registration_type="WW1",
            collection_name="United States, World War I Draft Registration Cards, 1917-1918"
        )

        bib = citation_builder.format_bibliography(metadata)

        assert "World War I Draft Registration Cards, 1917-1918" in bib
        assert "Database with images" in bib

    def test_format_bibliography_generates_name(self, citation_builder):
        """Test bibliography generates collection name if missing."""
        metadata = FamilySearchMetadata(
            state="Pennsylvania",
            registration_type="WW2"
        )

        bib = citation_builder.format_bibliography(metadata)

        assert "Pennsylvania" in bib
        assert "World War II" in bib
        assert "1940-1947" in bib


class TestBuildSource:
    """Test building source data."""

    def test_build_source_ww2(self, citation_builder):
        """Test building WW2 source data."""
        metadata = FamilySearchMetadata(
            state="Pennsylvania",
            state_abbr="PA",
            collection_name="Pennsylvania, World War II Draft Registration Cards, 1940-1945",
            registration_type="WW2"
        )

        source = citation_builder.build_source(metadata)

        assert source.name == "Pennsylvania, World War II Draft Registration Cards, 1940-1945"
        assert source.template_id == 0  # Free-form
        assert "Database with images" in source.bibliography
        assert source.fields_blob is not None
        assert source.fields_blob.startswith(b'\xef\xbb\xbf')  # UTF-8 BOM

    def test_build_source_has_comments(self, citation_builder):
        """Test that source includes comments."""
        metadata = FamilySearchMetadata(
            state="Ohio",
            collection_name="Ohio Draft Cards",
            registration_type="WW2"
        )

        source = citation_builder.build_source(metadata)

        assert "Ohio" in source.comments
        assert "draft" in source.comments.lower()


class TestBuildCitation:
    """Test building citation data."""

    def test_build_citation_ww2(self, citation_builder, sample_ww2_record):
        """Test building WW2 citation."""
        metadata = FamilySearchMetadata(
            state="Pennsylvania",
            state_abbr="PA",
            county="Allegheny",
            year=1940,
            registration_type="WW2",
            collection_name="Pennsylvania, World War II Draft Registration Cards, 1940-1945",
            url="https://familysearch.org/ark:/61903/1:1:ABC123"
        )

        citation = citation_builder.build_citation(sample_ww2_record, metadata, source_id=1)

        assert citation.source_id == 1
        assert "1940 U.S. draft registration" in citation.footnote
        assert "John Smith" in citation.footnote
        assert "1940 U.S. draft reg." in citation.short_footnote
        assert "Database with images" in citation.bibliography
        assert citation.fields_blob is not None
        assert citation.fields_blob.startswith(b'\xef\xbb\xbf')  # UTF-8 BOM

    def test_build_citation_has_all_fields(self, citation_builder, sample_ww2_record):
        """Test that citation has all required fields populated."""
        metadata = FamilySearchMetadata(
            state="Pennsylvania",
            year=1940,
            registration_type="WW2",
            url="https://familysearch.org/test"
        )

        citation = citation_builder.build_citation(sample_ww2_record, metadata, source_id=5)

        assert citation.footnote != ""
        assert citation.short_footnote != ""
        assert citation.bibliography != ""
        assert citation.fields_blob is not None


class TestBLOBCreation:
    """Test XML BLOB creation."""

    def test_blob_has_utf8_bom(self, citation_builder):
        """Test that BLOB starts with UTF-8 BOM."""
        blob = citation_builder._create_source_fields_blob(
            "Test footnote",
            "Test short",
            "Test bib"
        )

        assert blob.startswith(b'\xef\xbb\xbf')

    def test_blob_is_valid_xml(self, citation_builder):
        """Test that BLOB contains valid XML."""
        blob = citation_builder._create_source_fields_blob(
            "Test footnote",
            "Test short",
            "Test bibliography"
        )

        # Remove BOM and decode
        xml_text = blob[3:].decode('utf-8')

        assert '<?xml version="1.0" encoding="UTF-8"?>' in xml_text
        assert '<Root>' in xml_text
        assert '</Root>' in xml_text
        assert '<Footnote>' in xml_text
        assert '<ShortFootnote>' in xml_text
        assert '<Bibliography>' in xml_text

    def test_blob_xml_escapes_special_chars(self, citation_builder):
        """Test that special characters are XML-escaped in BLOB."""
        blob = citation_builder._create_source_fields_blob(
            'Test <i>italics</i> & "quotes"',
            "Test & more",
            "Test bibliography"
        )

        xml_text = blob[3:].decode('utf-8')

        # Should have XML entities, not raw characters
        assert '&lt;' in xml_text or '&amp;' in xml_text or '&quot;' in xml_text


class TestIntegration:
    """Test integrated citation building workflow."""

    def test_full_ww2_workflow(self, citation_builder, sample_ww2_record):
        """Test complete workflow from URL to citation."""
        # Parse URL
        metadata = citation_builder.parse_familysearch_url(
            sample_ww2_record.familysearch_citation,
            state_hint=sample_ww2_record.state
        )

        # Build source
        source = citation_builder.build_source(metadata)

        # Build citation
        citation = citation_builder.build_citation(sample_ww2_record, metadata, source_id=1)

        # Verify complete citation
        assert citation.footnote != ""
        assert citation.short_footnote != ""
        assert citation.bibliography != ""
        assert "John Smith" in citation.footnote
        assert "Pennsylvania" in citation.footnote or "PA" in citation.short_footnote

    def test_full_ww1_workflow(self, citation_builder, sample_ww1_record):
        """Test complete workflow for WW1 registration."""
        # Parse URL with WW1 hint
        citation_text = (
            '"United States, World War I Draft Registration Cards, 1917-1918", '
            'FamilySearch (https://familysearch.org/ark:/61903/3:1:XYZ789)'
        )

        metadata = citation_builder.parse_familysearch_url(
            citation_text,
            state_hint=sample_ww1_record.state
        )

        assert metadata.is_ww1

        # Build citation
        citation = citation_builder.build_citation(sample_ww1_record, metadata, source_id=2)

        assert "1917 U.S. draft registration" in citation.footnote
        assert "William Jones" in citation.footnote
