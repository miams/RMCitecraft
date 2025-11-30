"""Census transcription service for extracting data from census images.

This module provides a facade over the refactored CensusTranscriptionService,
maintaining backward compatibility while using the new schema-based architecture.

For new code, consider using CensusTranscriptionService directly from
rmcitecraft.services.census.transcription_service.
"""

import os
from pathlib import Path
from typing import Any

from loguru import logger

from rmcitecraft.llm import ExtractionResponse, LLMProvider, create_provider
from rmcitecraft.services.census.data_validator import CensusDataValidator
from rmcitecraft.services.census.prompt_builder import CensusPromptBuilder
from rmcitecraft.services.census.response_parser import CensusResponseParser
from rmcitecraft.services.census.schema_registry import CensusSchemaRegistry
from rmcitecraft.services.census.transcription_service import (
    CensusTranscriptionService,
    TranscriptionResult,
)


class CensusTranscriber:
    """Service for transcribing and extracting census data.

    This class provides backward compatibility with the original API while
    delegating to the new schema-based CensusTranscriptionService.

    For new code, consider using CensusTranscriptionService directly:

        from rmcitecraft.services.census import CensusTranscriptionService

        service = CensusTranscriptionService(provider=my_provider)
        result = service.transcribe(image_path, census_year=1940)

    The original CENSUS_SCHEMAS class attribute is maintained for backward
    compatibility but is no longer used internally - schemas are now loaded
    from YAML files via CensusSchemaRegistry.
    """

    # Maintained for backward compatibility - not used internally
    CENSUS_SCHEMAS: dict[str, dict[str, str]] = {}

    def __init__(
        self,
        provider: LLMProvider | None = None,
        model: str | None = None,
    ):
        """Initialize census transcriber.

        Args:
            provider: LLM provider to use (or create from config)
            model: Model to use for transcription
        """
        if provider:
            self.provider = provider
        else:
            # Create from environment config
            config = self._load_config()
            self.provider = create_provider(config)

        # Use configured model or provider default
        self.model = model or os.getenv("CENSUS_TRANSCRIPTION_MODEL")

        # Initialize the new service with direct provider access
        self._prompt_builder = CensusPromptBuilder()
        self._response_parser = CensusResponseParser()
        self._validator = CensusDataValidator()

        logger.info(f"Census transcriber initialized with {self.provider.name}")
        if self.model:
            logger.info(f"Using model: {self.model}")

    def _load_config(self) -> dict:
        """Load configuration from environment."""
        provider_type = os.getenv("DEFAULT_LLM_PROVIDER", "llm")

        config = {
            "provider": provider_type,
        }

        if provider_type == "openrouter":
            config["openrouter_api_key"] = os.getenv("OPENROUTER_API_KEY")
            config["openrouter_site_url"] = os.getenv("OPENROUTER_SITE_URL")
            config["openrouter_app_name"] = os.getenv(
                "OPENROUTER_APP_NAME", "RMCitecraft"
            )

        return config

    def _get_schema_for_year(self, year: int) -> Any:
        """Get the schema for a census year.

        Now delegates to CensusSchemaRegistry for YAML-based schemas.
        """
        return CensusSchemaRegistry.get_schema(year)

    def transcribe_census(
        self,
        image_path: str | Path,
        census_year: int,
        target_names: list[str] | None = None,
        target_line: int | None = None,
        sheet: str | None = None,
        enumeration_district: str | None = None,
    ) -> ExtractionResponse:
        """Transcribe census image and extract structured data.

        Args:
            image_path: Path to census image
            census_year: Year of the census (1790-1950)
            target_names: Names of people to find (helps focus extraction)
            target_line: Known line number from footnote
            sheet: Sheet identifier from footnote (e.g., "9A")
            enumeration_district: ED from footnote (e.g., "93-76")

        Returns:
            ExtractionResponse with extracted census data

        Raises:
            FileNotFoundError: If image doesn't exist
            ValueError: If census year is invalid
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Validate year using the registry
        if not CensusSchemaRegistry.is_valid_year(census_year):
            raise ValueError(
                f"Invalid census year: {census_year}. "
                f"Valid years are: {CensusSchemaRegistry.list_years()}"
            )

        logger.info(f"Transcribing {census_year} census: {image_path.name}")
        if target_names:
            logger.info(f"Target names: {target_names}")
        if target_line:
            logger.info(f"Target line: {target_line}, sheet: {sheet}")

        # Use the new schema-based approach
        return self._transcribe_with_yaml_schema(
            image_path,
            census_year,
            target_names=target_names,
            target_line=target_line,
            sheet=sheet,
            enumeration_district=enumeration_district,
        )

    def _transcribe_with_yaml_schema(
        self,
        image_path: Path,
        census_year: int,
        target_names: list[str] | None = None,
        target_line: int | None = None,
        sheet: str | None = None,
        enumeration_district: str | None = None,
    ) -> ExtractionResponse:
        """Transcribe using YAML schema-based extraction."""
        try:
            # Get schema from YAML
            logger.info(f"Loading YAML schema for {census_year}")
            schema = CensusSchemaRegistry.get_schema(census_year)
            logger.info(f"Schema loaded: {schema.year}, era={schema.era}")

            # Build prompt using the new builder
            logger.info("Building transcription prompt...")
            prompt = self._prompt_builder.build_transcription_prompt(
                schema=schema,
                target_names=target_names,
                target_line=target_line,
                sheet=sheet,
                enumeration_district=enumeration_district,
            )
            logger.info(f"Prompt built, length={len(prompt)} chars")

            # Call LLM
            logger.info(f"Calling LLM provider: {self.provider.name}, model={self.model}")
            logger.info(f"Image path: {image_path}")
            response = self.provider.complete_with_image(
                prompt,
                str(image_path),
                model=self.model,
                temperature=0.2,
            )
            logger.info(f"LLM response received, length={len(response.text)} chars")

            # Parse response
            data = self._response_parser.parse_response(response.text)
            persons = self._response_parser.extract_persons(data)
            metadata = self._response_parser.extract_metadata(data)

            # Validate
            warnings = self._validator.validate(
                {"metadata": metadata, "persons": persons},
                schema,
            )

            if warnings:
                logger.warning(f"Validation warnings: {warnings}")

            # Extract confidence if present
            confidence = data.pop("confidence", 0.7)

            # Build response in original format
            return ExtractionResponse(
                data={
                    "page_info": metadata,
                    "records": persons,
                },
                confidence=confidence,
                metadata={
                    "census_year": census_year,
                    "target_names": target_names,
                    "target_line": target_line,
                    "raw_response": response.text,
                    "warnings": warnings,
                },
            )

        except FileNotFoundError:
            logger.warning(
                f"YAML schema not found for {census_year}, falling back to legacy"
            )
            return self._transcribe_with_legacy_schema(
                image_path,
                census_year,
                target_names,
                target_line,
                sheet,
                enumeration_district,
            )

    def _transcribe_with_legacy_schema(
        self,
        image_path: Path,
        census_year: int,
        target_names: list[str] | None = None,
        target_line: int | None = None,
        sheet: str | None = None,
        enumeration_district: str | None = None,
    ) -> ExtractionResponse:
        """Fallback to legacy schema-based extraction.

        This method is maintained for cases where YAML schemas aren't available.
        """
        import json
        import re

        # Legacy schemas (simplified version for fallback)
        legacy_schemas = {
            "1940": {
                "sheet": "string",
                "enumeration_district": "string",
                "line_number": "integer",
                "name": "string",
                "relationship": "string",
                "sex": "string",
                "race": "string",
                "age": "integer",
                "marital_status": "string",
                "birthplace": "string",
                "occupation": "string",
            },
            "default": {
                "name": "string",
                "age": "integer",
                "sex": "string",
                "birthplace": "string",
                "occupation": "string",
            },
        }

        schema = legacy_schemas.get(str(census_year), legacy_schemas["default"])

        prompt = self._build_legacy_prompt(
            census_year, schema, target_names, target_line, sheet, enumeration_district
        )

        response = self.provider.complete_with_image(
            prompt,
            str(image_path),
            model=self.model,
            temperature=0.2,
        )

        text = response.text.strip()

        # Parse JSON from response
        json_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
        if json_match:
            text = json_match.group(1).strip()
        else:
            obj_start = text.find("{")
            if obj_start != -1:
                text = text[obj_start:]

        try:
            data = json.loads(text)
            confidence = data.pop("confidence", 0.7)

            return ExtractionResponse(
                data=data,
                confidence=confidence,
                metadata={
                    "census_year": census_year,
                    "target_names": target_names,
                    "raw_response": response.text,
                    "used_legacy_schema": True,
                },
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse transcription response: {e}")
            raise

    def _build_legacy_prompt(
        self,
        year: int,
        schema: dict[str, str],
        target_names: list[str] | None = None,
        target_line: int | None = None,
        sheet: str | None = None,
        enumeration_district: str | None = None,
    ) -> str:
        """Build legacy prompt for fallback."""
        import json

        targeting = ""
        if target_names or target_line:
            targeting = "\n\nFocus on household containing: "
            if target_names:
                targeting += ", ".join(target_names)
            if target_line:
                targeting += f" (line {target_line})"

        return f"""Transcribe this {year} US Federal Census image.
{targeting}

Extract these fields:
{json.dumps(schema, indent=2)}

Return ONLY valid JSON with "records" array containing extracted persons."""

    def extract_family_group(
        self, census_data: dict[str, Any], head_name: str
    ) -> list[dict[str, Any]]:
        """Extract a family group from census data.

        Args:
            census_data: Complete census transcription data
            head_name: Name of head of household

        Returns:
            List of family member records
        """
        records = census_data.get("records", [])
        family = []
        in_family = False
        current_dwelling = None

        for record in records:
            if record.get("name") == head_name:
                in_family = True
                current_dwelling = record.get("dwelling_number")
                family.append(record)
            elif in_family:
                if record.get("dwelling_number") == current_dwelling:
                    family.append(record)
                else:
                    break

        return family

    def validate_transcription(
        self, data: dict[str, Any], census_year: int
    ) -> list[str]:
        """Validate transcribed data for common issues.

        Args:
            data: Transcribed census data
            census_year: Year of census

        Returns:
            List of validation warnings
        """
        try:
            schema = CensusSchemaRegistry.get_schema(census_year)
            records = data.get("records", [])

            return self._validator.validate(
                {
                    "metadata": data.get("page_info", {}),
                    "persons": records,
                },
                schema,
            )
        except FileNotFoundError:
            # Fallback to legacy validation
            return self._legacy_validate(data, census_year)

    def _legacy_validate(
        self, data: dict[str, Any], census_year: int
    ) -> list[str]:
        """Legacy validation for backward compatibility."""
        warnings = []
        records = data.get("records", [])

        for i, record in enumerate(records):
            age = record.get("age")
            if age is not None and isinstance(age, int):
                if age < 0 or age > 120:
                    warnings.append(f"Record {i+1}: Unusual age {age}")

            if census_year >= 1850 and not record.get("name"):
                warnings.append(f"Record {i+1}: Missing name")

            if census_year >= 1880:
                rel = record.get("relationship_to_head") or record.get("relationship")
                if i == 0 and rel and rel.lower() != "head":
                    warnings.append("Record 1: First person should be head")

        return warnings

    @staticmethod
    def list_supported_years() -> list[int]:
        """List all supported census years.

        Returns:
            List of valid census years (1790-1950, excluding 1890)
        """
        return CensusSchemaRegistry.list_years()
