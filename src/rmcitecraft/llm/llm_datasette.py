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
        """Generate completion with image input.

        Uses llm library's attachment API for vision-capable models like Gemini.

        Args:
            prompt: Text prompt to send with the image
            image_path: Path to the image file
            model: Model name (default: gemini-3-pro-preview for vision tasks)
            **kwargs: Additional options passed to the model

        Returns:
            CompletionResponse with the model's analysis
        """
        import time
        from .llm_logger import log_llm_request, log_llm_response

        # Default to Gemini for vision tasks (best vision support in llm ecosystem)
        model_name = model or "gemini-3-pro-preview"

        # Build options, filtering out None values
        options = {k: v for k, v in kwargs.items() if v is not None}

        # Log the request
        request_id = log_llm_request(
            provider="llm",
            model=model_name,
            prompt=prompt,
            image_path=image_path,
            options=options,
            context=kwargs.get("context"),
        )

        logger.info(f"complete_with_image called: model={model_name}, image={image_path}")
        logger.info(f"Prompt length: {len(prompt)} chars")

        start_time = time.time()

        try:
            logger.info(f"Getting LLM model: {model_name}")
            llm_model = self._llm.get_model(model_name)
            logger.info(f"Model obtained: {llm_model}")

            # Use llm library's Attachment API for image input
            logger.info(f"Creating attachment for: {image_path}")
            attachment = self._llm.Attachment(path=image_path)

            logger.info(f"Options: {options}")

            # Execute prompt with image attachment
            logger.info("Calling llm_model.prompt()...")
            response = llm_model.prompt(
                prompt,
                attachments=[attachment],
                **options
            )

            logger.info("Getting response text...")
            text = response.text()
            duration = time.time() - start_time
            logger.info(f"Response received, length={len(text)} chars, duration={duration:.2f}s")

            # Try to get token count if available
            tokens = None
            if hasattr(response, 'input_tokens') and hasattr(response, 'output_tokens'):
                tokens = (response.input_tokens or 0) + (response.output_tokens or 0)
                logger.info(f"Tokens used: {tokens}")

            # Log the response
            log_llm_response(
                request_id=request_id,
                response_text=text,
                tokens_used=tokens,
                duration_seconds=duration,
                metadata={
                    'input_tokens': getattr(response, 'input_tokens', None),
                    'output_tokens': getattr(response, 'output_tokens', None),
                },
            )

            return CompletionResponse(
                text=text,
                model=model_name,
                provider="llm",
                tokens_used=tokens,
                metadata={
                    'image_path': image_path,
                    'input_tokens': getattr(response, 'input_tokens', None),
                    'output_tokens': getattr(response, 'output_tokens', None),
                    'request_id': request_id,
                    'duration_seconds': duration,
                }
            )

        except self._llm.UnknownModelError as e:
            logger.error(f"Unknown model error: {model_name}")
            log_llm_response(request_id=request_id, response_text="", error=str(e))
            raise ModelNotFoundError(
                f"Model not found: {model_name}. "
                f"For vision tasks, install llm-gemini: llm install llm-gemini"
            ) from e
        except Exception as e:
            duration = time.time() - start_time
            log_llm_response(request_id=request_id, response_text="", error=str(e), duration_seconds=duration)
            # Check for rate limit errors
            if 'rate' in str(e).lower() or '429' in str(e):
                logger.error(f"Rate limit error: {e}")
                raise RateLimitError(f"Rate limit exceeded: {e}") from e
            logger.error(f"Vision completion failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise LLMError(f"Vision completion failed: {e}") from e

    def list_models(self) -> list[str]:
        """List available models in LLM."""
        try:
            # Get all available models
            models = []

            # Try to get models from the LLM registry
            if hasattr(self._llm, 'get_models'):
                for model in self._llm.get_models():
                    # Newer llm versions use model_id, older use name
                    if hasattr(model, 'model_id'):
                        models.append(model.model_id)
                    elif hasattr(model, 'name'):
                        models.append(model.name)

            if not models:
                # Fallback: Try common model names
                common_models = [
                    'gpt-4',
                    'gpt-4o',
                    'gpt-3.5-turbo',
                    'gemini-3-pro-preview',
                    'gemini-2.5-pro',
                    'claude-3-opus',
                    'claude-3-sonnet',
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
            # Vision-capable models
            if any(v in model_lower for v in ['vision', 'gpt-4', 'gemini']):
                capabilities.add(ModelCapability.VISION)
            # Function calling and JSON mode capable models
            if any(v in model_lower for v in ['gpt', 'claude', 'gemini']):
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