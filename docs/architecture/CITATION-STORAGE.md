# RootsMagic Citation Storage Architecture

**Critical Reference for RMCitecraft Development**

This document explains how RootsMagic stores citation data for free-form sources (TemplateID=0), which includes all Federal Census citations used in this project.

---

## Overview

RootsMagic uses **different storage locations** for citations depending on whether they use templates or are free-form:

| Source Type | TemplateID | Footnote Storage | Input Citation Storage |
|-------------|------------|------------------|------------------------|
| Template-based | > 0 | `CitationTable.Footnote` (TEXT) | `CitationTable.Fields` (BLOB) |
| **Free-form (Census)** | **0** | **`SourceTable.Fields` (BLOB)** | **`CitationTable.Fields` (BLOB)** |

**All Federal Census citations in RMCitecraft use free-form sources (TemplateID=0).**

---

## Free-Form Citation Architecture

### Storage Locations

#### 1. SourceTable.Fields BLOB (Output)
Stores **generated** Evidence Explained citations:
- Footnote
- ShortFootnote
- Bibliography

#### 2. CitationTable.Fields BLOB (Input)
Stores **scraped** FamilySearch citation in "Page" field

#### 3. CitationTable TEXT Fields (Not Used for TemplateID=0)
- `CitationTable.Footnote` - Empty
- `CitationTable.ShortFootnote` - Empty
- `CitationTable.Bibliography` - Empty

**These TEXT fields are only used for template-based sources (TemplateID > 0).**

---

## XML Structure

### SourceTable.Fields BLOB (Generated Citations)

```xml
<Root>
  <Fields>
    <Field>
      <Name>Footnote</Name>
      <Value>1930 U.S. census, Greene County, Pennsylvania, Jefferson Township, enumeration district (ED) 30-17, sheet 13-A, line 15, George B Iams; imaged, "United States Census, 1930," &lt;i&gt;FamilySearch&lt;/i&gt;, (https://www.familysearch.org/ark:/61903/1:1:XH3Z-4J8 : accessed 7 November 2020).</Value>
    </Field>
    <Field>
      <Name>ShortFootnote</Name>
      <Value>1930 U.S. census, Greene Co., Pa., pop. sch., Jefferson Township, E.D. 30-17, sheet 13-A, George B Iams.</Value>
    </Field>
    <Field>
      <Name>Bibliography</Name>
      <Value>U.S. Pennsylvania. Greene County. 1930 U.S Census. Population Schedule. Imaged. "1930 United States Federal Census". &lt;i&gt;FamilySearch&lt;/i&gt; https://www.familysearch.org/ark:/61903/1:1:XH3Z-4J8 : 2020.</Value>
    </Field>
  </Fields>
</Root>
```

### CitationTable.Fields BLOB (Input from FamilySearch)

```xml
<Root>
  <Fields>
    <Field>
      <Name>Page</Name>
      <Value>"United States Census, 1930," database with images, FamilySearch (https://familysearch.org/ark:/61903/1:1:XH3Z-4J8 : accessed 7 November 2020), George B Iams, Jefferson, Greene, Pennsylvania, United States; citing enumeration district (ED) ED 17, sheet 13A, line 15, family 281, NARA microfilm publication T626 (Washington D.C.: National Archives and Records Administration, 2002), roll 2044; FHL microfilm 2,341,778.</Value>
    </Field>
  </Fields>
</Root>
```

---

## Code Examples

### Reading Citations from Database

```python
import sqlite3
import xml.etree.ElementTree as ET

def get_citation_data(citation_id):
    """Read both input and output citation data."""

    cursor.execute("""
        SELECT s.SourceID, s.TemplateID, s.Fields, c.Fields
        FROM CitationTable c
        JOIN SourceTable s ON c.SourceID = s.SourceID
        WHERE c.CitationID = ?
    """, (citation_id,))

    source_id, template_id, source_fields, citation_fields = cursor.fetchone()

    if template_id != 0:
        raise ValueError("This function only handles free-form sources (TemplateID=0)")

    # Parse SourceTable.Fields for generated citations
    if source_fields:
        root = ET.fromstring(source_fields.decode('utf-8'))
        footnote = root.find('.//Field[Name="Footnote"]/Value')
        short_footnote = root.find('.//Field[Name="ShortFootnote"]/Value')
        bibliography = root.find('.//Field[Name="Bibliography"]/Value')

        generated = {
            'footnote': footnote.text if footnote is not None and footnote.text else "",
            'short_footnote': short_footnote.text if short_footnote is not None and short_footnote.text else "",
            'bibliography': bibliography.text if bibliography is not None and bibliography.text else ""
        }
    else:
        generated = {'footnote': "", 'short_footnote': "", 'bibliography': ""}

    # Parse CitationTable.Fields for FamilySearch citation
    if citation_fields:
        root = ET.fromstring(citation_fields.decode('utf-8'))
        page_field = root.find('.//Field[Name="Page"]/Value')
        familysearch_citation = page_field.text if page_field is not None and page_field.text else ""
    else:
        familysearch_citation = ""

    return {
        'source_id': source_id,
        'familysearch_citation': familysearch_citation,
        **generated
    }
```

### Writing Generated Citations to Database

```python
import html

def write_generated_citations(source_id, footnote, short_footnote, bibliography):
    """Write generated Evidence Explained citations to SourceTable.Fields BLOB."""

    # Escape XML entities
    footnote_escaped = html.escape(footnote)
    short_escaped = html.escape(short_footnote)
    bib_escaped = html.escape(bibliography)

    # Build XML structure
    xml_content = f"""<Root><Fields>
<Field><Name>Footnote</Name><Value>{footnote_escaped}</Value></Field>
<Field><Name>ShortFootnote</Name><Value>{short_escaped}</Value></Field>
<Field><Name>Bibliography</Name><Value>{bib_escaped}</Value></Field>
</Fields></Root>"""

    # Update SourceTable.Fields BLOB
    cursor.execute("""
        UPDATE SourceTable
        SET Fields = ?, UTCModDate = (julianday('now') - 2415018.5)
        WHERE SourceID = ?
    """, (xml_content.encode('utf-8'), source_id))

    conn.commit()
```

### Complete Workflow Example

```python
def process_citation(citation_id):
    """Complete workflow: read input, generate citations, write output."""

    # 1. Read input data
    data = get_citation_data(citation_id)
    familysearch_citation = data['familysearch_citation']
    source_id = data['source_id']

    # 2. Parse FamilySearch citation with LLM
    extraction = llm_parser.extract(familysearch_citation)

    # 3. Get place details from EventTable
    place_details = get_event_place(citation_id)

    # 4. Generate Evidence Explained citations
    footnote = generate_footnote(extraction, place_details)
    short_footnote = generate_short_footnote(extraction, place_details)
    bibliography = generate_bibliography(extraction, place_details)

    # 5. Write generated citations to database
    write_generated_citations(source_id, footnote, short_footnote, bibliography)
```

---

## Census Events and Shared Facts

### Census as Shared Events

Census records in RootsMagic are typically **shared facts** (witnesses). The census event is owned by one person (usually head of household) and shared with other household members via WitnessTable.

### Finding All Census Citations for a Person

```python
def get_person_census_citations(person_id):
    """Get all census citations for a person (owned + shared events)."""

    # Owned census events (person owns the event)
    cursor.execute("""
        SELECT e.EventID, c.CitationID, s.SourceID, s.Name, 'owned' as relationship
        FROM EventTable e
        JOIN CitationLinkTable cl ON e.EventID = cl.OwnerID AND cl.OwnerType = 2
        JOIN CitationTable c ON cl.CitationID = c.CitationID
        JOIN SourceTable s ON c.SourceID = s.SourceID
        WHERE e.OwnerID = ?
        AND e.OwnerType = 0
        AND e.EventType = 18
    """, (person_id,))
    owned = cursor.fetchall()

    # Shared census events (person is a witness)
    cursor.execute("""
        SELECT e.EventID, c.CitationID, s.SourceID, s.Name, 'witness' as relationship
        FROM WitnessTable w
        JOIN EventTable e ON w.EventID = e.EventID
        JOIN CitationLinkTable cl ON e.EventID = cl.OwnerID AND cl.OwnerType = 2
        JOIN CitationTable c ON cl.CitationID = c.CitationID
        JOIN SourceTable s ON c.SourceID = s.SourceID
        WHERE w.PersonID = ?
        AND e.EventType = 18
    """, (person_id,))
    shared = cursor.fetchall()

    return owned + shared
```

### Example: George B Iams (PersonID 3447)

```python
# PersonID 3447 (George B Iams) shares a 1930 census event
# EventID 24124 is owned by PersonID 3447
# CitationID 9816 is linked to EventID 24124

# George Edward Iams (PersonID 3330) is a witness to EventID 29424
# EventID 29424 is owned by PersonID 3001 (Hattie Ellen Porter)
# PersonID 3330 appears in WitnessTable for EventID 29424
```

---

## Database Tables Reference

### SourceTable
| Field | Type | Purpose |
|-------|------|---------|
| SourceID | INTEGER | Primary key |
| Name | TEXT | Source name (e.g., "Fed Census: 1930, Pennsylvania, Greene...") |
| TemplateID | INTEGER | 0 = Free-form, >0 = Template-based |
| Fields | BLOB | **Stores Footnote/ShortFootnote/Bibliography for TemplateID=0** |

### CitationTable
| Field | Type | Purpose |
|-------|------|---------|
| CitationID | INTEGER | Primary key |
| SourceID | INTEGER | Foreign key to SourceTable |
| Footnote | TEXT | Only used for TemplateID > 0 |
| ShortFootnote | TEXT | Only used for TemplateID > 0 |
| Bibliography | TEXT | Only used for TemplateID > 0 |
| Fields | BLOB | **Stores "Page" field with FamilySearch citation for TemplateID=0** |

### EventTable
| Field | Type | Purpose |
|-------|------|---------|
| EventID | INTEGER | Primary key |
| EventType | INTEGER | 18 = Census (FK to FactTypeTable) |
| OwnerID | INTEGER | PersonID who owns this event |
| OwnerType | INTEGER | 0 = Person, 1 = Family |
| PlaceID | INTEGER | FK to PlaceTable |

### WitnessTable
| Field | Type | Purpose |
|-------|------|---------|
| WitnessID | INTEGER | Primary key |
| EventID | INTEGER | FK to EventTable (the shared event) |
| PersonID | INTEGER | FK to PersonTable (person sharing the event) |
| Role | INTEGER | FK to RoleTable (witness role type) |

### CitationLinkTable
| Field | Type | Purpose |
|-------|------|---------|
| LinkID | INTEGER | Primary key |
| CitationID | INTEGER | FK to CitationTable |
| OwnerType | INTEGER | 2 = Event, 0 = Person, 4 = Citation |
| OwnerID | INTEGER | FK based on OwnerType (EventID when OwnerType=2) |

---

## Common Mistakes to Avoid

### ❌ WRONG: Writing to CitationTable TEXT fields
```python
# This will NOT work for free-form sources (TemplateID=0)
cursor.execute("""
    UPDATE CitationTable
    SET Footnote = ?, ShortFootnote = ?, Bibliography = ?
    WHERE CitationID = ?
""", (footnote, short, bib, citation_id))
```

### ✅ CORRECT: Writing to SourceTable.Fields BLOB
```python
# This is the correct approach for TemplateID=0
xml_content = f"""<Root><Fields>
<Field><Name>Footnote</Name><Value>{html.escape(footnote)}</Value></Field>
<Field><Name>ShortFootnote</Name><Value>{html.escape(short_footnote)}</Value></Field>
<Field><Name>Bibliography</Name><Value>{html.escape(bibliography)}</Value></Field>
</Fields></Root>"""

cursor.execute("""
    UPDATE SourceTable
    SET Fields = ?
    WHERE SourceID = (SELECT SourceID FROM CitationTable WHERE CitationID = ?)
""", (xml_content.encode('utf-8'), citation_id))
```

### ❌ WRONG: Only checking EventTable for census events
```python
# This misses shared census events where person is a witness
cursor.execute("""
    SELECT EventID FROM EventTable
    WHERE OwnerID = ? AND EventType = 18
""", (person_id,))
```

### ✅ CORRECT: Checking both EventTable and WitnessTable
```python
# Check owned events
cursor.execute("""
    SELECT EventID FROM EventTable
    WHERE OwnerID = ? AND OwnerType = 0 AND EventType = 18
""", (person_id,))
owned = cursor.fetchall()

# Check shared events
cursor.execute("""
    SELECT EventID FROM WitnessTable w
    JOIN EventTable e ON w.EventID = e.EventID
    WHERE w.PersonID = ? AND e.EventType = 18
""", (person_id,))
shared = cursor.fetchall()
```

---

## References

- **Schema Documentation**: `docs/reference/schema-reference.md`
- **BLOB Structure**: `docs/reference/RM11_BLOB_SourceFields.md`, `docs/reference/RM11_BLOB_CitationFields.md`
- **Database Examples**: `sqlite-extension/python_example.py`
- **Project Instructions**: `CLAUDE.md`, `AGENTS.md`

---

**Last Updated**: 2025-10-25
**Project**: RMCitecraft
**Critical**: This architecture is fundamental to the entire application. All citation processing must follow these patterns.
