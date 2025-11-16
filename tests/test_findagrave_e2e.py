"""
End-to-end test for Find a Grave functionality.

This test verifies the complete workflow:
1. Query database for Find a Grave URLs
2. Extract memorial data from saved HTML
3. Format Evidence Explained citations
4. Generate source names and filenames
"""

import pytest
from pathlib import Path

from rmcitecraft.database.findagrave_queries import find_findagrave_people
from rmcitecraft.services.findagrave_formatter import (
    format_findagrave_citation,
    generate_source_name,
    generate_image_filename,
)


@pytest.mark.integration
class TestFindAGraveEndToEnd:
    """End-to-end tests for Find a Grave processing."""

    def test_query_and_format_citation(self):
        """Test querying database and formatting citation."""
        # Query database for people with Find a Grave URLs
        result = find_findagrave_people('data/Iiams.rmtree', limit=5)

        assert result['total'] > 0, "Should find at least one person with Find a Grave URL"

        # Take first person
        person = result['people'][0]

        # Simulate extracted memorial data (would come from browser automation)
        memorial_data = {
            'memorialId': person['memorial_id'],
            'url': person['url'],
            'accessDate': 'November 15, 2025',
            'cemeteryName': 'Test Cemetery',
            'cemeteryCity': 'Test City',
            'cemeteryCounty': 'Test County',
            'cemeteryState': 'Test State',
            'cemeteryCountry': 'USA',
        }

        # Format citation
        citation = format_findagrave_citation(
            memorial_data=memorial_data,
            person_name=person['full_name'],
            birth_year=person['birth_year'],
            death_year=person['death_year'],
            maiden_name=None,  # Would detect from HTML
        )

        # Verify citation structure
        assert '<i>Find a Grave</i>' in citation['footnote']
        assert person['memorial_id'] in citation['footnote']
        assert citation['short_footnote']
        assert citation['bibliography']

    def test_generate_source_name_and_filename(self):
        """Test source name and filename generation."""
        # Query database
        result = find_findagrave_people('data/Iiams.rmtree', limit=1)
        assert result['total'] > 0

        person = result['people'][0]

        # Generate source name
        source_name = generate_source_name(
            surname=person['surname'],
            given_name=person['given_name'],
            maiden_name=None,
            birth_year=person['birth_year'],
            death_year=person['death_year'],
            person_id=person['person_id'],
        )

        # Verify pattern: "Find a Grave: Surname, GivenName (BirthYear-DeathYear) RIN PersonID"
        assert source_name.startswith('Find a Grave:')
        assert person['surname'] in source_name
        assert f"RIN {person['person_id']}" in source_name

        # Generate image filename
        filename = generate_image_filename(
            surname=person['surname'],
            given_name=person['given_name'],
            maiden_name=None,
            birth_year=person['birth_year'],
            death_year=person['death_year'],
        )

        # Verify pattern: "Surname, GivenName (BirthYear-DeathYear).jpg"
        assert filename.endswith('.jpg')
        assert person['surname'] in filename

    def test_ruth_eleanor_excluded(self):
        """Test that Ruth Eleanor (Person ID 1095) is correctly excluded."""
        # Query all people (no limit)
        result = find_findagrave_people('data/Iiams.rmtree', limit=None)

        # Ruth Eleanor should NOT be in results (already has citation)
        person_ids = [p['person_id'] for p in result['people']]
        assert 1095 not in person_ids, "Ruth Eleanor should be excluded (already has citation)"

    def test_expected_citation_format(self):
        """Test that generated citation matches expected format for Ruth Eleanor."""
        # Create citation using known Ruth Eleanor data
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

        citation = format_findagrave_citation(
            memorial_data=memorial_data,
            person_name='Ruth Eleanor Hand Iams',
            birth_year=1937,
            death_year=2021,
            maiden_name='Hand',
        )

        # Compare with expected database citation (from database query)
        # Expected footnote pattern from database:
        # <i>Find a Grave</i>, database and images (URL: accessed DATE),
        # memorial page for NAME (DATES), maintained by CONTRIBUTOR,
        # citing CEMETERY, LOCATION.

        assert '<i>Find a Grave</i>, database and images' in citation['footnote']
        assert '234450077' in citation['footnote']
        assert 'December 23, 2021' in citation['footnote']
        assert '<i>Hand</i>' in citation['footnote']
        assert '1937–2021' in citation['footnote']
        assert 'North Ten Mile Baptist Cemetery' in citation['footnote']
        assert 'Amwell Township' in citation['footnote']
        assert 'Washington County' in citation['footnote']
        assert 'Pennsylvania' in citation['footnote']
        assert 'wndwlker (contributor 47340661)' in citation['footnote']

        # Verify short footnote
        assert citation['short_footnote'] == (
            '<i>Find a Grave,</i> "Ruth Eleanor <i>Hand</i> Iams" (1937–2021), '
            'memorial #234450077.'
        )

        # Verify bibliography contains year
        assert '2021' in citation['bibliography'] or '2025' in citation['bibliography']

    def test_source_name_matches_database(self):
        """Test that generated source name matches database pattern."""
        source_name = generate_source_name(
            surname='Iams',
            given_name='Ruth Eleanor',
            maiden_name='Hand',
            birth_year=1937,
            death_year=2021,
            person_id=1095,
        )

        # Should match database pattern:
        # "Find a Grave: Iams, Ruth Eleanor (Hand) (1937-2021) RIN 1095"
        expected = 'Find a Grave: Iams, Ruth Eleanor (Hand) (1937-2021) RIN 1095'
        assert source_name == expected

    def test_image_filename_format(self):
        """Test that image filename matches expected pattern."""
        filename = generate_image_filename(
            surname='Iams',
            given_name='Ruth Eleanor',
            maiden_name='Hand',
            birth_year=1937,
            death_year=2021,
        )

        # Should match pattern:
        # "Iams, Ruth Eleanor (Hand) (1937-2021).jpg"
        expected = 'Iams, Ruth Eleanor (Hand) (1937-2021).jpg'
        assert filename == expected
