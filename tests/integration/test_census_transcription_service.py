"""Integration tests for CensusTranscriptionService."""

from unittest.mock import MagicMock, patch

import pytest

from rmcitecraft.services.census.transcription_service import (
    CensusTranscriptionService,
    TranscriptionResult,
)


class MockLLMProvider:
    """Mock LLM provider for testing."""

    def __init__(self, response_text: str):
        self.response_text = response_text
        self.call_count = 0
        self.last_prompt = None
        self.last_image_path = None

    def complete_with_image(self, prompt: str, image_path: str, **kwargs):
        """Mock complete_with_image."""
        self.call_count += 1
        self.last_prompt = prompt
        self.last_image_path = image_path

        mock_response = MagicMock()
        mock_response.text = self.response_text
        return mock_response


class TestCensusTranscriptionService:
    """Integration tests for the transcription service."""

    @pytest.fixture
    def mock_1940_response(self):
        """Mock response for 1940 census."""
        return """{
            "metadata": {
                "census_year": 1940,
                "enumeration_district": "93-76",
                "sheet": "9A"
            },
            "persons": [
                {
                    "line_number": 24,
                    "name": "Smith, John",
                    "relationship": "Head",
                    "sex": "M",
                    "race": "W",
                    "age": 35,
                    "birthplace": "Ohio"
                },
                {
                    "line_number": 25,
                    "name": "Smith, Mary",
                    "relationship": "Wife",
                    "sex": "F",
                    "race": "W",
                    "age": 32,
                    "birthplace": "Indiana"
                }
            ]
        }"""

    def test_transcribe_with_valid_year(self, mock_1940_response, tmp_path):
        """Test transcription with valid census year."""
        # Create a dummy image file
        image_file = tmp_path / "census.jpg"
        image_file.write_bytes(b"fake image data")

        provider = MockLLMProvider(mock_1940_response)
        service = CensusTranscriptionService(provider=provider)

        result = service.transcribe(
            image_path=image_file,
            census_year=1940,
        )

        assert result.success is True
        assert len(result.persons) == 2
        assert result.persons[0]["name"] == "Smith, John"
        assert result.metadata["enumeration_district"] == "93-76"

    def test_transcribe_with_targeting(self, mock_1940_response, tmp_path):
        """Test transcription with targeting hints."""
        image_file = tmp_path / "census.jpg"
        image_file.write_bytes(b"fake image data")

        provider = MockLLMProvider(mock_1940_response)
        service = CensusTranscriptionService(provider=provider)

        result = service.transcribe(
            image_path=image_file,
            census_year=1940,
            target_names=["John Smith"],
            target_line=24,
        )

        # Verify targeting was included in prompt
        assert "John Smith" in provider.last_prompt
        assert "24" in provider.last_prompt

    def test_transcribe_invalid_year(self, tmp_path):
        """Test transcription with invalid census year."""
        image_file = tmp_path / "census.jpg"
        image_file.write_bytes(b"fake image data")

        provider = MockLLMProvider("{}")
        service = CensusTranscriptionService(provider=provider)

        result = service.transcribe(
            image_path=image_file,
            census_year=1890,  # Invalid - destroyed by fire
        )

        assert result.success is False
        assert "invalid" in result.error.lower() or "1890" in result.error

    def test_transcribe_without_provider(self, tmp_path):
        """Test transcription without provider configured."""
        image_file = tmp_path / "census.jpg"
        image_file.write_bytes(b"fake image data")

        service = CensusTranscriptionService(provider=None)

        result = service.transcribe(
            image_path=image_file,
            census_year=1940,
        )

        assert result.success is False
        assert "provider" in result.error.lower()

    def test_transcribe_with_validation_warnings(self, tmp_path):
        """Test that validation warnings are included in result."""
        # Response with invalid sex value
        response = """{
            "metadata": {"enumeration_district": "93-76", "sheet": "9A"},
            "persons": [
                {"name": "John Smith", "sex": "X", "age": 35}
            ]
        }"""

        image_file = tmp_path / "census.jpg"
        image_file.write_bytes(b"fake image data")

        provider = MockLLMProvider(response)
        service = CensusTranscriptionService(provider=provider)

        result = service.transcribe(
            image_path=image_file,
            census_year=1940,
        )

        assert result.success is True
        assert len(result.warnings) > 0

    def test_extract_family(self, tmp_path):
        """Test family extraction."""
        response = """{
            "metadata": {"enumeration_district": "93-76"},
            "persons": [
                {"name": "Smith, John", "relationship": "Head"},
                {"name": "Smith, Mary", "relationship": "Wife"},
                {"name": "Smith, Jr", "relationship": "Son"}
            ]
        }"""

        image_file = tmp_path / "census.jpg"
        image_file.write_bytes(b"fake image data")

        provider = MockLLMProvider(response)
        service = CensusTranscriptionService(provider=provider)

        result = service.extract_family(
            image_path=image_file,
            census_year=1940,
            target_names=["John Smith"],
        )

        assert result.success is True
        assert len(result.persons) == 3

    def test_list_supported_years(self):
        """Test listing supported years."""
        years = CensusTranscriptionService.list_supported_years()

        assert 1790 in years
        assert 1950 in years
        assert 1890 not in years

    def test_get_schema(self):
        """Test getting schema through service."""
        service = CensusTranscriptionService(provider=None)
        schema = service.get_schema(1940)

        assert schema.year == 1940


class TestTranscriptionResultFormats:
    """Test different response formats are handled."""

    def test_json_in_markdown_code_block(self, tmp_path):
        """Test parsing JSON in markdown code block."""
        response = '''Here is the transcription:

```json
{
    "persons": [{"name": "John Smith", "age": 35}]
}
```'''

        image_file = tmp_path / "census.jpg"
        image_file.write_bytes(b"fake image data")

        provider = MockLLMProvider(response)
        service = CensusTranscriptionService(provider=provider)

        result = service.transcribe(image_file, 1940)

        assert result.success is True
        assert result.persons[0]["name"] == "John Smith"

    def test_plain_json_response(self, tmp_path):
        """Test parsing plain JSON response."""
        response = '{"persons": [{"name": "John Smith"}]}'

        image_file = tmp_path / "census.jpg"
        image_file.write_bytes(b"fake image data")

        provider = MockLLMProvider(response)
        service = CensusTranscriptionService(provider=provider)

        result = service.transcribe(image_file, 1940)

        assert result.success is True

    def test_invalid_json_response(self, tmp_path):
        """Test handling of invalid JSON response."""
        response = "This is not valid JSON at all"

        image_file = tmp_path / "census.jpg"
        image_file.write_bytes(b"fake image data")

        provider = MockLLMProvider(response)
        service = CensusTranscriptionService(provider=provider)

        result = service.transcribe(image_file, 1940)

        assert result.success is False
        assert result.error is not None
