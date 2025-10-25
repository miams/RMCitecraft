# LLM Architecture for Citation Parsing

## Overview

RMCitecraft uses LLM-based citation parsing instead of traditional rule-based regex parsing to handle the high variability in FamilySearch citation formats. This document describes the architectural decisions, implementation patterns, and prompt engineering strategies.

## Architecture Decision: Why LLM?

### Traditional Parsing Challenges
FamilySearch citations have extreme format variability:

```
Example variations observed:
- ED formats: "ED 95", "enumeration district (ED) 214", "E.D. 95"
- Dates: "24 July 2015", "Fri Mar 08 08:10:13 UTC 2024"
- Names: "Ella Ijams" vs "William H Ijams in household of Margaret E Brannon"
- Locations: "Baltimore (Independent City)", "Olive Township Caldwell village"
```

**Traditional approach complexity:**
- 30-40 regex patterns needed
- 500-800 lines of parsing code
- 200-300 unit tests
- Brittle to format changes
- 2-3 weeks development time

**LLM approach benefits:**
- Handles variations naturally
- Robust to unexpected formats
- Faster development (3-5 days)
- Self-documenting prompts
- Easy to extend

## Two-Phase Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PHASE 1: EXTRACTION                      │
│                     (LLM-Powered)                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
         Input: RM Source Name + FamilySearch Entry
                              ↓
┌──────────────────────────────────────────────────────────────┐
│  LLM with Structured Output (Pydantic)                       │
│  - Cached: System prompt, examples, templates                │
│  - Variable: Citation text only                              │
│  - Output: CitationExtraction model                          │
│  - Missing fields detection                                  │
└──────────────────────────────────────────────────────────────┘
                              ↓
              CitationExtraction (Pydantic Model)
                missing_fields: ["enumeration_district"]
                              ↓
┌──────────────────────────────────────────────────────────────┐
│  User Review & Missing Data Entry                            │
│  - Side-by-side: App + FamilySearch page                     │
│  - User fills missing_fields array                           │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  PHASE 2: GENERATION                        │
│                 (Template-Based)                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
         Complete CitationExtraction (with user data)
                              ↓
┌──────────────────────────────────────────────────────────────┐
│  Template Selection & Rendering                              │
│  - Select template by census year                            │
│  - Apply deterministic formatting rules                      │
│  - Generate: Footnote, Short Footnote, Bibliography          │
└──────────────────────────────────────────────────────────────┘
                              ↓
              Evidence Explained Citations (Output)
```

## Data Models

### CitationExtraction (Pydantic)

```python
from pydantic import BaseModel, Field, validator, HttpUrl
from typing import Optional
from datetime import date

class CitationExtraction(BaseModel):
    """Structured output from LLM extraction"""

    # Required fields (always present)
    year: int = Field(
        ge=1790,
        le=1950,
        description="Census year (1790-1950, every 10 years)"
    )
    state: str = Field(
        min_length=2,
        description="US state or territory name"
    )
    county: str = Field(
        min_length=1,
        description="County name"
    )
    person_name: str = Field(
        description="Full name including prefixes/suffixes"
    )
    familysearch_url: HttpUrl = Field(
        description="FamilySearch ARK URL"
    )
    access_date: str = Field(
        description="Date citation was accessed"
    )

    # Optional fields (vary by census year)
    town_ward: Optional[str] = Field(
        None,
        description="Township, town, ward, or village"
    )
    enumeration_district: Optional[str] = Field(
        None,
        description="ED number (required for 1880-1950)"
    )
    sheet: Optional[str] = Field(
        None,
        description="Sheet or page number (e.g., '3B', '11A')"
    )
    family_number: Optional[str] = Field(
        None,
        description="Family number on census page"
    )
    dwelling_number: Optional[str] = Field(
        None,
        description="Dwelling number (1850-1880)"
    )
    nara_publication: Optional[str] = Field(
        None,
        description="NARA microfilm publication (e.g., 'T623')"
    )
    fhl_microfilm: Optional[str] = Field(
        None,
        description="FHL microfilm number"
    )

    # Metadata
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Array of required fields that couldn't be extracted"
    )
    confidence: dict[str, float] = Field(
        default_factory=dict,
        description="Per-field confidence scores (0.0-1.0)"
    )
    raw_extraction: Optional[str] = Field(
        None,
        description="Original LLM response for debugging"
    )

    @validator('year')
    def validate_census_year(cls, v):
        """Census years are every 10 years"""
        if v % 10 != 0:
            raise ValueError(f"Census year must be divisible by 10: {v}")
        return v

    @validator('enumeration_district')
    def normalize_ed(cls, v):
        """Normalize ED format: 'ED 95', 'E.D. 95' -> '95'"""
        if v is None:
            return v
        # Extract just the number
        import re
        match = re.search(r'\d+', v)
        return match.group(0) if match else v

    def get_required_fields_for_year(self) -> list[str]:
        """Return required fields based on census year"""
        base_required = ['year', 'state', 'county', 'person_name', 'familysearch_url']

        if 1790 <= self.year <= 1840:
            return base_required + ['town_ward', 'sheet']
        elif 1850 <= self.year <= 1870:
            return base_required + ['town_ward', 'sheet', 'dwelling_number']
        elif self.year == 1880:
            # ED is OPTIONAL for 1880 (first year introduced, not consistently used)
            return base_required + ['town_ward', 'sheet', 'family_number']
        elif self.year == 1890:
            # 1890 census not supported (most records destroyed)
            raise ValueError("1890 census is not currently supported")
        elif 1900 <= self.year <= 1950:
            return base_required + ['town_ward', 'enumeration_district', 'sheet', 'family_number']
        else:
            return base_required

    def validate_completeness(self) -> tuple[bool, list[str]]:
        """Check if all required fields are present"""
        required = self.get_required_fields_for_year()
        missing = []

        for field in required:
            value = getattr(self, field, None)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(field)

        return len(missing) == 0, missing
```

## LLM Provider Configuration

### Multi-Cloud Strategy

```python
# config/llm_config.py
from enum import Enum
from pydantic_settings import BaseSettings

class LLMProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"
    LITELLM = "litellm"

class LLMConfig(BaseSettings):
    """User-configurable LLM settings"""

    # Primary provider
    provider: LLMProvider = LLMProvider.ANTHROPIC
    model: str = "claude-3-5-sonnet-20241022"

    # API keys
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None

    # Fallback chain
    fallback_chain: list[LLMProvider] = [
        LLMProvider.ANTHROPIC,
        LLMProvider.OPENAI,
        LLMProvider.OLLAMA
    ]

    # Performance settings
    use_prompt_caching: bool = True
    max_concurrent_extractions: int = 20
    timeout_seconds: int = 30

    # Ollama settings (local)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # Cost optimization
    enable_smart_routing: bool = True  # Use litellm for cost optimization
    max_cost_per_citation: float = 0.002  # $0.002 max

    class Config:
        env_file = ".env"
        env_prefix = "LLM_"

# Provider-specific configurations
PROVIDER_CONFIGS = {
    LLMProvider.ANTHROPIC: {
        "models": {
            "high_quality": "claude-3-5-sonnet-20241022",
            "balanced": "claude-3-5-haiku-20241022",
        },
        "supports_caching": True,
        "cost_per_1k_input": 0.003,
        "cost_per_1k_output": 0.015,
    },
    LLMProvider.OPENAI: {
        "models": {
            "high_quality": "gpt-4o",
            "balanced": "gpt-4o-mini",
        },
        "supports_caching": False,
        "cost_per_1k_input": 0.00015,  # gpt-4o-mini
        "cost_per_1k_output": 0.0006,
    },
    LLMProvider.OLLAMA: {
        "models": {
            "default": "llama3.1:8b",
            "large": "llama3.1:70b",
        },
        "supports_caching": False,
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
    }
}
```

## Prompt Engineering

### Cached Prompt Structure

The prompt is designed with two parts:
1. **Cached context** (reused across all citations) - ~2000 tokens
2. **Variable input** (changes per citation) - ~300 tokens

This reduces cost and latency by ~90% after the first citation.

```python
# prompts/citation_extraction.py
CACHED_SYSTEM_PROMPT = """You are an expert genealogist specializing in US Federal Census citations. Your task is to extract structured information from FamilySearch census citations and transform them into Evidence Explained format.

CRITICAL INSTRUCTIONS:
1. Extract all available information from the citation
2. **STRICT EXTRACTION ONLY**: If a field cannot be reliably extracted, set to null and add to missing_fields array
3. **NEVER GUESS**: Do not make assumptions or "best guesses" about missing data
4. Normalize field formats (dates, ED numbers, etc.) only when explicitly present
5. Handle person names carefully:
   - For "Name in household of Other Name", extract primary person only
   - Preserve exactly as written (do not normalize middle initials or suffixes)
   - Preserve prefixes/suffixes: Jr., Sr., III, Dr., Rev.
6. Parse location details accounting for variations (Township, Ward, Independent City)
7. Extract FamilySearch ARK URLs completely
8. Detect NARA publication codes (T623, T624, T625, etc.)
9. Extract FHL microfilm numbers (may have commas: "1,241,311")
10. Calculate confidence scores (0.0-1.0) for each extracted field

REQUIRED FIELDS BY CENSUS YEAR:
- 1790-1840: year, state, county, town_ward, sheet, person_name
- 1850-1870: year, state, county, town_ward, sheet, dwelling_number, person_name
- 1880: year, state, county, town_ward, sheet, family_number, person_name (ED is OPTIONAL)
- 1890: NOT SUPPORTED (most records destroyed, skip this year)
- 1900-1950: year, state, county, town_ward, enumeration_district, sheet, family_number, person_name

COMMON VARIATIONS TO HANDLE:
- ED formats: "ED 95", "enumeration district (ED) 214", "E.D. 95" → normalize to number only
- Dates: "24 July 2015", "Fri Mar 08 08:10:13 UTC 2024" → preserve original
- Sheets: "3B", "11A", "sheet 7" → preserve original
- Locations: "Baltimore (Independent City)", "Olive Township Caldwell village" → preserve full text
- Names: "William H Ijams in household of Margaret E Brannon" → extract primary name only

Return your response as a JSON object matching the CitationExtraction schema.
"""

# Few-shot examples (also cached)
FEW_SHOT_EXAMPLES = [
    {
        "input": {
            "source_name": "Fed Census: 1900, Ohio, Noble [citing sheet 3B, family 57] Ijams, Ella",
            "familysearch_entry": '"United States Census, 1900," database with images, *FamilySearch* (https://familysearch.org/ark:/61903/1:1:MM6X-FGZ : accessed 24 July 2015), Ella Ijams, Olive Township Caldwell village, Noble, Ohio, United States; citing sheet 3B, family 57, NARA microfilm publication T623 (Washington, D.C.: National Archives and Records Administration, n.d.); FHL microfilm 1,241,311.'
        },
        "output": {
            "year": 1900,
            "state": "Ohio",
            "county": "Noble",
            "person_name": "Ella Ijams",
            "town_ward": "Olive Township Caldwell village",
            "enumeration_district": None,  # MISSING - required for 1900
            "sheet": "3B",
            "family_number": "57",
            "familysearch_url": "https://familysearch.org/ark:/61903/1:1:MM6X-FGZ",
            "access_date": "24 July 2015",
            "nara_publication": "T623",
            "fhl_microfilm": "1,241,311",
            "missing_fields": ["enumeration_district"],
            "confidence": {
                "year": 1.0,
                "state": 1.0,
                "county": 1.0,
                "person_name": 1.0,
                "sheet": 1.0,
                "family_number": 1.0
            }
        }
    },
    {
        "input": {
            "source_name": "Fed Census: 1910, Maryland, Baltimore [citing enumeration district (ED) ED 214, sheet 3B] Ijams, William H.",
            "familysearch_entry": '"United States Census, 1910," database with images, *FamilySearch*(https://familysearch.org/ark:/61903/1:1:M2F4-SVS : accessed 27 November 2015), William H Ijams in household of Margaret E Brannon, Baltimore Ward 13, Baltimore (Independent City), Maryland, United States; citing enumeration district (ED) ED 214, sheet 3B, NARA microfilm publication T624 (Washington, D.C.: National Archives and Records Administration, n.d.); FHL microfilm 1,374,570.'
        },
        "output": {
            "year": 1910,
            "state": "Maryland",
            "county": "Baltimore",
            "person_name": "William H. Ijams",
            "town_ward": "Baltimore Ward 13",
            "enumeration_district": "214",
            "sheet": "3B",
            "family_number": None,  # MISSING - required for 1910
            "familysearch_url": "https://familysearch.org/ark:/61903/1:1:M2F4-SVS",
            "access_date": "27 November 2015",
            "nara_publication": "T624",
            "fhl_microfilm": "1,374,570",
            "missing_fields": ["family_number"],
            "confidence": {
                "year": 1.0,
                "state": 1.0,
                "county": 1.0,
                "person_name": 0.95,  # "in household of" adds uncertainty
                "enumeration_district": 1.0,
                "sheet": 1.0
            }
        }
    }
]

# Variable input template (not cached)
VARIABLE_INPUT_TEMPLATE = """
Extract structured information from the following census citation:

SOURCE NAME:
{source_name}

FAMILYSEARCH ENTRY:
{familysearch_entry}

Return a JSON object matching the CitationExtraction schema. Remember to populate the missing_fields array with any required fields you cannot extract from the input.
"""
```

### Langchain Implementation

```python
# services/llm_citation_extractor.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_community.llms import Ollama
from langchain_core.output_parsers import PydanticOutputParser
from typing import AsyncIterator
import asyncio

class CitationExtractor:
    """LLM-based citation extraction service"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.llm = self._create_llm(config.provider, config.model)
        self.parser = PydanticOutputParser(pydantic_object=CitationExtraction)
        self.prompt = self._build_prompt()

    def _create_llm(self, provider: LLMProvider, model: str):
        """Create LLM instance based on provider"""
        if provider == LLMProvider.ANTHROPIC:
            return ChatAnthropic(
                model=model,
                api_key=self.config.anthropic_api_key,
                temperature=0,  # Deterministic
                timeout=self.config.timeout_seconds,
            )
        elif provider == LLMProvider.OPENAI:
            return ChatOpenAI(
                model=model,
                api_key=self.config.openai_api_key,
                temperature=0,
                timeout=self.config.timeout_seconds,
            )
        elif provider == LLMProvider.OLLAMA:
            return Ollama(
                model=self.config.ollama_model,
                base_url=self.config.ollama_base_url,
                temperature=0,
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def _build_prompt(self) -> ChatPromptTemplate:
        """Build prompt with cached context"""
        return ChatPromptTemplate.from_messages([
            ("system", CACHED_SYSTEM_PROMPT),
            ("system", "EXAMPLES:\n{examples}"),
            ("user", VARIABLE_INPUT_TEMPLATE),
        ])

    async def extract_citation(
        self,
        source_name: str,
        familysearch_entry: str
    ) -> CitationExtraction:
        """Extract structured data from citation"""
        try:
            # Format prompt
            formatted_prompt = self.prompt.format_messages(
                examples=self._format_examples(),
                source_name=source_name,
                familysearch_entry=familysearch_entry
            )

            # LLM call with structured output
            response = await self.llm.ainvoke(
                formatted_prompt,
                response_format={"type": "json_object"}
            )

            # Parse to Pydantic model
            extraction = self.parser.parse(response.content)

            # Validate completeness and update missing_fields
            is_complete, missing = extraction.validate_completeness()
            if not is_complete:
                extraction.missing_fields = missing

            return extraction

        except Exception as e:
            # Fallback to next provider in chain
            if self.config.fallback_chain:
                return await self._fallback_extract(source_name, familysearch_entry, e)
            raise

    async def _fallback_extract(
        self,
        source_name: str,
        familysearch_entry: str,
        original_error: Exception
    ) -> CitationExtraction:
        """Try fallback providers"""
        for provider in self.config.fallback_chain[1:]:
            try:
                fallback_llm = self._create_llm(provider, PROVIDER_CONFIGS[provider]["models"]["balanced"])
                # Retry with fallback...
                pass
            except Exception:
                continue

        raise original_error

    def _format_examples(self) -> str:
        """Format few-shot examples for prompt"""
        import json
        formatted = []
        for ex in FEW_SHOT_EXAMPLES:
            formatted.append(f"Input: {json.dumps(ex['input'], indent=2)}")
            formatted.append(f"Output: {json.dumps(ex['output'], indent=2)}")
            formatted.append("---")
        return "\n".join(formatted)

    async def extract_batch(
        self,
        citations: list[tuple[str, str]]
    ) -> list[CitationExtraction]:
        """Process multiple citations in parallel"""
        tasks = [
            self.extract_citation(source, entry)
            for source, entry in citations
        ]

        # Limit concurrency
        semaphore = asyncio.Semaphore(self.config.max_concurrent_extractions)

        async def bounded_extract(task):
            async with semaphore:
                return await task

        results = await asyncio.gather(*[bounded_extract(task) for task in tasks])
        return results
```

## Prompt Caching Implementation

### Anthropic Prompt Caching

Claude supports native prompt caching. Mark cacheable content:

```python
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    # Enable caching for system messages
    cache_control={"type": "ephemeral"}
)

# Cached messages (system + examples)
cached_messages = [
    {"role": "system", "content": CACHED_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
    {"role": "system", "content": f"EXAMPLES:\n{formatted_examples}", "cache_control": {"type": "ephemeral"}},
]

# Variable message (not cached)
variable_message = {
    "role": "user",
    "content": VARIABLE_INPUT_TEMPLATE.format(source_name=source, familysearch_entry=entry)
}
```

**Cache Behavior:**
- First request: Full prompt processed (~2000 tokens cached)
- Subsequent requests: Only variable input processed (~300 tokens)
- Cache TTL: 5 minutes (Anthropic default)
- Cost reduction: ~75% per citation after first

### Langchain Caching (Provider-Agnostic)

For providers without native caching, use Langchain's cache:

```python
from langchain.cache import SQLiteCache
from langchain.globals import set_llm_cache

# Cache LLM responses locally
set_llm_cache(SQLiteCache(database_path=".langchain.db"))

# Now all LLM calls are automatically cached
# Same input → instant response from cache
```

## Cost Tracking and Optimization

```python
# services/cost_tracker.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ExtractionCost:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_usd: float
    timestamp: datetime

class CostTracker:
    """Track LLM usage and costs"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.costs: list[ExtractionCost] = []

    def record_extraction(
        self,
        provider: str,
        model: str,
        response_metadata: dict
    ) -> ExtractionCost:
        """Record cost from LLM response"""
        input_tokens = response_metadata.get("token_usage", {}).get("prompt_tokens", 0)
        output_tokens = response_metadata.get("token_usage", {}).get("completion_tokens", 0)
        cached_tokens = response_metadata.get("token_usage", {}).get("cached_tokens", 0)

        # Calculate cost
        config = PROVIDER_CONFIGS[provider]
        cost = (
            (input_tokens - cached_tokens) * config["cost_per_1k_input"] / 1000 +
            output_tokens * config["cost_per_1k_output"] / 1000
        )

        extraction_cost = ExtractionCost(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            cost_usd=cost,
            timestamp=datetime.now()
        )

        self.costs.append(extraction_cost)
        self._save_to_db(extraction_cost)

        return extraction_cost

    def get_session_stats(self) -> dict:
        """Get statistics for current session"""
        if not self.costs:
            return {}

        total_cost = sum(c.cost_usd for c in self.costs)
        total_citations = len(self.costs)
        avg_cost = total_cost / total_citations if total_citations > 0 else 0

        return {
            "total_citations": total_citations,
            "total_cost_usd": round(total_cost, 4),
            "avg_cost_per_citation": round(avg_cost, 4),
            "total_input_tokens": sum(c.input_tokens for c in self.costs),
            "total_output_tokens": sum(c.output_tokens for c in self.costs),
            "cached_tokens": sum(c.cached_tokens for c in self.costs),
            "cache_hit_rate": (
                sum(c.cached_tokens for c in self.costs) /
                sum(c.input_tokens for c in self.costs)
            ) if self.costs else 0
        }
```

## Testing Strategy

### Unit Tests for LLM Integration

```python
# tests/test_citation_extractor.py
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.fixture
def mock_llm():
    """Mock LLM for testing without API calls"""
    llm = AsyncMock()
    llm.ainvoke.return_value = Mock(
        content='{"year": 1900, "state": "Ohio", ...}'
    )
    return llm

@pytest.mark.asyncio
async def test_extract_citation_complete_data(mock_llm):
    """Test extraction with all required fields present"""
    extractor = CitationExtractor(config=test_config)
    extractor.llm = mock_llm

    result = await extractor.extract_citation(
        source_name="Fed Census: 1900, Ohio, Noble [citing sheet 3B, family 57] Ijams, Ella",
        familysearch_entry="..."
    )

    assert result.year == 1900
    assert result.state == "Ohio"
    assert result.missing_fields == ["enumeration_district"]

@pytest.mark.asyncio
async def test_extract_citation_missing_ed():
    """Test that missing ED is detected for 1900 census"""
    # Use real LLM with example that's missing ED
    # Verify missing_fields contains "enumeration_district"
    pass

@pytest.mark.asyncio
async def test_batch_extraction_parallel():
    """Test parallel batch processing"""
    citations = [(f"Source {i}", f"Entry {i}") for i in range(20)]

    start = time.time()
    results = await extractor.extract_batch(citations)
    duration = time.time() - start

    # Should be much faster than sequential (20 * 2s = 40s)
    assert duration < 10  # Parallel should complete in <10s
    assert len(results) == 20

@pytest.mark.asyncio
async def test_fallback_on_error():
    """Test fallback to secondary provider on error"""
    # Mock primary provider to fail
    # Verify fallback provider is used
    pass
```

### Integration Tests

```python
# tests/integration/test_llm_extraction.py
@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_llm_extraction():
    """Test with real LLM (requires API key)"""
    config = LLMConfig()  # Load from .env
    extractor = CitationExtractor(config)

    # Test with actual FamilySearch citation
    result = await extractor.extract_citation(
        source_name="Fed Census: 1900, Ohio, Noble [citing sheet 3B, family 57] Ijams, Ella",
        familysearch_entry=EXAMPLE_1900_CITATION
    )

    # Verify extraction quality
    assert result.year == 1900
    assert result.state == "Ohio"
    assert result.county == "Noble"
    assert "Ijams" in result.person_name
    assert result.sheet == "3B"
    assert result.family_number == "57"
```

## Error Handling and Validation

### Handling LLM Errors

```python
class ExtractionError(Exception):
    """Base exception for extraction errors"""
    pass

class LLMTimeoutError(ExtractionError):
    """LLM request timed out"""
    pass

class ValidationError(ExtractionError):
    """Extracted data failed validation"""
    pass

class InsufficientDataError(ExtractionError):
    """Cannot extract minimum required fields"""
    pass

async def extract_with_validation(
    source_name: str,
    familysearch_entry: str
) -> CitationExtraction:
    """Extract with comprehensive error handling"""
    try:
        # Attempt extraction
        extraction = await extractor.extract_citation(source_name, familysearch_entry)

        # Validate Pydantic model
        extraction.model_validate(extraction)

        # Check minimum data present
        if not extraction.year or not extraction.state or not extraction.county:
            raise InsufficientDataError("Missing critical fields: year, state, or county")

        return extraction

    except asyncio.TimeoutError:
        raise LLMTimeoutError("LLM request timed out after {timeout}s")

    except ValidationError as e:
        # Log validation error, return partial extraction
        logger.error(f"Validation failed: {e}")
        # Allow user to manually correct
        return extraction

    except Exception as e:
        # Log unexpected error
        logger.exception("Unexpected error during extraction")
        raise ExtractionError(f"Extraction failed: {e}")
```

## Performance Monitoring

```python
# services/performance_monitor.py
import time
from dataclasses import dataclass
from typing import Optional

@dataclass
class ExtractionMetrics:
    citation_id: int
    duration_seconds: float
    input_tokens: int
    output_tokens: int
    cached: bool
    provider: str
    success: bool
    error: Optional[str] = None

class PerformanceMonitor:
    """Monitor LLM extraction performance"""

    def __init__(self):
        self.metrics: list[ExtractionMetrics] = []

    async def timed_extraction(
        self,
        citation_id: int,
        extractor: CitationExtractor,
        source_name: str,
        familysearch_entry: str
    ) -> tuple[CitationExtraction, ExtractionMetrics]:
        """Extract with timing"""
        start = time.time()
        error = None

        try:
            result = await extractor.extract_citation(source_name, familysearch_entry)
            success = True
        except Exception as e:
            error = str(e)
            success = False
            raise
        finally:
            duration = time.time() - start

            metrics = ExtractionMetrics(
                citation_id=citation_id,
                duration_seconds=duration,
                input_tokens=0,  # From response metadata
                output_tokens=0,
                cached=False,
                provider=extractor.config.provider,
                success=success,
                error=error
            )

            self.metrics.append(metrics)

        return result, metrics

    def get_summary(self) -> dict:
        """Get performance summary"""
        if not self.metrics:
            return {}

        successful = [m for m in self.metrics if m.success]

        return {
            "total": len(self.metrics),
            "successful": len(successful),
            "failed": len(self.metrics) - len(successful),
            "avg_duration": sum(m.duration_seconds for m in successful) / len(successful),
            "p95_duration": sorted([m.duration_seconds for m in successful])[int(len(successful) * 0.95)],
            "cache_hit_rate": sum(1 for m in successful if m.cached) / len(successful)
        }
```

## Summary

This LLM-based architecture provides:

1. **Flexibility**: Handles citation format variations naturally
2. **Maintainability**: Prompt updates vs. regex rewrites
3. **Cost-Effective**: Prompt caching reduces costs by 75-90%
4. **Configurable**: Multi-cloud support for cost optimization
5. **Robust**: Structured output validation + missing field detection
6. **Transparent**: Cost tracking and performance monitoring

The two-phase approach (LLM extraction → template generation) ensures the best of both worlds: flexible parsing with deterministic output.
