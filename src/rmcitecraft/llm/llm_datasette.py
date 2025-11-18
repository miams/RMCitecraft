"""
LLM (Datasette) provider implementation.

Uses Simon Willison's llm library for local tool integration.
"""

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


class LLMDatasette(LLMProvider):
    """Provider using the LLM CLI tool."""

    def __init__(self):
        """Initialize LLM Datasette provider."""
        try:
            import llm
            self._llm = llm
        except ImportError:
            raise ConfigurationError(
                "LLM package not installed. Run: pip install llm"
            )

        # Test that at least one model is available
        try:
            self._test_model_access()
        except Exception as e:
            raise ConfigurationError(
                f"LLM not properly configured: {e}\n"
                "Run 'llm keys set openai' or install a model plugin"
            )

    def _test_model_access(self):
        """Test that we can access at least one model."""
        models = self.list_models()
        if not models:
            raise ConfigurationError("No models available in LLM")

    def complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> CompletionResponse:
        """Generate a text completion using LLM."""
        model_name = model or self.default_model

        try:
            llm_model = self._llm.get_model(model_name)

            # Build options
            options = kwargs.copy()
            if temperature is not None:
                options['temperature'] = temperature
            if max_tokens is not None:
                options['max_tokens'] = max_tokens

            # Execute prompt
            response = llm_model.prompt(prompt, **options)
            text = response.text()

            # Try to get token count if available
            tokens = None
            if hasattr(response, 'tokens_used'):
                tokens = response.tokens_used

            return CompletionResponse(
                text=text,
                model=model_name,
                provider="llm",
                tokens_used=tokens,
                metadata={'options': options}
            )

        except self._llm.UnknownModelError as e:
            raise ModelNotFoundError(f"Model not found: {model_name}") from e
        except Exception as e:
            # Check for rate limit errors
            if 'rate' in str(e).lower() or '429' in str(e):
                raise RateLimitError(f"Rate limit exceeded: {e}") from e
            raise LLMError(f"LLM completion failed: {e}") from e

    def stream_complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Iterator[str]:
        """Stream a text completion using LLM."""
        model_name = model or self.default_model

        try:
            llm_model = self._llm.get_model(model_name)

            # Build options
            options = kwargs.copy()
            options['stream'] = True
            if temperature is not None:
                options['temperature'] = temperature
            if max_tokens is not None:
                options['max_tokens'] = max_tokens

            # Execute prompt with streaming
            response = llm_model.prompt(prompt, **options)

            # Stream chunks
            for chunk in response:
                yield chunk

        except self._llm.UnknownModelError as e:
            raise ModelNotFoundError(f"Model not found: {model_name}") from e
        except Exception as e:
            if 'rate' in str(e).lower() or '429' in str(e):
                raise RateLimitError(f"Rate limit exceeded: {e}") from e
            raise LLMError(f"LLM streaming failed: {e}") from e

    def complete_with_image(
        self,
        prompt: str,
        image_path: str,
        model: Optional[str] = None,
        **kwargs
    ) -> CompletionResponse:
        """Generate completion with image input."""
        # Check if model supports vision
        model_name = model or self.default_model

        # LLM doesn't have native vision support in most plugins
        # But some models like gpt-4-vision-preview might work through the API
        if 'vision' not in model_name.lower() and 'gpt-4' not in model_name.lower():
            raise NotImplementedError(
                f"Model {model_name} doesn't support vision. "
                "Try gpt-4-vision-preview or use OpenRouter provider."
            )

        try:
            # Attempt to use vision through LLM
            # This may require specific plugins or model support
            llm_model = self._llm.get_model(model_name)

            # Some LLM plugins may support attachments
            if hasattr(llm_model, 'prompt_with_attachments'):
                response = llm_model.prompt_with_attachments(
                    prompt,
                    attachments=[{'path': image_path, 'type': 'image'}],
                    **kwargs
                )
            else:
                # Fallback: Try to encode image in prompt (may not work)
                import base64
                with open(image_path, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode()

                vision_prompt = f"{prompt}\n\n[Image data: {image_path}]"
                response = llm_model.prompt(vision_prompt, **kwargs)

            text = response.text()

            return CompletionResponse(
                text=text,
                model=model_name,
                provider="llm",
                metadata={'image_path': image_path}
            )

        except Exception as e:
            logger.error(f"Vision completion failed: {e}")
            raise NotImplementedError(
                f"Vision not properly supported in LLM for model {model_name}. "
                "Consider using OpenRouter provider for vision tasks."
            )

    def list_models(self) -> list[str]:
        """List available models in LLM."""
        try:
            # Get all available models
            models = []

            # Try to get models from the LLM registry
            if hasattr(self._llm, 'get_models'):
                for model in self._llm.get_models():
                    models.append(model.name)
            else:
                # Fallback: Try common model names
                common_models = [
                    'gpt-4',
                    'gpt-4-32k',
                    'gpt-3.5-turbo',
                    'gpt-3.5-turbo-16k',
                    'claude-3-opus',
                    'claude-3-sonnet',
                    'claude-3-haiku',
                ]

                for model_name in common_models:
                    try:
                        self._llm.get_model(model_name)
                        models.append(model_name)
                    except:
                        continue

            return models

        except Exception as e:
            logger.warning(f"Failed to list LLM models: {e}")
            return []

    def get_capabilities(self, model: Optional[str] = None) -> set[ModelCapability]:
        """Get capabilities of LLM provider."""
        # Base capabilities for most LLM models
        capabilities = {
            ModelCapability.TEXT_COMPLETION,
            ModelCapability.CHAT,
            ModelCapability.STREAMING,
        }

        # Check for specific model capabilities
        if model:
            model_lower = model.lower()
            if 'vision' in model_lower or 'gpt-4' in model_lower:
                capabilities.add(ModelCapability.VISION)
            if 'gpt' in model_lower or 'claude' in model_lower:
                capabilities.add(ModelCapability.FUNCTION_CALLING)
                capabilities.add(ModelCapability.JSON_MODE)

        return capabilities

    @property
    def name(self) -> str:
        """Provider name for display."""
        return "LLM (Datasette)"

    @property
    def default_model(self) -> str:
        """Default model for LLM provider."""
        # Try to get the default from LLM config
        try:
            # Try GPT-3.5 first as it's commonly available
            self._llm.get_model("gpt-3.5-turbo")
            return "gpt-3.5-turbo"
        except:
            pass

        # Fall back to first available model
        models = self.list_models()
        if models:
            return models[0]

        raise ConfigurationError("No models available in LLM")