"""Unit tests for find_census_citations() function.

Tests the database query and citation filtering logic for census batch processing.
External dependencies (database, file system) are mocked.
"""

import pytest
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
import xml.etree.ElementTree as ET
import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "scripts"))


def create_source_fields_xml(
    footnote: str | None = None,
    short_footnote: str | None = None,
    bibliography: str | None = None
) -> bytes:
    """Create XML blob for SourceTable.Fields."""
    root = ET.Element("Root")
    fields = ET.SubElement(root, "Fields")

    if footnote is not None:
        field = ET.SubElement(fields, "Field")
        ET.SubElement(field, "Name").text = "Footnote"
        ET.SubElement(field, "Value").text = footnote

    if short_footnote is not None:
        field = ET.SubElement(fields, "Field")
        ET.SubElement(field, "Name").text = "ShortFootnote"
        ET.SubElement(field, "Value").text = short_footnote

    if bibliography is not None:
        field = ET.SubElement(fields, "Field")
        ET.SubElement(field, "Name").text = "Bibliography"
        ET.SubElement(field, "Value").text = bibliography

    return ET.tostring(root, encoding='utf-8')


def create_citation_fields_xml(page: str | None = None) -> bytes:
    """Create XML blob for CitationTable.Fields with Page field."""
    root = ET.Element("Root")
    fields = ET.SubElement(root, "Fields")

    if page is not None:
        field = ET.SubElement(fields, "Field")
        ET.SubElement(field, "Name").text = "Page"
        ET.SubElement(field, "Value").text = page

    return ET.tostring(root, encoding='utf-8')


class MockCursor:
    """Mock cursor that returns predefined rows."""

    def __init__(self, rows):
        self.rows = rows
        self._executed = None
        self._params = None

    def execute(self, sql, params=None):
        self._executed = sql
        self._params = params

    def fetchall(self):
        return self.rows


class MockConnection:
    """Mock database connection."""

    def __init__(self, cursor):
        self._cursor = cursor
        self._extension_enabled = False
        self._extension_loaded = None

    def enable_load_extension(self, enabled):
        self._extension_enabled = enabled

    def load_extension(self, path):
        self._extension_loaded = path

    def execute(self, sql):
        pass  # For ICU collation

    def cursor(self):
        return self._cursor

    def close(self):
        pass


@pytest.fixture
def mock_config():
    """Mock Config object."""
    config = MagicMock()
    config.rm_media_root_directory = Path("/Users/test/Media")
    return config


@pytest.fixture
def mock_media_resolver():
    """Mock MediaPathResolver."""
    resolver = MagicMock()
    resolver.resolve.return_value = Path("/Users/test/Media/census/image.jpg")
    return resolver


class TestFindCensusCitationsBasic:
    """Test basic functionality of find_census_citations."""

    def test_empty_database_returns_empty_results(self, mock_config, mock_media_resolver):
        """Test with no census records."""
        mock_cursor = MockCursor([])
        mock_conn = MockConnection(mock_cursor)

        with patch('sqlite3.connect', return_value=mock_conn), \
             patch('src.rmcitecraft.config.Config', return_value=mock_config), \
             patch('src.rmcitecraft.utils.media_resolver.MediaPathResolver', return_value=mock_media_resolver):

            # Import after patching
            from process_census_batch import find_census_citations
            result = find_census_citations(
                db_path="/path/to/db.rmtree",
                census_year=1940,
                limit=10
            )

        assert result['citations'] == []
        assert result['examined'] == 0
        assert result['found'] == 0
        assert result['excluded'] == 0
        assert result['skipped_processed'] == 0

    def test_finds_citation_with_familysearch_url_in_footnote(self, mock_config, mock_media_resolver):
        """Test finding citation with FamilySearch URL in footnote."""
        footnote = (
            "1940 U.S. census, Noble County, Ohio, E.D. 95, sheet 3B, "
            "FamilySearch (https://familysearch.org/ark:/61903/1:1:TEST)"
        )
        source_fields = create_source_fields_xml(
            footnote=footnote,
            short_footnote=footnote,  # Same = needs processing
            bibliography="1940 Census"
        )

        # Row: event_id, person_id, given, surname, citation_id, source_id, source_name,
        #      fields_blob, citation_fields_blob, existing_media_count, existing_files, existing_media_paths
        rows = [(
            100,  # event_id
            1000,  # person_id
            "John",  # given
            "Doe",  # surname
            200,  # citation_id
            300,  # source_id
            "Fed Census: 1940, Ohio, Noble",  # source_name
            source_fields,  # fields_blob
            None,  # citation_fields_blob
            0,  # existing_media_count
            None,  # existing_files
            None,  # existing_media_paths
        )]

        mock_cursor = MockCursor(rows)
        mock_conn = MockConnection(mock_cursor)

        with patch('sqlite3.connect', return_value=mock_conn), \
             patch('src.rmcitecraft.config.Config', return_value=mock_config), \
             patch('src.rmcitecraft.utils.media_resolver.MediaPathResolver', return_value=mock_media_resolver):

            from process_census_batch import find_census_citations
            result = find_census_citations(
                db_path="/path/to/db.rmtree",
                census_year=1940,
                limit=10,
                exclude_processed=True
            )

        assert result['found'] == 1
        assert result['examined'] == 1
        citation = result['citations'][0]
        assert citation['event_id'] == 100
        assert citation['person_id'] == 1000
        assert citation['full_name'] == "John Doe"
        assert citation['familysearch_url'] == "https://familysearch.org/ark:/61903/1:1:TEST"
        assert citation['has_existing_media'] is False

    def test_finds_citation_with_familysearch_url_in_page_field(self, mock_config, mock_media_resolver):
        """Test finding citation with FamilySearch URL in CitationTable.Fields Page."""
        source_fields = create_source_fields_xml(
            footnote="Some footnote without URL",
            short_footnote="Some footnote without URL",  # Same = needs processing
            bibliography="Bibliography"
        )

        citation_fields = create_citation_fields_xml(
            page="FamilySearch https://www.familysearch.org/ark:/61903/1:1:ABCD : 2023"
        )

        rows = [(
            101, 1001, "Jane", "Smith", 201, 301, "Fed Census: 1940, Texas, Harris",
            source_fields, citation_fields, 0, None, None,
        )]

        mock_cursor = MockCursor(rows)
        mock_conn = MockConnection(mock_cursor)

        with patch('sqlite3.connect', return_value=mock_conn), \
             patch('src.rmcitecraft.config.Config', return_value=mock_config), \
             patch('src.rmcitecraft.utils.media_resolver.MediaPathResolver', return_value=mock_media_resolver):

            from process_census_batch import find_census_citations
            result = find_census_citations(
                db_path="/path/to/db.rmtree",
                census_year=1940,
                limit=10,
                exclude_processed=True
            )

        assert result['found'] == 1
        citation = result['citations'][0]
        assert citation['familysearch_url'] == "https://www.familysearch.org/ark:/61903/1:1:ABCD"


class TestFindCensusCitationsFiltering:
    """Test citation filtering logic (criteria 5 & 6)."""

    def test_excludes_citation_without_familysearch_url(self, mock_config, mock_media_resolver):
        """Test that citations without FamilySearch URLs are excluded."""
        source_fields = create_source_fields_xml(
            footnote="1940 census, Ohio, Noble County",
            short_footnote="1940 census, Ohio",
            bibliography="Census 1940"
        )

        rows = [(
            100, 1000, "John", "Doe", 200, 300, "Fed Census: 1940",
            source_fields, None, 0, None, None,
        )]

        mock_cursor = MockCursor(rows)
        mock_conn = MockConnection(mock_cursor)

        with patch('sqlite3.connect', return_value=mock_conn), \
             patch('src.rmcitecraft.config.Config', return_value=mock_config), \
             patch('src.rmcitecraft.utils.media_resolver.MediaPathResolver', return_value=mock_media_resolver):

            from process_census_batch import find_census_citations
            result = find_census_citations(
                db_path="/path/to/db.rmtree",
                census_year=1940,
                limit=10
            )

        assert result['found'] == 0
        assert result['excluded'] == 1
        assert result['examined'] == 1

    def test_excludes_already_processed_citation(self, mock_config, mock_media_resolver):
        """Test that properly processed citations are excluded (criteria 5 & 6)."""
        # Valid processed citation - footnote != short_footnote and passes validation
        footnote = (
            "1940 U.S. census, Noble County, Ohio, population schedule, "
            "enumeration district (E.D.) 95, sheet 3B, John Doe; "
            "FamilySearch (https://familysearch.org/ark:/61903/1:1:TEST)"
        )
        short_footnote = (
            "1940 U.S. census, Noble Co., Ohio, pop. sch., E.D. 95, sheet 3B, John Doe."
        )
        bibliography = (
            "U.S. Ohio. Noble County. 1940 U.S Census. FamilySearch."
        )

        source_fields = create_source_fields_xml(
            footnote=footnote,
            short_footnote=short_footnote,
            bibliography=bibliography
        )

        rows = [(
            100, 1000, "John", "Doe", 200, 300, "Fed Census: 1940",
            source_fields, None, 0, None, None,
        )]

        mock_cursor = MockCursor(rows)
        mock_conn = MockConnection(mock_cursor)

        with patch('sqlite3.connect', return_value=mock_conn), \
             patch('src.rmcitecraft.config.Config', return_value=mock_config), \
             patch('src.rmcitecraft.utils.media_resolver.MediaPathResolver', return_value=mock_media_resolver):

            from process_census_batch import find_census_citations
            result = find_census_citations(
                db_path="/path/to/db.rmtree",
                census_year=1940,
                limit=10,
                exclude_processed=True
            )

        assert result['found'] == 0
        assert result['skipped_processed'] == 1

    def test_includes_citation_when_exclude_processed_false(self, mock_config, mock_media_resolver):
        """Test that exclude_processed=False includes all citations."""
        # Valid processed citation that would normally be skipped
        footnote = (
            "1940 U.S. census, Noble County, Ohio, population schedule, "
            "enumeration district (E.D.) 95, sheet 3B, John Doe; "
            "FamilySearch (https://familysearch.org/ark:/61903/1:1:TEST)"
        )
        short_footnote = (
            "1940 U.S. census, Noble Co., Ohio, pop. sch., E.D. 95, sheet 3B, John Doe."
        )
        bibliography = (
            "U.S. Ohio. Noble County. 1940 U.S Census. FamilySearch."
        )

        source_fields = create_source_fields_xml(
            footnote=footnote,
            short_footnote=short_footnote,
            bibliography=bibliography
        )

        rows = [(
            100, 1000, "John", "Doe", 200, 300, "Fed Census: 1940",
            source_fields, None, 0, None, None,
        )]

        mock_cursor = MockCursor(rows)
        mock_conn = MockConnection(mock_cursor)

        with patch('sqlite3.connect', return_value=mock_conn), \
             patch('src.rmcitecraft.config.Config', return_value=mock_config), \
             patch('src.rmcitecraft.utils.media_resolver.MediaPathResolver', return_value=mock_media_resolver):

            from process_census_batch import find_census_citations
            result = find_census_citations(
                db_path="/path/to/db.rmtree",
                census_year=1940,
                limit=10,
                exclude_processed=False  # Don't exclude processed
            )

        assert result['found'] == 1
        assert result['skipped_processed'] == 0

    def test_includes_unprocessed_citation_same_footnote_short(self, mock_config, mock_media_resolver):
        """Test that unprocessed citation (same footnote/short) is included."""
        # Same text for all = needs processing (criteria 5)
        same_text = (
            "1940 U.S. census, FamilySearch "
            "(https://familysearch.org/ark:/61903/1:1:TEST)"
        )

        source_fields = create_source_fields_xml(
            footnote=same_text,
            short_footnote=same_text,
            bibliography=same_text
        )

        rows = [(
            100, 1000, "John", "Doe", 200, 300, "Fed Census: 1940",
            source_fields, None, 0, None, None,
        )]

        mock_cursor = MockCursor(rows)
        mock_conn = MockConnection(mock_cursor)

        with patch('sqlite3.connect', return_value=mock_conn), \
             patch('src.rmcitecraft.config.Config', return_value=mock_config), \
             patch('src.rmcitecraft.utils.media_resolver.MediaPathResolver', return_value=mock_media_resolver):

            from process_census_batch import find_census_citations
            result = find_census_citations(
                db_path="/path/to/db.rmtree",
                census_year=1940,
                limit=10,
                exclude_processed=True
            )

        assert result['found'] == 1
        assert result['skipped_processed'] == 0


class TestFindCensusCitationsWithExistingMedia:
    """Test handling of existing media."""

    def test_includes_citation_with_existing_media(self, mock_config, mock_media_resolver):
        """Test that citations with existing media are included."""
        footnote = (
            "1940 U.S. census FamilySearch "
            "(https://familysearch.org/ark:/61903/1:1:TEST)"
        )
        source_fields = create_source_fields_xml(
            footnote=footnote,
            short_footnote=footnote,
            bibliography="Census"
        )

        rows = [(
            100, 1000, "John", "Doe", 200, 300, "Fed Census: 1940",
            source_fields, None,
            1,  # existing_media_count
            "1940_Ohio_Noble_John_Doe.jpg",  # existing_files
            "?Records - Census/1940 Federal/",  # existing_media_paths
        )]

        mock_cursor = MockCursor(rows)
        mock_conn = MockConnection(mock_cursor)

        with patch('sqlite3.connect', return_value=mock_conn), \
             patch('src.rmcitecraft.config.Config', return_value=mock_config), \
             patch('src.rmcitecraft.utils.media_resolver.MediaPathResolver', return_value=mock_media_resolver):

            from process_census_batch import find_census_citations
            result = find_census_citations(
                db_path="/path/to/db.rmtree",
                census_year=1940,
                limit=10,
                exclude_processed=True
            )

        assert result['found'] == 1
        citation = result['citations'][0]
        assert citation['has_existing_media'] is True
        assert citation['existing_files'] == "1940_Ohio_Noble_John_Doe.jpg"
        assert citation['existing_image_path'] is not None


class TestFindCensusCitationsPagination:
    """Test pagination (limit/offset)."""

    def test_respects_limit(self, mock_config, mock_media_resolver):
        """Test that limit parameter is respected."""
        footnote = (
            "1940 U.S. census FamilySearch "
            "(https://familysearch.org/ark:/61903/1:1:TEST)"
        )
        source_fields = create_source_fields_xml(
            footnote=footnote,
            short_footnote=footnote,
            bibliography="Census"
        )

        # Create 5 rows
        rows = [
            (100+i, 1000+i, f"Person{i}", f"Surname{i}", 200+i, 300, "Fed Census: 1940",
             source_fields, None, 0, None, None)
            for i in range(5)
        ]

        mock_cursor = MockCursor(rows)
        mock_conn = MockConnection(mock_cursor)

        with patch('sqlite3.connect', return_value=mock_conn), \
             patch('src.rmcitecraft.config.Config', return_value=mock_config), \
             patch('src.rmcitecraft.utils.media_resolver.MediaPathResolver', return_value=mock_media_resolver):

            from process_census_batch import find_census_citations
            result = find_census_citations(
                db_path="/path/to/db.rmtree",
                census_year=1940,
                limit=3,  # Only want 3
                exclude_processed=True
            )

        # Should stop at limit
        assert result['found'] == 3
        assert len(result['citations']) == 3


class TestFindCensusCitationsURLParsing:
    """Test URL extraction from various formats."""

    def test_extracts_url_with_https(self, mock_config, mock_media_resolver):
        """Test URL extraction with https://."""
        footnote = "Census, FamilySearch (https://familysearch.org/ark:/61903/1:1:K6VN-3T4)"
        source_fields = create_source_fields_xml(
            footnote=footnote,
            short_footnote=footnote,
            bibliography="Census"
        )

        rows = [(100, 1000, "John", "Doe", 200, 300, "Fed Census: 1940",
                 source_fields, None, 0, None, None)]

        mock_cursor = MockCursor(rows)
        mock_conn = MockConnection(mock_cursor)

        with patch('sqlite3.connect', return_value=mock_conn), \
             patch('src.rmcitecraft.config.Config', return_value=mock_config), \
             patch('src.rmcitecraft.utils.media_resolver.MediaPathResolver', return_value=mock_media_resolver):

            from process_census_batch import find_census_citations
            result = find_census_citations(
                db_path="/path/to/db.rmtree",
                census_year=1940,
                limit=10
            )

        assert result['citations'][0]['familysearch_url'] == "https://familysearch.org/ark:/61903/1:1:K6VN-3T4"

    def test_extracts_url_with_www(self, mock_config, mock_media_resolver):
        """Test URL extraction with www prefix."""
        footnote = "Census, FamilySearch (https://www.familysearch.org/ark:/61903/1:1:TEST)"
        source_fields = create_source_fields_xml(
            footnote=footnote,
            short_footnote=footnote,
            bibliography="Census"
        )

        rows = [(100, 1000, "John", "Doe", 200, 300, "Fed Census: 1940",
                 source_fields, None, 0, None, None)]

        mock_cursor = MockCursor(rows)
        mock_conn = MockConnection(mock_cursor)

        with patch('sqlite3.connect', return_value=mock_conn), \
             patch('src.rmcitecraft.config.Config', return_value=mock_config), \
             patch('src.rmcitecraft.utils.media_resolver.MediaPathResolver', return_value=mock_media_resolver):

            from process_census_batch import find_census_citations
            result = find_census_citations(
                db_path="/path/to/db.rmtree",
                census_year=1940,
                limit=10
            )

        assert result['citations'][0]['familysearch_url'] == "https://www.familysearch.org/ark:/61903/1:1:TEST"

    def test_strips_trailing_punctuation_from_url(self, mock_config, mock_media_resolver):
        """Test that trailing punctuation is stripped from URLs."""
        footnote = "Census, FamilySearch (https://familysearch.org/ark:/61903/1:1:TEST)."
        source_fields = create_source_fields_xml(
            footnote=footnote,
            short_footnote=footnote,
            bibliography="Census"
        )

        rows = [(100, 1000, "John", "Doe", 200, 300, "Fed Census: 1940",
                 source_fields, None, 0, None, None)]

        mock_cursor = MockCursor(rows)
        mock_conn = MockConnection(mock_cursor)

        with patch('sqlite3.connect', return_value=mock_conn), \
             patch('src.rmcitecraft.config.Config', return_value=mock_config), \
             patch('src.rmcitecraft.utils.media_resolver.MediaPathResolver', return_value=mock_media_resolver):

            from process_census_batch import find_census_citations
            result = find_census_citations(
                db_path="/path/to/db.rmtree",
                census_year=1940,
                limit=10
            )

        # Should strip trailing ) and .
        url = result['citations'][0]['familysearch_url']
        assert not url.endswith('.')
        assert not url.endswith(',')
        assert not url.endswith(';')


class TestFindCensusCitationsReturnStructure:
    """Test the structure of returned data."""

    def test_return_structure_keys(self, mock_config, mock_media_resolver):
        """Test that return dict has expected keys."""
        mock_cursor = MockCursor([])
        mock_conn = MockConnection(mock_cursor)

        with patch('sqlite3.connect', return_value=mock_conn), \
             patch('src.rmcitecraft.config.Config', return_value=mock_config), \
             patch('src.rmcitecraft.utils.media_resolver.MediaPathResolver', return_value=mock_media_resolver):

            from process_census_batch import find_census_citations
            result = find_census_citations(
                db_path="/path/to/db.rmtree",
                census_year=1940,
                limit=10
            )

        assert 'citations' in result
        assert 'examined' in result
        assert 'found' in result
        assert 'excluded' in result
        assert 'skipped_processed' in result

    def test_citation_dict_keys(self, mock_config, mock_media_resolver):
        """Test that citation dicts have expected keys."""
        footnote = "1940 Census FamilySearch (https://familysearch.org/ark:/61903/1:1:TEST)"
        source_fields = create_source_fields_xml(
            footnote=footnote,
            short_footnote=footnote,
            bibliography="Census"
        )

        rows = [(100, 1000, "John", "Doe", 200, 300, "Fed Census: 1940",
                 source_fields, None, 0, None, None)]

        mock_cursor = MockCursor(rows)
        mock_conn = MockConnection(mock_cursor)

        with patch('sqlite3.connect', return_value=mock_conn), \
             patch('src.rmcitecraft.config.Config', return_value=mock_config), \
             patch('src.rmcitecraft.utils.media_resolver.MediaPathResolver', return_value=mock_media_resolver):

            from process_census_batch import find_census_citations
            result = find_census_citations(
                db_path="/path/to/db.rmtree",
                census_year=1940,
                limit=10
            )

        citation = result['citations'][0]
        expected_keys = {
            'event_id', 'person_id', 'given_name', 'surname', 'full_name',
            'citation_id', 'source_id', 'source_name', 'familysearch_url',
            'has_existing_media', 'existing_files', 'existing_image_path',
            'footnote', 'short_footnote', 'bibliography'
        }
        assert set(citation.keys()) == expected_keys

    def test_handles_null_name_fields(self, mock_config, mock_media_resolver):
        """Test handling of NULL given/surname."""
        footnote = "1940 Census FamilySearch (https://familysearch.org/ark:/61903/1:1:TEST)"
        source_fields = create_source_fields_xml(
            footnote=footnote,
            short_footnote=footnote,
            bibliography="Census"
        )

        # Given and surname are NULL
        rows = [(100, 1000, None, None, 200, 300, "Fed Census: 1940",
                 source_fields, None, 0, None, None)]

        mock_cursor = MockCursor(rows)
        mock_conn = MockConnection(mock_cursor)

        with patch('sqlite3.connect', return_value=mock_conn), \
             patch('src.rmcitecraft.config.Config', return_value=mock_config), \
             patch('src.rmcitecraft.utils.media_resolver.MediaPathResolver', return_value=mock_media_resolver):

            from process_census_batch import find_census_citations
            result = find_census_citations(
                db_path="/path/to/db.rmtree",
                census_year=1940,
                limit=10
            )

        citation = result['citations'][0]
        assert citation['given_name'] == ''
        assert citation['surname'] == ''
        assert citation['full_name'] == ''


class TestFindCensusCitationsXMLParsing:
    """Test XML parsing edge cases."""

    def test_handles_empty_fields_blob(self, mock_config, mock_media_resolver):
        """Test handling of NULL/empty fields blob."""
        rows = [(100, 1000, "John", "Doe", 200, 300, "Fed Census: 1940",
                 None, None, 0, None, None)]  # NULL fields_blob

        mock_cursor = MockCursor(rows)
        mock_conn = MockConnection(mock_cursor)

        with patch('sqlite3.connect', return_value=mock_conn), \
             patch('src.rmcitecraft.config.Config', return_value=mock_config), \
             patch('src.rmcitecraft.utils.media_resolver.MediaPathResolver', return_value=mock_media_resolver):

            from process_census_batch import find_census_citations
            result = find_census_citations(
                db_path="/path/to/db.rmtree",
                census_year=1940,
                limit=10
            )

        # Should be excluded (no URL found)
        assert result['found'] == 0
        assert result['excluded'] == 1

    def test_handles_malformed_xml(self, mock_config, mock_media_resolver):
        """Test handling of malformed XML blob."""
        rows = [(100, 1000, "John", "Doe", 200, 300, "Fed Census: 1940",
                 b"<not valid xml", None, 0, None, None)]

        mock_cursor = MockCursor(rows)
        mock_conn = MockConnection(mock_cursor)

        with patch('sqlite3.connect', return_value=mock_conn), \
             patch('src.rmcitecraft.config.Config', return_value=mock_config), \
             patch('src.rmcitecraft.utils.media_resolver.MediaPathResolver', return_value=mock_media_resolver):

            from process_census_batch import find_census_citations
            result = find_census_citations(
                db_path="/path/to/db.rmtree",
                census_year=1940,
                limit=10
            )

        # Should handle gracefully (excluded, no crash)
        assert result['found'] == 0
        assert result['excluded'] == 1

    def test_handles_xml_without_footnote_element(self, mock_config, mock_media_resolver):
        """Test handling of XML without Footnote element."""
        source_fields = b"<Root><Fields></Fields></Root>"

        rows = [(100, 1000, "John", "Doe", 200, 300, "Fed Census: 1940",
                 source_fields, None, 0, None, None)]

        mock_cursor = MockCursor(rows)
        mock_conn = MockConnection(mock_cursor)

        with patch('sqlite3.connect', return_value=mock_conn), \
             patch('src.rmcitecraft.config.Config', return_value=mock_config), \
             patch('src.rmcitecraft.utils.media_resolver.MediaPathResolver', return_value=mock_media_resolver):

            from process_census_batch import find_census_citations
            result = find_census_citations(
                db_path="/path/to/db.rmtree",
                census_year=1940,
                limit=10
            )

        # Should be excluded (no URL found)
        assert result['found'] == 0
        assert result['excluded'] == 1
