"""Census transcription service orchestrating LLM-based census extraction.

This module provides the main service for transcribing census images using
vision LLMs, coordinating schema loading, prompt building, and response parsing.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from rmcitecraft.models.census_schema import CensusYearSchema
from rmcitecraft.services.census.data_validator import CensusDataValidator
from rmcitecraft.services.census.prompt_builder import CensusPromptBuilder
from rmcitecraft.services.census.response_parser import CensusResponseParser
from rmcitecraft.services.census.schema_registry import CensusSchemaRegistry


@dataclass
class TranscriptionResult:
    """Result of a census transcription operation.

    Attributes:
        success: Whether transcription succeeded
        data: Extracted census data as dictionary
        persons: List of extracted person records
        metadata: Extracted metadata (ED, sheet, page, etc.)
        warnings: List of validation warnings
        error: Error message if failed
        raw_response: Raw LLM response text
    """

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    persons: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    raw_response: str = ""


class CensusTranscriptionService:
    """Orchestrates census transcription using LLM vision models.

    This service coordinates:
    - Loading year-specific schemas from YAML
    - Building LLM prompts with targeting hints
    - Parsing LLM responses into structured data
    - Validating extracted data against schema

    Example:
        service = CensusTranscriptionService(provider=gemini_provider)
        result = await service.transcribe(
            image_path="/path/to/census.jpg",
            census_year=1940,
            target_names=["John Smith"],
        )
        if result.success:
            for person in result.persons:
                print(person["name"], person["age"])
    """

    def __init__(
        self,
        provider: Any | None = None,
        model: str | None = None,
    ):
        """Initialize transcription service.

        Args:
            provider: LLM provider with vision capabilities (e.g., Gemini)
            model: Specific model to use (optional)
        """
        self.provider = provider
        self.model = model
        self.prompt_builder = CensusPromptBuilder()
        self.response_parser = CensusResponseParser()
        self.validator = CensusDataValidator()

    def transcribe(
        self,
        image_path: str | Path,
        census_year: int,
        target_names: list[str] | None = None,
        target_line: int | None = None,
        sheet: str | None = None,
        enumeration_district: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe a census image.

        Args:
            image_path: Path to census image file
            census_year: Census year (1790-1950)
            target_names: Names to look for (helps LLM focus)
            target_line: Specific line number to find
            sheet: Expected sheet number
            enumeration_district: Expected ED number

        Returns:
            TranscriptionResult with extracted data or error
        """
        try:
            # Validate year and get schema
            schema = CensusSchemaRegistry.get_schema(census_year)

            # Build prompt
            prompt = self.prompt_builder.build_transcription_prompt(
                schema=schema,
                target_names=target_names,
                target_line=target_line,
                sheet=sheet,
                enumeration_district=enumeration_district,
            )

            # Call LLM
            if self.provider is None:
                return TranscriptionResult(
                    success=False,
                    error="No LLM provider configured",
                )

            response = self._call_llm(prompt, str(image_path))

            # Parse response
            data = self.response_parser.parse_response(response)
            persons = self.response_parser.extract_persons(data)
            metadata = self.response_parser.extract_metadata(data)

            # Validate
            warnings = self.validator.validate(
                {"metadata": metadata, "persons": persons},
                schema,
            )

            return TranscriptionResult(
                success=True,
                data=data,
                persons=persons,
                metadata=metadata,
                warnings=warnings,
                raw_response=response,
            )

        except FileNotFoundError as e:
            logger.error(f"Schema not found: {e}")
            return TranscriptionResult(
                success=False,
                error=f"Schema not found for year {census_year}: {e}",
            )
        except ValueError as e:
            logger.error(f"Transcription failed: {e}")
            return TranscriptionResult(
                success=False,
                error=str(e),
            )
        except Exception as e:
            logger.exception(f"Unexpected error during transcription: {e}")
            return TranscriptionResult(
                success=False,
                error=f"Transcription failed: {e}",
            )

    def _call_llm(self, prompt: str, image_path: str) -> str:
        """Call LLM with image and prompt.

        This method should be overridden or the provider should implement
        a compatible interface.

        Args:
            prompt: Text prompt
            image_path: Path to image file

        Returns:
            LLM response text
        """
        # Try different provider interfaces
        if hasattr(self.provider, "complete_with_image"):
            # Gemini-style provider
            response = self.provider.complete_with_image(
                prompt=prompt,
                image_path=image_path,
                model=self.model,
                temperature=0.2,
            )
            return response.text if hasattr(response, "text") else str(response)

        elif hasattr(self.provider, "transcribe_image"):
            # Generic vision provider
            return self.provider.transcribe_image(
                image_path=image_path,
                prompt=prompt,
            )

        else:
            raise ValueError(
                "Provider must implement 'complete_with_image' or 'transcribe_image'"
            )

    def extract_family(
        self,
        image_path: str | Path,
        census_year: int,
        target_names: list[str],
    ) -> TranscriptionResult:
        """Extract a complete family/household from census image.

        Optimized for finding a specific family and extracting all members.

        Args:
            image_path: Path to census image
            census_year: Census year
            target_names: Names of people in the family to find

        Returns:
            TranscriptionResult with family members
        """
        schema = CensusSchemaRegistry.get_schema(census_year)

        prompt = self.prompt_builder.build_family_extraction_prompt(
            schema=schema,
            target_names=target_names,
        )

        try:
            response = self._call_llm(prompt, str(image_path))
            data = self.response_parser.parse_response(response)
            persons = self.response_parser.extract_persons(data)
            metadata = self.response_parser.extract_metadata(data)

            # Validate household
            household_warnings = self.validator.validate_household(persons, schema)
            data_warnings = self.validator.validate(
                {"metadata": metadata, "persons": persons},
                schema,
            )

            return TranscriptionResult(
                success=True,
                data=data,
                persons=persons,
                metadata=metadata,
                warnings=household_warnings + data_warnings,
                raw_response=response,
            )

        except Exception as e:
            logger.exception(f"Family extraction failed: {e}")
            return TranscriptionResult(
                success=False,
                error=str(e),
            )

    def get_schema(self, year: int) -> CensusYearSchema:
        """Get schema for a census year.

        Convenience method for accessing schemas.

        Args:
            year: Census year

        Returns:
            CensusYearSchema for the year
        """
        return CensusSchemaRegistry.get_schema(year)

    @staticmethod
    def list_supported_years() -> list[int]:
        """List all supported census years.

        Returns:
            List of census years (1790-1950, excluding 1890)
        """
        return CensusSchemaRegistry.list_years()
