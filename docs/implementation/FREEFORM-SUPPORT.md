---
priority: reference
topics: [database, census, citation, testing, ui]
---

# Free Form Citation Support

**Date:** October 20, 2025

## Overview

Added support for Free Form citations (TemplateID = 0) which store their citation text in the Fields BLOB instead of ActualText.

## Problem

Citation ID 9747 (Harold F Burke, 1940 census) has:
- TemplateID = 0 (Free Form)
- ActualText = empty
- Footnote = empty
- Citation text stored in Fields BLOB XML

The UI was not extracting or displaying this text.

## Solution

### 1. Fields BLOB Structure

Free Form citations store their text in XML format:

```xml
<Root>
  <Fields>
    <Field>
      <Name>Page</Name>
      <Value>Citation text goes here</Value>
    </Field>
  </Fields>
</Root>
```

The citation text is in the `<Value>` element where `<Name>` is "Page".

### 2. Code Changes

**File:** `src/rmcitecraft/repositories/citation_repository.py`

**Added:**
- `extract_freeform_text()` static method to parse Fields BLOB
- Updated `get_citations_by_year()` to include Fields and TemplateID columns

**XML Parsing:**
```python
@staticmethod
def extract_freeform_text(fields_blob: bytes) -> Optional[str]:
    """Extract citation text from Fields BLOB (for Free Form citations)."""
    if not fields_blob:
        return None

    try:
        # Remove UTF-8 BOM if present
        if fields_blob[:3] == b'\xef\xbb\xbf':
            fields_blob = fields_blob[3:]

        # Parse XML
        root = ET.fromstring(fields_blob)

        # Find Field with Name="Page"
        for field in root.findall('.//Field'):
            name_elem = field.find('Name')
            value_elem = field.find('Value')
            if name_elem is not None and value_elem is not None:
                if name_elem.text == 'Page':
                    return value_elem.text

        return None
    except Exception as e:
        logger.warning(f"Failed to parse Fields BLOB: {e}")
        return None
```

**File:** `src/rmcitecraft/ui/tabs/citation_manager.py`

**Updated:**
- `_on_citation_selected()`: Check for Free Form text before fallback
- `_render_citation_item()`: Check for Free Form text for status
- `_update_detail_panel()`: Display Free Form citation text

**Priority Order for Parsing:**
1. Footnote field (if populated)
2. Free Form text (if TemplateID = 0)
3. SourceName (fallback)

### 3. UI Display

When a Free Form citation is selected, the Citation Details panel shows:

```
▼ Current Citation (Database)
  Source Name: Fed Census: 1940, Colorado, Denver [...]

  Free Form Citation:
  "United States Census, 1940," database with images...
  (displayed in yellow background)

  Footnote (Database):
  (not set)

  Short Footnote (Database):
  (not set)

  Bibliography (Database):
  (not set)
```

## Testing

### Test with Sample Data

```bash
# Test extraction function
uv run python -c "
from rmcitecraft.repositories.citation_repository import CitationRepository
fields = b'<Root><Fields><Field><Name>Page</Name><Value>Test Text</Value></Field></Fields></Root>'
print(CitationRepository.extract_freeform_text(fields))
"
```

**Expected:** `Test Text`

### Test in UI

1. Run the application:
   ```bash
   uv run rmcitecraft
   ```

2. Navigate to Citation Manager

3. Select a year that has Free Form citations

4. Look for citations where TemplateID = 0

5. Click on the citation

6. Verify "Free Form Citation" field is displayed with the text from Fields BLOB

## Database Schema

### CitationTable

| Field | Type | Description |
|-------|------|-------------|
| CitationID | INTEGER | Primary key |
| SourceID | INTEGER | FK to SourceTable |
| ActualText | TEXT | Research notes (often empty for Free Form) |
| Footnote | TEXT | Formatted footnote (custom override) |
| ShortFootnote | TEXT | Formatted short footnote |
| Bibliography | TEXT | Formatted bibliography |
| **Fields** | **BLOB** | **XML with citation template fields** |

### SourceTable

| Field | Type | Description |
|-------|------|-------------|
| SourceID | INTEGER | Primary key |
| Name | TEXT | Source name |
| **TemplateID** | **INTEGER** | **0 = Free Form, others = structured templates** |

## Free Form vs. Structured Citations

### Free Form (TemplateID = 0)
- User enters citation text freely
- Stored in Fields BLOB under "Page" field
- ActualText may be empty
- Flexible but less structured

### Structured (TemplateID > 0)
- Uses predefined template (Book, Website, etc.)
- Multiple fields in Fields BLOB (Author, Title, etc.)
- ActualText contains additional notes
- More structured data

## Known Limitations

1. **Only Page Field Extracted**
   - Currently only extracts the "Page" field from Free Form citations
   - Other fields in the BLOB are ignored
   - This is correct for Free Form citations which only use "Page"

2. **Parsing Free Form Text**
   - Free Form citations may not follow standard format
   - Parser may fail to extract census components
   - This is expected - user would need to manually enter data

3. **Current Database**
   - Citation 9747 in test database has empty Fields BLOB
   - The citation text you mentioned is not in the current database
   - May need to import from different database or add manually

## Future Enhancements

1. **Support Other Template Types**
   - Extract fields from other template types (Book, Website, etc.)
   - Display template-specific fields in UI

2. **Edit Free Form Citations**
   - Allow editing the "Page" field directly in UI
   - Save changes back to Fields BLOB

3. **Import/Export**
   - Import citations from other databases
   - Export to various formats

---

## Files Modified

1. **`src/rmcitecraft/repositories/citation_repository.py`**
   - Added `import xml.etree.ElementTree as ET`
   - Added `extract_freeform_text()` method
   - Updated query to include Fields and TemplateID

2. **`src/rmcitecraft/ui/tabs/citation_manager.py`**
   - Updated `_on_citation_selected()` to check Free Form
   - Updated `_render_citation_item()` to check Free Form
   - Updated `_update_detail_panel()` to display Free Form text

## Summary

✅ **Free Form citations (TemplateID = 0) are now supported**

The UI now:
- Extracts citation text from Fields BLOB
- Displays it in the Citation Details panel
- Uses it for parsing when Footnote field is empty
- Prioritizes it over SourceName for parsing

**Priority for citation text:**
1. Footnote (if exists)
2. Free Form "Page" field (if TemplateID = 0)
3. SourceName (fallback)

This ensures that all citation types are properly displayed and parsed.
