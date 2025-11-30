"""Unit tests for CensusResponseParser."""

import pytest

from rmcitecraft.services.census.response_parser import CensusResponseParser


class TestCensusResponseParser:
    """Tests for the CensusResponseParser class."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return CensusResponseParser()

    def test_parse_plain_json(self, parser):
        """Test parsing plain JSON response."""
        response = '{"name": "John Smith", "age": 35}'

        result = parser.parse_response(response)

        assert result["name"] == "John Smith"
        assert result["age"] == 35

    def test_parse_json_in_code_block(self, parser):
        """Test parsing JSON in markdown code block."""
        response = '''```json
{"name": "John Smith", "age": 35}
```'''

        result = parser.parse_response(response)

        assert result["name"] == "John Smith"
        assert result["age"] == 35

    def test_parse_json_in_code_block_no_language(self, parser):
        """Test parsing JSON in code block without language specifier."""
        response = '''```
{"name": "John Smith", "age": 35}
```'''

        result = parser.parse_response(response)

        assert result["name"] == "John Smith"

    def test_parse_json_with_preamble(self, parser):
        """Test parsing JSON with explanatory text before."""
        response = '''Here is the transcription:
{"name": "John Smith", "age": 35}'''

        result = parser.parse_response(response)

        assert result["name"] == "John Smith"

    def test_parse_json_with_postamble(self, parser):
        """Test parsing JSON with text after."""
        response = '''{"name": "John Smith", "age": 35}

I hope this helps!'''

        result = parser.parse_response(response)

        assert result["name"] == "John Smith"

    def test_parse_json_array(self, parser):
        """Test parsing JSON array response."""
        response = '[{"name": "John"}, {"name": "Mary"}]'

        result = parser.parse_response(response)

        assert isinstance(result, list)
        assert len(result) == 2

    def test_parse_empty_response_raises(self, parser):
        """Test that empty response raises ValueError."""
        with pytest.raises(ValueError, match="Empty response"):
            parser.parse_response("")

    def test_parse_no_json_raises(self, parser):
        """Test that response with no JSON raises ValueError."""
        with pytest.raises(ValueError, match="No JSON found"):
            parser.parse_response("No JSON here, just text.")

    def test_parse_invalid_json_raises(self, parser):
        """Test that invalid JSON raises ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            parser.parse_response('{"name": "John", age: 35}')  # Missing quotes

    def test_extract_json_removes_markdown(self, parser):
        """Test that extract_json handles markdown code blocks."""
        text = '''```json
{"name": "John"}
```'''

        json_str = parser.extract_json(text)

        assert json_str == '{"name": "John"}'

    def test_fix_trailing_comma(self, parser):
        """Test that trailing commas are fixed."""
        # Some LLMs add trailing commas
        response = '{"name": "John", "age": 35,}'

        result = parser.parse_response(response)

        assert result["name"] == "John"


class TestExtractPersons:
    """Tests for extracting persons from parsed data."""

    @pytest.fixture
    def parser(self):
        return CensusResponseParser()

    def test_extract_from_persons_array(self, parser):
        """Test extracting persons from standard format."""
        data = {
            "metadata": {"sheet": "9A"},
            "persons": [
                {"name": "John Smith", "age": 35},
                {"name": "Mary Smith", "age": 32},
            ],
        }

        persons = parser.extract_persons(data)

        assert len(persons) == 2
        assert persons[0]["name"] == "John Smith"
        assert persons[1]["name"] == "Mary Smith"

    def test_extract_from_households(self, parser):
        """Test extracting persons from household structure."""
        data = {
            "households": [
                {
                    "members": [
                        {"name": "John Smith"},
                        {"name": "Mary Smith"},
                    ]
                }
            ]
        }

        persons = parser.extract_persons(data)

        assert len(persons) == 2

    def test_extract_from_head_of_household(self, parser):
        """Test extracting from household-only census format."""
        data = {
            "households": [
                {
                    "head_of_household": "John Smith",
                    "statistics": {"free_white_males_under_10": 2},
                }
            ]
        }

        persons = parser.extract_persons(data)

        assert len(persons) == 1
        assert persons[0]["name"] == "John Smith"
        assert persons[0]["relationship"] == "Head"

    def test_extract_from_list(self, parser):
        """Test extracting when data is already a list."""
        data = [
            {"name": "John Smith"},
            {"name": "Mary Smith"},
        ]

        persons = parser.extract_persons(data)

        assert len(persons) == 2

    def test_extract_from_single_person(self, parser):
        """Test extracting from single person object."""
        data = {"name": "John Smith", "age": 35}

        persons = parser.extract_persons(data)

        assert len(persons) == 1
        assert persons[0]["name"] == "John Smith"


class TestExtractMetadata:
    """Tests for extracting metadata."""

    @pytest.fixture
    def parser(self):
        return CensusResponseParser()

    def test_extract_from_metadata_section(self, parser):
        """Test extracting from explicit metadata section."""
        data = {
            "metadata": {
                "census_year": 1940,
                "enumeration_district": "93-76",
                "sheet": "9A",
            },
            "persons": [],
        }

        metadata = parser.extract_metadata(data)

        assert metadata["census_year"] == 1940
        assert metadata["enumeration_district"] == "93-76"
        assert metadata["sheet"] == "9A"

    def test_extract_from_top_level(self, parser):
        """Test extracting metadata from top-level fields."""
        data = {
            "census_year": 1940,
            "enumeration_district": "93-76",
            "persons": [],
        }

        metadata = parser.extract_metadata(data)

        assert metadata["census_year"] == 1940
        assert metadata["enumeration_district"] == "93-76"

    def test_metadata_section_takes_precedence(self, parser):
        """Test that metadata section takes precedence over top-level."""
        data = {
            "census_year": 1930,  # Top level
            "metadata": {"census_year": 1940},  # Metadata section
        }

        metadata = parser.extract_metadata(data)

        assert metadata["census_year"] == 1940
