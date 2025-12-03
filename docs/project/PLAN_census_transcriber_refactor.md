# Census Transcriber Refactoring Plan

## Overview

Refactor `CensusTranscriber` to implement all 5 architectural recommendations from the evaluation, with comprehensive test coverage.

## Recommendations to Implement

1. **High**: Expand 1950 schema to match 1940's detail level
2. **High**: Split 1910-1930 into individual year schemas
3. **Medium**: Externalize schemas to YAML files
4. **Medium**: Add missing year-specific instructions
5. **Lower**: Refactor to separate concerns

## Implementation Plan

### Phase 1: Create YAML Schema Infrastructure

**Files to Create:**
```
src/rmcitecraft/schemas/
├── __init__.py
└── census/
    ├── __init__.py
    ├── 1790.yaml
    ├── 1800.yaml
    ├── 1810.yaml
    ├── 1820.yaml
    ├── 1830.yaml
    ├── 1840.yaml
    ├── 1850.yaml
    ├── 1860.yaml
    ├── 1870.yaml
    ├── 1880.yaml
    ├── 1900.yaml
    ├── 1910.yaml
    ├── 1920.yaml
    ├── 1930.yaml
    ├── 1940.yaml
    └── 1950.yaml
```

**YAML Schema Format:**
```yaml
# Example: 1940.yaml
year: 1940
era: "individual_with_ed_sheet"
form_structure:
  lines_per_side: 40
  sides: ["A", "B"]
  supplemental_lines: [14, 29]

columns:
  - name: line_number
    column_number: null
    data_type: integer
    description: "Line number (1-40 on each sheet side)"
    required: true

  - name: street_name
    column_number: 1
    data_type: string
    description: "Street name"
    required: false

  # ... all 32+ columns

instructions: |
  1940 CENSUS FORM STRUCTURE:

  The 1940 census sheet has 40 lines per side (A/B)...
  [detailed instructions]

abbreviations:
  "do": "same as above"
  "—": "same as above"
  "O": "Owned"
  "R": "Rented"
  # etc.

valid_values:
  sex: ["M", "F"]
  marital_status: ["S", "M", "Wd", "D"]
  race: ["W", "Neg", "In", "Ch", "Jp", "Fil", "Hin", "Kor"]
```

### Phase 2: Create Schema Data Classes

**File: `src/rmcitecraft/models/census_schema.py`**

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class CensusEra(Enum):
    HOUSEHOLD_ONLY = "household_only"           # 1790-1840
    INDIVIDUAL_NO_ED = "individual_no_ed"       # 1850-1870
    INDIVIDUAL_WITH_ED_SHEET = "individual_with_ed_sheet"  # 1880-1940
    INDIVIDUAL_WITH_ED_PAGE = "individual_with_ed_page"    # 1950

@dataclass
class CensusColumn:
    name: str
    data_type: str
    description: str
    column_number: int | None = None
    required: bool = False
    abbreviations: dict[str, str] | None = None
    valid_values: list[str] | None = None

@dataclass
class FormStructure:
    lines_per_side: int | None = None
    sides: list[str] | None = None
    supplemental_lines: list[int] | None = None
    uses_page: bool = False
    uses_sheet: bool = False

@dataclass
class CensusYearSchema:
    year: int
    era: CensusEra
    columns: list[CensusColumn]
    instructions: str
    form_structure: FormStructure
    abbreviations: dict[str, str] = field(default_factory=dict)
    valid_values: dict[str, list[str]] = field(default_factory=dict)
```

### Phase 3: Create Separated Service Classes

**Files to Create:**
```
src/rmcitecraft/services/census/
├── __init__.py
├── schema_registry.py      # Loads/caches YAML schemas
├── prompt_builder.py       # Builds LLM prompts from schemas
├── response_parser.py      # Parses JSON/markdown responses
├── transcription_service.py # Orchestrates transcription
└── data_validator.py       # Validates extracted data
```

#### 3.1 CensusSchemaRegistry

```python
class CensusSchemaRegistry:
    """Loads and caches census schemas from YAML files."""

    _schemas: dict[int, CensusYearSchema] = {}

    @classmethod
    def get_schema(cls, year: int) -> CensusYearSchema:
        """Get schema for a census year, loading from YAML if needed."""

    @classmethod
    def get_era(cls, year: int) -> CensusEra:
        """Get the census era for a year."""

    @classmethod
    def list_years(cls) -> list[int]:
        """List all available census years."""
```

#### 3.2 CensusPromptBuilder

```python
class CensusPromptBuilder:
    """Builds LLM prompts from census schemas."""

    def build_transcription_prompt(
        self,
        schema: CensusYearSchema,
        target_names: list[str] | None = None,
        target_line: int | None = None,
        sheet: str | None = None,
        enumeration_district: str | None = None,
    ) -> str:
        """Build complete transcription prompt."""

    def _build_schema_section(self, schema: CensusYearSchema) -> str:
        """Build the JSON schema section."""

    def _build_targeting_section(self, ...) -> str:
        """Build targeting hints section."""

    def _build_rules_section(self, schema: CensusYearSchema) -> str:
        """Build transcription rules from schema."""
```

#### 3.3 CensusResponseParser

```python
class CensusResponseParser:
    """Parses LLM responses into structured data."""

    def parse_response(self, response_text: str) -> dict[str, Any]:
        """Parse JSON from LLM response (handles markdown, etc.)"""

    def extract_json(self, text: str) -> str:
        """Extract JSON from text (handles code blocks)."""
```

#### 3.4 CensusDataValidator

```python
class CensusDataValidator:
    """Validates extracted census data against schema."""

    def validate(
        self,
        data: dict[str, Any],
        schema: CensusYearSchema
    ) -> list[str]:
        """Validate data against schema, return warnings."""

    def validate_required_fields(self, ...) -> list[str]:
        """Check all required fields are present."""

    def validate_field_values(self, ...) -> list[str]:
        """Validate field values against constraints."""
```

#### 3.5 CensusTranscriptionService (Refactored)

```python
class CensusTranscriptionService:
    """Orchestrates census transcription using separated concerns."""

    def __init__(
        self,
        provider: LLMProvider | None = None,
        model: str | None = None,
    ):
        self.provider = provider or create_provider(...)
        self.model = model
        self.schema_registry = CensusSchemaRegistry()
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
    ) -> ExtractionResponse:
        """Transcribe census image."""
        schema = self.schema_registry.get_schema(census_year)
        prompt = self.prompt_builder.build_transcription_prompt(
            schema, target_names, target_line, sheet, enumeration_district
        )
        response = self.provider.complete_with_image(prompt, str(image_path), ...)
        data = self.response_parser.parse_response(response.text)
        warnings = self.validator.validate(data, schema)
        # ...
```

### Phase 4: Remove LLMProvider Duplication

**Modify: `src/rmcitecraft/llm/base.py`**

Remove or deprecate `transcribe_census_image()` method, replacing with delegation to `CensusTranscriptionService`.

### Phase 5: Backward Compatibility

**Modify: `src/rmcitecraft/services/census_transcriber.py`**

Keep `CensusTranscriber` as a facade that delegates to the new `CensusTranscriptionService`:

```python
class CensusTranscriber:
    """Census transcriber - delegates to CensusTranscriptionService.

    This class is maintained for backward compatibility.
    New code should use CensusTranscriptionService directly.
    """

    def __init__(self, ...):
        self._service = CensusTranscriptionService(...)

    def transcribe_census(self, ...) -> ExtractionResponse:
        return self._service.transcribe(...)
```

---

## Test Plan

### Unit Tests

**File: `tests/unit/test_census_schema_registry.py`**
- Test loading each year's YAML schema
- Test schema validation
- Test era detection
- Test caching behavior

**File: `tests/unit/test_census_prompt_builder.py`**
- Test prompt generation for each era
- Test targeting section generation
- Test schema section formatting
- Test abbreviation inclusion

**File: `tests/unit/test_census_response_parser.py`**
- Test JSON extraction from plain text
- Test JSON extraction from markdown code blocks
- Test handling of malformed JSON
- Test handling of empty responses

**File: `tests/unit/test_census_data_validator.py`**
- Test required field validation for each era
- Test value validation (age ranges, valid values)
- Test warning generation

**File: `tests/unit/test_census_year_schemas.py`**
- Test each year's schema has required fields
- Test schema structure consistency
- Test era-appropriate fields present/absent

### Integration Tests

**File: `tests/integration/test_census_transcription_service.py`**
- Test full transcription flow (mocked LLM)
- Test different census years
- Test targeting hints

### Functional Tests

**File: `tests/functional/test_census_schema_loading.py`**
- Test all 17 YAML files load correctly
- Test schema validation passes for all years
- Test no duplicate field names

### E2E Tests (Playwright not needed - these are LLM-based)

**File: `tests/e2e/test_census_transcription_e2e.py`** (marked `@pytest.mark.llm`)
- Test real transcription with sample census images
- Test 1940 census image extraction
- Test 1950 census image extraction
- Validate extracted data matches known values

---

## Detailed YAML Schemas by Year

Based on `docs/analysis/CENSUS-COMPLETE-ANALYSIS-1790-1950.md`, here are the schemas:

### Era 1: Household Only (1790-1840)

**Common structure for 1790-1840:**
- Head of household name only
- Statistical tallies by age/sex categories
- Page number (no sheet, no ED)

### Era 2: Individual, No ED (1850-1870)

**1850:**
- First year with individual names
- dwelling_number, family_number
- name, age, sex, color, occupation
- value_real_estate, birthplace
- page_number, line_number

**1860:**
- Same as 1850 plus:
- value_personal_estate

**1870:**
- Same as 1860 plus:
- relationship field appears

### Era 3: Individual, With ED, Sheet (1880-1940)

**1880:**
- First year with Enumeration Districts
- Sheet number (not page)
- relationship_to_head, marital_status added
- father_birthplace, mother_birthplace

**1900:**
- birth_month, birth_year added
- immigration/naturalization fields
- mother_children_born/living

**1910:**
- Similar to 1900
- Industry field

**1920:**
- Similar to 1910
- Year naturalized

**1930:**
- Similar to 1920
- Value of home, radio set
- Veteran status

**1940:**
- Most detailed pre-1950
- 32+ columns with specific positions
- Residence in 1935
- Employment status
- Supplemental questions (lines 14, 29)

### Era 4: Individual, With ED, Page (1950)

**1950:**
- Returns to page numbers (not sheets)
- Uses "stamp" instead of "sheet" in citations
- Enumeration District required
- Industry field
- Residence in 1949

---

## Implementation Order

1. Create `src/rmcitecraft/schemas/` directory structure
2. Create `CensusYearSchema` and related models
3. Create `CensusSchemaRegistry` with YAML loading
4. Write YAML schemas for all 17 years (1790-1950)
5. Create `CensusPromptBuilder`
6. Create `CensusResponseParser`
7. Create `CensusDataValidator`
8. Create `CensusTranscriptionService`
9. Refactor `CensusTranscriber` as facade
10. Remove duplication from `LLMProvider.transcribe_census_image()`
11. Write unit tests
12. Write integration tests
13. Write functional tests
14. Update documentation

---

## Files to Modify

- `src/rmcitecraft/services/census_transcriber.py` - Refactor as facade
- `src/rmcitecraft/llm/base.py` - Remove/deprecate census method

## Files to Create

- `src/rmcitecraft/schemas/__init__.py`
- `src/rmcitecraft/schemas/census/__init__.py`
- `src/rmcitecraft/schemas/census/1790.yaml` through `1950.yaml` (17 files)
- `src/rmcitecraft/models/census_schema.py`
- `src/rmcitecraft/services/census/__init__.py`
- `src/rmcitecraft/services/census/schema_registry.py`
- `src/rmcitecraft/services/census/prompt_builder.py`
- `src/rmcitecraft/services/census/response_parser.py`
- `src/rmcitecraft/services/census/data_validator.py`
- `src/rmcitecraft/services/census/transcription_service.py`
- `tests/unit/test_census_schema_registry.py`
- `tests/unit/test_census_prompt_builder.py`
- `tests/unit/test_census_response_parser.py`
- `tests/unit/test_census_data_validator.py`
- `tests/unit/test_census_year_schemas.py`
- `tests/integration/test_census_transcription_service.py`
- `tests/functional/test_census_schema_loading.py`

## Estimated File Count

- 17 YAML schema files
- 8 Python source files
- 7 test files
- **Total: 32 new files**
