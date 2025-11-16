"""Unit tests for Find a Grave citation formatter."""

import pytest
from datetime import datetime

from rmcitecraft.services.findagrave_formatter import (
    format_findagrave_citation,
    generate_source_name,
    generate_image_filename,
)


class TestFormatFindAGraveCitation:
    """Test Find a Grave citation formatting."""

    def test_format_citation_female_with_maiden_name(self):
        """Test formatting citation for female with maiden name."""
        memorial_data = {
            'memorialId': '234450077',
            'url': 'https://www.findagrave.com/memorial/234450077/ruth-eleanor-iams',
            'accessDate': 'December 23, 2021',
            'cemeteryName': 'North Ten Mile Baptist Cemetery',
            'cemeteryCity': 'Amwell Township',
            'cemeteryCounty': 'Washington',
            'cemeteryState': 'Pennsylvania',
            'cemeteryCountry': 'USA',
            'maintainedBy': 'Maintained by: wndwlker (contributor 47340661)',
        }

        result = format_findagrave_citation(
            memorial_data=memorial_data,
            person_name='Ruth Eleanor Hand Iams',
            birth_year=1937,
            death_year=2021,
            maiden_name='Hand',
        )

        # Check footnote
        assert '<i>Find a Grave</i>' in result['footnote']
        assert '234450077' in result['footnote']
        assert 'December 23, 2021' in result['footnote']
        assert '<i>Hand</i>' in result['footnote']
        assert '1937–2021' in result['footnote']
        assert 'North Ten Mile Baptist Cemetery' in result['footnote']
        assert 'Amwell Township' in result['footnote']
        assert 'Washington County' in result['footnote']
        assert 'Pennsylvania' in result['footnote']
        assert 'wndwlker (contributor 47340661)' in result['footnote']

        # Check short footnote
        assert '<i>Find a Grave,</i>' in result['short_footnote']
        assert 'memorial #234450077' in result['short_footnote']
        assert '1937–2021' in result['short_footnote']

        # Check bibliography
        assert '<i>Find a Grave</i>' in result['bibliography']
        assert 'Database with images' in result['bibliography']
        assert str(datetime.now().year) in result['bibliography']

    def test_format_citation_male_no_maiden_name(self):
        """Test formatting citation for male (no maiden name)."""
        memorial_data = {
            'memorialId': '126643703',
            'url': 'https://www.findagrave.com/memorial/126643703',
            'accessDate': 'November 15, 2025',
            'cemeteryName': 'Sunset Memorial Park',
            'cemeteryCity': 'North Huntingdon',
            'cemeteryCounty': 'Westmoreland',
            'cemeteryState': 'Pennsylvania',
            'cemeteryCountry': 'USA',
        }

        result = format_findagrave_citation(
            memorial_data=memorial_data,
            person_name='Isaac Lindsey Morrison Iams',
            birth_year=1925,
            death_year=2010,
            maiden_name=None,
        )

        # Should not have italicized name
        assert '<i>Isaac' not in result['footnote']
        assert 'Isaac Lindsey Morrison Iams' in result['footnote']
        assert '1925–2010' in result['footnote']

    def test_format_citation_minimal_data(self):
        """Test formatting with minimal data."""
        memorial_data = {
            'memorialId': '123456789',
            'url': 'https://www.findagrave.com/memorial/123456789',
            'accessDate': 'November 15, 2025',
        }

        result = format_findagrave_citation(
            memorial_data=memorial_data,
            person_name='John Doe',
            birth_year=None,
            death_year=2020,
            maiden_name=None,
        )

        # Should still generate valid citation
        assert '<i>Find a Grave</i>' in result['footnote']
        assert '123456789' in result['footnote']
        assert 'John Doe' in result['footnote']
        assert 'd. 2020' in result['footnote']

    def test_format_citation_no_death_year(self):
        """Test formatting with only birth year."""
        memorial_data = {
            'memorialId': '123456789',
            'url': 'https://www.findagrave.com/memorial/123456789',
            'accessDate': 'November 15, 2025',
        }

        result = format_findagrave_citation(
            memorial_data=memorial_data,
            person_name='John Doe',
            birth_year=1900,
            death_year=None,
            maiden_name=None,
        )

        # Should show "1900–"
        assert '1900–' in result['footnote']


class TestGenerateSourceName:
    """Test source name generation."""

    def test_source_name_female_with_maiden_name(self):
        """Test source name for female with maiden name."""
        result = generate_source_name(
            surname='Iams',
            given_name='Ruth Eleanor',
            maiden_name='Hand',
            birth_year=1937,
            death_year=2021,
            person_id=1095,
        )

        expected = 'Find a Grave: Iams, Ruth Eleanor (Hand) (1937-2021) RIN 1095'
        assert result == expected

    def test_source_name_male_no_maiden_name(self):
        """Test source name for male (no maiden name)."""
        result = generate_source_name(
            surname='Iams',
            given_name='Isaac Lindsey Morrison',
            maiden_name=None,
            birth_year=1925,
            death_year=2010,
            person_id=123,
        )

        expected = 'Find a Grave: Iams, Isaac Lindsey Morrison (1925-2010) RIN 123'
        assert result == expected

    def test_source_name_partial_dates(self):
        """Test source name with partial dates."""
        result = generate_source_name(
            surname='Doe',
            given_name='Jane',
            maiden_name='Smith',
            birth_year=1950,
            death_year=None,
            person_id=999,
        )

        expected = 'Find a Grave: Doe, Jane (Smith) (1950-) RIN 999'
        assert result == expected


class TestGenerateImageFilename:
    """Test image filename generation."""

    def test_image_filename_female_with_maiden_name(self):
        """Test image filename for female with maiden name."""
        result = generate_image_filename(
            surname='Iams',
            given_name='Ruth Eleanor',
            maiden_name='Hand',
            birth_year=1937,
            death_year=2021,
        )

        expected = 'Iams, Ruth Eleanor (Hand) (1937-2021).jpg'
        assert result == expected

    def test_image_filename_male_no_maiden_name(self):
        """Test image filename for male (no maiden name)."""
        result = generate_image_filename(
            surname='Iams',
            given_name='Isaac Lindsey Morrison',
            maiden_name=None,
            birth_year=1925,
            death_year=2010,
        )

        expected = 'Iams, Isaac Lindsey Morrison (1925-2010).jpg'
        assert result == expected

    def test_image_filename_partial_dates(self):
        """Test image filename with partial dates."""
        result = generate_image_filename(
            surname='Doe',
            given_name='Jane',
            maiden_name='Smith',
            birth_year=None,
            death_year=2020,
        )

        expected = 'Doe, Jane (Smith) (-2020).jpg'
        assert result == expected
