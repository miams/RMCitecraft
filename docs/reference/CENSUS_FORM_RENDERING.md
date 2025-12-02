# Census Form Rendering Architecture

This document describes the architecture for dynamically rendering census forms from data stored in `census.db`.

## Overview

The census form rendering system uses a layered architecture:

1. **Database Layer** (`census_extraction_db.py`) - Raw data storage using EAV pattern
2. **Data Service Layer** (`census_form_service.py`) - Transforms raw data to rendering models
3. **Renderer Layer** (`census_form_renderer.py`) - Combines data with Jinja2 templates
4. **Template Layer** (`templates/census/jinja/`) - Year-specific HTML templates

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Request                              │
│                    (page_id or person_id)                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CensusFormRenderer                             │
│  - render_page(page_id)                                          │
│  - render_for_person(person_id)                                  │
│  - render_multi_page(page_ids)                                   │
└─────────────────────────────────────────────────────────────────┘
                                │
           ┌────────────────────┼────────────────────┐
           ▼                                         ▼
┌─────────────────────────┐            ┌─────────────────────────┐
│  CensusFormDataService  │            │    Jinja2 Templates     │
│  - load_form_context()  │            │    - base.html          │
│  - _load_page()         │            │    - 1950.html          │
│  - _load_persons()      │            │    - (future years)     │
└─────────────────────────┘            └─────────────────────────┘
           │                                         │
           ▼                                         │
┌─────────────────────────┐                         │
│  CensusExtraction       │                         │
│  Repository             │                         │
│  - get_persons_on_page()│                         │
│  - get_person_fields()  │                         │
│  - get_field_quality()  │                         │
└─────────────────────────┘                         │
           │                                         │
           ▼                                         │
┌─────────────────────────┐                         │
│      census.db          │                         │
│  - census_page          │                         │
│  - census_person        │                         │
│  - census_person_field  │                         │
│  - field_quality        │                         │
└─────────────────────────┘                         │
                                                    │
                                                    ▼
                               ┌─────────────────────────────────┐
                               │       Rendered HTML Output       │
                               └─────────────────────────────────┘
```

## Data Models

### CensusFormContext

The top-level context object passed to Jinja2 templates:

```python
@dataclass
class CensusFormContext:
    census_year: int
    pages: list[FormPageData]
    columns: list[FormColumnDef]
    households: list[FormHousehold]
    title: str
    target_person_name: str
    show_quality_indicators: bool
    show_sample_columns: bool
    extracted_at: datetime | None
    familysearch_url: str
    notes: str
```

### FormPageData

Page-level metadata:

```python
@dataclass
class FormPageData:
    page_id: int | None
    census_year: int
    state: str
    county: str
    township_city: str
    enumeration_district: str
    sheet_number: str
    page_number: str
    persons: list[FormPersonRow]
```

### FormPersonRow

Individual person with all fields:

```python
@dataclass
class FormPersonRow:
    person_id: int | None
    line_number: int | None
    is_target: bool
    is_sample_person: bool
    is_head_of_household: bool
    fields: dict[str, FieldValue]
```

### FieldValue

Field value with quality metadata:

```python
@dataclass
class FieldValue:
    value: str | int | None
    quality: FieldQualityLevel
    confidence: float
    note: str
    original_label: str
    is_sample_line_field: bool
```

## Usage Examples

### Basic Page Rendering

```python
from src.rmcitecraft.services.census_form_renderer import render_census_page

# Render page to HTML string
html = render_census_page(page_id=123)

# Save to file with embedded CSS
from pathlib import Path
from src.rmcitecraft.services.census_form_renderer import save_census_html
save_census_html(page_id=123, output_path=Path("output.html"))
```

### Render for Specific Person

```python
from src.rmcitecraft.services.census_form_renderer import CensusFormRenderer

renderer = CensusFormRenderer()
html = renderer.render_for_person(person_id=456)
```

### Multi-Page Rendering

For families spanning multiple pages:

```python
renderer = CensusFormRenderer()
html = renderer.render_multi_page(page_ids=[123, 124])
```

### Custom Template Context

```python
from src.rmcitecraft.services.census_form_service import CensusFormDataService

service = CensusFormDataService()
context = service.load_form_context(page_id=123)

# Modify context as needed
context.show_quality_indicators = False

renderer = CensusFormRenderer()
html = renderer.render_from_context(context, embed_css=True)
```

## Template Structure

### Directory Layout

```
src/rmcitecraft/templates/census/
├── jinja/
│   ├── base.html          # Base template with common structure
│   ├── 1950.html          # 1950 census template
│   └── (future years)
├── static/
│   └── census_forms.css   # Shared CSS styles
└── __init__.py            # Template utilities
```

### Template Inheritance

The 1950 template extends the base template:

```jinja
{% extends "base.html" %}

{% block content %}
<div class="census-form census-1950">
    {# Census form content #}
</div>
{% endblock %}
```

### Accessing Data in Templates

```jinja
{# Access page data #}
{% set page = ctx.primary_page %}
{{ page.state }}
{{ page.county }}
{{ page.enumeration_district }}

{# Loop through persons #}
{% for person in page.persons %}
    {{ person.get_field('full_name') }}
    {{ person.get_field('age') }}
{% endfor %}

{# Check sample persons #}
{% for person in page.persons | selectattr('is_sample_person') %}
    {{ person.get_field('highest_grade_attended') }}
{% endfor %}
```

## Quality Indicators

Field values include quality metadata:

```jinja
{% set fv = person.get_field_value('full_name') %}
{% if fv.has_quality_issue %}
    <span class="{{ fv.css_class }}">{{ fv.value }}</span>
    <span class="quality-badge {{ fv.quality.value }}"></span>
{% else %}
    {{ fv.value }}
{% endif %}
```

Quality levels:
- `verified` - Human-verified, high confidence
- `clear` - Machine-extracted, clearly legible
- `uncertain` - Readable but uncertain
- `damaged` - Source is damaged/faded
- `illegible` - Cannot be read

## CSS Classes

### Row Classes

- `.data-row` - Base row styling
- `.sample-line` - Sample line person (1950: lines 1, 6, 11, 16, 21, 26)
- `.head-row` - Head of household
- `.target-row` - Target person (highlighted)

### Quality Classes

- `.quality-verified` - Verified fields
- `.quality-clear` - Clear fields
- `.quality-uncertain` - Yellow background
- `.quality-damaged` - Red background
- `.quality-illegible` - Gray, italic

## Adding New Census Years

1. Create template file `templates/census/jinja/YYYY.html`
2. Add column definitions in `models/census_form_data.py`:
   ```python
   COLUMNS_YYYY = [
       FormColumnDef(name="...", column_number="...", label="..."),
   ]
   ```
3. Update `get_columns_for_year()` function
4. Add CSS for year-specific grid layout in `census_forms.css`

## File Locations

| File | Purpose |
|------|---------|
| `models/census_form_data.py` | Data models for rendering |
| `services/census_form_service.py` | Data loading from census.db |
| `services/census_form_renderer.py` | HTML rendering with Jinja2 |
| `templates/census/jinja/*.html` | Jinja2 templates |
| `templates/census/static/census_forms.css` | Shared CSS |
| `database/census_extraction_db.py` | Database models and repository |

## Related Documentation

- [CENSUS_EXTRACTION_DATABASE_SCHEMA.md](CENSUS_EXTRACTION_DATABASE_SCHEMA.md) - Database schema
- [CENSUS_BATCH_PROCESSING_ARCHITECTURE.md](../architecture/CENSUS_BATCH_PROCESSING_ARCHITECTURE.md) - Extraction workflow
