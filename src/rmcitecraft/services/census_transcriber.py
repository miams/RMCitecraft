"""
Census transcription service for extracting data from census images.

Handles US Federal Census records from 1790-1950, adapting to the
different formats and fields used in each census year.
"""

import os
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from rmcitecraft.llm import create_provider, ExtractionResponse, LLMProvider


class CensusTranscriber:
    """Service for transcribing and extracting census data."""

    # Census field schemas by year range
    CENSUS_SCHEMAS = {
        # 1790-1840: Head of household enumeration
        "1790-1840": {
            "head_of_household": "string",
            "free_white_males_under_10": "integer",
            "free_white_males_10_to_16": "integer",
            "free_white_males_16_to_26": "integer",
            "free_white_males_26_to_45": "integer",
            "free_white_males_over_45": "integer",
            "free_white_females_under_10": "integer",
            "free_white_females_10_to_16": "integer",
            "free_white_females_16_to_26": "integer",
            "free_white_females_26_to_45": "integer",
            "free_white_females_over_45": "integer",
            "other_free_persons": "integer",
            "slaves": "integer",
            "county": "string",
            "township": "string",
            "page": "string",
        },

        # 1850-1870: Individual enumeration begins
        "1850-1870": {
            "dwelling_number": "string",
            "family_number": "string",
            "name": "string",
            "age": "integer",
            "sex": "string (M/F)",
            "color": "string (W/B/M)",  # White/Black/Mulatto
            "occupation": "string",
            "value_real_estate": "integer",
            "value_personal_estate": "integer",  # Added 1860
            "birthplace": "string",
            "married_within_year": "boolean",
            "attended_school": "boolean",
            "cannot_read_write": "boolean",
            "county": "string",
            "township": "string",
            "post_office": "string",
            "page": "string",
        },

        # 1880-1890: Enumeration districts introduced
        "1880-1890": {
            "enumeration_district": "string",
            "dwelling_number": "string",
            "family_number": "string",
            "name": "string",
            "relationship_to_head": "string",
            "color": "string (W/B/Mu/Ch/In)",  # Added Chinese/Indian
            "sex": "string (M/F)",
            "age": "integer",
            "marital_status": "string",
            "married_within_year": "boolean",
            "occupation": "string",
            "months_unemployed": "integer",
            "attended_school": "boolean",
            "cannot_read": "boolean",
            "cannot_write": "boolean",
            "birthplace": "string",
            "father_birthplace": "string",
            "mother_birthplace": "string",
            "county": "string",
            "city_ward": "string",
            "street": "string",
            "house_number": "string",
            "page": "string",
        },

        # 1900: Birth month/year added
        "1900": {
            "sheet": "string",
            "enumeration_district": "string",
            "dwelling_number": "string",
            "family_number": "string",
            "name": "string",
            "relationship": "string",
            "color": "string",
            "sex": "string",
            "birth_month": "string",
            "birth_year": "integer",
            "age": "integer",
            "marital_status": "string",
            "years_married": "integer",
            "mother_children_born": "integer",
            "mother_children_living": "integer",
            "birthplace": "string",
            "father_birthplace": "string",
            "mother_birthplace": "string",
            "year_immigrated": "integer",
            "years_in_us": "integer",
            "naturalization": "string",
            "occupation": "string",
            "months_not_employed": "integer",
            "attended_school_months": "integer",
            "can_read": "boolean",
            "can_write": "boolean",
            "can_speak_english": "boolean",
            "home_owned_or_rented": "string",
            "home_owned_free": "boolean",
            "farm_or_house": "string",
            "county": "string",
            "city_ward": "string",
            "street": "string",
        },

        # 1910-1930: Similar to 1900 with variations
        "1910-1930": {
            "sheet": "string",
            "enumeration_district": "string",
            "dwelling_number": "string",
            "family_number": "string",
            "name": "string",
            "relationship": "string",
            "sex": "string",
            "race": "string",  # "Race" replaces "Color"
            "age": "integer",
            "marital_status": "string",
            "years_married": "integer",
            "birthplace": "string",
            "father_birthplace": "string",
            "mother_birthplace": "string",
            "year_immigrated": "integer",
            "naturalization": "string",
            "occupation": "string",
            "industry": "string",
            "employer_employee_own": "string",
            "home_owned_or_rented": "string",
            "home_owned_free": "boolean",
            "can_read": "boolean",
            "can_write": "boolean",
            "attended_school": "boolean",
            "can_speak_english": "boolean",
            "county": "string",
            "city_ward": "string",
            "street": "string",
        },

        # 1940-1950: Sampling lines added
        "1940-1950": {
            "sheet": "string",
            "enumeration_district": "string",
            "block": "string",  # Added in urban areas
            "dwelling_number": "string",
            "family_number": "string",
            "name": "string",
            "relationship": "string",
            "sex": "string",
            "race": "string",
            "age": "integer",
            "marital_status": "string",
            "attended_school": "boolean",
            "highest_grade": "string",
            "birthplace": "string",
            "citizenship": "string",
            "residence_1935_city": "string",  # 1940
            "residence_1935_county": "string",  # 1940
            "residence_1935_state": "string",  # 1940
            "residence_1949_county": "string",  # 1950
            "residence_1949_state": "string",  # 1950
            "occupation": "string",
            "industry": "string",
            "class_of_worker": "string",
            "weeks_worked_1939": "integer",  # 1940
            "income_1939": "integer",  # 1940
            "income_1949": "integer",  # 1950
            "county": "string",
            "city_ward": "string",
            "street": "string",
            "house_number": "string",
        },
    }

    def __init__(self, provider: Optional[LLMProvider] = None,
                 model: Optional[str] = None):
        """
        Initialize census transcriber.

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

        logger.info(f"Census transcriber initialized with {self.provider.name}")
        if self.model:
            logger.info(f"Using model: {self.model}")

    def _load_config(self) -> dict:
        """Load configuration from environment."""
        provider_type = os.getenv("DEFAULT_LLM_PROVIDER", "openrouter")

        config = {
            "provider": provider_type,
        }

        # Add provider-specific config
        if provider_type == "openrouter":
            config["openrouter_api_key"] = os.getenv("OPENROUTER_API_KEY")
            config["openrouter_site_url"] = os.getenv("OPENROUTER_SITE_URL")
            config["openrouter_app_name"] = os.getenv("OPENROUTER_APP_NAME", "RMCitecraft")

        return config

    def _get_schema_for_year(self, year: int) -> dict[str, Any]:
        """Get the appropriate schema for a census year."""
        if year <= 1840:
            return self.CENSUS_SCHEMAS["1790-1840"]
        elif year <= 1870:
            return self.CENSUS_SCHEMAS["1850-1870"]
        elif year <= 1890:
            return self.CENSUS_SCHEMAS["1880-1890"]
        elif year == 1900:
            return self.CENSUS_SCHEMAS["1900"]
        elif year <= 1930:
            return self.CENSUS_SCHEMAS["1910-1930"]
        else:
            return self.CENSUS_SCHEMAS["1940-1950"]

    def transcribe_census(self, image_path: str | Path,
                         census_year: int) -> ExtractionResponse:
        """
        Transcribe census image and extract structured data.

        Args:
            image_path: Path to census image
            census_year: Year of the census (1790-1950)

        Returns:
            ExtractionResponse with extracted census data

        Raises:
            FileNotFoundError: If image doesn't exist
            ValueError: If census year is invalid
            LLMError: If transcription fails
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        if census_year < 1790 or census_year > 1950 or census_year % 10 != 0:
            raise ValueError(
                f"Invalid census year: {census_year}. "
                "Must be 1790-1950 in 10-year increments."
            )

        logger.info(f"Transcribing {census_year} census: {image_path.name}")

        # Use provider's census transcription method if available
        try:
            response = self.provider.transcribe_census_image(
                str(image_path),
                census_year,
                model=self.model
            )

            logger.info(
                f"Transcribed with confidence {response.confidence:.2%}"
            )

            return response

        except NotImplementedError:
            # Provider doesn't have native census support
            # Use manual extraction
            logger.warning(
                f"{self.provider.name} doesn't have native census transcription. "
                "Using manual extraction."
            )
            return self._transcribe_with_schema(image_path, census_year)

    def _transcribe_with_schema(self, image_path: Path,
                                census_year: int) -> ExtractionResponse:
        """
        Transcribe using schema-based extraction.

        Args:
            image_path: Path to census image
            census_year: Year of the census

        Returns:
            ExtractionResponse
        """
        schema = self._get_schema_for_year(census_year)

        # Build detailed prompt
        prompt = self._build_transcription_prompt(census_year, schema)

        response = self.provider.complete_with_image(
            prompt,
            str(image_path),
            model=self.model,
            temperature=0.2  # Very low temperature for accuracy
        )

        # Parse response
        import json
        try:
            data = json.loads(response.text)
            confidence = data.pop("confidence", 0.7)

            # Clean up data (remove null/empty values)
            cleaned_data = {
                k: v for k, v in data.items()
                if v is not None and v != ""
            }

            return ExtractionResponse(
                data=cleaned_data,
                confidence=confidence,
                metadata={
                    "census_year": census_year,
                    "raw_response": response.text
                }
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse transcription response: {e}")
            raise

    def _build_transcription_prompt(self, year: int,
                                   schema: dict[str, str]) -> str:
        """Build detailed transcription prompt for census year."""
        import json

        # Year-specific instructions
        year_instructions = self._get_year_instructions(year)

        prompt = f"""You are transcribing a {year} United States Federal Census image.

{year_instructions}

Extract ALL visible information for EACH person/household listed. Fields to extract:

{json.dumps(schema, indent=2)}

CRITICAL INSTRUCTIONS:
1. Transcribe names EXACTLY as written (including spelling variations)
2. Use standard abbreviations: Wm for William, Jno for John, etc.
3. For age: Use the exact number shown (including fractions like 3/12 for 3 months)
4. For birthplace: Use standard state abbreviations (Pa., N.Y., Va., etc.)
5. For occupation: Transcribe exactly (including "ditto" marks as previous entry)
6. For illegible text: Use [?] for uncertain characters, [illegible] for completely unreadable
7. Include line numbers or dwelling/family numbers to maintain record relationships

Respond with a JSON object containing:
{{
    "confidence": 0.0-1.0,
    "records": [
        {{ extracted data for person/household 1 }},
        {{ extracted data for person/household 2 }},
        ...
    ],
    "page_info": {{
        "page": "page number",
        "enumeration_district": "ED if applicable",
        "county": "county name",
        "township": "township/city",
        "enumerator": "enumerator name if visible",
        "enumeration_date": "date if visible"
    }}
}}

Focus on accuracy over speed. Double-check names and ages especially."""

        return prompt

    def _get_year_instructions(self, year: int) -> str:
        """Get year-specific transcription instructions."""
        if year <= 1840:
            return """This census only lists heads of household by name.
Other household members are counted in age/sex/race categories.
Pay attention to tick marks and tallies in the columns."""

        elif year <= 1870:
            return """This census lists all individuals by name.
Note dwelling and family numbers to track household groups.
Watch for "ditto" marks (") in occupation and birthplace columns."""

        elif year <= 1890:
            return """This census includes enumeration districts (ED).
Relationship to head of household is now recorded.
Note street addresses in urban areas."""

        elif year == 1900:
            return """This census includes birth month and year.
Immigration year and naturalization status are important.
Note the number of years married and children born/living for women."""

        elif year <= 1930:
            return """Similar format to 1900 with additional employment details.
Note industry and class of worker for employed persons.
Home ownership and value are recorded."""

        else:  # 1940-1950
            return """This census includes sampling lines with additional questions.
Note the circled line numbers which indicate sampling.
1940 asks about 1935 residence; 1950 asks about 1949 residence.
Income information may be present for some individuals."""

    def extract_family_group(self, census_data: dict[str, Any],
                            head_name: str) -> list[dict[str, Any]]:
        """
        Extract a family group from census data.

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
            # Check if this is the head we're looking for
            if record.get("name") == head_name:
                in_family = True
                current_dwelling = record.get("dwelling_number")
                family.append(record)
            elif in_family:
                # Continue adding family members until dwelling changes
                if record.get("dwelling_number") == current_dwelling:
                    family.append(record)
                else:
                    break

        return family

    def validate_transcription(self, data: dict[str, Any],
                              census_year: int) -> list[str]:
        """
        Validate transcribed data for common issues.

        Args:
            data: Transcribed census data
            census_year: Year of census

        Returns:
            List of validation warnings
        """
        warnings = []
        records = data.get("records", [])

        for i, record in enumerate(records):
            # Check age validity
            age = record.get("age")
            if age is not None:
                if isinstance(age, int) and (age < 0 or age > 120):
                    warnings.append(
                        f"Record {i+1}: Unusual age {age}"
                    )

            # Check name presence
            if census_year >= 1850 and not record.get("name"):
                warnings.append(
                    f"Record {i+1}: Missing name for individual enumeration"
                )

            # Check relationships (1880+)
            if census_year >= 1880:
                rel = record.get("relationship_to_head") or record.get("relationship")
                if i == 0 and rel and rel.lower() != "head":
                    warnings.append(
                        f"Record 1: First person should be head of household"
                    )

            # Check birthplace format
            birthplace = record.get("birthplace")
            if birthplace and len(birthplace) > 50:
                warnings.append(
                    f"Record {i+1}: Unusually long birthplace '{birthplace}'"
                )

        return warnings