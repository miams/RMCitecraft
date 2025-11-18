"""
LLM provider configuration and error handling tests.

Tests provider initialization, configuration validation, and error handling.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from rmcitecraft.llm import (
    ConfigurationError,
    LLMError,
    ModelNotFoundError,
    RateLimitError,
    create_provider,
    get_available_providers,
)


class TestProviderConfiguration:
    """Test provider configuration and initialization."""

    def test_missing_openrouter_api_key_raises_error(self):
        """Verify ConfigurationError when OpenRouter API key missing."""
        config = {"provider": "openrouter"}

        with pytest.raises(ConfigurationError, match="api_key"):
            create_provider(config)

    def test_invalid_provider_name_raises_error(self):
        """Verify error when unknown provider requested."""
        config = {"provider": "invalid_provider"}

        with pytest.raises(ConfigurationError, match="Unknown provider"):
            create_provider(config)

    def test_default_provider_from_config(self):
        """Verify provider created from config dict."""
        config = {
            "provider": "openrouter",
            "openrouter_api_key": "test-key",
        }

        with patch("openai.OpenAI"):
            provider = create_provider(config)
            assert provider.name == "OpenRouter"

    def test_llm_datasette_initialization_without_package(self):
        """Verify error when LLM package not installed.

        Tests that ImportError is raised when llm package is not available.
        We simulate this by making the import fail via sys.modules manipulation.
        """
        config = {"provider": "llm"}

        # Make llm import fail by setting it to None in sys.modules
        # This simulates llm not being installed
        with patch.dict('sys.modules', {'llm': None}):
            # Should raise ImportError when llm package not available
            with pytest.raises(ImportError, match="not installed"):
                create_provider(config)

    def test_get_available_providers(self):
        """Verify get_available_providers returns dict of availability."""
        providers = get_available_providers()

        assert isinstance(providers, dict)
        assert "llm" in providers
        assert "openrouter" in providers
        assert all(isinstance(v, bool) for v in providers.values())

    def test_openrouter_with_optional_headers(self):
        """Verify OpenRouter accepts optional site_url and app_name."""
        config = {
            "provider": "openrouter",
            "openrouter_api_key": "test-key",
            "openrouter_site_url": "https://test.com",
            "openrouter_app_name": "TestApp",
        }

        with patch("openai.OpenAI") as mock_openai:
            provider = create_provider(config)
            assert provider.name == "OpenRouter"

    def test_configuration_error_message_helpful(self):
        """Verify ConfigurationError has helpful message."""
        config = {"provider": "openrouter"}

        try:
            create_provider(config)
            assert False, "Should have raised ConfigurationError"
        except ConfigurationError as e:
            error_msg = str(e)
            assert "api_key" in error_msg.lower()

    def test_llm_datasette_model_access_error(self):
        """Verify error when LLM models not accessible.

        Tests that LLMDatasette raises ConfigurationError when llm package is installed
        but no models are available (e.g., no API keys configured).
        """
        config = {"provider": "llm"}

        # Create a mock llm module with no models
        with patch("rmcitecraft.llm.llm_datasette.LLMDatasette._test_model_access") as mock_test:
            # Make _test_model_access raise ConfigurationError (simulating no models)
            mock_test.side_effect = ConfigurationError("No models available in LLM")

            # Should raise ConfigurationError when no models available
            with pytest.raises(ConfigurationError, match="No models available"):
                provider = create_provider(config)


class TestProviderErrorHandling:
    """Test error handling for provider operations.

    NOTE: These tests have bugs - they patch _llm with None then try to set attributes on it.
    Tests need to be rewritten with proper mocking.
    """

    def test_model_not_found_error(self):
        """Verify ModelNotFoundError raised for unknown models."""
        # Create a provider with the llm package installed
        config = {"provider": "llm"}

        # Mock the llm package that gets imported in LLMDatasette.__init__
        mock_llm_module = MagicMock()

        # Create a mock model for initial setup
        mock_model = MagicMock()
        mock_model.name = "test-model"
        mock_llm_module.get_models.return_value = [mock_model]
        mock_llm_module.get_model.return_value = mock_model

        # Create UnknownModelError exception class
        class MockUnknownModelError(Exception):
            pass

        mock_llm_module.UnknownModelError = MockUnknownModelError

        # Patch the llm package import
        with patch.dict('sys.modules', {'llm': mock_llm_module}):
            provider = create_provider(config)

            # Now configure get_model to raise UnknownModelError for unknown models
            mock_llm_module.get_model.side_effect = MockUnknownModelError("Unknown model")

            # Should convert UnknownModelError to ModelNotFoundError
            with pytest.raises(ModelNotFoundError):
                provider.complete("Test prompt", model="unknown-model")

    def test_handles_api_errors_gracefully(self):
        """Verify graceful handling of API errors."""
        config = {
            "provider": "openrouter",
            "openrouter_api_key": "test-key",
        }

        with patch("openai.OpenAI") as mock_openai:
            provider = create_provider(config)
            provider.client = MagicMock()

            # Simulate API error
            provider.client.chat.completions.create.side_effect = Exception("API Error")

            with pytest.raises(LLMError):
                provider.complete("Test prompt", model="test-model")

    def test_handles_network_errors(self):
        """Verify handling of network-related errors."""
        config = {
            "provider": "openrouter",
            "openrouter_api_key": "test-key",
        }

        with patch("openai.OpenAI") as mock_openai:
            provider = create_provider(config)
            provider.client = MagicMock()

            # Simulate connection error
            import requests
            provider.client.chat.completions.create.side_effect = \
                requests.exceptions.ConnectionError("Network error")

            with pytest.raises((LLMError, requests.exceptions.ConnectionError)):
                provider.complete("Test prompt", model="test-model")


class TestModelCapabilities:
    """Test model capability detection."""

    def test_openrouter_vision_model_detection(self):
        """Verify vision capability detected for vision models."""
        config = {
            "provider": "openrouter",
            "openrouter_api_key": "test-key",
        }

        with patch("openai.OpenAI"):
            provider = create_provider(config)

            from rmcitecraft.llm import ModelCapability

            # Test vision models
            caps = provider.get_capabilities("openai/gpt-4-vision-preview")
            assert ModelCapability.VISION in caps

            caps = provider.get_capabilities("anthropic/claude-3-opus")
            assert ModelCapability.VISION in caps

            # Test non-vision model
            caps = provider.get_capabilities("openai/gpt-3.5-turbo")
            assert ModelCapability.VISION not in caps

    def test_vision_not_supported_error(self):
        """Verify error when using vision with non-vision model."""
        config = {
            "provider": "openrouter",
            "openrouter_api_key": "test-key",
        }

        with patch("openai.OpenAI"):
            provider = create_provider(config)
            provider.client = MagicMock()

            with pytest.raises(NotImplementedError, match="doesn't support vision"):
                provider.complete_with_image(
                    "Describe this",
                    "test.jpg",
                    model="openai/gpt-3.5-turbo"
                )

    def test_list_models_returns_models(self):
        """Verify list_models returns available models."""
        config = {
            "provider": "openrouter",
            "openrouter_api_key": "test-key",
        }

        with patch("openai.OpenAI"):
            provider = create_provider(config)

            models = provider.list_models()
            assert isinstance(models, list)
            assert len(models) > 0
            assert "openai/gpt-4" in models
            assert "anthropic/claude-3-opus" in models


class TestProviderDefaults:
    """Test provider default settings."""

    def test_default_model_fallback(self):
        """Verify default model used when not specified."""
        config = {"provider": "llm"}

        # Mock the llm package that gets imported in LLMDatasette.__init__
        mock_llm_module = MagicMock()

        # Create a mock model
        mock_model = MagicMock()
        mock_model.name = "gpt-3.5-turbo"

        # Create mock response
        mock_response = MagicMock()
        mock_response.text.return_value = "Response"
        mock_model.prompt.return_value = mock_response

        mock_llm_module.get_model.return_value = mock_model
        mock_llm_module.get_models.return_value = [mock_model]

        # Patch the llm package import
        with patch.dict('sys.modules', {'llm': mock_llm_module}):
            provider = create_provider(config)

            # Call without model parameter - should use default
            response = provider.complete("Test")

            # Verify response
            assert response.text == "Response"

            # Should have called get_model (for default model)
            mock_llm_module.get_model.assert_called()

    def test_default_temperature(self):
        """Verify default temperature applied."""
        config = {
            "provider": "openrouter",
            "openrouter_api_key": "test-key",
        }

        with patch("openai.OpenAI"):
            provider = create_provider(config)
            provider.client = MagicMock()

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test"
            mock_response.usage.total_tokens = 100
            provider.client.chat.completions.create.return_value = mock_response

            # Call with default temperature
            provider.complete("Test", model="test-model")

            # Verify temperature was set (default or explicit)
            call_kwargs = provider.client.chat.completions.create.call_args[1]
            assert "temperature" in call_kwargs


class TestEnvironmentConfiguration:
    """Test configuration from environment variables."""

    def test_reads_api_key_from_env(self, monkeypatch):
        """Verify API key read from environment variable."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "env-test-key")

        config = {
            "provider": "openrouter",
            "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
        }

        with patch("openai.OpenAI"):
            provider = create_provider(config)
            assert provider.name == "OpenRouter"

    def test_handles_missing_env_variables(self):
        """Verify handling when environment variables not set."""
        # Don't set any env vars
        api_key = os.getenv("NONEXISTENT_API_KEY")
        assert api_key is None

        config = {
            "provider": "openrouter",
            "openrouter_api_key": api_key,
        }

        with pytest.raises(ConfigurationError):
            create_provider(config)


class TestProviderSwitching:
    """Test switching between providers."""

    def test_can_create_multiple_providers(self):
        """Verify multiple providers can be created."""
        config_openrouter = {
            "provider": "openrouter",
            "openrouter_api_key": "test-key-1",
        }

        config_llm = {"provider": "llm"}

        # Create first provider (OpenRouter)
        with patch("openai.OpenAI"):
            provider1 = create_provider(config_openrouter)
            assert provider1.name == "OpenRouter"

        # Create second provider (LLM Datasette)
        mock_llm_module = MagicMock()
        mock_model = MagicMock()
        mock_model.name = "test-model"
        mock_llm_module.get_model.return_value = mock_model
        mock_llm_module.get_models.return_value = [mock_model]

        # Patch the llm package import
        with patch.dict('sys.modules', {'llm': mock_llm_module}):
            provider2 = create_provider(config_llm)
            assert provider2.name == "LLM (Datasette)"

    def test_providers_are_independent(self):
        """Verify providers don't interfere with each other."""
        with patch("openai.OpenAI"):
            provider1 = create_provider({
                "provider": "openrouter",
                "openrouter_api_key": "key1",
            })

            provider2 = create_provider({
                "provider": "openrouter",
                "openrouter_api_key": "key2",
            })

            # Should be different instances
            assert provider1 is not provider2
