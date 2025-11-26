# RootsMagic Database Patterns

Common SQL patterns and code examples for working with the RootsMagic database.

## Database Connection

**CRITICAL: Always load ICU extension for RMNOCASE collation support.**

```python
import sqlite3

def connect_rmtree(db_path, extension_path='./sqlite-extension/icu.dylib'):
    """Connect to RootsMagic database with RMNOCASE collation support."""
    conn = sqlite3.connect(db_path)

    # Load ICU extension and register RMNOCASE collation
    conn.enable_load_extension(True)
    conn.load_extension(extension_path)
    conn.execute(
        "SELECT icu_load_collation('en_US@colStrength=primary;caseLevel=off;normalization=on','RMNOCASE')"
    )
    conn.enable_load_extension(False)

    return conn

# Usage
conn = connect_rmtree('data/Iiams.rmtree')
cursor = conn.cursor()
cursor.execute("SELECT Surname FROM NameTable ORDER BY Surname COLLATE RMNOCASE LIMIT 10")
```

See `sqlite-extension/python_example.py` for complete working examples.

## Free-Form Citation Architecture

For free-form sources (TemplateID=0), RootsMagic stores Footnote, ShortFootnote, and Bibliography in **SourceTable.Fields BLOB**, NOT in CitationTable TEXT fields.

### Citation Storage Locations

| TemplateID | Location | Content |
|------------|----------|---------|
| 0 (free-form) | SourceTable.Fields BLOB | Footnote, ShortFootnote, Bibliography (XML) |
| 0 (free-form) | CitationTable.Fields BLOB | "Page" field with FamilySearch citation (XML) |
| >0 (template) | CitationTable TEXT fields | Footnote, ShortFootnote, Bibliography |

### Reading Free-Form Citation Fields

```python
import xml.etree.ElementTree as ET

# Get citation's source
cursor.execute("""
    SELECT s.SourceID, s.TemplateID, s.Fields, c.Fields
    FROM CitationTable c
    JOIN SourceTable s ON c.SourceID = s.SourceID
    WHERE c.CitationID = ?
""", (citation_id,))

source_id, template_id, source_fields, citation_fields = cursor.fetchone()

if template_id == 0:  # Free-form source
    # Parse SourceTable.Fields for Footnote/ShortFootnote/Bibliography
    root = ET.fromstring(source_fields.decode('utf-8'))
    footnote = root.find('.//Field[Name="Footnote"]/Value').text
    short_footnote = root.find('.//Field[Name="ShortFootnote"]/Value').text
    bibliography = root.find('.//Field[Name="Bibliography"]/Value').text

    # Parse CitationTable.Fields for "Page" (FamilySearch citation)
    root = ET.fromstring(citation_fields.decode('utf-8'))
    familysearch_citation = root.find('.//Field[Name="Page"]/Value').text
```

### Writing Generated Citations (Free-Form Sources)

```python
# For TemplateID=0, write to SourceTable.Fields BLOB, not CitationTable
xml_content = f"""<Root><Fields>
<Field><Name>Footnote</Name><Value>{footnote}</Value></Field>
<Field><Name>ShortFootnote</Name><Value>{short_footnote}</Value></Field>
<Field><Name>Bibliography</Name><Value>{bibliography}</Value></Field>
</Fields></Root>"""

cursor.execute("""
    UPDATE SourceTable
    SET Fields = ?
    WHERE SourceID = ?
""", (xml_content.encode('utf-8'), source_id))
```

## Census Events: Shared Facts

Census records in RootsMagic are often **shared facts** (witnesses). The census event is owned by one person (usually head of household) and shared with other household members via the WitnessTable.

### Finding a Person's Census Citations

```python
# Person may own the event OR be a witness to someone else's event
# Must check both EventTable (owned) and WitnessTable (shared)

def get_person_census_citations(cursor, person_id):
    """Get all census citations for a person (owned and witnessed)."""

    # Option 1: Person owns the census event
    cursor.execute("""
        SELECT e.EventID, c.CitationID, s.Name
        FROM EventTable e
        JOIN CitationLinkTable cl ON e.EventID = cl.OwnerID AND cl.OwnerType = 2
        JOIN CitationTable c ON cl.CitationID = c.CitationID
        JOIN SourceTable s ON c.SourceID = s.SourceID
        WHERE e.OwnerID = ? AND e.OwnerType = 0 AND e.EventType = 18
    """, (person_id,))
    owned = cursor.fetchall()

    # Option 2: Person is a witness to someone else's census event
    cursor.execute("""
        SELECT e.EventID, c.CitationID, s.Name
        FROM WitnessTable w
        JOIN EventTable e ON w.EventID = e.EventID
        JOIN CitationLinkTable cl ON e.EventID = cl.OwnerID AND cl.OwnerType = 2
        JOIN CitationTable c ON cl.CitationID = c.CitationID
        JOIN SourceTable s ON c.SourceID = s.SourceID
        WHERE w.PersonID = ? AND e.EventType = 18
    """, (person_id,))
    shared = cursor.fetchall()

    return owned + shared
```

## Key Database Conventions

1. **RMNOCASE collation**: Required for text fields (Surname, Given, Name, CitationName)
2. **UTCModDate**: Always check before updates to detect conflicts
3. **MediaPath symbols**:
   - `?` = Media Folder (configured in `.env` as `RM_MEDIA_ROOT_DIRECTORY`)
   - `~` = User's home directory
   - `*` = Folder containing RM database
4. **Store relative paths**, not absolute
5. **Integer columns**: Use 0, not NULL (RootsMagic requires this)
6. **SortDate**: BIGINT type, not INTEGER

## OwnerType Values

Used in CitationLinkTable, MediaLinkTable, and other link tables:

| OwnerType | Entity |
|-----------|--------|
| 0 | Person |
| 1 | Family |
| 2 | Event |
| 3 | Source |
| 4 | Citation |
| 5 | Place |
| 6 | Name |
| 7 | MediaLink |

## MediaType Values

Used in MultimediaTable:

| MediaType | Description |
|-----------|-------------|
| 1 | Image |
| 2 | File |
| 3 | Sound |
| 4 | Video |

---

**Related Documentation:**
- [Schema Reference](./schema-reference.md) - Complete table and field documentation
- [Database Testing](./DATABASE_TESTING.md) - Integrity testing methodology
- [Batch State Schema](./BATCH_STATE_DATABASE_SCHEMA.md) - Batch processing state database
