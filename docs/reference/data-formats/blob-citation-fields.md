---
priority: reference
topics: [database, citation, findagrave, ui]
---

# RootsMagic 11: CitationTable.Fields BLOB Structure

**Document Version:** 1.0
**Last Updated:** 2025-01-08
**Related Tables:** CitationTable, SourceTable, SourceTemplateTable
**Field:** Fields (BLOB)

---

## Overview

The `CitationTable.Fields` BLOB field contains XML data storing citation-specific field values in RootsMagic 11. Unlike `SourceTable.Fields` (which stores source-level metadata like author and title), citation fields contain information that varies per citation, such as page numbers, access dates, or specific items of interest.

### Key Facts

- **Total Citations in Sample Database:** 10,838 citations
- **Citations with BLOB Data:** 10,838 (100%)
- **Encoding:** UTF-8 with BOM (byte order mark: `EF BB BF`)
- **Format:** XML with root element `<Root><Fields>...</Fields></Root>`
- **Most Common Pattern:** Single field (95.8% of citations have exactly 1 field)

---

## XML Schema Structure

### Root Structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Root>
  <Fields>
    <Field>
      <Name>...</Name>
      <Value>...</Value>
    </Field>
    <!-- Zero or more Field elements -->
  </Fields>
</Root>
```

### Field Element Structure

Each `<Field>` element contains exactly two child elements:

| Element | Type | Required | Description |
|---------|------|----------|-------------|
| `Name` | Text | Yes | Field name as defined in SourceTemplateTable.FieldDefs |
| `Value` | Text | Yes | Field value (may be empty string) |

**Note:** This is **identical** to the structure used in `SourceTable.Fields` BLOB (see RM11_BLOB_SourceFields.md).

---

## Field Count Distribution

Based on analysis of 10,838 citations:

| Field Count | Citation Count | Percentage | Usage Pattern |
|-------------|----------------|------------|---------------|
| 0 fields | 24 | 0.2% | Empty citations (rare) |
| **1 field** | **10,386** | **95.8%** | **Standard: Page field only** |
| 2 fields | 53 | 0.5% | Page + one other field |
| 3 fields | 110 | 1.0% | Multiple citation details |
| 4 fields | 17 | 0.2% | Complex citations |
| 5 fields | 77 | 0.7% | Rich metadata |
| 6 fields | 25 | 0.2% | Detailed citations |
| 7 fields | 7 | 0.1% | Very detailed |
| 10 fields | 108 | 1.0% | Find-a-Grave citations |
| 11 fields | 30 | 0.3% | Find-a-Grave citations |
| 12 fields | 1 | 0.0% | Maximum observed |

**Key Insight:** The vast majority (95.8%) of citations contain only a **Page** field, reflecting the most common citation pattern: referencing a specific page in a book or document.

---

## Common Field Names

Based on 41 unique field names found across 10,838 citations:

### Most Frequent Fields

| Field Name | Occurrences | Percentage | Typical Usage |
|------------|-------------|------------|---------------|
| **Page** | 10,437 | 96.3% | Page number(s) in source |
| **AccessType** | 226 | 2.1% | How website was accessed (e.g., "accessed", "viewed") |
| **URL** | 211 | 1.9% | Web address for online sources |
| **AccessDate** | 157 | 1.4% | Date website was accessed |
| **ItemOfInterest** | 151 | 1.4% | Specific item/person/event referenced |
| **citedname** | 139 | 1.3% | Name as cited in Find-a-Grave |
| **PersonName** | 139 | 1.3% | Actual person name (Find-a-Grave) |
| **Retrieved** | 139 | 1.3% | Date retrieved (Find-a-Grave) |
| **Attributes** | 139 | 1.3% | Find-a-Grave entry attributes |
| **cemname** | 139 | 1.3% | Cemetery name (Find-a-Grave) |
| **cemloc** | 139 | 1.3% | Cemetery location (Find-a-Grave) |
| **Owner** | 139 | 1.3% | Find-a-Grave memorial owner |
| **photographer** | 139 | 1.3% | Photo credit (Find-a-Grave) |
| **lifetime** | 109 | 1.0% | Birth-death years (Find-a-Grave) |

**Note:** Fields appearing exactly 139 times are all from Find-a-Grave template citations, showing consistent multi-field pattern for that source type.

### Other Notable Fields

- **Date** (71): Generic date field for various templates
- **AccessedDate** (70): Alternative spelling of AccessDate
- **ItemofInterest** (60): Alternative capitalization
- **ShortItem** (53): Shortened form of item description
- **DetailedItem** (53): Detailed form of item description
- **Annotation** (43): Notes or annotations
- **SubmitData** (31): Submission information
- **AFNumbers** (21): Ancestral File numbers
- **OwnerEmail** (29): Email address (Find-a-Grave)
- **SiteUpdated** (29): Last update date (Find-a-Grave)

---

## Citation Patterns by Template Type

### Pattern 1: Book Citations (Most Common)

**Template:** Book, General (Author(s) known) - Template 14, 10006
**Field Count:** 1
**Fields:** Page only

```xml
<Root>
  <Fields>
    <Field>
      <Name>Page</Name>
      <Value>p. 295</Value>
    </Field>
  </Fields>
</Root>
```

**Usage:** 95.8% of citations follow this pattern

---

### Pattern 2: Online Database Citations

**Template:** Ancestral File, online database - Template 3
**Field Count:** 2-3
**Fields:** AccessType, AccessDate, ItemOfInterest

```xml
<Root>
  <Fields>
    <Field>
      <Name>AccessType</Name>
      <Value>accessed</Value>
    </Field>
    <Field>
      <Name>AccessDate</Name>
      <Value>4 February 2012</Value>
    </Field>
    <Field>
      <Name>ItemOfInterest</Name>
      <Value>William Iiams entry (1670-1738)</Value>
    </Field>
  </Fields>
</Root>
```

---

### Pattern 3: Find-a-Grave Citations (Richest Metadata)

**Template:** Find-a-grave - Template 10014
**Field Count:** 10-12
**Fields:** citedname, PersonName, lifetime, URL, Retrieved, Attributes, cemname, cemloc, Owner, photographer, SiteUpdated, OwnerEmail

```xml
<Root>
  <Fields>
    <Field>
      <Name>citedname</Name>
      <Value>Gail Cynthia Shepherd Iams</Value>
    </Field>
    <Field>
      <Name>PersonName</Name>
      <Value>Gail Cynthia Shepherd</Value>
    </Field>
    <Field>
      <Name>URL</Name>
      <Value>http://www.findagrave.com/cgi-bin/fg.cgi?page=gr&amp;GRid=131122515</Value>
    </Field>
    <Field>
      <Name>Retrieved</Name>
      <Value>21 February 2016</Value>
    </Field>
    <Field>
      <Name>Attributes</Name>
      <Value>family links, tombstone photo, and subject photo</Value>
    </Field>
    <Field>
      <Name>SiteUpdated</Name>
      <Value>9 June 2014</Value>
    </Field>
    <Field>
      <Name>cemname</Name>
      <Value>Saint Francis Cemetery</Value>
    </Field>
    <Field>
      <Name>cemloc</Name>
      <Value>Plot: Sec. 800, Plot 21, Row 2, Space 2; Phoenix, Maricopa, Arizona</Value>
    </Field>
    <Field>
      <Name>Owner</Name>
      <Value>miams</Value>
    </Field>
    <Field>
      <Name>OwnerEmail</Name>
      <Value>michael.iams@gmail.com</Value>
    </Field>
    <Field>
      <Name>photographer</Name>
      <Value>Michael Iams</Value>
    </Field>
  </Fields>
</Root>
```

**Find-a-Grave Field Definitions:**
- **citedname**: Name as it appears in Find-a-Grave memorial
- **PersonName**: Standardized person name
- **lifetime**: Birth-death years in format `(YYYY-YYYY)`
- **URL**: Direct link to Find-a-Grave memorial
- **Retrieved**: Date memorial was accessed
- **Attributes**: What information is available (photos, bio, links, etc.)
- **SiteUpdated**: Last update date of memorial
- **cemname**: Cemetery name
- **cemloc**: Plot location within cemetery
- **Owner**: Find-a-Grave user who created/manages memorial
- **OwnerEmail**: Owner's email address
- **photographer**: Photo contributor

---

### Pattern 4: Free-Form Source Citations

**Template:** None (TemplateID = 0)
**Field Count:** 1
**Fields:** Page (even for non-book sources)

```xml
<Root>
  <Fields>
    <Field>
      <Name>Page</Name>
      <Value>Retrieved Feb 4, 2012.</Value>
    </Field>
  </Fields>
</Root>
```

**Note:** Free-form sources still use the "Page" field, but the value may contain any citation detail, not just page numbers.

---

### Pattern 5: Empty Citations

**Field Count:** 0
**Frequency:** 24 citations (0.2%)

```xml
<Root>
  <Fields>
  </Fields>
</Root>
```

**Interpretation:** Citation exists but has no detail values. The citation may rely entirely on source-level information.

---

## Relationship to SourceTemplateTable.FieldDefs

The field names in `CitationTable.Fields` must match field names defined in `SourceTemplateTable.FieldDefs` where `CitationField=True`.

### Source-Level vs Citation-Level Fields

Fields are categorized in the template definition:

- **`CitationField=False`** → Stored in `SourceTable.Fields`
  - Examples: Author, Title, Publisher, PubDate
  - Same for all citations of that source

- **`CitationField=True`** → Stored in `CitationTable.Fields`
  - Examples: Page, ItemOfInterest, AccessDate
  - Varies per citation

See `RM11_BLOB_SourceTemplateFieldDefs.md` for complete template field definitions.

---

## Parsing Code Examples

### Python: Extract Citation Fields

```python
import sqlite3
import xml.etree.ElementTree as ET

def parse_citation_fields(blob_data):
    """Parse CitationTable.Fields BLOB to extract field values."""
    if not blob_data:
        return {}

    # Decode UTF-8 with BOM
    xml_text = blob_data.decode('utf-8-sig')

    # Parse XML
    root = ET.fromstring(xml_text)

    # Extract fields
    fields = {}
    for field in root.findall('.//Field'):
        name = field.find('Name').text
        value_elem = field.find('Value')
        value = value_elem.text if value_elem is not None else ''
        fields[name] = value or ''

    return fields

# Usage example
db_path = 'path/to/database.rmtree'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT CitationID, CitationName, Fields FROM CitationTable WHERE CitationID = ?", (58,))
cit_id, cit_name, blob = cursor.fetchone()

fields = parse_citation_fields(blob)

print(f"Citation: {cit_name}")
for name, value in fields.items():
    print(f"  {name}: {value}")

# Output:
# Citation: p. 295
#   Page: p. 295

conn.close()
```

### Python: Get Complete Citation with Source

```python
def get_complete_citation(citation_id, conn):
    """Retrieve both source-level and citation-level fields."""
    cursor = conn.cursor()

    # Get citation with source information
    cursor.execute("""
        SELECT
            c.CitationID,
            c.CitationName,
            c.Fields as CitationFields,
            s.SourceID,
            s.TemplateID,
            s.Fields as SourceFields,
            st.Name as TemplateName
        FROM CitationTable c
        JOIN SourceTable s ON c.SourceID = s.SourceID
        LEFT JOIN SourceTemplateTable st ON s.TemplateID = st.TemplateID
        WHERE c.CitationID = ?
    """, (citation_id,))

    row = cursor.fetchone()
    cit_id, cit_name, cit_blob, src_id, tmpl_id, src_blob, tmpl_name = row

    # Parse both BLOBs
    citation_fields = parse_citation_fields(cit_blob)
    source_fields = parse_citation_fields(src_blob)  # Same parser works for both

    return {
        'citation_id': cit_id,
        'citation_name': cit_name,
        'source_id': src_id,
        'template_id': tmpl_id,
        'template_name': tmpl_name,
        'source_fields': source_fields,
        'citation_fields': citation_fields
    }

# Example: Citation 58 (book with page number)
citation = get_complete_citation(58, conn)

print(f"Template: {citation['template_name']}")
print(f"\nSource-level fields:")
for name, value in citation['source_fields'].items():
    print(f"  {name}: {value}")

print(f"\nCitation-level fields:")
for name, value in citation['citation_fields'].items():
    print(f"  {name}: {value}")

# Output:
# Template: Book, Reprint (Author(s) known)
#
# Source-level fields:
#   Author: Newman, Harry Wright
#   Title: Anne Arundel Gentry
#   Publisher: ...
#   PubDate: 1970
#
# Citation-level fields:
#   Page: p. 295
```

### SQL: Find Citations Missing Page Numbers

```sql
-- Note: Requires custom function to parse XML
-- This is conceptual; standard SQLite doesn't parse XML

SELECT
    c.CitationID,
    c.CitationName,
    s.SourceID,
    st.Name as TemplateName
FROM CitationTable c
JOIN SourceTable s ON c.SourceID = s.SourceID
LEFT JOIN SourceTemplateTable st ON s.TemplateID = st.TemplateID
WHERE
    s.TemplateID IN (14, 15, 21, 22, 10006)  -- Book templates
    AND (c.Fields IS NULL OR LENGTH(c.Fields) < 100)  -- Likely empty or missing
ORDER BY s.TemplateID, c.CitationID;
```

### Python: Extract Page Numbers

```python
def get_page_number(citation_blob):
    """Extract page number from citation BLOB."""
    fields = parse_citation_fields(citation_blob)
    return fields.get('Page', '')

# Find all citations with page numbers
cursor.execute("SELECT CitationID, CitationName, Fields FROM CitationTable WHERE Fields IS NOT NULL")

for cit_id, cit_name, blob in cursor.fetchall():
    page = get_page_number(blob)
    if page:
        print(f"Citation {cit_id}: {page}")
```

---

## Field Name Variations

Some field names have multiple spellings/capitalizations:

| Canonical | Variations | Count |
|-----------|------------|-------|
| **ItemOfInterest** | ItemofInterest | 151 vs 60 |
| **AccessDate** | AccessedDate | 157 vs 70 |

**Recommendation:** When parsing, normalize field names to canonical form or check for both variants.

---

## Special Characters and Encoding

### HTML Entity Encoding

Field values may contain HTML entities:

```xml
<Field>
  <Name>URL</Name>
  <Value>http://www.findagrave.com/cgi-bin/fg.cgi?page=gr&amp;GRid=131122515</Value>
</Field>
```

**Note:** `&amp;` is encoded as HTML entity. XML parsers automatically decode these.

### Quote Escaping

```xml
<Field>
  <Name>citedname</Name>
  <Value>Theodore &quot;Theo&quot; Joten</Value>
</Field>
```

**Note:** `&quot;` represents double quotes in XML.

---

## Data Quality Indicators

### Empty Field Values

Fields may have empty `<Value>` elements:

```xml
<Field>
  <Name>Page</Name>
  <Value></Value>
</Field>
```

**Interpretation:** Field is defined in template but user didn't fill it in. This is a data quality issue.

### Missing Expected Fields

For template-based sources, compare actual fields against template definition:

```python
def validate_citation_completeness(citation_blob, template_field_defs):
    """Check if citation has all expected citation-level fields."""
    actual_fields = set(parse_citation_fields(citation_blob).keys())
    expected_fields = set(
        field['field_name']
        for field in template_field_defs
        if field['citation_field']
    )

    missing_fields = expected_fields - actual_fields
    return {
        'complete': len(missing_fields) == 0,
        'missing_fields': list(missing_fields)
    }
```

---

## Statistical Summary

### Database-Wide Analysis (Iiams.rmtree)

- **Total citations:** 10,838
- **Citations with BLOB data:** 10,838 (100%)
- **Unique field names:** 41
- **Most common field:** Page (96.3% of citations)
- **Average fields per citation:** 1.04
- **Maximum fields observed:** 12 (single Find-a-Grave citation)

### Template-Specific Patterns

| Template Type | Typical Field Count | Common Fields |
|---------------|---------------------|---------------|
| Books | 1 | Page |
| Online databases | 2-3 | AccessType, AccessDate, ItemOfInterest |
| Find-a-Grave | 10-12 | citedname, PersonName, URL, cemname, cemloc, etc. |
| Free-form | 1 | Page (repurposed) |

---

## Relationship to CitationName Field

The `CitationTable.CitationName` (TEXT field) often duplicates the most important citation field value:

- **Book citations:** CitationName = Page field value
  - Example: CitationName="p. 295", Page field="p. 295"

- **Online citations:** CitationName = access info
  - Example: CitationName="Retrieved Feb 4, 2012.", Page field="Retrieved Feb 4, 2012."

- **Find-a-Grave:** CitationName = person name
  - Example: CitationName="Gail Cynthia Shepherd Iams", citedname field="Gail Cynthia Shepherd Iams"

**Purpose:** CitationName provides quick reference without parsing BLOB.

---

## Notes for AI Agents

1. **Always decode with `utf-8-sig`** to handle the byte order mark (BOM)

2. **95.8% of citations have exactly one field (Page)** - optimize for this common case

3. **Field names are case-sensitive** - "ItemOfInterest" ≠ "ItemofInterest"

4. **Empty values are valid** - check for both missing fields and empty `<Value>` elements

5. **Find-a-Grave citations are richest** - 10-12 fields with detailed metadata

6. **Page field is multipurpose** - in free-form sources, may contain any citation detail

7. **HTML entities are used** - `&amp;`, `&quot;` must be decoded

8. **CitationName often duplicates field values** - can use for quick filtering without BLOB parsing

9. **Field names must match template** - validate against SourceTemplateTable.FieldDefs where CitationField=True

10. **Template ID 0 (free-form) uses simplified structure** - typically just Page field

---

## Data Quality Checks

### Recommended Validation Queries

**1. Find citations with empty Page fields (books):**
```python
# Find book citations with no page number
cursor.execute("""
    SELECT c.CitationID, c.CitationName, s.SourceID
    FROM CitationTable c
    JOIN SourceTable s ON c.SourceID = s.SourceID
    WHERE s.TemplateID IN (14, 15, 21, 22, 10006)
""")

for cit_id, cit_name, src_id in cursor.fetchall():
    fields = parse_citation_fields(get_citation_blob(cit_id))
    if not fields.get('Page', '').strip():
        print(f"Citation {cit_id}: Missing page number")
```

**2. Find citations with missing required fields:**
```python
# Compare actual fields against template expectations
def find_incomplete_citations(conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.CitationID, c.Fields, s.TemplateID, st.FieldDefs
        FROM CitationTable c
        JOIN SourceTable s ON c.SourceID = s.SourceID
        JOIN SourceTemplateTable st ON s.TemplateID = st.TemplateID
        WHERE s.TemplateID > 0
    """)

    for cit_id, cit_blob, tmpl_id, tmpl_blob in cursor.fetchall():
        cit_fields = parse_citation_fields(cit_blob)
        tmpl_fields = parse_template_field_defs(tmpl_blob)

        required = [f for f in tmpl_fields if f['citation_field']]
        missing = [f['field_name'] for f in required if f['field_name'] not in cit_fields]

        if missing:
            print(f"Citation {cit_id} missing: {', '.join(missing)}")
```

**3. Find inconsistent field name spellings:**
```python
# Detect variations like "ItemOfInterest" vs "ItemofInterest"
field_variations = {}
for cit_id, blob in get_all_citation_blobs():
    fields = parse_citation_fields(blob)
    for name in fields.keys():
        normalized = name.lower()
        if normalized not in field_variations:
            field_variations[normalized] = set()
        field_variations[normalized].add(name)

# Report variations
for normalized, variants in field_variations.items():
    if len(variants) > 1:
        print(f"Inconsistent: {variants}")
```

---

## Related Documentation

- **RM11_BLOB_SourceFields.md** - SourceTable.Fields BLOB structure (source-level fields)
- **RM11_BLOB_SourceTemplateFieldDefs.md** - Template field definitions (determines which fields are citation-level)
- **RM11_Schema_Reference.md** - Complete schema documentation
- **RM11_Date_Format.md** - Date field encoding (for AccessDate, Retrieved fields)

---

## Summary

The `CitationTable.Fields` BLOB stores **citation-specific details** that vary per citation, most commonly page numbers. The structure is identical to `SourceTable.Fields` (Name/Value pairs), but the fields stored are those marked `CitationField=True` in the template definition.

**Key takeaways:**
- 95.8% of citations have just a **Page** field
- Find-a-Grave citations are outliers with 10-12 fields
- Field names must match template definitions
- Empty values indicate incomplete data entry
- XML structure is simple and consistent

This BLOB format enables flexible, template-driven citation metadata while maintaining a consistent storage structure across all source types.

---

**End of Document**
