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
        """Verify ' VVeteran' removed from name."""
        automation = FindAGraveAutomation()

        # Mock page evaluation
        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(return_value={
            'personName': 'John Doe VVeteran',
            'memorialId': '123456',
            'birthDate': '1920',
            'deathDate': '2000',
            'cemeteryName': 'Test Cemetery',
            'cemeteryLocation': 'City, State',
        })

        # Extract data (which should clean veteran symbol)
        with patch.object(automation, '_extract_source_comment', return_value=('', {})):
            result = await automation.extract_memorial_data(mock_page)

        # Veteran symbol should be removed
        assert result['personName'] == 'John Doe'
        assert 'VVeteran' not in result['personName']

    @pytest.mark.asyncio
    async def test_handles_veteran_symbol_with_extra_spaces(self):
        """Verify whitespace variations handled."""
        automation = FindAGraveAutomation()

        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(return_value={
            'personName': 'Jane  VVeteran  Smith',
            'memorialId': '234567',
            'birthDate': '1925',
            'deathDate': '2005',
            'cemeteryName': 'Test Cemetery',
            'cemeteryLocation': 'City, State',
        })

        with patch.object(automation, '_extract_source_comment', return_value=('', {})):
            result = await automation.extract_memorial_data(mock_page)

        # Should remove VVeteran and normalize spaces
        assert 'VVeteran' not in result['personName']
        # Name should still be present
        assert 'Jane' in result['personName']
        assert 'Smith' in result['personName']

    @pytest.mark.asyncio
    async def test_preserves_name_without_symbol(self):
        """Verify names without symbol unchanged."""
        automation = FindAGraveAutomation()

        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(return_value={
            'personName': 'Robert Johnson',
            'memorialId': '345678',
            'birthDate': '1930',
            'deathDate': '2010',
            'cemeteryName': 'Test Cemetery',
            'cemeteryLocation': 'City, State',
        })

        with patch.object(automation, '_extract_source_comment', return_value=('', {})):
            result = await automation.extract_memorial_data(mock_page)

        # Name should be unchanged
        assert result['personName'] == 'Robert Johnson'

    @pytest.mark.asyncio
    async def test_handles_multiple_veteran_symbols(self):
        """Verify multiple occurrences of VVeteran removed."""
        automation = FindAGraveAutomation()

        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(return_value={
            'personName': 'VVeteran John VVeteran Doe',
            'memorialId': '456789',
            'birthDate': '1935',
            'deathDate': '2015',
            'cemeteryName': 'Test Cemetery',
            'cemeteryLocation': 'City, State',
        })

        with patch.object(automation, '_extract_source_comment', return_value=('', {})):
            result = await automation.extract_memorial_data(mock_page)

        # All VVeteran occurrences should be removed
        assert 'VVeteran' not in result['personName']
        assert 'John' in result['personName']
        assert 'Doe' in result['personName']

    @pytest.mark.asyncio
    async def test_handles_veteran_at_beginning(self):
        """Verify VVeteran at start of name removed."""
        automation = FindAGraveAutomation()

        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(return_value={
            'personName': 'VVeteran William Smith',
            'memorialId': '567890',
            'birthDate': '1940',
            'deathDate': '2020',
            'cemeteryName': 'Test Cemetery',
            'cemeteryLocation': 'City, State',
        })

        with patch.object(automation, '_extract_source_comment', return_value=('', {})):
            result = await automation.extract_memorial_data(mock_page)

        # VVeteran should be removed from beginning
        assert not result['personName'].startswith('VVeteran')
        assert 'William Smith' in result['personName']

    @pytest.mark.asyncio
    async def test_handles_veteran_at_end(self):
        """Verify VVeteran at end of name removed."""
        automation = FindAGraveAutomation()

        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(return_value={
            'personName': 'Michael Brown VVeteran',
            'memorialId': '678901',
            'birthDate': '1945',
            'deathDate': '2022',
            'cemeteryName': 'Test Cemetery',
            'cemeteryLocation': 'City, State',
        })

        with patch.object(automation, '_extract_source_comment', return_value=('', {})):
            result = await automation.extract_memorial_data(mock_page)

        # VVeteran should be removed from end
        assert not result['personName'].endswith('VVeteran')
        assert 'Michael Brown' in result['personName']

    @pytest.mark.asyncio
    async def test_preserves_legitimate_v_words(self):
        """Verify legitimate words starting with V not affected."""
        automation = FindAGraveAutomation()

        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(return_value={
            'personName': 'Vincent Van Buren',
            'memorialId': '789012',
            'birthDate': '1950',
            'deathDate': '2023',
            'cemeteryName': 'Test Cemetery',
            'cemeteryLocation': 'City, State',
        })

        with patch.object(automation, '_extract_source_comment', return_value=('', {})):
            result = await automation.extract_memorial_data(mock_page)

        # Legitimate V words should be preserved
        assert result['personName'] == 'Vincent Van Buren'


class TestFamilyDataExtraction:
    """Test family data extraction for citation linking."""

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

        mock_page = MagicMock()

        # Mock the main extraction
        mock_page.evaluate = AsyncMock(return_value={
            'personName': 'Test Person',
            'memorialId': '123456',
            'birthDate': '1920',
            'deathDate': '2000',
            'cemeteryName': 'Test Cemetery',
            'cemeteryLocation': 'City, State',
        })

        # Mock source comment extraction to return family data
        family_data = {
            'family': {
                'spouse': [{'name': 'Jane Doe'}],
                'parents': [{'name': 'John Sr.'}],
            }
        }

        with patch.object(
            automation,
            '_extract_source_comment',
            return_value=('Source comment', family_data)
        ):
            result = await automation.extract_memorial_data(mock_page)

        # Verify family data stored in result
        assert 'family' in result
        assert 'spouse' in result['family']
        assert 'parents' in result['family']

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
