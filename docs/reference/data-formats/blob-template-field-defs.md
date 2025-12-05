---
priority: reference
topics: [database, census, citation, ui, automation]
---

# RootsMagic 11: SourceTemplateTable.FieldDefs BLOB Structure

**Document Version:** 1.0
**Last Updated:** 2025-01-08
**Related Tables:** SourceTemplateTable
**Field:** FieldDefs (BLOB)

---

## Overview

The `SourceTemplateTable.FieldDefs` BLOB field contains XML data defining the structure of source citation templates in RootsMagic 11. Each template specifies a set of fields that users fill in when creating sources based on that template. These field definitions control how citation data is captured and formatted.

### Key Facts

- **Total Templates in Database:** 433 built-in templates
- **Encoding:** UTF-8 with BOM (byte order mark: `EF BB BF`)
- **Format:** XML with root element `<Root><Fields>...</Fields></Root>`
- **Purpose:** Define structured input fields for different source types (books, census records, websites, etc.)

---

## XML Schema Structure

### Root Structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Root>
  <Fields>
    <Field>
      <FieldName>...</FieldName>
      <DisplayName>...</DisplayName>
      <Type>...</Type>
      <Hint>...</Hint>
      <LongHint>...</LongHint>
      <CitationField>...</CitationField>
    </Field>
    <!-- Multiple Field elements -->
  </Fields>
</Root>
```

### Field Element Structure

Each `<Field>` element contains exactly six child elements:

| Element | Type | Required | Description |
|---------|------|----------|-------------|
| `FieldName` | Text | Yes | Internal field identifier (used in BLOB storage) |
| `DisplayName` | Text | Yes | User-facing label shown in UI |
| `Type` | Text | Yes | Data type: `Text`, `Name`, `Date`, or `Place` |
| `Hint` | Text | Yes | Short help text for the field |
| `LongHint` | Text | Yes | Extended help text with examples (may be empty) |
| `CitationField` | Text | Yes | `True` if field varies per citation, `False` if source-level |

---

## Field Types

Based on analysis of all 433 templates, four field types are used:

| Type | Count | Usage | Examples |
|------|-------|-------|----------|
| **Text** | 3,102 | General text fields | Title, Publisher, Volume, Page |
| **Place** | 447 | Location fields | Publish Place, Repository Location |
| **Date** | 419 | Date fields | Publish Date, Access Date, Record Date |
| **Name** | 243 | Person/organization names | Author, Compiler, Creator |

### Type-Specific Behavior

- **Text**: Free-form text input
- **Name**: Formatted for names with surname/given name parsing (supports multi-part surnames with slashes: `/van Durren/`)
- **Date**: Uses RM11 date format (see RM11_Date_Format.md) with support for ranges, modifiers, qualifiers
- **Place**: Hierarchical place names with comma-delimited format (see RM11_Place_Format.md)

---

## CitationField Flag

The `CitationField` element controls field-level granularity:

- **`False`** (2,817 occurrences): **Source-level field**
  - Value applies to all citations of this source
  - Examples: Author, Title, Publisher, Publish Date
  - Stored in SourceTable.Fields BLOB

- **`True`** (1,394 occurrences): **Citation-level field**
  - Value varies for each citation
  - Examples: Page, Item of Interest, Access Date
  - Stored in CitationTable.Fields BLOB

This distinction allows sources to have invariant information (book metadata) separate from citation-specific details (which page was referenced).

---

## Hint and LongHint Usage

### Hint Pattern

Short instructional text (typically 5-15 words):
- "the author(s) of the book"
- "the page number(s) where the information appears"
- "date you accessed the site"

### LongHint Pattern

Extended help with examples or formatting instructions. Common patterns:

**1. Examples:**
```
e.g. John Doe-May Smith family group sheet
e.g. compiler, editor, transcriber, abstractor, indexer, translator
```

**2. Default values:**
```
[default = FamilySearch]
N.p. [no place] inserted if field blank
n.d. [no date] inserted if field blank
```

**3. Formatting instructions:**
```
full title||shortened title for subsequent footnotes; after double bars || (if no short title, full title is used)
Separate multiple authors with a semicolon, like this:

John Doe;Bill Smith;David Jones
```

**4. Empty:** Many LongHint elements are empty (`<LongHint/>` or `<LongHint></LongHint>`)

---

## Complete Template Example

**Template ID:** 14
**Template Name:** Book, General (Author(s) known)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Root>
  <Fields>
    <Field>
      <FieldName>Author</FieldName>
      <DisplayName>Author</DisplayName>
      <Type>Name</Type>
      <Hint>the author(s) of the book</Hint>
      <LongHint>Separate multiple authors with a semicolon, like this:

John Doe;Bill Smith;David Jones</LongHint>
      <CitationField>False</CitationField>
    </Field>
    <Field>
      <FieldName>Role</FieldName>
      <DisplayName>Role</DisplayName>
      <Type>Text</Type>
      <Hint>(optional) enter the role, only if applicable</Hint>
      <LongHint>e.g. compiler, editor, transcriber, abstractor, indexer, translator</LongHint>
      <CitationField>False</CitationField>
    </Field>
    <Field>
      <FieldName>Title</FieldName>
      <DisplayName>Title</DisplayName>
      <Type>Text</Type>
      <Hint>the title of the book</Hint>
      <LongHint>full title||shortened title for subsequent footnotes; after double bars || (if no short title, full title is used)</LongHint>
      <CitationField>False</CitationField>
    </Field>
    <Field>
      <FieldName>SubTitle</FieldName>
      <DisplayName>Sub-title</DisplayName>
      <Type>Text</Type>
      <Hint>sub-title for the book, if applicable</Hint>
      <LongHint></LongHint>
      <CitationField>False</CitationField>
    </Field>
    <Field>
      <FieldName>SuplAuthor</FieldName>
      <DisplayName>Supplemental author</DisplayName>
      <Type>Name</Type>
      <Hint>name of the supplemental author</Hint>
      <LongHint>supplemental author could be editor, compiler, etc., as entered in Supplemental Role field</LongHint>
      <CitationField>False</CitationField>
    </Field>
    <Field>
      <FieldName>SuplRole</FieldName>
      <DisplayName>Supplemental role</DisplayName>
      <Type>Text</Type>
      <Hint>role of the supplemental author</Hint>
      <LongHint></LongHint>
      <CitationField>False</CitationField>
    </Field>
    <Field>
      <FieldName>Edition</FieldName>
      <DisplayName>Edition</DisplayName>
      <Type>Text</Type>
      <Hint>edition details</Hint>
      <LongHint>e.g. new edition, 2nd edition ||2nd Ed. (shortened for footnotes)</LongHint>
      <CitationField>False</CitationField>
    </Field>
    <Field>
      <FieldName>PubPlace</FieldName>
      <DisplayName>Publish Place</DisplayName>
      <Type>Place</Type>
      <Hint>the place the book was published, if known</Hint>
      <LongHint>N.p. [no place] inserted if field blank</LongHint>
      <CitationField>False</CitationField>
    </Field>
    <Field>
      <FieldName>Publisher</FieldName>
      <DisplayName>Publisher</DisplayName>
      <Type>Text</Type>
      <Hint>the publisher of the book, if known</Hint>
      <LongHint>n.p. [no publisher] inserted if field blank</LongHint>
      <CitationField>False</CitationField>
    </Field>
    <Field>
      <FieldName>PubDate</FieldName>
      <DisplayName>Publish Date</DisplayName>
      <Type>Date</Type>
      <Hint>the date the book was published, if known</Hint>
      <LongHint>n.d. [no date] inserted if field blank</LongHint>
      <CitationField>False</CitationField>
    </Field>
    <Field>
      <FieldName>Page</FieldName>
      <DisplayName>Page</DisplayName>
      <Type>Text</Type>
      <Hint>the page number(s) where the information appears</Hint>
      <LongHint>e.g. 23 or p.23||23 (full version and shortened version for subsequent footnotes)</LongHint>
      <CitationField>True</CitationField>
    </Field>
  </Fields>
</Root>
```

**Field Summary:**
- 11 total fields
- 10 source-level fields (Author, Role, Title, SubTitle, SuplAuthor, SuplRole, Edition, PubPlace, Publisher, PubDate)
- 1 citation-level field (Page)
- Types: 2 Name, 1 Date, 1 Place, 7 Text

---

## Statistical Summary

Based on analysis of 433 templates in the database:

### Template Usage in Iiams.rmtree Database

- **Templates in database:** 433 built-in templates
- **Templates actually used:** 32 templates
- **Sources using templates:** 114 sources

### Field Type Distribution

| Type | Field Count | Percentage |
|------|-------------|------------|
| Text | 3,102 | 74.0% |
| Place | 447 | 10.7% |
| Date | 419 | 10.0% |
| Name | 243 | 5.8% |
| **Total** | **4,211** | **100%** |

### CitationField Distribution

| Value | Field Count | Percentage |
|-------|-------------|------------|
| False (Source-level) | 2,817 | 66.9% |
| True (Citation-level) | 1,394 | 33.1% |
| **Total** | **4,211** | **100%** |

### Unique Field Names

- **Total unique FieldName values:** 515

Common FieldName values include:
- Author, Title, Publisher, PubDate, PubPlace
- Page, Volume, ItemOfInterest
- AccessDate, AccessType, URL
- Creator, RepositoryName, CallNumber
- RecordDate, RecordType, FilingDate

---

## Parsing Code Examples

### Python: Extract Field Definitions

```python
import sqlite3
import xml.etree.ElementTree as ET

def parse_template_field_defs(blob_data):
    """Parse SourceTemplateTable.FieldDefs BLOB to extract field definitions."""
    # Decode UTF-8 with BOM
    xml_text = blob_data.decode('utf-8-sig')

    # Parse XML
    root = ET.fromstring(xml_text)

    # Extract field definitions
    field_defs = []
    for field in root.findall('.//Field'):
        field_def = {
            'field_name': field.find('FieldName').text,
            'display_name': field.find('DisplayName').text,
            'type': field.find('Type').text,
            'hint': field.find('Hint').text,
            'long_hint': field.find('LongHint').text or '',
            'citation_field': field.find('CitationField').text == 'True'
        }
        field_defs.append(field_def)

    return field_defs

# Usage example
db_path = 'path/to/database.rmtree'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT TemplateID, Name, FieldDefs FROM SourceTemplateTable WHERE TemplateID = ?", (14,))
template_id, name, blob = cursor.fetchone()

field_defs = parse_template_field_defs(blob)

print(f"Template: {name}")
for field in field_defs:
    print(f"  {field['field_name']} ({field['type']}) - Citation: {field['citation_field']}")

conn.close()
```

### SQL: Extract Field Count Per Template

```sql
-- Note: Requires custom function to parse XML BLOBs
-- This is conceptual; SQLite doesn't have built-in XML parsing

SELECT
    TemplateID,
    Name,
    LENGTH(FieldDefs) as BlobSize
FROM SourceTemplateTable
ORDER BY TemplateID;
```

### Python: Categorize Fields by Citation Level

```python
def categorize_template_fields(blob_data):
    """Separate source-level and citation-level fields."""
    xml_text = blob_data.decode('utf-8-sig')
    root = ET.fromstring(xml_text)

    source_fields = []
    citation_fields = []

    for field in root.findall('.//Field'):
        field_name = field.find('FieldName').text
        is_citation = field.find('CitationField').text == 'True'

        if is_citation:
            citation_fields.append(field_name)
        else:
            source_fields.append(field_name)

    return {
        'source_fields': source_fields,
        'citation_fields': citation_fields
    }

# Example output for Template 14:
# {
#   'source_fields': ['Author', 'Role', 'Title', 'SubTitle', 'SuplAuthor',
#                     'SuplRole', 'Edition', 'PubPlace', 'Publisher', 'PubDate'],
#   'citation_fields': ['Page']
# }
```

---

## Relationship to Other Tables

### SourceTable.Fields BLOB

The field definitions in `SourceTemplateTable.FieldDefs` determine which fields appear in `SourceTable.Fields` BLOB for template-based sources (TemplateID > 0).

**Source-level fields** (`CitationField=False`) are stored in SourceTable.Fields:

```xml
<Root>
  <Fields>
    <Field>
      <Name>Author</Name>
      <Value>Weaver, Michael E.</Value>
    </Field>
    <Field>
      <Name>Title</Name>
      <Value>The Guard Wars: the 28th Infantry Division in World War II</Value>
    </Field>
    <!-- ... more source-level fields ... -->
  </Fields>
</Root>
```

### CitationTable.Fields BLOB

**Citation-level fields** (`CitationField=True`) are stored in CitationTable.Fields:

```xml
<Root>
  <Fields>
    <Field>
      <Name>Page</Name>
      <Value>157-158</Value>
    </Field>
    <!-- ... more citation-level fields ... -->
  </Fields>
</Root>
```

See `RM11_BLOB_SourceFields.md` and `RM11_BLOB_CitationFields.md` for BLOB storage format.

---

## Template Categories

The 433 templates cover these major categories (examples):

### Books and Publications
- Book, General (Author(s) known) - Template 14
- Book, General (Author(s) unknown) - Template 15
- Book, Reprint - Template 21
- Book, Series - Template 22

### Online Resources
- Website "as book" - Template 197
- Database (online) - Various templates
- Ancestral File, online database - Template 3

### Records
- Birth Certificate - Various templates
- Census Records - Various templates
- Court Records - Template 239
- Marriage Records - Various templates
- Wills - Template 199

### Research Materials
- Letters - Template 111
- Journal Article - Template 103
- Newspaper - Template 141
- Periodical - Template 151
- Thesis - Template 247

### Other
- Artifacts - Templates 4, 5
- Discussion Forums - Template 78
- Find-a-Grave - Template 10014
- Military Records - Template 424

---

## Double-Bar (||) Notation

Many LongHint elements reference `||` (double bars) for specifying **full** and **shortened** versions:

```
full title||shortened title for subsequent footnotes
```

This notation allows:
- First citation: Use full version
- Subsequent citations: Use shortened version after `||`
- If no `||` present: Use full text for all citations

Examples:
- `"The Complete Guide to Genealogy||Complete Guide"`
- `"p. 23||23"` (page formatting)
- `"accessed||acc."` (shortened access type)

This supports Chicago Manual of Style citation conventions for subsequent references.

---

## Notes for AI Agents

1. **Always decode with `utf-8-sig`** to handle the byte order mark (BOM)

2. **CitationField distinction is critical:**
   - `False` = stored in SourceTable.Fields
   - `True` = stored in CitationTable.Fields

3. **Field types control validation:**
   - Name fields expect surname/given name format
   - Date fields use RM11 24-character encoding
   - Place fields use hierarchical comma-delimited format
   - Text fields are free-form

4. **LongHint contains formatting rules:**
   - Look for `||` notation for full/short versions
   - Check for default values (`[default = ...]`)
   - Parse examples (`e.g. ...`)

5. **Template variety is extensive:**
   - 433 built-in templates cover most source types
   - FieldName values are unique to each template type
   - Some templates have 3-4 fields, others have 15-20

6. **Not all templates are used:**
   - In the sample database, only 32 of 433 templates are used
   - Custom templates (TemplateID >= 10000) may exist

---

## Related Documentation

- **RM11_BLOB_SourceFields.md** - SourceTable.Fields BLOB structure
- **RM11_BLOB_CitationFields.md** - CitationTable.Fields BLOB structure (TBD - Task 1.3)
- **RM11_Schema_Reference.md** - Complete schema documentation
- **RM11_Date_Format.md** - Date field encoding specification
- **RM11_Place_Format.md** - Place field format (TBD - Task 5.6)

---

## Validation and Quality Checks

### Template Integrity

1. **All Field elements must have 6 children:** FieldName, DisplayName, Type, Hint, LongHint, CitationField
2. **Type must be valid:** Text, Name, Date, or Place
3. **CitationField must be boolean:** True or False
4. **FieldName must be unique** within a template

### Field Naming Conventions

Common patterns observed:
- CamelCase with no spaces: `FieldName`, `PubDate`, `ItemOfInterest`
- Abbreviations: `Supl` (Supplemental), `Pub` (Publish), `AF` (Ancestral File)
- Compound names: `SuplAuthor`, `PubPlace`, `AccessDate`

---

**End of Document**
