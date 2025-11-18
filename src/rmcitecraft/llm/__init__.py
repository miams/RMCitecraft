"""
LLM provider abstraction for RMCitecraft.

Supports multiple LLM providers:
- LLM (Datasette) - Local tool with conversation history
- OpenRouter - Cloud API with multi-model support
"""

from .base import (
    LLMProvider,
    CompletionResponse,
    ClassificationResponse,
    ExtractionResponse,
    ModelCapability,
    LLMError,
    ModelNotFoundError,
    RateLimitError,
    ConfigurationError,
)
from .factory import create_provider, get_available_providers

__all__ = [
    'LLMProvider',
    'CompletionResponse',
    'ClassificationResponse',
    'ExtractionResponse',
    'ModelCapability',
    'LLMError',
    'ModelNotFoundError',
    'RateLimitError',
    'ConfigurationError',
    'create_provider',
    'get_available_providers',
]