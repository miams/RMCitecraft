"""
OpenRouter provider implementation.

Uses OpenRouter API for access to multiple LLM models.
"""

import base64
from pathlib import Path
from typing import Any, Iterator, Optional

from loguru import logger

from .base import (
    CompletionResponse,
    ConfigurationError,
    LLMError,
    LLMProvider,
    ModelCapability,
    ModelNotFoundError,
    RateLimitError,
)


# Model capabilities mapping
OPENROUTER_MODELS = {
    # OpenAI models
    "openai/gpt-4-turbo": {
        "capabilities": {ModelCapability.TEXT_COMPLETION, ModelCapability.CHAT,
                        ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE,
                        ModelCapability.STREAMING},
        "context": 128000,
        "vision": False,
    },
    "openai/gpt-4-turbo-preview": {
        "capabilities": {ModelCapability.TEXT_COMPLETION, ModelCapability.CHAT,
                        ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE,
                        ModelCapability.STREAMING},
        "context": 128000,
        "vision": False,
    },
    "openai/gpt-4-vision-preview": {
        "capabilities": {ModelCapability.TEXT_COMPLETION, ModelCapability.CHAT,
                        ModelCapability.VISION, ModelCapability.STREAMING},
        "context": 128000,
        "vision": True,
    },
    "openai/gpt-4": {
        "capabilities": {ModelCapability.TEXT_COMPLETION, ModelCapability.CHAT,
                        ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE,
                        ModelCapability.STREAMING},
        "context": 8192,
        "vision": False,
    },
    "openai/gpt-3.5-turbo": {
        "capabilities": {ModelCapability.TEXT_COMPLETION, ModelCapability.CHAT,
                        ModelCapability.FUNCTION_CALLING, ModelCapability.JSON_MODE,
                        ModelCapability.STREAMING},
        "context": 16384,
        "vision": False,
    },

    # Anthropic models
    "anthropic/claude-3-opus": {
        "capabilities": {ModelCapability.TEXT_COMPLETION, ModelCapability.CHAT,
                        ModelCapability.VISION, ModelCapability.STREAMING},
        "context": 200000,
        "vision": True,
    },
    "anthropic/claude-3-sonnet": {
        "capabilities": {ModelCapability.TEXT_COMPLETION, ModelCapability.CHAT,
                        ModelCapability.VISION, ModelCapability.STREAMING},
        "context": 200000,
        "vision": True,
    },
    "anthropic/claude-3-haiku": {
        "capabilities": {ModelCapability.TEXT_COMPLETION, ModelCapability.CHAT,
                        ModelCapability.VISION, ModelCapability.STREAMING},
        "context": 200000,
        "vision": True,
    },
    "anthropic/claude-2.1": {
        "capabilities": {ModelCapability.TEXT_COMPLETION, ModelCapability.CHAT,
                        ModelCapability.STREAMING},
        "context": 200000,
        "vision": False,
    },

    # Google models
    "google/gemini-pro": {
        "capabilities": {ModelCapability.TEXT_COMPLETION, ModelCapability.CHAT,
                        ModelCapability.STREAMING},
        "context": 32760,
        "vision": False,
    },
    "google/gemini-pro-vision": {
        "capabilities": {ModelCapability.TEXT_COMPLETION, ModelCapability.CHAT,
                        ModelCapability.VISION, ModelCapability.STREAMING},
        "context": 32760,
        "vision": True,
    },
    "google/gemini-pro-1.5": {
        "capabilities": {ModelCapability.TEXT_COMPLETION, ModelCapability.CHAT,
                        ModelCapability.VISION, ModelCapability.STREAMING},
        "context": 1000000,  # 1M context window
        "vision": True,
    },
    "google/gemini-flash-1.5": {
        "capabilities": {ModelCapability.TEXT_COMPLETION, ModelCapability.CHAT,
                        ModelCapability.VISION, ModelCapability.STREAMING},
        "context": 1000000,  # 1M context window
        "vision": True,
    },

    # Meta models
    "meta-llama/llama-3-70b-instruct": {
        "capabilities": {ModelCapability.TEXT_COMPLETION, ModelCapability.CHAT,
                        ModelCapability.STREAMING},
        "context": 8192,
        "vision": False,
    },
}


class OpenRouterProvider(LLMProvider):
    """Provider using OpenRouter API."""

    def __init__(self, api_key: str, site_url: Optional[str] = None,
                 app_name: Optional[str] = None):
        """
        Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key
            site_url: Optional site URL for rate limit benefits
            app_name: Optional app name for tracking
        """
        try:
            import openai
            self._openai = openai
        except ImportError:
            raise ConfigurationError(
                "OpenAI package not installed. Run: pip install openai"
            )

        if not api_key:
            raise ConfigurationError("OpenRouter API key is required")

        # Initialize OpenAI client with OpenRouter base URL
        self.client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

        # Optional headers for better rate limits and tracking
        self.extra_headers = {}
        if site_url:
            self.extra_headers["HTTP-Referer"] = site_url
        if app_name:
            self.extra_headers["X-Title"] = app_name

    def complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> CompletionResponse:
        """Generate a text completion using OpenRouter."""
        model_name = model or self.default_model

        try:
            # Build request
            request_params = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            }

            if max_tokens:
                request_params["max_tokens"] = max_tokens

            # Add any extra kwargs
            request_params.update(kwargs)

            # Make request
            response = self.client.chat.completions.create(
                **request_params,
                extra_headers=self.extra_headers if self.extra_headers else None,
            )

            # Extract response
            text = response.choices[0].message.content
            tokens = None
            cost = None

            if hasattr(response, 'usage'):
                tokens = response.usage.total_tokens
                # OpenRouter provides cost in headers sometimes
                if hasattr(response, '_headers'):
                    cost_str = response._headers.get('X-Cost')
                    if cost_str:
                        cost = float(cost_str)

            return CompletionResponse(
                text=text,
                model=model_name,
                provider="openrouter",
                tokens_used=tokens,
                cost=cost,
                metadata={'request_params': request_params}
            )

        except self._openai.NotFoundError as e:
            raise ModelNotFoundError(f"Model not found: {model_name}") from e
        except self._openai.RateLimitError as e:
            raise RateLimitError(f"Rate limit exceeded: {e}") from e
        except Exception as e:
            raise LLMError(f"OpenRouter completion failed: {e}") from e

    def stream_complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Iterator[str]:
        """Stream a text completion using OpenRouter."""
        model_name = model or self.default_model

        try:
            # Build request
            request_params = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "stream": True,
            }

            if max_tokens:
                request_params["max_tokens"] = max_tokens

            # Add any extra kwargs
            request_params.update(kwargs)

            # Make streaming request
            stream = self.client.chat.completions.create(
                **request_params,
                extra_headers=self.extra_headers if self.extra_headers else None,
            )

            # Stream chunks
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except self._openai.NotFoundError as e:
            raise ModelNotFoundError(f"Model not found: {model_name}") from e
        except self._openai.RateLimitError as e:
            raise RateLimitError(f"Rate limit exceeded: {e}") from e
        except Exception as e:
            raise LLMError(f"OpenRouter streaming failed: {e}") from e

    def complete_with_image(
        self,
        prompt: str,
        image_path: str,
        model: Optional[str] = None,
        **kwargs
    ) -> CompletionResponse:
        """Generate completion with image input using OpenRouter."""
        model_name = model or self.default_model

        # Check if model supports vision
        if not self._model_supports_vision(model_name):
            raise NotImplementedError(
                f"Model {model_name} doesn't support vision. "
                f"Try one of: {self._get_vision_models()}"
            )

        try:
            # Read and encode image
            image_path = Path(image_path)
            if not image_path.exists():
                raise FileNotFoundError(f"Image not found: {image_path}")

            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode()

            # Determine MIME type
            mime_type = "image/jpeg"
            if image_path.suffix.lower() == '.png':
                mime_type = "image/png"
            elif image_path.suffix.lower() in ['.gif', '.webp']:
                mime_type = f"image/{image_path.suffix[1:].lower()}"

            # Build message with image
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_data}"
                        }
                    }
                ]
            }]

            # Make request
            response = self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                **kwargs,
                extra_headers=self.extra_headers if self.extra_headers else None,
            )

            # Extract response
            text = response.choices[0].message.content
            tokens = None
            if hasattr(response, 'usage'):
                tokens = response.usage.total_tokens

            return CompletionResponse(
                text=text,
                model=model_name,
                provider="openrouter",
                tokens_used=tokens,
                metadata={'image_path': str(image_path)}
            )

        except self._openai.NotFoundError as e:
            raise ModelNotFoundError(f"Model not found: {model_name}") from e
        except self._openai.RateLimitError as e:
            raise RateLimitError(f"Rate limit exceeded: {e}") from e
        except Exception as e:
            raise LLMError(f"OpenRouter vision completion failed: {e}") from e

    def list_models(self) -> list[str]:
        """List available models from OpenRouter."""
        # Return our known models
        # In production, you could fetch this from OpenRouter's API
        return list(OPENROUTER_MODELS.keys())

    def get_capabilities(self, model: Optional[str] = None) -> set[ModelCapability]:
        """Get capabilities of a model or provider."""
        if model:
            # Get specific model capabilities
            model_info = OPENROUTER_MODELS.get(model, {})
            return model_info.get("capabilities", set())
        else:
            # Return all capabilities supported by any model
            all_capabilities = set()
            for model_info in OPENROUTER_MODELS.values():
                all_capabilities.update(model_info.get("capabilities", set()))
            return all_capabilities

    def _model_supports_vision(self, model: str) -> bool:
        """Check if a model supports vision."""
        model_info = OPENROUTER_MODELS.get(model, {})
        return model_info.get("vision", False)

    def _get_vision_models(self) -> list[str]:
        """Get list of models that support vision."""
        return [
            model for model, info in OPENROUTER_MODELS.items()
            if info.get("vision", False)
        ]

    @property
    def name(self) -> str:
        """Provider name for display."""
        return "OpenRouter"

    @property
    def default_model(self) -> str:
        """Default model for OpenRouter provider."""
        # Default to GPT-3.5 for cost effectiveness
        return "openai/gpt-3.5-turbo"