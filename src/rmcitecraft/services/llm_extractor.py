"""LLM-based citation extraction service.

This module uses LLM with structured output (Pydantic) to extract citation
components from FamilySearch citation text, handling format variations across
census years.
"""

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from loguru import logger

from rmcitecraft.models.census_citation import CensusExtraction

# System instructions (cached for all requests)
SYSTEM_INSTRUCTIONS = """You are a genealogical citation parser specialized in US Federal Census records from FamilySearch.

Your task is to extract structured data from FamilySearch census citations and convert them into a standardized format.

CRITICAL RULES:
1. Extract ALL available fields from the citation text
2. For missing REQUIRED fields, add them to the missing_fields array
3. Preserve exact formatting (e.g., "13A" should become "13-A" with hyphen)
4. Strip query parameters from URLs (e.g., remove "?lang=en")
5. Use "D Month YYYY" format for access dates (e.g., "7 November 2020")
6. Census years are every 10 years: 1790, 1800, ..., 1950
7. Extract county and state names WITHOUT suffixes ("Greene" not "Greene County")
8. Parse locality and type separately ("Jefferson Township" → locality="Jefferson", type="Township")

REQUIRED FIELDS BY CENSUS YEAR:
- 1790-1840: year, state, county, person_name, familysearch_url, access_date
- 1850-1880: + sheet, dwelling_number, family_number
- 1900-1950: + enumeration_district, sheet, line (family_number optional)

If you cannot extract a required field, add its name to missing_fields array.
"""

# Few-shot examples (cached)
FEW_SHOT_EXAMPLES = """
EXAMPLE 1 (1900 Census):
Source Name: Fed Census: 1900, Ohio, Noble [citing sheet 3B, family 57] Ijams, Ella
FamilySearch Entry: "United States Census, 1900," database with images, FamilySearch (https://familysearch.org/ark:/61903/1:1:MM6X-FGZ : accessed 24 July 2015), Ella Ijams, Olive Township Caldwell village, Noble, Ohio, United States; citing sheet 3B, family 57, NARA microfilm publication T623 (Washington, D.C.: National Archives and Records Administration, n.d.); FHL microfilm 1,241,311.

Expected Output:
{
  "year": 1900,
  "state": "Ohio",
  "county": "Noble",
  "locality": "Olive",
  "locality_type": "Township",
  "enumeration_district": null,
  "sheet": "3-B",
  "line": null,
  "family_number": "57",
  "dwelling_number": null,
  "person_name": "Ella Ijams",
  "familysearch_url": "https://familysearch.org/ark:/61903/1:1:MM6X-FGZ",
  "access_date": "24 July 2015",
  "nara_publication": "T623",
  "fhl_microfilm": "1,241,311",
  "missing_fields": ["enumeration_district", "line"]
}

EXAMPLE 2 (1930 Census):
Source Name: Fed Census: 1930, Pennsylvania, Greene [citing enumeration district (ED) ED 17, sheet 13A, line 15] Iams, George B.
FamilySearch Entry: "United States Census, 1930," database with images, FamilySearch (https://familysearch.org/ark:/61903/1:1:XH3Z-4J8 : accessed 7 November 2020), George B Iams, Jefferson, Greene, Pennsylvania, United States; citing enumeration district (ED) ED 17, sheet 13A, line 15, family 281, NARA microfilm publication T626 (Washington D.C.: National Archives and Records Administration, 2002), roll 2044; FHL microfilm 2,341,778.

Expected Output:
{
  "year": 1930,
  "state": "Pennsylvania",
  "county": "Greene",
  "locality": "Jefferson",
  "locality_type": null,
  "enumeration_district": "17",
  "sheet": "13-A",
  "line": "15",
  "family_number": "281",
  "dwelling_number": null,
  "person_name": "George B Iams",
  "familysearch_url": "https://familysearch.org/ark:/61903/1:1:XH3Z-4J8",
  "access_date": "7 November 2020",
  "nara_publication": "T626",
  "fhl_microfilm": "2,341,778",
  "missing_fields": []
}

NOTE: In Example 2, the ED "ED 17" is incomplete. The full ED is "30-17" but the citation only shows "17".
The extractor should extract "17" and flag that the ED may be incomplete (but don't add to missing_fields since it was present).
"""


def create_llm_client(provider: str, model: str, api_key: str | None = None) -> Any:
    """Create LLM client based on provider.

    Args:
        provider: "anthropic" or "openai"
        model: Model name (e.g., "claude-3-5-sonnet-20250110")
        api_key: API key (optional if set in environment)

    Returns:
        LLM client instance

    Raises:
        ValueError: If provider is not supported
    """
    if provider == "anthropic":
        return ChatAnthropic(
            model=model,
            anthropic_api_key=api_key,
            temperature=0.2,  # Low temperature for consistent extraction
            max_tokens=1024,
        )
    elif provider == "openai":
        return ChatOpenAI(
            model=model,
            openai_api_key=api_key,
            temperature=0.2,
            max_tokens=1024,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


class LLMCitationExtractor:
    """Extract structured citation data from FamilySearch citations using LLM."""

    def __init__(
        self,
        provider: str = "anthropic",
        model: str = "claude-3-5-sonnet-20250110",
        api_key: str | None = None,
    ):
        """Initialize extractor with LLM provider.

        Args:
            provider: LLM provider ("anthropic" or "openai")
            model: Model name
            api_key: API key (optional if in environment)
        """
        self.llm = create_llm_client(provider, model, api_key)
        self.parser = PydanticOutputParser(pydantic_object=CensusExtraction)
        self.prompt = self._build_prompt()

    def _build_prompt(self) -> ChatPromptTemplate:
        """Build prompt template with cached context.

        The system instructions and examples are cached, only the citation
        text changes per request.
        """
        return ChatPromptTemplate.from_messages([
            ("system", SYSTEM_INSTRUCTIONS + "\n\n" + FEW_SHOT_EXAMPLES),
            ("human", """Extract citation data from the following:

Source Name: {source_name}
FamilySearch Entry: {familysearch_entry}

{format_instructions}

Return ONLY the JSON object, no additional text."""),
        ])

    def extract_citation(
        self,
        source_name: str,
        familysearch_entry: str,
    ) -> CensusExtraction:
        """Extract structured citation data from FamilySearch citation text.

        Args:
            source_name: RM Source Name from SourceTable.Name
            familysearch_entry: FamilySearch citation from CitationTable.Fields BLOB "Page" field

        Returns:
            CensusExtraction model with structured data and missing_fields array

        Raises:
            ValueError: If LLM output cannot be parsed or validated
        """
        logger.debug(f"Extracting citation: {source_name[:50]}...")

        # Build prompt with format instructions
        chain = self.prompt | self.llm | self.parser

        try:
            extraction = chain.invoke({
                "source_name": source_name,
                "familysearch_entry": familysearch_entry,
                "format_instructions": self.parser.get_format_instructions(),
            })

            logger.info(
                f"Extracted {extraction.year} census for {extraction.person_name} "
                f"in {extraction.county}, {extraction.state}"
            )

            if extraction.missing_fields:
                logger.warning(
                    f"Missing required fields: {', '.join(extraction.missing_fields)}"
                )

            return extraction

        except Exception as e:
            logger.error(f"Failed to extract citation: {e}")
            raise ValueError(f"Citation extraction failed: {e}") from e


async def extract_citation_async(
    source_name: str,
    familysearch_entry: str,
    provider: str = "anthropic",
    model: str = "claude-3-5-sonnet-20250110",
    api_key: str | None = None,
) -> CensusExtraction:
    """Async version of citation extraction (for batch processing).

    Args:
        source_name: RM Source Name
        familysearch_entry: FamilySearch citation
        provider: LLM provider
        model: Model name
        api_key: API key (optional)

    Returns:
        CensusExtraction with structured data
    """
    extractor = LLMCitationExtractor(provider, model, api_key)
    return extractor.extract_citation(source_name, familysearch_entry)
