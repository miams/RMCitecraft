"""Unit tests for Find a Grave database queries."""

import xml.etree.ElementTree as ET
import pytest

from rmcitecraft.database.findagrave_queries import (
    find_findagrave_people,
    _extract_memorial_id,
    _build_source_fields_xml,
    _build_citation_fields_xml,
)


class TestExtractMemorialId:
    """Test memorial ID extraction from URLs."""

    def test_extract_from_standard_url(self):
        """Test extraction from standard memorial URL."""
        url = 'https://www.findagrave.com/memorial/234450077/ruth-eleanor-iams'
        assert _extract_memorial_id(url) == '234450077'

    def test_extract_from_url_without_name(self):
        """Test extraction from URL without name slug."""
        url = 'https://www.findagrave.com/memorial/234450077'
        assert _extract_memorial_id(url) == '234450077'

    def test_extract_from_url_with_query_params(self):
        """Test extraction from URL with query parameters."""
        url = 'https://www.findagrave.com/memorial/234450077/ruth-eleanor-iams?foo=bar'
        assert _extract_memorial_id(url) == '234450077'

    def test_extract_from_invalid_url(self):
        """Test extraction from invalid URL returns empty string."""
        url = 'https://www.findagrave.com/cemetery/123456'
        assert _extract_memorial_id(url) == ''

    def test_extract_from_empty_url(self):
        """Test extraction from empty URL returns empty string."""
        url = ''
        assert _extract_memorial_id(url) == ''


@pytest.mark.integration
class TestFindFindAGravePeople:
    """Integration tests for finding Find a Grave people in database."""

    def test_find_people_with_limit(self):
        """Test finding people with limit."""
        result = find_findagrave_people(
            db_path='data/Iiams.rmtree',
            limit=5,
        )

        assert 'people' in result
        assert 'total' in result
        assert 'examined' in result
        assert 'excluded' in result

        # Should respect limit
        assert len(result['people']) <= 5

        # Each person should have required fields
        if result['people']:
            person = result['people'][0]
            assert 'person_id' in person
            assert 'url' in person
            assert 'surname' in person
            assert 'given_name' in person
            assert 'memorial_id' in person
            assert 'full_name' in person

    def test_find_all_people(self):
        """Test finding all people without limit."""
        result = find_findagrave_people(
            db_path='data/Iiams.rmtree',
            limit=None,
        )

        assert result['examined'] >= 0
        assert result['total'] >= 0
        assert result['excluded'] >= 0

        # Total + excluded should equal examined
        assert result['total'] + result['excluded'] == result['examined']


class TestBuildSourceFieldsXml:
    """Test XML building for SourceTable.Fields."""

    def test_build_source_fields_xml(self):
        """Test building XML for source fields."""
        footnote = '<i>Find a Grave</i>, database with images...'
        short_footnote = '<i>Find a Grave</i>, memorial 234450077...'
        bibliography = 'Find a Grave, database with images...'

        xml_str = _build_source_fields_xml(footnote, short_footnote, bibliography)

        # Parse XML
        root = ET.fromstring(xml_str)

        # Verify structure
        assert root.tag == 'Root'
        fields = root.find('Fields')
        assert fields is not None

        # Find fields by name
        field_dict = {}
        for field in fields.findall('Field'):
            name_elem = field.find('Name')
            value_elem = field.find('Value')
            if name_elem is not None and value_elem is not None:
                field_dict[name_elem.text] = value_elem.text

        # Verify all three fields present
        assert 'Footnote' in field_dict
        assert 'ShortFootnote' in field_dict
        assert 'Bibliography' in field_dict

        # Verify values
        assert field_dict['Footnote'] == footnote
        assert field_dict['ShortFootnote'] == short_footnote
        assert field_dict['Bibliography'] == bibliography

    def test_build_source_fields_with_special_characters(self):
        """Test building XML with special characters."""
        footnote = 'Test with <i>italics</i> & "quotes"'
        short_footnote = 'Short <i>test</i>'
        bibliography = 'Bibliography with & ampersand'

        xml_str = _build_source_fields_xml(footnote, short_footnote, bibliography)

        # Should parse without error
        root = ET.fromstring(xml_str)
        assert root.tag == 'Root'


class TestBuildCitationFieldsXml:
    """Test XML building for CitationTable.Fields."""

    def test_build_citation_fields_xml(self):
        """Test building XML for citation fields (empty for Find a Grave)."""
        xml_str = _build_citation_fields_xml()

        # Parse XML
        root = ET.fromstring(xml_str)

        # Verify structure
        assert root.tag == 'Root'
        fields = root.find('Fields')
        assert fields is not None

        # Verify no fields (empty for Find a Grave)
        # URL is stored in footnote text, not in reference fields
        assert len(fields.findall('Field')) == 0

    def test_build_citation_fields_structure(self):
        """Test XML structure is valid even when empty."""
        xml_str = _build_citation_fields_xml()

        # Should parse without error
        root = ET.fromstring(xml_str)
        assert root.tag == 'Root'
        assert root.find('Fields') is not None
