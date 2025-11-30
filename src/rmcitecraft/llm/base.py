"""
Base classes and interfaces for LLM providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional
from enum import Enum


# Custom exceptions
class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass


class ModelNotFoundError(LLMError):
    """Raised when a requested model is not available."""
    pass


class RateLimitError(LLMError):
    """Raised when rate limits are exceeded."""
    pass


class ConfigurationError(LLMError):
    """Raised when provider is misconfigured."""
    pass


# Response types
@dataclass
class CompletionResponse:
    """Response from an LLM completion request."""
    text: str
    model: str
    provider: str
    tokens_used: Optional[int] = None
    cost: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ClassificationResponse:
    """Response from a classification request."""
    category: str
    confidence: float
    reasoning: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResponse:
    """Response from a data extraction request."""
    data: dict[str, Any]
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelCapability(Enum):
    """Capabilities that models may support."""
    TEXT_COMPLETION = "text_completion"
    CHAT = "chat"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    STREAMING = "streaming"
    JSON_MODE = "json_mode"


# Base provider interface
class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> CompletionResponse:
        """
        Generate a text completion.

        Args:
            prompt: The input prompt
            model: Model to use (None for default)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Provider-specific parameters

        Returns:
            CompletionResponse with generated text

        Raises:
            ModelNotFoundError: If model doesn't exist
            RateLimitError: If rate limits exceeded
            LLMError: For other errors
        """
        pass

    @abstractmethod
    def stream_complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Iterator[str]:
        """
        Stream a text completion.

        Args:
            prompt: The input prompt
            model: Model to use (None for default)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Provider-specific parameters

        Yields:
            Text chunks as they're generated

        Raises:
            ModelNotFoundError: If model doesn't exist
            RateLimitError: If rate limits exceeded
            LLMError: For other errors
        """
        pass

    @abstractmethod
    def complete_with_image(
        self,
        prompt: str,
        image_path: str,
        model: Optional[str] = None,
        **kwargs
    ) -> CompletionResponse:
        """
        Generate completion with image input (for vision models).

        Args:
            prompt: The text prompt
            image_path: Path to image file
            model: Model to use (must support vision)
            **kwargs: Provider-specific parameters

        Returns:
            CompletionResponse with generated text

        Raises:
            NotImplementedError: If provider doesn't support vision
            ModelNotFoundError: If model doesn't exist
            LLMError: For other errors
        """
        raise NotImplementedError(f"{self.__class__.__name__} doesn't support vision")

    @abstractmethod
    def list_models(self) -> list[str]:
        """
        List available models.

        Returns:
            List of model identifiers
        """
        pass

    @abstractmethod
    def get_capabilities(self, model: Optional[str] = None) -> set[ModelCapability]:
        """
        Get capabilities of a model or provider.

        Args:
            model: Specific model to check (None for provider capabilities)

        Returns:
            Set of supported capabilities
        """
        pass

    def supports(self, capability: ModelCapability, model: Optional[str] = None) -> bool:
        """
        Check if a capability is supported.

        Args:
            capability: The capability to check
            model: Specific model to check (None for any model)

        Returns:
            True if capability is supported
        """
        return capability in self.get_capabilities(model)

    # High-level task methods
    def classify_image(
        self,
        image_path: str,
        categories: list[str],
        model: Optional[str] = None,
        **kwargs
    ) -> ClassificationResponse:
        """
        Classify an image into categories.

        Args:
            image_path: Path to image file
            categories: List of possible categories
            model: Model to use (must support vision)
            **kwargs: Provider-specific parameters

        Returns:
            ClassificationResponse with category and confidence

        Raises:
            NotImplementedError: If not supported
            LLMError: For other errors
        """
        if not self.supports(ModelCapability.VISION, model):
            raise NotImplementedError(f"Image classification not supported by {self.__class__.__name__}")

        # Default implementation using vision completion
        prompt = f"""Classify this image into one of these categories: {', '.join(categories)}

Respond in this exact JSON format:
{{
    "category": "chosen category",
    "confidence": 0.95,
    "reasoning": "brief explanation"
}}"""

        response = self.complete_with_image(prompt, image_path, model, **kwargs)

        # Parse JSON response
        import json
        try:
            data = json.loads(response.text)
            return ClassificationResponse(
                category=data['category'],
                confidence=data['confidence'],
                reasoning=data.get('reasoning'),
                metadata={'raw_response': response.text}
            )
        except (json.JSONDecodeError, KeyError) as e:
            raise LLMError(f"Failed to parse classification response: {e}")

    def extract_structured_data(
        self,
        text: str,
        schema: dict[str, Any],
        model: Optional[str] = None,
        **kwargs
    ) -> ExtractionResponse:
        """
        Extract structured data from text.

        Args:
            text: Input text to extract from
            schema: Expected data schema (as dict or JSON schema)
            model: Model to use
            **kwargs: Provider-specific parameters

        Returns:
            ExtractionResponse with extracted data

        Raises:
            LLMError: For extraction errors
        """
        import json

        # Build extraction prompt
        prompt = f"""Extract the following information from the text below.

Expected schema:
{json.dumps(schema, indent=2)}

Text to extract from:
{text}

Respond with valid JSON matching the schema. Include a "confidence" field (0.0-1.0) indicating extraction confidence."""

        response = self.complete(prompt, model, temperature=0.3, **kwargs)  # Lower temp for consistency

        try:
            data = json.loads(response.text)
            confidence = data.pop('confidence', 0.8)
            return ExtractionResponse(
                data=data,
                confidence=confidence,
                metadata={'raw_response': response.text}
            )
        except json.JSONDecodeError as e:
            raise LLMError(f"Failed to parse extraction response: {e}")

    def transcribe_census_image(
        self,
        image_path: str,
        census_year: int,
        model: Optional[str] = None,
        **kwargs
    ) -> ExtractionResponse:
        """
        Transcribe and extract data from census image.

        .. deprecated::
            Use CensusTranscriber or CensusTranscriptionService instead.
            These provide year-specific schemas loaded from YAML files with
            much better accuracy and maintainability.

            Example:
                from rmcitecraft.services.census_transcriber import CensusTranscriber

                transcriber = CensusTranscriber(provider=self)
                result = transcriber.transcribe_census(image_path, census_year)

        Args:
            image_path: Path to census image
            census_year: Year of census (affects expected fields)
            model: Model to use (must support vision)
            **kwargs: Provider-specific parameters

        Returns:
            ExtractionResponse with census data

        Raises:
            NotImplementedError: If not supported
            LLMError: For other errors
        """
        import warnings
        warnings.warn(
            "transcribe_census_image is deprecated. Use CensusTranscriber or "
            "CensusTranscriptionService for better accuracy with year-specific schemas.",
            DeprecationWarning,
            stacklevel=2
        )

        if not self.supports(ModelCapability.VISION, model):
            raise NotImplementedError("Census transcription requires vision support")

        # Use the new service internally for better results
        try:
            from rmcitecraft.services.census.prompt_builder import CensusPromptBuilder
            from rmcitecraft.services.census.response_parser import CensusResponseParser
            from rmcitecraft.services.census.schema_registry import CensusSchemaRegistry

            schema = CensusSchemaRegistry.get_schema(census_year)
            builder = CensusPromptBuilder()
            parser = CensusResponseParser()

            prompt = builder.build_transcription_prompt(schema)
            response = self.complete_with_image(prompt, image_path, model, **kwargs)

            data = parser.parse_response(response.text)
            persons = parser.extract_persons(data)
            metadata = parser.extract_metadata(data)
            confidence = data.pop("confidence", 0.7) if isinstance(data, dict) else 0.7

            return ExtractionResponse(
                data={"page_info": metadata, "records": persons},
                confidence=confidence,
                metadata={"census_year": census_year, "raw_response": response.text},
            )
        except (ImportError, FileNotFoundError):
            # Fallback to legacy behavior if new service not available
            pass

        # Legacy implementation (kept for backward compatibility)
        import json
        if census_year >= 1850 and census_year <= 1880:
            schema_dict = {
                "dwelling_number": "string",
                "family_number": "string",
                "name": "string",
                "age": "integer",
                "sex": "string",
                "race": "string",
                "occupation": "string",
                "birthplace": "string",
                "page": "string",
            }
        elif census_year >= 1900:
            schema_dict = {
                "sheet": "string",
                "enumeration_district": "string",
                "family_number": "string",
                "name": "string",
                "relationship": "string",
                "age": "integer",
                "birth_date": "string",
                "marital_status": "string",
                "occupation": "string",
                "birthplace": "string",
            }
        else:
            schema_dict = {
                "head_of_household": "string",
                "free_white_males": "object",
                "free_white_females": "object",
                "other_free_persons": "integer",
                "slaves": "integer",
                "page": "string",
            }

        prompt = f"""Transcribe this {census_year} US Federal Census image.

Extract the following information:
{json.dumps(schema_dict, indent=2)}

Provide the data in JSON format with a confidence score (0.0-1.0).
Focus on accurately transcribing names, ages, and locations."""

        response = self.complete_with_image(prompt, image_path, model, **kwargs)

        try:
            import re
            text = response.text.strip()

            json_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', text)
            if json_match:
                text = json_match.group(1).strip()
            else:
                obj_start = text.find('{')
                arr_start = text.find('[')

                if obj_start != -1 and (arr_start == -1 or obj_start < arr_start):
                    text = text[obj_start:]
                elif arr_start != -1:
                    text = text[arr_start:]

            data = json.loads(text)

            if isinstance(data, list):
                confidence = 0.7
                for record in data:
                    if isinstance(record, dict) and 'confidence' in record:
                        confidence = record.pop('confidence')
                        break
                data = {'records': data}
            else:
                confidence = data.pop('confidence', 0.7)

            return ExtractionResponse(
                data=data,
                confidence=confidence,
                metadata={
                    'census_year': census_year,
                    'raw_response': response.text
                }
            )
        except json.JSONDecodeError as e:
            raise LLMError(f"Failed to parse census transcription: {e}")

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for display."""
        pass

    @property
    def default_model(self) -> str:
        """Default model for this provider."""
        models = self.list_models()
        if models:
            return models[0]
        raise LLMError(f"No models available for {self.name}")