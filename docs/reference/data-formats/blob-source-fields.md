# RootsMagic 11 SourceTable.Fields BLOB Structure

This document describes the XML structure stored in the `SourceTable.Fields` BLOB column.

## Overview

The `SourceTable.Fields` column contains UTF-8 encoded XML that stores source-specific field values. The structure differs based on whether the source uses a template (`TemplateID > 0`) or is free-form (`TemplateID = 0`).

## XML Schema

### Root Structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Root>
  <Fields>
    <Field>
      <Name>FieldName</Name>
      <Value>FieldValue</Value>
    </Field>
    <!-- Additional Field elements -->
  </Fields>
</Root>
```

### Elements

#### Root Element: `<Root>`
- Container for the entire XML document
- Always present
- Contains single `<Fields>` child element

#### Fields Container: `<Fields>`
- Contains zero or more `<Field>` elements
- Each `<Field>` represents one source attribute

#### Field Element: `<Field>`
- Represents a single source field name-value pair
- Contains exactly two child elements: `<Name>` and `<Value>`

#### Field Name: `<Name>`
- Text content is the field name
- Field names depend on TemplateID (see below)

#### Field Value: `<Value>`
- Text content is the field value
- May contain HTML entities (&quot;, &lt;, &gt;, &amp;)
- May be empty string
- Supports rich text formatting in some cases

## Field Types by TemplateID

### Free-Form Sources (TemplateID = 0)

Free-form sources always contain exactly **three fields**:

| Field Name | Description | Content Type |
|------------|-------------|--------------|
| `Footnote` | Full footnote citation | Formatted text with HTML entities |
| `ShortFootnote` | Abbreviated footnote | Formatted text with HTML entities |
| `Bibliography` | Bibliography entry | Formatted text with HTML entities |

**Example:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Root><Fields>
  <Field>
    <Name>Footnote</Name>
    <Value>&quot;New York, Births and Christenings, 1640-1962,&quot; database, &lt;i&gt;FamilySearch&lt;/i&gt; (https://familysearch.org/ark:/61903/1:1:FDPC-K8S : accessed 26 July 2015), William C. Shepherd in entry for Frances Almira Shepherd, 29 Jul 1876; citing BIRTH CERTIFICATES, MANHATTAN, NEW YORK, NEW YORK, reference ; FHL microfilm 1,322,104.</Value>
  </Field>
  <Field>
    <Name>ShortFootnote</Name>
    <Value>&quot;New York, Births and Christenings, 1640-1962,&quot; database, &lt;i&gt;FamilySearch&lt;/i&gt; (https://familysearch.org/ark:/61903/1:1:FDPC-K8S : accessed 26 July 2015), William C. Shepherd.</Value>
  </Field>
  <Field>
    <Name>Bibliography</Name>
    <Value>&quot;New York, Births and Christenings, 1640-1962,&quot; database, &lt;i&gt;FamilySearch&lt;/i&gt; (https://familysearch.org/ark:/61903/1:1:FDPC-K8S : accessed 26 July 2015).</Value>
  </Field>
</Fields></Root>
```

### Template-Based Sources (TemplateID > 0)

Template-based sources contain fields defined by the template. Field names vary by template type.

#### Common Database Template Fields (TemplateID 10001-10005)

| Field Name | Description | Example Value |
|------------|-------------|---------------|
| `Author` | Database author/compiler | "Martin-Rott, Susie" |
| `DatabaseTitle` | Title of database | "Muscatine County, Iowa Civil War Soldiers" |
| `CreatorOwner` | Creator/owner organization | "Ancestry.com" |
| `WebsiteTitle` | Website title | "Ancestry.com" |
| `URL` | Website URL | "http://search.ancestry.com/..." |
| `ItemType` | Type of item | "database" |
| `CreditLine` | Credit/citation line | Various |
| `Series` | Series name | "Iowa, County Marriages, 1838-1934" |
| `Format` | Format type | "database" |
| `WebsiteCreator` | Website creator | "FamilySearch" |
| `Jurisdiction` | Geographic jurisdiction | "Ohio" |
| `Creator` | Creator organization | "FamilySearch" |
| `ItemTitle` | Item title | "Ohio, Marriages, 1800-1958" |
| `ItemAuthor` | Item author | Empty or author name |

**Example (Database):**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Root><Fields>
  <Field>
    <Name>Author</Name>
    <Value>Martin-Rott, Susie</Value>
  </Field>
  <Field>
    <Name>DatabaseTitle</Name>
    <Value>Muscatine County, Iowa Civil War Soldiers</Value>
  </Field>
  <Field>
    <Name>CreatorOwner</Name>
    <Value>Ancestry.com</Value>
  </Field>
  <Field>
    <Name>WebsiteTitle</Name>
    <Value>Muscatine County, Iowa Civil War Soldiers</Value>
  </Field>
  <Field>
    <Name>URL</Name>
    <Value>http://search.ancestry.com/search/db.aspx?dbid=1199</Value>
  </Field>
  <Field>
    <Name>ItemType</Name>
    <Value></Value>
  </Field>
  <Field>
    <Name>CreditLine</Name>
    <Value></Value>
  </Field>
</Fields></Root>
```

#### Book Template Fields (TemplateID 10006-10007)

| Field Name | Description | Example Value |
|------------|-------------|---------------|
| `Author` | Book author | "Karen Boyer" |
| `Role` | Author role | "compiler" |
| `Title` | Book title | "Wilderness Pioneers of America" |
| `SubTitle` | Book subtitle | "genealogy..." |
| `SuplAuthor` | Supplemental author | Additional authors |
| `SuplRole` | Supplemental role | Role of additional authors |
| `Edition` | Edition information | "2nd printing (with addenda)" |
| `PubPlace` | Publication place | "Baltimore, Maryland" |
| `Publisher` | Publisher name | "Gateway Press" |
| `PubDate` | Publication date | "2008" |
| `NewFormat` | New format info | Various |
| `Creator` | Creator | Various |
| `WebsiteTitle` | Website title (if online) | Library catalog title |
| `URL` | URL (if online) | Library catalog URL |

**Example (Book):**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Root><Fields>
  <Field>
    <Name>Author</Name>
    <Value>Karen Boyer</Value>
  </Field>
  <Field>
    <Name>Role</Name>
    <Value></Value>
  </Field>
  <Field>
    <Name>Title</Name>
    <Value>Wilderness Pioneers of America : genealogy</Value>
  </Field>
  <Field>
    <Name>SubTitle</Name>
    <Value></Value>
  </Field>
  <Field>
    <Name>Edition</Name>
    <Value></Value>
  </Field>
  <Field>
    <Name>PubPlace</Name>
    <Value>Baltimore, Maryland</Value>
  </Field>
  <Field>
    <Name>Publisher</Name>
    <Value>Gateway Press</Value>
  </Field>
  <Field>
    <Name>PubDate</Name>
    <Value>2008</Value>
  </Field>
  <Field>
    <Name>WebsiteTitle</Name>
    <Value></Value>
  </Field>
  <Field>
    <Name>URL</Name>
    <Value>https://search.library.wisc.edu/catalog/9910064099...</Value>
  </Field>
</Fields></Root>
```

#### Online Forum Template Fields (TemplateID 78)

| Field Name | Description | Example Value |
|------------|-------------|---------------|
| `ForumName` | Forum name | "Ancestry.com - Surnames - Ijams" |
| `ForumType` | Type of forum | "message board" |
| `URL` | Forum URL | "http://boards.ancestry.com/..." |

## Parsing Guidelines

### Python Example

```python
import sqlite3
import xml.etree.ElementTree as ET

def parse_source_fields(blob_data):
    """Parse SourceTable.Fields BLOB to dictionary"""
    if not blob_data:
        return {}

    # Decode UTF-8 with BOM
    xml_text = blob_data.decode('utf-8-sig')

    # Parse XML
    root = ET.fromstring(xml_text)
    fields_elem = root.find('Fields')

    # Extract field name-value pairs
    fields = {}
    if fields_elem is not None:
        for field in fields_elem.findall('Field'):
            name_elem = field.find('Name')
            value_elem = field.find('Value')
            if name_elem is not None and value_elem is not None:
                field_name = name_elem.text or ''
                field_value = value_elem.text or ''
                fields[field_name] = field_value

    return fields

# Usage
conn = sqlite3.connect('database.rmtree')
cursor = conn.cursor()
cursor.execute("SELECT Fields FROM SourceTable WHERE SourceID = ?", (1,))
row = cursor.fetchone()
if row and row[0]:
    fields = parse_source_fields(row[0])
    print(fields)
```

### SQL Example (Extract as JSON)

```sql
-- SQLite doesn't have native XML parsing, but you can extract the raw text
SELECT
    SourceID,
    Name,
    TemplateID,
    CAST(Fields AS TEXT) as FieldsXML
FROM SourceTable
WHERE Fields IS NOT NULL;
```

## HTML Entity Handling

Values may contain HTML entities that need decoding:

| Entity | Character | Meaning |
|--------|-----------|---------|
| `&quot;` | `"` | Double quote |
| `&lt;` | `<` | Less than |
| `&gt;` | `>` | Greater than |
| `&amp;` | `&` | Ampersand |

HTML tags (like `<i>` for italics) may appear in citation text and should be preserved or converted appropriately for display.

## Field Relationship to SourceTemplateTable

For template-based sources (TemplateID > 0):
- Field names in `SourceTable.Fields` correspond to template field definitions
- Template field definitions are stored in `SourceTemplateTable.FieldDefs` (also a BLOB)
- The template defines which fields appear and in what order
- Empty `<Value>` elements indicate optional fields left blank

For free-form sources (TemplateID = 0):
- Always use Footnote, ShortFootnote, Bibliography fields
- User manually enters formatted citations
- No template constrains the format

## Data Quality Checks

### Validation Queries

**Check for malformed XML:**
```sql
SELECT SourceID, Name
FROM SourceTable
WHERE Fields IS NOT NULL
  AND CAST(Fields AS TEXT) NOT LIKE '<?xml%';
```

**Check for sources with missing Fields:**
```sql
SELECT SourceID, Name, TemplateID
FROM SourceTable
WHERE Fields IS NULL;
```

**Check free-form sources have required fields:**
```python
# Requires Python parsing
def validate_freeform_source(blob_data):
    fields = parse_source_fields(blob_data)
    required = ['Footnote', 'ShortFootnote', 'Bibliography']
    return all(field in fields for field in required)
```

## Common Issues

1. **BOM (Byte Order Mark)**: XML starts with UTF-8 BOM (EFBBBF in hex). Use `utf-8-sig` encoding when decoding.

2. **Empty Values**: Many fields have empty `<Value></Value>` elements. Check for empty strings after parsing.

3. **Whitespace**: Values may contain leading/trailing whitespace. Trim if necessary.

4. **Case Sensitivity**: Field names are case-sensitive in XML. "Author" ≠ "author".

5. **Missing Fields**: Not all template fields will be present. Handle missing fields gracefully.

## Usage in Biography/Timeline Generation

When generating narratives:

1. **Extract citation text**: For free-form sources, use the `Footnote` field directly
2. **Build citations from templates**: For template sources, use SourceTemplateTable to format the fields
3. **Handle empty fields**: Skip empty fields when building citations
4. **Decode HTML**: Convert HTML entities and tags appropriately
5. **Format consistently**: Maintain consistent citation style across narratives

## Related Documentation

- **RM11_BLOB_SourceTemplateFieldDefs.md** - Structure of SourceTemplateTable.FieldDefs
- **RM11_BLOB_CitationFields.md** - Structure of CitationTable.Fields
- **RM11_Schema_Reference.md** - Overall schema documentation
- **RM11_DataDef.yaml** - Field definitions for SourceTable

## Metadata

- **Task**: 1.1 - Extract and document XML schema for SourceTable.Fields
- **Status**: ✓ Completed
- **Database**: Iiams.rmtree (sample database)
- **Date**: 2025-01-08
- **Total Examples Analyzed**: 30 sources (10 free-form, 20 template-based)
