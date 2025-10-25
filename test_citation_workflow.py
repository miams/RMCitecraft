"""Test end-to-end citation processing workflow.

This script demonstrates the complete citation processing workflow:
1. Load citations from database
2. Parse with regex parser (Week 1)
3. Format with Evidence Explained templates (Week 1)
4. Optional: Extract with LLM (Week 2, if API keys available)
"""

import asyncio

from loguru import logger

from rmcitecraft.parsers.citation_formatter import CitationFormatter
from rmcitecraft.parsers.familysearch_parser import FamilySearchParser
from rmcitecraft.repositories import CitationRepository, DatabaseConnection
from rmcitecraft.services.citation_extractor import CitationExtractor

logger.add("logs/test_workflow.log", rotation="1 MB")


async def test_regex_parser_workflow() -> None:
    """Test citation workflow using regex parser (Week 1)."""
    print("=" * 80)
    print("Testing Citation Workflow - Regex Parser (Week 1)")
    print("=" * 80)

    # 1. Connect to database
    print("\n1. Connecting to database...")
    db = DatabaseConnection()
    if not db.test_connection():
        print("   ✗ Database connection failed")
        return
    print("   ✓ Database connected")

    # 2. Load citations
    print("\n2. Loading citations from database...")
    repo = CitationRepository(db)
    citations_1900 = repo.get_citations_by_year(1900)
    print(f"   ✓ Found {len(citations_1900)} citations for 1900")

    if not citations_1900:
        print("   ✗ No citations found")
        db.close()
        return

    # 3. Parse first citation
    print("\n3. Parsing citation with regex parser...")
    citation_row = citations_1900[0]
    parser = FamilySearchParser()

    parsed = parser.parse(
        citation_row["SourceName"],
        citation_row["ActualText"],
        citation_id=citation_row["CitationID"],
    )

    print(f"   Citation ID: {parsed.citation_id}")
    print(f"   Person: {parsed.person_name}")
    print(f"   Location: {parsed.census_year} {parsed.state}, {parsed.county}")
    print(f"   Details: Sheet {parsed.sheet}, Family {parsed.family_number}")
    print(f"   Missing fields: {parsed.missing_fields}")
    print(f"   ✓ Parsed successfully")

    # 4. Format citation
    print("\n4. Formatting citation to Evidence Explained...")
    formatter = CitationFormatter()
    footnote, short_footnote, bibliography = formatter.format(parsed)

    print("\n   --- FOOTNOTE ---")
    print(f"   {footnote}")
    print("\n   --- SHORT FOOTNOTE ---")
    print(f"   {short_footnote}")
    print("\n   --- BIBLIOGRAPHY ---")
    print(f"   {bibliography}")
    print("\n   ✓ Formatted successfully")

    # 5. Compare with existing (if any)
    print("\n5. Comparing with existing database values...")
    has_existing = bool(citation_row["Footnote"])
    if has_existing:
        print("   Existing footnote found (not showing - likely placeholder)")
    else:
        print("   No existing footnote (placeholder citation)")
    print("   ✓ New formatted citation ready for database update")

    db.close()
    print("\n" + "=" * 80)
    print("✓ Regex parser workflow complete")
    print("=" * 80)


async def test_llm_extractor_workflow() -> None:
    """Test citation workflow using LLM extractor (Week 2)."""
    print("\n" + "=" * 80)
    print("Testing Citation Workflow - LLM Extractor (Week 2)")
    print("=" * 80)

    # 1. Check if LLM is available
    print("\n1. Checking LLM availability...")
    extractor = CitationExtractor()
    if not extractor.is_available():
        print("   ⚠ No LLM provider available (API keys not set)")
        print("   ℹ Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env to test LLM extraction")
        return
    print(f"   ✓ LLM provider available: {extractor.provider.name}")

    # 2. Connect to database
    print("\n2. Connecting to database...")
    db = DatabaseConnection()
    repo = CitationRepository(db)
    citations_1900 = repo.get_citations_by_year(1900)
    print(f"   ✓ Found {len(citations_1900)} citations for 1900")

    if not citations_1900:
        db.close()
        return

    # 3. Extract with LLM
    print("\n3. Extracting citation with LLM...")
    citation_row = citations_1900[0]

    extraction = await extractor.extract_citation(
        citation_row["SourceName"], citation_row["ActualText"]
    )

    if not extraction:
        print("   ✗ LLM extraction failed")
        db.close()
        return

    print(f"   Year: {extraction.year}")
    print(f"   State: {extraction.state}")
    print(f"   County: {extraction.county}")
    print(f"   Person: {extraction.person_name}")
    print(f"   Town/Ward: {extraction.town_ward}")
    print(f"   ED: {extraction.enumeration_district}")
    print(f"   Sheet: {extraction.sheet}")
    print(f"   Family: {extraction.family_number}")
    print(f"   Missing fields: {extraction.missing_fields}")
    print(f"   ✓ LLM extraction successful")

    # 4. Show confidence scores
    print("\n4. LLM confidence scores:")
    for field, confidence in extraction.confidence.items():
        status = "✓" if confidence >= 0.9 else "⚠" if confidence >= 0.8 else "✗"
        print(f"   {status} {field}: {confidence:.2f}")

    db.close()
    print("\n" + "=" * 80)
    print("✓ LLM extractor workflow complete")
    print("=" * 80)


async def test_batch_processing() -> None:
    """Test batch processing of multiple citations."""
    print("\n" + "=" * 80)
    print("Testing Batch Processing")
    print("=" * 80)

    # 1. Connect to database
    print("\n1. Connecting to database...")
    db = DatabaseConnection()
    repo = CitationRepository(db)

    # 2. Load first 5 citations
    print("\n2. Loading citations...")
    citations_1900 = repo.get_citations_by_year(1900)[:5]
    print(f"   ✓ Loaded {len(citations_1900)} citations for testing")

    # 3. Batch parse with regex parser
    print("\n3. Batch parsing with regex parser...")
    parser = FamilySearchParser()
    parsed_citations = []

    for citation_row in citations_1900:
        parsed = parser.parse(
            citation_row["SourceName"],
            citation_row["ActualText"],
            citation_id=citation_row["CitationID"],
        )
        parsed_citations.append(parsed)

    print(f"   ✓ Parsed {len(parsed_citations)} citations")

    # 4. Batch format
    print("\n4. Batch formatting...")
    formatter = CitationFormatter()
    formatted_count = 0

    for parsed in parsed_citations:
        footnote, short_footnote, bibliography = formatter.format(parsed)
        if footnote:
            formatted_count += 1

    print(f"   ✓ Formatted {formatted_count} citations")

    # 5. Summary
    print("\n5. Summary:")
    complete_count = sum(1 for p in parsed_citations if p.is_complete)
    incomplete_count = len(parsed_citations) - complete_count
    print(f"   Complete citations: {complete_count}")
    print(f"   Citations needing user input: {incomplete_count}")

    if incomplete_count > 0:
        print("\n   Missing fields by citation:")
        for parsed in parsed_citations:
            if not parsed.is_complete:
                print(
                    f"   - Citation {parsed.citation_id}: missing {parsed.missing_fields}"
                )

    db.close()
    print("\n" + "=" * 80)
    print("✓ Batch processing complete")
    print("=" * 80)


async def main() -> None:
    """Run all workflow tests."""
    # Test 1: Regex parser workflow (always available)
    await test_regex_parser_workflow()

    # Test 2: LLM extractor workflow (only if API keys available)
    await test_llm_extractor_workflow()

    # Test 3: Batch processing
    await test_batch_processing()

    print("\n" + "=" * 80)
    print("All workflow tests complete!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
