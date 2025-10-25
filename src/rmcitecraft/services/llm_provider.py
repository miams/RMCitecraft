"""LLM provider abstraction for citation extraction.

Supports multiple LLM providers with fallback chain.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from loguru import logger
from pydantic import BaseModel

from rmcitecraft.config import get_config


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def get_model(self) -> BaseChatModel:
        """Get the language model instance."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available (API key set, etc.)."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass


class AnthropicProvider(LLMProvider):
    """Anthropic (Claude) LLM provider."""

    def __init__(self) -> None:
        """Initialize Anthropic provider."""
        self.config = get_config()

    def get_model(self) -> BaseChatModel:
        """Get Claude model instance."""
        return ChatAnthropic(
            model=self.config.anthropic_model,
            api_key=self.config.anthropic_api_key,
            temperature=self.config.llm_temperature,
            max_tokens=self.config.llm_max_tokens,
        )

    def is_available(self) -> bool:
        """Check if Anthropic API key is set."""
        return bool(self.config.anthropic_api_key)

    @property
    def name(self) -> str:
        """Provider name."""
        return "anthropic"


class OpenAIProvider(LLMProvider):
    """OpenAI (GPT) LLM provider."""

    def __init__(self) -> None:
        """Initialize OpenAI provider."""
        self.config = get_config()

    def get_model(self) -> BaseChatModel:
        """Get OpenAI model instance."""
        return ChatOpenAI(
            model=self.config.openai_model,
            api_key=self.config.openai_api_key,
            temperature=self.config.llm_temperature,
            max_tokens=self.config.llm_max_tokens,
        )

    def is_available(self) -> bool:
        """Check if OpenAI API key is set."""
        return bool(self.config.openai_api_key)

    @property
    def name(self) -> str:
        """Provider name."""
        return "openai"


class OllamaProvider(LLMProvider):
    """Ollama (local) LLM provider."""

    def __init__(self) -> None:
        """Initialize Ollama provider."""
        self.config = get_config()

    def get_model(self) -> BaseChatModel:
        """Get Ollama model instance."""
        return ChatOllama(
            model=self.config.ollama_model,
            base_url=self.config.ollama_base_url,
            temperature=self.config.llm_temperature,
        )

    def is_available(self) -> bool:
        """Check if Ollama is available (assumes always available if configured)."""
        # Could ping the Ollama server here, but for now assume available
        return True

    @property
    def name(self) -> str:
        """Provider name."""
        return "ollama"


class LLMProviderFactory:
    """Factory for creating LLM providers with fallback chain."""

    _providers = {
        "anthropic": AnthropicProvider,
        "openai": OpenAIProvider,
        "ollama": OllamaProvider,
    }

    @classmethod
    def create_provider(cls, provider_name: str) -> Optional[LLMProvider]:
        """Create a specific LLM provider.

        Args:
            provider_name: Name of provider (anthropic, openai, ollama)

        Returns:
            LLMProvider instance or None if unavailable
        """
        provider_class = cls._providers.get(provider_name.lower())
        if not provider_class:
            logger.warning(f"Unknown provider: {provider_name}")
            return None

        provider = provider_class()
        if not provider.is_available():
            logger.warning(f"Provider {provider_name} not available (missing API key?)")
            return None

        logger.info(f"Created LLM provider: {provider_name}")
        return provider

    @classmethod
    def get_default_provider(cls) -> Optional[LLMProvider]:
        """Get the default LLM provider from config.

        Returns:
            LLMProvider instance or None if none available
        """
        config = get_config()
        provider = cls.create_provider(config.default_llm_provider)

        if provider:
            return provider

        # Try fallback chain
        logger.warning(
            f"Default provider {config.default_llm_provider} not available, trying fallbacks"
        )

        for provider_name in ["anthropic", "openai", "ollama"]:
            if provider_name == config.default_llm_provider:
                continue  # Already tried

            provider = cls.create_provider(provider_name)
            if provider:
                logger.info(f"Using fallback provider: {provider_name}")
                return provider

        logger.error("No LLM providers available!")
        return None

    @classmethod
    def create_chain_with_parser(
        cls,
        provider: LLMProvider,
        parser: PydanticOutputParser,
    ) -> Any:
        """Create a LangChain chain with structured output.

        Args:
            provider: LLM provider instance
            parser: Pydantic output parser

        Returns:
            LangChain chain with structured output
        """
        model = provider.get_model()

        # For models that support structured output natively
        if hasattr(model, "with_structured_output"):
            # Get the Pydantic model from the parser
            pydantic_model = parser.pydantic_object
            return model.with_structured_output(pydantic_model)
        else:
            # Fallback to using parser in chain
            return model | parser


def get_llm_for_extraction() -> Optional[BaseChatModel]:
    """Get an LLM instance for citation extraction.

    Returns:
        LangChain chat model instance or None if no provider available
    """
    provider = LLMProviderFactory.get_default_provider()
    if not provider:
        return None

    return provider.get_model()
