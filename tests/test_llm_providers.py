#!/usr/bin/env python3
"""
Test LLM providers and services.

Tests both LLM Datasette and OpenRouter providers, along with
photo classification and census transcription services.
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rmcitecraft.llm import (
    CompletionResponse,
    ConfigurationError,
    LLMError,
    ModelCapability,
    ModelNotFoundError,
    create_provider,
    get_available_providers,
)


class TestProviderFactory:
    """Test provider factory and configuration."""

    def test_get_available_providers(self):
        """Test checking available providers."""
        providers = get_available_providers()
        assert isinstance(providers, dict)
        assert "llm" in providers
        assert "openrouter" in providers
        assert all(isinstance(v, bool) for v in providers.values())

    def test_create_openrouter_provider(self):
        """Test creating OpenRouter provider."""
        config = {
            "provider": "openrouter",
            "openrouter_api_key": "test-key",
            "openrouter_site_url": "https://test.com",
            "openrouter_app_name": "TestApp",
        }

        with patch("rmcitecraft.llm.openrouter.openai.OpenAI") as mock_openai:
            from rmcitecraft.llm.openrouter import OpenRouterProvider
            provider = create_provider(config)
            assert isinstance(provider, OpenRouterProvider)
            assert provider.name == "OpenRouter"

    def test_create_llm_provider(self):
        """Test creating LLM Datasette provider."""
        config = {"provider": "llm"}

        with patch("rmcitecraft.llm.llm_datasette.llm") as mock_llm:
            # Mock successful model access
            mock_llm.get_model.return_value = MagicMock()
            mock_llm.get_models.return_value = [MagicMock(name="test-model")]

            from rmcitecraft.llm.llm_datasette import LLMDatasette
            provider = create_provider(config)
            assert isinstance(provider, LLMDatasette)
            assert provider.name == "LLM (Datasette)"

    def test_invalid_provider(self):
        """Test invalid provider configuration."""
        config = {"provider": "invalid"}

        with pytest.raises(ConfigurationError) as exc_info:
            create_provider(config)
        assert "Unknown provider" in str(exc_info.value)

    def test_missing_openrouter_key(self):
        """Test OpenRouter without API key."""
        config = {"provider": "openrouter"}

        with pytest.raises(ConfigurationError) as exc_info:
            create_provider(config)
        assert "api_key" in str(exc_info.value).lower()


class TestOpenRouterProvider:
    """Test OpenRouter provider implementation."""

    @pytest.fixture
    def provider(self):
        """Create mocked OpenRouter provider."""
        with patch("rmcitecraft.llm.openrouter.openai.OpenAI") as mock_openai:
            from rmcitecraft.llm.openrouter import OpenRouterProvider
            provider = OpenRouterProvider("test-key")
            provider.client = MagicMock()
            return provider

    def test_complete(self, provider):
        """Test text completion."""
        # Mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.usage.total_tokens = 100
        provider.client.chat.completions.create.return_value = mock_response

        response = provider.complete("Test prompt", model="openai/gpt-3.5-turbo")

        assert isinstance(response, CompletionResponse)
        assert response.text == "Test response"
        assert response.model == "openai/gpt-3.5-turbo"
        assert response.provider == "openrouter"
        assert response.tokens_used == 100

    def test_stream_complete(self, provider):
        """Test streaming completion."""
        # Mock streaming response
        mock_chunks = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=" world"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=None))]),
        ]
        provider.client.chat.completions.create.return_value = iter(mock_chunks)

        chunks = list(provider.stream_complete("Test", model="openai/gpt-3.5-turbo"))

        assert chunks == ["Hello", " world"]

    def test_list_models(self, provider):
        """Test listing available models."""
        models = provider.list_models()
        assert isinstance(models, list)
        assert len(models) > 0
        assert "openai/gpt-3.5-turbo" in models
        assert "anthropic/claude-3-opus" in models

    def test_get_capabilities(self, provider):
        """Test getting model capabilities."""
        # Test GPT-4 capabilities
        caps = provider.get_capabilities("openai/gpt-4")
        assert ModelCapability.TEXT_COMPLETION in caps
        assert ModelCapability.CHAT in caps
        assert ModelCapability.FUNCTION_CALLING in caps
        assert ModelCapability.VISION not in caps

        # Test vision model capabilities
        caps = provider.get_capabilities("openai/gpt-4-vision-preview")
        assert ModelCapability.VISION in caps

        # Test Claude capabilities
        caps = provider.get_capabilities("anthropic/claude-3-opus")
        assert ModelCapability.VISION in caps

    def test_complete_with_image(self, provider):
        """Test vision completion."""
        # Create test image
        test_image = Path(__file__).parent / "test_image.jpg"
        test_image.write_bytes(b"fake image data")

        try:
            # Mock response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "I see an image"
            provider.client.chat.completions.create.return_value = mock_response

            response = provider.complete_with_image(
                "What's in this image?",
                str(test_image),
                model="openai/gpt-4-vision-preview"
            )

            assert response.text == "I see an image"
            assert response.model == "openai/gpt-4-vision-preview"

        finally:
            test_image.unlink()

    def test_vision_not_supported(self, provider):
        """Test vision with non-vision model."""
        with pytest.raises(NotImplementedError) as exc_info:
            provider.complete_with_image(
                "Test",
                "image.jpg",
                model="openai/gpt-3.5-turbo"
            )
        assert "doesn't support vision" in str(exc_info.value)


class TestLLMDatasetteProvider:
    """Test LLM Datasette provider implementation."""

    @pytest.fixture
    def provider(self):
        """Create mocked LLM provider."""
        with patch("rmcitecraft.llm.llm_datasette.llm") as mock_llm:
            # Mock successful initialization
            mock_llm.get_model.return_value = MagicMock()
            mock_llm.get_models.return_value = [MagicMock(name="test-model")]

            from rmcitecraft.llm.llm_datasette import LLMDatasette
            provider = LLMDatasette()
            provider._llm = mock_llm
            return provider

    def test_complete(self, provider):
        """Test text completion."""
        # Mock model and response
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "Test response"
        mock_model.prompt.return_value = mock_response
        provider._llm.get_model.return_value = mock_model

        response = provider.complete("Test prompt", model="gpt-3.5-turbo")

        assert isinstance(response, CompletionResponse)
        assert response.text == "Test response"
        assert response.model == "gpt-3.5-turbo"
        assert response.provider == "llm"

    def test_stream_complete(self, provider):
        """Test streaming completion."""
        # Mock streaming
        mock_model = MagicMock()
        mock_model.prompt.return_value = iter(["Hello", " ", "world"])
        provider._llm.get_model.return_value = mock_model

        chunks = list(provider.stream_complete("Test", model="gpt-3.5-turbo"))

        assert chunks == ["Hello", " ", "world"]

    def test_model_not_found(self, provider):
        """Test handling unknown model."""
        provider._llm.UnknownModelError = Exception
        provider._llm.get_model.side_effect = provider._llm.UnknownModelError("Unknown")

        with pytest.raises(ModelNotFoundError) as exc_info:
            provider.complete("Test", model="unknown-model")
        assert "unknown-model" in str(exc_info.value)


class TestPhotoClassifier:
    """Test photo classification service."""

    @pytest.fixture
    def classifier(self):
        """Create photo classifier with mocked provider."""
        from rmcitecraft.services.photo_classifier import PhotoClassifier

        mock_provider = MagicMock()
        classifier = PhotoClassifier(provider=mock_provider)
        return classifier

    def test_classify_photo(self, classifier):
        """Test photo classification."""
        from rmcitecraft.llm import ClassificationResponse

        # Create test image
        test_image = Path(__file__).parent / "test_photo.jpg"
        test_image.write_bytes(b"fake image")

        try:
            # Mock classification response
            mock_response = ClassificationResponse(
                category="Grave",
                confidence=0.95,
                reasoning="Headstone visible"
            )
            classifier.provider.classify_image.return_value = mock_response

            result = classifier.classify_photo(test_image)

            assert result.category == "Grave"
            assert result.confidence == 0.95
            assert result.reasoning == "Headstone visible"

        finally:
            test_image.unlink()

    def test_suggest_photo_type(self):
        """Test photo type suggestion from description."""
        from rmcitecraft.services.photo_classifier import PhotoClassifier

        classifier = PhotoClassifier(provider=MagicMock())

        # Test various descriptions
        assert classifier.suggest_photo_type("Headstone inscription") == "Grave"
        assert classifier.suggest_photo_type("Portrait of John Doe") == "Person"
        assert classifier.suggest_photo_type("Family gathering photo") == "Family"
        assert classifier.suggest_photo_type("Death certificate") == "Document"
        assert classifier.suggest_photo_type("Cemetery entrance gate") == "Cemetery"
        assert classifier.suggest_photo_type("Beautiful roses") == "Flowers"
        assert classifier.suggest_photo_type("Random text") == "Other"
        assert classifier.suggest_photo_type("") == "Other"


class TestCensusTranscriber:
    """Test census transcription service."""

    @pytest.fixture
    def transcriber(self):
        """Create census transcriber with mocked provider."""
        from rmcitecraft.services.census_transcriber import CensusTranscriber

        mock_provider = MagicMock()
        transcriber = CensusTranscriber(provider=mock_provider)
        return transcriber

    def test_get_schema_for_year(self, transcriber):
        """Test schema selection by census year."""
        # Test different year ranges
        schema_1790 = transcriber._get_schema_for_year(1790)
        assert "head_of_household" in schema_1790
        assert "slaves" in schema_1790

        schema_1850 = transcriber._get_schema_for_year(1850)
        assert "dwelling_number" in schema_1850
        assert "occupation" in schema_1850

        schema_1880 = transcriber._get_schema_for_year(1880)
        assert "enumeration_district" in schema_1880
        assert "relationship_to_head" in schema_1880

        schema_1900 = transcriber._get_schema_for_year(1900)
        assert "birth_month" in schema_1900
        assert "years_married" in schema_1900

        schema_1920 = transcriber._get_schema_for_year(1920)
        assert "industry" in schema_1920

        schema_1940 = transcriber._get_schema_for_year(1940)
        assert "income_1939" in schema_1940
        assert "residence_1935_city" in schema_1940

    def test_transcribe_census(self, transcriber):
        """Test census transcription."""
        from rmcitecraft.llm import ExtractionResponse

        # Create test image
        test_image = Path(__file__).parent / "census_1900.jpg"
        test_image.write_bytes(b"fake census image")

        try:
            # Mock transcription response
            mock_response = ExtractionResponse(
                data={
                    "name": "John Doe",
                    "age": 35,
                    "occupation": "Farmer",
                    "birthplace": "Ohio"
                },
                confidence=0.85
            )
            transcriber.provider.transcribe_census_image.return_value = mock_response

            result = transcriber.transcribe_census(test_image, 1900)

            assert result.data["name"] == "John Doe"
            assert result.data["age"] == 35
            assert result.confidence == 0.85

        finally:
            test_image.unlink()

    def test_invalid_census_year(self, transcriber):
        """Test handling invalid census year."""
        # Create a test image so it exists
        test_image = Path(__file__).parent / "test_census.jpg"
        test_image.write_bytes(b"fake census")

        try:
            with pytest.raises(ValueError) as exc_info:
                transcriber.transcribe_census(test_image, 1905)
            assert "Invalid census year" in str(exc_info.value)

            with pytest.raises(ValueError) as exc_info:
                transcriber.transcribe_census(test_image, 1780)
            assert "Invalid census year" in str(exc_info.value)
        finally:
            test_image.unlink()

    def test_validate_transcription(self, transcriber):
        """Test transcription validation."""
        data = {
            "records": [
                {"name": "John Doe", "age": 150},  # Invalid age
                {"age": 25},  # Missing name
                {"name": "Jane Doe", "age": 30, "relationship": "Wife"},  # Not head
            ]
        }

        warnings = transcriber.validate_transcription(data, 1900)

        assert any("Unusual age 150" in w for w in warnings)
        assert any("Missing name" in w for w in warnings)

        # Test with explicit head of household issue
        data2 = {
            "records": [
                {"name": "Jane Doe", "age": 30, "relationship": "Wife"},  # First person not head
            ]
        }
        warnings2 = transcriber.validate_transcription(data2, 1900)
        assert any("should be head" in w for w in warnings2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])