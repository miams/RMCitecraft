"""
Factory for creating LLM providers based on configuration.
"""

from typing import Optional

from loguru import logger

from .base import ConfigurationError, LLMProvider


# Track available providers
AVAILABLE_PROVIDERS = {}


def _check_llm_available() -> bool:
    """Check if LLM Datasette is available."""
    try:
        import llm
        return True
    except ImportError:
        return False


def _check_openrouter_available() -> bool:
    """Check if OpenRouter (OpenAI) is available."""
    try:
        import openai
        return True
    except ImportError:
        return False


def get_available_providers() -> dict[str, bool]:
    """
    Get dict of available providers and their status.

    Returns:
        Dict mapping provider name to availability status
    """
    return {
        "llm": _check_llm_available(),
        "openrouter": _check_openrouter_available(),
    }


def create_provider(config: dict) -> LLMProvider:
    """
    Create an LLM provider based on configuration.

    Args:
        config: Configuration dict with at minimum:
            - provider: "llm" or "openrouter"
            For OpenRouter:
            - openrouter_api_key: API key
            - openrouter_site_url: Optional site URL
            - openrouter_app_name: Optional app name

    Returns:
        Configured LLMProvider instance

    Raises:
        ConfigurationError: If provider is misconfigured
        ImportError: If required packages aren't installed
    """
    provider_type = config.get("provider", "openrouter").lower()

    logger.info(f"Creating LLM provider: {provider_type}")

    if provider_type == "llm":
        if not _check_llm_available():
            raise ImportError(
                "LLM package not installed. "
                "Run: pip install llm"
            )

        from .llm_datasette import LLMDatasette
        return LLMDatasette()

    elif provider_type == "openrouter":
        if not _check_openrouter_available():
            raise ImportError(
                "OpenAI package not installed. "
                "Run: pip install openai"
            )

        api_key = config.get("openrouter_api_key")
        if not api_key:
            raise ConfigurationError(
                "OpenRouter requires 'openrouter_api_key' in config"
            )

        from .openrouter import OpenRouterProvider
        return OpenRouterProvider(
            api_key=api_key,
            site_url=config.get("openrouter_site_url"),
            app_name=config.get("openrouter_app_name", "RMCitecraft"),
        )

    else:
        raise ConfigurationError(
            f"Unknown provider: {provider_type}. "
            "Supported: 'llm', 'openrouter'"
        )