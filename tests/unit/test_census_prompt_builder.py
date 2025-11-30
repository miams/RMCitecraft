"""Unit tests for CensusPromptBuilder."""

import pytest

from rmcitecraft.models.census_schema import CensusEra
from rmcitecraft.services.census.prompt_builder import CensusPromptBuilder
from rmcitecraft.services.census.schema_registry import CensusSchemaRegistry


class TestCensusPromptBuilder:
    """Tests for the CensusPromptBuilder class."""

    @pytest.fixture
    def builder(self):
        """Create a prompt builder instance."""
        return CensusPromptBuilder()

    @pytest.fixture
    def schema_1940(self):
        """Get 1940 schema."""
        return CensusSchemaRegistry.get_schema(1940)

    @pytest.fixture
    def schema_1950(self):
        """Get 1950 schema."""
        return CensusSchemaRegistry.get_schema(1950)

    @pytest.fixture
    def schema_1850(self):
        """Get 1850 schema."""
        return CensusSchemaRegistry.get_schema(1850)

    @pytest.fixture
    def schema_1790(self):
        """Get 1790 schema."""
        return CensusSchemaRegistry.get_schema(1790)

    def test_build_prompt_includes_year(self, builder, schema_1940):
        """Test that prompt includes census year."""
        prompt = builder.build_transcription_prompt(schema_1940)

        assert "1940" in prompt

    def test_build_prompt_includes_schema_fields(self, builder, schema_1940):
        """Test that prompt includes schema field definitions."""
        prompt = builder.build_transcription_prompt(schema_1940)

        # Should include key fields
        assert "name" in prompt.lower()
        assert "age" in prompt.lower()
        assert "relationship" in prompt.lower()

    def test_build_prompt_includes_instructions(self, builder, schema_1940):
        """Test that prompt includes year-specific instructions."""
        prompt = builder.build_transcription_prompt(schema_1940)

        # 1940 schema has detailed instructions
        assert "COLUMN" in prompt or "column" in prompt.lower()

    def test_build_prompt_with_target_names(self, builder, schema_1940):
        """Test prompt with target names hint."""
        prompt = builder.build_transcription_prompt(
            schema_1940,
            target_names=["John Smith", "Mary Smith"],
        )

        assert "John Smith" in prompt
        assert "Mary Smith" in prompt
        assert "PRIORITY" in prompt or "focus" in prompt.lower()

    def test_build_prompt_with_target_line(self, builder, schema_1940):
        """Test prompt with target line hint."""
        prompt = builder.build_transcription_prompt(
            schema_1940,
            target_line=24,
        )

        assert "24" in prompt
        assert "line" in prompt.lower()

    def test_build_prompt_with_sheet(self, builder, schema_1940):
        """Test prompt with sheet hint."""
        prompt = builder.build_transcription_prompt(
            schema_1940,
            sheet="9A",
        )

        assert "9A" in prompt

    def test_build_prompt_with_enumeration_district(self, builder, schema_1940):
        """Test prompt with ED hint."""
        prompt = builder.build_transcription_prompt(
            schema_1940,
            enumeration_district="93-76",
        )

        assert "93-76" in prompt

    def test_build_prompt_includes_json_format(self, builder, schema_1940):
        """Test that prompt requests JSON output."""
        prompt = builder.build_transcription_prompt(schema_1940)

        assert "JSON" in prompt or "json" in prompt

    def test_build_prompt_includes_abbreviations(self, builder, schema_1940):
        """Test that prompt includes abbreviation guide."""
        prompt = builder.build_transcription_prompt(schema_1940)

        # Should mention ditto marks or common abbreviations
        assert "ditto" in prompt.lower() or "do" in prompt

    def test_household_only_prompt_mentions_limitation(self, builder, schema_1790):
        """Test that household-only census prompt mentions the limitation."""
        prompt = builder.build_transcription_prompt(schema_1790)

        assert "head" in prompt.lower()
        # Should mention that only head is named
        assert "household" in prompt.lower()

    def test_build_prompt_for_1950_mentions_stamp(self, builder, schema_1950):
        """Test that 1950 prompt mentions stamp/page terminology."""
        prompt = builder.build_transcription_prompt(schema_1950)

        # 1950 uses page numbers (stamp in citations)
        assert "1950" in prompt
        assert "page" in prompt.lower() or "stamp" in prompt.lower()

    def test_build_family_extraction_prompt(self, builder, schema_1940):
        """Test family extraction prompt."""
        prompt = builder.build_family_extraction_prompt(
            schema_1940,
            target_names=["John Smith", "Mary Smith"],
        )

        assert "John Smith" in prompt
        assert "Mary Smith" in prompt
        assert "household" in prompt.lower()

    def test_prompt_requests_structured_output(self, builder, schema_1940):
        """Test that prompt asks for structured JSON output."""
        prompt = builder.build_transcription_prompt(schema_1940)

        # Should request persons/records array
        assert "persons" in prompt.lower() or "records" in prompt.lower()


class TestPromptBuilderEdgeCases:
    """Edge case tests for prompt builder."""

    @pytest.fixture
    def builder(self):
        return CensusPromptBuilder()

    def test_empty_target_names_list(self, builder):
        """Test with empty target names list."""
        schema = CensusSchemaRegistry.get_schema(1940)
        prompt = builder.build_transcription_prompt(schema, target_names=[])

        # Should not crash, should not include targeting section
        assert "1940" in prompt

    def test_all_targeting_hints(self, builder):
        """Test with all targeting hints provided."""
        schema = CensusSchemaRegistry.get_schema(1940)
        prompt = builder.build_transcription_prompt(
            schema,
            target_names=["John Smith"],
            target_line=24,
            sheet="9A",
            enumeration_district="93-76",
        )

        assert "John Smith" in prompt
        assert "24" in prompt
        assert "9A" in prompt
        assert "93-76" in prompt
