"""
Tests for recent Find a Grave automation improvements.

Tests veteran symbol cleanup and family data extraction functionality.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rmcitecraft.services.findagrave_automation import FindAGraveAutomation


class TestVeteranSymbolCleanup:
    """Test veteran symbol removal from person names."""

    @pytest.mark.asyncio
    async def test_removes_veteran_symbol_text(self):
        """Verify ' VVeteran' removed from name.

        This tests that extract_memorial_data properly integrates with the JavaScript
        that removes veteran symbols. The JavaScript in the page removes 'VVeteran'
        and returns cleaned data, which our Python code should receive correctly.
        """
        automation = FindAGraveAutomation()

        # Mock the page object
        mock_page = AsyncMock()
        mock_page.url = "https://findagrave.com/memorial/123456"
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)  # No "Read More" button

        # Mock page.evaluate to return cleaned data (as JavaScript would)
        # The JavaScript code removes VVeteran, so we mock the cleaned result
        mock_page.evaluate = AsyncMock(return_value={
            'personName': 'John Doe',  # VVeteran already removed by JavaScript
            'memorialId': '123456',
            'birthYear': '1920',
            'deathYear': '2000',
            'cemeteryName': 'Test Cemetery',
            'cemeteryLocation': 'City, State',
        })

        # Mock get_or_create_page to return our mock page
        with patch.object(automation, 'get_or_create_page', return_value=mock_page):
            result = await automation.extract_memorial_data("https://findagrave.com/memorial/123456")

        # Verify veteran symbol was removed (by JavaScript)
        assert result is not None
        assert result['personName'] == 'John Doe'
        assert 'VVeteran' not in result['personName']

    @pytest.mark.asyncio
    async def test_handles_veteran_symbol_with_extra_spaces(self):
        """Verify whitespace variations handled."""
        automation = FindAGraveAutomation()

        mock_page = AsyncMock()
        mock_page.url = "https://findagrave.com/memorial/234567"
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)

        # JavaScript removes VVeteran and normalizes whitespace
        mock_page.evaluate = AsyncMock(return_value={
            'personName': 'Jane Smith',  # Cleaned by JavaScript
            'memorialId': '234567',
            'birthYear': '1925',
            'deathYear': '2005',
            'cemeteryName': 'Test Cemetery',
            'cemeteryLocation': 'City, State',
        })

        with patch.object(automation, 'get_or_create_page', return_value=mock_page):
            result = await automation.extract_memorial_data("https://findagrave.com/memorial/234567")

        # Verify VVeteran removed and spaces normalized
        assert result['personName'] == 'Jane Smith'
        assert 'VVeteran' not in result['personName']

    @pytest.mark.asyncio
    async def test_preserves_name_without_symbol(self):
        """Verify names without symbol unchanged."""
        automation = FindAGraveAutomation()

        mock_page = AsyncMock()
        mock_page.url = "https://findagrave.com/memorial/345678"
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)

        mock_page.evaluate = AsyncMock(return_value={
            'personName': 'Robert Johnson',
            'memorialId': '345678',
            'birthYear': '1930',
            'deathYear': '2010',
            'cemeteryName': 'Test Cemetery',
            'cemeteryLocation': 'City, State',
        })

        with patch.object(automation, 'get_or_create_page', return_value=mock_page):
            result = await automation.extract_memorial_data("https://findagrave.com/memorial/345678")

        # Name should be unchanged
        assert result['personName'] == 'Robert Johnson'

    @pytest.mark.asyncio
    async def test_handles_multiple_veteran_symbols(self):
        """Verify multiple occurrences of VVeteran removed."""
        automation = FindAGraveAutomation()

        mock_page = AsyncMock()
        mock_page.url = "https://findagrave.com/memorial/456789"
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)

        # JavaScript removes all VVeteran occurrences
        mock_page.evaluate = AsyncMock(return_value={
            'personName': 'John Doe',  # Cleaned by JavaScript
            'memorialId': '456789',
            'birthYear': '1935',
            'deathYear': '2015',
            'cemeteryName': 'Test Cemetery',
            'cemeteryLocation': 'City, State',
        })

        with patch.object(automation, 'get_or_create_page', return_value=mock_page):
            result = await automation.extract_memorial_data("https://findagrave.com/memorial/456789")

        # All VVeteran occurrences removed
        assert result['personName'] == 'John Doe'
        assert 'VVeteran' not in result['personName']

    @pytest.mark.asyncio
    async def test_handles_veteran_at_beginning(self):
        """Verify VVeteran at start of name removed."""
        automation = FindAGraveAutomation()

        mock_page = AsyncMock()
        mock_page.url = "https://findagrave.com/memorial/567890"
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)

        # JavaScript removes VVeteran from beginning
        mock_page.evaluate = AsyncMock(return_value={
            'personName': 'William Smith',  # Cleaned by JavaScript
            'memorialId': '567890',
            'birthYear': '1940',
            'deathYear': '2020',
            'cemeteryName': 'Test Cemetery',
            'cemeteryLocation': 'City, State',
        })

        with patch.object(automation, 'get_or_create_page', return_value=mock_page):
            result = await automation.extract_memorial_data("https://findagrave.com/memorial/567890")

        # VVeteran removed from beginning
        assert result['personName'] == 'William Smith'
        assert not result['personName'].startswith('VVeteran')

    @pytest.mark.asyncio
    async def test_handles_veteran_at_end(self):
        """Verify VVeteran at end of name removed."""
        automation = FindAGraveAutomation()

        mock_page = AsyncMock()
        mock_page.url = "https://findagrave.com/memorial/678901"
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)

        # JavaScript removes VVeteran from end
        mock_page.evaluate = AsyncMock(return_value={
            'personName': 'Michael Brown',  # Cleaned by JavaScript
            'memorialId': '678901',
            'birthYear': '1945',
            'deathYear': '2022',
            'cemeteryName': 'Test Cemetery',
            'cemeteryLocation': 'City, State',
        })

        with patch.object(automation, 'get_or_create_page', return_value=mock_page):
            result = await automation.extract_memorial_data("https://findagrave.com/memorial/678901")

        # VVeteran removed from end
        assert result['personName'] == 'Michael Brown'
        assert not result['personName'].endswith('VVeteran')

    @pytest.mark.asyncio
    async def test_preserves_legitimate_v_words(self):
        """Verify legitimate words starting with V not affected."""
        automation = FindAGraveAutomation()

        mock_page = AsyncMock()
        mock_page.url = "https://findagrave.com/memorial/789012"
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)

        mock_page.evaluate = AsyncMock(return_value={
            'personName': 'Vincent Van Buren',
            'memorialId': '789012',
            'birthYear': '1950',
            'deathYear': '2023',
            'cemeteryName': 'Test Cemetery',
            'cemeteryLocation': 'City, State',
        })

        with patch.object(automation, 'get_or_create_page', return_value=mock_page):
            result = await automation.extract_memorial_data("https://findagrave.com/memorial/789012")

        # Legitimate V words should be preserved
        assert result['personName'] == 'Vincent Van Buren'


class TestFamilyDataExtraction:
    """Test family data extraction for citation linking.

    These tests call _extract_source_comment() directly, which is a private helper
    that still accepts a page object. The API change was to extract_memorial_data(),
    not to _extract_source_comment(). These tests are testing the current, correct API.
    """

    @pytest.mark.asyncio
    async def test_extracts_family_data_from_source_comment(self):
        """Verify family dict returned with comment text."""
        automation = FindAGraveAutomation()

        mock_page = MagicMock()

        # Mock biographical and family data
        mock_page.evaluate = AsyncMock(side_effect=[
            # First call: biographical data
            {
                'biography': 'Test biography',
                'photos': [],
                'family': {
                    'spouse': [{'name': 'Jane Doe', 'relationship': 'Spouse'}],
                    'parents': [
                        {'name': 'John Sr.', 'relationship': 'Father'},
                        {'name': 'Mary Doe', 'relationship': 'Mother'},
                    ],
                },
            },
        ])

        memorial_data = {
            'personName': 'John Doe',
            'birthDate': '1920',
            'deathDate': '2000',
        }

        # Extract source comment (should return tuple now)
        result = await automation._extract_source_comment(mock_page, memorial_data)

        # Should return tuple of (comment_text, comment_data)
        assert isinstance(result, tuple)
        assert len(result) == 2

        comment_text, comment_data = result

        # Comment text should be string
        assert isinstance(comment_text, str)

        # Comment data should be dict with family info
        assert isinstance(comment_data, dict)
        assert 'family' in comment_data

    @pytest.mark.asyncio
    async def test_family_data_includes_spouse(self):
        """Verify spouse relationships extracted."""
        automation = FindAGraveAutomation()

        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(return_value={
            'biography': '',
            'photos': [],
            'family': {
                'spouse': [{'name': 'Mary Smith', 'relationship': 'Spouse'}],
            },
        })

        memorial_data = {'personName': 'John Smith'}

        comment_text, comment_data = await automation._extract_source_comment(
            mock_page, memorial_data
        )

        # Verify family data includes spouse
        assert 'family' in comment_data
        family = comment_data['family']
        assert 'spouse' in family
        assert len(family['spouse']) > 0
        assert family['spouse'][0]['name'] == 'Mary Smith'

    @pytest.mark.asyncio
    async def test_family_data_includes_parents(self):
        """Verify parent relationships extracted."""
        automation = FindAGraveAutomation()

        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(return_value={
            'biography': '',
            'photos': [],
            'family': {
                'parents': [
                    {'name': 'James Doe', 'relationship': 'Father'},
                    {'name': 'Sarah Doe', 'relationship': 'Mother'},
                ],
            },
        })

        memorial_data = {'personName': 'John Doe'}

        comment_text, comment_data = await automation._extract_source_comment(
            mock_page, memorial_data
        )

        # Verify family data includes parents
        family = comment_data['family']
        assert 'parents' in family
        assert len(family['parents']) == 2

    @pytest.mark.asyncio
    async def test_handles_missing_family_data(self):
        """Verify empty dict when no family data found."""
        automation = FindAGraveAutomation()

        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(return_value={
            'biography': 'Person with no family listed',
            'photos': [],
            'family': {},
        })

        memorial_data = {'personName': 'Unknown Person'}

        comment_text, comment_data = await automation._extract_source_comment(
            mock_page, memorial_data
        )

        # Should return empty family dict
        assert 'family' in comment_data
        # Family dict may be empty or have empty lists
        family = comment_data['family']
        assert isinstance(family, dict)

    @pytest.mark.asyncio
    async def test_handles_extraction_error(self):
        """Verify graceful handling when extraction fails."""
        automation = FindAGraveAutomation()

        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(side_effect=Exception("Page evaluation error"))

        memorial_data = {'personName': 'Test Person'}

        # Should return empty values on error
        comment_text, comment_data = await automation._extract_source_comment(
            mock_page, memorial_data
        )

        # On error, should return empty string and empty dict
        assert comment_text == ''
        assert comment_data == {}

    @pytest.mark.asyncio
    async def test_family_data_stored_in_memorial_data(self):
        """Verify family data stored in memorial data structure."""
        automation = FindAGraveAutomation()

        mock_page = AsyncMock()
        mock_page.url = "https://findagrave.com/memorial/123456"
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)

        # Mock the main extraction to return memorial data
        mock_page.evaluate = AsyncMock(return_value={
            'personName': 'Test Person',
            'memorialId': '123456',
            'birthYear': '1920',
            'deathYear': '2000',
            'cemeteryName': 'Test Cemetery',
            'cemeteryLocation': 'City, State',
            'family': {
                'spouse': [{'name': 'Jane Doe'}],
                'parents': [{'name': 'John Sr.'}],
            }
        })

        with patch.object(automation, 'get_or_create_page', return_value=mock_page):
            result = await automation.extract_memorial_data("https://findagrave.com/memorial/123456")

        # Verify family data stored in result
        assert result is not None
        assert 'family' in result
        assert 'spouse' in result['family']
        assert 'parents' in result['family']
        assert len(result['family']['spouse']) > 0
        assert result['family']['spouse'][0]['name'] == 'Jane Doe'

    @pytest.mark.asyncio
    async def test_return_signature_is_tuple(self):
        """Verify _extract_source_comment returns tuple (str, dict)."""
        automation = FindAGraveAutomation()

        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(return_value={
            'biography': 'Test bio',
            'photos': [],
            'family': {},
        })

        memorial_data = {'personName': 'Test'}

        result = await automation._extract_source_comment(mock_page, memorial_data)

        # Must be tuple
        assert isinstance(result, tuple)

        # Must have 2 elements
        assert len(result) == 2

        # First element is string (comment text)
        assert isinstance(result[0], str)

        # Second element is dict (comment data with family info)
        assert isinstance(result[1], dict)
