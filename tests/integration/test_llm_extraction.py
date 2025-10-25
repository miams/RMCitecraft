"""Integration tests for LLM-based citation extraction.

These tests can run with real LLM APIs (if API keys are set) or be skipped.
Mark tests with @pytest.mark.llm to run only when explicitly requested.
"""

import pytest

from rmcitecraft.services.citation_extractor import CitationExtractor
from rmcitecraft.services.llm_provider import LLMProviderFactory


class TestLLMExtraction:
    """Test LLM-based citation extraction."""

    @pytest.fixture
    def extractor(self) -> CitationExtractor:
        """Create citation extractor instance."""
        return CitationExtractor()

    @pytest.fixture
    def check_llm_available(self, extractor: CitationExtractor) -> None:
        """Skip test if no LLM provider is available."""
        if not extractor.is_available():
            pytest.skip("No LLM provider available (API keys not set)")

    @pytest.mark.llm
    @pytest.mark.asyncio
    async def test_extract_1900_census_ella_ijams(
        self, extractor: CitationExtractor, check_llm_available: None
    ) -> None:
        """Test LLM extraction of 1900 census citation."""
        source_name = "Fed Census: 1900, Ohio, Noble [citing sheet 3B, family 57] Ijams, Ella"
        familysearch_entry = (
            '"United States Census, 1900," database with images, *FamilySearch* '
            "(https://familysearch.org/ark:/61903/1:1:MM6X-FGZ : accessed 24 July 2015), "
            "Ella Ijams, Olive Township Caldwell village, Noble, Ohio, United States; "
            "citing sheet 3B, family 57, NARA microfilm publication T623 "
            "(Washington, D.C.: National Archives and Records Administration, n.d.); "
            "FHL microfilm 1,241,311."
        )

        result = await extractor.extract_citation(source_name, familysearch_entry)

        assert result is not None, "Extraction should return a result"
        assert result.year == 1900
        assert result.state == "Ohio"
        assert result.county == "Noble"
        assert "Ijams" in result.person_name or "Ella" in result.person_name
        assert result.sheet == "3B"
        assert result.family_number == "57"

        # ED is missing in this example - should be in missing_fields
        assert "enumeration_district" in result.missing_fields or result.enumeration_district is None

        # URL should be extracted
        assert "familysearch.org/ark:/61903/1:1:MM6X-FGZ" in result.familysearch_url

    @pytest.mark.llm
    @pytest.mark.asyncio
    async def test_extract_1910_census_william_ijams(
        self, extractor: CitationExtractor, check_llm_available: None
    ) -> None:
        """Test LLM extraction of 1910 census citation with ED."""
        source_name = (
            "Fed Census: 1910, Maryland, Baltimore "
            "[citing enumeration district (ED) ED 214, sheet 3B] Ijams, William H."
        )
        familysearch_entry = (
            '"United States Census, 1910," database with images, *FamilySearch*'
            "(https://familysearch.org/ark:/61903/1:1:M2F4-SVS : accessed 27 November 2015), "
            "William H Ijams in household of Margaret E Brannon, "
            "Baltimore Ward 13, Baltimore (Independent City), Maryland, United States; "
            "citing enumeration district (ED) ED 214, sheet 3B, "
            "NARA microfilm publication T624 "
            "(Washington, D.C.: National Archives and Records Administration, n.d.); "
            "FHL microfilm 1,374,570."
        )

        result = await extractor.extract_citation(source_name, familysearch_entry)

        assert result is not None
        assert result.year == 1910
        assert result.state == "Maryland"
        assert result.county == "Baltimore"

        # Person name should be William H Ijams, not Margaret E Brannon
        assert "William" in result.person_name
        assert "Ijams" in result.person_name

        # ED should be extracted
        assert result.enumeration_district == "214"
        assert result.sheet == "3B"

    @pytest.mark.llm
    @pytest.mark.asyncio
    async def test_batch_extraction(
        self, extractor: CitationExtractor, check_llm_available: None
    ) -> None:
        """Test batch extraction of multiple citations."""
        citations = [
            (
                "Fed Census: 1900, Ohio, Noble [citing sheet 3B, family 57] Ijams, Ella",
                '"United States Census, 1900," database with images, *FamilySearch* '
                "(https://familysearch.org/ark:/61903/1:1:MM6X-FGZ : accessed 24 July 2015), "
                "Ella Ijams, Olive Township Caldwell village, Noble, Ohio, United States; "
                "citing sheet 3B, family 57, NARA microfilm publication T623 "
                "(Washington, D.C.: National Archives and Records Administration, n.d.); "
                "FHL microfilm 1,241,311.",
            ),
            (
                "Fed Census: 1910, Maryland, Baltimore "
                "[citing enumeration district (ED) ED 214, sheet 3B] Ijams, William H.",
                '"United States Census, 1910," database with images, *FamilySearch*'
                "(https://familysearch.org/ark:/61903/1:1:M2F4-SVS : accessed 27 November 2015), "
                "William H Ijams in household of Margaret E Brannon, "
                "Baltimore Ward 13, Baltimore (Independent City), Maryland, United States; "
                "citing enumeration district (ED) ED 214, sheet 3B, "
                "NARA microfilm publication T624 "
                "(Washington, D.C.: National Archives and Records Administration, n.d.); "
                "FHL microfilm 1,374,570.",
            ),
        ]

        results = await extractor.extract_batch(citations, max_concurrent=2)

        assert len(results) == 2
        # Both should succeed (or at least not be None)
        successful = sum(1 for r in results if r is not None)
        assert successful >= 1, "At least one extraction should succeed"

    def test_llm_provider_factory(self) -> None:
        """Test LLM provider factory."""
        # This test doesn't require API keys, just tests the factory logic
        factory = LLMProviderFactory()

        # Test that we can get a provider (or None if no API keys)
        provider = factory.get_default_provider()

        # If provider exists, it should have required methods
        if provider:
            assert provider.name in ["anthropic", "openai", "ollama"]
            assert callable(provider.get_model)
            assert callable(provider.is_available)

    def test_extractor_graceful_failure(self) -> None:
        """Test that extractor handles missing LLM provider gracefully."""
        # Create extractor (may or may not have provider)
        extractor = CitationExtractor()

        # Should not crash even if no provider
        available = extractor.is_available()
        assert isinstance(available, bool)


class TestLLMProviderSelection:
    """Test LLM provider selection and fallback logic."""

    def test_create_specific_provider(self) -> None:
        """Test creating specific providers."""
        # Anthropic
        anthropic = LLMProviderFactory.create_provider("anthropic")
        if anthropic:
            assert anthropic.name == "anthropic"

        # OpenAI
        openai = LLMProviderFactory.create_provider("openai")
        if openai:
            assert openai.name == "openai"

        # Ollama
        ollama = LLMProviderFactory.create_provider("ollama")
        if ollama:
            assert ollama.name == "ollama"

    def test_unknown_provider(self) -> None:
        """Test that unknown provider returns None."""
        provider = LLMProviderFactory.create_provider("unknown_provider")
        assert provider is None
