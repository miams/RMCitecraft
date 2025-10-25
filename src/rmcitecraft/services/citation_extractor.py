"""LLM-based citation extraction service.

Extracts structured citation data from FamilySearch entries using LLM.
"""

import asyncio
from typing import List, Optional

from langchain_core.output_parsers import PydanticOutputParser
from loguru import logger

from rmcitecraft.config import get_config
from rmcitecraft.models.citation import CitationExtraction
from rmcitecraft.services.citation_prompts import create_citation_extraction_prompt
from rmcitecraft.services.llm_provider import LLMProviderFactory


class CitationExtractor:
    """Extract citation data using LLM with structured output."""

    def __init__(self) -> None:
        """Initialize citation extractor."""
        self.config = get_config()
        self.provider = LLMProviderFactory.get_default_provider()

        if not self.provider:
            logger.warning("No LLM provider available - extractor will not work")
            self.chain = None
        else:
            # Create output parser for structured extraction
            self.parser = PydanticOutputParser(pydantic_object=CitationExtraction)

            # Create the prompt template
            self.prompt = create_citation_extraction_prompt()

            # Create the chain with structured output
            self.chain = LLMProviderFactory.create_chain_with_parser(
                self.provider, self.parser
            )

            logger.info(f"Citation extractor initialized with {self.provider.name}")

    async def extract_citation(
        self,
        source_name: str,
        familysearch_entry: str,
    ) -> Optional[CitationExtraction]:
        """Extract citation data from FamilySearch entry.

        Args:
            source_name: RM Source Name
            familysearch_entry: RM FamilySearch Entry

        Returns:
            CitationExtraction with extracted data or None if extraction fails
        """
        if not self.chain:
            logger.error("No LLM chain available - cannot extract citation")
            return None

        try:
            # Format the prompt with variables
            messages = self.prompt.format_messages(
                source_name=source_name,
                familysearch_entry=familysearch_entry,
            )

            # Invoke the chain
            logger.debug(f"Extracting citation from: {source_name[:50]}...")

            # If using structured output
            if hasattr(self.chain, 'invoke'):
                result = await self.chain.ainvoke(messages)
            else:
                # Fallback to model invocation
                model = self.provider.get_model()
                response = await model.ainvoke(messages)
                result = self.parser.parse(response.content)

            if isinstance(result, CitationExtraction):
                logger.info(
                    f"Extracted citation: {result.year} {result.state}, "
                    f"{result.county} - {result.person_name} "
                    f"(missing: {result.missing_fields})"
                )
                return result
            else:
                logger.warning(f"Unexpected result type: {type(result)}")
                return None

        except Exception as e:
            logger.error(f"Failed to extract citation: {e}", exc_info=True)
            return None

    async def extract_batch(
        self,
        citations: List[tuple[str, str]],
        max_concurrent: Optional[int] = None,
    ) -> List[Optional[CitationExtraction]]:
        """Extract multiple citations in parallel.

        Args:
            citations: List of (source_name, familysearch_entry) tuples
            max_concurrent: Maximum concurrent extractions (default from config)

        Returns:
            List of CitationExtraction results (None for failed extractions)
        """
        if max_concurrent is None:
            max_concurrent = self.config.batch_size

        logger.info(f"Extracting {len(citations)} citations (max concurrent: {max_concurrent})")

        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent)

        async def extract_with_semaphore(
            source_name: str, familysearch_entry: str
        ) -> Optional[CitationExtraction]:
            async with semaphore:
                return await self.extract_citation(source_name, familysearch_entry)

        # Process all citations in parallel (with concurrency limit)
        tasks = [
            extract_with_semaphore(source_name, familysearch_entry)
            for source_name, familysearch_entry in citations
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to None
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Citation {i+1} extraction failed: {result}")
                processed_results.append(None)
            else:
                processed_results.append(result)

        successful = sum(1 for r in processed_results if r is not None)
        logger.info(f"Batch extraction complete: {successful}/{len(citations)} successful")

        return processed_results

    def is_available(self) -> bool:
        """Check if extractor is available (has LLM provider).

        Returns:
            True if extractor can be used, False otherwise
        """
        return self.chain is not None


# Convenience function for single citation extraction
async def extract_citation_data(
    source_name: str,
    familysearch_entry: str,
) -> Optional[CitationExtraction]:
    """Extract citation data (convenience function).

    Args:
        source_name: RM Source Name
        familysearch_entry: RM FamilySearch Entry

    Returns:
        CitationExtraction or None if extraction fails
    """
    extractor = CitationExtractor()
    return await extractor.extract_citation(source_name, familysearch_entry)
